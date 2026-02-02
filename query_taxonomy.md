# Semantic XPath Query Taxonomy

This document provides a comprehensive taxonomy of query types supported by the Semantic XPath system.

## Overview

Semantic XPath extends traditional XPath with probabilistic semantic matching. Queries navigate hierarchical data structures while applying semantic predicates that understand meaning, not just exact text matches.

```
/RootNode/ContainerNode[predicate]/LeafNode[predicate]
```

---

## 1. Path Navigation

### 1.1 Simple Path
Navigate through the node hierarchy without any filtering.

```xpath
/Itinerary/Day/POI
```
**Result**: All POI nodes under all Days.

### 1.2 Partial Path
Start from any level in the hierarchy.

```xpath
/Itinerary/Day
```
**Result**: All Day nodes under Itinerary.

---

## 2. Index-Based Selection

### 2.1 Attribute Index
Select nodes by their index attribute using XPath attribute syntax.

```xpath
/Itinerary/Day[2]/POI
```
**Result**: All POIs in Day 2.

---

## 3. Semantic Predicates

### 3.1 Local Semantic Match: `sem()`

Matches based on the **node's own content only** (its fields like name, description, etc.). Does not consider children.

**Syntax**:
```xpath
NodeType[sem(content =~ "semantic description")]
```

**Example**:
```xpath
/Itinerary/Day/POI[sem(content =~ "museum")]
```
**Semantics**: Find POIs whose own content is semantically related to "museum".

**When to use**:
- The query describes a property of the target node itself
- Looking for specific characteristics in leaf nodes
- The answer can be determined from the node's own fields

---

### 3.2 Existential Quantifier: `exist()`

Checks if **at least one child** matches the inner predicate. Uses **Noisy-OR** aggregation.

**Syntax**:
```xpath
ContainerNode[exist(ChildType[sem(content =~ "description")])]
```

**Example**:
```xpath
/Itinerary/Day[exist(POI[sem(content =~ "museum")])]
```
**Semantics**: Find Days that have at least one POI related to "museum".

**Mathematical Model** (Noisy-OR):
```
P(match) = 1 - ∏(1 - p_i)
```
Where `p_i` is the score of each matching child. High score if **any** child matches well.

**When to use**:
- "Day with a museum" → checking existence of a specific child type
- "Project containing a bug fix task"
- "Genre that has a horror movie"

---

### 3.3 Prevalence Quantifier: `mass()`

Checks if children **generally/mostly** match the predicate. Uses **Beta-Bernoulli** aggregation.

**Syntax**:
```xpath
ContainerNode[mass(ChildType[sem(content =~ "description")])]
```

**Example**:
```xpath
/Itinerary/Day[mass(POI[sem(content =~ "artistic")])]
```
**Semantics**: Find Days where the POIs are generally artistic (overall character).

**Mathematical Model** (Beta-Bernoulli):
```
P(match) = (α + Σp_i) / (α + β + n)
```
With Beta(1,1) prior. Estimates the **proportion** of children that match.

**When to use**:
- "Artistic day" → overall character based on multiple children
- "Productive project" → general nature of tasks
- "Action-heavy genre" → most movies are action

---

## 4. Logical Operators

### 4.1 AND Operator

Combines conditions that must **all** be satisfied. Uses **log-odds aggregation**.

**Within sem()** - Multiple conditions on the same node:
```xpath
/Itinerary/Day/POI[sem(content =~ "outdoor") AND sem(content =~ "historic")]
```
**Semantics**: POIs that are both outdoor AND historic.

**Across aggregations** - Multiple child conditions:
```xpath
/Itinerary/Day[exist(POI[sem(content =~ "museum")]) AND exist(Restaurant[sem(content =~ "italian")])]
```
**Semantics**: Days that have both a museum AND an Italian restaurant.

**Mathematical Model**:
```
log_odds(combined) = Σ log_odds(p_i)
```

---

### 4.2 OR Operator

Satisfied if **any** condition matches. Uses **Noisy-OR aggregation**.

**Within sem()** - Alternative conditions:
```xpath
/Itinerary/Day/POI[sem(content =~ "museum") OR sem(content =~ "gallery")]
```
**Semantics**: POIs that are either museums OR galleries.

**Across aggregations**:
```xpath
/Itinerary/Day[exist(POI[sem(content =~ "beach")]) OR exist(POI[sem(content =~ "park")])]
```
**Semantics**: Days that have either a beach OR a park.

**Mathematical Model**:
```
P(match) = 1 - ∏(1 - p_i)
```

---

## 5. Combined Patterns

### 5.1 Path + Index + Predicate
```xpath
/Itinerary/Day[1]/POI[sem(content =~ "morning activity")]
```

