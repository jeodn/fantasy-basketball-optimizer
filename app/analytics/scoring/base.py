"""
app/analytics/scoring/base.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
ScoringStrategy — the abstract base class every scoring system must implement.

Contract
--------
Input:  PlayerPool  (raw stats, produced by the ingestion layer)
Output: ScoredPool  (scored players, consumed by evaluation / pipeline)

Any class that inherits ScoringStrategy can be passed to pipeline commands
or the evaluation engine without any other changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.player import PlayerPool
from app.domain.scoring import ScoredPool


class ScoringStrategy(ABC):
    """
    Interface for all fantasy scoring systems.

    Implementations must be stateless with respect to the pool they receive
    (i.e. ``score()`` must not mutate *pool*). Configuration (weights,
    punt categories, stats window, etc.) is injected via ``__init__``.
    """

    @abstractmethod
    def score(self, pool: PlayerPool) -> ScoredPool:
        """
        Score every player in *pool* and return a ScoredPool.

        :param pool: The PlayerPool to score. Must not be mutated.
        :returns:    A new ScoredPool; does not share state with *pool*.
        """
        ...
