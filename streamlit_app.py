import streamlit as st
import pandas as pd
from scripts import z_scores, util, generate_roster

# Set page configuration
st.set_page_config(
    page_title="Fantasy Basketball Optimizer",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load data function
@st.cache_data
def load_data():
    json_data = util.load_player_data(util.DATA_SOURCE_FILENAME)
    df = z_scores.generate_z_scores_df(json_data)
    return df

def main():
    st.title("Fantasy Basketball Optimizer")

    # Load Data
    try:
        df = load_data()
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return

    # Sidebar
    st.sidebar.header("Settings")
    
    # Section 1: My Team
    st.header("My Team")
    
    # Filter for my team
    my_team_ids = set(generate_roster.my_team)
    my_team_df = df[df['player_id'].astype(int).isin(my_team_ids)]
    
    # Calculate Team Totals (similar to cumulative stats)
    if not my_team_df.empty:
        # Display Team Stats
        st.subheader("Team Roster")
        st.dataframe(my_team_df, use_container_width=True)
        
        # Calculate totals for z-scores
        z_cols = [col for col in my_team_df.columns if col.startswith('z')]
        team_totals = my_team_df[z_cols].sum()
        
        st.subheader("Team Totals (Z-Scores)")
        # Transpose for better display
        st.dataframe(team_totals.to_frame(name="Total Value").T, use_container_width=True)
    else:
        st.warning("No players found for 'My Team'. Check generate_roster.py.")

    # Section 2: League Data
    st.header("League Data")
    st.markdown("### All Players")
    
    # Optional: Search/Filter
    search_term = st.text_input("Search Player", "")
    if search_term:
        league_display_df = df[df['name'].str.contains(search_term, case=False)]
    else:
        league_display_df = df

    st.dataframe(league_display_df, use_container_width=True)

    # Section 3: Comparison
    st.header("Player Comparison")
    
    col1, col2 = st.columns(2)
    
    with col1:
        player1_name = st.selectbox("Select Player 1 (My Team)", my_team_df['name'].tolist(), key="p1")
        if player1_name:
            player1_data = df[df['name'] == player1_name].iloc[0]
            st.write(f"**{player1_name}**")
            st.write(f"Total Value: {player1_data['Total_Value']:.2f}")

    with col2:
        # Filter out player 1 from the list if desired, but keeping all is fine
        player2_name = st.selectbox("Select Player 2 (League)", df['name'].unique().tolist(), key="p2")
        if player2_name:
            player2_data = df[df['name'] == player2_name].iloc[0]
            st.write(f"**{player2_name}**")
            st.write(f"Total Value: {player2_data['Total_Value']:.2f}")

    if player1_name and player2_name:
        st.subheader("Comparison Table")
        
        # Extract relevant columns for comparison (Raw stats + Z categories)
        # Assuming util.process_data gives us raw stats, but z_scores.generate_z_scores_df might have them too 
        # or we might want to look at the z-score columns specifically.
        # Let's show the columns present in the dataframe.
        
        comp_df = df[df['name'].isin([player1_name, player2_name])].set_index('name').T
        st.dataframe(comp_df, use_container_width=True)

if __name__ == "__main__":
    main()
