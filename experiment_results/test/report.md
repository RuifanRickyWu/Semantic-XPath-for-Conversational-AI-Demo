# Experiment Report: test

## Summary

| Query ID | Pipeline | Operation | XPath / Logic | Result | Tokens (Total) | Time (s) |
|---|---|---|---|---|---|---|
| 001 | incontext | READ | `N/A (Full Tree)` |  | 5,783 (4,618 / 1,165) | 16.92 |
| 001 | semantic_xpath | READ | `/Itinerary/Day[not(agg_exists(POI[atom(content =~...` | Selected 0 nodes | 4,176 (4,081 / 95) | 26.14 |
| 002 | incontext | READ | `N/A (Full Tree)` |  | 4,799 (4,617 / 182) | 2.12 |
| 002 | semantic_xpath | READ | `/Itinerary/Day[7]/POI[atom(content =~ "outdoor")]` | Selected 1 nodes | 3,998 (3,897 / 101) | 3.40 |
| 003 | incontext | READ | `N/A (Full Tree)` |  | 4,991 (4,627 / 364) | 3.24 |
| 003 | semantic_xpath | READ | `/Itinerary/Day[6]/POI[atom(content =~ "fun for a kid")]` | Selected 2 nodes | 4,097 (3,950 / 147) | 3.37 |
| 004 | incontext | READ | `N/A (Full Tree)` |  | 4,903 (4,610 / 293) | 2.84 |
| 004 | semantic_xpath | READ | `/Itinerary/desc::Restaurant[atom(content =~ "expensive")]` | Selected 3 nodes | 4,404 (4,233 / 171) | 10.52 |
| 005 | incontext | READ | `N/A (Full Tree)` |  | 4,990 (4,616 / 374) | 3.10 |
| 005 | semantic_xpath | READ | `/Itinerary/Day[agg_exists(POI[atom(content =~ "nature")])]` | Selected 4 nodes | 5,718 (5,514 / 204) | 11.28 |
| 006 | incontext | READ | `N/A (Full Tree)` |  | 4,886 (4,605 / 281) | 2.56 |
| 006 | semantic_xpath | READ | `/Itinerary/Day[agg_exists(POI[atom(content =~ "sh...` | Selected 5 nodes | 4,395 (4,162 / 233) | 15.54 |
| 007 | incontext | DELETE | `N/A (Full Tree)` |  | 8,462 (4,619 / 3,843) | 33.02 |
| 007 | semantic_xpath | DELETE | `/Itinerary/Day/Restaurant[atom(content =~ "expens...` | Deleted 3 nodes | 4,599 (4,284 / 315) | 14.54 |
| 008 | incontext | DELETE | `N/A (Full Tree)` |  | 8,454 (4,589 / 3,865) | 31.15 |
| 008 | semantic_xpath | DELETE | `/Itinerary/Day[7]/POI[atom(content =~ "outdoor")]` | Deleted 1 nodes | 4,343 (4,143 / 200) | 4.90 |
| 009 | incontext | DELETE | `N/A (Full Tree)` |  | 8,163 (4,595 / 3,568) | 31.73 |
| 009 | semantic_xpath | DELETE | `/Itinerary/Day/POI[atom(content =~ "CN Tower")]` | Deleted 1 nodes | 4,269 (4,066 / 203) | 20.10 |
| 010 | incontext | DELETE | `N/A (Full Tree)` |  | 7,884 (4,327 / 3,557) | 17.64 |
| 010 | semantic_xpath | DELETE | `/Itinerary/Day/POI[atom(content =~ "Niagara Falls")]` | Deleted 1 nodes | 4,620 (4,335 / 285) | 25.88 |
| 011 | incontext | DELETE | `N/A (Full Tree)` |  | 7,912 (4,338 / 3,574) | 18.25 |
| 011 | semantic_xpath | DELETE | `/Itinerary/Day[5]/POI[atom(content =~ "work related")]` | Deleted 1 nodes | 4,530 (4,242 / 288) | 8.43 |
| 012 | incontext | CREATE | `N/A (Full Tree)` |  | 8,049 (4,342 / 3,707) | 29.49 |
| 012 | semantic_xpath | CREATE | `/Itinerary/Day[2]` | Created at Itinerary > Day 2/Restaurant | 5,331 (5,147 / 184) | 4.49 |
| 013 | incontext | CREATE | `N/A (Full Tree)` |  | 8,310 (4,470 / 3,840) | 33.17 |
| 013 | semantic_xpath | CREATE | `/Itinerary/Day[3]` | Created at Itinerary > Day 3/POI | 6,327 (6,122 / 205) | 4.73 |
| 014 | incontext | CREATE | `N/A (Full Tree)` |  | 8,431 (4,597 / 3,834) | 20.52 |
| 014 | semantic_xpath | CREATE | `/Itinerary/Day[10]` | Created at Itinerary > Day 10/POI | 6,217 (6,001 / 216) | 4.08 |

## Detailed Results
### Query 001
**Query:** My friend lives in Mississauga, about an hour from downtown. What days are without any work commitments or flights?

#### incontext
- **Operation:** READ
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 16.92s
- **Tokens:** 5,783 (4,618 / 1,165)

**Selected Nodes:**

