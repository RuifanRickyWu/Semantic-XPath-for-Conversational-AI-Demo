# Semantic XPath: Hierarchical Retrieval with Probabilistic Inference

A framework for querying hierarchical data using natural language with **semantic predicates**, **hierarchical aggregation**, and **Bayesian score fusion**.

## Core Idea

Traditional XPath operates on exact matches. Semantic XPath extends this with:
- **Semantic matching**: Match by meaning, not just text
- **Probabilistic scores**: Every match has a confidence score in [0, 1]
- **Hierarchical aggregation**: Aggregate evidence from children to parents
- **Bayesian fusion**: Combine scores across query steps

```
User: "find museums in artistic days"

Semantic XPath: /Itinerary/Day[mass(POI[sem(content =~ "artistic")])]/POI[sem(content =~ "museum")]

Result: [Art Gallery of Ontario: 0.95, Royal Ontario Museum: 0.89, ...]
```

---

## Table of Contents

1. [End-to-End Flow](#end-to-end-flow)
2. [Mathematical Foundation](#mathematical-foundation)
3. [Query Syntax](#query-syntax)
4. [Predicate Types](#predicate-types)
5. [Schema System](#schema-system)
6. [Usage](#usage)
7. [Configuration](#configuration)
8. [Project Structure](#project-structure)

---

## End-to-End Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           SEMANTIC XPATH PIPELINE                            │
└──────────────────────────────────────────────────────────────────────────────┘

     User Request                    LLM Query                   Structured
    (Natural Language)              Generator                      Query
          │                            │                            │
          ▼                            ▼                            ▼
┌─────────────────┐           ┌─────────────────┐           ┌─────────────────┐
│  "find museums  │           │   GPT-4 with    │           │   /Itinerary/   │
│   in artistic   │  ──────▶  │  schema-aware   │  ──────▶  │   Day[mass(...)]│
│     days"       │           │    prompts      │           │   /POI[sem(...)]│
└─────────────────┘           └─────────────────┘           └─────────────────┘
                                                                    │
                    ┌───────────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              QUERY EXECUTION                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   1. PARSE QUERY                                                             │
│      ┌─────────────────────────────────────────────────────┐                │
│      │ Query: /Itinerary/Day[mass(POI[sem(...)])]/POI[sem()]                │
│      │                                                                       │
│      │ Steps:                                                                │
│      │   Step 0: Itinerary (root)                                           │
│      │   Step 1: Day [predicate: mass(POI[sem(content =~ "artistic")])]     │
│      │   Step 2: POI [predicate: sem(content =~ "museum")]                  │
│      └─────────────────────────────────────────────────────┘                │
│                                                                              │
│   2. BFS TRAVERSAL WITH SCORING                                             │
│      ┌─────────────────────────────────────────────────────┐                │
│      │ Step 0: [Itinerary] ─── root                                         │
│      │            │                                                          │
│      │ Step 1: [Day1, Day2, Day3] ─── expand to children                    │
│      │            │                                                          │
│      │         Score each Day with mass(POI[sem("artistic")])               │
│      │            │  Day1: 0.72 (Beta-Bernoulli over POI scores)            │
│      │            │  Day2: 0.85                                              │
│      │            │  Day3: 0.45                                              │
│      │            │                                                          │
│      │ Step 2: [POI1, POI2, ...] ─── expand to children                     │
│      │            │                                                          │
│      │         Score each POI with sem("museum")                            │
│      │            │  Art Gallery: 0.92 (local score)                        │
│      │            │  CN Tower: 0.08                                          │
│      │            │  Royal Ontario Museum: 0.95                             │
│      └─────────────────────────────────────────────────────┘                │
│                                                                              │
│   3. BAYESIAN FUSION                                                         │
│      ┌─────────────────────────────────────────────────────┐                │
│      │ For each final node, accumulate log-odds from all steps:             │
│      │                                                                       │
│      │ Art Gallery of Ontario (in Day 1):                                   │
│      │   Step 1: Day "artistic" score = 0.72                                │
│      │           log-odds = log(0.72/0.28) = 0.944                          │
│      │   Step 2: POI "museum" score = 0.92                                  │
│      │           log-odds = log(0.92/0.08) = 2.442                          │
│      │   Total log-odds = 0.944 + 2.442 = 3.386                             │
│      │   Final score = sigmoid(3.386) = 0.967                               │
│      └─────────────────────────────────────────────────────┘                │
│                                                                              │
│   4. FILTER & RANK                                                           │
│      ┌─────────────────────────────────────────────────────┐                │
│      │ Apply threshold (e.g., 0.5) and top_k (e.g., 5)                      │
│      │ Sort by final score descending                                        │
│      │                                                                       │
│      │ Results:                                                              │
│      │   1. Royal Ontario Museum: 0.98                                      │
│      │   2. Art Gallery of Ontario: 0.97                                    │
│      │   3. Casa Loma: 0.61                                                 │
│      └─────────────────────────────────────────────────────┘                │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Component Summary

| Component | Role | Key Files |
|-----------|------|-----------|
| **Query Generator** | NL → Semantic XPath | `xpath_query_generation/` |
| **Parser** | Query string → AST | `dense_xpath/parser.py` |
| **Executor** | BFS traversal + fusion | `dense_xpath/dense_xpath_executor.py` |
| **Predicate Handler** | Scoring + aggregation | `dense_xpath/predicate_handler.py` |
| **Scorer** | Semantic similarity | `predicate_classifier/` |

---

## Mathematical Foundation

### Data Model

Hierarchical data is a rooted tree `T = (V, E, r)`:
- `V`: nodes (e.g., Day, POI, Restaurant)
- `E`: parent-child edges
- `r`: root node

Each node `v` has:
- Type `κ(v)` (e.g., "POI", "Day")
- Content `X_v` (text fields like name, description)
- Children `ch(v)` (structural children defined in schema)

### Semantic Scoring

For a semantic condition `c` (e.g., "museum") and node `v` with content `X_v`:

```
π_v(c) = P(node v satisfies c | X_v)
```

This posterior probability is computed by a scorer (LLM, NLI entailment, or cosine similarity).

### Three Predicate Types

#### 1. sem() - Local Semantic Match

Scores the node's **own content only**. Does not look at children.

```
POI[sem(content =~ "museum")]

π_v("museum") = Scorer(X_v, "museum")
```

#### 2. exist() - Existential Aggregation (Noisy-OR)

"At least one child matches" - high score if ANY child has high score.

```
Day[exist(POI[sem(content =~ "museum")])]

π_v(p) = 1 - ∏_{u ∈ children(v)} (1 - π_u(p))
```

**Example**: Children with scores [0.95, 0.1, 0.05]
```
exist() = 1 - (0.05 × 0.9 × 0.95) = 1 - 0.043 = 0.957
```

#### 3. mass() - Prevalence Aggregation (Beta-Bernoulli)

"Children are generally X" - smoothed average of child scores.

```
Day[mass(POI[sem(content =~ "artistic")])]

π_v(p) = (α + Σ_{u ∈ children(v)} π_u(p)) / (α + β + |children(v)|)
```

Where `α = β = 1` (uniform prior).

**Example**: Children with scores [0.8, 0.7, 0.6, 0.3]
```
mass() = (1 + 2.4) / (1 + 1 + 4) = 3.4 / 6 = 0.567
```

### Logical Operators

#### AND (Log-odds aggregation)

```
sem(content =~ "outdoor") AND sem(content =~ "historic")

ℓ(p) = Σ_j log(π(c_j) / (1 - π(c_j)))
π(p) = sigmoid(ℓ(p))
```

#### OR (Noisy-OR)

```
sem(content =~ "museum") OR sem(content =~ "gallery")

π(p) = 1 - ∏_j (1 - π(c_j))
```

### Bayesian Fusion Across Steps

For multi-step queries, scores accumulate in log-odds space:

```
Query: /Day[mass(...)]/POI[sem(...)]

For each final POI node u:
  ℓ(u) = Σ_{steps with predicates} log(π_i(u) / (1 - π_i(u)))
  
Final Score = sigmoid(ℓ(u))
```

This ensures:
- High parent score + high child score → very high final score
- Low parent score penalizes even high-scoring children
- Scores are properly calibrated probabilities

---

## Query Syntax

### Path Navigation

```xpath
/Itinerary/Day/POI                     # All POIs in all Days
/Itinerary/Day[@index='2']/POI         # POIs in Day 2 (attribute index)
/Itinerary/Day/POI[2]                  # 2nd POI in EACH Day (local)
(/Itinerary/Day/POI)[2]                # 2nd POI overall (global)
```

### Positional Indexing

| Syntax | Meaning |
|--------|---------|
| `[@index='2']` | Attribute-based index |
| `[2]` | 2nd element |
| `[-1]` | Last element |
| `[1:3]` | Elements 1, 2, 3 |
| `[-2:]` | Last 2 elements |

### Semantic Predicates

```xpath
# Local match (node's own content)
/Itinerary/Day/POI[sem(content =~ "museum")]

# Existential (any child matches)
/Itinerary/Day[exist(POI[sem(content =~ "museum")])]

# Prevalence (children generally match)
/Itinerary/Day[mass(POI[sem(content =~ "artistic")])]

# Logical operators
/Itinerary/Day/POI[sem(content =~ "outdoor") AND sem(content =~ "free")]
/Itinerary/Day/POI[sem(content =~ "museum") OR sem(content =~ "gallery")]

# Aggregation-level AND/OR
/Itinerary/Day[exist(POI[sem(content =~ "museum")]) AND exist(Restaurant[sem(content =~ "italian")])]
```

---

## Predicate Types

### Decision Guide

| Query Intent | Predicate | Example |
|--------------|-----------|---------|
| Property of the node itself | `sem()` | "museum POI" → `POI[sem(...)]` |
| Any child has property X | `exist()` | "day with a museum" → `Day[exist(POI[...])]` |
| Children are generally X | `mass()` | "artistic day" → `Day[mass(POI[...])]` |

### Comparison

```
Day with 5 POIs: [Museum: 0.95, Park: 0.1, Mall: 0.05, Theater: 0.1, Cafe: 0.02]

exist(POI[sem(content =~ "museum")]): 0.957 (high - museum exists)
mass(POI[sem(content =~ "museum")]):  0.317 (low - most aren't museums)
```

---

## Schema System

Schemas define the tree structure and distinguish node fields from children.

### Example Schema (itinerary.yaml)

```yaml
name: "itinerary"

nodes:
  Itinerary:
    type: root
    fields: []
    children: ["Day"]
    
  Day:
    type: container
    index_attr: "index"
    fields: []                      # Day's own fields
    children: ["POI", "Restaurant"] # Structural children
    
  POI:
    type: leaf
    fields: [name, time_block, description, travel_method, expected_cost, highlights]
    children: []
    
  Restaurant:
    type: leaf
    fields: [name, time_block, description, travel_method, expected_cost, highlights]
    children: []
```

### Why fields vs children matters

```xml
<Day index="1">
  <POI>...</POI>          <!-- Child: in children list -->
  <Restaurant>...</Restaurant>  <!-- Child: in children list -->
  <theme>relaxing</theme>  <!-- Field: NOT in children list, part of Day's own content -->
</Day>
```

When scoring `Day[mass(POI[...])]`:
- `<POI>` and `<Restaurant>` are structural children → aggregated
- `<theme>` is Day's own field → not treated as child

### Available Schemas

| Schema | Hierarchy | Use Case |
|--------|-----------|----------|
| `itinerary` | Itinerary → Day → POI/Restaurant | Travel planning |
| `todolist` | TodoList → Project → Task → SubTask | Task management |
| `curriculum` | Curriculum → Course → Concept/Exercise | Education |
| `support` | SupportSystem → Customer → Ticket → Symptom/Cause/Resolution | Help desk |
| `session_recommendation` | RecommendationHub → Session → Step → Objective → Item | Shopping/DIY |

---

## Usage

### Interactive Mode

```bash
python -m pipeline.semantic_xpath_pipeline
```

```
============================================================
Semantic XPath Pipeline - Interactive Mode
============================================================

Request: museums in artistic days

Query: /Itinerary/Day[mass(POI[sem(content =~ "artistic")])]/POI[sem(content =~ "museum")]

Matched 2 node(s) (sorted by score):
============================================================

[Result 1] ⭐ Score: 0.967
📍 Tree Path: Itinerary > Day 1 > Art Gallery of Ontario

[Result 2] ⭐ Score: 0.943
📍 Tree Path: Itinerary > Day 2 > Royal Ontario Museum
```

### Programmatic Usage

```python
from dense_xpath import DenseXPathExecutor

executor = DenseXPathExecutor(
    schema_name="itinerary",
    scoring_method="entailment",
    top_k=5,
    score_threshold=0.3
)

# Simple semantic query
result = executor.execute('/Itinerary/Day/POI[sem(content =~ "museum")]')

# Hierarchical query with aggregation
result = executor.execute(
    '/Itinerary/Day[mass(POI[sem(content =~ "artistic")])]/POI[sem(content =~ "museum")]'
)

# Aggregation-level AND
result = executor.execute(
    '/Itinerary/Day[exist(POI[sem(content =~ "museum")]) AND exist(Restaurant[sem(content =~ "italian")])]'
)

for node in result.matched_nodes:
    print(f"- {node.tree_path}: {node.score:.3f}")
```

### Command Line Options

```bash
# Scoring methods
python -m pipeline.semantic_xpath_pipeline --scoring llm
python -m pipeline.semantic_xpath_pipeline --scoring entailment
python -m pipeline.semantic_xpath_pipeline --scoring cosine

# Threshold and top-k
python -m pipeline.semantic_xpath_pipeline --top-k 10 --threshold 0.5
```

---

## Configuration

Edit `config.yaml`:

```yaml
# Schema selection
active_schema: "itinerary"
active_data: "travel_memory_3day"

# Executor settings
xpath_executor:
  top_k: 5
  score_threshold: 0.01
  scoring_method: "entailment"  # "llm", "entailment", or "cosine"

# OpenAI (for LLM scoring and query generation)
openai:
  api_key: "${OPENAI_API_KEY}"
  model: "gpt-4o"
```

### Scoring Methods

| Method | Speed | Accuracy | Cost |
|--------|-------|----------|------|
| `llm` | Slow | Highest | API costs |
| `entailment` | Medium | High | Free (local) |
| `cosine` | Fast | Good | Free (local) |

---

## Project Structure

```
LLM-VM/
├── pipeline/
│   └── semantic_xpath_pipeline.py   # Main entry point
├── xpath_query_generation/
│   └── xpath_query_generator.py     # NL → Semantic XPath (LLM)
├── dense_xpath/
│   ├── dense_xpath_executor.py      # Main executor with Bayesian fusion
│   ├── models.py                    # SemanticCondition, CompoundPredicate, etc.
│   ├── parser.py                    # Query parser (sem/exist/mass/AND/OR)
│   ├── predicate_handler.py         # Scoring + aggregation logic
│   ├── node_utils.py                # XML node utilities
│   ├── schema_loader.py             # Schema loading
│   └── trace_writer.py              # Execution traces
├── predicate_classifier/
│   ├── llm_scorer.py                # GPT-4 scoring
│   ├── entailment_scorer.py         # BART NLI scoring
│   └── cosine_scorer.py             # Embedding similarity
├── storage/
│   ├── schemas/                     # Schema definitions
│   ├── memory/                      # XML data files
│   └── prompts/                     # Query generation prompts
├── config.yaml
├── framework.md                     # Mathematical specification
└── README.md
```

---

## Quick Reference

### Predicate Syntax

| Predicate | Syntax | Use When |
|-----------|--------|----------|
| `sem()` | `sem(content =~ "X")` | Matching node's own content |
| `exist()` | `exist(Child[sem(...)])` | Any child has property |
| `mass()` | `mass(Child[sem(...)])` | Children generally have property |

### Aggregation Formulas

| Operator | Formula | Interpretation |
|----------|---------|----------------|
| `sem()` | `π = Scorer(content, query)` | Local score |
| `exist()` | `π = 1 - ∏(1 - π_child)` | Noisy-OR |
| `mass()` | `π = (α + Σπ_child) / (α + β + n)` | Beta-Bernoulli |
| `AND` | `π = sigmoid(Σ log-odds)` | All conditions |
| `OR` | `π = 1 - ∏(1 - π_j)` | Any condition |

### Example Queries

```xpath
# Find museums
/Itinerary/Day/POI[sem(content =~ "museum")]

# Find days with museums
/Itinerary/Day[exist(POI[sem(content =~ "museum")])]

# Find artistic days
/Itinerary/Day[mass(POI[sem(content =~ "artistic")])]

# Find museums in artistic days
/Itinerary/Day[mass(POI[sem(content =~ "artistic")])]/POI[sem(content =~ "museum")]

# Days with both museum AND Italian restaurant
/Itinerary/Day[exist(POI[sem(content =~ "museum")]) AND exist(Restaurant[sem(content =~ "italian")])]
```

---

## License

MIT License
