"""
app/repository/file_repository.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Generic file I/O primitives. This layer knows nothing about the domain —
it only reads and writes bytes. Path knowledge and domain semantics belong
in the pipeline commands that call these functions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from app.config import DATA_DIR


# ---------------------------------------------------------------------------
# Generic primitives
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict:
    """
    Load and parse a JSON file.

    :raises FileNotFoundError: if *path* does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any, indent: int = 4) -> None:
    """Serialise *data* to *path* as JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
    print(f"  Saved → {path}")


def save_dataframe_as_json(
    path: Path,
    df: pd.DataFrame,
    index_col: str = "player_id",
) -> None:
    """
    Write a DataFrame to JSON keyed by *index_col*.

    Output shape: ``{ "<player_id>": { col: val, … }, … }``
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
# Cache helpers (path-aware by necessity — acceptable exception)
# ---------------------------------------------------------------------------

def load_team_map_cache() -> Optional[Dict[int, int]]:
    """
    Load the cached player→team map.

    :returns: ``{player_id: team_id}`` dict, or ``None`` if no cache exists.
    """
    path = DATA_DIR / "team_map_cache.json"
    if not path.exists():
        return None
    with open(path, "r") as f:
        raw = json.load(f)
    return {int(k): int(v) for k, v in raw.items()}


def save_team_map_cache(team_map: Dict[int, int]) -> None:
    """Persist the player→team map to the cache file."""
    save_json(DATA_DIR / "team_map_cache.json", team_map)
