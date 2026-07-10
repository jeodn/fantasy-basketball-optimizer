"""
app/services/evaluation_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Computes the "Value Added" of replacing a specific roster player with
each available free agent, and saves the top-N results.

Pipeline step: `python main.py evaluate [--player <ID>]`
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from app.config import DATA_DIR, config
from app.repository import file_repository as file_repo


def run(drop_candidate_id: Optional[int] = None, top_n: int = 50) -> None:
    """
    Evaluate free-agent replacements for a given drop candidate.

    :param drop_candidate_id: Player ID to evaluate for dropping.
                              Defaults to config.roster.drop_candidate.
    :param top_n: How many replacement candidates to include in the output.
    """
    print("=== Player Evaluation ===")

    # Resolve the player to drop — CLI arg takes priority over config
    player_to_drop = str(drop_candidate_id or config.roster.drop_candidate)
    print(f"  Drop candidate: {player_to_drop}")

    # --- Load data ---
    all_players = file_repo.load_z_scores()
    my_team_data = file_repo.load_my_team_z_scores()

    df_all = pd.DataFrame(all_players).T
    df_all = df_all.apply(pd.to_numeric, errors="coerce").combine_first(
        pd.DataFrame(all_players).T[["name"]]
    )

    if player_to_drop not in df_all.index:
        print(f"  [ERROR] Player {player_to_drop} not found in dataset.")
        return

    # --- Identify numeric stat columns ---
    numeric_cols = df_all.select_dtypes(include=["number"]).columns.tolist()
    if "name" in numeric_cols:
        numeric_cols.remove("name")

    drop_vec = df_all.loc[player_to_drop, numeric_cols]
    drop_name = df_all.loc[player_to_drop, "name"] if "name" in df_all.columns else player_to_drop
    print(f"  Evaluating replacements for: {drop_name}")

    # --- Compute value added vs. drop candidate ---
    value_added = df_all[numeric_cols].subtract(drop_vec, axis=1)
    value_added["name"] = df_all["name"]
    value_added["Total_Added_Value"] = value_added[numeric_cols].sum(axis=1)

    # Remove the drop candidate itself from results
    value_added = value_added.drop(index=player_to_drop, errors="ignore")

    top_n_df = value_added.sort_values("Total_Added_Value", ascending=False).head(top_n)

    # --- Build output dict ---
    output = {
        pid: {
            "name": row["name"],
            "ValueAdded": {col: float(row[col]) for col in numeric_cols},
            "Total_Added_Value": float(row["Total_Added_Value"]),
        }
        for pid, row in top_n_df.iterrows()
    }

    # --- Persist ---
    file_repo.save_json(DATA_DIR / "data_top_n_replacements.json", output)
    print(f"\nEvaluation complete — top {len(output)} replacements saved.")
