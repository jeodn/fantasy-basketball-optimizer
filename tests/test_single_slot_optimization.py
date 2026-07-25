"""
tests/test_single_slot_optimization.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for SingleSlotOptimizationStrategy.
"""

import unittest

from app.analytics.optimization.single_slot import SingleSlotOptimizationStrategy
from app.domain.player import Player
from app.domain.roster import Roster
from app.domain.scoring import CategoryScores, RosterSnapshot, ScoredPlayer, ScoredPool


def _create_scored_player(pid: int, name: str, scores: dict[str, float]) -> ScoredPlayer:
    total_val = sum(scores.values())
    return ScoredPlayer(
        player=Player(player_id=pid, name=name),
        category_scores=CategoryScores(scores=scores, total_value=total_val),
    )


class TestSingleSlotOptimizationStrategy(unittest.TestCase):
    def setUp(self):
        # Roster player 1: pid 101, low REB (0.0), high PTS (5.0)
        self.p1 = _create_scored_player(101, "Roster Guard", {"zPTS": 5.0, "zREB": 0.0, "zAST": 3.0})
        # Roster player 2: pid 102, moderate stats
        self.p2 = _create_scored_player(102, "Roster Forward", {"zPTS": 2.0, "zREB": 2.0, "zAST": 1.0})

        roster = Roster(name="My Team", player_ids=[101, 102])
        self.roster_snapshot = RosterSnapshot(
            roster=roster,
            scored_players={101: self.p1, 102: self.p2},
        )

        # Free Agents
        self.fa1 = _create_scored_player(201, "Rebounder FA", {"zPTS": 1.0, "zREB": 6.0, "zAST": 0.0})
        self.fa2 = _create_scored_player(202, "Balanced FA", {"zPTS": 3.0, "zREB": 3.0, "zAST": 2.0})

        self.candidate_pool = ScoredPool(
            scored_players={
                101: self.p1,
                102: self.p2,
                201: self.fa1,
                202: self.fa2,
            }
        )

    def test_requires_current_roster(self):
        strategy = SingleSlotOptimizationStrategy()
        with self.assertRaisesRegex(ValueError, "requires a non-empty current_roster"):
            strategy.optimize(self.candidate_pool, current_roster=None)

    def test_invalid_parameters(self):
        with self.assertRaisesRegex(ValueError, "Invalid mode"):
            SingleSlotOptimizationStrategy(mode="invalid_mode")
        with self.assertRaisesRegex(ValueError, "Invalid tiebreaker"):
            SingleSlotOptimizationStrategy(tiebreaker="invalid_tiebreaker")

    def test_sequential_swap_improves_category_win(self):
        target_thresholds = {"zPTS": 6.0, "zREB": 6.0, "zAST": 3.0}
        strategy = SingleSlotOptimizationStrategy(
            target_thresholds=target_thresholds,
            mode="sequential",
            tiebreaker="margin",
        )

        result = strategy.optimize(self.candidate_pool, current_roster=self.roster_snapshot)

        self.assertEqual(result.objective_value, 3.0)
        self.assertEqual(result.metadata["swaps_made"], 1)
        self.assertEqual(result.metadata["initial_categories_won"], 2)
        self.assertEqual(result.metadata["final_categories_won"], 3)

        selected_ids = {sp.player.player_id for sp in result.selected_players}
        self.assertEqual(selected_ids, {101, 201})

        swap_entry = result.metadata["swap_history"][0]
        self.assertEqual(swap_entry["drop_player_id"], 102)
        self.assertEqual(swap_entry["add_player_id"], 201)
        self.assertEqual(swap_entry["categories_won_diff"], 1)

    def test_punt_categories(self):
        target_thresholds = {"zPTS": 6.0, "zREB": 6.0, "zAST": 3.0}
        strategy = SingleSlotOptimizationStrategy(
            target_thresholds=target_thresholds,
            punt_categories=["zREB"],
            mode="sequential",
            tiebreaker="none",
        )

        result = strategy.optimize(self.candidate_pool, current_roster=self.roster_snapshot)

        self.assertEqual(result.objective_value, 2.0)
        self.assertEqual(result.metadata["swaps_made"], 0)


    def test_simultaneous_mode(self):
        target_thresholds = {"zPTS": 6.0, "zREB": 6.0, "zAST": 3.0}
        strategy = SingleSlotOptimizationStrategy(
            target_thresholds=target_thresholds,
            mode="simultaneous",
            tiebreaker="margin",
        )

        result = strategy.optimize(self.candidate_pool, current_roster=self.roster_snapshot)

        self.assertEqual(result.objective_value, 3.0)
        self.assertEqual(result.metadata["mode"], "simultaneous")
        self.assertGreaterEqual(result.metadata["swaps_made"], 1)

    def test_total_value_tiebreaker(self):
        target_thresholds = {"zPTS": 6.0, "zREB": 6.0, "zAST": 3.0}
        strategy = SingleSlotOptimizationStrategy(
            target_thresholds=target_thresholds,
            mode="sequential",
            tiebreaker="total_value",
        )

        result = strategy.optimize(self.candidate_pool, current_roster=self.roster_snapshot)

        self.assertEqual(result.metadata["tiebreaker"], "total_value")
        self.assertIn("categories_won", result.summary_metrics)
        self.assertIn("total_zscore", result.summary_metrics)


if __name__ == "__main__":
    unittest.main()

