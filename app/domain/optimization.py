"""
app/domain/optimization.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Optimization domain objects: OptimizationResult.

Contains data structures representing the outputs of optimization strategies.
These domain models contain no mathematical logic or solver engines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from app.domain.scoring import ScoredPlayer


@dataclass
class OptimizationResult:
    """
    Result of a roster optimization pass.

    Contains the selected optimal combination of players, overall summary metrics
    (e.g., projected category totals, objective score, risk/variance metrics),
    and execution metadata.

    Attributes:
        selected_players: List of ScoredPlayer domain objects representing the chosen
            optimal roster composition or player subset.
        objective_value: Scalar evaluation score produced by the objective function
            (e.g. Sharpe ratio, win probability, total z-score value).
        summary_metrics: Dictionary of aggregate quantitative metrics across the
            selected players (e.g. category totals, portfolio variance, entropy).
        metadata: Execution details, solver status, algorithm parameters, and swap tracking.
    """

    selected_players: List[ScoredPlayer] = field(default_factory=list)
    objective_value: float = 0.0
    summary_metrics: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
