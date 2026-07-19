"""
app/ingestion/roster_ingestion.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Builds a RosterSnapshot from a ScoredPool and a Roster definition.
"""

from __future__ import annotations

from app.domain.roster import Roster
from app.domain.scoring import RosterSnapshot, ScoredPool


def build_roster_snapshot(scored_pool: ScoredPool, roster: Roster) -> RosterSnapshot:
    """
    Slice *scored_pool* to the players on *roster*.

    Players in *roster.player_ids* that are not present in *scored_pool*
    (e.g. they had no stats for the active scoring window) are silently
    omitted rather than raising an error.

    :param scored_pool: The full scored player pool.
    :param roster:      The roster to slice for.
    :returns:           RosterSnapshot containing only the roster's players.
    """
    return scored_pool.get_roster_snapshot(roster)
