# Context: Fantasy Basketball Roster Optimization (Single-Slot Model)

## Setup
- 9-category H2H fantasy basketball league.
- Each player has a black-box rating vector `v_i ∈ R^9`, one scalar per category,
  oriented so **higher is always better** (rate-based categories like TO must
  already be sign-flipped/negated by the rating method; percentage categories
  like FG%/FT% must already be volume-weighted "impact" scores, not raw
  percentages — raw percentages are not safely additive across players).
- Winning a category means clearing a threshold, not maximizing a sum. Winning
  a matchup means winning a majority of the 9 categories. This is the core
  fact the optimization must respect — it is NOT the same as maximizing total
  stat value.

## Model in use: single-slot (one-at-a-time) evaluation

Rather than jointly re-optimizing the whole roster, evaluate ONE roster slot
at a time, holding all other players fixed. This is coordinate descent /
greedy local search, not a global optimizer.

**Given:**
- Current roster `R`, size `m`. One slot `k ∈ R` is under review.
- Baseline contribution of the rest of the team:
  `B_c = sum over i in R\{k} of v_{i,c}`  (per category c)
- Candidate pool `C_k`: free agents / trade targets eligible for slot `k`'s
  position (or UTIL/flex eligibility), including the incumbent player `k`
  himself as the "do nothing" baseline.
- Opponent or threshold vector `o_c` per category (e.g. a specific H2H
  opponent's current stat line, or league-average/median team for planning
  ahead without a known opponent).

**For each candidate `j ∈ C_k`:**
```
S_c(j) = B_c + v_{j,c}                         # resulting team stat line
W(j)   = sum over c of  1[ S_c(j) >= o_c ]      # categories won
```

**Decision rule:**
```
j* = argmax over j in C_k of W(j)
Swap incumbent k -> j*  iff  W(j*) > W(k)
```

This requires no ILP solver — it's a direct ranking/scoring pass over
candidates, evaluated per position slot.

## Important considerations / known limitations

1. **Order dependence.** If multiple slots are being reconsidered, evaluating
   them sequentially (committing each swap before the next) can give a
   different final roster than a different evaluation order. State explicitly
   whether swaps are being applied sequentially (each commits before the next
   slot is evaluated) or simultaneously (all slots scored against the
   original frozen roster, proposed swaps then reconciled/tie-broken if two
   slots want the same free agent).

2. **Local optimum only — misses synergy.** This method cannot detect cases
   where two simultaneous swaps together flip two categories, even though
   neither swap alone flips any category. (Example: team is short in both AST
   and REB; swapping in a rebounder alone doesn't clear the REB threshold,
   swapping in a passer alone doesn't clear AST — but both together might
   clear both.) A joint multi-slot ILP is the fallback when this matters;
   the single-slot model is a practical/operational simplification, not
   claimed to be globally optimal.

3. **Ties in W(j).** Multiple candidates (or multiple full rosters, in the
   joint version) can tie on categories-won. This base formulation has no
   tiebreaker for margin-of-victory; if that matters, it needs a secondary
   objective term (e.g. lexicographic or weighted margin bonus), not assumed
   by default.

4. **Threshold vector `o_c` choice matters and should be stated per use:**
   specific known opponent (weekly H2H), league-average/median team
   (general roster planning), or manually suppressed/zeroed category (a
   deliberate "punt" — conceding a category by removing its constraint
   rather than letting it emerge from the data).

5. **Position/slot eligibility** is handled entirely by which players are
   allowed into `C_k` for a given slot — not via explicit ILP constraints in
   this single-slot formulation (that machinery is only needed in the full
   joint roster-optimization version).

## What this doc does NOT cover
- The full joint ILP formulation (`max sum_c y_c` over all `m` slots at once,
  with position-eligibility constraints) — that's a separate, harder
  combinatorial version, useful as a periodic sanity check against drift
  from greedy single-slot decisions.
- How the black-box per-category rating `v_i` itself is computed (z-scores,
  Elo, correlation adjustment, etc.) — assumed as a pre-existing input here.


# Context: Fantasy Basketball Roster Optimization (Joint ILP Model)

## Setup
- 9-category H2H fantasy basketball league.
- Player pool of size `N = m + n`: `m` players currently on roster, `n`
  players under consideration (free agents / trade targets).
- Each player has a black-box rating vector `v_i ∈ R^9`, one scalar per
  category, oriented so **higher is always better** (rate-based categories
  like TO must already be sign-flipped/negated by the rating method;
  percentage categories like FG%/FT% must already be volume-weighted
  "impact" scores, not raw percentages — raw percentages are not safely
  additive across players).
