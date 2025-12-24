import pandas as pd
import numpy as np
import json
from pathlib import Path
from nba_api.stats.endpoints import scoreboardv2, commonallplayers
from .util import DATA_DIR, process_data, load_player_data
from .z_scores import calculate_z_scores, CATEGORY_WEIGHTS, PUNT_CATEGORIES
import sys

# Set stdout to UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# -------------------------------------------------------------------------
# CONSTANTS
# -------------------------------------------------------------------------
INJURY_FILE = DATA_DIR / 'injuries.json'
TEAM_CACHE_FILE = DATA_DIR / 'team_map_cache.json'
DAILY_OUTPUT_FILE = DATA_DIR / 'daily_projections.json'

# Mute SettingWithCopyWarning
pd.options.mode.chained_assignment = None 

def get_player_team_map():
    """
    Returns a dictionary mapping player_id (int) to team_id (int).
    Tries to load from cache first.
    """
    if TEAM_CACHE_FILE.exists():
        with open(TEAM_CACHE_FILE, 'r') as f:
            data = json.load(f)
            return {int(k): v for k, v in data.items()}
            
    print("Fetching player team map from NBA API...")
    # IsActive=1 gets only active players
    try:
        players = commonallplayers.CommonAllPlayers(is_only_current_season=1).get_data_frames()[0]
        team_map = pd.Series(players.TEAM_ID.values, index=players.PERSON_ID).to_dict()
        team_map = {k: int(v) for k, v in team_map.items() if v > 0} # Filter invalid

        with open(TEAM_CACHE_FILE, 'w') as f:
            json.dump(team_map, f)
            
        return team_map
    except Exception as e:
        print(f"Error fetching team map: {e}")
        return {}

def get_todays_teams():
    """
    Returns a set of Team IDs playing today.
    """
    try:
        board = scoreboardv2.ScoreboardV2()
        games = board.get_data_frames()[0]
        home_teams = set(games['HOME_TEAM_ID'].tolist())
        visitor_teams = set(games['VISITOR_TEAM_ID'].tolist())
        return home_teams.union(visitor_teams)
    except Exception as e:
        print(f"Error fetching schedule: {e}")
        return set()

def load_injuries():
    """
    Returns a set of Player IDs who are OUT.
    """
    if not INJURY_FILE.exists():
        return set()
        
    with open(INJURY_FILE, 'r') as f:
        injuries = json.load(f)
        
    out_ids = {int(p['id']) for p in injuries if p.get('status') == 'OUT'}
    return out_ids

def redistribute_minutes(team_df):
    """
    Adjusts stats for active players based on missing minutes from injured players.
    """
    # Identify OUT players
    out_mask = team_df['IS_OUT']
    active_mask = ~out_mask
    
    # Calculate minutes to redistribute
    # Using 'MIN' from data.json which is avg minutes per game
    missing_minutes = team_df.loc[out_mask, 'MIN'].sum()
    
    if missing_minutes <= 0:
        return team_df.loc[active_mask]
    
    active_df = team_df.loc[active_mask].copy()
    
    # Total minutes of active players to use as weights
    total_active_minutes = active_df['MIN'].sum()
    
    if total_active_minutes == 0:
         return active_df
    
    # Distribute minutes proportionally
    # Project_Min = Base_Min + (Base_Min / Total_Active_Min) * Missing_Minutes
    # Which simplifies to: Base_Min * (1 + Missing_Minutes / Total_Active_Min)
    scaling_factor = 1 + (missing_minutes / total_active_minutes)
    
    # Cap scaling to prevent absurdity (e.g. 2.0x stats). Limit to 1.5x or max 40 min?
    # Let's verify resulting minutes.
    # For now, just apply factor.
    
    # Columns to scale: Counting stats
    cols_to_scale = ['FGM', 'FGA', 'FTM', 'FTA', '3PTM', 'PTS', 'REB', 'AST', 'ST', 'BLK', 'TO']
    
    for col in cols_to_scale:
        active_df[col] = active_df[col] * scaling_factor
        
    # Recalculate percentages
    active_df['FG%'] = active_df.apply(lambda r: r['FGM'] / r['FGA'] if r['FGA'] > 0 else 0, axis=1)
    active_df['FT%'] = active_df.apply(lambda r: r['FTM'] / r['FTA'] if r['FTA'] > 0 else 0, axis=1)
    
    # Update MIN for reference (optional)
    active_df['MIN'] = active_df['MIN'] * scaling_factor
    
    return active_df

