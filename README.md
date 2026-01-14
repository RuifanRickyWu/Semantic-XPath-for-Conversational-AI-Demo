# Semantic XPath: A Probabilistic Hierarchical Retrieval Framework

A natural language to XPath-like query system for structured hierarchical data. Convert plain English requests into executable queries against XML trees with **probabilistic semantic matching**, **Bayesian score fusion**, and **hierarchical quantifiers**.

## Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌─────────────┐
│  User Request   │────▶│  Query Generator │────▶│  XPath Executor  │────▶│   Results   │
│  (Natural Lang) │     │      (LLM)       │     │  (Probabilistic) │     │  (Ranked)   │
└─────────────────┘     └──────────────────┘     └──────────────────┘     └─────────────┘
     "find days                                                              [Day 1: 0.92
    with museums"        /Itinerary/Day                                      Day 2: 0.87]
                        [exists(description =~ "museum")]
```

## Key Features

- **Semantic Predicates**: Match nodes by meaning, not just exact text
- **Compound Predicates**: Combine conditions with `AND` / `OR`
- **Hierarchical Quantifiers**: `exists()` and `all()` for parent-child relationships
- **Bayesian Fusion**: Principled score aggregation across query steps
- **Multiple Scoring Methods**: LLM, NLI Entailment, or Cosine Similarity
- **Multi-Schema Support**: Itinerary, TodoList, Curriculum, Support, Recommendations

---

## Table of Contents

1. [Theoretical Foundation](#theoretical-foundation)
2. [Project Structure](#project-structure)
3. [Query Syntax Reference](#query-syntax-reference)
4. [Predicate Operators](#predicate-operators)
5. [Hierarchical Quantifiers](#hierarchical-quantifiers)
6. [Bayesian Score Fusion](#bayesian-score-fusion)
7. [Scoring Methods](#scoring-methods)
8. [Schema System](#schema-system)
9. [Usage](#usage)
10. [Execution Traces](#execution-traces)
11. [Configuration](#configuration)
12. [Installation](#installation)
13. [Architecture](#architecture)

---

## Theoretical Foundation

The framework extends classical XPath with **probabilistic inference** while preserving stepwise structural semantics.

### Data Model

Structured data is represented as a rooted tree `T = (V, E, r)`:
- `V`: set of nodes
- `E`: set of edges
- `r`: root node

Each node `v ∈ V` has a type `κ(v)` (e.g., *Day*, *POI*, *Restaurant*).

### Query Execution Model

A Semantic XPath query is a sequence of steps: `Q = <q₁, q₂, ..., qₙ>`

Each step applies:
```
Cᵢ = Select_ι( Filter_p( Expand_κ(Cᵢ₋₁) ) )
```

Where:
- `Expand_κ`: Find children of target type
- `Filter_p`: Apply semantic predicate scoring
- `Select_ι`: Apply positional constraints

### Probabilistic Semantics

For each semantic predicate, we compute a **posterior probability**:

```
π_v(c) = Pr(Z_v(c) = 1 | X_v)
```

Where:
- `Z_v(c)`: Indicator that node `v` satisfies condition `c`
- `X_v`: Textual content of node `v`

---

## Project Structure

```
LLM-VM/
├── pipeline/
│   └── semantic_xpath_pipeline.py   # Main entry point & orchestration
├── xpath_query_generation/
│   └── xpath_query_generator.py     # NL → XPath query (LLM-based)
├── dense_xpath/
│   ├── dense_xpath_executor.py      # Main executor with Bayesian fusion
│   ├── models.py                    # Data classes (QueryStep, CompoundPredicate, etc.)
│   ├── parser.py                    # XPath query string parser (supports AND/OR/exists/all)
│   ├── index_handler.py             # Positional indexing logic
│   ├── predicate_handler.py         # Semantic predicate scoring with batch optimization
│   ├── node_utils.py                # XML node utilities
│   ├── schema_loader.py             # Schema and data file loading
│   └── trace_writer.py              # Detailed execution trace logging
├── predicate_classifier/
│   ├── base.py                      # PredicateScorer abstract interface
│   ├── llm_scorer.py                # GPT-4 based scoring
│   ├── entailment_scorer.py         # BART NLI entailment scoring
│   └── cosine_scorer.py             # TAS-B embedding similarity
├── client/
│   ├── openai_client.py             # OpenAI API wrapper
│   ├── bart_client.py               # BART NLI model client
│   └── tas_b_client.py              # TAS-B embedding client
├── storage/
│   ├── schemas/                     # Tree schema definitions (5 schemas)
│   ├── memory/                      # XML data files
│   └── prompts/                     # XPath generation prompts (per schema)
├── traces/                          # Execution & scoring traces
│   ├── log/
│   └── reasoning_traces/
├── config.yaml                      # Configuration
├── framework.md                     # Mathematical framework specification
└── README.md
```

---

## Query Syntax Reference

### Basic Path Navigation

```xpath
/Itinerary/Day/POI                    # All POIs in all Days
/Itinerary/Day[1]/POI                 # All POIs in first Day
/Itinerary/Day/POI[2]                 # Second POI in each Day (local)
(/Itinerary/Day/POI)[2]               # Second POI overall (global)
```

### Positional Indexing

| Syntax | Meaning | Example |
|--------|---------|---------|
| `[1]` | First element | `POI[1]` |
| `[2]` | Second element | `POI[2]` |
| `[-1]` | Last element | `POI[-1]` |
| `[1:3]` | Elements 1, 2, 3 | `POI[1:3]` |
| `[-2:]` | Last 2 elements | `POI[-2:]` |

### Local vs Global Indexing

| Syntax | Scope | Result |
|--------|-------|--------|
| `/Day/POI[2]` | Local (per parent) | 2nd POI in EACH Day |
| `(/Day/POI)[2]` | Global (flattened) | 2nd POI overall |

### Semantic Predicates

```xpath
/Itinerary/Day/POI[description =~ "museum"]
/Itinerary/Day[description =~ "artistic"]/Restaurant
```

---

## Predicate Operators

### Simple Predicate

```xpath
POI[description =~ "museum"]
```

Scores the node's description against "museum" using the configured scorer.

### AND (Conjunction)

```xpath
POI[description =~ "outdoor" AND description =~ "historic"]
```

**Scoring Formula** (Log-odds aggregation):
```
ℓ_v(p) = Σⱼ log( π_v(cⱼ) / (1 - π_v(cⱼ)) )
π_v(p) = sigmoid(ℓ_v(p))
```

**Interpretation**: Node must satisfy BOTH conditions. Scores are combined in log-odds space, then converted back to probability.

**Example**:
```
Node: "Historic waterfront park with nature trails"
  - P(outdoor) = 0.85
  - P(historic) = 0.78
  
