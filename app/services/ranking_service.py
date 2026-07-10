"""
app/services/ranking_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Calculates z-scores for 9-category fantasy basketball and produces
ranked player files.

Pipeline step: `python main.py rank`
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple

import pandas as pd

from app.config import DATA_DIR, config
from app.models import RAW_STAT_COLS, STAT_MAP
from app.repository import file_repository as file_repo


# ---------------------------------------------------------------------------
# Core z-score calculation (pure function — no I/O, injected config)
# ---------------------------------------------------------------------------

def calculate_z_scores(
    df: pd.DataFrame,
    punt_cats: Optional[List[str]] = None,
    weights: Optional[Dict[str, float]] = None,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Compute category z-scores for a player DataFrame.

    FG% and FT% are treated as *impact* scores
    (player_made − attempts × league_average) rather than raw percentages,
    so that volume is properly accounted for.

    :param df: DataFrame with one row per player, containing raw stat columns.
    :param punt_cats: Category names to zero out (e.g. ["TO", "FT%"]).
    :param weights: Per-category multipliers (e.g. {"AST": 1.2}).
    :returns: (mutated df with z-score columns added, list of z-score column names)
    """
    if punt_cats is None:
        punt_cats = []
    if weights is None:
        weights = {}

    # --- Percentage impact scores ---
    league_fg_pct = df["FGM"].sum() / df["FGA"].sum()
    league_ft_pct = df["FTM"].sum() / df["FTA"].sum()

    df["FG%_Impact"] = df["FGM"] - (df["FGA"] * league_fg_pct)
    df["FT%_Impact"] = df["FTM"] - (df["FTA"] * league_ft_pct)

    # --- Z-scores per category ---
    z_score_cols: List[str] = []

    for cat_name, col_name, higher_better in STAT_MAP:
        mean = df[col_name].mean()
        std = df[col_name].std() or 1.0  # avoid division by zero

        z_col = f"z{cat_name}"

        if higher_better:
            df[z_col] = (df[col_name] - mean) / std
        else:
            df[z_col] = (mean - df[col_name]) / std

        weight = weights.get(cat_name, 1.0)
        df[z_col] = 0.0 if cat_name in punt_cats else df[z_col] * weight

        z_score_cols.append(z_col)

    # Round before summing for cleaner display
    df = df.round(3)

    # Total value excludes raw FG%/FT% z-scores (impact columns already capture them)
    df["Total_Value"] = df[z_score_cols].sum(axis=1)

    return df, z_score_cols


# ---------------------------------------------------------------------------
# Data loading helper (converts raw player JSON to a flat DataFrame)
# ---------------------------------------------------------------------------

def _build_player_dataframe(raw_data: Dict, stats_source: str) -> pd.DataFrame:
    """
    Flatten the nested player JSON into a single per-player DataFrame row.

    :param raw_data: Dict loaded from data.json
    :param stats_source: Which stat window to use (e.g. "stats_curr_season")
    """
    rows = []
    for pid, info in raw_data.items():
        stats = info.get(stats_source, {})
        if not stats:
            continue

        row = {
            "player_id": info.get("player_id", pid),
            "name": info.get("name", "Unknown"),
            "FGM": stats.get("FGM", 0),
            "FGA": stats.get("FGA", 0),
            "FTM": stats.get("FTM", 0),
            "FTA": stats.get("FTA", 0),
            "3PTM": stats.get("3PTM", 0),
            "PTS": stats.get("PTS", 0),
            "REB": stats.get("REB", 0),
            "AST": stats.get("AST", 0),
            "ST": stats.get("ST", 0),
            "BLK": stats.get("BLK", 0),
            "TO": stats.get("TO", 0),
            "GP": stats.get("GP", 0),
            "MIN": stats.get("MIN", 0.0),
        }
        row["FG%"] = row["FGM"] / row["FGA"] if row["FGA"] > 0 else 0.0
        row["FT%"] = row["FTM"] / row["FTA"] if row["FTA"] > 0 else 0.0
        rows.append(row)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

def generate_z_scores_df(raw_data: Dict) -> pd.DataFrame:
    """
    Build a z-score ranked DataFrame from raw player data.

    :param raw_data: Dict loaded from data.json
    :returns: Sorted DataFrame with z-score columns and Total_Value.
    """
    stats_source = config.scoring.stats_source
    df = _build_player_dataframe(raw_data, stats_source)

    final_df, _ = calculate_z_scores(
        df,
        punt_cats=config.scoring.punt_categories,
        weights=config.scoring.category_weights,
    )

    pd.options.display.float_format = "{:,.2f}".format
    return final_df.sort_values(by="Total_Value", ascending=False)


def run() -> None:
    """
    Load data.json, calculate z-scores, and write:
      - data/data_zscores.json (keyed by player_id)
      - data/fantasy_rankings.csv
    """
    print("=== Ranking / Z-Score Calculation ===")

    raw_data = file_repo.load_raw_player_data()
    final_df = generate_z_scores_df(raw_data)

    # --- JSON export (drop raw stat columns) ---
    json_df = final_df.drop(columns=RAW_STAT_COLS, errors="ignore").copy()
    file_repo.save_dataframe_as_json(DATA_DIR / "data_zscores.json", json_df)

    # --- CSV export ---
    file_repo.save_csv(DATA_DIR / "fantasy_rankings.csv", json_df)

    print(f"\nRanking complete — {len(final_df)} players ranked.")
    print(f"Punt categories: {config.scoring.punt_categories or 'none'}")
