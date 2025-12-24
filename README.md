# Fantasy Basketball Advisor

This project (formerly Fantasy Basketball Optimizer) acts as an advisor to optimize your fantasy basketball team.
It calculates category-wise z-scores, predicts daily performance, and helps evaluate free agents.

**Current Status**:
- Login integration (Not Started)
- AI Suggestions (Implemented via Google Gemini)


## Features
- **Daily Projections & Comparison**: View side-by-side daily stat projections for "My Team" vs. "Matchup Team".
- **AI Fantasy Assistant**: Chat with a Gemini-powered AI that analyzes your daily matchup.
    - Provides advice based on **Overall Team Totals**.
    - Analyzes **Individual Player Stats** (Z-Scores & Raw Stats) to suggest optimal benching strategies for specific categories (e.g., preserving FG%).
- **Player Evaluation**: Compare free agents to your worst players.

## Configuration

To customize your rosters:
1.  Open `scripts/generate_roster.py`.
2.  Update the `my_team` list with your player IDs.
3.  Update the `matchup_team` list with your opponent's player IDs.

To manage injuries:
1.  Open `data/injuries.json`.
2.  Add players with `"status": "OUT"` to exclude them from daily projections.


## Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

The project is orchestrated by `main.py`. Run the script with one of the following commands:

```bash
python main.py [command]
```

### Available Commands

*   `pull`: **Fetch Data**. Pulls the latest player statistics from the NBA API.
    *   *Output*: `data/data.json`
*   `rank`: **Calculate Rankings**. Computes z-scores for all players based on league averages.
    *   *Output*: `data/data_zscores.json`, `data/fantasy_rankings.csv`
*   `roster`: **Generate Roster Stats**. Filters the ranked data for your specific team (defined in `scripts/generate_roster.py`).
    *   *Output*: `data/data_myteam.json`, `data/data_myteam_cumulative.json`
*   `evaluate`: **Evaluate Player Value**. Calculates the "Value Added" of top free agents compared to a specific drop candidate on your roster.
    *   *Output*: `data/data_top_n_replacements.json`
*   `predict`: **Daily Projections**. Predicts fantasy value for today's games, accounting for injuries (defined in `data/injuries.json`) and minute redistribution.
    *   *Output*: `data/daily_projections.json`, `data/daily_projections_myteam.json`, `data/daily_projections_matchup.json`
*   `all`: **Run All**. Executes the entire pipeline in order: `pull` -> `rank` -> `roster` -> `evaluate`.

## Visualization

To view your team stats and daily projections in a web interface:
```bash
streamlit run streamlit_app.py
```
*   **Daily Projections**: Ensure you have run `python main.py predict` first to generate the latest daily data.
*   **AI Assistant**: You will need a valid Google Gemini API Key to use the chatbox feature (input in the sidebar).


## Project Structure

*   `scripts/`: Contains the logic for fetching data, calculating scores, and managing rosters.
*   `data/`: Stores all input and output data files (JSON/CSV).
*   `main.py`: The entry point for the application.