Log-odds:
  - log(0.85/0.15) = 1.735
  - log(0.78/0.22) = 1.265
  - Sum = 3.0
  
Final: sigmoid(3.0) = 0.953
```

### OR (Disjunction)

```xpath
Restaurant[description =~ "italian" OR description =~ "french"]
```

**Scoring Formula** (Noisy-OR):
```
π_v(p) = 1 - ∏ⱼ (1 - π_v(cⱼ))
```

**Interpretation**: Node satisfies AT LEAST ONE condition. High score if any condition matches.

**Example**:
```
Node: "Authentic Italian trattoria"
  - P(italian) = 0.92
  - P(french) = 0.15
  
Noisy-OR: 1 - (1-0.92)(1-0.15) = 1 - 0.068 = 0.932
```

### Combined Operators

```xpath
POI[(description =~ "outdoor" OR description =~ "nature") AND description =~ "family"]
```

Operators follow standard precedence: parentheses > AND > OR.

---

## Hierarchical Quantifiers

For **internal nodes** (non-leaf nodes like `Day`), predicates are evaluated over their children using explicit quantifiers.

### exists() - Existential Quantifier

```xpath
/Itinerary/Day[exists(description =~ "museum")]
```

**Meaning**: Day has **at least one child** (POI or Restaurant) related to "museum".

**Scoring Formula** (Noisy-OR over children):
```
π_v(p) = 1 - ∏_{u ∈ children(v)} (1 - π_u(p))
```

**Example**:
```
Day 1 children:
  - St. Lawrence Market: P(museum) = 0.05
  - CN Tower: P(museum) = 0.08
  - Art Gallery of Ontario: P(museum) = 0.99
  
