# Data Pipeline & Workflow

Orchestrates data fetching, transformation, injury-adjusted projections, scoring execution, and output file persistence.

## Pipeline Commands (`main.py`)

All commands are driven via `main.py` (orchestrated by `app/pipeline/commands.py`):

| Command | Action | Key Inputs | Primary Outputs |
| :--- | :--- | :--- | :--- |
| `pull` | Fetches raw stat totals/per-game averages from NBA API | `nba_api` | `data/data.json` |
| `rank` | Scores all players using `ZScoreStrategy` | `data/data.json`, `config.yaml` | `data/data_zscores.json`, `data/fantasy_rankings.csv` |
| `roster` | Slices `ScoredPool` into team snapshots | `data/data_zscores.json`, `config.yaml` | `data/data_myteam.json`, `data/data_matchup.json` |
| `evaluate` | Evaluates replacement candidates vs drop candidate | `data/data_zscores.json`, `config.yaml` | `data/data_top_n_replacements.json` |
| `predict` | Builds injury-adjusted projections for today's games | NBA Schedule, `data/injuries.json` | `data/daily_projections*.json` |
| `all` | Runs `pull` ➔ `rank` ➔ `roster` ➔ `evaluate` | All sources | All output files |

*CLI override*: `--player <ID>` overrides the default `drop_candidate` specified in `config.yaml`.

## Injury & Minute Redistribution (`app/ingestion/projection_ingestion.py`)

1. **Schedule Filter**: Identifies NBA teams playing today (`fetch_todays_playing_teams()`).
2. **Injury Marking**: Matches players against `data/injuries.json` with status `"OUT"`.
3. **Minute Redistribution**: Sums missing minutes per team from `OUT` players. Scales active players' counting stats by:
   $$\text{Factor} = 1 + \frac{\text{Missing Minutes}}{\text{Total Active Minutes}}$$
4. **Recalculation**: Recalculates `FG%`, `FT%`, and `MIN` post-scaling for active players; excludes non-playing and OUT players.

## Data Persistence (`data/`)

- `data.json`: Raw player stats dict (`stats_curr_season`, `stats_prev_season`).
- `data_zscores.json`: Scored pool checkpoint (`zPTS`, `zREB`, ..., `Total_Value`).
- `data_myteam.json` / `data_matchup.json`: Roster-sliced scored player dicts.
- `data_top_n_replacements.json`: Ranked replacement options containing per-category value-added dicts.
- `injuries.json`: Manual injury override list (`[{"id": 1234, "status": "OUT"}]`).