def calculate_daily_projections():
    print("--- Daily Player Value Prediction ---")
    
    # 1. Load Data
    json_data = load_player_data()
    df = process_data(json_data, 'stats_curr_season')
    
    # 2. Map Teams
    team_map = get_player_team_map()
    if not team_map:
        print("Could not map players to teams. Aborting.")
        return
    df['TEAM_ID'] = df['player_id'].map(team_map)
    df = df.dropna(subset=['TEAM_ID']) # Drop players with no team
    df['TEAM_ID'] = df['TEAM_ID'].astype(int)

    # 3. Filter Schedule
    playing_teams = get_todays_teams()
    if not playing_teams:
        print("No games scheduled today. Exiting.")
        # For dev, we might want to pretend everyone is playing
        # playing_teams = set(df['TEAM_ID'].unique()) 
        return

    df_today = df[df['TEAM_ID'].isin(playing_teams)].copy()
    print(f"Teams playing: {len(playing_teams)}. Players loaded: {len(df_today)}")

    # 4. Handle Injuries
    out_ids = load_injuries()
    df_today['IS_OUT'] = df_today['player_id'].isin(out_ids)
    
    # 5. Apply Projections per Team
    projected_dfs = []
    for team_id, team_df in df_today.groupby('TEAM_ID'):
        projected_team = redistribute_minutes(team_df)
        projected_dfs.append(projected_team)
        
    if not projected_dfs:
        print("No players remaining.")
        return
        
    final_df = pd.concat(projected_dfs)
    
    # 6. Calculate Z-Scores
    print("Calculating Z-Scores on projected stats...")
    final_df, z_cols = calculate_z_scores(final_df, punt_cats=PUNT_CATEGORIES, weights=CATEGORY_WEIGHTS)
    
    # 7. Sort and Display
    output_cols = ['name', 'Total_Value', 'MIN'] + z_cols
    final_df = final_df.sort_values(by='Total_Value', ascending=False)
    
    print("\nTop 20 Predicted Players for Tonight:")
    print(final_df[['name', 'Total_Value', 'MIN']].head(20).to_string(index=False))
    
    # 8. Export Full Projections
    # Re-index by player_id
    if final_df.index.name != 'player_id':
        final_df.set_index('player_id', inplace=True)
        
    final_df.to_json(DAILY_OUTPUT_FILE, orient='index', indent=4)
    print(f"\nProjections saved to {DAILY_OUTPUT_FILE}")

    # 9. Export My Team Projections
    from .generate_roster import my_team, matchup_team
    
    # my_team is a list of ints.
    # final_df index is player_id (int) because we just set it.
    
    my_team_df = final_df[final_df.index.isin(my_team)]
    
    MY_TEAM_OUTPUT_FILE = DATA_DIR / 'daily_projections_myteam.json'
    my_team_df.to_json(MY_TEAM_OUTPUT_FILE, orient='index', indent=4)
    print(f"My Team Projections ({len(my_team_df)} players) saved to {MY_TEAM_OUTPUT_FILE}")
    
    if not my_team_df.empty:
        print("\nMy Team Projections:")
        print(my_team_df[['name', 'Total_Value', 'MIN']].to_string(index=False))

    # 10. Export Matchup Team Projections
    matchup_df = final_df[final_df.index.isin(matchup_team)]
    
    MATCHUP_OUTPUT_FILE = DATA_DIR / 'daily_projections_matchup.json'
    matchup_df.to_json(MATCHUP_OUTPUT_FILE, orient='index', indent=4)
    print(f"Matchup Team Projections ({len(matchup_df)} players) saved to {MATCHUP_OUTPUT_FILE}")

    if not matchup_df.empty:
        print("\nMatchup Team Projections:")
        print(matchup_df[['name', 'Total_Value', 'MIN']].to_string(index=False))

if __name__ == "__main__":
    calculate_daily_projections()