exists() score: 1 - (0.95)(0.92)(0.01) = 0.991
```

**Use Cases**:
- "Days that have a museum" → `Day[exists(description =~ "museum")]`
- "Days with any Italian option" → `Day[exists(description =~ "italian")]`
- "Projects with at least one urgent task" → `Project[exists(description =~ "urgent")]`

### all() - Universal/Prevalence Quantifier

```xpath
/Itinerary/Day[all(description =~ "outdoor")]
```

**Meaning**: Day's children are **generally/mostly** outdoor-focused.

**Scoring Formula** (Beta-Bernoulli posterior mean):
```
π_v(p) = (α + Σ_{u ∈ children(v)} π_u(p)) / (α + β + |children(v)|)
```

Where `α = 1, β = 1` (uniform prior).

**Example**:
```
Day 3 children (6 total):
  - Toronto Islands: P(outdoor) = 0.95
  - Beach Boardwalk: P(outdoor) = 0.88
  - Harbourfront: P(outdoor) = 0.72
  - Seafood Restaurant: P(outdoor) = 0.45
  - Cafe: P(outdoor) = 0.30
  - Park: P(outdoor) = 0.85
  
Sum of scores: 4.15
all() score: (1 + 4.15) / (1 + 1 + 6) = 5.15 / 8 = 0.644
```

**Use Cases**:
- "Days focused on outdoor activities" → `Day[all(description =~ "outdoor")]`
- "Courses with generally practical content" → `Course[all(description =~ "practical")]`
- "Projects where tasks are mostly completed" → `Project[all(description =~ "completed")]`

### Key Differences

| Quantifier | Question It Answers | High Score When |
|------------|---------------------|-----------------|
| `exists()` | "Does any child match?" | At least one child has high score |
| `all()` | "Do children generally match?" | Most/all children have moderate-high scores |

**Example Comparison**:
```
Day with 5 POIs:
  - Museum (P=0.95), Park (P=0.1), Mall (P=0.05), Theater (P=0.1), Restaurant (P=0.02)

exists(description =~ "museum"): 0.95 (high - museum exists)
all(description =~ "museum"): (1 + 1.22) / 7 = 0.317 (low - most are not museums)
```

---

## Bayesian Score Fusion

When a query has **multiple predicate steps**, scores are combined using **Bayesian fusion**.

### The Problem

Consider this query:
```xpath
/Itinerary/Day[description =~ "cultural"]/POI[description =~ "museum"]
```

A POI's final relevance depends on:
1. Its parent Day's "cultural" score
2. Its own "museum" score

### The Solution: Log-Odds Accumulation

For each node `u`, we define a latent relevance variable with prior `P(Z_u = 1) = 0.5`.

Each predicate step contributes evidence:
```
ℓ(u) = Σᵢ log( πᵢ(u) / (1 - πᵢ(u)) )
```

Final score:
```
Score(u, Q) = sigmoid(ℓ(u))
```

### Example

```xpath
/Itinerary/Day[description =~ "cultural"]/POI[description =~ "historic"]
```

For "Art Gallery of Ontario" in Day 1:
```
Step 1 (Day "cultural"): π₁ = 0.85
  - log-odds₁ = log(0.85/0.15) = 1.735

Step 2 (POI "historic"): π₂ = 0.78
  - log-odds₂ = log(0.78/0.22) = 1.265

Accumulated log-odds: 1.735 + 1.265 = 3.0
Final score: sigmoid(3.0) = 0.953
```

### Deferred Filtering

**Important**: Score threshold and top-k filtering are applied **after** Bayesian fusion is complete.

```
Query: /Day[p1]/POI[p2] with top_k=3, threshold=0.5

