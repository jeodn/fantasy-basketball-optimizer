"""
app/analytics/optimization/base.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
OptimizationStrategy — abstract base class for portfolio theory and combinatorial
roster optimization.

Contract
--------
Input:  ScoredPool (scored player data), optional RosterSnapshot (current roster)
Output: OptimizationResult (optimal roster combination, metrics, metadata)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.domain.optimization import OptimizationResult
from app.domain.scoring import RosterSnapshot, ScoredPool


class OptimizationStrategy(ABC):
    """
    Interface for portfolio and combinatorial roster optimization algorithms.

    Implementations (e.g. Modern Portfolio Theory, Mean-Variance Optimization,
    Integer Linear Programming) should accept configuration (target roster size,
    category priorities, risk tolerance) in ``__init__`` and remain stateless
    with respect to the inputs passed to ``optimize()``.
    """

    @abstractmethod
    def optimize(
        self,
        candidate_pool: ScoredPool,
        current_roster: Optional[RosterSnapshot] = None,
    ) -> OptimizationResult:
        """
        Execute optimization over candidate_pool to produce an optimal player selection.

        :param candidate_pool: Available players with scores. Must not be mutated.
        :param current_roster: Optional current roster snapshot for baseline or swap constraints.
        :returns:             OptimizationResult containing selected players and metrics.
        """
        ...
