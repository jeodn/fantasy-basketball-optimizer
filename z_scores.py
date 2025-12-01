import pandas as pd
import numpy as np
import json

# -------------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------------
# Categories to exclude from the total score (e.g., ['TO', 'FG%'])
PUNT_CATEGORIES = ["BLK", "TO"] 

# Weights for each category (Default is 1.0). 
# You can increase this to 2.0 to make a category count double.
CATEGORY_WEIGHTS = {
    'FG%': 1.5, 'FT%': 1.0, '3PTM': 1.0, 'PTS': 0.8, 
    'REB': 1.0, 'AST': 1.2, 'ST': 1.0, 'BLK': 1.0, 'TO': 1.0
}

# The specific stats object to use from your JSON (e.g., 'stats_prev_season', 'stats_last_10')
STATS_SOURCE = 'stats_curr_season'

DATA_SOURCE_FILENAME = 'data.json'

# -------------------------------------------------------------------------
# LOAD DATA (From your prompt)
# -------------------------------------------------------------------------
def load_player_data(data_filename: str) -> str:
    json_data = ""
    try:
        # Load player data from an external JSON file
        with open(data_filename, 'r') as file:
            json_data = file.read()
    except FileNotFoundError:
        print(f"Error: {data_filename} not found. Please create {data_filename} with your player data.")
        # Fallback to an empty JSON structure if the file is missing to prevent immediate crash
        json_data = "{}" 

    return json_data


def process_data(json_input, stats_source='stats_curr_season') -> pd.DataFrame:
    """
    Parses JSON and creates a pandas DataFrame of the stats.
    """
    data = json.loads(json_input)
    
    rows = []
    for pid, info in data.items():
        if stats_source not in info:
            continue
            
        stats = info[stats_source]
        row = {
            'player_id': info.get('player_id', pid),
            'name': info.get('name', 'Unknown'),
            # Extract standard 9-cat stats
            'FGM': stats.get('FGM', 0),
            'FGA': stats.get('FGA', 0),
            'FTM': stats.get('FTM', 0),
            'FTA': stats.get('FTA', 0),
            '3PTM': stats.get('3PTM', 0),
            'PTS': stats.get('PTS', 0),
            'REB': stats.get('REB', 0),
            'AST': stats.get('AST', 0),
            'ST': stats.get('ST', 0),
            'BLK': stats.get('BLK', 0),
            'TO': stats.get('TO', 0),
            'GP': stats.get('GP', 0)
        }
        
        # Calculate raw percentages for display (handling div by zero)
        row['FG%'] = row['FGM'] / row['FGA'] if row['FGA'] > 0 else 0.0
        row['FT%'] = row['FTM'] / row['FTA'] if row['FTA'] > 0 else 0.0
        
        rows.append(row)
        
    return pd.DataFrame(rows)

# ------ 
# For external use: compile the last two functions
# -----
def get_players_dataframe() -> pd.DataFrame:
    return process_data(load_player_data(DATA_SOURCE_FILENAME))