1. **Day** -> Index: 3
2.   - **Restaurant** -> Hotel Continental Breakfast (7:30 AM - 8:30 AM, CAD 25, Walk)
3.   - **Restaurant** -> FRANK Restaurant at AGO (2:00 PM - 3:00 PM, CAD 35-50, Walk)
4.   - **Restaurant** -> Pai Northern Thai (7:00 PM - 8:30 PM, CAD 30-45, Public Transit)
5.   - **POI** -> Art Gallery of Ontario (12:00 PM - 2:00 PM, CAD 25, Walk)
6. **Day** -> Index: 6
7.   - **Restaurant** -> Sunset Grill (9:00 AM - 10:00 AM, CAD 20-30, Walk)
8.   - **Restaurant** -> Island Cafe Picnic Lunch (1:30 PM - 2:30 PM, CAD 25, Walk)
9.   - **POI** -> Toronto Islands Ferry and Bike Ride (10:30 AM - 1:30 PM, CAD 35, Walk and Ferry)
10.   - **POI** -> Ripley's Aquarium (3:30 PM - 5:30 PM, CAD 45, Ferry and Walk)

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[not(agg_exists(POI[atom(content =~ "work") OR atom(content =~ "flight")]))]`
- **Result:** Selected 0 nodes
- **Time:** 26.14s
- **Tokens:** 4,176 (4,081 / 95)

**Scoring Analysis:**

**Predicate:** `not(agg_exists(POI[atom(content =~ "work") OR atom(content =~ "flight")]))`
**Threshold:** `0.1`

| Node | Inner Score | Final Score | Result |
|---| --- |---|---|
| Day 1 | 0.9984 | 0.0016 | ❌ Filtered Out (Matches constraint) |
| Day 2 | 0.9999 | 0.0001 | ❌ Filtered Out (Matches constraint) |
| Day 3 | 0.9999 | 0.0001 | ❌ Filtered Out (Matches constraint) |
| Day 4 | 0.9998 | 0.0002 | ❌ Filtered Out (Matches constraint) |
| Day 5 | 0.9999 | 0.0001 | ❌ Filtered Out (Matches constraint) |
| Day 6 | 0.9593 | 0.0407 | ❌ Filtered Out (Matches constraint) |
| Day 7 | 0.9365 | 0.0635 | ❌ Filtered Out (Matches constraint) |
| Day 8 | 0.9080 | 0.0920 | ❌ Filtered Out (Matches constraint) |
| Day 9 | 0.8030 | 0.1970 | ✅ Pass |
| Day 10 | 0.9997 | 0.0003 | ❌ Filtered Out (Matches constraint) |


### Query 002
**Query:** The weather forecast shows heavy rain on Day 7. Which activities are outdoors that I might need to reschedule?

#### incontext
- **Operation:** READ
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 2.12s
- **Tokens:** 4,799 (4,617 / 182)

**Selected Nodes:**

1. **POI** -> Queen Street West Boutiques (3:00 PM - 5:00 PM, Variable, Walk)
2.   - **highlights** -> 

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[7]/POI[atom(content =~ "outdoor")]`
- **Result:** Selected 1 nodes
- **Time:** 3.40s
- **Tokens:** 3,998 (3,897 / 101)

**Selected Nodes:**

1. **POI** -> Distillery District Walk (3:00 PM - 5:00 PM, Free, Public Transit, {})

**Scoring Analysis:**

**Predicate:** `atom(content =~ "outdoor")`
**Threshold:** `0.1`

| Node | C1 (outdoor) | Final Score | Result |
|---| --- |---|---|
| Royal Ontario Museum | 0.1170 | 0.1170 | ✅ Pass |
| Distillery District Walk | 0.9981 | 0.9981 | ✅ Pass |


### Query 003
**Query:** My sister and nephew are joining me on Day 6. He's 10 years old. What activities do I already have planned that would be fun for a kid?

#### incontext
- **Operation:** READ
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 3.24s
- **Tokens:** 4,991 (4,627 / 364)

**Selected Nodes:**

1. **POI** -> Toronto Islands Ferry and Bike Ride (10:30 AM - 1:30 PM, CAD 35, Walk and Ferry)
2.   - **highlights** -> 
3. **POI** -> Ripley's Aquarium (3:30 PM - 5:30 PM, CAD 45, Ferry and Walk)
4.   - **highlights** -> 

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[6]/POI[atom(content =~ "fun for a kid")]`
- **Result:** Selected 2 nodes
- **Time:** 3.37s
- **Tokens:** 4,097 (3,950 / 147)

**Selected Nodes:**

1. **POI** -> Ripley's Aquarium (3:30 PM - 5:30 PM, CAD 45, Ferry and Walk, {})
2. **POI** -> Toronto Islands Ferry and Bike Ride (10:30 AM - 1:30 PM, CAD 35, Walk and Ferry, {})

**Scoring Analysis:**

**Predicate:** `atom(content =~ "fun for a kid")`
**Threshold:** `0.1`

| Node | C1 (fun for a kid) | Final Score | Result |
|---| --- |---|---|
| Toronto Islands Ferry and Bike Ride | 0.9990 | 0.9990 | ✅ Pass |
| Ripley's Aquarium | 0.9996 | 0.9996 | ✅ Pass |


### Query 004
**Query:** I'm putting together my expense report. What are the most expensive restaurants I've booked?

#### incontext
- **Operation:** READ
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 2.84s
- **Tokens:** 4,903 (4,610 / 293)

**Selected Nodes:**

1. **Restaurant** -> FRANK Restaurant at AGO (2:00 PM - 3:00 PM, CAD 35-50, Walk)
2.   - **highlights** -> 
3. **Restaurant** -> Eataly Toronto (12:30 PM - 1:30 PM, CAD 35-50, Walk)
4.   - **highlights** -> 

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/desc::Restaurant[atom(content =~ "expensive")]`
- **Result:** Selected 3 nodes
- **Time:** 10.52s
- **Tokens:** 4,404 (4,233 / 171)

