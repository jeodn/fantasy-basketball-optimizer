"""
app/services/roster_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Filters ranked player data to the user's team and matchup opponent,
and computes cumulative team z-score totals.

Pipeline step: `python main.py roster`
"""

from __future__ import annotations

import json
from typing import Dict

import pandas as pd

from app.config import DATA_DIR, config
from app.repository import file_repository as file_repo


# ---------------------------------------------------------------------------
# Cumulative stat keys tracked for team-level aggregation
# ---------------------------------------------------------------------------
_CUMULATIVE_KEYS = [
    "FG%_Impact", "FT%_Impact",
    "zFG%", "zFT%", "z3PTM", "zPTS",
    "zREB", "zAST", "zST", "zBLK", "zTO",
    "Total_Value",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _filter_by_ids(z_scores: Dict, player_ids: list[int]) -> Dict:
    """Return only entries whose player_id is in *player_ids*."""
    id_set = set(player_ids)
    return {
        pid: stats
        for pid, stats in z_scores.items()
        if int(pid) in id_set
    }


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

def run() -> None:
    """
    Read data_zscores.json and fantasy_rankings.csv, then write:
      - data/data_myteam.json           — z-scores for my roster
      - data/data_matchup.json          — z-scores for the matchup opponent
      - data/data_myteam_cumulative.json — summed team-level z-scores
      - data/fantasy_rankings_myteam.csv — CSV slice of my roster
    """
    print("=== Roster Generation ===")

    my_ids = config.roster.my_team
    matchup_ids = config.roster.matchup_team

    # --- Load ranked data ---
    all_z_scores = file_repo.load_z_scores()

    # --- My team JSON ---
    my_team_data = _filter_by_ids(all_z_scores, my_ids)
    file_repo.save_json(DATA_DIR / "data_myteam.json", my_team_data)

    # --- Matchup JSON ---
    matchup_data = _filter_by_ids(all_z_scores, matchup_ids)
    file_repo.save_json(DATA_DIR / "data_matchup.json", matchup_data)

    # --- Cumulative team z-scores ---
    cumulative: Dict[str, float] = {k: 0.0 for k in _CUMULATIVE_KEYS}
    for pid, stats in my_team_data.items():
        for key in _CUMULATIVE_KEYS:
            if key in stats and isinstance(stats[key], (int, float)):
                cumulative[key] = round(cumulative[key] + stats[key], 3)

    team_output = {"TEAM_CATEGORY_STATS": {"name": "TEAM", **cumulative}}
    file_repo.save_json(DATA_DIR / "data_myteam_cumulative.json", team_output)

    # --- My team CSV slice ---
    rankings_path = DATA_DIR / "fantasy_rankings.csv"
    if rankings_path.exists():
        df = pd.read_csv(rankings_path)
        my_csv = df[df["player_id"].isin(set(my_ids))]
        file_repo.save_csv(DATA_DIR / "fantasy_rankings_myteam.csv", my_csv)

    print(
        f"\nRoster generation complete — "
        f"{len(my_team_data)} my-team players, "
        f"{len(matchup_data)} matchup players."
    )
