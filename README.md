# Semantic XPath Query System

A natural language to XPath-like query system for structured itinerary data. Convert plain English requests into executable queries against an XML tree with semantic matching capabilities.

## Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌─────────────┐
│  User Request   │────▶│  Query Generator │────▶│  XPath Executor  │────▶│   Results   │
│  (Natural Lang) │     │      (LLM)       │     │  (BFS + Scoring) │     │  (Matched)  │
└─────────────────┘     └──────────────────┘     └──────────────────┘     └─────────────┘
     "find all                                                              [POI, POI,
    jazz venues"      /Itinerary/Day/POI                                   Restaurant]
                      [description =~ "jazz"]
```

## Project Structure

```
LLM-VM/
├── pipeline/
│   └── semantic_xpath_pipeline.py   # Main entry point & orchestration
├── xpath_query_generation/
│   └── xpath_query_generator.py     # NL → XPath query (LLM-based)
├── dense_xpath/
│   ├── dense_xpath_executor.py      # Main executor orchestrator
│   ├── models.py                    # Data classes (QueryStep, MatchedNode, etc.)
│   ├── parser.py                    # XPath query string parser
│   ├── index_handler.py             # Positional indexing logic
│   ├── predicate_handler.py         # Semantic predicate scoring
│   ├── node_utils.py                # XML node utilities (dynamic, schema-agnostic)
│   ├── schema_loader.py             # Schema and data file loading
│   └── trace_writer.py              # Execution trace logging
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
│   ├── schemas/                     # Tree schema definitions
│   │   └── itinerary.yaml           # Itinerary schema (Day/POI/Restaurant)
│   ├── memory/                      # XML data files
│   │   ├── travel_memory_3day.xml   # 3-day Toronto itinerary
│   │   └── travel_memory_5day.xml   # 5-day Toronto itinerary
│   └── prompts/
│       └── xpath_query_generator.txt
├── traces/                          # Execution & scoring traces
│   ├── log/
│   └── reasoning_traces/
└── config.yaml                      # Configuration (schema, data, scoring)
```

---

## Schema System

The system uses a **schema-based architecture** that supports multiple tree structures and data files.

### Schema Configuration

Each schema defines:
- Tree hierarchy (node types and relationships)
- Available data files
- Field mappings (name, description fields)

**Example schema (`storage/schemas/itinerary.yaml`):**
```yaml
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
  travel_memory_3day: "memory/travel_memory_3day.xml"
  travel_memory_5day: "memory/travel_memory_5day.xml"

default_data: "travel_memory_3day"
```

### Switching Data Files

**Method 1: Via config.yaml**
```yaml
active_schema: "itinerary"
active_data: "travel_memory_5day"  # Switch to 5-day itinerary
```

**Method 2: Via code**
```python
from dense_xpath import DenseXPathExecutor

# Use 3-day itinerary
executor_3day = DenseXPathExecutor(data_name="travel_memory_3day")

# Use 5-day itinerary
executor_5day = DenseXPathExecutor(data_name="travel_memory_5day")
```

**Method 3: Query available options**
```python
from dense_xpath import list_available_data_files, get_schema_info

print(list_available_data_files())
# ['travel_memory_3day', 'travel_memory_5day']

print(get_schema_info())
# {'schema_name': 'itinerary', 'active_data': 'travel_memory_3day', ...}
```

---

## Data Model: Itinerary Tree

```
Itinerary (root)
├── Day[1]
│   ├── POI: St. Lawrence Market
│   ├── POI: CN Tower
│   ├── Restaurant: Queen Street Warehouse
│   ├── POI: Art Gallery of Ontario
│   ├── Restaurant: Buca Yorkville
│   └── Restaurant: The Rex Hotel Jazz Bar
├── Day[2]
│   ├── Restaurant: Pow Wow Cafe
│   ├── POI: Royal Ontario Museum
│   └── ...
├── Day[3]
│   └── ...
├── Day[4] (5-day version only)
│   └── ...
└── Day[5] (5-day version only)
    └── ...
