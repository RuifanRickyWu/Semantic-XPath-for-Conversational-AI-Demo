# Semantic XPath: Hierarchical Retrieval with Score Fusion

A framework for querying and modifying hierarchical data using natural language with **semantic predicates**, **hierarchical aggregation**, **score fusion**, and **CRUD operations**.

## Core Idea

Traditional XPath operates on exact matches. Semantic XPath extends this with:
- **Semantic matching**: Match by meaning, not just text
- **Probabilistic scores**: Every match has a confidence score in [0, 1]
- **Hierarchical aggregation**: Aggregate scores from children to parents
- **Score fusion**: Combine scores across query steps (product)
- **CRUD Operations**: Create, Read, Update, Delete nodes using natural language

```
User: "find museums in artistic days"

Semantic XPath: Read(/Itinerary/Day[agg_prev(POI[atom(content =~ "artistic")])]/POI[atom(content =~ "museum")])

Result: [Art Gallery of Ontario: 0.95, Royal Ontario Museum: 0.89, ...]
```

```
User: "delete all the museums"

Semantic XPath: Delete(/Itinerary/Day/POI[atom(content =~ "museum")])

Result: Deleted 2 nodes, saved to result/travel_memory_v1.xml
```

---

## Table of Contents

1. [End-to-End Flow](#end-to-end-flow)
2. [CRUD Operations](#crud-operations)
3. [Mathematical Foundation](#mathematical-foundation)
4. [Query Syntax](#query-syntax)
5. [Predicate Types](#predicate-types)
6. [Schema System](#schema-system)
7. [Usage](#usage)
8. [Configuration](#configuration)
9. [Project Structure](#project-structure)

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
│      │ Query: /Itinerary/Day[agg_prev(POI[atom(...)])]/POI[atom()]          │
│      │                                                                       │
│      │ Steps:                                                                │
│      │   Step 0: Itinerary (root)                                           │
│      │   Step 1: Day [predicate: agg_prev(POI[atom(content =~ "artistic")])]│
│      │   Step 2: POI [predicate: atom(content =~ "museum")]                 │
│      └─────────────────────────────────────────────────────┘                │
│                                                                              │
│   2. BFS TRAVERSAL WITH SCORING                                             │
│      ┌─────────────────────────────────────────────────────┐                │
│      │ Step 0: [Itinerary] ─── root                                         │
│      │            │                                                          │
│      │ Step 1: [Day1, Day2, Day3] ─── expand to children                    │
│      │            │                                                          │
│      │         Score each Day with agg_prev(POI[atom("artistic")])          │
│      │            │  Day1: 0.72 (average over POI scores)                   │
│      │            │  Day2: 0.85                                              │
│      │            │  Day3: 0.45                                              │
│      │            │                                                          │
│      │ Step 2: [POI1, POI2, ...] ─── expand to children                     │
│      │            │                                                          │
│      │         Score each POI with atom("museum")                           │
│      │            │  Art Gallery: 0.92 (local score)                        │
│      │            │  CN Tower: 0.08                                          │
│      │            │  Royal Ontario Museum: 0.95                             │
│      └─────────────────────────────────────────────────────┘                │
│                                                                              │
│   3. SCORE FUSION (PRODUCT)                                                  │
│      ┌─────────────────────────────────────────────────────┐                │
│      │ For each final node, multiply scores from all steps:                 │
│      │                                                                       │
│      │ Art Gallery of Ontario (in Day 1):                                   │
│      │   Step 1: Day "artistic" score = 0.72                                │
│      │   Step 2: POI "museum" score = 0.92                                  │
│      │   Final score = 0.72 × 0.92 = 0.662                                  │
│      │                                                                       │
│      │                                                                       │
│      │                                                                       │
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
| **Parser** | Query string → AST (atom/agg_exists/agg_prev) | `dense_xpath/parser.py` |
| **Executor** | BFS traversal + fusion | `dense_xpath/dense_xpath_executor.py` |
| **Predicate Handler** | Scoring + aggregation | `dense_xpath/predicate_handler.py` |
| **Scorer** | Semantic similarity | `predicate_classifier/` |
| **CRUD Executor** | CRUD operations | `crud/crud_executor.py` |

---

## CRUD Operations

The system supports full CRUD (Create, Read, Update, Delete) operations on tree data using natural language.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CRUD PIPELINE                                    │
└─────────────────────────────────────────────────────────────────────────┘

    User Query              Intent              XPath Query
   (Natural Lang)         Classifier            Generator
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ "delete all   │     │   Classify:   │     │  Generate:    │
│  museums"     │ ──▶ │   DELETE      │ ──▶ │  /Day/POI     │
│               │     │               │     │  [sem(...)]   │
└───────────────┘     └───────────────┘     └───────────────┘
                                                   │
                      ┌────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      SEMANTIC XPATH EXECUTION                            │
│  Find candidate nodes with semantic scoring                              │
└─────────────────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      LLM NODE REASONING                                  │
│  Batched LLM calls to select truly relevant nodes from candidates        │
└─────────────────────────────────────────────────────────────────────────┘
                      │
          ┌───────────┴───────────┬───────────────┬───────────────┐
          ▼                       ▼               ▼               ▼
     ┌─────────┐            ┌─────────┐     ┌─────────┐     ┌─────────┐
     │  READ   │            │ DELETE  │     │ UPDATE  │     │ CREATE  │
     │ Return  │            │ Remove  │     │ Modify  │     │ Insert  │
     │ Results │            │ Nodes   │     │ Content │     │ New Node│
     └─────────┘            └────┬────┘     └────┬────┘     └────┬────┘
                                 │               │               │
                                 └───────────────┴───────────────┘
                                                 │
                                                 ▼
                                 ┌───────────────────────────────┐
                                 │     VERSION MANAGER           │
                                 │  Save to result/ folder       │
                                 │  (tree_v1.xml, tree_v2.xml)   │
                                 └───────────────────────────────┘
```

### Operation Types

| Operation | Description | Example Query |
|-----------|-------------|---------------|
| **Read** | Find and retrieve nodes | "find museums in the itinerary" |
| **Create** | Add new nodes | "add a sushi restaurant after lunch on day 1" |
| **Update** | Modify existing nodes | "change the CN Tower visit to 2pm" |
| **Delete** | Remove nodes | "delete all the museums" |

### Full Query Format

Each operation displays a full query showing the operation type and XPath:

```
Read(/Itinerary/Day/POI[atom(content =~ "museum")])
Delete(/Itinerary/Day[@index='2']/POI[atom(content =~ "cafe")])
Update(/Itinerary/Day/POI[atom(content =~ "CN Tower")])
Create(/Itinerary/Day[@index='1']/Restaurant)
```

### Step Timing

Each operation displays detailed timing for performance analysis:

```
⏱️  Step Timing:
---------------------------------------------
  Intent Classification          523.4ms  ██████░░░░░░░░░░░░░░  28.5%
  XPath Generation               412.1ms  ████░░░░░░░░░░░░░░░░  22.4%
  Semantic XPath Execution       156.2ms  ██░░░░░░░░░░░░░░░░░░   8.5%
  LLM Node Reasoning             689.3ms  ████████░░░░░░░░░░░░  37.5%
  Tree Modification                2.1ms  ░░░░░░░░░░░░░░░░░░░░   0.1%
  Save Version                    55.8ms  █░░░░░░░░░░░░░░░░░░░   3.0%
---------------------------------------------
  TOTAL                         1838.9ms
```

### Output Files

Modified trees are saved to the `result/` folder with versioning:

```
result/
├── travel_memory_10day_themed_v1.xml    # After first modification
├── travel_memory_10day_themed_v2.xml    # After second modification
├── travel_memory_10day_themed_versions.json  # Version history
└── ...
```

### CRUD Usage

```python
from pipeline import SemanticXPathPipeline

pipeline = SemanticXPathPipeline()

# Read operation
result = pipeline.process_request("find museums in the itinerary")
# Displays: Read(/Itinerary/Day/POI[atom(content =~ "museum")])

# Delete operation
result = pipeline.process_request("delete all the museums")
# Displays: Delete(/Itinerary/Day/POI[atom(content =~ "museum")])
# Saves: result/travel_memory_v1.xml

# Update operation
result = pipeline.process_request("change the CN Tower visit to 2pm")
# Displays: Update(/Itinerary/Day/POI[atom(content =~ "CN Tower")])
# Saves: result/travel_memory_v2.xml

# Update with type change (POI → Restaurant)
result = pipeline.process_request("change the museum to Chinese food")
# Displays: Update(/Itinerary/Day/POI[atom(content =~ "museum")])
# The content updater detects the semantic shift and changes <POI> to <Restaurant>
# Saves: result/travel_memory_v3.xml

# Create operation
result = pipeline.process_request("add a sushi restaurant after lunch on day 1")
# Displays: Create(/Itinerary/Day[@index='1']/Restaurant)
# Saves: result/travel_memory_v4.xml
```

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

Following the paper formalization, we define recursive predicate scoring `Score(u, ψ)`:

#### 1. atom() - Atomic Predicate (Local Semantic Match)

Scores the node's **own content only**. Does not look at children.

```
POI[atom(content =~ "museum")]

Atom(u, φ) = Scorer(attr(u), φ)  where attr(u) = node's text content
```

#### 2. agg_exists() - Existential Aggregation (Max)

"At least one child matches" - high score if ANY child has high score.

```
Day[agg_exists(POI[atom(content =~ "museum")])]

Score(u, ψ) = Agg∃({Score(c, ψ') | c ∈ children(u)}) = max(...)
```

**Example**: Children with scores [0.95, 0.1, 0.05]
```
agg_exists() = max(0.95, 0.1, 0.05) = 0.95
```

#### 3. agg_prev() - Prevalence Aggregation (Average)

"Children are generally X" - average of child scores.

```
Day[agg_prev(POI[atom(content =~ "artistic")])]

Score(u, ψ) = Aggprev({Score(c, ψ') | c ∈ children(u)}) = mean(...)
```

**Example**: Children with scores [0.8, 0.7, 0.6, 0.3]
```
agg_prev() = (0.8 + 0.7 + 0.6 + 0.3) / 4 = 2.4 / 4 = 0.6
```

### Logical Operators

#### AND (Conjunction - Product)

```
atom(content =~ "outdoor") AND atom(content =~ "historic")

Score(u, ψ₁ ∧ ψ₂) = Score(u, ψ₁) × Score(u, ψ₂)
```

#### OR (Disjunction - Max)

```
atom(content =~ "museum") OR atom(content =~ "gallery")

Score(u, ψ₁ ∨ ψ₂) = max(Score(u, ψ₁), Score(u, ψ₂))
```

### Score Fusion Across Steps

For multi-step queries, scores are multiplied:

```
Query: /Day[agg_prev(...)]/POI[atom(...)]

For each final POI node u:
  Final Score = ∏_{steps with predicates} Score(u, ψ_i)
```

This ensures:
- High parent score + high child score → high final score
- Low parent score penalizes even high-scoring children
- Simple and interpretable score combination

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
/Itinerary/Day/POI[atom(content =~ "museum")]

# Existential (any child matches)
/Itinerary/Day[agg_exists(POI[atom(content =~ "museum")])]

# Prevalence (children generally match)
/Itinerary/Day[agg_prev(POI[atom(content =~ "artistic")])]

# Logical operators
/Itinerary/Day/POI[atom(content =~ "outdoor") AND atom(content =~ "free")]
/Itinerary/Day/POI[atom(content =~ "museum") OR atom(content =~ "gallery")]

# Aggregation-level AND/OR
/Itinerary/Day[agg_exists(POI[atom(content =~ "museum")]) AND agg_exists(Restaurant[atom(content =~ "italian")])]
```

---

## Predicate Types

### Decision Guide

| Query Intent | Predicate | Example |
|--------------|-----------|---------|
| Property of the node itself | `atom()` | "museum POI" → `POI[atom(...)]` |
| Any child has property X | `agg_exists()` | "day with a museum" → `Day[agg_exists(POI[...])]` |
| Children are generally X | `agg_prev()` | "artistic day" → `Day[agg_prev(POI[...])]` |

### Comparison

```
Day with 5 POIs: [Museum: 0.95, Park: 0.1, Mall: 0.05, Theater: 0.1, Cafe: 0.02]

agg_exists(POI[atom(content =~ "museum")]): 0.95 (max - museum exists)
agg_prev(POI[atom(content =~ "museum")]):   0.244 (avg - most aren't museums)
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

When scoring `Day[agg_prev(POI[...])]`:
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

### Interactive Mode (CRUD Operations)

```bash
python -m pipeline.semantic_xpath_pipeline
```

```
============================================================
Semantic XPath Pipeline - CRUD Operations
============================================================
Commands:
  - Natural language query for CRUD operations
  - 'stats' - Session statistics
  - 'reload' - Reload tree from file
  - 'exit' or 'quit' - Exit
============================================================

🔄 Query: find museums in the itinerary

📋 Read(/Itinerary/Day/POI[atom(content =~ "museum")])

⏱️  Step Timing:
---------------------------------------------
  Intent Classification          412.3ms  ████░░░░░░░░░░░░░░░░  22.1%
  XPath Generation               523.1ms  ██████░░░░░░░░░░░░░░  28.0%
  Semantic XPath Execution       245.6ms  ███░░░░░░░░░░░░░░░░░  13.2%
  LLM Node Reasoning             685.2ms  ████████░░░░░░░░░░░░  36.7%
---------------------------------------------
  TOTAL                         1866.2ms

✅ READ Operation Succeeded
============================================================
⏱️  Time: 1872.4ms

📊 Results: 2 selected from 6 candidates

📋 Selected Nodes:
--------------------------------------------------

[1] POI: Royal Ontario Museum
    📝 World-renowned museum showcasing art, culture, and natural history.
    🕐 11:00 AM - 1:00 PM

[2] POI: Art Gallery of Ontario
    📝 Explore Canadian, European, and contemporary art in a Frank Gehry-designed building.
    🕐 2:30 PM - 4:00 PM
============================================================
```

### Programmatic Usage

```python
# Full CRUD Pipeline
from pipeline import SemanticXPathPipeline

pipeline = SemanticXPathPipeline(
    scoring_method="entailment",
    top_k=10,
    score_threshold=0.3
)

# Any CRUD operation via natural language
result = pipeline.process_request("delete all the museums")
print(pipeline.format_result(result))

# Direct XPath execution (read-only)
from dense_xpath import DenseXPathExecutor

executor = DenseXPathExecutor(
    schema_name="itinerary",
    scoring_method="entailment",
    top_k=5,
    score_threshold=0.3
)

# Simple semantic query
result = executor.execute('/Itinerary/Day/POI[atom(content =~ "museum")]')

# Hierarchical query with aggregation
result = executor.execute(
    '/Itinerary/Day[agg_prev(POI[atom(content =~ "artistic")])]/POI[atom(content =~ "museum")]'
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

# Single query mode (non-interactive)
python -m pipeline.semantic_xpath_pipeline -q "find museums"
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
│   └── semantic_xpath_pipeline.py   # Main entry point (CRUD pipeline)
├── crud/
│   └── crud_executor.py             # CRUD operation orchestrator
├── intent_classifier/
│   ├── base.py                      # IntentType enum, ClassifiedIntent
│   └── intent_classifier.py         # LLM-based intent classification
├── reasoner/
│   ├── base.py                      # ReasonerDecision, InsertionPoint
│   ├── node_reasoner.py             # Batched LLM node selection
│   └── insertion_reasoner.py        # Find insertion points for Create
├── tree_modification/
│   ├── base.py                      # OperationResult, path utilities
│   ├── node_deleter.py              # Delete nodes by path
│   ├── node_inserter.py             # Insert/replace nodes
│   └── version_manager.py           # Versioned tree saves
├── content_creator/
│   ├── base.py                      # ContentGenerationResult
│   ├── node_creator.py              # LLM content generation
│   └── node_updater.py              # LLM content updates
├── xpath_query_generation/
│   └── xpath_query_generator.py     # NL → Semantic XPath (LLM)
├── dense_xpath/
│   ├── dense_xpath_executor.py      # Main executor with score fusion
│   ├── models.py                    # AtomicPredicate, CompoundPredicate, etc.
│   ├── parser.py                    # Query parser (atom/agg_exists/agg_prev/AND/OR)
│   ├── predicate_handler.py         # Scoring + aggregation logic
│   ├── node_utils.py                # XML node utilities
│   ├── schema_loader.py             # Schema loading
│   └── trace_writer.py              # Execution + CRUD traces
├── predicate_classifier/
│   ├── llm_scorer.py                # GPT-4 scoring
│   ├── entailment_scorer.py         # BART NLI scoring
│   └── cosine_scorer.py             # Embedding similarity
├── storage/
│   ├── schemas/                     # Schema definitions
│   ├── memory/                      # XML data files
│   └── prompts/                     # All LLM prompts
│       ├── intent_classifier.txt
│       ├── node_reasoner.txt
│       ├── insertion_reasoner.txt
│       ├── content_creator.txt
│       ├── content_updater.txt
│       └── xpath_query_generator_*.txt
├── result/                          # Modified trees (versioned)
├── traces/                          # Execution logs and traces
│   ├── log/
│   └── reasoning_traces/
├── config.yaml
├── framework.md                     # Mathematical specification
└── README.md
```

---

## Quick Reference

### CRUD Operations

| Operation | Natural Language Example | Full Query |
|-----------|-------------------------|------------|
| **Read** | "find museums" | `Read(/Itinerary/Day/POI[atom(...)])` |
| **Create** | "add a cafe on day 1" | `Create(/Itinerary/Day[@index='1']/Restaurant)` |
| **Update** | "change CN Tower to 2pm" | `Update(/Itinerary/Day/POI[atom(...)])` |
| **Update** | "change museum to Chinese food" | Updates content and changes `<POI>` → `<Restaurant>` |
| **Delete** | "remove all museums" | `Delete(/Itinerary/Day/POI[atom(...)])` |

### Predicate Syntax

| Predicate | Syntax | Use When |
|-----------|--------|----------|
| `atom()` | `atom(content =~ "X")` | Matching node's own content |
| `agg_exists()` | `agg_exists(Child[atom(...)])` | Any child has property |
| `agg_prev()` | `agg_prev(Child[atom(...)])` | Children generally have property |

### Aggregation Formulas

| Operator | Formula | Interpretation |
|----------|---------|----------------|
| `atom()` | `Atom(u, φ) = Scorer(attr(u), φ)` | Local score |
| `agg_exists()` | `Agg∃(A) = max(A)` | Max over children |
| `agg_prev()` | `Aggprev(A) = mean(A)` | Average over children |
| `AND` | `Score(u, ψ₁ ∧ ψ₂) = ∏` | Product of scores |
| `OR` | `Score(u, ψ₁ ∨ ψ₂) = max` | Max of scores |

### Example Queries

```xpath
# Find museums
/Itinerary/Day/POI[atom(content =~ "museum")]

# Find days with museums
/Itinerary/Day[agg_exists(POI[atom(content =~ "museum")])]

# Find artistic days
/Itinerary/Day[agg_prev(POI[atom(content =~ "artistic")])]

# Find museums in artistic days
/Itinerary/Day[agg_prev(POI[atom(content =~ "artistic")])]/POI[atom(content =~ "museum")]

# Days with both museum AND Italian restaurant
/Itinerary/Day[agg_exists(POI[atom(content =~ "museum")]) AND agg_exists(Restaurant[atom(content =~ "italian")])]
```

### CRUD Pipeline Components

| Component | Purpose |
|-----------|---------|
| `IntentClassifier` | Classify NL → CREATE/READ/UPDATE/DELETE |
| `NodeReasoner` | LLM selects relevant nodes from candidates |
| `InsertionReasoner` | LLM finds best insertion point |
| `NodeCreator` | LLM generates new node content |
| `NodeUpdater` | LLM modifies existing content (can change node type, e.g., POI → Restaurant) |
| `NodeDeleter` | Remove nodes by path |
| `VersionManager` | Save versioned trees to `result/` |

---

## License

MIT License
