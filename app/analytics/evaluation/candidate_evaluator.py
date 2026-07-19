"""
app/analytics/evaluation/candidate_evaluator.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Scorer-agnostic evaluation engine.

Given a ScoredPool (produced by *any* ScoringStrategy), a drop candidate,
and a RosterSnapshot for context, computes a ranked list of replacement
options and returns a typed EvaluationResult.

The evaluation math is intentionally simple: per-category value-added =
(candidate score − drop candidate score). The sophistication lives in the
ScoringStrategy that produced the scores — not here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from app.domain.scoring import RosterSnapshot, ScoredPlayer, ScoredPool


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class ReplacementOption:
    """A single candidate ranked against the drop candidate."""

    candidate: ScoredPlayer
    value_added: Dict[str, float]   # per-category diff (candidate − drop)
    total_added_value: float        # sum of value_added


@dataclass
class EvaluationResult:
    """
    Full evaluation output for a drop candidate.

    ``replacements`` is sorted descending by ``total_added_value``.
    """

    drop_candidate: ScoredPlayer
    replacements: List[ReplacementOption] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core engine
# ---------------------------------------------------------------------------

def evaluate_replacements(
    scored_pool: ScoredPool,
    drop_candidate_id: int,
    roster_snapshot: RosterSnapshot,
    top_n: int = 50,
) -> EvaluationResult:
    """
    Rank every player in *scored_pool* as a replacement for *drop_candidate_id*.

    Scorer-agnostic: works with any ScoredPool regardless of how it was
    produced (z-score, diversification-adjusted, etc.).

    :param scored_pool:       The full player pool with scores applied.
    :param drop_candidate_id: Integer player ID to evaluate for dropping.
    :param roster_snapshot:   Current roster context (available to future
                              scorers that need roster-level information;
                              not used by the base evaluator itself).
    :param top_n:             Maximum number of replacement options to return.
    :returns:                 EvaluationResult sorted descending by total_added_value.
    :raises ValueError:       If drop_candidate_id is not in scored_pool.
    """
    drop = scored_pool.get(drop_candidate_id)
    if drop is None:
        raise ValueError(
            f"Drop candidate {drop_candidate_id} not found in ScoredPool. "
            "Ensure data_zscores.json is up to date (run `python main.py rank`)."
        )

    drop_scores = drop.category_scores.scores

    options: List[ReplacementOption] = []

    for pid, sp in scored_pool.scored_players.items():
        if pid == drop_candidate_id:
            continue

        value_added = {
            cat: sp.category_scores.scores.get(cat, 0.0) - drop_scores.get(cat, 0.0)
            for cat in drop_scores
        }
        total_added = sum(value_added.values())

        options.append(
            ReplacementOption(
                candidate=sp,
                value_added=value_added,
                total_added_value=total_added,
            )
        )

    options.sort(key=lambda o: o.total_added_value, reverse=True)

    return EvaluationResult(
        drop_candidate=drop,
        replacements=options[:top_n],
    )
