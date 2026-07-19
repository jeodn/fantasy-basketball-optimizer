"""
app/pipeline/commands.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Thin orchestrators for each CLI command.

These are the *only* functions where ingestion, analytics, and persistence
appear in the same call stack. Each command:
  1. Loads data (via ingestion layer or file_repository)
  2. Runs analytics (via scoring/evaluation layer)
  3. Persists results (via file_repository)

No business logic lives here — commands are glue.
"""

from __future__ import annotations

import sys
from typing import Optional

from app.analytics.evaluation.candidate_evaluator import evaluate_replacements
from app.analytics.scoring.z_score import ZScoreStrategy
from app.config import DATA_DIR, config
from app.domain.roster import Roster
from app.domain.scoring import ScoredPool
from app.domain.stats import RAW_STAT_COLS
from app.ingestion import player_ingestion, projection_ingestion, roster_ingestion
from app.repository import file_repository as file_repo

sys.stdout.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------------------
# Convenience: build the configured ZScoreStrategy in one place
# ---------------------------------------------------------------------------

def _default_strategy() -> ZScoreStrategy:
    return ZScoreStrategy(
        weights=config.scoring.category_weights,
        punt_categories=config.scoring.punt_categories,
        stats_source=config.scoring.stats_source,
    )


# ---------------------------------------------------------------------------
# pull — fetch raw NBA stats → data/data.json
# ---------------------------------------------------------------------------

def pull() -> None:
    """Fetch raw NBA stats and persist to data/data.json."""
    pool = player_ingestion.fetch_and_build_pool()
    player_ingestion.save_pool(pool, DATA_DIR / "data.json")


# ---------------------------------------------------------------------------
# rank — score all players → data/data_zscores.json + fantasy_rankings.csv
# ---------------------------------------------------------------------------

def rank() -> None:
    """Load data.json, apply ZScoreStrategy, save checkpoint and CSV."""
    pool = player_ingestion.load_pool_from_file(DATA_DIR / "data.json")

    scored_pool = _default_strategy().score(pool)

    df = scored_pool.to_dataframe()

    # Strip raw stat columns before saving the checkpoint
    df_scores = df.drop(columns=RAW_STAT_COLS, errors="ignore")

    file_repo.save_dataframe_as_json(DATA_DIR / "data_zscores.json", df_scores)
    file_repo.save_csv(DATA_DIR / "fantasy_rankings.csv", df_scores)

    print(f"\nRanking complete — {len(scored_pool)} players ranked.")
    print(f"Punt categories: {config.scoring.punt_categories or 'none'}")


# ---------------------------------------------------------------------------
# roster — filter scored pool to team/matchup → roster JSON files + CSV
# ---------------------------------------------------------------------------

def roster() -> None:
    """Slice the scored pool for my_team and matchup_team, save all outputs."""
    raw = file_repo.load_json(DATA_DIR / "data_zscores.json")
    scored_pool = ScoredPool.from_zscores_dict(raw)

    my_roster      = Roster("my_team",      config.roster.my_team)
    matchup_roster = Roster("matchup_team", config.roster.matchup_team)

    my_snap      = roster_ingestion.build_roster_snapshot(scored_pool, my_roster)
    matchup_snap = roster_ingestion.build_roster_snapshot(scored_pool, matchup_roster)

    # --- JSON outputs ---
    file_repo.save_json(DATA_DIR / "data_myteam.json",   my_snap.to_dict())
    file_repo.save_json(DATA_DIR / "data_matchup.json",  matchup_snap.to_dict())

    # Cumulative team z-score totals
    cumulative = {"TEAM_CATEGORY_STATS": {"name": "TEAM", **my_snap.category_totals}}
    file_repo.save_json(DATA_DIR / "data_myteam_cumulative.json", cumulative)

    # --- CSV: my team slice from the full rankings ---
    rankings_path = DATA_DIR / "fantasy_rankings.csv"
    if rankings_path.exists():
        import pandas as pd
        df = pd.read_csv(rankings_path)
        my_csv = df[df["player_id"].isin(set(config.roster.my_team))]
        file_repo.save_csv(DATA_DIR / "fantasy_rankings_myteam.csv", my_csv)

    print(
        f"\nRoster generation complete — "
        f"{len(my_snap.scored_players)} my-team players, "
        f"{len(matchup_snap.scored_players)} matchup players."
    )