```

**Node Types:**
- `Itinerary` - Root node
- `Day` - Contains POIs and Restaurants (has `index` attribute)
- `POI` - Points of Interest (museums, towers, markets, etc.)
- `Restaurant` - Dining locations

**Important:** POI and Restaurant are **siblings** (same level under Day), NOT parent-child.

---

## End-to-End Flow

### Step 1: Natural Language → XPath Query

The `XPathQueryGenerator` uses an LLM (GPT-4) to convert user requests into structured XPath-like queries.

```
User: "find all jazz venues"
     ↓ LLM
Query: /Itinerary/Day/POI[description =~ "jazz"]
```

### Step 2: Query Parsing

The `QueryParser` breaks down the query string into structured `QueryStep` objects:

```python
# Query: /Itinerary/Day[description =~ "artistic"]/POI[2]
steps = [
    QueryStep(node_type="Itinerary"),
    QueryStep(node_type="Day", predicate="artistic"),
    QueryStep(node_type="POI", index=IndexRange(start=2))
]
```

### Step 3: BFS Traversal & Execution

The `DenseXPathExecutor` traverses the XML tree step by step:

```
Step 1: Match root "Itinerary"
        → [Itinerary node]

Step 2: Find all "Day" children
        → [Day 1, Day 2, Day 3]
        
Step 3: Apply semantic predicate "artistic"
        → Score each Day, filter by threshold
        → [Day 1 (score: 0.85)]

Step 4: Find "POI" children of matched Days
        → [POI 1, POI 2, POI 3]

Step 5: Apply positional index [2]
        → [POI 2]
```

### Step 4: Semantic Scoring

Three scoring methods available:

| Method | Model | Speed | Accuracy |
|--------|-------|-------|----------|
| `llm` | GPT-4 | Slow | Highest |
| `entailment` | BART NLI | Medium | High |
| `cosine` | TAS-B | Fast | Good |

### Step 5: Result Formatting

```
Query: /Itinerary/Day/POI[description =~ "jazz"]

Matched 2 node(s) (sorted by score):
============================================================

[Result 1] ⭐ Score: 0.920
📍 Tree Path: Itinerary > Day 1 > The Rex Hotel Jazz Bar
--------------------------------------------------
🏷️  Restaurant: The Rex Hotel Jazz & Blues Bar
📝 Live jazz performances in a cozy, iconic Toronto venue.
🕐 8:00 PM - 10:30 PM

[Result 2] ⭐ Score: 0.875
📍 Tree Path: Itinerary > Day 2 > Rivoli
--------------------------------------------------
🏷️  POI: Rivoli
📝 Live music venue showcasing jazz, indie, and emerging artists.
🕐 8:00 PM - 10:00 PM
```

---

## The 6 Query Types

The system supports **6 fundamental query types**. Understanding these categories helps you craft effective queries:

| # | Type | Description | Example Query |
|---|------|-------------|---------------|
| 1 | **Global** | Nth item across ALL results | `(/Itinerary/Day/POI)[5]` |
| 2 | **Local** | Nth item within EACH parent | `/Itinerary/Day/POI[2]` |
| 3 | **Syntactic** | Structural path navigation | `/Itinerary/Day[1]/POI[2]` |
| 4 | **Semantic** | Content-based filtering | `Day[description =~ "artistic"]` |
| 5 | **Single** | Find one matching item | `(/Itinerary/Day/POI[description =~ "museum"])[1]` |
| 6 | **Multiple** | Find all matching items | `/Itinerary/Day/POI[description =~ "museum"]` |

---

### Type 1: Global Index

Select by position **across ALL matched nodes** (flattened list).

```
User: "find me the 5th POI"
Query: (/Itinerary/Day/POI)[5]
```

**How it works:**
```
All POIs flattened: [POI1, POI2, POI3, POI4, POI5, POI6, POI7, POI8]
                                             ↑
                                        Select 5th
