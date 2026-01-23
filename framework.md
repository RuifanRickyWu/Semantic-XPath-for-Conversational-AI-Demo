# Hierarchical Retrieval with Semantic Predicates

We formalize **Hierarchical Retrieval** as a structure-aware retrieval mechanism for localizing relevant substructure of conversational history over tree-structured data.

## Data Model

Conversational history is represented as a rooted tree:

- Tree: `T = (V, E, r)`
- `V`: set of nodes (versioned units of conversational state)
- `E ⊆ V × V`: parent-child relations between versions
- `r ∈ V`: root (initial conversational state)

Each node `v ∈ V` has:
- A node type `κ(v) ∈ K` (e.g., Turn, Plan, Day, POI)
- A (possibly empty) set of textual attributes `attr(v)`

## Query Generation

A query generator produces a **hierarchical retrieval query** that specifies a navigation path over the conversational history tree.

Formally, a query is an XPath-style path expression:

- `Q = s₁/s₂/.../sₘ`

where each step:

- `sᵢ = (axisᵢ, κᵢ, ψᵢ)`

consists of:
- An axis `axisᵢ ∈ {child, desc}` (children or descendants)
- A node-type test `κᵢ ∈ K`
- A (possibly empty) semantic predicate expression `ψᵢ`

## Query Execution

Query execution follows the standard XPath execution model: evaluation proceeds by recursively consuming path steps while propagating a set of candidate nodes over the conversational history tree.

### Weighted Node Sets

We represent intermediate results as weighted node sets:

- `W ⊆ V × [0, 1]`

where each pair `(v, w)` associates a history node `v` with a relevance weight `w`.

### Evaluator

We define an evaluation function:

- `Eval : P(V × [0, 1]) × Q → P(V × [0, 1])`

where `Q` is the set of all hierarchical path expressions. The evaluator is defined recursively as:

```
Eval(W, Q) = {
  W,                        if Q = ε (empty)
  Eval(Step(W, s), Q'),     if Q = s/Q'
}
```

Execution is initialized from the root:

- `Eval({(r, 1)}, Q)`

## Step Semantics

Each recursive step `Step(W, s)` expands the current node set structurally and then evaluates semantic predicates.

### Structural Expansion

For a node `v` and step `s = (axis, κ, ψ)`, let:

- `Axis(v, axis) ∈ {Ch(v), Desc(v)}`

where `Ch(v)` denotes children nodes and `Desc(v)` denotes descendant nodes. The typed candidate set is:

- `Cand(v, s) = {u ∈ Axis(v, axis) | κ(u) = κ}`

### Step Transition

The one-step transition function is defined as:

- `Step(W, s) = {(u, w · Score(u, ψ)) | (v,w)∈W, u∈Cand(v,s)}`

Thus, each recursive step updates relevance weights according to semantic predicate evaluation.

## Semantic Predicate Evaluation

Semantic predicate evaluation assigns graded relevance scores in `[0, 1]` and is defined recursively over predicate structure.

### Atomic Predicates - Atom(u, φ)

An atomic semantic predicate `φ` evaluates a node `u` and returns a score:

- `Atom(u, φ) ∈ [0, 1]`

Atomic predicates may be:
- **Local**: evaluated from `attr(u)`
- **Hierarchical**: inferred from descendant nodes

### Hierarchical Aggregation

For a hierarchical predicate `φ`, let `Sφ(u) ⊆ Desc(u)` denote the set of evidence nodes. We define two aggregation operators:

- `Agg∃(A) = max A` (existential - "at least one")
- `Aggprev(A) = (1/|A|) Σ A` (prevalence - "on average")

The hierarchical predicate score is then:

- `Atom(u, φ) = Aggφ({Atom(x, φ) | x ∈ Sφ(u)})`

### Predicate Composition - Score(u, ψ)

For a composite predicate expression `ψ`, the score is defined as:

```
Score(u, ψ) = {
  Atom(u, φ)                           if ψ = φ (atomic)
  Score(u, ψ₁) · Score(u, ψ₂)          if ψ = ψ₁ ∧ ψ₂ (conjunction)
  max{Score(u, ψ₁), Score(u, ψ₂)}      if ψ = ψ₁ ∨ ψ₂ (disjunction)
}
```

## Syntax Reference

### 1. atom() - Local Atomic Predicate

Evaluates the node's **own content** (local attribute scoring).

**Syntax:** `atom(content =~ "value")`

**Example:** `POI[atom(content =~ "museum")]`

**Paper:** `Atom(u, φ)` evaluated from `attr(u)`

### 2. agg_exists() - Existential Aggregation

Checks if **at least one child** of specified type matches the inner predicate.

**Syntax:** `agg_exists(ChildType[inner_predicate])`

**Example:** `Day[agg_exists(POI[atom(content =~ "museum")])]`

**Paper:** `Atom(u, φ) = Agg∃({Atom(x, φ) | x ∈ Sφ(u)})` where `Agg∃(A) = max A`

### 3. agg_prev() - Prevalence Aggregation

Characterizes the **general prevalence** of a property among children.

**Syntax:** `agg_prev(ChildType[inner_predicate])`

**Example:** `Day[agg_prev(POI[atom(content =~ "artistic")])]`

**Paper:** `Atom(u, φ) = Aggprev({Atom(x, φ) | x ∈ Sφ(u)})` where `Aggprev(A) = (1/|A|) Σ A`

## Logical Operators

### Disjunction (OR)

For a predicate `ψ = ψ₁ ∨ ψ₂`, use **max**:

- `Score(u, ψ) = max{Score(u, ψ₁), Score(u, ψ₂)}`

### Conjunction (AND)

For a predicate `ψ = ψ₁ ∧ ψ₂`, use **product**:

- `Score(u, ψ) = Score(u, ψ₁) · Score(u, ψ₂)`

## Decision Guide: Choosing Predicates

| Scenario | Predicate | Paper Formalization |
|----------|-----------|---------------------|
| Property of the node itself | `atom()` | `Atom(u, φ)` from `attr(u)` |
| "Any child has property X" | `agg_exists()` | `Agg∃ = max` over `Sφ(u)` |
| "Children are generally X" | `agg_prev()` | `Aggprev = avg` over `Sφ(u)` |

## Score Fusion Across Query Steps

For each returned node `u`, the final score is the **product** of all predicate scores along the execution path:

- `Score(u, Q) = ∏_{i : ψᵢ ≠ ⊥} Score(u, ψᵢ)`

## Query Examples

### Find Museums in the Second Day

```xpath
/Itinerary/Day[@index='2']/POI[atom(content =~ "museum")]
```

### Find Museums and Art Galleries

```xpath
/Itinerary/Day/POI[atom(content =~ "museum") OR atom(content =~ "art gallery")]
```

### Find an Artistic Day

```xpath
/Itinerary/Day[agg_prev(POI[atom(content =~ "artistic")])]
```

Each POI contributes local semantic evidence. The `agg_prev` operator aggregates these scores using average (`Aggprev`).

### Find Museums in an Artistic Day

```xpath
/Itinerary/Day[agg_prev(POI[atom(content =~ "artistic")])]/POI[atom(content =~ "museum")]
```

- The `Day` node acquires a contextual score (e.g., artistic day = 0.8)
- The `POI` node has its own local score (e.g., museum = 0.9)
- Final relevance is computed as the product: 0.8 × 0.9 = 0.72

### Find Days with a Museum

```xpath
/Itinerary/Day[agg_exists(POI[atom(content =~ "museum")])]
```

Uses existential aggregation (`Agg∃ = max`): day score is the highest museum score among its POIs.
