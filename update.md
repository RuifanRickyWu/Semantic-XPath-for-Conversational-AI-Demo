# Hierarchical Retrieval with Semantic XPath


## 1. Running Example

### Travel Itinerary as XML

We use a travel itinerary represented as a hierarchical XML document:

```xml
<Itinerary>
  <Day index="1">
    <POI>
      <name>St. Lawrence Market</name>
      <description>
        Start your day at this iconic market featuring local artisans and specialty foods.
      </description>
    </POI>
    <POI>
      <name>Art Gallery of Ontario</name>
      <description>
        A world-class museum showcasing Canadian and international art.
      </description>
    </POI>
  </Day>

  <Day index="2">
    <POI>
      <name>Royal Ontario Museum</name>
      <description>
        A major museum dedicated to art, culture, and natural history.
      </description>
    </POI>
    <POI>
      <name>Distillery District</name>
      <description>
        A historic area known for its artistic atmosphere and cultural events.
      </description>
    </POI>
  </Day>
</Itinerary>
```

---

### Query: Find Museums in the Second Day

#### Standard XPath

```xpath
/Itinerary/Day[@index='2']/POI[contains(name, 'Museum')]
```

#### Semantic XPath

```xpath
/Itinerary/Day[@index = '2']/POI[sem(name, 'Museum')]
```

- Structural navigation is identical to XPath.
- Predicate test is replaced by semantic similarity scoring: `sem` instead of `contains`.
- POIs receive scores in [0, 1] and can be ranked

---
### Query: Find Museums and Art Galleries

#### Standard XPath

```xpath
/Itinerary/Day/POI[
  contains(name, 'Museum')
  or
  contains(name, 'Art Gallery')
]
```

#### Semantic XPath

```xpath
/Itinerary/Day/POI[
  sem(name, 'Museum')
  or
  sem(name, 'Art Gallery')
]
```

- `or` operator combines the two predicate scores using Noisy-OR.
---

### Query: Find an artistic day

#### Standard XPath

```xpath
/Itinerary/Day[
  POI[contains(description, 'artistic')]
]
```
- Approximates the notion of an artistic day using a binary existential test.
- The predicate evaluates to true if at least one POI under the day contains the lexical token “artistic”.

#### Semantic XPath

```xpath
/Itinerary/Day[
  mass(POI[sem(description, 'artistic')])
]
```

- Each POI contributes local semantic evidence.
- `mass` operator aggregates these local scores across all POIs under a day using Beta–Bernoulli model.

---

### Query: Find museums in an artistic day

#### Standard XPath

```xpath
/Itinerary/Day[
  POI[contains(description, 'artistic')]
]/POI[contains(name, 'Museum')]
```

#### Semantic XPath

```xpath
/Itinerary/Day[
  mass(POI[sem(description, 'artistic')])
]/POI[sem(name, 'Museum')]
```
- The `Day` node acquires a contextual score (e.g., artistic day = 0.8).
- The `POI` node has its own local score (e.g., museum = 0.9).
- Final relevance is computed via Bayesian log-odds fusion.



## 2. Overall Paper Idea: New Retrieval Problem + Solution

### New Problem: Hierarchical Retrieval

Hierarchical retrieval operates over **tree structures** where:

- retrieval units are **structurally dependent** rather than independent, and  
- retrieval targets and semantic evidence may reside at **different levels of granularity** within the hierarchy.

---

#### Core Challenges

- **Lack of structural dependency awareness in flat retrieval**  
  Flat retrieval treats all items as independent and cannot exploit structural dependencies to constrain the search space (e..g, *“find a museum in the second day”*).

- **Semantic propagation and distributed evidence**  
  Structural dependency leads to semantic propagation across levels (e.g., *a museum in an artistic day*), and semantic properties may be distributed across multiple descendants (e.g., *an artistic day* emerging from several POIs).

- **Multi-level queries**  
  Hierarchical systems naturally support **multi-granularity queries**, such as:
  - “Find an *artistic day*”
  - “Find a *museum* in an artistic day”

  Traditional retrieval models are flat and lack native support for reasoning across hierarchical levels.

---

### Proposed Solution: Semantic XPath

See above


## 3. Paper Submission Venues

### ACL Demo Track  
- **Deadline**: Feb 27  
- **Format**: 6 pages + 2-page appendix + 2.5-minute video  

### SIGIR Demo Track  
- **Abstract Deadline**: Feb 5  
- **Full Paper Deadline**: Feb 12  
- **Format**: 4 pages (including appendix) + video / web interface  

### ACL Industry Track  
- **Deadline**: Feb 14  
- **Format**: 6 pages  


## 4. Evaluation Plan

### Demo-Oriented Evaluation (ACL / SIGIR Demo)

- Application domains:
  - travel itinerary
  - todo list
  - curriculum planning
  - customer support
- Each domain includes:
  - one or more designed hierarchical schema
  - a set of queries with varying difficulty and granularity
- Evaluation metrics:
  - Precision@k
  - Recall@k
  - nDCG@k

The goal is to demonstrate the advantages of Semantic XPath over flat retrieval in controlled, interpretable settings.

---

### Industry-Oriented Evaluation (ACL Industry Track)

- Demo evaluation
- Observe that many product search and NL recommendation datasets implicitly exhibit hierarchical structure and can be formed as hierarchical retrieval task
- Compare Semantic XPath against standard baselines:
  - sparse retrieval
  - dense retrieval
  - retrieval with fusion
