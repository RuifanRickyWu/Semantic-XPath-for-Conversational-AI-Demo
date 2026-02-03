# Experiment Report: test

## Summary

| Query ID | Pipeline | Operation | XPath / Logic | Result | Tokens (Total) | Time (s) |
|---|---|---|---|---|---|---|
| 001 | incontext | READ | `N/A (Full Tree)` |  | 7,845 (6,415 / 1,430) | 11.79 |
| 001 | semantic_xpath | READ | `/Itinerary/Day[
not(agg_exists(desc :: POI [atom(...` | Selected 0 nodes | 15,406 (12,071 / 3,335) | 35.06 |
| 002 | incontext | READ | `N/A (Full Tree)` |  | 6,602 (6,414 / 188) | 2.56 |
| 002 | semantic_xpath | READ | `/Itinerary/Day[7]/POI[atom(content =~ "outdoor")]` | Selected 1 nodes | 3,245 (3,004 / 241) | 3.78 |
| 003 | incontext | READ | `N/A (Full Tree)` |  | 6,782 (6,424 / 358) | 2.93 |
| 003 | semantic_xpath | READ | `/Itinerary/Day[6]/POI[atom(content =~ "kid")]` | Selected 2 nodes | 3,472 (3,196 / 276) | 11.24 |
| 004 | incontext | READ | `N/A (Full Tree)` |  | 6,898 (6,407 / 491) | 3.45 |
| 004 | semantic_xpath | READ | `/Itinerary/Day/Restaurant[atom(content =~ "expensive")]` | Selected 3 nodes | 6,545 (5,381 / 1,164) | 18.93 |
| 005 | incontext | READ | `N/A (Full Tree)` |  | 6,806 (6,413 / 393) | 9.64 |
| 005 | semantic_xpath | READ | `/Itinerary/Day[
agg_exists(desc :: POI [
atom(con...` | Selected 3 nodes | 9,216 (7,385 / 1,831) | 21.72 |
| 006 | incontext | READ | `N/A (Full Tree)` |  | 6,806 (6,402 / 404) | 13.92 |
| 006 | semantic_xpath | READ | `/Itinerary/Day[
agg_exists(desc :: POI [atom(cont...` | Selected 2 nodes | 11,934 (9,418 / 2,516) | 36.43 |
| 007 | incontext | DELETE | `N/A (Full Tree)` |  | 11,230 (6,416 / 4,814) | 51.71 |
| 007 | semantic_xpath | DELETE | `/Itinerary/Day/Restaurant[atom(content =~ "dinner...` | Deleted 3 nodes | 9,780 (7,624 / 2,156) | 24.75 |
| 008 | incontext | DELETE | `N/A (Full Tree)` |  | 10,130 (5,461 / 4,669) | 36.21 |
| 008 | semantic_xpath | DELETE | `/Itinerary/Day[7]/POI[atom(content =~ "outdoor")]` | Deleted 1 nodes | 3,712 (3,311 / 401) | 5.29 |
| 009 | incontext | DELETE | `N/A (Full Tree)` |  | 9,712 (5,330 / 4,382) | 27.68 |
| 009 | semantic_xpath | DELETE | `/Itinerary/Day/POI[atom(content =~ "CN Tower")]` | Deleted 0 nodes | 9,587 (7,518 / 2,069) | 17.79 |
| 010 | incontext | DELETE | `N/A (Full Tree)` |  | 9,155 (5,071 / 4,084) | 26.48 |
| 010 | semantic_xpath | DELETE | `/Itinerary/Day/POI[atom(content =~ "Niagara Falls")]` | Deleted 0 nodes | 9,593 (7,523 / 2,070) | 22.45 |
| 011 | incontext | DELETE | `N/A (Full Tree)` |  | 8,638 (4,804 / 3,834) | 24.15 |
| 011 | semantic_xpath | DELETE | `/Itinerary/Day[5]/POI[atom(content =~ "work related")]` | Deleted 2 nodes | 5,323 (4,416 / 907) | 8.06 |
| 012 | incontext | CREATE | `N/A (Full Tree)` |  | 8,531 (4,580 / 3,951) | 25.23 |
| 012 | semantic_xpath | CREATE | `/Itinerary/Day[2]` | Created at Itinerary > Day 2/POI | 3,353 (3,167 / 186) | 5.18 |
| 013 | incontext | CREATE | `N/A (Full Tree)` |  | 8,811 (4,709 / 4,102) | 27.50 |
| 013 | semantic_xpath | CREATE | `/Itinerary/Day[3]` | Created at Itinerary > Day 3/POI | 4,512 (4,314 / 198) | 4.83 |
| 014 | incontext | CREATE | `N/A (Full Tree)` |  | 9,058 (4,837 / 4,221) | 45.54 |
| 014 | semantic_xpath | CREATE | `/Itinerary/Day[10]` | Created at Itinerary > Day 10/POI | 4,970 (4,748 / 222) | 5.91 |

## Detailed Results
### Query 001
**Query:** My friend lives in Mississauga, about an hour from downtown. What days are without any work commitments or flights?

#### incontext
- **Operation:** READ
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 11.79s
- **Tokens:** 7,845 (6,415 / 1,430)

