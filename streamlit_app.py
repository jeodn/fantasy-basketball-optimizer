import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from google import genai

from app.analytics.optimization.single_slot import SingleSlotOptimizationStrategy
from app.analytics.scoring.z_score import ZScoreStrategy
from app.config import DATA_DIR, config
from app.domain.roster import Roster
from app.domain.scoring import ScoredPool
from app.domain.stats import ZCategory
from app.ingestion import player_ingestion
from app.repository import file_repository as file_repo

# Set page configuration
st.set_page_config(
    page_title="Fantasy Basketball Advisor & Optimizer",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS styling for modern UI presentation
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #FFFFFF;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #0F172A;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def ensure_data_initialized():
    """
    If running in remote deployment mode (IS_LOCAL is false in st.secrets or env) 
    or if data.json does not exist, run the full pipeline (pull -> rank -> roster -> evaluate).
    Cached via @st.cache_resource so it only executes once on server startup.
    """
    is_local = True
    try:
        sec_val = None
        # Safely attempt to read IS_LOCAL from st.secrets dict or attributes
        if hasattr(st.secrets, "get"):
            sec_val = st.secrets.get("IS_LOCAL")
            if sec_val is None:
                env_dict = st.secrets.get("env")
                if isinstance(env_dict, dict):
                    sec_val = env_dict.get("IS_LOCAL")

        if sec_val is not None:
            is_local = str(sec_val).lower() in ("true", "1", "yes")
    except Exception:
        pass

    if is_local:
        is_local = os.getenv("IS_LOCAL", "true").lower() in ("true", "1", "yes")

    data_file = DATA_DIR / "data.json"

    if not is_local or not data_file.exists():
        with st.spinner("Initializing pipeline data on remote startup (pull -> rank -> roster -> evaluate)..."):
            from app.pipeline import commands

            commands.pull()
            commands.rank()
            commands.roster()
            commands.evaluate()


@st.cache_data
def load_scored_pool_data():
    """Load player pool, apply ZScoreStrategy, and return ScoredPool and DataFrame."""
    pool = player_ingestion.load_pool_from_file(DATA_DIR / "data.json")
    strategy = ZScoreStrategy(
        weights=config.scoring.category_weights,
        punt_categories=config.scoring.punt_categories,
        stats_source=config.scoring.stats_source,
    )
    scored_pool = strategy.score(pool)
    df = scored_pool.to_dataframe()
    return scored_pool, df


def get_gemini_response(api_key: str, context: str, prompt: str) -> str:
    """Query Gemini AI model with fantasy basketball context."""
    try:
        client = genai.Client(api_key=api_key)
        full_prompt = (
            f"Context:\n{context}\n\nUser Question: {prompt}\n\n"
            "Please answer as a fantasy basketball expert advisor."
        )
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite", contents=full_prompt
        )
        return response.text
    except Exception as e:
        return f"Error communicating with Gemini: {e}"


