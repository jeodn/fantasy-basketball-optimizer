"""
app/domain/stats.py
~~~~~~~~~~~~~~~~~~~~
PlayerStats — the canonical per-game stat line.
Also owns the shared stat-schema constants (STAT_MAP, SCALABLE_STAT_COLS, RAW_STAT_COLS)
since they are properties of the stat domain, not of any service.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


# ---------------------------------------------------------------------------
# Core dataclass
# ---------------------------------------------------------------------------

@dataclass
class PlayerStats:
    """
    A per-game stat line for a single window (season average, last-10, or
    a projected/redistributed line from the ingestion layer).

    Note: three-point makes are stored as ``three_ptm`` to avoid the
    Python-identifier restriction on leading digits; all serialisation uses
    the canonical ``"3PTM"`` key.
    """

    FGM: float = 0.0
    FGA: float = 0.0
    FTM: float = 0.0
    FTA: float = 0.0
    three_ptm: float = 0.0      # serialises as "3PTM"
    PTS: float = 0.0
    REB: float = 0.0
    AST: float = 0.0
    ST: float = 0.0
    BLK: float = 0.0
    TO: float = 0.0
    GP: int = 0
    MIN: float = 0.0

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def fg_pct(self) -> float:
        return self.FGM / self.FGA if self.FGA > 0 else 0.0

    @property
    def ft_pct(self) -> float:
        return self.FTM / self.FTA if self.FTA > 0 else 0.0

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, d: dict) -> "PlayerStats":
        """Deserialise from the app's stat-dict format (as stored in data.json)."""
        return cls(
            FGM=float(d.get("FGM", 0)),
            FGA=float(d.get("FGA", 0)),
            FTM=float(d.get("FTM", 0)),
            FTA=float(d.get("FTA", 0)),
            three_ptm=float(d.get("3PTM", 0)),
            PTS=float(d.get("PTS", 0)),
            REB=float(d.get("REB", 0)),
            AST=float(d.get("AST", 0)),
            ST=float(d.get("ST", 0)),
            BLK=float(d.get("BLK", 0)),
            TO=float(d.get("TO", 0)),
            GP=int(d.get("GP", 0)),
            MIN=float(d.get("MIN", 0)),
        )

    def to_dict(self) -> dict:
        """Serialise to the app's stat-dict format."""
        return {
            "FGM": self.FGM,
            "FGA": self.FGA,
            "FTM": self.FTM,
            "FTA": self.FTA,
            "3PTM": self.three_ptm,
            "PTS": self.PTS,
            "REB": self.REB,
            "AST": self.AST,
            "ST": self.ST,
            "BLK": self.BLK,
            "TO": self.TO,
            "GP": self.GP,
            "MIN": self.MIN,
            "FG%": self.fg_pct,
            "FT%": self.ft_pct,
        }


# ---------------------------------------------------------------------------
# Stat-schema constants
# (live here because they describe the domain, not any service)
# ---------------------------------------------------------------------------

# 9-category stat map: (display_name, dataframe_column, higher_is_better)
# FG%/FT% reference their *impact* columns (volume-weighted; computed during scoring).
STAT_MAP: List[Tuple[str, str, bool]] = [
    ("FG%",  "FG%_Impact", True),
    ("FT%",  "FT%_Impact", True),
    ("3PTM", "3PTM",       True),
    ("PTS",  "PTS",        True),
    ("REB",  "REB",        True),
    ("AST",  "AST",        True),
    ("ST",   "ST",         True),
    ("BLK",  "BLK",        True),
    ("TO",   "TO",         False),   # lower is better
]

# Counting stats that scale proportionally with redistributed minutes
SCALABLE_STAT_COLS: List[str] = [
    "FGM", "FGA", "FTM", "FTA",
    "3PTM", "PTS", "REB", "AST",
    "ST", "BLK", "TO",
]

# Raw stat columns present in a flattened stat DataFrame
RAW_STAT_COLS: List[str] = [
    "FGM", "FGA", "FTM", "FTA",
    "3PTM", "PTS", "REB", "AST",
    "ST", "BLK", "TO", "GP",
    "FG%", "FT%", "MIN",
]