def calculate_z_scores(df: pd.DataFrame, punt_cats=None, weights=None):
    """
    Calculates z-scores for 9-cat fantasy basketball.
    Uses 'Impact' score for percentages to account for volume.
    """
    if punt_cats is None: punt_cats = []
    if weights is None: weights = {}

    # 1. Calculate League Averages (Baseline)
    # Ideally, you might want to filter this to only 'rostered' players (e.g. top 150)
    # For now, we use the whole provided pool.
    pool_stats = df
    
    # Calculate League Weighted Percentages
    league_fg_pct = pool_stats['FGM'].sum() / pool_stats['FGA'].sum()
    league_ft_pct = pool_stats['FTM'].sum() / pool_stats['FTA'].sum()
    
    # 2. Prepare Impact Columns for Percentages
    # Impact = (Player% - League%) * Attempts 
    # This is mathematically equivalent to: Made - (Attempts * League%)
    # It represents "How many shots did I make above expectation?"
    df['FG%_Impact'] = df['FGM'] - (df['FGA'] * league_fg_pct)
    df['FT%_Impact'] = df['FTM'] - (df['FTA'] * league_ft_pct)

    # 3. Define Stat Map (Category Name -> DataFrame Column)
    # format: (Display Name, Column Name, HigherIsBetter?)
    stat_map = [
        ('FG%', 'FG%_Impact', True),
        ('FT%', 'FT%_Impact', True),
        ('3PTM', '3PTM', True),
        ('PTS', 'PTS', True),
        ('REB', 'REB', True),
        ('AST', 'AST', True),
        ('ST', 'ST', True),
        ('BLK', 'BLK', True),
        ('TO', 'TO', False) # False means lower is better
    ]

    # 4. Compute Z-Scores per Category
    z_score_cols = []
    
    for cat_name, col_name, higher_better in stat_map:
        # Calculate Mean and Std Dev for this category across the pool
        mean = pool_stats[col_name].mean()
        std = pool_stats[col_name].std()
        
        # Avoid division by zero
        if std == 0:
            std = 1 
            
        z_col = f"z{cat_name}"
        
        # Calculate Z-Score
        if higher_better:
            df[z_col] = (df[col_name] - mean) / std
        else:
            # For Turnovers: (Mean - Player) / Std  OR  (Player - Mean) / Std * -1
            df[z_col] = (mean - df[col_name]) / std
            
        # Apply Weights and Punts
        weight = weights.get(cat_name, 1.0)
        
        if cat_name in punt_cats:
            df[z_col] = 0.0 # Zero out the value for punted categories
        else:
            df[z_col] = df[z_col] * weight
            
        z_score_cols.append(z_col)

    

    # DON'T COUNT RAW FG%
    z_score_cols_no_rawFG = z_score_cols
    z_score_cols_no_rawFG.remove("zFG%")
    z_score_cols_no_rawFG.remove("zFT%")

    # round to 3 decimals
    df = df.round(3)

    # 5. Sum Z-Scores for Total Value
    df['Total_Value'] = df[z_score_cols].sum(axis=1)
    
    return df, z_score_cols

# -------------------------------------------------------------------------
# EXECUTION
# -------------------------------------------------------------------------
def generate_z_scores_df(json_data: str) -> pd.DataFrame:
    """
    Generates a dataframe of each player's z scores.
    
    :param json_data: data
    :type json_data: str

    :param export_type: PRINT, CSV, or JSON
    :type export_type: str
    """
    # 1. Load Data
    df = process_data(json_data, STATS_SOURCE)

    # 2. Calculate
    # Note: You can pass punt_cats=['TO', 'FT%'] to test punting
    final_df, z_cols = calculate_z_scores(df, punt_cats=PUNT_CATEGORIES, weights=CATEGORY_WEIGHTS)

    # 3. Format Output
    output_cols = ['name', 'Total_Value'] + z_cols
    final_df = final_df.sort_values(by='Total_Value', ascending=False)

    # Rounding for cleaner display
    pd.options.display.float_format = '{:,.2f}'.format

    return final_df


    

def export_z_scores_as_file(final_df: pd.DataFrame, export_types: list[str]) -> None:
    
    # Exporting
    json_df = final_df.copy()

    raw_stats = ["FGM", "FGA", "FTM", "FTA", 
                        "3PTM", "PTS", "REB", "AST", 
                        "ST", "BLK", "TO", "GP", 
                        "FG%", "FT%"]
    json_df = json_df.drop(columns=raw_stats)

    if "PRINT" in export_types:
        print("--- FANTASY BASKETBALL Z-SCORES ---")
        print(f"Punted Categories: {PUNT_CATEGORIES}")
        print(json_df)
        #print(final_df[output_cols].to_string(index=False))

    if "CSV" in export_types:
        json_df.to_csv("fantasy_rankings.csv", index=False)

    # Save to json
    # To export the JSON keyed by player_id, we need to set player_id as the index
    if "JSON" in export_types:
        if not final_df.empty:
            
            # 1. Set the 'player_id' as the index
            # This column will become the top-level keys in the final JSON object.
            json_df.set_index('player_id', inplace=True)
            
            # 2. Use orient='index' to key the output by the index (player_id)
            # The output format will be: {"player_id": {col1: val1, col2: val2, ...}, ...}
            json_df.to_json('data_zscores.json', orient='index', indent=4)
            print("\nData exported to 'data_zscores.json' (keyed by player_id).")


if __name__ == "__main__":
    json_data = load_player_data(DATA_SOURCE_FILENAME)
    zscore_df = generate_z_scores_df(json_data)
    export_z_scores_as_file(zscore_df, ["JSON", "CSV"])