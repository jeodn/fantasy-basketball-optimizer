"""
app/domain/scoring.py
~~~~~~~~~~~~~~~~~~~~~~
Scored domain objects: CategoryScores, ScoredPlayer, ScoredPool, RosterSnapshot.

These are produced by the analytics layer (scoring strategies) and consumed
by the evaluation and pipeline layers. They contain no business logic —
only data and the structural operations needed to navigate that data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from app.domain.player import Player
from app.domain.roster import Roster


# ---------------------------------------------------------------------------
# Per-player scored output
# ---------------------------------------------------------------------------

@dataclass
class CategoryScores:
    """
    The scoring result for a single player across all categories.

    ``scores`` maps column name → float value and contains:
      - All z-score columns (``zFG%``, ``zPTS``, …, ``zTO``)
      - Impact columns (``FG%_Impact``, ``FT%_Impact``)

    ``total_value`` is the sum of z-score columns only (not impact columns).
    """

    scores: Dict[str, float] = field(default_factory=dict)
    total_value: float = 0.0


@dataclass
class ScoredPlayer:
    """A Player paired with the output of a ScoringStrategy."""

    player: Player
    category_scores: CategoryScores


# ---------------------------------------------------------------------------
# Roster-level scored view
# ---------------------------------------------------------------------------

@dataclass
class RosterSnapshot:
    """
    A Roster's players looked up from a ScoredPool.

    Produced by ingestion/roster_ingestion (or ScoredPool.get_roster_snapshot).
    Used by the evaluation layer to understand the current team's category profile.
    """

    roster: Roster
    scored_players: Dict[int, ScoredPlayer] = field(default_factory=dict)

    @property
    def category_totals(self) -> Dict[str, float]:
        """Sum of each score column across all roster players."""
        totals: Dict[str, float] = {}
        for sp in self.scored_players.values():
            for cat, val in sp.category_scores.scores.items():
                totals[cat] = round(totals.get(cat, 0.0) + val, 3)
        totals["Total_Value"] = round(
            sum(sp.category_scores.total_value for sp in self.scored_players.values()), 3
        )
        return totals

    def to_dict(self) -> dict:
        """
        Serialise to the ``data_myteam.json`` / ``data_matchup.json`` format::

            { "<player_id>": { "name": ..., "Total_Value": ..., <scores...> } }
        """
        result: dict = {}
        for pid, sp in self.scored_players.items():
            result[str(pid)] = {
                "name": sp.player.name,
                "Total_Value": sp.category_scores.total_value,
                **sp.category_scores.scores,
            }
        return result


# ---------------------------------------------------------------------------
# Full scored player pool
# ---------------------------------------------------------------------------

@dataclass
class ScoredPool:
    """
    The full set of players after a ScoringStrategy has been applied.

    Produced by analytics/scoring; consumed by analytics/evaluation and
    the pipeline layer.
    """

    scored_players: Dict[int, ScoredPlayer] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Collection interface
    # ------------------------------------------------------------------

    def get(self, player_id: int) -> Optional[ScoredPlayer]:
        return self.scored_players.get(player_id)

    def __len__(self) -> int:
        return len(self.scored_players)

    # ------------------------------------------------------------------
    # Roster operations
    # ------------------------------------------------------------------

    def get_roster_snapshot(self, roster: Roster) -> RosterSnapshot:
        """Slice this pool to the players on *roster*."""
        scored = {
            pid: self.scored_players[pid]
            for pid in roster.player_ids
            if pid in self.scored_players
        }
        return RosterSnapshot(roster=roster, scored_players=scored)

    # ------------------------------------------------------------------
    # DataFrame conversion (used by pipeline for persistence)
    # ------------------------------------------------------------------

    def to_dataframe(self) -> pd.DataFrame:
        """
        Flatten to a DataFrame suitable for saving or Streamlit display.

        Columns: player_id, name, Total_Value, <score columns>,
        and raw stat columns when the ScoredPlayer's player object has
        ``stats_curr_season`` populated (i.e. when built from a full
        PlayerPool rather than from a checkpoint file).
        """
        rows: List[dict] = []
        for pid, sp in self.scored_players.items():
            row: dict = {
                "player_id": pid,
                "name": sp.player.name,
                "Total_Value": sp.category_scores.total_value,
                **sp.category_scores.scores,
            }
            # Include raw stats when available (pool built from data.json)
            if sp.player.stats_curr_season is not None:
                row.update(sp.player.stats_curr_season.to_dict())
            rows.append(row)

        df = pd.DataFrame(rows)
        return (
            df.sort_values("Total_Value", ascending=False)
            if not df.empty
            else df
        )

    # ------------------------------------------------------------------
    # Deserialisation from checkpoint (data_zscores.json)
    # ------------------------------------------------------------------

    @classmethod
    def from_zscores_dict(cls, raw: dict) -> "ScoredPool":
        """
        Reconstruct a ScoredPool from the ``data_zscores.json`` format.

        Player objects will have no raw stats (only name and player_id),
        since the checkpoint file stores only scores. This is sufficient
        for evaluation and roster operations.
        """
        scored_players: Dict[int, ScoredPlayer] = {}

        for pid_str, data in raw.items():
            pid = int(pid_str)

            scores = {
                k: float(v)
                for k, v in data.items()
                if k not in ("name", "Total_Value") and isinstance(v, (int, float))
            }
            total_value = float(data.get("Total_Value", 0.0))

            player = Player(
                player_id=pid,
                name=str(data.get("name", "Unknown")),
            )
            scored_players[pid] = ScoredPlayer(
                player=player,
                category_scores=CategoryScores(
                    scores=scores,
                    total_value=total_value,
                ),
            )

        return cls(scored_players=scored_players)
