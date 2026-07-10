"""
app/repository/file_repository.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
All file-system I/O is centralised here.
Services call these functions — they never open files themselves.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Set

import pandas as pd

from app.config import DATA_DIR


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def save_json(path: Path, data: Any, indent: int = 4) -> None:
    """Serialize *data* to *path* as JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
    print(f"  Saved → {path}")


def save_dataframe_as_json(path: Path, df: pd.DataFrame, index_col: str = "player_id") -> None:
    """
    Write a DataFrame to JSON keyed by *index_col*.
    The resulting file has the shape: {"<player_id>": {col: val, ...}, ...}
    """
    if df.empty:
        return
    out = df.copy()
    if out.index.name != index_col and index_col in out.columns:
        out = out.set_index(index_col)
    out.to_json(path, orient="index", indent=4)
    print(f"  Saved → {path}")


def save_csv(path: Path, df: pd.DataFrame, index: bool = False) -> None:
    """Write a DataFrame to CSV."""
    df.to_csv(path, index=index)
    print(f"  Saved → {path}")


# ---------------------------------------------------------------------------
# Domain-specific loaders
# ---------------------------------------------------------------------------

def load_raw_player_data() -> Dict:
    """
    Load the primary data file (data/data.json).

    :returns: Parsed dict keyed by player_id string.
    :raises FileNotFoundError: if data.json has not been generated yet.
    """
    path = DATA_DIR / "data.json"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `python main.py pull` first."
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_z_scores() -> Dict:
    """
    Load the z-score ranked data (data/data_zscores.json).

    :returns: Parsed dict keyed by player_id string.
    :raises FileNotFoundError: if the file has not been generated yet.
    """
    path = DATA_DIR / "data_zscores.json"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `python main.py rank` first."
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_my_team_z_scores() -> Dict:
    """
    Load z-scores filtered to the user's roster (data/data_myteam.json).

    :returns: Parsed dict keyed by player_id string.
    :raises FileNotFoundError: if the file has not been generated yet.
    """
    path = DATA_DIR / "data_myteam.json"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `python main.py roster` first."
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_injuries() -> Set[int]:
    """
    Load the manual injury list (data/injuries.json).

    :returns: Set of player IDs with status == "OUT". Empty set if file missing.
    """
    path = DATA_DIR / "injuries.json"
    if not path.exists():
        return set()
    with open(path, "r", encoding="utf-8") as f:
        injuries = json.load(f)
    return {int(p["id"]) for p in injuries if p.get("status") == "OUT"}


def load_team_map_cache() -> Dict[int, int] | None:
    """
    Load the cached player→team map (data/team_map_cache.json).

    :returns: Dict {player_id: team_id}, or None if no cache file exists.
    """
    path = DATA_DIR / "team_map_cache.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {int(k): int(v) for k, v in raw.items()}


def save_team_map_cache(team_map: Dict[int, int]) -> None:
    """Persist the player→team map to disk for reuse."""
    path = DATA_DIR / "team_map_cache.json"
    save_json(path, team_map)