Result: 1 node (Royal Ontario Museum)
```

**More examples:**
```
User: "the third POI globally"
Query: (/Itinerary/Day/POI)[3]

User: "POIs 2 to 4 globally"  
Query: (/Itinerary/Day/POI)[2:4]

User: "last 2 POIs globally"
Query: (/Itinerary/Day/POI)[-2:]
```

---

### Type 2: Local Index (Per Parent)

Select by position **within EACH parent node** separately.

```
User: "find me the second POI in each day"
Query: /Itinerary/Day/POI[2]
```

**How it works:**
```
Day 1 POIs: [St. Lawrence, CN Tower, Art Gallery] → Select 2nd → CN Tower
Day 2 POIs: [ROM, Casa Loma, Rivoli]              → Select 2nd → Casa Loma  
Day 3 POIs: [Toronto Islands, Distillery]         → Select 2nd → Distillery

Result: 3 nodes (one from each Day)
```

**More examples:**
```
User: "second POI in every day"
Query: /Itinerary/Day/POI[2]
→ Returns: CN Tower, Casa Loma, Distillery District

User: "last restaurant in each day"  
Query: /Itinerary/Day/Restaurant[-1]

User: "first 2 POIs in every day"
Query: /Itinerary/Day/POI[1:2]
```

**Key Difference - Local vs Global:**
```
/Itinerary/Day/POI[2]      → 2nd POI in EACH day (3 results)
(/Itinerary/Day/POI)[2]    → 2nd POI OVERALL (1 result)
```

---

### Type 3: Syntactic (Structural Path)

Navigate using **explicit structural constraints** (specific Day, specific position).

```
User: "find me the second POI in first day"
Query: /Itinerary/Day[1]/POI[2]
```

**How it works:**
```
Step 1: Day[1]  → Select only Day 1
Step 2: POI[2]  → Select 2nd POI within Day 1

Result: 1 node (CN Tower)
```

**More examples:**
```
User: "POI in second day"
Query: /Itinerary/Day[2]/POI

User: "first 3 POIs in day 1"
Query: /Itinerary/Day[1]/POI[1:3]

User: "last restaurant in day 1"
Query: /Itinerary/Day[1]/Restaurant[-1]

User: "all restaurants in the last day"
Query: /Itinerary/Day[-1]/Restaurant
```

---

### Type 4: Semantic (Content-Based)

Filter nodes by **semantic meaning** using `[description =~ "query"]`.

```
User: "find me an artistic day"
Query: /Itinerary/Day[description =~ "artistic"]
```

**How it works:**
```
Score each Day against "artistic":
  Day 1: 0.85 (has Art Gallery) ✓
  Day 2: 0.45 (below threshold) ✗
  Day 3: 0.32 (below threshold) ✗

Result: Day 1 (and all its children)
```

**More examples:**
```
User: "jazz venues"
Query: /Itinerary/Day/POI[description =~ "jazz"]

User: "Italian restaurants"  
Query: /Itinerary/Day/Restaurant[description =~ "italian"]

User: "all restaurants in a cultural day"
Query: /Itinerary/Day[description =~ "cultural"]/Restaurant

User: "museums"
Query: /Itinerary/Day/POI[description =~ "museum"]
```

---

### Type 5: Single Result

Find **one specific item** matching criteria (semantic + global index).

```
User: "find me a museum"
Query: (/Itinerary/Day/POI[description =~ "museum"])[1]
```

**How it works:**
```
Step 1: Find all POIs matching "museum"
        → [ROM, Art Gallery, ...]
Step 2: Global index [1] → Select first one

Result: 1 node (Royal Ontario Museum)
```

**More examples:**
```
User: "a jazz venue"
Query: (/Itinerary/Day/POI[description =~ "jazz"])[1]

User: "an Italian restaurant"
Query: (/Itinerary/Day/Restaurant[description =~ "italian"])[1]

