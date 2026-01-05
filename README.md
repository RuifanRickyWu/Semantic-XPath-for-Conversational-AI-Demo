# Semantic XPath Query System

A natural language to XPath-like query system for structured itinerary data. Convert plain English requests into executable queries against an XML tree with semantic matching capabilities.

## 🎯 Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌─────────────┐
│  User Request   │────▶│  Query Generator │────▶│  XPath Executor  │────▶│   Results   │
│  (Natural Lang) │     │      (LLM)       │     │  (BFS + Scoring) │     │  (Matched)  │
└─────────────────┘     └──────────────────┘     └──────────────────┘     └─────────────┘
     "find all                                                              [POI, POI,
    jazz venues"      /Itinerary/Day/POI                                   Restaurant]
                      [description =~ "jazz"]
```

## 📁 Project Structure

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
│   ├── node_utils.py                # XML node utilities
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
│   ├── memory/tree_memory.xml       # Itinerary data (XML tree)
│   └── prompts/xpath_query_generator.txt
├── traces/                          # Execution & scoring traces
│   ├── log/
│   └── reasoning_traces/
└── config.yaml                      # Configuration
```

## 🌳 Data Model: Itinerary Tree

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
└── Day[3]
    └── ...
```

**Node Types:**
- `Itinerary` - Root node
- `Day` - Contains POIs and Restaurants
- `POI` - Points of Interest (museums, towers, markets, etc.)
- `Restaurant` - Dining locations

**Important:** POI and Restaurant are **siblings** (same level under Day), NOT parent-child.

---

## 🔄 End-to-End Flow

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

## 📝 Query Types & Examples

### 1. Simple Path Queries

```
User: "all POIs"
Query: /Itinerary/Day/POI

User: "all restaurants"
Query: /Itinerary/Day/Restaurant
```

### 2. Positional Indexing (Local)

Select by position **within each parent node**:

```
User: "second POI in every day"
Query: /Itinerary/Day/POI[2]
→ Returns: POI #2 from Day 1, POI #2 from Day 2, POI #2 from Day 3

User: "last restaurant in each day"
Query: /Itinerary/Day/Restaurant[-1]
→ Returns: Last restaurant from each day
```

### 3. Global Indexing

Select by position **across all matched nodes**:

```
User: "the third POI globally"
Query: (/Itinerary/Day/POI)[3]
→ Returns: The 3rd POI overall (not per-day)

User: "globally 5th POI"
Query: (/Itinerary/Day/POI)[5]
```

**Local vs Global:**
```
/Itinerary/Day/POI[2]      → 2nd POI in EACH day (multiple results)
(/Itinerary/Day/POI)[2]    → 2nd POI OVERALL (single result)
```

### 4. Range Indexing

Select multiple elements by range:

```
User: "first 3 POIs in day 1"
Query: /Itinerary/Day[1]/POI[1:3]

User: "POIs 2 to 4 globally"
Query: (/Itinerary/Day/POI)[2:4]

User: "restaurants 1 and 2 in every day"
Query: /Itinerary/Day/Restaurant[1:2]
```

### 5. Last N Elements

```
User: "last 2 POIs"
Query: (/Itinerary/Day/POI)[-2:]

User: "last 3 restaurants globally"
Query: (/Itinerary/Day/Restaurant)[-3:]

User: "last 2 POIs in every day"
Query: /Itinerary/Day/POI[-2:]
```

### 6. Semantic Predicates

Filter by content/meaning:

```
User: "all restaurants in a cultural day"
Query: /Itinerary/Day[description =~ "cultural"]/Restaurant

User: "find Italian restaurants"
Query: /Itinerary/Day/Restaurant[description =~ "italian"]

User: "jazz venues"
Query: /Itinerary/Day/POI[description =~ "jazz"]
```

### 7. Combined Queries

Semantic predicates + positional indexing:

```
User: "second museum"
Query: (/Itinerary/Day/POI[description =~ "museum"])[2]

User: "first Italian restaurant"
Query: (/Itinerary/Day/Restaurant[description =~ "italian"])[1]

User: "second museum in an artistic day"
Query: /Itinerary/Day[description =~ "artistic"]/POI[description =~ "museum"][2]

User: "first 2 Italian restaurants"
Query: (/Itinerary/Day/Restaurant[description =~ "italian"])[1:2]

User: "last 2 museums"
Query: (/Itinerary/Day/POI[description =~ "museum"])[-2:]
```

---

## ⚙️ Configuration

Edit `config.yaml`:

```yaml
openai:
  api_key: "your-api-key"
  model: "gpt-4o"

xpath_executor:
  top_k: 5                    # Max nodes to return
  score_threshold: 0.01       # Min score for semantic matches
  scoring_method: "entailment"  # "llm", "entailment", or "cosine"

entailment:
  model: "facebook/bart-large-mnli"
  hypothesis_template: "This is related to {predicate}."

cosine:
  model: "sentence-transformers/msmarco-distilbert-base-tas-b"
  predicate_template: "{predicate}"
```

---

## 🚀 Usage

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

pipeline = SemanticXPathPipeline(
    scoring_method="entailment",
    top_k=5,
    score_threshold=0.3
)

result = pipeline.process_request("find all jazz venues")
print(f"Query: {result['query']}")
for node in result['matched_nodes']:
    print(f"- {node.tree_path}: {node.score:.3f}")
```

---

## 🔬 Scoring Methods Deep Dive

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

## 📊 Execution Traces

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

## 🛠️ Installation

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

## 📈 Architecture Diagram

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
                               └───────────┬─────────────┘    │  - CosineScorer         │
                                           │                  └─────────────────────────┘
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
```

---

## 📚 Key Concepts

### Local vs Global Indexing

| Syntax | Scope | Example |
|--------|-------|---------|
| `Day/POI[2]` | Local (per parent) | 2nd POI in EACH Day |
| `(Day/POI)[2]` | Global (all results) | 2nd POI overall |

### Semantic Predicate Syntax

```
NodeType[description =~ "query"]
```

- Uses `description` field for matching
- Operator `=~` indicates semantic (fuzzy) matching
- Quotes around the search term

### Index Syntax

| Syntax | Meaning |
|--------|---------|
| `[1]` | First element |
| `[2]` | Second element |
| `[-1]` | Last element |
| `[1:3]` | Elements 1, 2, 3 |
| `[-2:]` | Last 2 elements |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

---

## 📄 License

MIT License


