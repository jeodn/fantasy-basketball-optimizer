import pandas as pd
import time
from nba_api.stats.endpoints import leaguedashplayerstats, commonplayerinfo
from nba_api.stats.static import players

import json
from .util import DATA_DIR

# --- CONFIGURATION ---
CURRENT_SEASON = '2025-26'
PREV_SEASON = '2024-25'

# Columns we want to extract and rename to your format
# NBA API Format -> Your Format
STATS_MAPPING = {
    'MIN': 'MIN',
    'FGM': 'FGM',
    'FGA': 'FGA',
    'FG_PCT': 'FG%',
    'FG3M': '3PTM', # Note: NBA API uses FG3M
    'FTM': 'FTM',
    'FTA': 'FTA',
    'FT_PCT': 'FT%',
    'PTS': 'PTS',
    'REB': 'REB',
    'AST': 'AST',
    'STL': 'ST',    # Note: NBA API uses STL
    'BLK': 'BLK',
    'TOV': 'TO',    # Note: NBA API uses TOV
    'GP': 'GP'      # Games Played (useful for weighting)
}

def fetch_league_stats(season, last_n_games=0):
    """
    Fetches stats for ALL players in one go.
    last_n_games: 0 for full season, 10 for last 10 games.
    """
    print(f"Fetching data for Season: {season}, Last N Games: {last_n_games}...")
    
    # logic for 'LastNGames' parameter
    last_n_str = f"{last_n_games}" if last_n_games > 0 else "0"
    
    try:
        # We use PerGame mode to get averages immediately
        dash = leaguedashplayerstats.LeagueDashPlayerStats(
            season=season,
            last_n_games=last_n_str,
            per_mode_detailed='PerGame',
            measure_type_detailed_defense='Base'
        )
        df = dash.get_data_frames()[0]
        return df
    except Exception as e:
        print(f"Error fetching stats: {e}")
        return pd.DataFrame()

def process_row(row):
    """Extracts only the columns we want from a dataframe row."""
    if row is None:
        return {}
    
    stats = {}
    for api_key, my_key in STATS_MAPPING.items():
        if api_key in row:
            stats[my_key] = row[api_key]
    return stats

def main():
    # 1. Fetch Data Batches
    # Current Season Stats
    df_curr = fetch_league_stats(CURRENT_SEASON)
    time.sleep(1) # Be nice to the API
    
    # Previous Season Stats
    df_prev = fetch_league_stats(PREV_SEASON)
    time.sleep(1)
    
    # Last 10 Games (Averages over the last 10)
    df_last10 = fetch_league_stats(CURRENT_SEASON, last_n_games=10)

    # 2. Get Active Players list to build the skeleton
    # This helps ensures we only look at currently active guys
    active_players = players.get_active_players()
    
    # INITIALIZE FINAL DATA
    final_data = {}

    print(f"\nProcessing {len(active_players)} players...")

    # 3. Merge Data
    # We convert DataFrames to dictionaries keyed by PLAYER_ID for fast lookup
    # Orient='index' turns the Player ID into the key
    curr_dict = df_curr.set_index('PLAYER_ID').to_dict(orient='index') if not df_curr.empty else {}
    prev_dict = df_prev.set_index('PLAYER_ID').to_dict(orient='index') if not df_prev.empty else {}
    l10_dict = df_last10.set_index('PLAYER_ID').to_dict(orient='index') if not df_last10.empty else {}

    for p in active_players:
        p_id = p['id']
        p_name = p['full_name']
        
        # Base Object
        player_obj = {
            "player_id": p_id,
            "name": p_name,
            "positions": [], # Filled below
            "stats_prev_season": {},
            "stats_curr_season": {},
            "stats_last_10": {},
            "combined_stats": {} # Placeholder
        }

        # --- Fill Stats ---
        # Current Season
        if p_id in curr_dict:
            raw_stats = curr_dict[p_id]
            player_obj['stats_curr_season'] = process_row(raw_stats)
            # Try to grab detailed position info if available, otherwise API defaults strictly to G/F/C
            # For exact fantasy positions (PG, SF), you often need an external mapping or deeper scraping,
            # but we can try to find the generic one here.
            # NBA API usually returns strict positions here.
        
        # Previous Season
        if p_id in prev_dict:
            player_obj['stats_prev_season'] = process_row(prev_dict[p_id])

        # Last 10
        if p_id in l10_dict:
            player_obj['stats_last_10'] = process_row(l10_dict[p_id])

        # --- Handle Positions ---
        pass

        final_data[player_obj.get("player_id")] = (player_obj)

    # 4. Output (Example of first 2 players)

    print("\n--- Data Ingestion Complete ---")
    print("Example Output (First 1 Player):")
    print(json.dumps(list(final_data.items())[0], indent=4))  # random element
    
    return final_data

if __name__ == "__main__":
    data = main()

    with open(DATA_DIR / 'data.json', 'w') as f:
        json.dump(data, f)