**Selected Nodes:**

1. **Restaurant** -> Kaiseki Kaji (8:00 PM - 10:00 PM, CAD 250-350, Taxi, {})
2. **Restaurant** -> Alo Restaurant (7:00 PM - 9:30 PM, CAD 300-400, Taxi, {})
3. **Restaurant** -> Canoe Restaurant (7:30 PM - 9:00 PM, CAD 150-200, Taxi, {})

**Scoring Analysis:**

**Predicate:** `atom(content =~ "expensive")`
**Threshold:** `0.1`

| Node | C1 (expensive) | Final Score | Result |
|---| --- |---|---|
| Canoe Restaurant | 0.9978 | 0.9978 | ✅ Pass |
| Alo Restaurant | 0.9982 | 0.9982 | ✅ Pass |
| Hotel Continental Breakfast | 0.1213 | 0.1213 | ✅ Pass |
| FRANK Restaurant at AGO | 0.9310 | 0.9310 | ✅ Pass |
| Pai Northern Thai | 0.9373 | 0.9373 | ✅ Pass |
| Quick Grab Coffee | 0.4355 | 0.4355 | ✅ Pass |
| Lee Restaurant | 0.9826 | 0.9826 | ✅ Pass |
| Mildred's Temple Kitchen | 0.9468 | 0.9468 | ✅ Pass |
| Kaiseki Kaji | 0.9987 | 0.9987 | ✅ Pass |
| Sunset Grill | 0.3724 | 0.3724 | ✅ Pass |
| Island Cafe Picnic Lunch | 0.7898 | 0.7898 | ✅ Pass |
| The Keg Steakhouse | 0.7176 | 0.7176 | ✅ Pass |
| Fran's Restaurant | 0.5388 | 0.5388 | ✅ Pass |
| Eataly Toronto | 0.9085 | 0.9085 | ✅ Pass |
| Cluny Bistro | 0.9631 | 0.9631 | ✅ Pass |
| Elements on the Falls | 0.9610 | 0.9610 | ✅ Pass |
| Antler Kitchen | 0.9850 | 0.9850 | ✅ Pass |
| Lady Marmalade | 0.9775 | 0.9775 | ✅ Pass |
| Urban Eatery Food Court | 0.1900 | 0.1900 | ✅ Pass |
| Bar Isabel | 0.8872 | 0.8872 | ✅ Pass |
| Hotel Quick Checkout Breakfast | 0.6455 | 0.6455 | ✅ Pass |
| 360 Restaurant at CN Tower | 0.9896 | 0.9896 | ✅ Pass |


### Query 005
**Query:** I've been stuck in meetings most of the week. Which days have nature activities where I can actually get outside?

#### incontext
- **Operation:** READ
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 3.10s
- **Tokens:** 4,990 (4,616 / 374)

**Selected Nodes:**

1. **Day** -> Index: 1
2.   - **POI** -> Harbourfront Stroll (5:00 PM - 6:30 PM, Free, Walk)
3. **Day** -> Index: 6
4.   - **POI** -> Toronto Islands Ferry and Bike Ride (10:30 AM - 1:30 PM, CAD 35, Walk and Ferry)

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[agg_exists(POI[atom(content =~ "nature")])]`
- **Result:** Selected 4 nodes
- **Time:** 11.28s
- **Tokens:** 5,718 (5,514 / 204)

**Selected Nodes:**

1. **Day** ->  ({'index': '8'})
2. **Day** ->  ({'index': '6'})
3. **Day** ->  ({'index': '1'})
4. **Day** ->  ({'index': '7'})

**Scoring Analysis:**

**Predicate:** `agg_exists(POI[atom(content =~ "nature")])`
**Threshold:** `0.1`

| Node | C1 (nature) | Final Score | Result |
|---| --- |---|---|
| Day 1 | 0.9874 | 0.9874 | ✅ Pass |
| Day 2 | 0.2128 | 0.2128 | ✅ Pass |
| Day 3 | 0.7987 | 0.7987 | ✅ Pass |
| Day 4 | 0.6491 | 0.6491 | ✅ Pass |
| Day 5 | 0.0431 | 0.0431 | ❌ Filtered Out |
| Day 6 | 0.9992 | 0.9992 | ✅ Pass |
| Day 7 | 0.9981 | 0.9981 | ✅ Pass |
| Day 8 | 0.9994 | 0.9994 | ✅ Pass |
| Day 9 | 0.9455 | 0.9455 | ✅ Pass |
| Day 10 | 0.8239 | 0.8239 | ✅ Pass |


### Query 006
**Query:** Where do i go for breakfast on a shopping day?

#### incontext
- **Operation:** READ
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 2.56s
- **Tokens:** 4,886 (4,605 / 281)

**Selected Nodes:**

1. **Restaurant** -> Quick Grab Coffee (7:00 AM - 7:30 AM, CAD 8, Walk)
2.   - **highlights** -> 
3. **Restaurant** -> Hotel Quick Checkout Breakfast (7:30 AM - 8:15 AM, CAD 15, Walk)
4.   - **highlights** -> 

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[agg_exists(POI[atom(content =~ "shopping")])]/Restaurant[atom(content =~ "breakfast")]`
- **Result:** Selected 5 nodes
- **Time:** 15.54s
- **Tokens:** 4,395 (4,162 / 233)

