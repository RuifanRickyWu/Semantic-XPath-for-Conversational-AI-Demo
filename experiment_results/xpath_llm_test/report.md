# Experiment Report: xpath_llm_test

## Summary

| Query ID | Pipeline | Operation | XPath / Logic | Result | Tokens (Total) | Time (s) |
|---|---|---|---|---|---|---|
| 001 | semantic_xpath | READ | `/Itinerary/Day[not(agg_exists(POI[atom(content =~...` | Selected 3 nodes | 11,944 (10,181 / 1,763) | 29.78 |
| 002 | semantic_xpath | READ | `/Itinerary/Day[7]/POI[atom(content =~ "outdoor")]` | Selected 1 nodes | 4,659 (4,436 / 223) | 4.98 |
| 003 | semantic_xpath | READ | `/Itinerary/Day[6]/POI[atom(content =~ "fun for a kid")]` | Selected 2 nodes | 4,879 (4,619 / 260) | 6.01 |
| 004 | semantic_xpath | READ | `/Itinerary/desc::Restaurant[atom(content =~ "real...` | Selected 3 nodes | 8,077 (7,106 / 971) | 16.26 |
| 005 | semantic_xpath | READ | `/Itinerary/Day[agg_exists(POI[atom(content =~ "nature")])]` | Selected 4 nodes | 8,773 (7,791 / 982) | 20.07 |
| 006 | semantic_xpath | DELETE | `/Itinerary/Day/Restaurant[atom(content =~ "expens...` | Deleted 3 nodes | 8,342 (7,181 / 1,161) | 19.74 |
| 007 | semantic_xpath | DELETE | `/Itinerary/Day[7]/POI[atom(content =~ "outdoor")]` | Deleted 1 nodes | 5,066 (4,730 / 336) | 5.11 |
| 008 | semantic_xpath | DELETE | `/Itinerary/Day/POI[atom(content =~ "CN Tower")]` | Deleted 0 nodes | 10,841 (8,772 / 2,069) | 19.75 |
| 009 | semantic_xpath | DELETE | `/Itinerary/Day[POI[atom(content =~ "Niagara Falls")]]` | Deleted 3 nodes | 10,294 (8,958 / 1,336) | 12.67 |
| 010 | semantic_xpath | DELETE | `/Itinerary/Day[5]/POI[atom(content =~ "work related")]` | Deleted 3 nodes | 7,267 (6,178 / 1,089) | 10.29 |
| 011 | semantic_xpath | CREATE | `/Itinerary/Day[2]` | Created at Itinerary > Day 2/Restaurant | 5,335 (5,150 / 185) | 4.58 |
| 012 | semantic_xpath | CREATE | `/Itinerary/Day[3]` | Created at Itinerary > Day 3/POI | 6,699 (6,506 / 193) | 5.18 |
| 013 | semantic_xpath | CREATE | `/Itinerary/Day[9]` | Created at Itinerary > Day 9/Restaurant | 5,566 (5,366 / 200) | 5.26 |
| 014 | semantic_xpath | CREATE | `/Itinerary/Day[6]` | Created at Itinerary > Day 6/Restaurant | 7,332 (7,102 / 230) | 5.39 |
| 015 | semantic_xpath | CREATE | `/Itinerary/Day[10]` | Created at Itinerary > Day 10/POI | 5,605 (5,385 / 220) | 8.17 |

## Detailed Results
### Query 001
**Query:** My college friend lives in Mississauga, about an hour from downtown. What days are without any work commitments or flights.

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[not(agg_exists(POI[atom(content =~ "work commitment")])) AND not(agg_exists(POI[atom(content =~ "flight")]))]`
- **Result:** Selected 3 nodes
- **Time:** 29.78s
- **Tokens:** 11,944 (10,181 / 1,763)

**Selected Nodes:**

**1. Day**
- **Type:** Day
- **Reasoning:** Day 6 has no work commitments or flights.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 6`

**2. Day**
- **Type:** Day
- **Reasoning:** Day 7 has no work commitments or flights.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 7`

**3. Day**
- **Type:** Day
- **Reasoning:** Day 9 has no work commitments or flights.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 9`

**Scoring Analysis:**

