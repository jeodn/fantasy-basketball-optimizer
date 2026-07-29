# Scoring & Player Evaluation

Defines per-player statistical valuation, z-score calculations, percentage impact models, and replacement evaluations (VORP).

## Standard 9-Category Scoring

Categories tracked: `FG%`, `FT%`, `3PM`, `PTS`, `REB`, `AST`, `STL`, `BLK`, `TO` (Turnovers: lower is better).

## Z-Score Strategy (`app/analytics/scoring/z_score.py`)

1. **Category Z-Scores**:
   $$z_{i,c} = \begin{cases} \frac{x_{i,c} - \mu_c}{\sigma_c} & \text{for standard categories (higher is better)} \\ \frac{\mu_c - x_{i,c}}{\sigma_c} & \text{for TO (lower is better)} \end{cases}$$

2. **Volume-Weighted Impact Scores (FG% / FT%)**:
   Raw percentages are not additive across players. To accurately account for volume:
   $$\text{FG\% Impact}_i = \text{FGM}_i - (\text{FGA}_i \times \text{League FG\%})$$
   $$\text{FT\% Impact}_i = \text{FTM}_i - (\text{FTA}_i \times \text{League FT\%})$$
   Z-scores for percentages ($z_{\text{FG\%}}$, $z_{\text{FT\%}}$) are computed on these impact metrics, not raw percentages.

3. **Weighting & Punting**:
   $$z'_{i,c} = \begin{cases} 0.0 & \text{if } c \in \text{punt\_categories} \\ z_{i,c} \times w_c & \text{otherwise} \end{cases}$$

4. **Total Value**:
   $$\text{Total\_Value}_i = \sum_{c \in \text{categories}} z'_{i,c}$$

## Replacement Evaluation / VORP (`app/analytics/evaluation/candidate_evaluator.py`)

Evaluates free agent / candidate replacements against a specific roster drop candidate:

- **Per-Category Value Added**:
  $$\text{Value Added}_c(j) = \text{Score}_c(\text{candidate } j) - \text{Score}_c(\text{drop candidate } k)$$

- **Total Added Value**:
  $$\text{Total Added Value}(j) = \sum_{c} \text{Value Added}_c(j)$$

- **Output**: Returns `EvaluationResult` containing top $N$ `ReplacementOption` instances sorted descending by total added value.
