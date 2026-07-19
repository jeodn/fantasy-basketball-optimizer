"""
app/ingestion/projection_ingestion.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Builds a projected PlayerPool for today's games by:
  1. Fetching today's NBA schedule (or reading from cache)
  2. Filtering the base pool to players with a game today
  3. Loading the injury list and marking OUT players
  4. Redistributing the missing minutes to active teammates (per team)

Returns a new PlayerPool where each player's ``stats_curr_season`` has been
replaced with their projected (injury-adjusted) stat line. OUT players and
players on teams with no game are excluded entirely.

This is a data-transformation step — no scoring is performed here.
"""

from __future__ import annotations

from dataclasses import replace as dc_replace
from pathlib import Path
from typing import Optional

import pandas as pd

from app.config import DATA_DIR
from app.domain.player import Player, PlayerPool
from app.domain.stats import PlayerStats, SCALABLE_STAT_COLS
from app.repository import file_repository as file_repo
from app.repository import nba_api_repository as nba_repo

pd.options.mode.chained_assignment = None   # suppress chained-assignment warning


# ---------------------------------------------------------------------------
# Private helpers
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


def _load_out_player_ids() -> set[int]:
    """
    Load the manual injury list from data/injuries.json.
    Returns an empty set if the file does not exist.
    """
    path = DATA_DIR / "injuries.json"
    if not path.exists():
        return set()
    injuries = file_repo.load_json(path)
    return {int(p["id"]) for p in injuries if p.get("status") == "OUT"}


def _redistribute_minutes(team_df: pd.DataFrame) -> pd.DataFrame:
    """
    Scale active players' counting stats proportionally to absorb the
    minutes lost to OUT players on the same team.

    :param team_df: DataFrame for a single NBA team.
                    Must have ``IS_OUT`` and ``MIN`` columns.
    :returns:       DataFrame containing only active (non-OUT) players
                    with adjusted stat columns.
    """
    out_mask    = team_df["IS_OUT"]
    active_mask = ~out_mask

    missing_minutes = team_df.loc[out_mask, "MIN"].sum()
    if missing_minutes <= 0:
        return team_df.loc[active_mask]

    active_df = team_df.loc[active_mask].copy()
    total_active_min = active_df["MIN"].sum()
    if total_active_min == 0:
        return active_df

    factor = 1 + (missing_minutes / total_active_min)

    for col in SCALABLE_STAT_COLS:
        if col in active_df.columns:
            active_df[col] = active_df[col] * factor

    # Recalculate percentage columns after scaling
    active_df["FG%"] = active_df.apply(
        lambda r: r["FGM"] / r["FGA"] if r["FGA"] > 0 else 0.0, axis=1
    )
    active_df["FT%"] = active_df.apply(
        lambda r: r["FTM"] / r["FTA"] if r["FTA"] > 0 else 0.0, axis=1
    )
    active_df["MIN"] = active_df["MIN"] * factor

    return active_df


def _row_to_player_stats(row: pd.Series) -> PlayerStats:
    """Convert a DataFrame row (post-redistribution) to a PlayerStats object."""
    return PlayerStats.from_dict(row.to_dict())


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def build_projected_pool(base_pool: PlayerPool) -> Optional[PlayerPool]:
    """
    Build a projected PlayerPool for today's games.

    :param base_pool: The full PlayerPool from data.json (current season stats).
    :returns:         A new PlayerPool with projected ``stats_curr_season``
                      for each active player playing today, or ``None`` if
                      there are no games today or no players remain after
                      injury filtering.
    """
    print("  Fetching today's schedule and team map...")

    team_map = _get_player_team_map()
    if not team_map:
        print("  [ERROR] Could not load player→team map. Aborting.")
        return None

    playing_teams = nba_repo.fetch_todays_playing_teams()
    if not playing_teams:
        print("  [INFO] No games scheduled today. Nothing to project.")
        return None

    # Flatten the pool to a DataFrame for groupby operations
    df = base_pool.to_dataframe("stats_curr_season")
    df["TEAM_ID"] = df["player_id"].map(team_map)
    df = df.dropna(subset=["TEAM_ID"])
    df["TEAM_ID"] = df["TEAM_ID"].astype(int)

    df_today = df[df["TEAM_ID"].isin(playing_teams)].copy()
    print(
        f"  Teams playing: {len(playing_teams)} | "
        f"Players loaded: {len(df_today)}"
    )

    # Mark injured / OUT players
    out_ids = _load_out_player_ids()
    df_today["IS_OUT"] = df_today["player_id"].isin(out_ids)

    # Redistribute minutes per team
    projected_dfs = [
        _redistribute_minutes(team_df)
        for _, team_df in df_today.groupby("TEAM_ID")
    ]

    if not projected_dfs:
        print("  [INFO] No players remaining after injury filtering.")
        return None

    final_df = pd.concat(projected_dfs).reset_index(drop=True)

    # Rebuild a PlayerPool with projected stats
    projected_players: dict[int, Player] = {}
    for _, row in final_df.iterrows():
        pid = int(row["player_id"])
        original = base_pool.get(pid)
        if original is None:
            continue

        projected_stats = _row_to_player_stats(row)
        projected_player = dc_replace(original, stats_curr_season=projected_stats)
        projected_players[pid] = projected_player

    return PlayerPool(players=projected_players)