**Predicate:** `not(agg_exists(POI[atom(content =~ "work commitment")])) AND not(agg_exists(POI[atom(content =~ "flight")]))`
**Threshold:** `0.01`

| Node | C1 (work commitment) | C2 (flight) | Final Score | Result |
|---| --- | --- |---|---|
| Day 1 | 1.0000 | 0.0000 | 0.0000 | ❌ Filtered Out (flight) |
| Day 2 | 0.0000 | 1.0000 | 0.0000 | ❌ Filtered Out (work commitment) |
| Day 3 | 0.0000 | 1.0000 | 0.0000 | ❌ Filtered Out (work commitment) |
| Day 4 | 0.0000 | 1.0000 | 0.0000 | ❌ Filtered Out (work commitment) |
| Day 5 | 0.1000 | 1.0000 | 0.1000 | ✅ Pass |
| Day 6 | 1.0000 | 1.0000 | 1.0000 | ✅ Pass |
| Day 7 | 1.0000 | 1.0000 | 1.0000 | ✅ Pass |
| Day 8 | 1.0000 | 1.0000 | 1.0000 | ✅ Pass |
| Day 9 | 1.0000 | 1.0000 | 1.0000 | ✅ Pass |
| Day 10 | 1.0000 | 0.0000 | 0.0000 | ❌ Filtered Out (flight) |


### Query 002
**Query:** The weather forecast shows heavy rain on Day 7. I want to check which activities are outdoors that I might need to reschedule.

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[7]/POI[atom(content =~ "outdoor")]`
- **Result:** Selected 1 nodes
- **Time:** 4.98s
- **Tokens:** 4,659 (4,436 / 223)

**Selected Nodes:**

**1. Distillery District Walk**
- **Name:** Distillery District Walk
- **Type:** POI
- **Time:** 3:00 PM - 5:00 PM
- **Cost:** Free
- **Description:** Historic pedestrian village with cobblestone streets, artisan shops, and galleries. Outdoor walking experience through restored Victorian industrial architecture.
- **Highlights:** Outdoor walking tour, Historic architecture, Artisan shops
- **Reasoning:** Distillery District Walk is an outdoor activity, as it involves walking through an outdoor historic pedestrian village.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 7 > Distillery District Walk`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "outdoor")`
**Threshold:** `0.01`

| Node | C1 (outdoor) | Final Score | Result |
|---| --- |---|---|
| Royal Ontario Museum | 0.0000 | 0.0000 | ❌ Filtered Out |
| Distillery District Walk | 1.0000 | 1.0000 | ✅ Pass |


### Query 003
**Query:** My sister and nephew are joining me on Day 6. He's 10 years old. What activities do I already have planned that would be fun for a kid?

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[6]/POI[atom(content =~ "fun for a kid")]`
- **Result:** Selected 2 nodes
- **Time:** 6.01s
- **Tokens:** 4,879 (4,619 / 260)

**Selected Nodes:**

**1. Ripley's Aquarium**
- **Name:** Ripley's Aquarium
- **Type:** POI
- **Time:** 3:30 PM - 5:30 PM
- **Cost:** CAD 45
- **Description:** World-class aquarium with underwater tunnel and interactive exhibits. Indoor family attraction perfect for kids. Sharks, jellyfish, and touch tanks.
- **Highlights:** Indoor attraction, Kid-friendly family activity, Marine life
- **Reasoning:** Ripley's Aquarium is a kid-friendly indoor attraction with interactive exhibits and marine life, making it fun for a 10-year-old.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 6 > Ripley's Aquarium`

**2. Toronto Islands Ferry and Bike Ride**
- **Name:** Toronto Islands Ferry and Bike Ride
- **Type:** POI
- **Time:** 10:30 AM - 1:30 PM
- **Cost:** CAD 35
- **Description:** Ferry ride to Toronto Islands followed by bike rental and exploration. Outdoor nature activity with beaches, gardens, and stunning skyline views. Perfect for families and kids.
- **Highlights:** Outdoor nature, Kid-friendly family activity, Bike riding, Beach access
- **Reasoning:** Toronto Islands Ferry and Bike Ride is a kid-friendly outdoor activity with bike riding and beach access, suitable for a 10-year-old.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 6 > Toronto Islands Ferry and Bike Ride`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "fun for a kid")`
**Threshold:** `0.01`

| Node | C1 (fun for a kid) | Final Score | Result |
|---| --- |---|---|
| Toronto Islands Ferry and Bike Ride | 0.9000 | 0.9000 | ✅ Pass |
| Ripley's Aquarium | 1.0000 | 1.0000 | ✅ Pass |


### Query 004
**Query:** I'm putting together my expense report. Can you show me all the restaurants I've booked that are really expensive

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/desc::Restaurant[atom(content =~ "really expensive")]`
- **Result:** Selected 3 nodes
- **Time:** 16.26s
- **Tokens:** 8,077 (7,106 / 971)