**Selected Nodes:**

1. **Restaurant** -> Hotel Continental Breakfast (7:30 AM - 8:30 AM, CAD 25, Walk, {})
2. **Restaurant** -> Sunset Grill (9:00 AM - 10:00 AM, CAD 20-30, Walk, {})
3. **Restaurant** -> Fran's Restaurant (8:30 AM - 9:30 AM, CAD 20, Walk, {})
4. **Restaurant** -> Lady Marmalade (9:00 AM - 10:30 AM, CAD 25-35, Taxi, {})
5. **Restaurant** -> Hotel Quick Checkout Breakfast (7:30 AM - 8:15 AM, CAD 15, Walk, {})

**Scoring Analysis:**

**Predicate:** `agg_exists(POI[atom(content =~ "shopping")])`
**Threshold:** `0.1`

| Node | C1 (shopping) | Final Score | Result |
|---| --- |---|---|
| Day 1 | 0.0025 | 0.0025 | ❌ Filtered Out |
| Day 2 | 0.0007 | 0.0007 | ❌ Filtered Out |
| Day 3 | 0.0028 | 0.0028 | ❌ Filtered Out |
| Day 4 | 0.9998 | 0.9998 | ✅ Pass |
| Day 5 | 0.0008 | 0.0008 | ❌ Filtered Out |
| Day 6 | 0.0131 | 0.0131 | ❌ Filtered Out |
| Day 7 | 0.0358 | 0.0358 | ❌ Filtered Out |
| Day 8 | 0.0017 | 0.0017 | ❌ Filtered Out |
| Day 9 | 0.9996 | 0.9996 | ✅ Pass |
| Day 10 | 0.0068 | 0.0068 | ❌ Filtered Out |


### Query 007
**Query:** I just checked my spending and I'm way over budget. Cut the expensive dinners from the itinerary and I'll find cheaper alternatives later.

#### incontext
- **Operation:** DELETE
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 33.02s
- **Tokens:** 8,462 (4,619 / 3,843)

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day/Restaurant[atom(content =~ "expensive dinner")]`
- **Result:** Deleted 3 nodes
- **Time:** 14.54s
- **Tokens:** 4,599 (4,284 / 315)

**Deleted Nodes:**

- `Root > Itinerary_Version 1 > Itinerary > Day 2 > Alo Restaurant`
- `Root > Itinerary_Version 1 > Itinerary > Day 5 > Kaiseki Kaji`
- `Root > Itinerary_Version 1 > Itinerary > Day 1 > Canoe Restaurant`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "expensive dinner")`
**Threshold:** `0.1`

| Node | C1 (expensive dinner) | Final Score | Result |
|---| --- |---|---|
| Canoe Restaurant | 0.9979 | 0.9979 | ✅ Pass |
| Alo Restaurant | 0.9990 | 0.9990 | ✅ Pass |
| Hotel Continental Breakfast | 0.0008 | 0.0008 | ❌ Filtered Out |
| FRANK Restaurant at AGO | 0.5450 | 0.5450 | ✅ Pass |
| Pai Northern Thai | 0.7968 | 0.7968 | ✅ Pass |
| Quick Grab Coffee | 0.0006 | 0.0006 | ❌ Filtered Out |
| Lee Restaurant | 0.9867 | 0.9867 | ✅ Pass |
| Mildred's Temple Kitchen | 0.0067 | 0.0067 | ❌ Filtered Out |
| Kaiseki Kaji | 0.9987 | 0.9987 | ✅ Pass |
| Sunset Grill | 0.0028 | 0.0028 | ❌ Filtered Out |
| Island Cafe Picnic Lunch | 0.0041 | 0.0041 | ❌ Filtered Out |
| The Keg Steakhouse | 0.3927 | 0.3927 | ✅ Pass |
| Fran's Restaurant | 0.0018 | 0.0018 | ❌ Filtered Out |
| Eataly Toronto | 0.0188 | 0.0188 | ❌ Filtered Out |
| Cluny Bistro | 0.9509 | 0.9509 | ✅ Pass |
| Elements on the Falls | 0.8184 | 0.8184 | ✅ Pass |
| Antler Kitchen | 0.9540 | 0.9540 | ✅ Pass |
| Lady Marmalade | 0.0067 | 0.0067 | ❌ Filtered Out |
| Urban Eatery Food Court | 0.0038 | 0.0038 | ❌ Filtered Out |
| Bar Isabel | 0.3521 | 0.3521 | ✅ Pass |
| Hotel Quick Checkout Breakfast | 0.0012 | 0.0012 | ❌ Filtered Out |
| 360 Restaurant at CN Tower | 0.0791 | 0.0791 | ❌ Filtered Out |


