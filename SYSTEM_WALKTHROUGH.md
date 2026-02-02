# Semantic XPath System: End-to-End Walkthrough

This document explains how the Semantic XPath system works from end to end, walking through concrete examples of query generation, execution, and CRUD operations.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Data Model](#2-data-model)
3. [Query Generation](#3-query-generation)
4. [Query Format](#4-query-format)
5. [Query Execution](#5-query-execution)
6. [Walkthrough Examples](#6-walkthrough-examples)
7. [CRUD Operations](#7-crud-operations)

---

## 1. System Overview

The Semantic XPath system enables **natural language queries** over **hierarchical XML data** with:

- **Semantic matching**: Match by meaning, not exact text
- **Probabilistic scoring**: Every match has a confidence score [0, 1]
- **Hierarchical aggregation**: Aggregate scores from children to parents
- **Score fusion**: Combine scores across query steps (product)
- **Full CRUD**: Create, Read, Update, Delete via natural language
- **In-tree versioning**: Every modification creates a new version in the tree

### High-Level Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              PIPELINE                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   User Input              LLM Query              Semantic XPath          │
│   (Natural Language)      Generation             Execution               │
│         │                     │                       │                  │
│         ▼                     ▼                       ▼                  │
│   ┌───────────┐        ┌───────────┐           ┌───────────┐            │
│   │ "find     │   →    │ GPT-4     │    →      │ BFS with  │    →       │
│   │  museums  │        │ generates │           │ semantic  │            │
│   │  in the   │        │ XPath     │           │ scoring   │            │
│   │  trip"    │        │ query     │           │           │            │
│   └───────────┘        └───────────┘           └───────────┘            │
│                                                       │                  │
│                                                       ▼                  │
│                                              ┌───────────────┐           │
│                                              │ Ranked        │           │
│                                              │ Results       │           │
│                                              │ with scores   │           │
│                                              └───────────────┘           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Model

### Tree Structure

Data is stored as hierarchical XML with versioning. Here's a simplified example of a travel itinerary:

```xml
<Root>
  <Itinerary_Version number="1">
    <patch_info>None</patch_info>
    <conversation_history>Initial_Version</conversation_history>
    <Itinerary>
      <Day index="1">
        <POI>
          <name>St. Lawrence Market</name>
          <time_block>9:00 AM - 10:30 AM</time_block>
          <description>Start your day at this iconic market...</description>
          <expected_cost>CAD 10-15</expected_cost>
        </POI>
        <POI>
          <name>Art Gallery of Ontario</name>
          <time_block>2:30 PM - 4:00 PM</time_block>
          <description>Explore Canadian, European, and contemporary art...</description>
          <expected_cost>CAD 25</expected_cost>
        </POI>
        <Restaurant>
          <name>Buca Yorkville</name>
          <description>Upscale Italian dining...</description>
        </Restaurant>
      </Day>
      <Day index="2">
        <POI>
          <name>Royal Ontario Museum</name>
          <description>World-renowned museum showcasing art, culture...</description>
        </POI>
        <!-- more POIs and Restaurants -->
      </Day>
    </Itinerary>
  </Itinerary_Version>
</Root>
```

### Schema Definition

The tree structure is defined in a YAML schema (e.g., `storage/schemas/itinerary.yaml`):

```yaml
name: "itinerary"
hierarchy: |
  Root
  └── Itinerary_Version (container, indexed by @number)
      └── Itinerary (container)
          └── Day (container, indexed by @index)
              ├── POI (leaf)
              └── Restaurant (leaf)

nodes:
  Day:
    type: container
    index_attr: "index"
    children: ["POI", "Restaurant"]   # Structural children
    
  POI:
    type: leaf
    fields: [name, time_block, description, expected_cost, highlights]
    children: []
```

**Key distinction:**
- `fields`: Node's own content (name, description, etc.)
- `children`: Structural child node types (for aggregation)

---

## 3. Query Generation

### Input

A natural language request from the user:

```
"find museums in the trip"
```

### Process

The system uses an LLM (GPT-4) with a schema-aware prompt to convert natural language to Semantic XPath:

1. **Load prompt template**: `storage/prompts/xpath_query_generator.txt`
2. **Inject schema context**: Tree structure, syntax rules, examples
3. **LLM generates XPath**: Single query with semantic predicates

### LLM Prompt Structure

```
You are a Semantic XPath query generator for a itinerary tree.

Task:
- Convert a user request into a valid Semantic XPath query
- Output ONLY the XPath path (no operation prefix)

## Schema
Root → Itinerary_Version → Itinerary → Day → POI/Restaurant

## Grammar
[grammar rules - see section 4]

## Examples
User: museums
Output: /Itinerary/Day/POI[atom(content =~ "museum")]

User: restaurants on day 2
Output: /Itinerary/Day[2]/Restaurant

User: days with jazz activities
Output: /Itinerary/Day[agg_exists(POI[atom(content =~ "jazz")])]

Now convert the following user request into a Semantic XPath query.
```

### Output

The LLM generates a structured XPath query:

```xpath
/Itinerary/Day/POI[atom(content =~ "museum")]
```

---

## 4. Query Format

### Grammar Specification

```
Query     := Step | Step / Query | (Query)[GlobalIndex]
Step      := Axis NodeType Index [Predicate]
Axis      := none | desc::
NodeType  := Name | "."
Index     := none | [i] | [-i] | [i:j]
Predicate := Atom | Agg | Predicate AND Predicate | Predicate OR Predicate | not(Predicate)
Atom      := atom(content =~ "value")
Agg       := agg_exists(ChildType[Predicate]) | agg_prev(ChildType[Predicate])
```

### Components Explained

| Component | Syntax | Description |
|-----------|--------|-------------|
| **Path Navigation** | `/Itinerary/Day/POI` | Navigate through tree hierarchy |
| **Positional Index** | `Day[2]`, `POI[-1]`, `POI[1:3]` | Select by position (1-based) |
| **Global Index** | `(/Itinerary/Day/POI)[5]` | 5th POI across ALL days |
| **atom()** | `atom(content =~ "museum")` | Semantic match on node's content |
| **agg_exists()** | `agg_exists(POI[...])` | ANY child matches (max) |
| **agg_prev()** | `agg_prev(POI[...])` | Children GENERALLY match (mean) |
| **Logical** | `AND`, `OR`, `not()` | Combine predicates |
| **Descendant** | `desc::POI` | Match at any depth |

### Example Queries

| Natural Language | Generated XPath |
|------------------|-----------------|
| "museums" | `/Itinerary/Day/POI[atom(content =~ "museum")]` |
| "restaurants on day 2" | `/Itinerary/Day[2]/Restaurant` |
| "museums in an artistic day" | `/Itinerary/Day[agg_prev(POI[atom(content =~ "artistic")])]/POI[atom(content =~ "museum")]` |
| "days with jazz activities" | `/Itinerary/Day[agg_exists(POI[atom(content =~ "jazz")])]` |
| "the first activity each day" | `/Itinerary/Day/POI[1]` |
| "the 5th restaurant overall" | `(/Itinerary/Day/Restaurant)[5]` |
| "activities that are not expensive" | `/Itinerary/Day/POI[not(atom(content =~ "expensive"))]` |

---

## 5. Query Execution

### Execution Engine: `DenseXPathExecutor`

The executor processes queries through 4 stages:

### Stage 1: Parse Query → AST

```
Query: /Itinerary/Day[agg_prev(POI[atom(content =~ "artistic")])]/POI[atom(content =~ "museum")]

Parsed Steps:
  Step 0: Itinerary (root)
  Step 1: Day [predicate: agg_prev(POI[atom(content =~ "artistic")])]
  Step 2: POI [predicate: atom(content =~ "museum")]
```

### Stage 2: BFS Traversal with Scoring

For each step, expand nodes and apply predicates:

```
Step 0: [Itinerary] ─── root node (score: 1.0)
           │
Step 1: [Day1, Day2, Day3] ─── expand to children
           │
        Score each Day with agg_prev(POI[atom("artistic")])
           │  Day1: 0.72 (average of POI "artistic" scores)
           │  Day2: 0.85
           │  Day3: 0.45
           │
Step 2: [POI1, POI2, ...] ─── expand Day children to POIs
           │
        Score each POI with atom("museum")
           │  Art Gallery of Ontario: 0.92
           │  CN Tower: 0.08
           │  Royal Ontario Museum: 0.95
```

### Stage 3: Score Fusion (Product)

Multiply scores across all steps:

```
Art Gallery of Ontario (in Day 1):
  - Step 1: Day "artistic" score = 0.72
  - Step 2: POI "museum" score = 0.92
  - Final score = 0.72 × 0.92 = 0.662

Royal Ontario Museum (in Day 2):
  - Step 1: Day "artistic" score = 0.85
  - Step 2: POI "museum" score = 0.95
  - Final score = 0.85 × 0.95 = 0.807
```

### Stage 4: Filter & Rank

- Apply threshold (default: 0.01)
- Apply top_k (default: 10)
- Sort by final score descending

```
Final Results:
  1. Royal Ontario Museum: 0.807
  2. Art Gallery of Ontario: 0.662
```

### Scoring Methods

| Method | Implementation | Speed | Accuracy |
|--------|----------------|-------|----------|
| `llm` | GPT-4 scoring | Slow | Highest |
| `entailment` | BART-MNLI NLI | Medium | High |
| `cosine` | TAS-B embeddings | Fast | Good |

### Predicate Scoring Formulas

| Predicate | Formula | Semantics |
|-----------|---------|-----------|
| `atom(c)` | `Scorer(node_content, c)` | Direct semantic match |
| `agg_exists(...)` | `max(child_scores)` | At least one child matches |
| `agg_prev(...)` | `mean(child_scores)` | Children generally match |
| `A AND B` | `min(score_A, score_B)` | Both must match |
| `A OR B` | `max(score_A, score_B)` | Either matches |
| `not(A)` | `1 - score_A` | Negation |

---

## 6. Walkthrough Examples

### Example 1: Simple Semantic Query

**User Input:**
```
"find museums in the trip"
```

**Step 1: Query Generation (LLM)**
```xpath
/Itinerary/Day/POI[atom(content =~ "museum")]
```

**Step 2: Execution**

| POI Name | Content Match ("museum") | Final Score |
|----------|-------------------------|-------------|
| Royal Ontario Museum | 0.95 | 0.95 |
| Art Gallery of Ontario | 0.92 | 0.92 |
| CN Tower | 0.08 | 0.08 |
| Toronto Islands | 0.05 | 0.05 |

**Step 3: Filter & Rank (threshold=0.5)**

```
Results:
  1. Royal Ontario Museum (0.95)
  2. Art Gallery of Ontario (0.92)
```

---

### Example 2: Hierarchical Aggregation Query

**User Input:**
```
"find museums in artistic days"
```

**Step 1: Query Generation (LLM)**
```xpath
/Itinerary/Day[agg_prev(POI[atom(content =~ "artistic")])]/POI[atom(content =~ "museum")]
```

**Step 2: Score Day "artistic" levels**

For Day 1 with POIs: [St. Lawrence Market, CN Tower, Art Gallery of Ontario]
```
POI Scores for "artistic":
  - St. Lawrence Market: 0.3
  - CN Tower: 0.4
  - Art Gallery of Ontario: 0.9

Day 1 score = mean(0.3, 0.4, 0.9) = 0.53
```

For Day 2 with POIs: [Royal Ontario Museum, Casa Loma, Rivoli]
```
POI Scores for "artistic":
  - Royal Ontario Museum: 0.85
  - Casa Loma: 0.7
  - Rivoli: 0.8

Day 2 score = mean(0.85, 0.7, 0.8) = 0.78
```

**Step 3: Score POIs for "museum"**

| POI | Day Score | Museum Score | Final = Day × Museum |
|-----|-----------|--------------|----------------------|
| Art Gallery of Ontario | 0.53 | 0.92 | 0.488 |
| Royal Ontario Museum | 0.78 | 0.95 | 0.741 |

**Step 4: Results**
```
Results:
  1. Royal Ontario Museum (0.741) ← in more artistic day
  2. Art Gallery of Ontario (0.488)
```

---

### Example 3: Existential vs Prevalence

**Query A: "days WITH a museum" (existential)**
```xpath
/Itinerary/Day[agg_exists(POI[atom(content =~ "museum")])]
```

**Query B: "days that ARE museum-focused" (prevalence)**
```xpath
/Itinerary/Day[agg_prev(POI[atom(content =~ "museum")])]
```

**Data:**
```
Day 1: [Market (0.1), Tower (0.1), Art Gallery (0.9)]
Day 2: [Museum (0.95), Museum2 (0.9), Concert (0.1)]
```

**Scoring Comparison:**

| Day | agg_exists (max) | agg_prev (mean) |
|-----|------------------|-----------------|
| Day 1 | max(0.1, 0.1, 0.9) = 0.9 | mean(0.1, 0.1, 0.9) = 0.37 |
| Day 2 | max(0.95, 0.9, 0.1) = 0.95 | mean(0.95, 0.9, 0.1) = 0.65 |

- **agg_exists**: "Does day have at least one museum?" → Day 1 ≈ Day 2
- **agg_prev**: "Is the day mostly museums?" → Day 2 >> Day 1

---

### Example 4: Negation Query

**User Input:**
```
"affordable restaurants (not expensive)"
```

**Step 1: Query Generation**
```xpath
/Itinerary/Day/Restaurant[not(atom(content =~ "expensive"))]
```

**Step 2: Scoring**

| Restaurant | "expensive" Score | not() = 1 - score |
|------------|-------------------|-------------------|
| Queen Street Warehouse | 0.1 | 0.9 ✓ |
| Buca Yorkville ("upscale Italian") | 0.8 | 0.2 |
| Pow Wow Cafe | 0.15 | 0.85 ✓ |

---

### Example 5: Combined AND Query

**User Input:**
```
"outdoor activities that are free"
```

**Step 1: Query Generation**
```xpath
/Itinerary/Day/POI[atom(content =~ "outdoor") AND atom(content =~ "free")]
```

**Step 2: Scoring**

| POI | "outdoor" | "free" | AND = min() |
|-----|-----------|--------|-------------|
| Toronto Islands | 0.95 | 0.3 | 0.30 |
| Distillery District | 0.7 | 0.9 | 0.70 |
| CN Tower | 0.2 | 0.1 | 0.10 |

---

## 7. CRUD Operations

The system supports full CRUD with automatic versioning.

### Operation Flow

```
User Request → [Version Resolution] → [XPath Generation] → [Execution] → [Handler] → [New Version]
```

### READ Operation

**Input:** `"find museums"`

**Generated Query:**
```
Read(/Itinerary/Version[-1]/Day/POI[atom(content =~ "museum")])
```

**Output:**
```json
{
  "operation": "READ",
  "selected_nodes": [
    {
      "name": "Royal Ontario Museum",
      "tree_path": "Itinerary > Version 1 > Day 2 > Royal Ontario Museum",
      "score": 0.95
    },
    {
      "name": "Art Gallery of Ontario",
      "tree_path": "Itinerary > Version 1 > Day 1 > Art Gallery of Ontario",
      "score": 0.92
    }
  ]
}
```

---

### DELETE Operation

**Input:** `"delete all the museums"`

**Generated Query:**
```
Delete(/Itinerary/Version[-1]/Day/POI[atom(content =~ "museum")])
```

**Process:**
1. Execute XPath → find museum nodes
2. LLM confirms which nodes to delete
3. Create new version with nodes removed

**Result:**
```xml
<Root>
  <Itinerary_Version number="1">
    <!-- original version -->
  </Itinerary_Version>
  <Itinerary_Version number="2">
    <patch_info>Deleted: Royal Ontario Museum, Art Gallery of Ontario</patch_info>
    <conversation_history>delete all the museums</conversation_history>
    <Itinerary>
      <!-- Days without museum POIs -->
    </Itinerary>
  </Itinerary_Version>
</Root>
```

---

### UPDATE Operation

**Input:** `"change the CN Tower visit to 2pm"`

**Generated Query:**
```
Update(/Itinerary/Version[-1]/Day/POI[atom(content =~ "CN Tower")], time_block: 2:00 PM)
```

**Process:**
1. Execute XPath → find CN Tower node
2. LLM generates updated content with new time
3. Create new version with modified node

---

### CREATE Operation

**Input:** `"add a sushi restaurant after lunch on day 1"`

**Generated Query:**
```
Create(/Itinerary/Version[-1]/Day[1], Restaurant, sushi restaurant after lunch)
```

**Process:**
1. Find parent node (Day 1)
2. LLM generates new Restaurant content
3. LLM determines insertion position
4. Create new version with new node inserted

---

### Version Selection

Versions can be referenced by:

| Selector | Example | Meaning |
|----------|---------|---------|
| Index | `Version[-1]` | Latest version |
| Number | `Version[2]` | Specific version |
| Semantic | `Version[atom(content =~ "delete museum")]` | Find by changes |

**Compound Query Example:**
```
"in the version that deleted museums, update the first POI"

Generated: Update(/Itinerary/Version[atom(content =~ "delete museum")]/Day/POI[1], ...)
```

The system uses semantic scoring on `patch_info` + `conversation_history` to find the matching version.

---

## Summary: End-to-End Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         COMPLETE PIPELINE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. USER INPUT                                                               │
│     "find museums in artistic days"                                          │
│                                                                              │
│  2. VERSION RESOLUTION (LLM Call 1)                                          │
│     - Classify CRUD operation: READ                                          │
│     - Determine version: Version[-1] (latest)                                │
│                                                                              │
│  3. XPATH GENERATION (LLM Call 2)                                            │
│     - Load schema + grammar + examples                                       │
│     - Generate: /Itinerary/Day[agg_prev(POI[atom(...)])]/POI[atom(...)]     │
│                                                                              │
│  4. SEMANTIC XPATH EXECUTION (Non-LLM)                                       │
│     - Parse query → AST                                                      │
│     - BFS traversal with scoring                                             │
│     - Score fusion (product)                                                 │
│     - Filter & rank                                                          │
│                                                                              │
│  5. LLM NODE REASONING (LLM Call 3)                                          │
│     - Review candidate nodes                                                 │
│     - Select truly relevant nodes                                            │
│                                                                              │
│  6. RESULT                                                                   │
│     - Ranked list of matching nodes                                          │
│     - For modifications: new version created                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **3-Stage LLM Processing**: Version resolution → Query generation → Node reasoning
2. **Score Fusion (Product)**: All predicates must match well for high final score
3. **In-Tree Versioning**: Full history stored in single XML file
4. **Schema-Driven**: Tree structure defined in YAML, prompts generated dynamically
5. **Batch Optimization**: Nodes grouped by semantic value to minimize LLM calls
