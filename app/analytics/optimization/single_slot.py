"""
app/analytics/optimization/single_slot.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Single-Slot (Coordinate Descent / Greedy Local Search) OptimizationStrategy.

Evaluates one roster slot at a time while holding all other players fixed.
Optimizes for categories won against category target thresholds (h2h opponent stat line
or median threshold) rather than total z-score sum. Uses pandas and numpy for vectorized
stat aggregation and evaluation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd

from app.analytics.optimization.base import OptimizationStrategy
from app.analytics.optimization.utils import eval_score_matrix
from app.domain.optimization import OptimizationResult
from app.domain.scoring import (
    RosterSnapshot,
    ScoredPlayer,
    ScoredPool,
    scored_players_sum_series,
    scored_players_to_dataframe,
)
from app.domain.stats import StatCategory, ZCategory

CategoryKey = Union[str, StatCategory, ZCategory]


class SingleSlotOptimizationStrategy(OptimizationStrategy):
    """
    Greedy coordinate descent optimization for fantasy basketball roster slots.

    Evaluates replacing each player on the current roster with candidates from the available pool
    one slot at a time using vectorized pandas/numpy matrix operations.
    """

    def __init__(
        self,
        target_thresholds: Optional[Dict[CategoryKey, float]] = None,
        punt_categories: Optional[List[CategoryKey]] = None,
        mode: str = "sequential",
        tiebreaker: str = "margin",
        eps: float = 1e-5,
    ) -> None:
        """
        Initialize SingleSlotOptimizationStrategy.

        :param target_thresholds: Dict mapping category name/Enum -> target threshold o_c.
        :param punt_categories: Categories (str or Enum) to concede/ignore during win calculations.
        :param mode: Execution mode ('sequential' or 'simultaneous').
        :param tiebreaker: Secondary objective for ties ('margin', 'total_value', or 'none').
        :param eps: Epsilon margin for strict win determination (totals >= threshold - eps).
        """
        valid_modes = {"sequential", "simultaneous"}
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode '{mode}'. Must be one of {valid_modes}")

        valid_tiebreakers = {"margin", "total_value", "none"}
        if tiebreaker not in valid_tiebreakers:
            raise ValueError(
                f"Invalid tiebreaker '{tiebreaker}'. Must be one of {valid_tiebreakers}"
            )

        self.target_thresholds = {
            (k.value if isinstance(k, (StatCategory, ZCategory)) else str(k)): float(v)
            for k, v in (target_thresholds or {}).items()
        }
        self.punt_categories = {
            (c.value if isinstance(c, (StatCategory, ZCategory)) else str(c))
            for c in (punt_categories or [])
        }
        self.mode = mode
        self.tiebreaker = tiebreaker
        self.eps = eps

    def optimize(
        self,
        candidate_pool: ScoredPool,
        current_roster: Optional[RosterSnapshot] = None,
    ) -> OptimizationResult:
        """
        Execute single-slot optimization over candidate_pool and current_roster.

        :param candidate_pool: Available scored player pool.
        :param current_roster: Required current roster snapshot.
        :returns: OptimizationResult containing the updated roster, categories won, and metadata.
        :raises ValueError: If current_roster is None or empty.
        """
        if current_roster is None or not current_roster.scored_players:
            raise ValueError("SingleSlotOptimizationStrategy requires a non-empty current_roster.")

        roster_players: List[ScoredPlayer] = list(current_roster.scored_players.values())
        roster_player_ids: Set[int] = {sp.player.player_id for sp in roster_players}

        # Available candidates (exclude players currently rostered)
        available_candidates: List[ScoredPlayer] = [
            sp for sp in candidate_pool.scored_players.values()
            if sp.player.player_id not in roster_player_ids
        ]

        # Active categories
        first_player = roster_players[0]
        all_categories = list(first_player.category_scores.scores.keys())
        active_categories: List[str] = [c for c in all_categories if c not in self.punt_categories]

        # Build category threshold numpy vector (shape: N_categories,)
        thresh_vec = np.array([self.target_thresholds.get(c, 0.0) for c in active_categories], dtype=float)

        # Compute initial roster baseline
        initial_series = current_roster.category_series(active_categories)
        init_wins_arr, init_margins_arr, init_z_arr = eval_score_matrix(
            initial_series.values.reshape(1, -1), thresh_vec, self.eps
        )
        init_won = int(init_wins_arr[0])
        init_margin = float(init_margins_arr[0])
        init_z = float(init_z_arr[0])

        current_roster_list: List[ScoredPlayer] = list(roster_players)
        swap_history: List[Dict[str, Any]] = []

        if self.mode == "sequential":
            for k in range(len(current_roster_list)):
                incumbent = current_roster_list[k]
                others = current_roster_list[:k] + current_roster_list[k + 1:]
                baseline_series = scored_players_sum_series(others, active_categories)

                incumbent_series = baseline_series + incumbent.to_series(active_categories)
                inc_wins_arr, inc_margins_arr, inc_z_arr = eval_score_matrix(
                    incumbent_series.values.reshape(1, -1), thresh_vec, self.eps
                )
                inc_won = int(inc_wins_arr[0])
                inc_margin = float(inc_margins_arr[0])
                inc_z = float(inc_z_arr[0])

                best_cand = incumbent
                best_won = inc_won
                best_margin = inc_margin
                best_z = inc_z

                if available_candidates:
                    cand_df = scored_players_to_dataframe(available_candidates, active_categories)
                    cand_matrix = cand_df.values + baseline_series.values  # Broadcast addition: (N, C) + (C,)
                    cand_wins, cand_margins, cand_zs = eval_score_matrix(cand_matrix, thresh_vec, self.eps)

                    for i, cand in enumerate(available_candidates):
                        c_won = int(cand_wins[i])
                        c_margin = float(cand_margins[i])
                        c_z = float(cand_zs[i])

                        is_better = False
                        if c_won > best_won:
                            is_better = True
                        elif c_won == best_won:
                            if self.tiebreaker == "margin" and c_margin > best_margin + self.eps:
                                is_better = True
                            elif self.tiebreaker == "total_value" and c_z > best_z + self.eps:
                                is_better = True

                        if is_better:
                            best_cand = cand
                            best_won = c_won
                            best_margin = c_margin
                            best_z = c_z

                if best_cand.player.player_id != incumbent.player.player_id:
                    current_roster_list[k] = best_cand
                    available_candidates = [
                        c for c in available_candidates if c.player.player_id != best_cand.player.player_id
                    ] + [incumbent]
                    swap_history.append({
                        "slot_index": k,
                        "drop_player_id": incumbent.player.player_id,
                        "drop_player_name": incumbent.player.name,
                        "add_player_id": best_cand.player.player_id,
                        "add_player_name": best_cand.player.name,
                        "categories_won_before": inc_won,
                        "categories_won_after": best_won,
                        "categories_won_diff": best_won - inc_won,
                        "margin_before": inc_margin,
                        "margin_after": best_margin,
                    })

        elif self.mode == "simultaneous":
            proposed_swaps = []
            for k in range(len(current_roster_list)):
                incumbent = current_roster_list[k]
                others = current_roster_list[:k] + current_roster_list[k + 1:]
                baseline_series = scored_players_sum_series(others, active_categories)

                incumbent_series = baseline_series + incumbent.to_series(active_categories)
                inc_wins_arr, inc_margins_arr, inc_z_arr = eval_score_matrix(
                    incumbent_series.values.reshape(1, -1), thresh_vec, self.eps
                )
                inc_won = int(inc_wins_arr[0])
                inc_margin = float(inc_margins_arr[0])
                inc_z = float(inc_z_arr[0])

                best_cand = None
                best_won = inc_won
                best_margin = inc_margin
                best_z = inc_z

                if available_candidates:
                    cand_df = scored_players_to_dataframe(available_candidates, active_categories)
                    cand_matrix = cand_df.values + baseline_series.values
                    cand_wins, cand_margins, cand_zs = eval_score_matrix(cand_matrix, thresh_vec, self.eps)


                    for i, cand in enumerate(available_candidates):
                        c_won = int(cand_wins[i])
                        c_margin = float(cand_margins[i])
                        c_z = float(cand_zs[i])

                        is_better = False
                        if c_won > best_won:
                            is_better = True
                        elif c_won == best_won:
                            if self.tiebreaker == "margin" and c_margin > best_margin + self.eps:
                                is_better = True
                            elif self.tiebreaker == "total_value" and c_z > best_z + self.eps:
                                is_better = True

                        if is_better:
                            best_cand = cand
                            best_won = c_won
                            best_margin = c_margin
                            best_z = c_z

                if best_cand is not None:
                    gain_won = best_won - inc_won
                    gain_margin = best_margin - inc_margin
                    gain_z = best_z - inc_z
                    proposed_swaps.append((
                        k, incumbent, best_cand, best_won, gain_won, best_margin, gain_margin, gain_z
                    ))

            def _swap_sort_key(s: tuple) -> tuple:
                return (s[4], s[6] if self.tiebreaker == "margin" else s[7])

            proposed_swaps.sort(key=_swap_sort_key, reverse=True)
            claimed_candidates: Set[int] = set()

            for k, incumbent, best_cand, best_won, gain_won, best_margin, gain_margin, gain_z in proposed_swaps:
                if best_cand.player.player_id in claimed_candidates:
                    continue
                claimed_candidates.add(best_cand.player.player_id)
                current_roster_list[k] = best_cand
                swap_history.append({
                    "slot_index": k,
                    "drop_player_id": incumbent.player.player_id,
                    "drop_player_name": incumbent.player.name,
                    "add_player_id": best_cand.player.player_id,
                    "add_player_name": best_cand.player.name,
                    "categories_won_before": best_won - gain_won,
                    "categories_won_after": best_won,
                    "categories_won_diff": gain_won,
                    "margin_before": best_margin - gain_margin,
                    "margin_after": best_margin,
                })

        final_series = scored_players_sum_series(current_roster_list, active_categories)
        final_wins_arr, final_margins_arr, final_z_arr = eval_score_matrix(
            final_series.values.reshape(1, -1), thresh_vec, self.eps
        )

        final_won = int(final_wins_arr[0])
        final_margin = float(final_margins_arr[0])
        final_z = float(final_z_arr[0])

        summary_metrics: Dict[str, float] = {
            f"total_{cat}": round(float(final_series[cat]), 4) for cat in active_categories
        }
        summary_metrics.update({
            "categories_won": float(final_won),
            "categories_lost": float(len(active_categories) - final_won),
            "total_margin": round(final_margin, 4),
            "total_zscore": round(final_z, 4),
        })

        metadata: Dict[str, Any] = {
            "strategy": "SingleSlotOptimizationStrategy",
            "mode": self.mode,
            "tiebreaker": self.tiebreaker,
            "target_thresholds": self.target_thresholds,
            "punt_categories": list(self.punt_categories),
            "initial_categories_won": init_won,
            "final_categories_won": final_won,
            "swaps_made": len(swap_history),
            "swap_history": swap_history,
        }

        return OptimizationResult(
            selected_players=current_roster_list,
            objective_value=float(final_won),
            summary_metrics=summary_metrics,
            metadata=metadata,
        )