**Selected Nodes:**

1. **Day** -> Index: 6
2.   - **Restaurant** -> Sunset Grill (9:00 AM - 10:00 AM, CAD 20-30, Walk)
3.   - **Restaurant** -> Island Cafe Picnic Lunch (1:30 PM - 2:30 PM, CAD 25, Walk)
4.   - **Restaurant** -> The Keg Steakhouse (7:00 PM - 8:30 PM, CAD 60-80, Walk)
5.   - **POI** -> Toronto Islands Ferry and Bike Ride (10:30 AM - 1:30 PM, CAD 35, Walk and Ferry)
6.   - **POI** -> Ripley's Aquarium (3:30 PM - 5:30 PM, CAD 45, Ferry and Walk)
7. **Day** -> Index: 9
8.   - **Restaurant** -> Lady Marmalade (9:00 AM - 10:30 AM, CAD 25-35, Taxi)
9.   - **Restaurant** -> Urban Eatery Food Court (1:30 PM - 2:15 PM, CAD 15, Walk)
10.   - **Restaurant** -> Bar Isabel (7:30 PM - 9:30 PM, CAD 70-90, Taxi)
11.   - **POI** -> Eaton Centre Shopping (11:00 AM - 1:30 PM, Variable, Public Transit)
12.   - **POI** -> Queen Street West Boutiques (3:00 PM - 5:00 PM, Variable, Walk)

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[
not(agg_exists(desc :: POI [atom(content =~ "work") OR atom(content =~ "flight")]))
]`
- **Result:** Selected 0 nodes
- **Time:** 35.06s
- **Tokens:** 15,406 (12,071 / 3,335)

**Scoring Analysis:**

**Predicate:** `not(agg_exists(atom(content =~ "desc :: POI [atom(content =~ "work")") OR atom(content =~ "atom(content =~ "flight")]")))`
**Threshold:** `0.5`

| Node | Inner Score | Final Score | Result |
|---| --- |---|---|
| Day 1 | 1.0000 | 0.0000 | ❌ Filtered Out (Matches constraint) |
| Day 2 | 1.0000 | 0.0000 | ❌ Filtered Out (Matches constraint) |
| Day 3 | 1.0000 | 0.0000 | ❌ Filtered Out (Matches constraint) |
| Day 4 | 1.0000 | 0.0000 | ❌ Filtered Out (Matches constraint) |
| Day 5 | 0.9000 | 0.1000 | ❌ Filtered Out (Matches constraint) |
| Day 6 | 0.0000 | 1.0000 | ✅ Pass |
| Day 7 | 0.0000 | 1.0000 | ✅ Pass |
| Day 8 | 0.0000 | 1.0000 | ✅ Pass |
| Day 9 | 0.0000 | 1.0000 | ✅ Pass |
| Day 10 | 1.0000 | 0.0000 | ❌ Filtered Out (Matches constraint) |


### Query 002
**Query:** The weather forecast shows heavy rain on Day 7. Which activities are outdoors that I might need to reschedule?

#### incontext
- **Operation:** READ
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 2.56s
- **Tokens:** 6,602 (6,414 / 188)

**Selected Nodes:**

1. **POI** -> Distillery District Walk (3:00 PM - 5:00 PM, Free, Public Transit)
2.   - **highlights** -> 

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[7]/POI[atom(content =~ "outdoor")]`
- **Result:** Selected 1 nodes
- **Time:** 3.78s
- **Tokens:** 3,245 (3,004 / 241)

**Selected Nodes:**

1. **POI** -> Distillery District Walk (3:00 PM - 5:00 PM, Free, Public Transit, {})

**Scoring Analysis:**

**Predicate:** `atom(content =~ "outdoor")`
**Threshold:** `0.5`

| Node | C1 (outdoor) | Final Score | Result |
|---| --- |---|---|
| Royal Ontario Museum | 0.0000 | 0.0000 | ❌ Filtered Out |
| Distillery District Walk | 1.0000 | 1.0000 | ✅ Pass |


### Query 003
**Query:** My sister and nephew are joining me on Day 6. He's 10 years old. What activities do I already have planned that would be fun for a kid?

#### incontext
- **Operation:** READ
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 2.93s
- **Tokens:** 6,782 (6,424 / 358)

**Selected Nodes:**