### Query 008
**Query:** It's definitely going to rain all day on Day 7. Cancel any outdoor activities, I'll figure out replacements.

#### incontext
- **Operation:** DELETE
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 31.15s
- **Tokens:** 8,454 (4,589 / 3,865)

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day[7]/POI[atom(content =~ "outdoor")]`
- **Result:** Deleted 1 nodes
- **Time:** 4.90s
- **Tokens:** 4,343 (4,143 / 200)

**Deleted Nodes:**

- `Root > Itinerary_Version 1 > Itinerary > Day 7 > Distillery District Walk`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "outdoor")`
**Threshold:** `0.1`

| Node | C1 (outdoor) | Final Score | Result |
|---| --- |---|---|
| Royal Ontario Museum | 0.1170 | 0.1170 | ✅ Pass |
| Distillery District Walk | 0.9981 | 0.9981 | ✅ Pass |
| Royal Ontario Museum | 0.1170 | 0.1170 | ✅ Pass |
| Distillery District Walk | 0.9981 | 0.9981 | ✅ Pass |


### Query 009
**Query:** I actually went to the CN Tower on my last trip to Toronto. Remove any CN Tower activities. I'd rather do something new.

#### incontext
- **Operation:** DELETE
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 31.73s
- **Tokens:** 8,163 (4,595 / 3,568)

**Deleted Nodes:**

- `Day 9 > Queen Street West Boutiques`
- `Day 10 > CN Tower EdgeWalk`

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day/POI[atom(content =~ "CN Tower")]`
- **Result:** Deleted 1 nodes
- **Time:** 20.10s
- **Tokens:** 4,269 (4,066 / 203)

**Deleted Nodes:**

- `Root > Itinerary_Version 1 > Itinerary > Day 10 > CN Tower EdgeWalk`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "CN Tower")`
**Threshold:** `0.1`

| Node | C1 (CN Tower) | Final Score | Result |
|---| --- |---|---|
| YYZ Airport Arrival | 0.0157 | 0.0157 | ❌ Filtered Out |
| Harbourfront Stroll | 0.0028 | 0.0028 | ❌ Filtered Out |
| Client Kickoff Meeting | 0.0271 | 0.0271 | ❌ Filtered Out |
| Strategy Workshop | 0.0544 | 0.0544 | ❌ Filtered Out |
| Stakeholder Presentation | 0.0555 | 0.0555 | ❌ Filtered Out |
| Art Gallery of Ontario | 0.0196 | 0.0196 | ❌ Filtered Out |
| Full-Day Workshop | 0.0777 | 0.0777 | ❌ Filtered Out |
| Bloor Street Shopping | 0.0023 | 0.0023 | ❌ Filtered Out |
| Client Check-in Call | 0.0506 | 0.0506 | ❌ Filtered Out |
| Email Catch-up Block | 0.0082 | 0.0082 | ❌ Filtered Out |
| Networking Drinks | 0.0389 | 0.0389 | ❌ Filtered Out |
| Toronto Islands Ferry and Bike Ride | 0.0229 | 0.0229 | ❌ Filtered Out |
| Ripley's Aquarium | 0.0024 | 0.0024 | ❌ Filtered Out |
| Royal Ontario Museum | 0.0120 | 0.0120 | ❌ Filtered Out |
| Distillery District Walk | 0.0023 | 0.0023 | ❌ Filtered Out |
| Niagara Falls Day Trip | 0.0023 | 0.0023 | ❌ Filtered Out |
| Eaton Centre Shopping | 0.0032 | 0.0032 | ❌ Filtered Out |
| Queen Street West Boutiques | 0.0048 | 0.0048 | ❌ Filtered Out |
| CN Tower EdgeWalk | 0.9995 | 0.9995 | ✅ Pass |
| Airport Snack Stop | 0.0157 | 0.0157 | ❌ Filtered Out |
| YYZ Departure | 0.0597 | 0.0597 | ❌ Filtered Out |
| YYZ Airport Arrival | 0.0157 | 0.0157 | ❌ Filtered Out |
| Harbourfront Stroll | 0.0028 | 0.0028 | ❌ Filtered Out |
| Client Kickoff Meeting | 0.0271 | 0.0271 | ❌ Filtered Out |
| Strategy Workshop | 0.0544 | 0.0544 | ❌ Filtered Out |
| Stakeholder Presentation | 0.0555 | 0.0555 | ❌ Filtered Out |
| Art Gallery of Ontario | 0.0196 | 0.0196 | ❌ Filtered Out |
| Full-Day Workshop | 0.0777 | 0.0777 | ❌ Filtered Out |
| Bloor Street Shopping | 0.0023 | 0.0023 | ❌ Filtered Out |
| Client Check-in Call | 0.0506 | 0.0506 | ❌ Filtered Out |
| Email Catch-up Block | 0.0082 | 0.0082 | ❌ Filtered Out |
| Networking Drinks | 0.0389 | 0.0389 | ❌ Filtered Out |
| Toronto Islands Ferry and Bike Ride | 0.0229 | 0.0229 | ❌ Filtered Out |
| Ripley's Aquarium | 0.0024 | 0.0024 | ❌ Filtered Out |
| Royal Ontario Museum | 0.0120 | 0.0120 | ❌ Filtered Out |
| Distillery District Walk | 0.0023 | 0.0023 | ❌ Filtered Out |
| Niagara Falls Day Trip | 0.0023 | 0.0023 | ❌ Filtered Out |
| Eaton Centre Shopping | 0.0032 | 0.0032 | ❌ Filtered Out |
| Queen Street West Boutiques | 0.0048 | 0.0048 | ❌ Filtered Out |
| CN Tower EdgeWalk | 0.9995 | 0.9995 | ✅ Pass |
| Airport Snack Stop | 0.0157 | 0.0157 | ❌ Filtered Out |
| YYZ Departure | 0.0597 | 0.0597 | ❌ Filtered Out |
| YYZ Airport Arrival | 0.0157 | 0.0157 | ❌ Filtered Out |
| Harbourfront Stroll | 0.0028 | 0.0028 | ❌ Filtered Out |
| Client Kickoff Meeting | 0.0271 | 0.0271 | ❌ Filtered Out |
| Strategy Workshop | 0.0544 | 0.0544 | ❌ Filtered Out |
| Stakeholder Presentation | 0.0555 | 0.0555 | ❌ Filtered Out |
| Art Gallery of Ontario | 0.0196 | 0.0196 | ❌ Filtered Out |
| Full-Day Workshop | 0.0777 | 0.0777 | ❌ Filtered Out |
| Bloor Street Shopping | 0.0023 | 0.0023 | ❌ Filtered Out |
| Client Check-in Call | 0.0506 | 0.0506 | ❌ Filtered Out |
| Email Catch-up Block | 0.0082 | 0.0082 | ❌ Filtered Out |
| Networking Drinks | 0.0389 | 0.0389 | ❌ Filtered Out |
| Toronto Islands Ferry and Bike Ride | 0.0229 | 0.0229 | ❌ Filtered Out |
| Ripley's Aquarium | 0.0024 | 0.0024 | ❌ Filtered Out |
| Royal Ontario Museum | 0.0120 | 0.0120 | ❌ Filtered Out |
| Niagara Falls Day Trip | 0.0023 | 0.0023 | ❌ Filtered Out |
| Eaton Centre Shopping | 0.0032 | 0.0032 | ❌ Filtered Out |
| Queen Street West Boutiques | 0.0048 | 0.0048 | ❌ Filtered Out |
| CN Tower EdgeWalk | 0.9995 | 0.9995 | ✅ Pass |
| Airport Snack Stop | 0.0157 | 0.0157 | ❌ Filtered Out |
| YYZ Departure | 0.0597 | 0.0597 | ❌ Filtered Out |


