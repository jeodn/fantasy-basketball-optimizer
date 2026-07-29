# System Architecture

Domain-driven, modular Python application for fantasy basketball analysis, replacement evaluation, and roster optimization.

## Layer Boundaries & Directory Structure

```
app/
├── domain/       # Pure data models & schemas (no I/O, no business math)
├── ingestion/    # Data fetching, transformation, injury/minute redistribution
├── analytics/    # Core mathematical engines (scoring, evaluation, optimization)
│   ├── scoring/      # Scoring strategies (Z-score, impact math)
│   ├── evaluation/   # Candidate vs drop evaluation (VORP)
│   └── optimization/ # Roster optimization (Single-slot greedy, Joint ILP)
├── repository/   # Layer-agnostic I/O primitives (JSON files, NBA API)
└── pipeline/     # High-level CLI command orchestrators
```

## Key Domain Models (`app/domain/`)

- `Player` (`app/domain/player.py`): Primary player entity (`player_id`, `name`, `stats_curr_season`, `stats_prev_season`).
- `PlayerPool` (`app/domain/player.py`): Keyed dictionary `Dict[int, Player]`. Converts to Pandas DataFrame for vector ops.
- `CategoryScores` (`app/domain/scoring.py`): Per-player score output (`scores` dict containing `zPTS`, `zREB`, ..., `FG%_Impact`, `total_value`).
- `ScoredPlayer` (`app/domain/scoring.py`): Pair of `(Player, CategoryScores)`. Converts to Pandas Series.
- `ScoredPool` (`app/domain/scoring.py`): Keyed dictionary `Dict[int, ScoredPlayer]`. Serializes to/from `data/data_zscores.json`.
- `Roster` (`app/domain/roster.py`): Lightweight container holding `team_name` and list of `player_ids`.
- `RosterSnapshot` (`app/domain/scoring.py`): Slice of a `ScoredPool` for a given `Roster`. Aggregates category totals and Series.
- `OptimizationResult` (`app/domain/optimization.py`): Result wrapper containing `selected_players`, `objective_value`, `summary_metrics`, and `metadata`.

## Data Flow Diagram

```
[ NBA API / Remote ]
        │
        ▼ (ingestion / repository)
 [ data/data.json ] ──► [ PlayerPool ]
                             │
                             ▼ (analytics/scoring)
                   [ ScoredPool ] (data/data_zscores.json)
                             │
            ┌────────────────┴────────────────┐
            ▼ (analytics/evaluation)          ▼ (analytics/optimization)
    [ EvaluationResult ]              [ OptimizationResult ]
  (data/data_top_n_replacements.json) (Single-slot / Joint ILP)
```