User: "second museum"
Query: (/Itinerary/Day/POI[description =~ "museum"])[2]
```

---

### Type 6: Multiple Results

Find **all items** matching criteria (no index constraint).

```
User: "find me all the museums"
Query: /Itinerary/Day/POI[description =~ "museum"]
```

**How it works:**
```
Score each POI against "museum":
  St. Lawrence Market: 0.12 ✗
  CN Tower: 0.08 ✗
  Art Gallery: 0.92 ✓
  Royal Ontario Museum: 0.95 ✓
  Casa Loma: 0.35 ✗
  ...

Result: All POIs above threshold (Art Gallery, ROM, etc.)
```

**More examples:**
```
User: "all jazz venues"
Query: /Itinerary/Day/POI[description =~ "jazz"]

User: "all Italian restaurants"
Query: /Itinerary/Day/Restaurant[description =~ "italian"]

User: "all POIs"
Query: /Itinerary/Day/POI
```

---

## Query Type Decision Tree

```
                        ┌─────────────────────────────┐
                        │     What do you want?       │
                        └──────────────┬──────────────┘
                                       │
                 ┌─────────────────────┼─────────────────────┐
                 │                     │                     │
                 ▼                     ▼                     ▼
         ┌───────────┐         ┌───────────┐         ┌───────────┐
         │ By Content│         │By Position│         │    All    │
         │(Semantic) │         │           │         │           │
         └─────┬─────┘         └─────┬─────┘         └─────┬─────┘
               │                     │                     │
               │              ┌──────┴──────┐              │
               │              │             │              │
               ▼              ▼             ▼              ▼
         ┌──────────┐   ┌──────────┐ ┌──────────┐   ┌──────────┐
         │ Single?  │   │  Global  │ │  Local   │   │ Type 6:  │
         │ Multiple?│   │ (across  │ │(per-Day) │   │ Multiple │
         └────┬─────┘   │  all)    │ │          │   │          │
              │         └────┬─────┘ └────┬─────┘   └──────────┘
        ┌─────┴─────┐        │            │
        │           │        │            │
        ▼           ▼        ▼            ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
   │ Type 5: │ │ Type 6: │ │ Type 1: │ │ Type 2: │
   │ Single  │ │Multiple │ │ Global  │ │  Local  │
   └─────────┘ └─────────┘ └─────────┘ └─────────┘


   Type 3 (Syntactic): Use when you know exact Day number
   Type 4 (Semantic):  Use for content-based filtering at any level
```

---

## Advanced: Combined Queries

Combine multiple query types for precise results:

```
User: "second museum in an artistic day"
Query: /Itinerary/Day[description =~ "artistic"]/POI[description =~ "museum"][2]
       ├── Type 4: Semantic filter on Day
       ├── Type 4: Semantic filter on POI  
       └── Type 2: Local index [2]

User: "first 2 Italian restaurants globally"
Query: (/Itinerary/Day/Restaurant[description =~ "italian"])[1:2]
       ├── Type 4: Semantic filter
       └── Type 1: Global range index

User: "last jazz venue in each day"
Query: /Itinerary/Day/POI[description =~ "jazz"][-1]
       ├── Type 4: Semantic filter
       └── Type 2: Local last index
```

---

## Configuration

Edit `config.yaml`:

```yaml
# Schema and data file selection
active_schema: "itinerary"
active_data: "travel_memory_3day"  # Options: travel_memory_3day, travel_memory_5day

openai:
  api_key: "your-api-key"
  model: "gpt-4o"

xpath_executor:
  top_k: 5                    # Max nodes to return
  score_threshold: 0.01       # Min score for semantic matches
  scoring_method: "cosine"    # "llm", "entailment", or "cosine"

entailment:
  model: "facebook/bart-large-mnli"
  hypothesis_template: "This is related to {predicate}."