### Query 010
**Query:** Bad news. my friend who was going to host me at Niagara just tested positive for COVID. I need to cancel the Niagara Falls trip.

#### incontext
- **Operation:** DELETE
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 17.64s
- **Tokens:** 7,884 (4,327 / 3,557)

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day/POI[atom(content =~ "Niagara Falls")]`
- **Result:** Deleted 1 nodes
- **Time:** 25.88s
- **Tokens:** 4,620 (4,335 / 285)

**Deleted Nodes:**

- `Root > Itinerary_Version 1 > Itinerary > Day 8 > Niagara Falls Day Trip`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "Niagara Falls")`
**Threshold:** `0.1`

| Node | C1 (Niagara Falls) | Final Score | Result |
|---| --- |---|---|
| YYZ Airport Arrival | 0.0024 | 0.0024 | ❌ Filtered Out |
| Harbourfront Stroll | 0.0104 | 0.0104 | ❌ Filtered Out |
| Client Kickoff Meeting | 0.0125 | 0.0125 | ❌ Filtered Out |
| Strategy Workshop | 0.0448 | 0.0448 | ❌ Filtered Out |
| Stakeholder Presentation | 0.0300 | 0.0300 | ❌ Filtered Out |
| Art Gallery of Ontario | 0.1759 | 0.1759 | ✅ Pass |
| Full-Day Workshop | 0.1064 | 0.1064 | ✅ Pass |
| Bloor Street Shopping | 0.0030 | 0.0030 | ❌ Filtered Out |
| Client Check-in Call | 0.0372 | 0.0372 | ❌ Filtered Out |
| Email Catch-up Block | 0.0059 | 0.0059 | ❌ Filtered Out |
| Networking Drinks | 0.0211 | 0.0211 | ❌ Filtered Out |
| Toronto Islands Ferry and Bike Ride | 0.0123 | 0.0123 | ❌ Filtered Out |
| Ripley's Aquarium | 0.0471 | 0.0471 | ❌ Filtered Out |
| Royal Ontario Museum | 0.0648 | 0.0648 | ❌ Filtered Out |
| Distillery District Walk | 0.0063 | 0.0063 | ❌ Filtered Out |
| Niagara Falls Day Trip | 0.9997 | 0.9997 | ✅ Pass |
| Eaton Centre Shopping | 0.0097 | 0.0097 | ❌ Filtered Out |
| Queen Street West Boutiques | 0.0145 | 0.0145 | ❌ Filtered Out |
| CN Tower EdgeWalk | 0.0071 | 0.0071 | ❌ Filtered Out |
| Airport Snack Stop | 0.0360 | 0.0360 | ❌ Filtered Out |
| YYZ Departure | 0.1150 | 0.1150 | ✅ Pass |
| YYZ Airport Arrival | 0.0024 | 0.0024 | ❌ Filtered Out |
| Harbourfront Stroll | 0.0104 | 0.0104 | ❌ Filtered Out |
| Client Kickoff Meeting | 0.0125 | 0.0125 | ❌ Filtered Out |
| Strategy Workshop | 0.0448 | 0.0448 | ❌ Filtered Out |
| Stakeholder Presentation | 0.0300 | 0.0300 | ❌ Filtered Out |
| Art Gallery of Ontario | 0.1759 | 0.1759 | ✅ Pass |
| Full-Day Workshop | 0.1064 | 0.1064 | ✅ Pass |
| Bloor Street Shopping | 0.0030 | 0.0030 | ❌ Filtered Out |
| Client Check-in Call | 0.0372 | 0.0372 | ❌ Filtered Out |
| Email Catch-up Block | 0.0059 | 0.0059 | ❌ Filtered Out |
| Networking Drinks | 0.0211 | 0.0211 | ❌ Filtered Out |
| Toronto Islands Ferry and Bike Ride | 0.0123 | 0.0123 | ❌ Filtered Out |
| Ripley's Aquarium | 0.0471 | 0.0471 | ❌ Filtered Out |
| Royal Ontario Museum | 0.0648 | 0.0648 | ❌ Filtered Out |
| Distillery District Walk | 0.0063 | 0.0063 | ❌ Filtered Out |
| Niagara Falls Day Trip | 0.9997 | 0.9997 | ✅ Pass |
| Eaton Centre Shopping | 0.0097 | 0.0097 | ❌ Filtered Out |
| Queen Street West Boutiques | 0.0145 | 0.0145 | ❌ Filtered Out |
| CN Tower EdgeWalk | 0.0071 | 0.0071 | ❌ Filtered Out |
| Airport Snack Stop | 0.0360 | 0.0360 | ❌ Filtered Out |
| YYZ Departure | 0.1150 | 0.1150 | ✅ Pass |
| YYZ Airport Arrival | 0.0024 | 0.0024 | ❌ Filtered Out |
| Harbourfront Stroll | 0.0104 | 0.0104 | ❌ Filtered Out |
| Client Kickoff Meeting | 0.0125 | 0.0125 | ❌ Filtered Out |
| Strategy Workshop | 0.0448 | 0.0448 | ❌ Filtered Out |
| Stakeholder Presentation | 0.0300 | 0.0300 | ❌ Filtered Out |
| Art Gallery of Ontario | 0.1759 | 0.1759 | ✅ Pass |
| Full-Day Workshop | 0.1064 | 0.1064 | ✅ Pass |
| Bloor Street Shopping | 0.0030 | 0.0030 | ❌ Filtered Out |
| Client Check-in Call | 0.0372 | 0.0372 | ❌ Filtered Out |
| Email Catch-up Block | 0.0059 | 0.0059 | ❌ Filtered Out |
| Networking Drinks | 0.0211 | 0.0211 | ❌ Filtered Out |
| Toronto Islands Ferry and Bike Ride | 0.0123 | 0.0123 | ❌ Filtered Out |
| Ripley's Aquarium | 0.0471 | 0.0471 | ❌ Filtered Out |
| Royal Ontario Museum | 0.0648 | 0.0648 | ❌ Filtered Out |
| Niagara Falls Day Trip | 0.9997 | 0.9997 | ✅ Pass |
| Eaton Centre Shopping | 0.0097 | 0.0097 | ❌ Filtered Out |
| Queen Street West Boutiques | 0.0145 | 0.0145 | ❌ Filtered Out |
| CN Tower EdgeWalk | 0.0071 | 0.0071 | ❌ Filtered Out |
| Airport Snack Stop | 0.0360 | 0.0360 | ❌ Filtered Out |
| YYZ Departure | 0.1150 | 0.1150 | ✅ Pass |
| YYZ Airport Arrival | 0.0024 | 0.0024 | ❌ Filtered Out |
| Harbourfront Stroll | 0.0104 | 0.0104 | ❌ Filtered Out |
| Client Kickoff Meeting | 0.0125 | 0.0125 | ❌ Filtered Out |
| Strategy Workshop | 0.0448 | 0.0448 | ❌ Filtered Out |
| Stakeholder Presentation | 0.0300 | 0.0300 | ❌ Filtered Out |
| Art Gallery of Ontario | 0.1759 | 0.1759 | ✅ Pass |
| Full-Day Workshop | 0.1064 | 0.1064 | ✅ Pass |
| Bloor Street Shopping | 0.0030 | 0.0030 | ❌ Filtered Out |
| Client Check-in Call | 0.0372 | 0.0372 | ❌ Filtered Out |
| Email Catch-up Block | 0.0059 | 0.0059 | ❌ Filtered Out |
| Networking Drinks | 0.0211 | 0.0211 | ❌ Filtered Out |
| Toronto Islands Ferry and Bike Ride | 0.0123 | 0.0123 | ❌ Filtered Out |
| Ripley's Aquarium | 0.0471 | 0.0471 | ❌ Filtered Out |
| Royal Ontario Museum | 0.0648 | 0.0648 | ❌ Filtered Out |
| Niagara Falls Day Trip | 0.9997 | 0.9997 | ✅ Pass |
| Eaton Centre Shopping | 0.0097 | 0.0097 | ❌ Filtered Out |
| Queen Street West Boutiques | 0.0145 | 0.0145 | ❌ Filtered Out |
| Airport Snack Stop | 0.0360 | 0.0360 | ❌ Filtered Out |
| YYZ Departure | 0.1150 | 0.1150 | ✅ Pass |


