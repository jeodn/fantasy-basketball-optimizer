# Fantasy Basketball Advisor

This project acts as an advisor for optimizing your fantasy basketball team by calculating category-wise scores, predicting daily performance, and evaluating replacements.

## Features
- **Daily Projections & Comparison**: View side-by-side daily stat projections for "My Team" vs. "Matchup Team".
- **AI Fantasy Assistant**: Chat with a Gemini-powered AI that analyzes your daily matchup.
- **Player Evaluation**: Compare replacement candidates (e.g. free agents) to a specific roster drop candidate.

## Gallery
<img width="1633" height="779" alt="image" src="https://github.com/user-attachments/assets/f93d1417-fcb1-4bc6-b1fd-d375b6a47235" />

<img width="1464" height="903" alt="image" src="https://github.com/user-attachments/assets/041baa6e-e435-4ffb-998d-93c5ded2c1cc" />

<img width="1413" height="1269" alt="image" src="https://github.com/user-attachments/assets/9539eeb5-880c-4eff-a8ed-c65b921c7979" />

<img width="1437" height="785" alt="image" src="https://github.com/user-attachments/assets/b41661bb-a98e-4b56-a276-1d7606721eab" />

<img width="1338" height="893" alt="image" src="https://github.com/user-attachments/assets/cde53cd6-a079-48b9-b946-e6a333acce9c" />

## Architecture

The project code is separated into modular domains inside the `app/` directory:
- **`app/domain/`**: Strongly-typed model definitions (`Player`, `PlayerPool`, `PlayerStats`, `ScoredPool`, `RosterSnapshot`) and schema constants. No I/O or math.
- **`app/ingestion/`**: Handles data fetching, transformation, and projection (e.g., minute redistribution for active players to account for injuries).
- **`app/analytics/`**: Core mathematical calculations. Supports pluggable `ScoringStrategy` systems (e.g., standard `ZScoreStrategy` or future diversification-adjusted scoring) and replacement evaluations.
- **`app/repository/`**: Layer-agnostic I/O primitives (`file_repository.py` and `nba_api_repository.py`).
- **`app/pipeline/`**: CLI orchestrators linking ingestion, analytics, and I/O together.

## Configuration

Customize rosters, scoring parameters, and settings in `config.yaml`:
- **`roster`**: Configures `my_team` (list of player IDs), `matchup_team` (list of player IDs), and default `drop_candidate` (player ID).
- **`scoring`**: Configures `stats_source`, `punt_categories`, and `category_weights`.
- **`season`**: Set `current` and `previous` NBA season identifiers (e.g. `2025-26`).

Manage injuries manually:
- Set `"status": "OUT"` on players in `data/injuries.json` to exclude them from daily projections.

## Setup & Running

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run Pipeline Command**:
   ```bash
   python main.py [command] [--player PLAYER_ID]
   ```
   - `pull`: Fetches raw NBA API stats -> `data/data.json`.
   - `rank`: Calculates category z-scores for all players -> `data/data_zscores.json`, `data/fantasy_rankings.csv`.
   - `roster`: Slices statistics for your teams -> `data/data_myteam.json`, `data/data_matchup.json`, etc.
   - `evaluate`: Ranks replacement options against a drop candidate -> `data/data_top_n_replacements.json`. Override the target using `--player <ID>`.
   - `predict`: Builds injury-adjusted projections -> `data/daily_projections*.json`.
   - `all`: Runs `pull` -> `rank` -> `roster` -> `evaluate` in sequence.

3. **Launch Streamlit Dashboard**:
   ```bash
   streamlit run streamlit_app.py
   ```