# ---------------------------------------------------------------------------
# evaluate — rank free-agent replacements → data/data_top_n_replacements.json
# ---------------------------------------------------------------------------

def evaluate(drop_candidate_id: Optional[int] = None, top_n: int = 50) -> None:
    """
    Evaluate replacement candidates for a drop candidate.

    Loads the scored-pool checkpoint (data_zscores.json) and builds the
    roster snapshot in memory — no dependency on data_myteam.json.

    :param drop_candidate_id: Overrides config.roster.drop_candidate when provided.
    :param top_n:             Number of top candidates to output.
    """
    player_to_drop = int(drop_candidate_id or config.roster.drop_candidate)
    print(f"  Drop candidate: {player_to_drop}")

    raw = file_repo.load_json(DATA_DIR / "data_zscores.json")
    scored_pool = ScoredPool.from_zscores_dict(raw)

    my_roster   = Roster("my_team", config.roster.my_team)
    my_snapshot = roster_ingestion.build_roster_snapshot(scored_pool, my_roster)

    try:
        result = evaluate_replacements(
            scored_pool, player_to_drop, my_snapshot, top_n=top_n
        )
    except ValueError as e:
        print(f"  [ERROR] {e}")
        return

    drop_name = result.drop_candidate.player.name
    print(f"  Evaluating replacements for: {drop_name}")

    output = {
        str(opt.candidate.player.player_id): {
            "name": opt.candidate.player.name,
            "ValueAdded": opt.value_added,
            "Total_Added_Value": opt.total_added_value,
        }
        for opt in result.replacements
    }

    file_repo.save_json(DATA_DIR / "data_top_n_replacements.json", output)
    print(f"\nEvaluation complete — top {len(output)} replacements saved.")


# ---------------------------------------------------------------------------
# predict — daily projections → data/daily_projections*.json
# ---------------------------------------------------------------------------

def predict() -> None:
    """
    Build injury-adjusted daily projections, score them, and save three
    output files (all players, my team, matchup team).
    """
    print("=== Daily Prediction ===")

    base_pool = player_ingestion.load_pool_from_file(DATA_DIR / "data.json")

    projected_pool = projection_ingestion.build_projected_pool(base_pool)
    if projected_pool is None:
        return

    scored_pool = _default_strategy().score(projected_pool)
    df = scored_pool.to_dataframe()
    df = df.sort_values("Total_Value", ascending=False)

    print("\nTop 20 Predicted Players for Tonight:")
    print(df[["name", "Total_Value", "MIN"]].head(20).to_string(index=False))

    # All players
    file_repo.save_dataframe_as_json(DATA_DIR / "daily_projections.json", df)

    # My team
    my_ids  = set(config.roster.my_team)
    my_df   = df[df["player_id"].isin(my_ids)]
    file_repo.save_dataframe_as_json(DATA_DIR / "daily_projections_myteam.json", my_df)
    print(f"\nMy Team Projections ({len(my_df)} players):")
    if not my_df.empty:
        print(my_df[["name", "Total_Value", "MIN"]].to_string(index=False))

    # Matchup team
    matchup_ids = set(config.roster.matchup_team)
    matchup_df  = df[df["player_id"].isin(matchup_ids)]
    file_repo.save_dataframe_as_json(
        DATA_DIR / "daily_projections_matchup.json", matchup_df
    )
    print(f"\nMatchup Team Projections ({len(matchup_df)} players):")
    if not matchup_df.empty:
        print(matchup_df[["name", "Total_Value", "MIN"]].to_string(index=False))
