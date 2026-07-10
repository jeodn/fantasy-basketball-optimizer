"""
app/services/prediction_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Generates daily fantasy value projections for players with games today,
redistributing minutes from injured/OUT players to their active teammates.

Pipeline step: `python main.py predict`
"""

from __future__ import annotations

import sys

import pandas as pd

# Ensure UTF-8 output on all platforms
sys.stdout.reconfigure(encoding="utf-8")

# Mute pandas chained-assignment warning (we copy explicitly where needed)
pd.options.mode.chained_assignment = None

from app.config import DATA_DIR, config
from app.models import SCALABLE_STAT_COLS
from app.repository import file_repository as file_repo
from app.repository import nba_api_repository as nba_repo
from app.services.ranking_service import (
    _build_player_dataframe,
    calculate_z_scores,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_player_team_map() -> dict[int, int]:
    """Return player→team map, preferring the on-disk cache."""
    cached = file_repo.load_team_map_cache()
    if cached:
        return cached

    team_map = nba_repo.fetch_player_team_map()
    if team_map:
        file_repo.save_team_map_cache(team_map)
    return team_map


def _redistribute_minutes(team_df: pd.DataFrame) -> pd.DataFrame:
    """
    Scale active players' counting stats proportionally to absorb
    the minutes lost to OUT players.

    :param team_df: DataFrame for a single NBA team, must have 'IS_OUT' and 'MIN' columns.
    :returns: DataFrame with only active players and adjusted stats.
    """
    out_mask = team_df["IS_OUT"]
    active_mask = ~out_mask

    missing_minutes = team_df.loc[out_mask, "MIN"].sum()
    if missing_minutes <= 0:
        return team_df.loc[active_mask]

    active_df = team_df.loc[active_mask].copy()
    total_active_minutes = active_df["MIN"].sum()
    if total_active_minutes == 0:
        return active_df

    scaling_factor = 1 + (missing_minutes / total_active_minutes)

    for col in SCALABLE_STAT_COLS:
        if col in active_df.columns:
            active_df[col] = active_df[col] * scaling_factor

    # Recalculate percentages after scaling
    active_df["FG%"] = active_df.apply(
        lambda r: r["FGM"] / r["FGA"] if r["FGA"] > 0 else 0, axis=1
    )
    active_df["FT%"] = active_df.apply(
        lambda r: r["FTM"] / r["FTA"] if r["FTA"] > 0 else 0, axis=1
    )
    active_df["MIN"] = active_df["MIN"] * scaling_factor

    return active_df


# ---------------------------------------------------------------------------
# Public service function
# ---------------------------------------------------------------------------

def run() -> None:
    """
    Produce daily projection files:
      - data/daily_projections.json         — all playing players
      - data/daily_projections_myteam.json  — my roster subset
      - data/daily_projections_matchup.json — matchup opponent subset
    """
    print("=== Daily Prediction ===")

    # 1. Load raw player data and flatten to DataFrame
    raw_data = file_repo.load_raw_player_data()
    df = _build_player_dataframe(raw_data, "stats_curr_season")

    # 2. Map players to their NBA teams
    team_map = _get_player_team_map()
    if not team_map:
        print("[ERROR] Could not load player→team map. Aborting.")
        return

    df["TEAM_ID"] = df["player_id"].map(team_map)
    df = df.dropna(subset=["TEAM_ID"])
    df["TEAM_ID"] = df["TEAM_ID"].astype(int)

    # 3. Filter to players with a game today
    playing_teams = nba_repo.fetch_todays_playing_teams()
    if not playing_teams:
        print("[INFO] No games scheduled today. Nothing to project.")
        return

    df_today = df[df["TEAM_ID"].isin(playing_teams)].copy()
    print(f"  Teams playing: {len(playing_teams)} | Players loaded: {len(df_today)}")

    # 4. Mark injured / OUT players
    out_ids = file_repo.load_injuries()
    df_today["IS_OUT"] = df_today["player_id"].isin(out_ids)

    # 5. Redistribute minutes per team
    projected_dfs = [
        _redistribute_minutes(team_df)
        for _, team_df in df_today.groupby("TEAM_ID")
    ]

    if not projected_dfs:
        print("[INFO] No players remaining after injury filtering.")
        return

    final_df = pd.concat(projected_dfs)

    # 6. Calculate z-scores on projected stats
    print("  Calculating z-scores on projected stats...")
    final_df, z_cols = calculate_z_scores(
        final_df,
        punt_cats=config.scoring.punt_categories,
        weights=config.scoring.category_weights,
    )
    final_df = final_df.sort_values(by="Total_Value", ascending=False)

    print("\nTop 20 Predicted Players for Tonight:")
    print(final_df[["name", "Total_Value", "MIN"]].head(20).to_string(index=False))

    # 7. Index by player_id for JSON export
    if final_df.index.name != "player_id":
        final_df = final_df.set_index("player_id")

    # 8. Save all-players projection
    file_repo.save_dataframe_as_json(DATA_DIR / "daily_projections.json", final_df)

    # 9. Save my-team projection
    my_ids = config.roster.my_team
    my_team_df = final_df[final_df.index.isin(my_ids)]
    file_repo.save_dataframe_as_json(DATA_DIR / "daily_projections_myteam.json", my_team_df)
    print(f"\nMy Team Projections ({len(my_team_df)} players):")
    if not my_team_df.empty:
        print(my_team_df[["name", "Total_Value", "MIN"]].to_string())

    # 10. Save matchup projection
    matchup_ids = config.roster.matchup_team
    matchup_df = final_df[final_df.index.isin(matchup_ids)]
    file_repo.save_dataframe_as_json(DATA_DIR / "daily_projections_matchup.json", matchup_df)
    print(f"\nMatchup Team Projections ({len(matchup_df)} players):")
    if not matchup_df.empty:
        print(matchup_df[["name", "Total_Value", "MIN"]].to_string())