**Selected Nodes:**

**1. Alo Restaurant**
- **Name:** Alo Restaurant
- **Type:** Restaurant
- **Time:** 7:00 PM - 9:30 PM
- **Cost:** CAD 300-400
- **Description:** Three Michelin-starred French tasting menu. Extremely expensive and exclusive fine dining. Intimate 8-course experience with wine pairings. Very formal and upscale.
- **Highlights:** Expensive Michelin dining, Upscale French cuisine, Formal atmosphere
- **Reasoning:** Alo Restaurant is described as extremely expensive with a cost of CAD 300-400, fitting the 'really expensive' criteria.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Alo Restaurant`

**2. Kaiseki Kaji**
- **Name:** Kaiseki Kaji
- **Type:** Restaurant
- **Time:** 8:00 PM - 10:00 PM
- **Cost:** CAD 250-350
- **Description:** Exquisite Japanese kaiseki dining experience. Very expensive omakase with seasonal courses. Intimate and formal setting.
- **Highlights:** Expensive Japanese dining, Upscale omakase, Formal atmosphere
- **Reasoning:** Kaiseki Kaji is described as very expensive with a cost of CAD 250-350, fitting the 'really expensive' criteria.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Kaiseki Kaji`

**3. Canoe Restaurant**
- **Name:** Canoe Restaurant
- **Type:** Restaurant
- **Time:** 7:30 PM - 9:00 PM
- **Cost:** CAD 150-200
- **Description:** Upscale Canadian cuisine on the 54th floor of TD Tower. Expensive fine dining with panoramic city views. Elegant and formal atmosphere.
- **Highlights:** Expensive fine dining, City skyline views, Upscale atmosphere
- **Reasoning:** Canoe Restaurant is described as expensive with a cost of CAD 150-200, which is relatively high and fits the 'really expensive' criteria.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Canoe Restaurant`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "really expensive")`
**Threshold:** `0.01`

| Node | C1 (really expensive) | Final Score | Result |
|---| --- |---|---|
| Canoe Restaurant | 0.8000 | 0.8000 | ✅ Pass |
| Alo Restaurant | 1.0000 | 1.0000 | ✅ Pass |
| Hotel Continental Breakfast | 0.1000 | 0.1000 | ✅ Pass |
| FRANK Restaurant at AGO | 0.2000 | 0.2000 | ✅ Pass |
| Pai Northern Thai | 0.2000 | 0.2000 | ✅ Pass |
| Quick Grab Coffee | 0.0000 | 0.0000 | ❌ Filtered Out |
| Lee Restaurant | 0.5000 | 0.5000 | ✅ Pass |
| Mildred's Temple Kitchen | 0.2000 | 0.2000 | ✅ Pass |
| Kaiseki Kaji | 0.9000 | 0.9000 | ✅ Pass |
| Sunset Grill | 0.1000 | 0.1000 | ✅ Pass |
| Island Cafe Picnic Lunch | 0.1000 | 0.1000 | ✅ Pass |
| The Keg Steakhouse | 0.3000 | 0.3000 | ✅ Pass |
| Fran's Restaurant | 0.0000 | 0.0000 | ❌ Filtered Out |
| Eataly Toronto | 0.2000 | 0.2000 | ✅ Pass |
| Cluny Bistro | 0.4000 | 0.4000 | ✅ Pass |
| Elements on the Falls | 0.2000 | 0.2000 | ✅ Pass |
| Antler Kitchen | 0.5000 | 0.5000 | ✅ Pass |
| Lady Marmalade | 0.2000 | 0.2000 | ✅ Pass |
| Urban Eatery Food Court | 0.0000 | 0.0000 | ❌ Filtered Out |
| Bar Isabel | 0.3000 | 0.3000 | ✅ Pass |
| Hotel Quick Checkout Breakfast | 0.0000 | 0.0000 | ❌ Filtered Out |
| 360 Restaurant at CN Tower | 0.5000 | 0.5000 | ✅ Pass |