### Query 011
**Query:** I'm exhausted. I'm going to take Day 5 as a personal day and skip all the work stuff. Cancel every work-related activity on that day.

#### incontext
- **Operation:** DELETE
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 18.25s
- **Tokens:** 7,912 (4,338 / 3,574)

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day[5]/POI[atom(content =~ "work related")]`
- **Result:** Deleted 1 nodes
- **Time:** 8.43s
- **Tokens:** 4,530 (4,242 / 288)

**Deleted Nodes:**

- `Root > Itinerary_Version 1 > Itinerary > Day 5 > Email Catch-up Block`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "work related")`
**Threshold:** `0.1`

| Node | C1 (work related) | Final Score | Result |
|---| --- |---|---|
| Client Check-in Call | 0.9999 | 0.9999 | ✅ Pass |
| Email Catch-up Block | 0.9999 | 0.9999 | ✅ Pass |
| Networking Drinks | 0.9996 | 0.9996 | ✅ Pass |
| Client Check-in Call | 0.9999 | 0.9999 | ✅ Pass |
| Email Catch-up Block | 0.9999 | 0.9999 | ✅ Pass |
| Networking Drinks | 0.9996 | 0.9996 | ✅ Pass |
| Client Check-in Call | 0.9999 | 0.9999 | ✅ Pass |
| Email Catch-up Block | 0.9999 | 0.9999 | ✅ Pass |
| Networking Drinks | 0.9996 | 0.9996 | ✅ Pass |
| Client Check-in Call | 0.9999 | 0.9999 | ✅ Pass |
| Email Catch-up Block | 0.9999 | 0.9999 | ✅ Pass |
| Networking Drinks | 0.9996 | 0.9996 | ✅ Pass |
| Client Check-in Call | 0.9999 | 0.9999 | ✅ Pass |
| Email Catch-up Block | 0.9999 | 0.9999 | ✅ Pass |
| Networking Drinks | 0.9996 | 0.9996 | ✅ Pass |


