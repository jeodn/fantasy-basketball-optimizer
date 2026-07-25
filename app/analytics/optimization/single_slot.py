"""
app/analytics/optimization/single_slot.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Single-Slot (Coordinate Descent / Greedy Local Search) OptimizationStrategy.

Evaluates one roster slot at a time while holding all other players fixed.
Optimizes for categories won against category target thresholds (h2h opponent stat line
or median threshold) rather than total z-score sum.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from app.analytics.optimization.base import OptimizationStrategy
from app.domain.optimization import OptimizationResult
from app.domain.scoring import RosterSnapshot, ScoredPlayer, ScoredPool


class SingleSlotOptimizationStrategy(OptimizationStrategy):
    """
    Greedy coordinate descent optimization for fantasy basketball roster slots.

    Evaluates replacing each player on the current roster with candidates from the available pool
    one slot at a time. Candidates are evaluated by counting categories won against target thresholds.
    """

    def __init__(
        self,
        target_thresholds: Optional[Dict[str, float]] = None,
        punt_categories: Optional[List[str]] = None,
        mode: str = "sequential",
        tiebreaker: str = "margin",
        eps: float = 1e-5,
    ) -> None:
        """
        Initialize SingleSlotOptimizationStrategy.

        :param target_thresholds: Dict mapping category name (e.g. 'zPTS' or 'PTS') -> target threshold o_c.
        :param punt_categories: Categories to concede/ignore during win calculations.
        :param mode: Execution mode ('sequential' or 'simultaneous').
        :param tiebreaker: Secondary objective for ties ('margin', 'total_value', or 'none').
        :param eps: Epsilon margin for strict win determination (totals >= threshold + eps).
        """
        valid_modes = {"sequential", "simultaneous"}
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode '{mode}'. Must be one of {valid_modes}")

        valid_tiebreakers = {"margin", "total_value", "none"}
        if tiebreaker not in valid_tiebreakers:
            raise ValueError(
                f"Invalid tiebreaker '{tiebreaker}'. Must be one of {valid_tiebreakers}"
            )

        self.target_thresholds = target_thresholds or {}
        self.punt_categories = set(punt_categories or [])
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

        # Determine active category names
        first_player = roster_players[0]
        all_categories = list(first_player.category_scores.scores.keys())
        active_categories = [c for c in all_categories if c not in self.punt_categories]

        def _sum_stats(players: List[ScoredPlayer]) -> Dict[str, float]:
            totals: Dict[str, float] = {cat: 0.0 for cat in active_categories}
            for p in players:
                for cat in active_categories:
                    totals[cat] += p.category_scores.scores.get(cat, 0.0)
            return totals

        def _eval_totals(totals: Dict[str, float]) -> tuple[int, float, float]:
            won = 0
            margin_sum = 0.0
            total_z = 0.0
            for cat in active_categories:
                val = totals[cat]
                thresh = self.target_thresholds.get(cat, 0.0)
                diff = val - thresh
                if val >= thresh - self.eps:
                    won += 1
                margin_sum += diff
                total_z += val
            return won, margin_sum, total_z


        initial_totals = _sum_stats(roster_players)
        init_won, init_margin, init_z = _eval_totals(initial_totals)

        current_roster_list: List[ScoredPlayer] = list(roster_players)
        swap_history: List[Dict[str, Any]] = []

        if self.mode == "sequential":
            for k in range(len(current_roster_list)):
                incumbent = current_roster_list[k]
                others = current_roster_list[:k] + current_roster_list[k + 1:]
                baseline_totals = _sum_stats(others)

                incumbent_totals = {
                    c: baseline_totals[c] + incumbent.category_scores.scores.get(c, 0.0)
                    for c in active_categories
                }
                inc_won, inc_margin, inc_z = _eval_totals(incumbent_totals)

                best_cand = incumbent
                best_won = inc_won
                best_margin = inc_margin
                best_z = inc_z

                for cand in available_candidates:
                    cand_totals = {
                        c: baseline_totals[c] + cand.category_scores.scores.get(c, 0.0)
                        for c in active_categories
                    }
                    cand_won, cand_margin, cand_z = _eval_totals(cand_totals)

                    is_better = False
                    if cand_won > best_won:
                        is_better = True
                    elif cand_won == best_won:
                        if self.tiebreaker == "margin" and cand_margin > best_margin + self.eps:
                            is_better = True
                        elif self.tiebreaker == "total_value" and cand_z > best_z + self.eps:
                            is_better = True

                    if is_better:
                        best_cand = cand
                        best_won = cand_won
                        best_margin = cand_margin
                        best_z = cand_z

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
                baseline_totals = _sum_stats(others)

                incumbent_totals = {
                    c: baseline_totals[c] + incumbent.category_scores.scores.get(c, 0.0)
                    for c in active_categories
                }
                inc_won, inc_margin, inc_z = _eval_totals(incumbent_totals)

                best_cand = None
                best_won = inc_won
                best_margin = inc_margin
                best_z = inc_z

                for cand in available_candidates:
                    cand_totals = {
                        c: baseline_totals[c] + cand.category_scores.scores.get(c, 0.0)
                        for c in active_categories
                    }
                    cand_won, cand_margin, cand_z = _eval_totals(cand_totals)

                    is_better = False
                    if cand_won > best_won:
                        is_better = True
                    elif cand_won == best_won:
                        if self.tiebreaker == "margin" and cand_margin > best_margin + self.eps:
                            is_better = True
                        elif self.tiebreaker == "total_value" and cand_z > best_z + self.eps:
                            is_better = True

                    if is_better:
                        best_cand = cand
                        best_won = cand_won
                        best_margin = cand_margin
                        best_z = cand_z

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

        final_totals = _sum_stats(current_roster_list)
        final_won, final_margin, final_z = _eval_totals(final_totals)

        summary_metrics: Dict[str, float] = {
            f"total_{cat}": round(final_totals[cat], 4) for cat in active_categories
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