cosine:
  model: "sentence-transformers/msmarco-distilbert-base-tas-b"
  predicate_template: "{predicate}"
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
Config: scoring_method=entailment, top_k=5, score_threshold=0.01
Enter your request to generate and execute an XPath query.
Type 'exit' to quit.

Request: find me all jazz venues
Query: /Itinerary/Day/POI[description =~ "jazz"]

Matched 2 node(s) (sorted by score):
...
```

### Command Line Options

```bash
# Use LLM scoring
python -m pipeline.semantic_xpath_pipeline --scoring llm

# Use cosine similarity
python -m pipeline.semantic_xpath_pipeline --scoring cosine

# Custom threshold and top_k
python -m pipeline.semantic_xpath_pipeline --top-k 10 --threshold 0.5
```

### Programmatic Usage

```python
from pipeline import SemanticXPathPipeline
from dense_xpath import DenseXPathExecutor, list_available_data_files

# Check available data files
print(list_available_data_files())
# ['travel_memory_3day', 'travel_memory_5day']

# Use specific data file
executor = DenseXPathExecutor(
    data_name="travel_memory_5day",
    scoring_method="cosine"
)

result = executor.execute("/Itinerary/Day/POI[description =~ \"museum\"]")
for node in result.matched_nodes:
    print(f"- {node.tree_path}: {node.score:.3f}")

# Or use the full pipeline
pipeline = SemanticXPathPipeline(
    scoring_method="entailment",
    top_k=5,
    score_threshold=0.3
)

result = pipeline.process_request("find all jazz venues")
print(f"Query: {result['query']}")
```

---

## Scoring Methods Deep Dive

### 1. LLM Scoring (`llm`)

Uses GPT-4 to evaluate semantic relevance:

```
Premise: "POI: Art Gallery of Ontario - Explore Canadian, European..."
Predicate: "artistic"
→ Score: 0.95 (LLM reasoning: "Art gallery is highly artistic")
```

**Pros:** Most accurate, can understand nuanced queries
**Cons:** Slow, requires API calls, costs money

### 2. Entailment Scoring (`entailment`)

Uses BART-large-mnli for natural language inference:

```
Premise: "POI: Art Gallery of Ontario - Explore Canadian, European..."
Hypothesis: "This is related to artistic."
→ Entailment score: 0.87
```

**Pros:** Fast local inference, no API costs
**Cons:** May miss nuanced relationships

### 3. Cosine Similarity (`cosine`)

Uses TAS-B embeddings for semantic similarity:

```
Node embedding: embed("POI: Art Gallery of Ontario...")
Query embedding: embed("artistic")
→ Cosine similarity: 0.72
```

**Pros:** Fastest, good for keyword-style queries
**Cons:** Less accurate for complex semantic relationships

---

## Execution Traces

All executions are logged to `traces/`:

```
traces/
├── log/
│   └── execution_20250102_143052.log
└── reasoning_traces/
    ├── entailment_scoring_20250102_143052.json
    └── execution_trace_20250102_143052.json
```

**Execution trace example:**
```json
{
  "query": "/Itinerary/Day/POI[description =~ \"jazz\"]",
  "data_file": "travel_memory_3day.xml",
  "traversal_steps": [
    {
      "step_index": 0,
      "action": "root_match",
      "nodes_after_count": 1
    },
    {
      "step_index": 1,
      "action": "type_match",
      "details": {"target_type": "Day", "found_count": 3}
    },
    {
      "step_index": 2,
      "action": "type_match",
      "details": {"target_type": "POI", "found_count": 8}
    },
    {
      "step_index": 2,
      "action": "semantic_predicate",
      "details": {"predicate": "jazz"}
    }
  ]
}
```

---

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd LLM-VM

# Install dependencies
pip install -r requirements.txt

# Set up your OpenAI API key in config.yaml
```

### Requirements

```
openai>=1.0.0
pyyaml
torch
transformers
numpy
```

---

