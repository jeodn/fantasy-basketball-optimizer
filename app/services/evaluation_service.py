"""
app/services/evaluation_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Computes the "Value Added" of replacing a specific roster player with
each available free agent, and saves the top-N results.

Pipeline step: `python main.py evaluate [--player <ID>]`

Architecture
------------
run()                         ← public orchestrator (unchanged behaviour)
 │
 ├── load_player_pool()       ← parse z-score JSON into typed DataFrame
 ├── load_roster_df()         ← parse my-team JSON into typed DataFrame
 │
 ├── evaluate_candidates()    ← core engine (accepts any scorer callable)
 │    └── scorer(...)         ← injectable; default: naive_value_added_scorer
 │
 └── results_to_dict()        ← serialise ranked DataFrame → output JSON shape
"""

from __future__ import annotations

from typing import Callable, Optional

import pandas as pd

from app.config import DATA_DIR, config
from app.repository import file_repository as file_repo


# ---------------------------------------------------------------------------
# Scorer callable interface (contract for all scorers)
# ---------------------------------------------------------------------------
#
# Any scorer passed to evaluate_candidates() must match this signature:
#
#   def my_scorer(
#       candidates_df:    pd.DataFrame,  # full player pool, indexed by player_id str
#       drop_candidate_id: str,          # player being dropped
#       roster_df:         pd.DataFrame, # current roster z-scores (may be unused)
#       numeric_cols:      list[str],    # stat columns to score on
#   ) -> pd.DataFrame:
#       """
#       Returns a DataFrame with:
#         - 'name' column preserved (str)
#         - 'Total_Added_Value' column (float) — the sortable score
#         - drop candidate row excluded
#       Per-category breakdown columns are optional but recommended.
#       """
#
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_player_pool() -> pd.DataFrame:
    """
    Load all z-scored players from file into a typed DataFrame.

    Index = player_id string.
    'name' is preserved as str; all stat columns are float.

    :raises FileNotFoundError: if data_zscores.json has not been generated.
    """
    raw = file_repo.load_z_scores()
    raw_df = pd.DataFrame(raw).T
    # Coerce numeric columns to float, restore the string 'name' column
    df = raw_df.apply(pd.to_numeric, errors="coerce").combine_first(raw_df[["name"]])
    return df


def load_roster_df(my_team_data: dict) -> pd.DataFrame:
    """
    Build a typed DataFrame for the current roster from the my-team z-score dict.

    Same schema as load_player_pool(). Passed to scorers so they can inspect
    the roster's existing category profile for diversification-aware scoring.

    :param my_team_data: Dict loaded from data_myteam.json.
    """
    if not my_team_data:
        return pd.DataFrame()
    raw_df = pd.DataFrame(my_team_data).T
    return raw_df.apply(pd.to_numeric, errors="coerce").combine_first(raw_df[["name"]])


# ---------------------------------------------------------------------------
# Scorers
# ---------------------------------------------------------------------------

def naive_value_added_scorer(
    candidates_df: pd.DataFrame,
    drop_candidate_id: str,
    roster_df: pd.DataFrame,
    numeric_cols: list[str],
) -> pd.DataFrame:
    """
    Default scorer.

    For each candidate, computes the per-category difference
    ``candidate_stat − drop_candidate_stat`` and sums across all categories
    to produce ``Total_Added_Value``.

    The drop candidate's own row is excluded from the result.

    :param candidates_df:     Full player pool DataFrame.
    :param drop_candidate_id: Player ID (str) being evaluated for dropping.
    :param roster_df:         Current roster DataFrame (unused by this scorer;
                              present to satisfy the shared scorer interface).
    :param numeric_cols:      Stat columns to compute differences over.
    :returns:                 DataFrame with per-category diffs and
                              'Total_Added_Value', drop candidate excluded.
    """
    drop_vec = candidates_df.loc[drop_candidate_id, numeric_cols]

    scored = candidates_df[numeric_cols].subtract(drop_vec, axis=1)
    scored["name"] = candidates_df["name"]
    scored["Total_Added_Value"] = scored[numeric_cols].sum(axis=1)

    return scored.drop(index=drop_candidate_id, errors="ignore")