### Query 012
**Query:** I just noticed Day 2 has no breakfast, my first meeting is at 9am and I'll be starving. Add a quick hotel breakfast before the meeting.

#### incontext
- **Operation:** CREATE
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 29.49s
- **Tokens:** 8,049 (4,342 / 3,707)

**Created Nodes:**

**Path:** `Day 2 > Hotel Quick Breakfast`

#### semantic_xpath
- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day[2]`
- **Result:** Created at Itinerary > Day 2/Restaurant
- **Time:** 4.49s
- **Tokens:** 5,331 (5,147 / 184)

**Created Nodes:**

**Path:** `Itinerary > Day 2/Restaurant`
- **Name:** Hotel Breakfast
- **Time:** 7:30 AM - 8:30 AM
- **Cost:** CAD 15-25
- **Description:** Quick breakfast at the hotel before heading to the meeting.
- **Highlights:** Convenient location, Quick service, Continental options


### Query 013
**Query:** The workshop on Day 3 ends at 11am and then I have nothing until the AGO at noon. Add a coffee break in between. there's a good cafe near the gallery.

#### incontext
- **Operation:** CREATE
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 33.17s
- **Tokens:** 8,310 (4,470 / 3,840)

**Created Nodes:**

**Path:** `Day 3 > Gallery Cafe`

#### semantic_xpath
- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day[3]`
- **Result:** Created at Itinerary > Day 3/POI
- **Time:** 4.73s
- **Tokens:** 6,327 (6,122 / 205)

**Created Nodes:**

**Path:** `Itinerary > Day 3/POI`
- **Name:** AGO Coffee Break
- **Time:** 11:00 AM - 11:45 AM
- **Cost:** CAD 10-15
- **Description:** Relaxing coffee break at a nearby cafe before visiting the Art Gallery of Ontario.
- **Highlights:** Proximity to AGO, Relaxing atmosphere


### Query 014
**Query:** I completely forgot about souvenirs. Add a stop at Roots or the Hudson's Bay flagship on Day 10 morning before the CN Tower. I need to grab gifts before I fly out.

#### incontext
- **Operation:** CREATE
- **Logic/XPath:** `N/A (Full Tree)`
- **Result:** 
- **Time:** 20.52s
- **Tokens:** 8,431 (4,597 / 3,834)

#### semantic_xpath
- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day[10]`
- **Result:** Created at Itinerary > Day 10/POI
- **Time:** 4.08s
- **Tokens:** 6,217 (6,001 / 216)

**Created Nodes:**

**Path:** `Itinerary > Day 10/POI`
- **Name:** Roots or Hudson's Bay Flagship
- **Time:** 8:30 AM - 9:30 AM
- **Cost:** Varies
- **Description:** Stop at Roots or the Hudson's Bay flagship store to purchase souvenirs and gifts before heading to the CN Tower.
- **Highlights:** Souvenir shopping, Canadian brands

