# Roster Optimization Strategies

Models roster optimization for Head-to-Head (H2H) 9-category fantasy basketball leagues.

## H2H Matchup Objective vs Total Value

- **Core Matchup Reality**: Winning H2H requires clearing category target thresholds $o_c$ (opponent totals or league median) in a majority of categories ($\ge 5$ of 9).
- **Rejected Proxy**: Maximizing $\sum_i \text{Total\_Value}_i$ is suboptimal — it over-invests in dominant categories while losing close categories.

---

## 1. Single-Slot Model (`SingleSlotOptimizationStrategy`)

Greedy coordinate descent algorithm evaluating one roster slot at a time while holding the rest of the roster fixed.

### Formulation
- **Baseline stat line**: $B_c = \sum_{i \in R \setminus \{k\}} v_{i,c}$ (for roster $R$ and slot under review $k$).
- **Candidate evaluation**: For candidate $j$, resulting team total $S_c(j) = B_c + v_{j,c}$.
- **Categories won**:
  $$W(j) = \sum_{c} \mathbf{1}[S_c(j) \ge o_c - \epsilon]$$
- **Decision rule**: Swap incumbent $k \to j^*$ iff $W(j^*) > W(k)$ (or tiebroken by margin / total value).

### Execution Modes
- **Sequential**: Swaps commit immediately slot-by-slot before evaluating subsequent slots.
- **Simultaneous**: All slots evaluated against frozen roster; proposed swaps sorted by gain and claimed without candidate reuse.

### Tiebreaker Rules
- `margin`: Maximizes total category win margin $\sum_{c \in \text{won}} (S_c(j) - o_c)$.
- `total_value`: Maximizes total z-score sum.

---

## 2. Joint ILP Model (Global Optimization)

Mixed-Integer Linear Program (MILP) selecting all $m$ roster slots simultaneously.

### Formulation
$$\max \sum_{c=1}^{9} y_c$$

**Subject to**:
1. **Roster Size**: $\sum_{i=1}^{N} x_i = m \quad (x_i \in \{0,1\})$
2. **Category Win-Linking (Big-M)**:
   $$\sum_{i=1}^{N} x_i v_{i,c} \ge o_c + \epsilon - M_c (1 - y_c) \quad (y_c \in \{0,1\})$$
   *Note*: $M_c$ must be calculated per category ($M_c > \max \text{Team Total}_c - o_c$).
3. **Position Constraints**:
   $$\sum_{i \in \text{eligible}(p)} x_i \ge \text{required\_slots}(p)$$

### Punting in Joint ILP
- **Emergent**: Solver naturally concedes categories when concentrating value elsewhere yields more total category wins.
- **Deliberate**: Fix $y_c = 0$ for punt categories, releasing the solver from clearing $o_c$.