# ---------------------------------------------------------------------------
# Core evaluation engine
# ---------------------------------------------------------------------------

def evaluate_candidates(
    df_all: pd.DataFrame,
    drop_candidate_id: str,
    roster_df: pd.DataFrame,
    scorer: Callable = naive_value_added_scorer,
    top_n: int = 50,
) -> pd.DataFrame:
    """
    Core evaluation engine.

    Validates the drop candidate, resolves numeric columns, delegates scoring
    to *scorer*, sorts by ``Total_Added_Value``, and returns the top-N rows.

    :param df_all:            Full player pool DataFrame (from load_player_pool).
    :param drop_candidate_id: String player ID to evaluate dropping.
    :param roster_df:         Current roster DataFrame (forwarded to scorer).
    :param scorer:            Callable matching the scorer interface above.
                              Defaults to naive_value_added_scorer.
    :param top_n:             Number of top candidates to return.
    :returns:                 Ranked DataFrame (top_n rows) with 'name' and
                              'Total_Added_Value'.
    :raises ValueError:       If drop_candidate_id is not present in df_all.
    """
    if drop_candidate_id not in df_all.index:
        raise ValueError(
            f"Drop candidate '{drop_candidate_id}' not found in player pool. "
            "Ensure data_zscores.json is up to date (run `python main.py rank`)."
        )

    numeric_cols = df_all.select_dtypes(include=["number"]).columns.tolist()

    scored_df = scorer(df_all, drop_candidate_id, roster_df, numeric_cols)

    return scored_df.sort_values("Total_Added_Value", ascending=False).head(top_n)


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def results_to_dict(ranked_df: pd.DataFrame, numeric_cols: list[str]) -> dict:
    """
    Serialise a ranked candidates DataFrame into the output JSON structure.

    Output shape::

        {
            "<player_id>": {
                "name": "...",
                "ValueAdded": {"zPTS": 0.4, "zREB": -0.1, ...},
                "Total_Added_Value": 1.23
            },
            ...
        }

    :param ranked_df:    DataFrame returned by evaluate_candidates().
    :param numeric_cols: Stat columns to include in the ValueAdded breakdown.
                         Columns absent from ranked_df are silently skipped.
    """
    output = {}
    present_cols = [c for c in numeric_cols if c in ranked_df.columns]

    for pid, row in ranked_df.iterrows():
        output[pid] = {
            "name": row["name"],
            "ValueAdded": {col: float(row[col]) for col in present_cols},
            "Total_Added_Value": float(row["Total_Added_Value"]),
        }

    return output


# ---------------------------------------------------------------------------
# Public orchestrator — behaviour identical to before the refactor
# ---------------------------------------------------------------------------

def run(drop_candidate_id: Optional[int] = None, top_n: int = 50) -> None:
    """
    Evaluate free-agent replacements for a given drop candidate and save
    the top-N results to data/data_top_n_replacements.json.

    :param drop_candidate_id: Player ID to evaluate for dropping.
                              Defaults to config.roster.drop_candidate.
    :param top_n: How many replacement candidates to include in the output.
    """
    print("=== Player Evaluation ===")

    player_to_drop = str(drop_candidate_id or config.roster.drop_candidate)
    print(f"  Drop candidate: {player_to_drop}")

    # Load data
    df_all = load_player_pool()
    roster_df = load_roster_df(file_repo.load_my_team_z_scores())

    # Run engine with default scorer
    try:
        ranked_df = evaluate_candidates(
            df_all,
            player_to_drop,
            roster_df,
            scorer=naive_value_added_scorer,
            top_n=top_n,
        )
    except ValueError as e:
        print(f"  [ERROR] {e}")
        return

    drop_name = df_all.loc[player_to_drop, "name"] if "name" in df_all.columns else player_to_drop
    print(f"  Evaluating replacements for: {drop_name}")

    numeric_cols = df_all.select_dtypes(include=["number"]).columns.tolist()
    output = results_to_dict(ranked_df, numeric_cols)

    file_repo.save_json(DATA_DIR / "data_top_n_replacements.json", output)
    print(f"\nEvaluation complete — top {len(output)} replacements saved.")
