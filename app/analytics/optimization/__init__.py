"""
app/analytics/optimization
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Package for portfolio theory and combinatorial roster optimization.
"""

from app.domain.optimization import OptimizationResult
from app.analytics.optimization.base import OptimizationStrategy

__all__ = ["OptimizationStrategy", "OptimizationResult"]
