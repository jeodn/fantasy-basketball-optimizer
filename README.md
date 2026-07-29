# Fantasy Basketball Advisor & Optimizer

A modular Python framework and interactive web application for fantasy basketball team analysis, replacement player evaluation, injury-adjusted daily projections, and Head-to-Head (H2H) roster optimization.

## Features

- **Head-to-Head Roster Optimizer**: Evaluates roster slots using greedy coordinate descent search to maximize category win totals ($S_c(j) \ge o_c$) rather than naive stat sum proxies. Supports sequential/simultaneous execution modes and win-margin tiebreaking.
- **Configurable Candidate Pool & Roster Editing**: Filter candidate player pools by Top N free agents, custom player lists, or all non-rostered players. Edit active team rosters dynamically in the web interface.
- **Daily Projections & Injury Redistribution**: Calculates daily stat projections by identifying scheduled games and proportionally redistributing missing minutes from OUT players to active teammates.
- **Player Evaluation (VORP)**: Ranks replacement options against specific drop candidates by calculating per-category value-added ($v_{\text{candidate}} - v_{\text{drop}}$).
- **AI Matchup Assistant**: Provides context-aware strategic advice using Google Gemini models.
- **Comprehensive Documentation Suite**: Includes dedicated documentation in `./docs/` detailing architecture, data pipeline mechanics, scoring formulas, and optimization models.

## Repository Structure & Architecture

The codebase follows a domain-driven architecture separated inside the `app/` directory:

- **`app/domain/`**: Pure data models (`Player`, `PlayerPool`, `CategoryScores`, `ScoredPool`, `RosterSnapshot`, `OptimizationResult`). Contains no I/O or math logic.
- **`app/ingestion/`**: Data fetching, schedule filtering, and injury-adjusted minute redistribution (`projection_ingestion.py`).
- **`app/analytics/`**: Core mathematical calculation engines:
  - `app/analytics/scoring/`: Z-score calculations and volume-weighted percentage impact metrics (`ZScoreStrategy`).
  - `app/analytics/evaluation/`: Value Over Replacement Player candidate ranking (`candidate_evaluator.py`).
  - `app/analytics/optimization/`: Single-Slot greedy coordinate descent optimization (`SingleSlotOptimizationStrategy`) and Joint ILP context.
- **`app/repository/`**: Layer-agnostic I/O primitives (`file_repository.py`, `nba_api_repository.py`).
- **`app/pipeline/`**: CLI orchestrators linking ingestion, analytics, and persistence (`commands.py`).

For full technical specifications, see the `./docs/` directory:
- [architecture.md](docs/architecture.md): Layer boundaries, domain models, and data flow.
- [data_pipeline.md](docs/data_pipeline.md): Ingestion workflows, minute redistribution, CLI commands, and output schemas.
- [scoring_and_evaluation.md](docs/scoring_and_evaluation.md): 9-category Z-scores, volume-weighted impact formulas, and VORP math.
- [optimization.md](docs/optimization.md): H2H category-threshold win conditions, Single-Slot model, and Joint ILP formulation.

## Configuration

Customize settings in `config.yaml`:
- **`roster`**: Default player IDs for `my_team`, `matchup_team`, and default `drop_candidate`.
- **`scoring`**: Configures `stats_source`, `punt_categories`, and category weights.
- **`season`**: Identifies current and previous NBA seasons (e.g., `2025-26`).

Manage injuries manually:
- Set `"status": "OUT"` on player entries in `data/injuries.json` to exclude them and redistribute their minutes during daily projection generation.

## Setup & Execution

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run Pipeline Commands**:
   ```bash
   python main.py [command] [--player PLAYER_ID]
   ```
   - `pull`: Fetches raw NBA API statistics -> `data/data.json`.
   - `rank`: Calculates category z-scores -> `data/data_zscores.json`, `data/fantasy_rankings.csv`.
   - `roster`: Slices scored statistics for configured teams -> `data/data_myteam.json`, `data/data_matchup.json`.
   - `evaluate`: Ranks replacement options against a drop candidate -> `data/data_top_n_replacements.json`. Override drop candidate via `--player <ID>`.
   - `predict`: Builds injury-adjusted projections -> `data/daily_projections*.json`.
   - `all`: Sequentially runs `pull` -> `rank` -> `roster` -> `evaluate`.

3. **Launch Streamlit Web Application**:
   ```bash
   streamlit run streamlit_app.py
   ```