### Query 005
**Query:** I've been stuck in meetings most of the week. Which days have nature activities where I can actually get outside and see some green space?

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[agg_exists(POI[atom(content =~ "nature")])]`
- **Result:** Selected 4 nodes
- **Time:** 20.07s
- **Tokens:** 8,773 (7,791 / 982)

**Selected Nodes:**

**1. Day**
- **Type:** Day
- **Reasoning:** Day 6 includes the Toronto Islands Ferry and Bike Ride, which is an outdoor nature activity with beaches and gardens.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 6`

**2. Day**
- **Type:** Day
- **Reasoning:** Day 8 features a Niagara Falls Day Trip, which is an outdoor scenic adventure and nature activity.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 8`

**3. Day**
- **Type:** Day
- **Reasoning:** Day 1 includes a Harbourfront Stroll, which is an outdoor activity with lake views and fresh air.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 1`

**4. Day**
- **Type:** Day
- **Reasoning:** Day 7 includes a Distillery District Walk, which is an outdoor walking experience through a historic area.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 7`

**Scoring Analysis:**

**Predicate:** `agg_exists(POI[atom(content =~ "nature")])`
**Threshold:** `0.01`

| Node | C1 (nature) | Final Score | Result |
|---| --- |---|---|
| Day 1 | 0.7000 | 0.7000 | ✅ Pass |
| Day 2 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 3 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 4 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 5 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 6 | 1.0000 | 1.0000 | ✅ Pass |
| Day 7 | 0.4000 | 0.4000 | ✅ Pass |
| Day 8 | 1.0000 | 1.0000 | ✅ Pass |
| Day 9 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 10 | 0.3000 | 0.3000 | ✅ Pass |


### Query 006
**Query:** I just checked my spending and I'm way over budget. I need to cut the expensive dinners from the itinerary and find cheaper alternatives later.

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day/Restaurant[atom(content =~ "expensive dinner")]`
- **Result:** Deleted 3 nodes
- **Time:** 19.74s
- **Tokens:** 8,342 (7,181 / 1,161)

**Deleted Nodes:**

- `Root > Itinerary_Version 1 > Itinerary > Day 2 > Alo Restaurant`
- `Root > Itinerary_Version 1 > Itinerary > Day 1 > Canoe Restaurant`
- `Root > Itinerary_Version 1 > Itinerary > Day 5 > Kaiseki Kaji`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "expensive dinner")`
**Threshold:** `0.01`

| Node | C1 (expensive dinner) | Final Score | Result |
|---| --- |---|---|
| Canoe Restaurant | 0.9000 | 0.9000 | ✅ Pass |
| Alo Restaurant | 1.0000 | 1.0000 | ✅ Pass |
| Hotel Continental Breakfast | 0.0000 | 0.0000 | ❌ Filtered Out |
| FRANK Restaurant at AGO | 0.2000 | 0.2000 | ✅ Pass |
| Pai Northern Thai | 0.1000 | 0.1000 | ✅ Pass |
| Quick Grab Coffee | 0.0000 | 0.0000 | ❌ Filtered Out |
| Lee Restaurant | 0.5000 | 0.5000 | ✅ Pass |
| Mildred's Temple Kitchen | 0.0000 | 0.0000 | ❌ Filtered Out |
| Kaiseki Kaji | 0.9000 | 0.9000 | ✅ Pass |
| Sunset Grill | 0.0000 | 0.0000 | ❌ Filtered Out |
| Island Cafe Picnic Lunch | 0.0000 | 0.0000 | ❌ Filtered Out |
| The Keg Steakhouse | 0.3000 | 0.3000 | ✅ Pass |
| Fran's Restaurant | 0.0000 | 0.0000 | ❌ Filtered Out |
| Eataly Toronto | 0.2000 | 0.2000 | ✅ Pass |
| Cluny Bistro | 0.5000 | 0.5000 | ✅ Pass |
| Elements on the Falls | 0.1000 | 0.1000 | ✅ Pass |
| Antler Kitchen | 0.4000 | 0.4000 | ✅ Pass |
| Lady Marmalade | 0.0000 | 0.0000 | ❌ Filtered Out |
| Urban Eatery Food Court | 0.0000 | 0.0000 | ❌ Filtered Out |
| Bar Isabel | 0.3000 | 0.3000 | ✅ Pass |
| Hotel Quick Checkout Breakfast | 0.0000 | 0.0000 | ❌ Filtered Out |
| 360 Restaurant at CN Tower | 0.4000 | 0.4000 | ✅ Pass |


### Query 007
**Query:** It's definitely going to rain all day on Day 7. Cancel any outdoor activities, I'll figure out replacements.

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day[7]/POI[atom(content =~ "outdoor")]`
- **Result:** Deleted 1 nodes
- **Time:** 5.11s
- **Tokens:** 5,066 (4,730 / 336)