1. **POI** -> Toronto Islands Ferry and Bike Ride (10:30 AM - 1:30 PM, CAD 35, Walk and Ferry)
2.   - **highlights** -> 
3. **POI** -> Ripley's Aquarium (3:30 PM - 5:30 PM, CAD 45, Ferry and Walk)
4.   - **highlights** -> 

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[6]/POI[atom(content =~ "kid")]`
- **Result:** Selected 2 nodes
- **Time:** 11.24s
- **Tokens:** 3,472 (3,196 / 276)

**Selected Nodes:**

1. **POI** -> Ripley's Aquarium (3:30 PM - 5:30 PM, CAD 45, Ferry and Walk, {})
2. **POI** -> Toronto Islands Ferry and Bike Ride (10:30 AM - 1:30 PM, CAD 35, Walk and Ferry, {})

**Scoring Analysis:**

**Predicate:** `atom(content =~ "kid")`
**Threshold:** `0.5`

| Node | C1 (kid) | Final Score | Result |
|---| --- |---|---|
| Toronto Islands Ferry and Bike Ride | 0.9000 | 0.9000 | ✅ Pass |
| Ripley's Aquarium | 1.0000 | 1.0000 | ✅ Pass |


### Query 004
**Query:** I'm putting together my expense report. What are the most expensive restaurants I've booked?

#### incontext
- **Operation:** READ
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 3.45s
- **Tokens:** 6,898 (6,407 / 491)

**Selected Nodes:**

1. **results** -> 
2.   - **Restaurant** -> Alo Restaurant (7:00 PM - 9:30 PM, CAD 300-400, Taxi)
3.   - **Restaurant** -> Kaiseki Kaji (8:00 PM - 10:00 PM, CAD 250-350, Taxi)
4.   - **Restaurant** -> Canoe Restaurant (7:30 PM - 9:00 PM, CAD 150-200, Taxi)

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day/Restaurant[atom(content =~ "expensive")]`
- **Result:** Selected 3 nodes
- **Time:** 18.93s
- **Tokens:** 6,545 (5,381 / 1,164)

**Selected Nodes:**

1. **Restaurant** -> Alo Restaurant (7:00 PM - 9:30 PM, CAD 300-400, Taxi, {})
2. **Restaurant** -> Kaiseki Kaji (8:00 PM - 10:00 PM, CAD 250-350, Taxi, {})
3. **Restaurant** -> Canoe Restaurant (7:30 PM - 9:00 PM, CAD 150-200, Taxi, {})

**Scoring Analysis:**

**Predicate:** `atom(content =~ "expensive")`
**Threshold:** `0.5`

| Node | C1 (expensive) | Final Score | Result |
|---| --- |---|---|
| Canoe Restaurant | 0.9000 | 0.9000 | ✅ Pass |
| Alo Restaurant | 1.0000 | 1.0000 | ✅ Pass |
| Hotel Continental Breakfast | 0.1000 | 0.1000 | ❌ Filtered Out |
| FRANK Restaurant at AGO | 0.3000 | 0.3000 | ❌ Filtered Out |
| Pai Northern Thai | 0.2000 | 0.2000 | ❌ Filtered Out |
| Quick Grab Coffee | 0.0000 | 0.0000 | ❌ Filtered Out |
| Lee Restaurant | 0.6000 | 0.6000 | ✅ Pass |
| Mildred's Temple Kitchen | 0.2000 | 0.2000 | ❌ Filtered Out |
| Kaiseki Kaji | 0.9000 | 0.9000 | ✅ Pass |
| Sunset Grill | 0.1000 | 0.1000 | ❌ Filtered Out |
| Island Cafe Picnic Lunch | 0.1000 | 0.1000 | ❌ Filtered Out |
| The Keg Steakhouse | 0.4000 | 0.4000 | ❌ Filtered Out |
| Fran's Restaurant | 0.0000 | 0.0000 | ❌ Filtered Out |
| Eataly Toronto | 0.3000 | 0.3000 | ❌ Filtered Out |
| Cluny Bistro | 0.5000 | 0.5000 | ✅ Pass |
| Elements on the Falls | 0.2000 | 0.2000 | ❌ Filtered Out |
| Antler Kitchen | 0.5000 | 0.5000 | ✅ Pass |
| Lady Marmalade | 0.2000 | 0.2000 | ❌ Filtered Out |
| Urban Eatery Food Court | 0.0000 | 0.0000 | ❌ Filtered Out |
| Bar Isabel | 0.4000 | 0.4000 | ❌ Filtered Out |
| Hotel Quick Checkout Breakfast | 0.0000 | 0.0000 | ❌ Filtered Out |
| 360 Restaurant at CN Tower | 0.6000 | 0.6000 | ✅ Pass |


### Query 005
**Query:** I've been stuck in meetings most of the week. Which days have nature activities where I can actually get outside?

#### incontext
- **Operation:** READ
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 9.64s
- **Tokens:** 6,806 (6,413 / 393)

**Selected Nodes:**

