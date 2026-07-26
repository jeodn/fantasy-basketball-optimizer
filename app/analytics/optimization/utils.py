"""
app/analytics/optimization/utils.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Vectorized scoring and evaluation utilities for optimization strategies.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np


def eval_score_matrix(
    matrix: np.ndarray,
    target_thresholds: np.ndarray,
    eps: float = 1e-5,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Vectorized category score evaluation for a 2D matrix of shape (N, C).

    :param matrix: 2D array of totals (N candidates x C categories).
    :param target_thresholds: 1D array of category threshold target values o_c (C categories).
    :param eps: Epsilon offset for win determination.
    :returns: Tuple of 1D arrays of length N:
              - categories_won (int array)
              - margin_sum (float array)
              - total_zscore (float array)
    """
    wins = (matrix >= (target_thresholds - eps)).sum(axis=1)
    margins = (matrix - target_thresholds).sum(axis=1)
    total_z = matrix.sum(axis=1)
    return wins, margins, total_z
