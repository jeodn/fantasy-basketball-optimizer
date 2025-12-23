# Fantasy Basketball Optimizer

This project optimizes a fantasy basketball team based on a set of player IDs by calculating category-wise z-scores compared to the league average.

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
*   `all`: **Run All**. Executes the entire pipeline in order: `pull` -> `rank` -> `roster` -> `evaluate`.

## Project Structure

*   `scripts/`: Contains the logic for fetching data, calculating scores, and managing rosters.
*   `data/`: Stores all input and output data files (JSON/CSV).
*   `main.py`: The entry point for the application.