1. **Day** -> Index: 6
2.   - **POI** -> Toronto Islands Ferry and Bike Ride (10:30 AM - 1:30 PM, CAD 35, Walk and Ferry)
3. **Day** -> Index: 8
4.   - **POI** -> Niagara Falls Day Trip (8:00 AM - 6:00 PM, CAD 150, Tour Bus)

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[
agg_exists(desc :: POI [
atom(content =~ "nature")
])
]`
- **Result:** Selected 3 nodes
- **Time:** 21.72s
- **Tokens:** 9,216 (7,385 / 1,831)

**Selected Nodes:**

1. **Day** ->  ({'index': '6'})
2. **Day** ->  ({'index': '8'})
3. **Day** ->  ({'index': '1'})

**Scoring Analysis:**

**Predicate:** `agg_exists(atom(content =~ "desc :: POI [
atom(content =~ "nature")
]"))`
**Threshold:** `0.5`

| Node | C1 (desc :: POI [
atom(content =~ "nature")
]) | Final Score | Result |
|---| --- |---|---|
| Day 1 | 0.6000 | 0.6000 | ✅ Pass |
| Day 2 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 3 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 4 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 5 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 6 | 1.0000 | 1.0000 | ✅ Pass |
| Day 7 | 0.4000 | 0.4000 | ❌ Filtered Out |
| Day 8 | 1.0000 | 1.0000 | ✅ Pass |
| Day 9 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 10 | 0.0000 | 0.0000 | ❌ Filtered Out |


### Query 006
**Query:** Where do i go for breakfast on a shopping day?

#### incontext
- **Operation:** READ
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 13.92s
- **Tokens:** 6,806 (6,402 / 404)

**Selected Nodes:**

1. **Restaurant** -> Hotel Continental Breakfast (7:30 AM - 8:30 AM, CAD 25, Walk)
2.   - **highlights** -> 
3. **Restaurant** -> Quick Grab Coffee (7:00 AM - 7:30 AM, CAD 8, Walk)
4.   - **highlights** -> 
5. **Restaurant** -> Lady Marmalade (9:00 AM - 10:30 AM, CAD 25-35, Taxi)
6.   - **highlights** -> 

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[
agg_exists(desc :: POI [atom(content =~ "shopping")])
]/Restaurant[atom(content =~ "breakfast")]`
- **Result:** Selected 2 nodes
- **Time:** 36.43s
- **Tokens:** 11,934 (9,418 / 2,516)

**Selected Nodes:**

1. **Restaurant** -> Sunset Grill (9:00 AM - 10:00 AM, CAD 20-30, Walk, {})
2. **Restaurant** -> Fran's Restaurant (8:30 AM - 9:30 AM, CAD 20, Walk, {})

**Scoring Analysis:**

**Predicate:** `agg_exists(atom(content =~ "desc :: POI [atom(content =~ "shopping")]"))`
**Threshold:** `0.5`

| Node | C1 (desc :: POI [atom(content =~ "shopping")]) | Final Score | Result |
|---| --- |---|---|
| Day 1 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 2 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 3 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 4 | 1.0000 | 1.0000 | ✅ Pass |
| Day 5 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 6 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 7 | 0.6000 | 0.6000 | ✅ Pass |
| Day 8 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 9 | 1.0000 | 1.0000 | ✅ Pass |
| Day 10 | 0.0000 | 0.0000 | ❌ Filtered Out |


### Query 007
**Query:** I just checked my spending and I'm way over budget. Cut the expensive dinners from the itinerary and I'll find cheaper alternatives later.

#### incontext
- **Operation:** DELETE
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 51.71s
- **Tokens:** 11,230 (6,416 / 4,814)

**Deleted Nodes:**

- `Day 1 > Canoe Restaurant`
- `Day 2 > Alo Restaurant`
- `Day 4 > Lee Restaurant`
- `Day 5 > Kaiseki Kaji`
- `Day 6 > The Keg Steakhouse`
- `Day 7 > Cluny Bistro`
- `Day 8 > Antler Kitchen`
- `Day 9 > Bar Isabel`

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day/Restaurant[atom(content =~ "dinner") AND atom(content =~ "expensive")]`
- **Result:** Deleted 3 nodes
- **Time:** 24.75s
- **Tokens:** 9,780 (7,624 / 2,156)

**Deleted Nodes:**

- `Root > Itinerary_Version 1 > Itinerary > Day 1 > Canoe Restaurant`
- `Root > Itinerary_Version 1 > Itinerary > Day 2 > Alo Restaurant`
- `Root > Itinerary_Version 1 > Itinerary > Day 5 > Kaiseki Kaji`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "dinner") AND atom(content =~ "expensive")`
**Threshold:** `0.5`

| Node | C1 (dinner) | C2 (expensive) | Final Score | Result |
|---| --- | --- |---|---|
| Canoe Restaurant | 0.9000 | 0.9000 | 0.9000 | ✅ Pass |
| Alo Restaurant | 0.9000 | 1.0000 | 0.9000 | ✅ Pass |
| Hotel Continental Breakfast | 0.0000 | 0.1000 | 0.0000 | ❌ Filtered Out (dinner) |
| FRANK Restaurant at AGO | 0.0000 | 0.3000 | 0.0000 | ❌ Filtered Out (dinner) |
| Pai Northern Thai | 0.8000 | 0.2000 | 0.2000 | ❌ Filtered Out (expensive) |
| Quick Grab Coffee | 0.0000 | 0.0000 | 0.0000 | ❌ Filtered Out (dinner) |
| Lee Restaurant | 0.8000 | 0.6000 | 0.6000 | ✅ Pass |
| Mildred's Temple Kitchen | 0.0000 | 0.2000 | 0.0000 | ❌ Filtered Out (dinner) |
| Kaiseki Kaji | 0.9000 | 0.9000 | 0.9000 | ✅ Pass |
| Sunset Grill | 0.0000 | 0.1000 | 0.0000 | ❌ Filtered Out (dinner) |
| Island Cafe Picnic Lunch | 0.0000 | 0.1000 | 0.0000 | ❌ Filtered Out (dinner) |
| The Keg Steakhouse | 0.9000 | 0.4000 | 0.4000 | ❌ Filtered Out (expensive) |
| Fran's Restaurant | 0.0000 | 0.0000 | 0.0000 | ❌ Filtered Out (dinner) |
| Eataly Toronto | 0.0000 | 0.3000 | 0.0000 | ❌ Filtered Out (dinner) |
| Cluny Bistro | 0.9000 | 0.5000 | 0.5000 | ✅ Pass |
| Elements on the Falls | 0.0000 | 0.2000 | 0.0000 | ❌ Filtered Out (dinner) |
| Antler Kitchen | 0.8000 | 0.5000 | 0.5000 | ✅ Pass |
| Lady Marmalade | 0.0000 | 0.2000 | 0.0000 | ❌ Filtered Out (dinner) |
| Urban Eatery Food Court | 0.0000 | 0.0000 | 0.0000 | ❌ Filtered Out (dinner) |
| Bar Isabel | 0.9000 | 0.4000 | 0.4000 | ❌ Filtered Out (expensive) |
| Hotel Quick Checkout Breakfast | 0.0000 | 0.0000 | 0.0000 | ❌ Filtered Out (dinner) |
| 360 Restaurant at CN Tower | 0.0000 | 0.5000 | 0.0000 | ❌ Filtered Out (dinner) |


### Query 008
**Query:** It's definitely going to rain all day on Day 7. Cancel any outdoor activities, I'll figure out replacements.

#### incontext
- **Operation:** DELETE
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 36.21s
- **Tokens:** 10,130 (5,461 / 4,669)

**Deleted Nodes:**

- `Day 7 > Distillery District Walk`

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day[7]/POI[atom(content =~ "outdoor")]`
- **Result:** Deleted 1 nodes
- **Time:** 5.29s
- **Tokens:** 3,712 (3,311 / 401)