**Deleted Nodes:**

- `Root > Itinerary_Version 1 > Itinerary > Day 7 > Distillery District Walk`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "outdoor")`
**Threshold:** `0.01`

| Node | C1 (outdoor) | Final Score | Result |
|---| --- |---|---|
| Royal Ontario Museum | 0.0000 | 0.0000 | ❌ Filtered Out |
| Distillery District Walk | 1.0000 | 1.0000 | ✅ Pass |
| Royal Ontario Museum | 0.0000 | 0.0000 | ❌ Filtered Out |
| Distillery District Walk | 1.0000 | 1.0000 | ✅ Pass |


### Query 008
**Query:** I actually went to the CN Tower on my last trip to Toronto. Remove any CN Tower activities. I'd rather do something new.

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day/POI[atom(content =~ "CN Tower")]`
- **Result:** Deleted 0 nodes
- **Time:** 19.75s
- **Tokens:** 10,841 (8,772 / 2,069)

**Scoring Analysis:**

**Predicate:** `atom(content =~ "CN Tower")`
**Threshold:** `0.01`

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


### Query 009
**Query:** Bad news. my friend who was going to host me at Niagara just tested positive for COVID. I need to cancel the whole Niagara Falls day trip.

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day[POI[atom(content =~ "Niagara Falls")]]`
- **Result:** Deleted 3 nodes
- **Time:** 12.67s
- **Tokens:** 10,294 (8,958 / 1,336)

**Deleted Nodes:**

- `Root > Itinerary_Version 1 > Itinerary > Day 8`
- `Root > Itinerary_Version 2 > Itinerary > Day 8`
- `Root > Itinerary_Version 3 > Itinerary > Day 8`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "POI[atom(content =~ "Niagara Falls")]")`
**Threshold:** `0.01`

| Node | C1 (POI[atom(content =~ "Niagara Falls")]) | Final Score | Result |
|---| --- |---|---|
| Day 1 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 2 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 3 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 4 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 5 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 6 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 7 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 8 | 1.0000 | 1.0000 | ✅ Pass |
| Day 9 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 10 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 1 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 2 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 3 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 4 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 5 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 6 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 7 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 8 | 1.0000 | 1.0000 | ✅ Pass |
| Day 9 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 10 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 1 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 2 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 3 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 4 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 5 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 6 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 7 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 8 | 1.0000 | 1.0000 | ✅ Pass |
| Day 9 | 0.0000 | 0.0000 | ❌ Filtered Out |
| Day 10 | 0.0000 | 0.0000 | ❌ Filtered Out |


### Query 010
**Query:** I'm exhausted. I'm going to take Day 5 as a personal day and skip all the work stuff. Cancel every work-related activity on that day.

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day[5]/POI[atom(content =~ "work related")]`
- **Result:** Deleted 3 nodes
- **Time:** 10.29s
- **Tokens:** 7,267 (6,178 / 1,089)

**Deleted Nodes:**

- `Root > Itinerary_Version 1 > Itinerary > Day 5 > Client Check-in Call`
- `Root > Itinerary_Version 1 > Itinerary > Day 5 > Email Catch-up Block`
- `Root > Itinerary_Version 1 > Itinerary > Day 5 > Networking Drinks`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "work related")`
**Threshold:** `0.01`

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
| Client Check-in Call | 1.0000 | 1.0000 | ✅ Pass |
| Email Catch-up Block | 1.0000 | 1.0000 | ✅ Pass |
| Networking Drinks | 0.8000 | 0.8000 | ✅ Pass |