- Winning a category means clearing a threshold, not maximizing a sum.
  Winning a matchup means winning a majority of the 9 categories. This is
  the fact the optimization is built around — it is NOT the same as
  maximizing total stat value across the roster (that's a different, much
  simpler, and provably worse-aligned objective — see "Rejected
  alternative" below).

## Model: joint ILP — select the whole roster at once

Unlike the single-slot model (a separate, simpler local-search
approximation used elsewhere), this version selects all `m` roster spots
**simultaneously** by solving one mixed-integer program. It is the
global-optimum counterpart to the single-slot greedy model.

**Decision variables:**
```
x_i ∈ {0,1}   for each player i in the pool (1 = selected onto roster)
y_c ∈ {0,1}   for each category c            (1 = category is won)
```

**Objective:**
```
maximize   sum over c of y_c
```

**Constraints:**
```
sum over i of x_i = m                                   # roster size

for each category c:
  sum over i of (x_i * v_{i,c})  >=  o_c + EPS - M*(1 - y_c)
```
- `o_c`: opponent/threshold vector per category (specific H2H opponent's
  stat line, or a league-average/median team when planning without a known
  opponent).
- `EPS`: small positive tie-breaker (avoids counting an exact tie as a win).
- `M`: big-M constant. **Must be chosen larger than any plausible gap
  between team total and threshold** for every category, or the
  win-linking constraint can be silently wrong (either too loose, letting
  `y_c=1` without actually clearing the threshold, or too tight, blocking
  feasible solutions). Recompute `M` per category ideally, rather than
  using one shared constant, since category scales differ.

**Interpretation of the win-linking constraint:** if `y_c = 1`, the
constraint is active and forces the team's total in category c to actually
clear the threshold. If `y_c = 0`, the constraint goes slack (the big-M term
neutralizes it) and costs nothing. Since the objective only rewards
`y_c = 1`, the solver sets it to 1 everywhere it legally can — this is what
correctly encodes "count the categories cleared," rather than needing to be
told which ones to target.

## Rejected alternative (why not just maximize total value)

`maximize sum_i x_i * (sum_c v_{i,c})` — i.e., pick the top-`m` players by
total value — is a much simpler LP/greedy problem, but it is a poor proxy
for the actual goal. It can select a team that loses the majority of
categories (e.g. by overloading on a category you were always going to win
anyway, at the expense of others) even though its raw stat total is higher
than a joint-ILP-selected team. Do not substitute this for the categories-won
objective; it was tested against a toy example and shown to pick a
matchup-losing roster over a matchup-winning one with lower total value.

## Extending to positions / roster slots

Add linear eligibility constraints on `x`, one per position group:
```
sum over i in eligible(position p) of x_i  >=  required_count(p)
```
Multiple overlapping constraints (e.g. UTIL slots eligible for any
position) are fine — this is standard ILP constraint stacking and doesn't
change the objective or the win-linking logic above.

## Punting

Punting fits naturally into this model in two ways:
1. **Emergent punting**: solve unconstrained across all categories and
   observe which categories the optimal roster fails to clear — the solver
   may naturally abandon a category if concentrating value elsewhere wins
   more categories overall.
2. **Deliberate punting**: manually remove a category's win-linking
   constraint (or fix `y_c = 0`) to explicitly concede it, freeing the
   solver from needing to clear its threshold and letting it reallocate
   roster value elsewhere. This should be evaluated by comparing the total
   `sum y_c` with and without the punt to check whether it actually helps.

## Known considerations / limitations

1. **Multiple optima.** Different rosters can tie on categories-won; the
   solver returns one arbitrarily (solver/implementation-dependent, not
   necessarily the one with the largest safety margins). If margin-of-victory
   should break ties, add a secondary objective term (e.g. lexicographic:
   first maximize `sum y_c`, then re-solve maximizing total margin subject
   to matching that category count) — not handled by the base formulation.

2. **Big-M correctness.** Get `M` wrong (too small) and the model can be
   infeasible or give incorrect win/loss attributions; get it very large and
   some solvers suffer numerical/performance issues. Recommend computing a
   safe `M` per category from the data (e.g. max possible team total minus
   min possible threshold) rather than guessing a shared constant.

3. **Percentage categories.** As in the setup section — raw percentage
   z-scores are not additive across players; if the rating vector wasn't
   already built with volume-weighted impact scores for FG%/FT%, the model
   will produce a mathematically valid but practically wrong roster for
   those categories specifically.

4. **This is a full re-draft, not an incremental move.** The joint ILP tells
   you the best possible `m`-player team from the pool; it does not by
   itself express "the smallest set of changes from my current roster." If
   incremental/practical moves are wanted, either (a) fall back to the
   single-slot model (see separate context doc), or (b) add a constraint/
   penalty limiting the number of changes from the current roster (a
   "distance from current team" budget).

## What this doc does NOT cover
- The single-slot (one-at-a-time, coordinate-descent) model — a separate,
  simpler local-search approximation of this same problem, useful for
  routine one-move decisions without needing a solver.
- How the black-box per-category rating `v_i` itself is computed (z-scores,
  Elo, correlation adjustment, etc.) — assumed as a pre-existing input here.
- PuLP-specific implementation syntax — assumed to be supplied separately
  alongside this context if code generation is requested.