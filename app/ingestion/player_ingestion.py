"""
app/ingestion/player_ingestion.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Fetches raw NBA stats from the API, merges stat windows, and builds a
typed PlayerPool. Also provides load/save helpers for the data.json checkpoint.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from app.domain.player import Player, PlayerPool
from app.domain.stats import PlayerStats
from app.config import config
from app.repository import file_repository as file_repo
from app.repository import nba_api_repository as nba_repo

# NBA API column name → internal app column name
# Kept here because it is only used during ingestion.
_STATS_MAPPING: dict[str, str] = {
    "MIN":    "MIN",
    "FGM":    "FGM",
    "FGA":    "FGA",
    "FG_PCT": "FG%",
    "FG3M":   "3PTM",
    "FTM":    "FTM",
    "FTA":    "FTA",
    "FT_PCT": "FT%",
    "PTS":    "PTS",
    "REB":    "REB",
    "AST":    "AST",
    "STL":    "ST",
    "BLK":    "BLK",
    "TOV":    "TO",
    "GP":     "GP",
}


def _extract_stats(row: dict) -> dict:
    """Map NBA API column names to internal app column names."""
    return {
        app_key: row[api_key]
        for api_key, app_key in _STATS_MAPPING.items()
        if api_key in row
    }


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def fetch_and_build_pool() -> PlayerPool:
    """
    Hit the NBA API for current season, previous season, and last-10-games
    stats, merge them into a PlayerPool, and return it.

    Applies a 1-second sleep between API calls to be polite to the rate limiter.
    """
    print("=== Data Ingestion ===")

    df_curr   = nba_repo.fetch_league_stats(config.season.current)
    time.sleep(1)
    df_prev   = nba_repo.fetch_league_stats(config.season.previous)
    time.sleep(1)
    df_last10 = nba_repo.fetch_league_stats(config.season.current, last_n_games=10)
    time.sleep(1)

    curr_dict  = df_curr.set_index("PLAYER_ID").to_dict(orient="index")  if not df_curr.empty  else {}
    prev_dict  = df_prev.set_index("PLAYER_ID").to_dict(orient="index")  if not df_prev.empty  else {}
    l10_dict   = df_last10.set_index("PLAYER_ID").to_dict(orient="index") if not df_last10.empty else {}

    active_players = nba_repo.fetch_active_players()
    print(f"  Processing {len(active_players)} active players...")

    players: dict[int, Player] = {}
    for p in active_players:
        pid: int = p["id"]

        def _stats(d: dict) -> PlayerStats | None:
            return PlayerStats.from_dict(_extract_stats(d)) if d else None

        players[pid] = Player(
            player_id=pid,
            name=p["full_name"],
            positions=[],
            stats_curr_season=_stats(curr_dict.get(pid, {})),
            stats_prev_season=_stats(prev_dict.get(pid, {})),
            stats_last_10=_stats(l10_dict.get(pid, {})),
        )

    return PlayerPool(players=players)


def load_pool_from_file(path: Path) -> PlayerPool:
    """
    Load a PlayerPool from a data.json-format file.

    :raises FileNotFoundError: if *path* does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `python main.py pull` first."
        )
    raw = file_repo.load_json(path)
    return PlayerPool.from_raw_dict(raw)


def save_pool(pool: PlayerPool, path: Path) -> None:
    """Persist a PlayerPool to *path* in data.json format."""
    file_repo.save_json(path, pool.to_raw_dict())

    # Print a one-player sample as a sanity check
    sample = next(iter(pool.players.values()), None)
    if sample:
        print("\nSample (first player):")
        raw_sample = pool.to_raw_dict().get(str(sample.player_id), {})
        print(json.dumps(raw_sample, indent=2))

    print(f"\nData ingestion complete — {len(pool)} players written to {path}")