1. Expand to all Days
2. Score Days with p1 → accumulate log-odds
3. Expand to all POIs
4. Score POIs with p2 → accumulate log-odds
5. Compute final scores via sigmoid
6. NOW apply threshold and top_k filtering
```

This ensures fair comparison across all candidates.

---

## Scoring Methods

Three methods available for computing `π_v(c)`:

### 1. LLM Scoring (`llm`)

Uses GPT-4 to evaluate semantic relevance.

```
Premise: "Art Gallery of Ontario - Explore Canadian and European art..."
Predicate: "museum"
→ Score: 0.95
```

| Pros | Cons |
|------|------|
| Most accurate | Slow |
| Understands nuance | API costs |
| Can reason about context | Rate limits |

### 2. Entailment Scoring (`entailment`)

Uses BART-large-mnli for Natural Language Inference.

```
Premise: "Art Gallery of Ontario - Explore Canadian and European art..."
Hypothesis: "This is related to museum."
→ Entailment probability: 0.87
```

| Pros | Cons |
|------|------|
| Local inference | Less nuanced |
| No API costs | Fixed hypothesis template |
| Fast | Model size ~1.5GB |

### 3. Cosine Similarity (`cosine`)

Uses TAS-B embeddings for semantic similarity.

```
Node embedding: encode("Art Gallery of Ontario...")
Query embedding: encode("museum")
→ Cosine similarity: 0.72
```

| Pros | Cons |
|------|------|
| Fastest | Less accurate |
| Good for keywords | Misses complex relationships |
| Small model | No reasoning |

### Batch Optimization

All scorers use **batch processing** for efficiency:

```python
# For predicate: description =~ "A" AND description =~ "B"
# With 10 nodes to score

# Without batching: 20 scorer calls (10 nodes × 2 predicates)
# With batching: 2 scorer calls (1 per unique predicate value)
```

The system collects all scoring tasks first, then batches by predicate value.

---

## Schema System

### Available Schemas

| Schema | Hierarchy | Use Case |
|--------|-----------|----------|
| `itinerary` | Itinerary → Day → POI/Restaurant | Travel planning |
| `todolist` | TodoList → Project → Task → SubTask | Task management |
| `curriculum` | Curriculum → Course → Concept/Exercise | Education |
| `support` | SupportSystem → Customer → Ticket → Symptom/Cause/Resolution | Help desk |
| `session_recommendation` | RecommendationHub → Session → Step → Objective → Item | Shopping/DIY |

### Schema Definition Example

```yaml
# storage/schemas/itinerary.yaml
name: "itinerary"
description: "Travel itinerary with days, POIs and restaurants"

hierarchy: |
  Itinerary (root)
  ├── Day
  │   ├── POI
  │   └── Restaurant

nodes:
  Day:
    type: container
    index_attr: "index"
  POI:
    type: leaf
    name_field: "name"
    description_field: "description"
  Restaurant:
    type: leaf
    name_field: "name"
    description_field: "description"

data_files:
  travel_memory_3day: "memory/travel/travel_memory_3day.xml"
  travel_memory_5day: "memory/travel/travel_memory_5day.xml"

default_data: "travel_memory_3day"
prompt_file: "prompts/xpath_query_generator_itinerary.txt"
```

### Switching Schemas

**Via config.yaml**:
```yaml
active_schema: "itinerary"
active_data: "travel_memory_5day"
```

**Via code**:
```python
from dense_xpath import DenseXPathExecutor

executor = DenseXPathExecutor(
    schema_name="itinerary",
    data_name="travel_memory_5day"
)
```

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
Config: scoring_method=entailment, top_k=5, threshold=0.01

Request: days with museums
Query: /Itinerary/Day[exists(description =~ "museum")]

Matched 3 node(s) (sorted by score):
============================================================

[Result 1] ⭐ Score: 0.9991
📍 Tree Path: Itinerary > Day 2
--------------------------------------------------
Day 2 contains: Royal Ontario Museum, Casa Loma...

[Result 2] ⭐ Score: 0.9929
📍 Tree Path: Itinerary > Day 1
--------------------------------------------------
Day 1 contains: Art Gallery of Ontario...
```

### Command Line Options

```bash
# Use different scoring methods
python -m pipeline.semantic_xpath_pipeline --scoring llm
python -m pipeline.semantic_xpath_pipeline --scoring cosine
python -m pipeline.semantic_xpath_pipeline --scoring entailment

# Custom threshold and top_k
python -m pipeline.semantic_xpath_pipeline --top-k 10 --threshold 0.5
```

### Programmatic Usage

