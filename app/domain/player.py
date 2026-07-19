"""
app/domain/player.py
~~~~~~~~~~~~~~~~~~~~~
Player and PlayerPool domain objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from app.domain.stats import PlayerStats


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------

@dataclass
class Player:
    """
    A single NBA player with stat lines for up to three windows.
    ``stats_curr_season`` is the default window used by the scoring layer.
    """

    player_id: int
    name: str
    positions: List[str] = field(default_factory=list)
    stats_curr_season: Optional[PlayerStats] = None
    stats_prev_season: Optional[PlayerStats] = None
    stats_last_10: Optional[PlayerStats] = None

    def get_stats(self, source: str) -> Optional[PlayerStats]:
        """
        Return the stats window identified by *source*.

        :param source: ``"stats_curr_season"`` | ``"stats_prev_season"`` | ``"stats_last_10"``
        """
        return {
            "stats_curr_season": self.stats_curr_season,
            "stats_prev_season": self.stats_prev_season,
            "stats_last_10":     self.stats_last_10,
        }.get(source)


# ---------------------------------------------------------------------------
# PlayerPool
# ---------------------------------------------------------------------------

@dataclass
class PlayerPool:
    """
    The full set of players with their raw stat lines.

    Produced by the ingestion layer; consumed by the analytics layer.
    Does not contain any scores — scoring is a separate step.
    """

    players: Dict[int, Player]   # player_id (int) → Player

    # ------------------------------------------------------------------
    # Collection interface
    # ------------------------------------------------------------------

    def get(self, player_id: int) -> Optional[Player]:
        return self.players.get(player_id)

    def __len__(self) -> int:
        return len(self.players)

    # ------------------------------------------------------------------
    # Conversion to DataFrame (used by scoring strategies)
    # ------------------------------------------------------------------

    def to_dataframe(self, stats_source: str = "stats_curr_season") -> pd.DataFrame:
        """
        Flatten the pool to a single DataFrame row per player.

        Players with no stats for *stats_source* are excluded.
        The ``"3PTM"`` column name is used (not ``"three_ptm"``) so it
        matches the STAT_MAP column references.

        :param stats_source: Which window to flatten.
        :returns: DataFrame with columns:
                  player_id, name, FGM, FGA, FTM, FTA, 3PTM, PTS, REB,
                  AST, ST, BLK, TO, GP, MIN, FG%, FT%
        """
        rows = []
        for player in self.players.values():
            stats = player.get_stats(stats_source)
            if stats is None:
                continue
            row = {"player_id": player.player_id, "name": player.name}
            row.update(stats.to_dict())
            rows.append(row)
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Serialisation (data.json format)
    # ------------------------------------------------------------------

    @classmethod
    def from_raw_dict(cls, raw: dict) -> "PlayerPool":
        """
        Deserialise from the ``data.json`` format::

            { "<player_id_str>": {
                "player_id": ..., "name": ..., "positions": [...],
                "stats_curr_season": {...}, "stats_prev_season": {...},
                "stats_last_10": {...}
              }, ... }
        """
        players: Dict[int, Player] = {}
        for pid_str, info in raw.items():
            pid = int(pid_str)

            def _load(key: str) -> Optional[PlayerStats]:
                d = info.get(key)
                return PlayerStats.from_dict(d) if d else None

            players[pid] = Player(
                player_id=pid,
                name=info.get("name", "Unknown"),
                positions=info.get("positions", []),
                stats_curr_season=_load("stats_curr_season"),
                stats_prev_season=_load("stats_prev_season"),
                stats_last_10=_load("stats_last_10"),
            )
        return cls(players=players)

    def to_raw_dict(self) -> dict:
        """Serialise to the ``data.json`` format."""
        result: dict = {}
        for pid, player in self.players.items():
            result[str(pid)] = {
                "player_id": pid,
                "name": player.name,
                "positions": player.positions,
                "stats_curr_season": (
                    player.stats_curr_season.to_dict()
                    if player.stats_curr_season else {}
                ),
                "stats_prev_season": (
                    player.stats_prev_season.to_dict()
                    if player.stats_prev_season else {}
                ),
                "stats_last_10": (
                    player.stats_last_10.to_dict()
                    if player.stats_last_10 else {}
                ),
                "combined_stats": {},
            }
        return result
