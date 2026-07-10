"""
app/services/data_ingestion_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Orchestrates fetching raw NBA stats and merging them into the canonical
player data file (data/data.json).

Pipeline step: `python main.py pull`
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict

from app.config import DATA_DIR, config
from app.models import STATS_MAPPING
from app.repository import nba_api_repository as nba_repo
from app.repository import file_repository as file_repo


def _extract_stats(row: dict) -> dict:
    """Map NBA API column names to internal app column names."""
    return {
        app_key: row[api_key]
        for api_key, app_key in STATS_MAPPING.items()
        if api_key in row
    }


def run() -> None:
    """
    Fetch current-season, previous-season, and last-10-games stats from
    the NBA API, merge them into a single player dict, and save to
    data/data.json.
    """
    print("=== Data Ingestion ===")

    # 1. Fetch all three stat windows
    df_curr = nba_repo.fetch_league_stats(config.season.current)
    time.sleep(1)

    df_prev = nba_repo.fetch_league_stats(config.season.previous)
    time.sleep(1)

    df_last10 = nba_repo.fetch_league_stats(config.season.current, last_n_games=10)
    time.sleep(1)

    # 2. Convert DataFrames to dicts keyed by PLAYER_ID for O(1) lookup
    curr_dict: Dict[int, dict] = (
        df_curr.set_index("PLAYER_ID").to_dict(orient="index")
        if not df_curr.empty
        else {}
    )
    prev_dict: Dict[int, dict] = (
        df_prev.set_index("PLAYER_ID").to_dict(orient="index")
        if not df_prev.empty
        else {}
    )
    l10_dict: Dict[int, dict] = (
        df_last10.set_index("PLAYER_ID").to_dict(orient="index")
        if not df_last10.empty
        else {}
    )

    # 3. Build the merged player objects from the active-player list
    active_players = nba_repo.fetch_active_players()
    print(f"  Processing {len(active_players)} active players...")

    final_data: Dict[str, Any] = {}
    for p in active_players:
        p_id: int = p["id"]
        player_obj: Dict[str, Any] = {
            "player_id": p_id,
            "name": p["full_name"],
            "positions": [],
            "stats_prev_season": _extract_stats(prev_dict[p_id]) if p_id in prev_dict else {},
            "stats_curr_season": _extract_stats(curr_dict[p_id]) if p_id in curr_dict else {},
            "stats_last_10": _extract_stats(l10_dict[p_id]) if p_id in l10_dict else {},
            "combined_stats": {},
        }
        final_data[str(p_id)] = player_obj

    # 4. Persist
    output_path = DATA_DIR / "data.json"
    file_repo.save_json(output_path, final_data)

    print(f"\nData ingestion complete — {len(final_data)} players written to {output_path}")

    # Show a quick sanity-check sample
    sample = list(final_data.values())[0]
    print("\nSample (first player):")
    print(json.dumps(sample, indent=2))