```python
from dense_xpath import DenseXPathExecutor

# Create executor
executor = DenseXPathExecutor(
    schema_name="itinerary",
    data_name="travel_memory_3day",
    scoring_method="entailment",
    top_k=5,
    score_threshold=0.3
)

# Simple semantic query
result = executor.execute('/Itinerary/Day/POI[description =~ "museum"]')
for node in result.matched_nodes:
    print(f"- {node.tree_path}: {node.score:.3f}")

# Compound predicate with AND
result = executor.execute(
    '/Itinerary/Day/POI[description =~ "outdoor" AND description =~ "historic"]'
)

# Hierarchical quantifier
result = executor.execute(
    '/Itinerary/Day[exists(description =~ "museum")]/POI'
)

# Multi-step with Bayesian fusion
result = executor.execute(
    '/Itinerary/Day[description =~ "cultural"]/POI[description =~ "art"]'
)
```

### Example Queries by Schema

**Itinerary**:
```xpath
/Itinerary/Day[exists(description =~ "museum")]
/Itinerary/Day[all(description =~ "outdoor")]/POI
/Itinerary/Day/POI[description =~ "historic" AND description =~ "free"]
/Itinerary/Day/Restaurant[description =~ "italian" OR description =~ "french"]
```

**TodoList**:
```xpath
/TodoList/Project[exists(description =~ "urgent")]/Task
/TodoList/Project[all(description =~ "completed")]
/TodoList/Project/Task[description =~ "backend" AND description =~ "critical"]
```

**Curriculum**:
```xpath
/Curriculum/Course[exists(description =~ "machine learning")]/Concept
/Curriculum/Course[all(description =~ "practical")]/Exercise
/Curriculum/Course/Concept[description =~ "neural" AND description =~ "advanced"]
```

---

## Execution Traces

All executions generate detailed traces in `traces/reasoning_traces/`.

### Trace Contents

```json
{
  "query": "/Itinerary/Day[exists(description =~ \"museum\")]",
  "scoring_traces": [
    {
      "step_index": 1,
      "predicate": "exists(description =~ \"museum\")",
      "node_scores": [
        {
          "node_name": "Day 1",
          "final_score": 0.9929,
          "scoring_steps": [
            {
              "type": "exists_quantifier",
              "child_type": "*",
              "num_children": 6,
              "child_scores": [0.01, 0.02, 0.002, 0.99, 0.004, 0.002],
              "result": 0.9929
            }
          ]
        }
      ]
    }
  ],
  "bayesian_fusion_trace": {
    "total_nodes_fused": 3,
    "node_details": [
      {
        "node_name": "Day 1",
        "accumulated_log_odds": 4.95,
        "final_score": 0.9929,
        "step_contributions": [
          {"step_index": 1, "predicate": "exists(...)", "score": 0.9929, "log_odds": 4.95}
        ]
      }
    ]
  },
  "final_filtering_trace": {
    "threshold": 0.01,
    "top_k": 5,
    "nodes_before_filter": 3,
    "nodes_after_filter": 3
  }
}
```

### Viewing Traces

```python
import json

with open('traces/reasoning_traces/execution_20260114_110248.json') as f:
    trace = json.load(f)
    
# View scoring breakdown
for node_score in trace['scoring_traces'][0]['node_scores']:
    print(f"{node_score['node_name']}: {node_score['final_score']:.4f}")
    for step in node_score['scoring_steps']:
        print(f"  - {step['type']}: {step.get('result', step.get('score'))}")
```

---

## Configuration

Edit `config.yaml`:

```yaml
# Schema and data file selection
active_schema: "itinerary"
active_data: "travel_memory_3day"

# OpenAI settings (for LLM scoring and query generation)
openai:
  api_key: "your-api-key"
  model: "gpt-4o"

# XPath executor settings
xpath_executor:
  top_k: 5                      # Max nodes to return
  score_threshold: 0.01         # Min score for semantic matches
  scoring_method: "entailment"  # "llm", "entailment", or "cosine"

# Entailment scorer settings
entailment:
  model: "facebook/bart-large-mnli"
  hypothesis_template: "This is related to {predicate}."

# Cosine scorer settings
cosine:
  model: "sentence-transformers/msmarco-distilbert-base-tas-b"
  predicate_template: "{predicate}"
```

---

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd LLM-VM

# Install dependencies
pip install -r requirements.txt

