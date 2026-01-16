# Hierarchical Semantic XPath with Bayesian Fusion

We formalize **Semantic XPath** as a hierarchical retrieval framework over tree-structured data. The framework extends classical XPath with semantic predicates and probabilistic inference, while preserving stepwise structural semantics and enabling principled score aggregation across hierarchy levels.

## Data Model

Structured data are represented as a rooted tree:

- Tree: `T = (V, E, r)`
- `V`: set of nodes  
- `E`: set of edges  
- `r`: root node  

Each node `v ∈ V` has a type `κ(v)` (e.g., *Day*, *POI*, *Restaurant*).

- Leaf nodes may contain textual attributes.
- Internal nodes may be non-textual and derive semantics from descendants.

## Semantic XPath Queries

A Semantic XPath query is an ordered sequence of query steps:

- `Q = <q1, q2, ..., qn>`

Each step is a triple:

- `qi = (κi, pi, ιi)`

where:
- `κi` is the target node type,
- `pi` is an optional semantic predicate,
- `ιi` is an optional positional constraint.

### Query Execution Semantics

Query execution follows standard XPath semantics. Starting from the root candidate set:

- `C0 = {r}`

Each step applies structural expansion, predicate filtering, and positional selection:

- `Ci = Select_ιi( Filter_pi( Expand_κi(Ci-1) ) )`

Structural operations are deterministic. Semantic predicates introduce probabilistic scoring.

## Semantic Predicates

Semantic XPath v2 introduces three predicate types with clear semantics:

### 1. sem() - Local Semantic Match

Scores the node's **own content only** (no subtree aggregation).

**Syntax:** `sem(content =~ "value")`

**Example:** `POI[sem(content =~ "museum")]`

For a node `v` with textual content `X_v`, the posterior probability is:

- `π_v(c) = Pr(Z_v(c) = 1 | X_v)`

### 2. exist() - Existential Aggregation

Checks if **at least one child** of specified type matches the inner predicate.

**Syntax:** `exist(ChildType[inner_predicate])`

**Example:** `Day[exist(POI[sem(content =~ "museum")])]`

Uses **Noisy-OR** aggregation over children:

- `π_v(p) = 1 − ∏_{u ∈ ch(v)} (1 − π_u(p))`

### 3. mass() - Prevalence Aggregation

Characterizes the **general prevalence** of a property among children.

**Syntax:** `mass(ChildType[inner_predicate])`

**Example:** `Day[mass(POI[sem(content =~ "artistic")])]`

Uses **Beta-Bernoulli** aggregation:

- `ρ_v(p) ~ Beta(α, β)`
- `Z_u(p) | ρ_v(p) ~ Bernoulli(ρ_v(p))`

Posterior mean:

- `π_v(p) = (α + Σ_{u ∈ ch(v)} π_u(p)) / (α + β + |ch(v)|)`

## AND and OR Operators

When a predicate contains multiple conditions, conjunction and disjunction are resolved.

### Disjunction (OR)

For a predicate `p = c1 OR c2 OR ... OR ck`, we use Noisy-OR:

- `π_v(p) = 1 − ∏_{j=1..k} (1 − π_v(cj))`

### Conjunction (AND)

For a predicate `p = c1 AND c2 AND ... AND ck`, evidence is aggregated in log-odds space:

- `ℓ_v(p) = Σ_{j=1..k} log( π_v(cj) / (1 − π_v(cj)) )`
- `π_v(p) = sigmoid(ℓ_v(p))`

## Decision Guide: Choosing Predicates

| Scenario | Predicate | Reasoning |
|----------|-----------|-----------|
| Property of the node itself | `sem()` | Score local content |
| "Any child has property X" | `exist()` | Noisy-OR over children |
| "Children are generally X" | `mass()` | Beta-Bernoulli prevalence |

## Bayesian Fusion Across Query Steps

For each returned node `u`, define a latent relevance variable:

- `Pr(Z_u = 1) = 0.5`

Each query step with a semantic predicate contributes independent evidence.

Let `π_i(u)` denote the predicate posterior at step `i` along the execution path to `u`. Accumulated log-odds are:

- `ℓ(u) = Σ_{i : pi ≠ ⊥} log( π_i(u) / (1 − π_i(u)) )`

The final relevance score is:

- `Score(u, Q) = sigmoid(ℓ(u))`

## Query Examples

### Find Museums in the Second Day

```xpath
/Itinerary/Day[@index='2']/POI[sem(content =~ "museum")]
```

### Find Museums and Art Galleries

```xpath
/Itinerary/Day/POI[sem(content =~ "museum") OR sem(content =~ "art gallery")]
```

### Find an Artistic Day

```xpath
/Itinerary/Day[mass(POI[sem(content =~ "artistic")])]
```

Each POI contributes local semantic evidence. The `mass` operator aggregates these scores using Beta-Bernoulli model.

### Find Museums in an Artistic Day

```xpath
/Itinerary/Day[mass(POI[sem(content =~ "artistic")])]/POI[sem(content =~ "museum")]
```

- The `Day` node acquires a contextual score (e.g., artistic day = 0.8)
- The `POI` node has its own local score (e.g., museum = 0.9)
- Final relevance is computed via Bayesian log-odds fusion

### Find Days with a Museum

```xpath
/Itinerary/Day[exist(POI[sem(content =~ "museum")])]
```

Uses Noisy-OR: day matches if any POI is a museum.