def main():
    # Title & Header
    st.markdown(
        "<div class='main-header'>Fantasy Basketball Optimizer & Advisor</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='sub-header'>Category-Driven Head-to-Head Optimization | Daily Projections | AI Matchup Analysis</div>",
        unsafe_allow_html=True,
    )

    # Initialize data pipeline on remote startup or if data is missing
    ensure_data_initialized()

    # Load Data
    try:
        scored_pool, df = load_scored_pool_data()
    except Exception as e:
        st.error(f"Error loading base player pool data: {e}")
        return

    # Name-to-ID mapping dictionary
    player_name_to_id = {}
    player_id_to_name = {}
    for pid, sp in scored_pool.scored_players.items():
        player_name_to_id[sp.player.name] = pid
        player_id_to_name[pid] = sp.player.name

    all_player_names = sorted(list(player_name_to_id.keys()))

    # Default my_team player names from config.yaml
    default_my_team_ids = set(config.roster.my_team)
    default_my_team_names = [
        player_id_to_name[pid]
        for pid in config.roster.my_team
        if pid in player_id_to_name
    ]

    # Sidebar settings
    st.sidebar.header("Global Settings")
    gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password")
    st.sidebar.caption("API key is used exclusively for the AI Assistant tab.")

    st.sidebar.markdown("---")
    st.sidebar.header("My Team Roster Editor")
    selected_my_team_names = st.sidebar.multiselect(
        "Edit Active Roster Players",
        options=all_player_names,
        default=default_my_team_names,
        help="Modify your team roster in real time. Updates optimization, team totals, and comparisons.",
    )

    # Active My Team Player IDs
    active_my_team_ids = [
        player_name_to_id[name] for name in selected_my_team_names
    ]

    # Load current user roster snapshot from selection
    my_roster = Roster(name="my_team", player_ids=active_my_team_ids)
    my_snapshot = scored_pool.get_roster_snapshot(my_roster)

    # Primary Top Navigation Tabs
    tab_opt, tab_daily, tab_roster, tab_ai, tab_league = st.tabs([
        "Roster Optimizer",
        "Daily Projections & Matchup",
        "My Team Roster",
        "AI Assistant",
        "League Explorer & Comparison",
    ])

    # Canonical 9 Z-Score Categories
    standard_z_cats = [z.value for z in ZCategory]

    # Map raw config punt categories (e.g. "TO") to z-categories (e.g. "zTO")
    default_punts = [
        f"z{c}" if not c.startswith("z") else c for c in config.scoring.punt_categories
    ]
    default_punts = [c for c in default_punts if c in standard_z_cats]

    # =========================================================================
    # TAB 1: ROSTER OPTIMIZER (FEATURED FRONT & CENTER)
    # =========================================================================
    with tab_opt:
        st.header("Roster Optimization Engine")
        st.markdown(
            "Re-evaluate your roster slot-by-slot using greedy coordinate descent optimization "
            "to maximize your Head-to-Head category win probability."
        )

        # Behind the Math Educational Blurb
        with st.expander("Methodology:", expanded=False):
            st.markdown(
                r"""
                ### Head-to-Head Category Win Logic
                In standard 9-category H2H fantasy basketball, **winning a matchup means winning a majority ($\ge 5$) of categories**, 
                not maximizing your team's total z-score sum. 

                - **Rejected Proxy (Total Z-Score Sum)**: Maximizing $\sum_i \text{Total\_Value}_i$ often over-invests in categories 
                  you already dominate (e.g. adding +4.0 z-score in PTS when you're winning by 50) while failing to flip close categories.
                - **The Threshold Clearing Objective**: For each category $c$, the optimizer targets clearing a specific threshold $o_c$:
                  $$\text{Categories Won} = \sum_{c=1}^{9} \mathbf{1}\left[ S_c(j) \ge o_c \right]$$
                  where $S_c(j) = B_c + v_{j,c}$ is your team's stat total in category $c$ when evaluating candidate $j$.

                ### Optimization Engine Algorithms
                1. **Single-Slot Model (Greedy Coordinate Descent)**: Evaluates replacing each player on your current roster one slot at a time, 
                   holding all other roster spots fixed as baseline $B_c$.
                2. **Sequential vs. Simultaneous**:
                   - *Sequential*: Commits each beneficial swap immediately before evaluating the next slot.
                   - *Simultaneous*: Scores all slot candidates against the initial frozen roster, then reconciles the top proposed swaps.
                3. **Tiebreakers**: When candidates yield identical category win totals, secondary objectives like **category win margin** 
                   break ties to maximize safety cushions.
                """
            )

        # Control Panel Form
        st.subheader("Optimizer Settings")
        ctrl_col1, ctrl_col2, ctrl_col3 = st.columns(3)

        with ctrl_col1:
            threshold_mode = st.selectbox(
                "Target Threshold Baseline ($o_c$)",
                options=["Zero Baseline (League Average)", "Matchup Team Totals", "Custom Target"],
                help="Determines the target values $o_c$ your team must clear per category to register a win.",
            )

        with ctrl_col2:
            exec_mode = st.selectbox(
                "Search Algorithm Mode",
                options=["sequential", "simultaneous"],
                index=0,
                help="Sequential commits swaps slot-by-slot. Simultaneous ranks candidates against a frozen roster.",
            )

        with ctrl_col3:
            tiebreaker_mode = st.selectbox(
                "Secondary Tiebreaker",
                options=["margin", "total_value", "none"],
                index=0,
                help="Used when candidate swaps yield identical category win totals.",
            )

        # Candidate Pool Selection UI
        st.subheader("Candidate Pool Selection")
        cand_col1, cand_col2 = st.columns(2)

        with cand_col1:
            candidate_pool_mode = st.selectbox(
                "Candidate Pool Scope",
                options=["Top N Free Agents", "Custom Player List", "All Non-Rostered Players"],
                index=0,
                help="Select which subset of players can be evaluated as replacement candidates.",
            )

        # Non-rostered available player pool
        active_my_team_set = set(active_my_team_ids)
        available_free_agents = {
            pid: sp
            for pid, sp in scored_pool.scored_players.items()
            if pid not in active_my_team_set
        }

        selected_candidate_names = []
        top_n_val = 50

        with cand_col2:
            if candidate_pool_mode == "Top N Free Agents":
                top_n_val = st.slider(
                    "Top N Free Agents (by Total Value)",
                    min_value=5,
                    max_value=200,
                    value=50,
                    step=5,
                    help="Limit candidates to the top N highest-ranked available free agents.",
                )
            elif candidate_pool_mode == "Custom Player List":
                available_fa_names = sorted(
                    [sp.player.name for sp in available_free_agents.values()]
                )
                selected_candidate_names = st.multiselect(
                    "Select Specific Candidate Players",
                    options=available_fa_names,
                    help="Explicitly pick which players to evaluate as replacement options.",
                )

        punt_selected = st.multiselect(
            "Punt Categories (concede/ignore)",
            options=standard_z_cats,
            default=default_punts,
            help="Punted categories are excluded from win-threshold calculations.",
        )

        # Custom Threshold Inputs if requested
        custom_thresholds = {}
        if threshold_mode == "Custom Target":
            st.markdown("##### Define Custom Category Targets ($o_c$):")
            t_cols = st.columns(3)
            for idx, cat in enumerate(standard_z_cats):
                with t_cols[idx % 3]:
                    custom_thresholds[cat] = st.number_input(f"Target for {cat}", value=0.0, step=0.5)

        # Determine Target Threshold Vector o_c
        target_thresholds = {}
        if threshold_mode == "Zero Baseline (League Average)":
            target_thresholds = {cat: 0.0 for cat in standard_z_cats}
        elif threshold_mode == "Custom Target":
            target_thresholds = custom_thresholds
        elif threshold_mode == "Matchup Team Totals":
            matchup_roster = Roster(name="matchup_team", player_ids=config.roster.matchup_team)
            matchup_snapshot = scored_pool.get_roster_snapshot(matchup_roster)
            target_thresholds = {cat: matchup_snapshot.category_totals.get(cat, 0.0) for cat in standard_z_cats}

        st.markdown("---")

        # Build Filtered Candidate ScoredPool
        if candidate_pool_mode == "Top N Free Agents":
            sorted_fa = sorted(
                available_free_agents.values(),
                key=lambda sp: sp.category_scores.total_value,
                reverse=True,
            )[:top_n_val]
            cand_pool_dict = {sp.player.player_id: sp for sp in sorted_fa}
        elif candidate_pool_mode == "Custom Player List":
            cand_pool_dict = {
                pid: sp
                for pid, sp in available_free_agents.items()
                if sp.player.name in selected_candidate_names
            }
        else:
            cand_pool_dict = dict(available_free_agents)

        # Ensure the candidate pool includes current team players by default
        cand_pool_dict.update(my_snapshot.scored_players)

        candidate_scored_pool = ScoredPool(scored_players=cand_pool_dict)

        # Run Optimization Button
        if st.button("Run Roster Optimization", type="primary", width="stretch"):
            if not my_snapshot.scored_players:
                st.error("Your current team roster is empty. Select players in the sidebar roster editor.")
            elif not candidate_scored_pool.scored_players:
                st.error("The selected candidate pool is empty. Please select candidate players or increase Top N.")
            else:
                all_punts = list(set(punt_selected + ["FG%_Impact", "FT%_Impact"]))

                strategy = SingleSlotOptimizationStrategy(
                    target_thresholds=target_thresholds,
                    punt_categories=all_punts,
                    mode=exec_mode,
                    tiebreaker=tiebreaker_mode,
                )

                res = strategy.optimize(
                    candidate_pool=candidate_scored_pool, current_roster=my_snapshot
                )

                st.success("Optimization pass complete.")

                # Key Metrics Row
                m1, m2, m3, m4 = st.columns(4)
                init_won = res.metadata.get("initial_categories_won", 0)
                final_won = res.metadata.get("final_categories_won", 0)
                win_diff = final_won - init_won
                swaps_made = res.metadata.get("swaps_made", 0)

                active_cat_count = len(standard_z_cats) - len(punt_selected)

                with m1:
                    st.metric("Categories Won", f"{final_won} / {active_cat_count}", delta=f"{win_diff:+d} vs baseline")
                with m2:
                    st.metric("Total Margin", f"{res.summary_metrics.get('total_margin', 0.0):.3f}")
                with m3:
                    st.metric("Total Z-Score", f"{res.summary_metrics.get('total_zscore', 0.0):.2f}")
                with m4:
                    st.metric("Swaps Recommended", f"{swaps_made}")

                # Recommended Swaps Schedule
                st.subheader("Recommended Roster Swap Schedule")
                swap_history = res.metadata.get("swap_history", [])

                if swap_history:
                    swap_rows = []
                    for s in swap_history:
                        swap_rows.append({
                            "Slot Index": s["slot_index"],
                            "Drop Player": f"{s['drop_player_name']} (ID: {s['drop_player_id']})",
                            "Add Player": f"{s['add_player_name']} (ID: {s['add_player_id']})",
                            "Wins Before": s["categories_won_before"],
                            "Wins After": s["categories_won_after"],
                            "Win Delta": f"{s['categories_won_diff']:+d}",
                            "Margin Gain": f"{s['margin_after'] - s['margin_before']:+.3f}",
                        })
                    st.dataframe(pd.DataFrame(swap_rows), width="stretch", hide_index=True)
                else:
                    st.info("No roster swaps recommended. Your current team roster is already optimal under the specified candidate pool.")

                # Category-by-Category Impact Analysis
                st.subheader("Category-by-Category Impact Analysis")
                cat_analysis = []
                active_cats = [c for c in standard_z_cats if c not in punt_selected]

                initial_series = my_snapshot.category_series(active_cats)

                for cat in active_cats:
                    init_val = float(initial_series.get(cat, 0.0))
                    opt_val = float(res.summary_metrics.get(f"total_{cat}", 0.0))
                    thresh = float(target_thresholds.get(cat, 0.0))
                    is_won = opt_val >= thresh

                    cat_analysis.append({
                        "Category": cat,
                        "Initial Team Total": round(init_val, 3),
                        "Optimized Team Total": round(opt_val, 3),
                        "Target Threshold (o_c)": round(thresh, 3),
                        "Net Change": round(opt_val - init_val, 3),
                        "Status": "WIN" if is_won else "LOSS",
                    })

                st.dataframe(pd.DataFrame(cat_analysis), width="stretch", hide_index=True)

    # =========================================================================
    # TAB 2: DAILY PROJECTIONS & MATCHUP
    # =========================================================================
    with tab_daily:
        st.header("Daily Projections & Matchup Analysis")
        st.markdown("Side-by-side daily stat projections for active players on today's schedule.")

        daily_proj_path = DATA_DIR / "daily_projections_myteam.json"
        matchup_proj_path = DATA_DIR / "daily_projections_matchup.json"

        my_daily_totals = {}
        matchup_daily_totals = {}
        my_df_display = pd.DataFrame()
        matchup_df_display = pd.DataFrame()

        if daily_proj_path.exists():
            try:
                with open(daily_proj_path, "r") as f:
                    d_data = json.load(f)
                if d_data:
                    daily_df = pd.DataFrame(d_data).T
                    cols = daily_df.columns.drop("name") if "name" in daily_df.columns else daily_df.columns
                    daily_df[cols] = daily_df[cols].apply(pd.to_numeric, errors="coerce")
                    daily_df = daily_df.sort_values(by="Total_Value", ascending=False)
                    num_cols = daily_df.select_dtypes(include=["number"]).columns
                    my_daily_totals = daily_df[num_cols].sum()
                    my_df_display = daily_df
            except Exception as e:
                st.error(f"Error loading daily team projections: {e}")

        if matchup_proj_path.exists():
            try:
                with open(matchup_proj_path, "r") as f:
                    m_data = json.load(f)
                if m_data:
                    matchup_df = pd.DataFrame(m_data).T
                    m_cols = matchup_df.columns.drop("name") if "name" in matchup_df.columns else matchup_df.columns
                    matchup_df[m_cols] = matchup_df[m_cols].apply(pd.to_numeric, errors="coerce")
                    matchup_df = matchup_df.sort_values(by="Total_Value", ascending=False)
                    m_num_cols = matchup_df.select_dtypes(include=["number"]).columns
                    matchup_daily_totals = matchup_df[m_num_cols].sum()
                    matchup_df_display = matchup_df
            except Exception as e:
                st.error(f"Error loading daily matchup projections: {e}")

        col_my, col_matchup = st.columns(2)

        with col_my:
            st.subheader("My Team (Today)")
            if not my_df_display.empty:
                st.dataframe(my_df_display, width="stretch", hide_index=True)
                st.write(f"**Projected Total Value:** {my_daily_totals.get('Total_Value', 0):.2f}")
            else:
                st.info("No daily projections found for My Team. Run `python main.py predict`.")

        with col_matchup:
            st.subheader("Matchup Team (Today)")
            if not matchup_df_display.empty:
                st.dataframe(matchup_df_display, width="stretch", hide_index=True)
                st.write(f"**Projected Total Value:** {matchup_daily_totals.get('Total_Value', 0):.2f}")
            else:
                st.info("No daily projections found for Matchup Team. Run `python main.py predict`.")

        if len(my_daily_totals) > 0 and len(matchup_daily_totals) > 0:
            st.subheader("Head-to-Head Stat Comparison")
            stats_to_compare = ["PTS", "REB", "AST", "ST", "BLK", "3PTM", "TO", "Total_Value"]
            comp_data = {}
            for stat in stats_to_compare:
                my_val = my_daily_totals.get(stat, 0)
                opp_val = matchup_daily_totals.get(stat, 0)
                diff = my_val - opp_val
                comp_data[stat] = f"{diff:+.2f}"
            st.dataframe(pd.DataFrame([comp_data]), width="stretch", hide_index=True)

    # =========================================================================
    # TAB 3: MY TEAM ROSTER
    # =========================================================================
    with tab_roster:
        st.header("My Team Roster & Stat Profile")
        my_team_df = df[df["player_id"].astype(int).isin(set(active_my_team_ids))]

        if not my_team_df.empty:
            cols = ["name"] + [c for c in my_team_df.columns if c != "name"]
            my_team_df = my_team_df[cols]

            st.subheader("Roster Players")
            st.dataframe(my_team_df, width="stretch", hide_index=True)

            z_cols = [c for c in my_team_df.columns if c.startswith("z")]
            team_totals = my_team_df[z_cols].sum()

            st.subheader("Team Category Z-Score Totals")
            st.dataframe(team_totals.to_frame(name="Cumulative Z-Score Total").T, width="stretch", hide_index=True)
        else:
            st.warning("No players currently selected for 'My Team'. Select players in the sidebar roster editor.")

    # =========================================================================
    # TAB 4: AI FANTASY ASSISTANT
    # =========================================================================
    with tab_ai:
        st.header("AI Fantasy Assistant")
        st.markdown("Ask Gemini for personalized strategy advice, benching recommendations, and matchup insights.")

        user_question = st.text_area(
            "Ask for advice (e.g., 'Who should I bench to protect FG%?', 'Am I favorite in blocks?')",
            height=100,
        )

        my_context = my_daily_totals.to_dict() if hasattr(my_daily_totals, "to_dict") else my_daily_totals
        matchup_context = matchup_daily_totals.to_dict() if hasattr(matchup_daily_totals, "to_dict") else matchup_daily_totals

        my_table_str = my_df_display.to_markdown(index=False) if not my_df_display.empty else "No players"
        matchup_table_str = matchup_df_display.to_markdown(index=False) if not matchup_df_display.empty else "No players"

        context_str = "--- My Team Daily Totals ---\n" + json.dumps(my_context, indent=2) + "\n\n"
        context_str += "--- Matchup Team Daily Totals ---\n" + json.dumps(matchup_context, indent=2) + "\n\n"
        context_str += "--- My Team Player Stat Details ---\n" + my_table_str + "\n\n"
        context_str += "--- Matchup Team Player Stat Details ---\n" + matchup_table_str + "\n\n"

        with st.expander("Show Prompt Context Sent to Gemini (Debug)", expanded=False):
            st.code(context_str)

        if st.button("Ask Gemini Advisor", type="primary"):
            if not gemini_api_key:
                st.warning("Please enter your Gemini API Key in the sidebar.")
            else:
                with st.spinner("Analyzing matchup and player statistics..."):
                    extra_instruction = (
                        "Provide expert fantasy basketball advice. Prioritize the user's specific question, "
                        "and use the per-category z-scores and raw stats to identify strategic category opportunities."
                    )
                    response = get_gemini_response(
                        gemini_api_key, context_str + "\n\nSystem Instruction: " + extra_instruction, user_question
                    )
                    st.markdown("### Advisor Response")
                    st.write(response)

    # =========================================================================
    # TAB 5: LEAGUE EXPLORER & PLAYER COMPARISON
    # =========================================================================
    with tab_league:
        st.header("League Player Pool & Comparison")

        st.subheader("All Scored Players")
        search_term = st.text_input("Search Player Name", "")
        if search_term:
            league_display_df = df[df["name"].str.contains(search_term, case=False)]
        else:
            league_display_df = df

        if "name" in league_display_df.columns:
            l_cols = ["name"] + [c for c in league_display_df.columns if c != "name"]
            league_display_df = league_display_df[l_cols]

        st.dataframe(league_display_df, width="stretch", hide_index=True)

        st.markdown("---")
        st.subheader("Head-to-Head Player Comparison")
        c1, c2 = st.columns(2)

        my_team_player_names = my_team_df["name"].tolist() if not my_team_df.empty else df["name"].unique().tolist()

        with c1:
            p1_name = st.selectbox("Select Player 1 (My Team)", options=my_team_player_names, key="p1_select")
            if p1_name:
                p1_data = df[df["name"] == p1_name].iloc[0]
                st.write(f"**{p1_name}** | Total Value: `{p1_data['Total_Value']:.2f}`")

        with c2:
            p2_name = st.selectbox("Select Player 2 (League Pool)", options=df["name"].unique().tolist(), key="p2_select")
            if p2_name:
                p2_data = df[df["name"] == p2_name].iloc[0]
                st.write(f"**{p2_name}** | Total Value: `{p2_data['Total_Value']:.2f}`")

        if p1_name and p2_name:
            st.subheader("Stat & Score Comparison Table")
            comp_df = df[df["name"].isin([p1_name, p2_name])].set_index("name").T
            st.dataframe(comp_df, width="stretch")


if __name__ == "__main__":
    main()