## Architecture Diagram

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
│  NL → XPath Query       │    │  Execute against tree   │    │                         │
│  (LLM-based)            │    │  BFS traversal          │    │  - LLMPredicateScorer   │
└─────────────────────────┘    │  Semantic filtering     │    │  - EntailmentScorer     │
                               │  Multi-data support     │    │  - CosineScorer         │
                               └───────────┬─────────────┘    └─────────────────────────┘
                                           │
                    ┌──────────────────────┼────────────────────────┐
                    │                      │                        │
                    ▼                      ▼                        ▼
          ┌─────────────────┐    ┌─────────────────┐      ┌─────────────────┐
          │   QueryParser   │    │  IndexHandler   │      │PredicateHandler │
          │                 │    │                 │      │                 │
          │ Parse XPath     │    │ [1], [2], [-1]  │      │ Semantic        │
          │ into steps      │    │ [1:3], [-2:]    │      │ predicate       │
          └─────────────────┘    │ Global/Local    │      │ scoring         │
                                 └─────────────────┘      └─────────────────┘
                                           │
                                           ▼
                                 ┌─────────────────┐
                                 │  SchemaLoader   │
                                 │                 │
                                 │ Load schema &   │
                                 │ resolve data    │
                                 │ file paths      │
                                 └─────────────────┘
```

---

## Extending to New Tree Structures

The system is **fully dynamic** and can support any tree structure (not just itineraries).

### Adding a New Schema

1. Create a new schema file (`storage/schemas/todo.yaml`):
```yaml
name: "todo"
description: "Todo list with projects and tasks"

hierarchy: |
  TodoList (root)
  ├── Project
  │   └── Task

nodes:
  TodoList:
    type: root
  Project:
    type: container
    index_attr: "index"
  Task:
    type: leaf
    name_field: "title"
    description_field: "description"

data_files:
  my_todos: "memory/todo_list.xml"

default_data: "my_todos"
```

2. Create the data file (`storage/memory/todo_list.xml`)

3. Update `config.yaml`:
```yaml
active_schema: "todo"
active_data: "my_todos"
```

4. The system will automatically adapt to your new structure!

---

## Key Concepts

### The 6 Query Types Summary

| Type | Syntax Pattern | Scope | Use Case |
|------|----------------|-------|----------|
| **Global** | `(/path)[n]` | Across all results | "5th POI overall" |
| **Local** | `/path[n]` | Per parent | "2nd POI in each Day" |
| **Syntactic** | `/Day[1]/POI[2]` | Explicit structure | "2nd POI in Day 1" |
| **Semantic** | `[description =~ "x"]` | Content filtering | "artistic days" |
| **Single** | Semantic + `[1]` | One result | "find a museum" |
| **Multiple** | Semantic only | All matches | "find all museums" |

### Local vs Global Indexing

| Syntax | Scope | Result |
|--------|-------|--------|
| `/Itinerary/Day/POI[2]` | Local (per parent) | 2nd POI in EACH Day (3 results) |
| `(/Itinerary/Day/POI)[2]` | Global (flattened) | 2nd POI overall (1 result) |

### Semantic Predicate Syntax

```
NodeType[description =~ "query"]
```

- Uses `description` field for matching
- Operator `=~` indicates semantic (fuzzy) matching
- Quotes around the search term
- Scored using LLM, entailment, or cosine similarity

### Index Syntax Reference

| Syntax | Meaning | Local Example | Global Example |
|--------|---------|---------------|----------------|
| `[1]` | First element | `POI[1]` | `(/Day/POI)[1]` |
| `[2]` | Second element | `POI[2]` | `(/Day/POI)[2]` |
| `[-1]` | Last element | `POI[-1]` | `(/Day/POI)[-1]` |
| `[1:3]` | Elements 1, 2, 3 | `POI[1:3]` | `(/Day/POI)[1:3]` |
| `[-2:]` | Last 2 elements | `POI[-2:]` | `(/Day/POI)[-2:]` |
---

## License

MIT License
