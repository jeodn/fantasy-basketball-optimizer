"""
app/repository/nba_api_repository.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
All outbound NBA API calls live here. Returns raw pandas DataFrames or
plain dicts — no business logic, no file I/O.
"""

from __future__ import annotations

import time
from typing import Dict, Set

import pandas as pd
from nba_api.stats.endpoints import (
    commonallplayers,
    leaguedashplayerstats,
    scoreboardv2,
)
from nba_api.stats.static import players


def fetch_league_stats(season: str, last_n_games: int = 0) -> pd.DataFrame:
    """
    Fetch per-game averages for ALL players in a given season window.

    :param season: e.g. "2025-26"
    :param last_n_games: 0 = full season, N = last N games
    :returns: Raw DataFrame from leaguedashplayerstats, or empty DataFrame on error.
    """
    last_n_str = str(last_n_games) if last_n_games > 0 else "0"
    print(f"  Fetching league stats — season={season}, last_n_games={last_n_str}...")
    try:
        dash = leaguedashplayerstats.LeagueDashPlayerStats(
            season=season,
            last_n_games=last_n_str,
            per_mode_detailed="PerGame",
            measure_type_detailed_defense="Base",
        )
        return dash.get_data_frames()[0]
    except Exception as e:
        print(f"  [ERROR] fetch_league_stats: {e}")
        return pd.DataFrame()


def fetch_active_players() -> list[dict]:
    """
    Return the list of currently active NBA players from the static dataset.

    :returns: List of player dicts with keys: id, full_name, etc.
    """
    return players.get_active_players()


def fetch_player_team_map() -> Dict[int, int]:
    """
    Fetch a mapping of player_id -> team_id for all currently active players.

    :returns: Dict {player_id: team_id}. Empty dict on error.
    """
    print("  Fetching player→team map from NBA API...")
    try:
        all_players = commonallplayers.CommonAllPlayers(
            is_only_current_season=1
        ).get_data_frames()[0]
        team_map = pd.Series(
            all_players.TEAM_ID.values, index=all_players.PERSON_ID
        ).to_dict()
        return {int(k): int(v) for k, v in team_map.items() if v > 0}
    except Exception as e:
        print(f"  [ERROR] fetch_player_team_map: {e}")
        return {}


def fetch_todays_playing_teams() -> Set[int]:
    """
    Return the set of NBA Team IDs with a scheduled game today.

    :returns: Set of team IDs. Empty set on error or no games.
    """
    try:
        board = scoreboardv2.ScoreboardV2()
        games = board.get_data_frames()[0]
        home = set(games["HOME_TEAM_ID"].tolist())
        away = set(games["VISITOR_TEAM_ID"].tolist())
        return home | away
    except Exception as e:
        print(f"  [ERROR] fetch_todays_playing_teams: {e}")
        return set()
