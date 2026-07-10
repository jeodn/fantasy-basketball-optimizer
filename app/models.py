"""
app/models.py
~~~~~~~~~~~~~
Shared constants and pure data definitions used across layers.
No business logic, no I/O.
"""

from __future__ import annotations
from typing import List, Tuple

# ---------------------------------------------------------------------------
# NBA API column name  ->  internal app column name
# ---------------------------------------------------------------------------
STATS_MAPPING: dict[str, str] = {
    "MIN": "MIN",
    "FGM": "FGM",
    "FGA": "FGA",
    "FG_PCT": "FG%",
    "FG3M": "3PTM",
    "FTM": "FTM",
    "FTA": "FTA",
    "FT_PCT": "FT%",
    "PTS": "PTS",
    "REB": "REB",
    "AST": "AST",
    "STL": "ST",
    "BLK": "BLK",
    "TOV": "TO",
    "GP": "GP",
}

# ---------------------------------------------------------------------------
# 9-category stat map used for z-score calculation.
# Each entry: (display_name, dataframe_column, higher_is_better)
# ---------------------------------------------------------------------------
STAT_MAP: List[Tuple[str, str, bool]] = [
    ("FG%", "FG%_Impact", True),
    ("FT%", "FT%_Impact", True),
    ("3PTM", "3PTM", True),
    ("PTS", "PTS", True),
    ("REB", "REB", True),
    ("AST", "AST", True),
    ("ST", "ST", True),
    ("BLK", "BLK", True),
    ("TO", "TO", False),  # lower is better
]

# ---------------------------------------------------------------------------
# Raw stat columns present after process_data()
# ---------------------------------------------------------------------------
RAW_STAT_COLS: List[str] = [
    "FGM", "FGA", "FTM", "FTA",
    "3PTM", "PTS", "REB", "AST",
    "ST", "BLK", "TO", "GP",
    "FG%", "FT%",
]

# ---------------------------------------------------------------------------
# Counting stats that scale with minutes (used in injury redistribution)
# ---------------------------------------------------------------------------
SCALABLE_STAT_COLS: List[str] = [
    "FGM", "FGA", "FTM", "FTA",
    "3PTM", "PTS", "REB", "AST",
    "ST", "BLK", "TO",
]
