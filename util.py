import pandas as pd
import numpy as np
import json



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
def get_players_dataframe(data_source_filename=DATA_SOURCE_FILENAME) -> pd.DataFrame:
    return process_data(load_player_data(data_source_filename))


def export_player_df_as_json(output_filename: str, export_df: pd.DataFrame) -> None:
    if not export_df.empty:
        json_df = export_df.copy()
        
        # 1. Set the 'player_id' as the index
        # This column will become the top-level keys in the final JSON object.
        json_df.set_index('player_id', inplace=True)
        
        # 2. Use orient='index' to key the output by the index (player_id)
        # The output format will be: {"player_id": {col1: val1, col2: val2, ...}, ...}
        json_df.to_json(output_filename, orient='index', indent=4)
        print(f"\nData exported to {output_filename} (keyed by player_id).")