**Deleted Nodes:**

- `Root > Itinerary_Version 1 > Itinerary > Day 7 > Distillery District Walk`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "outdoor")`
**Threshold:** `0.5`

| Node | C1 (outdoor) | Final Score | Result |
|---| --- |---|---|
| Royal Ontario Museum | 0.0000 | 0.0000 | ❌ Filtered Out |
| Distillery District Walk | 1.0000 | 1.0000 | ✅ Pass |
| Royal Ontario Museum | 0.0000 | 0.0000 | ❌ Filtered Out |
| Distillery District Walk | 1.0000 | 1.0000 | ✅ Pass |


### Query 009
**Query:** I actually went to the CN Tower on my last trip to Toronto. Remove any CN Tower activities. I'd rather do something new.

#### incontext
- **Operation:** DELETE
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 27.68s
- **Tokens:** 9,712 (5,330 / 4,382)

**Deleted Nodes:**

- `Day 10 > CN Tower EdgeWalk`
- `Day 10 > 360 Restaurant at CN Tower`

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day/POI[atom(content =~ "CN Tower")]`
- **Result:** Deleted 0 nodes
- **Time:** 17.79s
- **Tokens:** 9,587 (7,518 / 2,069)

**Scoring Analysis:**

**Predicate:** `atom(content =~ "CN Tower")`
**Threshold:** `0.5`