### Query 011
**Query:** I just noticed Day 2 has no breakfastâ€”my first meeting is at 9am and I'll be starving. Add a quick hotel breakfast before the meeting.

#### semantic_xpath
- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day[2]`
- **Result:** Created at Itinerary > Day 2/Restaurant
- **Time:** 4.58s
- **Tokens:** 5,335 (5,150 / 185)

**Created Nodes:**

**Path:** `Itinerary > Day 2/Restaurant`
- **Name:** Hotel Breakfast Buffet
- **Time:** 7:30 AM - 8:30 AM
- **Cost:** CAD 15-25
- **Description:** Quick and convenient breakfast at the hotel buffet before heading to the meeting.
- **Highlights:** Convenient location, Variety of breakfast options


### Query 012
**Query:** The workshop on Day 3 ends at 11am and then I have nothing until the AGO at noon. Add a coffee break in between. there's a good cafe near the gallery.

#### semantic_xpath
- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day[3]`
- **Result:** Created at Itinerary > Day 3/POI
- **Time:** 5.18s
- **Tokens:** 6,699 (6,506 / 193)

**Created Nodes:**

**Path:** `Itinerary > Day 3/POI`
- **Name:** AGO Coffee Break
- **Time:** 11:15 AM - 11:45 AM
- **Cost:** CAD 10-15
- **Description:** Relaxing coffee break at a nearby cafe before visiting the Art Gallery of Ontario.
- **Highlights:** Proximity to AGO, Relaxing atmosphere


### Query 013
**Query:** It's actually my wedding anniversary on Day 9. I want to add a special romantic dinner somewhere niceâ€”maybe Scaramouche with the city view.

#### semantic_xpath
- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day[9]`
- **Result:** Created at Itinerary > Day 9/Restaurant
- **Time:** 5.26s
- **Tokens:** 5,566 (5,366 / 200)

**Created Nodes:**

**Path:** `Itinerary > Day 9/Restaurant`
- **Name:** Scaramouche
- **Time:** 7:30 PM - 9:30 PM
- **Cost:** CAD 150-200
- **Description:** Special romantic dinner at Scaramouche with a stunning city view, perfect for celebrating a wedding anniversary.
- **Highlights:** Romantic atmosphere, City view, Fine dining


### Query 014
**Query:** My partner is arriving on Day 6 and she's vegetarian. Add a plant-based restaurant for dinner that nightâ€”I've heard Planta is good.

#### semantic_xpath
- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day[6]`
- **Result:** Created at Itinerary > Day 6/Restaurant
- **Time:** 5.39s
- **Tokens:** 7,332 (7,102 / 230)

**Created Nodes:**

**Path:** `Itinerary > Day 6/Restaurant`
- **Name:** Planta
- **Time:** 7:00 PM - 8:30 PM
- **Cost:** CAD 50-70
- **Description:** A chic plant-based restaurant offering innovative vegetarian and vegan dishes. Known for its creative menu and stylish ambiance.
- **Highlights:** Plant-based menu, Vegan options, Stylish ambiance


### Query 015
**Query:** I completely forgot about souvenirs. Add a stop at Roots or the Hudson's Bay flagship on Day 10 morning before the CN Tower. I need to grab gifts before I fly out.

#### semantic_xpath
- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day[10]`
- **Result:** Created at Itinerary > Day 10/POI
- **Time:** 8.17s
- **Tokens:** 5,605 (5,385 / 220)

**Created Nodes:**

**Path:** `Itinerary > Day 10/POI`
- **Name:** Roots or Hudson's Bay Flagship
- **Time:** 8:30 AM - 9:30 AM
- **Cost:** CAD 50-100
- **Description:** Stop at Roots or Hudson's Bay flagship store to purchase souvenirs and gifts before heading to the CN Tower.
- **Highlights:** Souvenir shopping, Iconic Canadian brands

