import json
import pandas as pd
from .util import DATA_DIR

def evaluate():
    # -----------------------------
    # Load Data
    # -----------------------------
    with open(DATA_DIR / "data_myteam.json", "r") as f:
        myteam = json.load(f)

    with open(DATA_DIR / "data_zscores.json", "r") as f:
        all_players = json.load(f)

    df_all = pd.DataFrame(all_players).T

    # Convert numeric-looking strings to floats
    df_all = df_all.apply(pd.to_numeric, errors="ignore")

    # -----------------------------
    # Identify numeric stat columns
    # -----------------------------
    numeric_cols = df_all.select_dtypes(include=["number"]).columns.tolist()

    if "name" in numeric_cols:
        numeric_cols.remove("name")

    print("Numeric columns used:", numeric_cols)   # debug

    # -----------------------------
    # Player to drop
    # -----------------------------
    player_to_drop = "1629675"

    if player_to_drop not in df_all.index:
        print(f"Player {player_to_drop} not found in dataset.")
        return

    drop_vec = df_all.loc[player_to_drop, numeric_cols]

    # -----------------------------
    # Compute ValueAdded
    # -----------------------------
    value_added = df_all[numeric_cols].subtract(drop_vec, axis=1)

    value_added["name"] = df_all["name"]
    value_added["Total_Added_Value"] = value_added[numeric_cols].sum(axis=1)

    value_added = value_added.drop(player_to_drop)

    # -----------------------------
    # Top n replacements
    # -----------------------------
    n= 50
    top_n = value_added.sort_values("Total_Added_Value", ascending=False).head(n)



    output = {}

    for pid, row in top_n.iterrows():
        # Extract per-category added values as a dict
        cat_values = {col: float(row[col]) for col in numeric_cols}

        output[pid] = {
            "name": row["name"],
            "ValueAdded": cat_values,
            "Total_Added_Value": float(row["Total_Added_Value"])
        }

    # Write to JSON file
    with open(DATA_DIR / "data_top_n_replacements.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    print("Saved results to top_n_replacements.json")

if __name__ == "__main__":
    evaluate()
