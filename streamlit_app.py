import streamlit as st
import pandas as pd
from scripts import z_scores, util, generate_roster
import json
from google import genai
import os

# Set page configuration
st.set_page_config(
    page_title="Fantasy Basketball Advisor",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load data function
@st.cache_data
def load_data():
    json_data = util.load_player_data(util.DATA_SOURCE_FILENAME)
    df = z_scores.generate_z_scores_df(json_data)
    return df

def get_gemini_response(api_key, context, prompt):
    try:
        client = genai.Client(api_key=api_key)
        full_prompt = f"Context:\n{context}\n\nUser Question: {prompt}\n\nPlease answer as a fantasy basketball expert advisor."
        response = client.models.generate_content(
            model='gemini-2.0-flash-lite',  
            contents=full_prompt
        )
        return response.text
    except Exception as e:
        return f"Error communicating with Gemini: {e}"

def main():
    st.title("Fantasy Basketball Optimizer")

    st.markdown("### Welcome to the Fantasy Basketball Advisor!")
    st.markdown("This app will help you optimize your fantasy basketball team.")
    st.markdown("#### Features")
    st.markdown("- View your team stats and daily projections in a web interface.")
    st.markdown("- Compare players from your team and the league.")
    st.markdown("- See your team's total value and projected totals.")
    st.markdown("Note: Login integration not completed. AI suggestions not implemented.")

    # Load Data
    try:
        df = load_data()
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return

    # Sidebar
    st.sidebar.header("Settings")
    gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password")
    
    # Section 1: My Team
    st.header("My Team")
    
    # Filter for my team
    my_team_ids = set(generate_roster.my_team)
    my_team_df = df[df['player_id'].astype(int).isin(my_team_ids)]
    
    # Rearrange columns to put 'name' first if present
    cols = ['name'] + [c for c in my_team_df.columns if c != 'name']
    my_team_df = my_team_df[cols]

    # Calculate Team Totals (similar to cumulative stats)
    if not my_team_df.empty:
        # Display Team Stats
        st.subheader("Team Roster")
        st.dataframe(
            my_team_df, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "name": st.column_config.TextColumn(
                    "Player Name",
                    pinned=True
                )
            }
        )
        
        # Calculate totals for z-scores
        z_cols = [col for col in my_team_df.columns if col.startswith('z')]
        team_totals = my_team_df[z_cols].sum()
        
        st.subheader("Team Totals (Z-Scores)")
        # Transpose for better display
        st.dataframe(team_totals.to_frame(name="Total Value").T, use_container_width=True, hide_index=True)
    else:
        st.warning("No players found for 'My Team'. Check generate_roster.py.")

    # Section 1.5: Daily Projections & Matchup
    st.header("Daily Projections (Today)")
    
    col_my, col_matchup = st.columns(2)
    
    my_daily_totals = {}
    matchup_daily_totals = {}
    
    # --- Data Loading & Logic ---
    my_daily_totals = {}
    matchup_daily_totals = {}
    my_df_display = pd.DataFrame()
    matchup_df_display = pd.DataFrame()
    
    # Load My Team
    daily_proj_path = util.DATA_DIR / 'daily_projections_myteam.json'
    if daily_proj_path.exists():
        try:
            with open(daily_proj_path, 'r') as f:
                daily_data = json.load(f)
            if daily_data:
                daily_df = pd.DataFrame(daily_data).T
                
                # Convert to numeric (ignore 'name' errors)
                cols = daily_df.columns.drop('name') if 'name' in daily_df.columns else daily_df.columns
                daily_df[cols] = daily_df[cols].apply(pd.to_numeric, errors='coerce')

                daily_df = daily_df.sort_values(by='Total_Value', ascending=False)
                # Calculate Totals
                daily_numeric_cols = daily_df.select_dtypes(include=['number']).columns
                my_daily_totals = daily_df[daily_numeric_cols].sum()
                
                # Prepare Display DF
                if 'name' in daily_df.columns:
                    d_cols = ['name'] + [c for c in daily_df.columns if c != 'name']
                    my_df_display = daily_df[d_cols]
                else:
                    my_df_display = daily_df
        except Exception as e:
            st.error(f"Error loading my team data: {e}")

    # Load Matchup Team
    matchup_proj_path = util.DATA_DIR / 'daily_projections_matchup.json'
    if matchup_proj_path.exists():
        try:
            with open(matchup_proj_path, 'r') as f:
                matchup_data = json.load(f)
            if matchup_data:
                matchup_df = pd.DataFrame(matchup_data).T
                
                # Convert to numeric
                m_cols_num = matchup_df.columns.drop('name') if 'name' in matchup_df.columns else matchup_df.columns
                matchup_df[m_cols_num] = matchup_df[m_cols_num].apply(pd.to_numeric, errors='coerce')

                matchup_df = matchup_df.sort_values(by='Total_Value', ascending=False)
                # Calculate Totals
                matchup_numeric_cols = matchup_df.select_dtypes(include=['number']).columns
                matchup_daily_totals = matchup_df[matchup_numeric_cols].sum()
                
                # Prepare Display DF
                if 'name' in matchup_df.columns:
                    m_cols = ['name'] + [c for c in matchup_df.columns if c != 'name']
                    matchup_df_display = matchup_df[m_cols]
                else:
                    matchup_df_display = matchup_df
        except Exception as e:
            st.error(f"Error loading matchup data: {e}")


    # --- Display Layout ---
    col_my, col_matchup = st.columns(2)
    
    # --- My Team Display ---
    with col_my:
        st.subheader("My Team")
        if not my_df_display.empty:
            st.dataframe(my_df_display, use_container_width=True, hide_index=True, column_config={"name": st.column_config.TextColumn("Player", pinned=True)})
            st.write(f"**Total Value:** {my_daily_totals.get('Total_Value', 0):.2f}")
        else:
            st.info("No projections found. Run 'python main.py predict'.")

    # --- Matchup Team Display ---
    with col_matchup:
        st.subheader("Matchup Team")
        if not matchup_df_display.empty:
            st.dataframe(matchup_df_display, use_container_width=True, hide_index=True, column_config={"name": st.column_config.TextColumn("Player", pinned=True)})
            st.write(f"**Total Value:** {matchup_daily_totals.get('Total_Value', 0):.2f}")
        else:
            st.info("No matchup data found.")

    # --- Comparison Summary ---
    if len(my_daily_totals) > 0 and len(matchup_daily_totals) > 0:
        st.subheader("Head-to-Head Comparison")
        stats_to_compare = ['PTS', 'REB', 'AST', 'ST', 'BLK', '3PTM', 'TO', 'Total_Value']
        
        comp_data = {}
        for stat in stats_to_compare:
            my_val = my_daily_totals.get(stat, 0)
            opp_val = matchup_daily_totals.get(stat, 0)
            diff = my_val - opp_val
            
            # Format diff string
            if stat == 'TO': # Lower is better for TO
                color = "green" if diff < 0 else "red"
            else:
                color = "green" if diff > 0 else "red"
                
            comp_data[stat] = f"{diff:+.2f}"
            
        st.dataframe(pd.DataFrame([comp_data]), use_container_width=True, hide_index=True)

    # --- AI Assistant ---
    st.header("Fantasy Assistant")
    user_question = st.text_area("Ask for advice (e.g., 'Who should I bench?', 'Am I winning blocks?')")
    
    # Prepare data for context logic (moved outside for visibility)
    # Totals (Numbers)
    my_context = my_daily_totals.to_dict() if hasattr(my_daily_totals, 'to_dict') else my_daily_totals
    matchup_context = matchup_daily_totals.to_dict() if hasattr(matchup_daily_totals, 'to_dict') else matchup_daily_totals
    
    # Details (Tables) - Convert display DFs to markdown for better readability by LLM
    my_table_str = my_df_display.to_markdown(index=False) if not my_df_display.empty else "No players"
    matchup_table_str = matchup_df_display.to_markdown(index=False) if not matchup_df_display.empty else "No players"

    # Construct Context
    context_str = "--- My Team Daily Totals ---\n" + json.dumps(my_context, indent=2) + "\n\n"
    context_str += "--- Matchup Team Daily Totals ---\n" + json.dumps(matchup_context, indent=2) + "\n\n"
    context_str += "--- My Team Player Stat Details ---\n" + my_table_str + "\n\n"
    context_str += "--- Matchup Team Player Stat Details ---\n" + matchup_table_str + "\n\n"
    
    # Debug: Show what we are sending
    with st.expander("Show Prompt Context (Debug)"):
        st.code(context_str)

    if st.button("Ask Gemini"):
        if not gemini_api_key:
            st.warning("Please enter your Gemini API Key in the sidebar.")
        else:
            with st.spinner("Thinking..."):
                extra_instruction = "Individual player stats are provided. This includes a set of raw stats and a corresponding set of z-scores for each statistic category. Please provide general fantasy advice for this matchup. You may suggest benching players if beneficial for specific categories (e.g. to protect FG% or FT%), but prioritize the user's specific question."
                response = get_gemini_response(gemini_api_key, context_str + "\n\nSystem Instruction: " + extra_instruction, user_question)
                st.write(response)

    # Section 2: League Data
    st.header("League Data")
    st.markdown("### All Players")
    
    # Optional: Search/Filter
    search_term = st.text_input("Search Player", "")
    if search_term:
        league_display_df = df[df['name'].str.contains(search_term, case=False)]
    else:
        league_display_df = df

    # Rearrange columns
    if 'name' in league_display_df.columns:
        l_cols = ['name'] + [c for c in league_display_df.columns if c != 'name']
        league_display_df = league_display_df[l_cols]

    st.dataframe(
        league_display_df, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "name": st.column_config.TextColumn(
                "Player Name",
                pinned=True
            )
        }
    )

    # Section 3: Comparison
    st.header("Player Comparison")
    
    col1, col2 = st.columns(2)
    
    with col1:
        player1_name = st.selectbox("Select Player 1 (My Team)", my_team_df['name'].tolist(), key="p1")
        if player1_name:
            player1_data = df[df['name'] == player1_name].iloc[0]
            st.write(f"**{player1_name}**")
            st.write(f"Total Value: {player1_data['Total_Value']:.2f}")

    with col2:
        # Filter out player 1 from the list if desired, but keeping all is fine
        player2_name = st.selectbox("Select Player 2 (League)", df['name'].unique().tolist(), key="p2")
        if player2_name:
            player2_data = df[df['name'] == player2_name].iloc[0]
            st.write(f"**{player2_name}**")
            st.write(f"Total Value: {player2_data['Total_Value']:.2f}")

    if player1_name and player2_name:
        st.subheader("Comparison Table")
        
        # Extract relevant columns for comparison (Raw stats + Z categories)
        # Assuming util.process_data gives us raw stats, but z_scores.generate_z_scores_df might have them too 
        # or we might want to look at the z-score columns specifically.
        # Let's show the columns present in the dataframe.
        
        comp_df = df[df['name'].isin([player1_name, player2_name])].set_index('name').T
        st.dataframe(comp_df, use_container_width=True)

if __name__ == "__main__":
    main()
