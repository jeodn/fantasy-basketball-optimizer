"""
app/analytics/optimization
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Package for portfolio theory and combinatorial roster optimization.
"""

from app.domain.optimization import OptimizationResult
from app.analytics.optimization.base import OptimizationStrategy
from app.analytics.optimization.single_slot import SingleSlotOptimizationStrategy

__all__ = [
    "OptimizationStrategy",
    "SingleSlotOptimizationStrategy",
    "OptimizationResult",
]