| Node | C1 (CN Tower) | Final Score | Result |
|---| --- |---|---|
| YYZ Airport Arrival | 0.0000 | 0.0000 | ❌ Filtered Out |
| Harbourfront Stroll | 0.0000 | 0.0000 | ❌ Filtered Out |
| Client Kickoff Meeting | 0.0000 | 0.0000 | ❌ Filtered Out |
| Strategy Workshop | 0.0000 | 0.0000 | ❌ Filtered Out |
| Stakeholder Presentation | 0.0000 | 0.0000 | ❌ Filtered Out |
| Art Gallery of Ontario | 0.0000 | 0.0000 | ❌ Filtered Out |
| Full-Day Workshop | 0.0000 | 0.0000 | ❌ Filtered Out |
| Bloor Street Shopping | 0.0000 | 0.0000 | ❌ Filtered Out |
| Client Check-in Call | 0.0000 | 0.0000 | ❌ Filtered Out |
| Email Catch-up Block | 0.0000 | 0.0000 | ❌ Filtered Out |
| Networking Drinks | 0.0000 | 0.0000 | ❌ Filtered Out |
| Toronto Islands Ferry and Bike Ride | 0.0000 | 0.0000 | ❌ Filtered Out |
| Ripley's Aquarium | 0.0000 | 0.0000 | ❌ Filtered Out |
| Royal Ontario Museum | 0.0000 | 0.0000 | ❌ Filtered Out |
| Distillery District Walk | 0.0000 | 0.0000 | ❌ Filtered Out |
| Niagara Falls Day Trip | 0.0000 | 0.0000 | ❌ Filtered Out |
| Eaton Centre Shopping | 0.0000 | 0.0000 | ❌ Filtered Out |
| Queen Street West Boutiques | 0.0000 | 0.0000 | ❌ Filtered Out |
| CN Tower EdgeWalk | 0.0000 | 0.0000 | ❌ Filtered Out |
| Airport Snack Stop | 0.0000 | 0.0000 | ❌ Filtered Out |
| YYZ Departure | 0.0000 | 0.0000 | ❌ Filtered Out |
| YYZ Airport Arrival | 0.0000 | 0.0000 | ❌ Filtered Out |
| Harbourfront Stroll | 0.0000 | 0.0000 | ❌ Filtered Out |
| Client Kickoff Meeting | 0.0000 | 0.0000 | ❌ Filtered Out |
| Strategy Workshop | 0.0000 | 0.0000 | ❌ Filtered Out |
| Stakeholder Presentation | 0.0000 | 0.0000 | ❌ Filtered Out |
| Art Gallery of Ontario | 0.0000 | 0.0000 | ❌ Filtered Out |
| Full-Day Workshop | 0.0000 | 0.0000 | ❌ Filtered Out |
| Bloor Street Shopping | 0.0000 | 0.0000 | ❌ Filtered Out |
| Client Check-in Call | 0.0000 | 0.0000 | ❌ Filtered Out |
| Email Catch-up Block | 0.0000 | 0.0000 | ❌ Filtered Out |
| Networking Drinks | 0.0000 | 0.0000 | ❌ Filtered Out |
| Toronto Islands Ferry and Bike Ride | 0.0000 | 0.0000 | ❌ Filtered Out |
| Ripley's Aquarium | 0.0000 | 0.0000 | ❌ Filtered Out |
| Royal Ontario Museum | 0.0000 | 0.0000 | ❌ Filtered Out |
| Distillery District Walk | 0.0000 | 0.0000 | ❌ Filtered Out |
| Niagara Falls Day Trip | 0.0000 | 0.0000 | ❌ Filtered Out |
| Eaton Centre Shopping | 0.0000 | 0.0000 | ❌ Filtered Out |
| Queen Street West Boutiques | 0.0000 | 0.0000 | ❌ Filtered Out |
| CN Tower EdgeWalk | 0.0000 | 0.0000 | ❌ Filtered Out |
| Airport Snack Stop | 0.0000 | 0.0000 | ❌ Filtered Out |
| YYZ Departure | 0.0000 | 0.0000 | ❌ Filtered Out |
| YYZ Airport Arrival | 0.0000 | 0.0000 | ❌ Filtered Out |
| Harbourfront Stroll | 0.0000 | 0.0000 | ❌ Filtered Out |
| Client Kickoff Meeting | 0.0000 | 0.0000 | ❌ Filtered Out |
| Strategy Workshop | 0.0000 | 0.0000 | ❌ Filtered Out |
| Stakeholder Presentation | 0.0000 | 0.0000 | ❌ Filtered Out |
| Art Gallery of Ontario | 0.0000 | 0.0000 | ❌ Filtered Out |
| Full-Day Workshop | 0.0000 | 0.0000 | ❌ Filtered Out |
| Bloor Street Shopping | 0.0000 | 0.0000 | ❌ Filtered Out |
| Client Check-in Call | 0.0000 | 0.0000 | ❌ Filtered Out |
| Email Catch-up Block | 0.0000 | 0.0000 | ❌ Filtered Out |
| Networking Drinks | 0.0000 | 0.0000 | ❌ Filtered Out |
| Toronto Islands Ferry and Bike Ride | 0.0000 | 0.0000 | ❌ Filtered Out |
| Ripley's Aquarium | 0.0000 | 0.0000 | ❌ Filtered Out |
| Royal Ontario Museum | 0.0000 | 0.0000 | ❌ Filtered Out |
| Niagara Falls Day Trip | 0.0000 | 0.0000 | ❌ Filtered Out |
| Eaton Centre Shopping | 0.0000 | 0.0000 | ❌ Filtered Out |
| Queen Street West Boutiques | 0.0000 | 0.0000 | ❌ Filtered Out |
| CN Tower EdgeWalk | 0.0000 | 0.0000 | ❌ Filtered Out |
| Airport Snack Stop | 0.0000 | 0.0000 | ❌ Filtered Out |
| YYZ Departure | 0.0000 | 0.0000 | ❌ Filtered Out |


### Query 010
**Query:** Bad news. my friend who was going to host me at Niagara just tested positive for COVID. I need to cancel the Niagara Falls trip.

#### incontext
- **Operation:** DELETE
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 26.48s
- **Tokens:** 9,155 (5,071 / 4,084)

**Deleted Nodes:**

