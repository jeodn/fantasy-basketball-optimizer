"""
app/analytics/scoring/z_score.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
ZScoreStrategy — standard 9-category fantasy basketball z-score ranking.

FG% and FT% are treated as *impact* scores (volume-weighted) rather than
raw percentages, so high-volume passable shooters don't drag the pool.

Usage::

    strategy = ZScoreStrategy(
        weights={"AST": 1.2, "FG%": 1.5},
        punt_categories=["TO"],
        stats_source="stats_curr_season",
    )
    scored_pool = strategy.score(player_pool)
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from app.analytics.scoring.base import ScoringStrategy
from app.domain.player import PlayerPool
from app.domain.scoring import CategoryScores, ScoredPlayer, ScoredPool
from app.domain.stats import STAT_MAP


class ZScoreStrategy(ScoringStrategy):
    """
    Scores players using per-category z-scores relative to the pool average.

    Configuration is injected at construction time; ``score()`` is stateless.

    :param weights:          Per-category multipliers. Absent keys default to 1.0.
    :param punt_categories:  Categories to zero out (e.g. ``["TO", "FT%"]``).
    :param stats_source:     Which PlayerStats window to score against.
    """

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        punt_categories: Optional[List[str]] = None,
        stats_source: str = "stats_curr_season",
    ) -> None:
        self.weights: Dict[str, float] = weights or {}
        self.punt_categories: List[str] = punt_categories or []
        self.stats_source = stats_source

    # ------------------------------------------------------------------
    # ScoringStrategy interface
    # ------------------------------------------------------------------

    def score(self, pool: PlayerPool) -> ScoredPool:
        """
        Score every player in *pool* and return a ScoredPool.

        :param pool: PlayerPool to score. Not mutated.
        :returns:    ScoredPool keyed by player_id (int).
        """
        df = pool.to_dataframe(self.stats_source)
        if df.empty:
            return ScoredPool()

        df = df.copy()   # never mutate the pool's dataframe

        # --- FG% / FT% impact scores (volume-weighted) ---
        league_fg_pct = df["FGM"].sum() / df["FGA"].sum()
        league_ft_pct = df["FTM"].sum() / df["FTA"].sum()
        df["FG%_Impact"] = df["FGM"] - (df["FGA"] * league_fg_pct)
        df["FT%_Impact"] = df["FTM"] - (df["FTA"] * league_ft_pct)

        # --- Z-scores per category ---
        z_score_cols: List[str] = []

        for cat_name, col_name, higher_better in STAT_MAP:
            mean = df[col_name].mean()
            std = df[col_name].std() or 1.0     # avoid division by zero

            z_col = f"z{cat_name}"

            if higher_better:
                df[z_col] = (df[col_name] - mean) / std
            else:
                df[z_col] = (mean - df[col_name]) / std

            weight = self.weights.get(cat_name, 1.0)
            df[z_col] = 0.0 if cat_name in self.punt_categories else df[z_col] * weight

            z_score_cols.append(z_col)

        df = df.round(3)
        df["Total_Value"] = df[z_score_cols].sum(axis=1)

        # --- Build ScoredPool from the scored DataFrame ---
        scored_players: Dict[int, ScoredPlayer] = {}

        for _, row in df.iterrows():
            pid = int(row["player_id"])
            player = pool.get(pid)
            if player is None:
                continue

            scores: Dict[str, float] = {col: float(row[col]) for col in z_score_cols}
            scores["FG%_Impact"] = float(row["FG%_Impact"])
            scores["FT%_Impact"] = float(row["FT%_Impact"])

            scored_players[pid] = ScoredPlayer(
                player=player,
                category_scores=CategoryScores(
                    scores=scores,
                    total_value=float(row["Total_Value"]),
                ),
            )

        return ScoredPool(scored_players=scored_players)