### 5.2 Nested Aggregations with Logic
```xpath
/Itinerary/Day[mass(POI[sem(content =~ "cultural")]) AND exist(Restaurant[sem(content =~ "fine dining")])]
```
**Semantics**: Days that are generally cultural AND have at least one fine dining restaurant.

### 5.3 Multiple OR Conditions
```xpath
/Itinerary/Day/POI[sem(content =~ "museum") OR sem(content =~ "gallery") OR sem(content =~ "exhibition")]
```

---

## 6. Decision Guide

| Query Intent | Predicate | Example |
|-------------|-----------|---------|
| Property of the node itself | `sem()` | "museum POI" → `POI[sem(content =~ "museum")]` |
| Has at least one child of type | `exist()` | "day with a museum" → `Day[exist(POI[sem(...)])]` |
| Overall character from children | `mass()` | "artistic day" → `Day[mass(POI[sem(...)])]` |
| Multiple conditions, all required | `AND` | "outdoor AND historic" |
| Alternative conditions | `OR` | "museum OR gallery" |
| Specific index | `[N]` | "day 2" → `Day[2]` |

---

## 7. Query Examples by Domain

### Itinerary Domain
```xpath
# Find all museums
/Itinerary/Day/POI[sem(content =~ "museum")]

# Days with outdoor activities
/Itinerary/Day[exist(POI[sem(content =~ "outdoor")])]

# Artistic days (most POIs are cultural)
/Itinerary/Day[mass(POI[sem(content =~ "artistic")])]

# Day 2 restaurants
/Itinerary/Day[2]/Restaurant

# Days with both museums and Italian food
/Itinerary/Day[exist(POI[sem(content =~ "museum")]) AND exist(Restaurant[sem(content =~ "italian")])]
```

### TodoList Domain
```xpath
# High priority tasks
/TodoList/Project/Task[sem(content =~ "high priority")]

# Projects with bug fixes
/TodoList/Project[exist(Task[sem(content =~ "bug fix")])]

# Productive projects (most tasks completed)
/TodoList/Project[mass(Task[sem(content =~ "completed")])]
```

### Movie Domain
```xpath
# Horror movies
/MovieDatabase/Genre/Movie[sem(content =~ "horror")]

# Genres with classic films
/MovieDatabase/Genre[exist(Movie[sem(content =~ "classic")])]

# Action-heavy genres
/MovieDatabase/Genre[mass(Movie[sem(content =~ "action")])]
```

### Support Domain
```xpath
# Performance-related tickets
/SupportSystem/Customer/Ticket[sem(content =~ "performance issue")]

# Customers with critical issues
/SupportSystem/Customer[exist(Ticket[sem(content =~ "critical")])]
```

### Curriculum Domain
```xpath
# Sorting-related concepts
/Curriculum/Course/Concept[sem(content =~ "sorting")]

# Courses covering machine learning
/Curriculum/Course[exist(Concept[sem(content =~ "machine learning")])]

# Math-heavy courses
/Curriculum/Course[mass(Concept[sem(content =~ "mathematical")])]
```

---

## 8. Scoring Methods

The semantic similarity in `sem()` can be computed using different backends:

| Method | Description | Speed | Quality |
|--------|-------------|-------|---------|
| `cosine` | TAS-B embedding similarity | Fast | Good |
| `entailment` | BART-MNLI NLI scoring | Medium | Better |
| `llm` | GPT-4 direct scoring | Slow | Best |

---

## 9. Grammar Summary (BNF-like)

```bnf
query       ::= path_step+
path_step   ::= '/' node_type index? predicate?

node_type   ::= identifier
index       ::= '[@' attr '=' "'" number "'" ']' | '[' number ']'
predicate   ::= '[' logical_expr ']'

logical_expr ::= term (('AND' | 'OR') term)*
term         ::= sem_pred | exist_pred | mass_pred | '(' logical_expr ')'

sem_pred    ::= 'sem(content =~ "' text '")'
exist_pred  ::= 'exist(' node_type '[' logical_expr ']' ')'
mass_pred   ::= 'mass(' node_type '[' logical_expr ']' ')'
```

---

## 10. Key Principles

1. **sem() is local**: Only considers the node's own fields, never its children
2. **exist() is existential**: "At least one" - high score if any child matches
3. **mass() is prevalence**: "Generally/mostly" - estimates proportion of matching children
4. **AND requires all**: All conditions must be satisfied (multiplicative in log-odds)
5. **OR requires any**: Any condition suffices (Noisy-OR aggregation)
6. **Scores are probabilistic**: All scores are in [0, 1] range, representing confidence