- `Day 8 > Niagara Falls Day Trip`
- `Day 8 > Elements on the Falls`

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day/POI[atom(content =~ "Niagara Falls")]`
- **Result:** Deleted 0 nodes
- **Time:** 22.45s
- **Tokens:** 9,593 (7,523 / 2,070)

**Scoring Analysis:**

**Predicate:** `atom(content =~ "Niagara Falls")`
**Threshold:** `0.5`

| Node | C1 (Niagara Falls) | Final Score | Result |
|---| --- |---|---|
| YYZ Airport Arrival | 0.0000 | 0.0000 | ❌ Filtered Out |
| Harbourfront Stroll | 0.0000 | 0.0000 | ❌ Filtered Out |
| Client Kickoff Meeting | 0.0000 | 0.0000 | ❌ Filtered Out |
| Strategy Workshop | 0.0000 | 0.0000 | ❌ Filtered Out |
| Stakeholder Presentation | 0.0000 | 0.0000 | ❌ Filtered Out |
| Art Gallery of Ontario | 0.0000 | 0.0000 | ❌ Filtered Out |
| Full-Day Workshop | 0.0000 | 0.0000 | ❌ Filtered Out |
| Bloor Street Shopping | 0.0000 | 0.0000 | ❌ Filtered Out |
| Client Check-in Call | 0.0000 | 0.0000 | ❌ Filtered Out |
| Email Catch-up Block | 0.0000 | 0.0000 | ❌ Filtered Out |
| Networking Drinks | 0.0000 | 0.0000 | ❌ Filtered Out |
| Toronto Islands Ferry and Bike Ride | 0.0000 | 0.0000 | ❌ Filtered Out |
| Ripley's Aquarium | 0.0000 | 0.0000 | ❌ Filtered Out |
| Royal Ontario Museum | 0.0000 | 0.0000 | ❌ Filtered Out |
| Distillery District Walk | 0.0000 | 0.0000 | ❌ Filtered Out |
| Niagara Falls Day Trip | 0.0000 | 0.0000 | ❌ Filtered Out |
| Eaton Centre Shopping | 0.0000 | 0.0000 | ❌ Filtered Out |
| Queen Street West Boutiques | 0.0000 | 0.0000 | ❌ Filtered Out |
| CN Tower EdgeWalk | 0.0000 | 0.0000 | ❌ Filtered Out |
| Airport Snack Stop | 0.0000 | 0.0000 | ❌ Filtered Out |
| YYZ Departure | 0.0000 | 0.0000 | ❌ Filtered Out |
| YYZ Airport Arrival | 0.0000 | 0.0000 | ❌ Filtered Out |
| Harbourfront Stroll | 0.0000 | 0.0000 | ❌ Filtered Out |
| Client Kickoff Meeting | 0.0000 | 0.0000 | ❌ Filtered Out |
| Strategy Workshop | 0.0000 | 0.0000 | ❌ Filtered Out |
| Stakeholder Presentation | 0.0000 | 0.0000 | ❌ Filtered Out |
| Art Gallery of Ontario | 0.0000 | 0.0000 | ❌ Filtered Out |
| Full-Day Workshop | 0.0000 | 0.0000 | ❌ Filtered Out |
| Bloor Street Shopping | 0.0000 | 0.0000 | ❌ Filtered Out |
| Client Check-in Call | 0.0000 | 0.0000 | ❌ Filtered Out |
| Email Catch-up Block | 0.0000 | 0.0000 | ❌ Filtered Out |
| Networking Drinks | 0.0000 | 0.0000 | ❌ Filtered Out |
| Toronto Islands Ferry and Bike Ride | 0.0000 | 0.0000 | ❌ Filtered Out |
| Ripley's Aquarium | 0.0000 | 0.0000 | ❌ Filtered Out |
| Royal Ontario Museum | 0.0000 | 0.0000 | ❌ Filtered Out |
| Distillery District Walk | 0.0000 | 0.0000 | ❌ Filtered Out |
| Niagara Falls Day Trip | 0.0000 | 0.0000 | ❌ Filtered Out |
| Eaton Centre Shopping | 0.0000 | 0.0000 | ❌ Filtered Out |
| Queen Street West Boutiques | 0.0000 | 0.0000 | ❌ Filtered Out |
| CN Tower EdgeWalk | 0.0000 | 0.0000 | ❌ Filtered Out |
| Airport Snack Stop | 0.0000 | 0.0000 | ❌ Filtered Out |
| YYZ Departure | 0.0000 | 0.0000 | ❌ Filtered Out |
| YYZ Airport Arrival | 0.0000 | 0.0000 | ❌ Filtered Out |
| Harbourfront Stroll | 0.0000 | 0.0000 | ❌ Filtered Out |
| Client Kickoff Meeting | 0.0000 | 0.0000 | ❌ Filtered Out |
| Strategy Workshop | 0.0000 | 0.0000 | ❌ Filtered Out |
| Stakeholder Presentation | 0.0000 | 0.0000 | ❌ Filtered Out |
| Art Gallery of Ontario | 0.0000 | 0.0000 | ❌ Filtered Out |
| Full-Day Workshop | 0.0000 | 0.0000 | ❌ Filtered Out |
| Bloor Street Shopping | 0.0000 | 0.0000 | ❌ Filtered Out |
| Client Check-in Call | 0.0000 | 0.0000 | ❌ Filtered Out |
| Email Catch-up Block | 0.0000 | 0.0000 | ❌ Filtered Out |
| Networking Drinks | 0.0000 | 0.0000 | ❌ Filtered Out |
| Toronto Islands Ferry and Bike Ride | 0.0000 | 0.0000 | ❌ Filtered Out |
| Ripley's Aquarium | 0.0000 | 0.0000 | ❌ Filtered Out |
| Royal Ontario Museum | 0.0000 | 0.0000 | ❌ Filtered Out |
| Niagara Falls Day Trip | 0.0000 | 0.0000 | ❌ Filtered Out |
| Eaton Centre Shopping | 0.0000 | 0.0000 | ❌ Filtered Out |
| Queen Street West Boutiques | 0.0000 | 0.0000 | ❌ Filtered Out |
| CN Tower EdgeWalk | 0.0000 | 0.0000 | ❌ Filtered Out |
| Airport Snack Stop | 0.0000 | 0.0000 | ❌ Filtered Out |
| YYZ Departure | 0.0000 | 0.0000 | ❌ Filtered Out |


### Query 011
**Query:** I'm exhausted. I'm going to take Day 5 as a personal day and skip all the work stuff. Cancel every work-related activity on that day.

#### incontext
- **Operation:** DELETE
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 24.15s
- **Tokens:** 8,638 (4,804 / 3,834)

**Deleted Nodes:**

- `Day 5 > Client Check-in Call`
- `Day 5 > Email Catch-up Block`

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day[5]/POI[atom(content =~ "work related")]`
- **Result:** Deleted 2 nodes
- **Time:** 8.06s
- **Tokens:** 5,323 (4,416 / 907)

