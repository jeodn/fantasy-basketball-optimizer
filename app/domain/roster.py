"""
app/domain/roster.py
~~~~~~~~~~~~~~~~~~~~~
Roster — a named list of player IDs (my_team or matchup_team).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class Roster:
    """
    A named list of player IDs representing a fantasy team.

    ``name`` is used as a label in outputs (e.g. ``"my_team"``).
    """

    name: str
    player_ids: List[int] = field(default_factory=list)
