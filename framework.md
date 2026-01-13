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

## Semantic Predicates and Leaf-Level Evidence

Each semantic predicate consists of one or more **atomic conditions**.

For a leaf node `v` and an atomic condition `c`, define a posterior probability:

- `π_v(c) = Pr(Z_v(c) = 1 | X_v)`

where:
- `Z_v(c)` indicates whether node `v` satisfies condition `c`,
- `X_v` denotes the textual content of `v`.

These posteriors are produced by a calibrated semantic scoring model.

## AND and OR Inside a Predicate

When a predicate contains multiple atomic conditions, conjunction and disjunction are resolved **within a single node**.

### Disjunction (OR)

For a predicate `p = c1 OR c2 OR ... OR ck`, we use a Noisy-OR model:

- `π_v(p) = 1 − ∏_{j=1..k} (1 − π_v(cj))`

### Conjunction (AND)

For a predicate `p = c1 AND c2 AND ... AND ck`, evidence is aggregated in log-odds space:

- `ℓ_v(p) = Σ_{j=1..k} log( π_v(cj) / (1 − π_v(cj)) )`
- `π_v(p) = sigmoid(ℓ_v(p))`

## Existential and Global Predicates over Hierarchy

Internal nodes without textual attributes infer semantic predicates from child evidence using explicit quantifiers.

### Existential Predicates (`exists`)

An internal node satisfies predicate `p` if **at least one child** satisfies `p`:

- `π_v(p) = 1 − ∏_{u ∈ ch(v)} (1 − π_u(p))`

### Global Predicates (`all`)

A predicate may characterize an internal node as a whole. We model prevalence using a Beta–Bernoulli hierarchy:

- `ρ_v(p) ~ Beta(α, β)`
- `Z_u(p) | ρ_v(p) ~ Bernoulli(ρ_v(p))`

The posterior mean prevalence is:

- `π_v(p) = (α + Σ_{u ∈ ch(v)} π_u(p)) / (α + β + |ch(v)|)`

## Bayesian Fusion Across Query Steps

For each returned node `u`, define a latent relevance variable:

- `Pr(Z_u = 1) = 0.5`

Each query step with a semantic predicate contributes independent evidence.

Let `π_i(u)` denote the predicate posterior at step `i` along the execution path to `u`. Accumulated log-odds are:

- `ℓ(u) = Σ_{i : pi ≠ ⊥} log( π_i(u) / (1 − π_i(u)) )`

The final relevance score is:

- `Score(u, Q) = sigmoid(ℓ(u))`
