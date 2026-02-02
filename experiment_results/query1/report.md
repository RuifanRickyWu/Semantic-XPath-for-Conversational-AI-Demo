# Experiment Report: query1

## Summary

| Query ID | Pipeline | Operation | XPath / Logic | Result | Tokens (Total) | Time (s) |
|---|---|---|---|---|---|---|
| 001 | semantic_xpath | READ | `/Itinerary/Day[not(agg_exists(POI[atom(content =~...` | Selected 0 nodes | 5,364 (5,238 / 126) | 14.68 |
| 001 | incontext | READ | `N/A (Full Tree)` |  | 7,189 (6,439 / 750) | 14.01 |

## Detailed Results
### Query 001
**Query:** My college friend lives in Mississauga, about an hour from downtown. I need a day without any work commitments or flights.

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[not(agg_exists(POI[atom(content =~ "work")])) AND not(agg_exists(POI[atom(content =~ "flight")]))]`
- **Result:** Selected 0 nodes
- **Time:** 14.68s
- **Tokens:** 5,364 (5,238 / 126)

#### incontext
- **Operation:** READ
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 14.01s
- **Tokens:** 7,189 (6,439 / 750)

**Selected Nodes:**

**1. Node**
