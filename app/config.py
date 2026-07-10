"""
app/config.py
~~~~~~~~~~~~~
Loads config.yaml from the project root and exposes a single typed
AppConfig object. All other modules import from here — no hardcoded
constants elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT_DIR: Path = Path(__file__).parent.parent
DATA_DIR: Path = ROOT_DIR / "data"
CONFIG_FILE: Path = ROOT_DIR / "config.yaml"

DATA_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Config dataclasses
# ---------------------------------------------------------------------------
@dataclass
class SeasonConfig:
    current: str
    previous: str


@dataclass
class ScoringConfig:
    stats_source: str
    punt_categories: List[str]
    category_weights: Dict[str, float]


@dataclass
class RosterConfig:
    my_team: List[int]
    matchup_team: List[int]
    drop_candidate: int


@dataclass
class AppConfig:
    season: SeasonConfig
    scoring: ScoringConfig
    roster: RosterConfig


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------
def load_config(path: Path = CONFIG_FILE) -> AppConfig:
    """Parse config.yaml and return a validated AppConfig."""
    with open(path, "r") as f:
        raw = yaml.safe_load(f)

    season = SeasonConfig(
        current=raw["season"]["current"],
        previous=raw["season"]["previous"],
    )

    scoring_raw = raw["scoring"]
    scoring = ScoringConfig(
        stats_source=scoring_raw["stats_source"],
        punt_categories=scoring_raw.get("punt_categories", []),
        category_weights={
            k: float(v) for k, v in scoring_raw["category_weights"].items()
        },
    )

    roster_raw = raw["roster"]
    roster = RosterConfig(
        my_team=[int(p) for p in roster_raw["my_team"]],
        matchup_team=[int(p) for p in roster_raw["matchup_team"]],
        drop_candidate=int(roster_raw["drop_candidate"]),
    )

    return AppConfig(season=season, scoring=scoring, roster=roster)


# ---------------------------------------------------------------------------
# Module-level singleton — import this everywhere
# ---------------------------------------------------------------------------
config: AppConfig = load_config()