**Deleted Nodes:**

- `Root > Itinerary_Version 1 > Itinerary > Day 5 > Client Check-in Call`
- `Root > Itinerary_Version 1 > Itinerary > Day 5 > Email Catch-up Block`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "work related")`
**Threshold:** `0.5`

| Node | C1 (work related) | Final Score | Result |
|---| --- |---|---|
| Client Check-in Call | 1.0000 | 1.0000 | ✅ Pass |
| Email Catch-up Block | 1.0000 | 1.0000 | ✅ Pass |
| Networking Drinks | 0.8000 | 0.8000 | ✅ Pass |
| Client Check-in Call | 1.0000 | 1.0000 | ✅ Pass |
| Email Catch-up Block | 1.0000 | 1.0000 | ✅ Pass |
| Networking Drinks | 0.8000 | 0.8000 | ✅ Pass |
| Client Check-in Call | 1.0000 | 1.0000 | ✅ Pass |
| Email Catch-up Block | 1.0000 | 1.0000 | ✅ Pass |
| Networking Drinks | 0.8000 | 0.8000 | ✅ Pass |


### Query 012
**Query:** I just noticed Day 2 has no breakfast, my first meeting is at 9am and I'll be starving. Add a quick hotel breakfast before the meeting.

#### incontext
- **Operation:** CREATE
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 25.23s
- **Tokens:** 8,531 (4,580 / 3,951)

**Created Nodes:**

**Path:** `Day 2 > Hotel Quick Breakfast`

#### semantic_xpath
- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day[2]`
- **Result:** Created at Itinerary > Day 2/POI
- **Time:** 5.18s
- **Tokens:** 3,353 (3,167 / 186)

**Created Nodes:**

**Path:** `Itinerary > Day 2/POI`
- **Name:** Hotel Breakfast
- **Time:** 7:30 AM - 8:30 AM
- **Cost:** CAD 20-30
- **Description:** Quick breakfast at the hotel buffet to start the day with a variety of options including continental and hot breakfast items.
- **Highlights:** Convenient location, Variety of breakfast options, Quick service


### Query 013
**Query:** The workshop on Day 3 ends at 11am and then I have nothing until the AGO at noon. Add a coffee break in between. there's a good cafe near the gallery.

#### incontext
- **Operation:** CREATE
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 27.50s
- **Tokens:** 8,811 (4,709 / 4,102)

**Created Nodes:**

**Path:** `Day 3 > Nearby Cafe Break`

#### semantic_xpath
- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day[3]`
- **Result:** Created at Itinerary > Day 3/POI
- **Time:** 4.83s
- **Tokens:** 4,512 (4,314 / 198)

**Created Nodes:**

**Path:** `Itinerary > Day 3/POI`
- **Name:** AGO Cafe
- **Time:** 11:00 AM - 11:45 AM
- **Cost:** CAD 10-15
- **Description:** A cozy cafe located near the Art Gallery of Ontario, perfect for a quick coffee break before exploring the museum.
- **Highlights:** Proximity to AGO, Relaxing atmosphere, Quality coffee


### Query 014
**Query:** I completely forgot about souvenirs. Add a stop at Roots or the Hudson's Bay flagship on Day 10 morning before the CN Tower. I need to grab gifts before I fly out.

#### incontext
- **Operation:** CREATE
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 45.54s
- **Tokens:** 9,058 (4,837 / 4,221)

**Created Nodes:**

**Path:** `Day 10 > Hudson's Bay Flagship Shopping`

#### semantic_xpath
- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day[10]`
- **Result:** Created at Itinerary > Day 10/POI
- **Time:** 5.91s
- **Tokens:** 4,970 (4,748 / 222)

**Created Nodes:**

**Path:** `Itinerary > Day 10/POI`
- **Name:** Roots or Hudson's Bay Flagship
- **Time:** 8:30 AM - 9:30 AM
- **Cost:** CAD 50-100
- **Description:** Visit to Roots or Hudson's Bay flagship store to purchase souvenirs and gifts before departure. Convenient shopping stop with a variety of Canadian-themed items.
- **Highlights:** Souvenir shopping, Canadian-themed gifts, Convenient location