# Set up your OpenAI API key in config.yaml (for LLM scoring/query generation)
```

### Requirements

```
openai>=1.0.0
pyyaml
torch
transformers
numpy
sentence-transformers
```

---

## Architecture

```
                         ┌─────────────────────────────────────────────────┐
                         │              SemanticXPathPipeline              │
                         │  - Orchestrates query generation & execution    │
                         │  - Formats results for display                  │
                         └───────────────────┬─────────────────────────────┘
                                             │
              ┌──────────────────────────────┼──────────────────────────────┐
              │                              │                              │
              ▼                              ▼                              ▼
┌─────────────────────────┐    ┌─────────────────────────┐    ┌─────────────────────────┐
│   XPathQueryGenerator   │    │   DenseXPathExecutor    │    │     PredicateScorer     │
│                         │    │                         │    │      (Interface)        │
│  NL → XPath Query       │    │  • BFS traversal        │    │                         │
│  (LLM-based)            │    │  • Bayesian fusion      │    │  - LLMPredicateScorer   │
│                         │    │  • Deferred filtering   │    │  - EntailmentScorer     │
└─────────────────────────┘    │  • Trace generation     │    │  - CosineScorer         │
                               └───────────┬─────────────┘    └─────────────────────────┘
                                           │
                    ┌──────────────────────┼────────────────────────┐
                    │                      │                        │
                    ▼                      ▼                        ▼
          ┌─────────────────┐    ┌─────────────────┐      ┌─────────────────┐
          │   QueryParser   │    │  IndexHandler   │      │PredicateHandler │
          │                 │    │                 │      │                 │
          │ Parse XPath     │    │ Local/Global    │      │ • AND/OR logic  │
          │ • AND/OR        │    │ indexing        │      │ • exists()/all()│
          │ • exists/all    │    │ [1], [-1]       │      │ • Batch scoring │
          │ • CompoundPred  │    │ [1:3], [-2:]    │      │ • Score caching │
          └─────────────────┘    └─────────────────┘      └─────────────────┘
```

### End-to-End Flow

```
1. User Input: "days that have museums"
                    │
                    ▼
2. Query Generation (LLM)
   → /Itinerary/Day[exists(description =~ "museum")]
                    │
                    ▼
3. Query Parsing
   → Steps: [Itinerary, Day[exists(...)]]
   → CompoundPredicate AST: EXISTS(ATOMIC("museum"))
                    │
                    ▼
4. BFS Traversal
   Step 0: Match root → [Itinerary]
   Step 1: Expand to Day → [Day1, Day2, Day3]
                    │
                    ▼
5. Predicate Scoring (Batch)
   Collect all children descriptions
   Single batch call for "museum"
   Cache results per node
                    │
                    ▼
6. Hierarchical Quantification
   For each Day: exists() = Noisy-OR over children
   Day1: 0.9929, Day2: 0.9991, Day3: 0.0344
                    │
                    ▼
7. Bayesian Fusion
   Convert scores to log-odds
   Accumulate across steps
   Convert back via sigmoid
                    │
                    ▼
8. Deferred Filtering
   Apply threshold (0.01)
   Apply top_k (5)
   Sort by final score
                    │
                    ▼
9. Result Output
   [Day2: 0.9991, Day1: 0.9929, Day3: 0.0344]
```

---

## Quick Reference

### Predicate Operators

| Operator | Syntax | Formula | Use Case |
|----------|--------|---------|----------|
| Simple | `description =~ "X"` | π(X) | Single condition |
| AND | `... AND ...` | sigmoid(Σ log-odds) | Must match all |
| OR | `... OR ...` | 1 - ∏(1-π) | Match any one |

### Hierarchical Quantifiers

| Quantifier | Syntax | Formula | Use Case |
|------------|--------|---------|----------|
| exists | `exists(pred)` | 1 - ∏(1-π_child) | Any child matches |
| all | `all(pred)` | (α + Σπ)/(α+β+n) | Children generally match |

### Scoring Methods

| Method | Speed | Accuracy | Cost |
|--------|-------|----------|------|
| `llm` | Slow | Highest | $$$ |
| `entailment` | Medium | High | Free |
| `cosine` | Fast | Good | Free |

---

## License

MIT License
