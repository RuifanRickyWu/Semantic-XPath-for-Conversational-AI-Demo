# Hierarchical Semantic XPath with Score Fusion

We formalize **Semantic XPath** as a hierarchical retrieval framework over tree-structured data. The framework extends classical XPath with semantic predicates and score aggregation, while preserving stepwise structural semantics and enabling principled score combination across hierarchy levels.

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

Uses **max** aggregation over children:

- `π_v(p) = max_{u ∈ ch(v)} π_u(p)`

### 3. mass() - Prevalence Aggregation

Characterizes the **general prevalence** of a property among children.

**Syntax:** `mass(ChildType[inner_predicate])`

**Example:** `Day[mass(POI[sem(content =~ "artistic")])]`

Uses **average** aggregation over children:

- `π_v(p) = Σ_{u ∈ ch(v)} π_u(p) / |ch(v)|`

## AND and OR Operators

When a predicate contains multiple conditions, conjunction and disjunction are resolved.

### Disjunction (OR)

For a predicate `p = c1 OR c2 OR ... OR ck`, we use **max**:

- `π_v(p) = max_{j=1..k} π_v(cj)`

### Conjunction (AND)

For a predicate `p = c1 AND c2 AND ... AND ck`, we use **product**:

- `π_v(p) = ∏_{j=1..k} π_v(cj)`

## Decision Guide: Choosing Predicates

| Scenario | Predicate | Reasoning |
|----------|-----------|-----------|
| Property of the node itself | `sem()` | Score local content |
| "Any child has property X" | `exist()` | Max over children |
| "Children are generally X" | `mass()` | Average over children |

## Score Fusion Across Query Steps

For each returned node `u`, the final score is the **product** of all predicate scores along the execution path.

Let `π_i(u)` denote the predicate score at step `i` along the execution path to `u`. The final relevance score is:

- `Score(u, Q) = ∏_{i : pi ≠ ⊥} π_i(u)`

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

Each POI contributes local semantic evidence. The `mass` operator aggregates these scores using average.

### Find Museums in an Artistic Day

```xpath
/Itinerary/Day[mass(POI[sem(content =~ "artistic")])]/POI[sem(content =~ "museum")]
```

- The `Day` node acquires a contextual score (e.g., artistic day = 0.8)
- The `POI` node has its own local score (e.g., museum = 0.9)
- Final relevance is computed as the product: 0.8 × 0.9 = 0.72

### Find Days with a Museum

```xpath
/Itinerary/Day[exist(POI[sem(content =~ "museum")])]
```

Uses max aggregation: day score is the highest museum score among its POIs.
