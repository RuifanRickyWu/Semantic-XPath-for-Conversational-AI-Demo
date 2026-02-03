# Experiment Report: xpath_entailment_test

## Summary

| Query ID | Pipeline | Operation | XPath / Logic | Result | Tokens (Total) | Time (s) |
|---|---|---|---|---|---|---|
| 001 | semantic_xpath | READ | `/Itinerary/Day[not(agg_exists(POI[atom(content =~...` | Selected 0 nodes | 5,351 (5,235 / 116) | 18.71 |
| 002 | semantic_xpath | READ | `/Itinerary/Day[7]/POI[atom(content =~ "outdoor")]` | Selected 1 nodes | 4,012 (3,909 / 103) | 4.57 |
| 003 | semantic_xpath | READ | `/Itinerary/Day[6]/POI[atom(content =~ "fun for a kid")]` | Selected 2 nodes | 4,095 (3,950 / 145) | 7.50 |
| 004 | semantic_xpath | READ | `/Itinerary/desc::Restaurant[atom(content =~ "real...` | Selected 3 nodes | 4,978 (4,789 / 189) | 11.33 |
| 005 | semantic_xpath | READ | `/Itinerary/Day[agg_exists(POI[atom(content =~ "nature")])]` | Selected 4 nodes | 7,583 (7,374 / 209) | 9.94 |
| 006 | semantic_xpath | DELETE | `/Itinerary/Day/Restaurant[atom(content =~ "expensive")]` | Deleted 3 nodes | 5,156 (4,863 / 293) | 12.41 |
| 007 | semantic_xpath | DELETE | `/Itinerary/Day[7]/POI[atom(content =~ "outdoor")]` | Deleted 1 nodes | 4,342 (4,143 / 199) | 6.63 |
| 008 | semantic_xpath | DELETE | `/Itinerary/Day/POI[atom(content =~ "CN Tower")]` | Deleted 1 nodes | 5,043 (4,791 / 252) | 22.88 |
| 009 | semantic_xpath | DELETE | `/Itinerary/Day[POI[atom(content =~ "Niagara Falls")]]` | Deleted 3 nodes | 6,785 (6,454 / 331) | 25.73 |
| 010 | semantic_xpath | DELETE | `/Itinerary/Day[5]/POI[atom(content =~ "work related")]` | Deleted 2 nodes | 5,293 (4,772 / 521) | 11.87 |
| 011 | semantic_xpath | CREATE | `/Itinerary/Day[2]` | Created at Itinerary > Day 2/Restaurant | 5,509 (5,328 / 181) | 5.02 |
| 012 | semantic_xpath | CREATE | `/Itinerary/Day[3]` | Created at Itinerary > Day 3/POI | 7,104 (6,899 / 205) | 5.06 |
| 013 | semantic_xpath | CREATE | `/Itinerary/Day[9]` | Created at Itinerary > Day 9/Restaurant | 5,968 (5,764 / 204) | 6.92 |
| 014 | semantic_xpath | CREATE | `/Itinerary/Day[6]` | Created at Itinerary > Day 6/Restaurant | 7,741 (7,522 / 219) | 6.36 |
| 015 | semantic_xpath | CREATE | `/Itinerary/Day[10]` | Created at Itinerary > Day 10/POI | 5,904 (5,693 / 211) | 5.89 |

## Detailed Results
### Query 001
**Query:** My college friend lives in Mississauga, about an hour from downtown. What days are without any work commitments or flights.

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[not(agg_exists(POI[atom(content =~ "work")])) AND not(agg_exists(POI[atom(content =~ "flight")]))]`
- **Result:** Selected 0 nodes
- **Time:** 18.71s
- **Tokens:** 5,351 (5,235 / 116)

**Scoring Analysis:**

**Predicate:** `not(agg_exists(POI[atom(content =~ "work")])) AND not(agg_exists(POI[atom(content =~ "flight")]))`
**Threshold:** `0.01`

| Node | C1 (work) | C2 (flight) | Final Score | Result |
|---| --- | --- |---|---|
| Day 1 | 0.0923 | 0.0016 | 0.0016 | ❌ Filtered Out (flight) |
| Day 2 | 0.0001 | 0.9470 | 0.0001 | ❌ Filtered Out (work) |
| Day 3 | 0.0001 | 0.8660 | 0.0001 | ❌ Filtered Out (work) |
| Day 4 | 0.0002 | 0.7961 | 0.0002 | ❌ Filtered Out (work) |
| Day 5 | 0.0001 | 0.8956 | 0.0001 | ❌ Filtered Out (work) |
| Day 6 | 0.0407 | 0.4609 | 0.0407 | ✅ Pass |
| Day 7 | 0.0635 | 0.5093 | 0.0635 | ✅ Pass |
| Day 8 | 0.0920 | 0.8973 | 0.0920 | ✅ Pass |
| Day 9 | 0.1970 | 0.9662 | 0.1970 | ✅ Pass |
| Day 10 | 0.0500 | 0.0003 | 0.0003 | ❌ Filtered Out (flight) |


### Query 002
**Query:** The weather forecast shows heavy rain on Day 7. I want to check which activities are outdoors that I might need to reschedule.

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[7]/POI[atom(content =~ "outdoor")]`
- **Result:** Selected 1 nodes
- **Time:** 4.57s
- **Tokens:** 4,012 (3,909 / 103)

**Selected Nodes:**

**1. Distillery District Walk**
- **Name:** Distillery District Walk
- **Type:** POI
- **Time:** 3:00 PM - 5:00 PM
- **Cost:** Free
- **Description:** Historic pedestrian village with cobblestone streets, artisan shops, and galleries. Outdoor walking experience through restored Victorian industrial architecture.
- **Highlights:** Outdoor walking tour, Historic architecture, Artisan shops
- **Reasoning:** Distillery District Walk is an outdoor activity, which may need rescheduling due to heavy rain.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 7 > Distillery District Walk`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "outdoor")`
**Threshold:** `0.01`

| Node | C1 (outdoor) | Final Score | Result |
|---| --- |---|---|
| Royal Ontario Museum | 0.1170 | 0.1170 | ✅ Pass |
| Distillery District Walk | 0.9981 | 0.9981 | ✅ Pass |


### Query 003
**Query:** My sister and nephew are joining me on Day 6. He's 10 years old. What activities do I already have planned that would be fun for a kid?

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[6]/POI[atom(content =~ "fun for a kid")]`
- **Result:** Selected 2 nodes
- **Time:** 7.50s
- **Tokens:** 4,095 (3,950 / 145)

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
- **Reasoning:** Toronto Islands Ferry and Bike Ride is an outdoor activity with bike riding and beach access, suitable and enjoyable for a child.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 6 > Toronto Islands Ferry and Bike Ride`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "fun for a kid")`
**Threshold:** `0.01`

| Node | C1 (fun for a kid) | Final Score | Result |
|---| --- |---|---|
| Toronto Islands Ferry and Bike Ride | 0.9990 | 0.9990 | ✅ Pass |
| Ripley's Aquarium | 0.9996 | 0.9996 | ✅ Pass |


### Query 004
**Query:** I'm putting together my expense report. Can you show me all the restaurants I've booked that are really expensive

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/desc::Restaurant[atom(content =~ "really expensive")]`
- **Result:** Selected 3 nodes
- **Time:** 11.33s
- **Tokens:** 4,978 (4,789 / 189)

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
| Canoe Restaurant | 0.9971 | 0.9971 | ✅ Pass |
| Alo Restaurant | 0.9989 | 0.9989 | ✅ Pass |
| Hotel Continental Breakfast | 0.0049 | 0.0049 | ❌ Filtered Out |
| FRANK Restaurant at AGO | 0.0531 | 0.0531 | ✅ Pass |
| Pai Northern Thai | 0.0595 | 0.0595 | ✅ Pass |
| Quick Grab Coffee | 0.0070 | 0.0070 | ❌ Filtered Out |
| Lee Restaurant | 0.3758 | 0.3758 | ✅ Pass |
| Mildred's Temple Kitchen | 0.1186 | 0.1186 | ✅ Pass |
| Kaiseki Kaji | 0.9988 | 0.9988 | ✅ Pass |
| Sunset Grill | 0.0059 | 0.0059 | ❌ Filtered Out |
| Island Cafe Picnic Lunch | 0.0115 | 0.0115 | ✅ Pass |
| The Keg Steakhouse | 0.0231 | 0.0231 | ✅ Pass |
| Fran's Restaurant | 0.0162 | 0.0162 | ✅ Pass |
| Eataly Toronto | 0.0780 | 0.0780 | ✅ Pass |
| Cluny Bistro | 0.2038 | 0.2038 | ✅ Pass |
| Elements on the Falls | 0.2220 | 0.2220 | ✅ Pass |
| Antler Kitchen | 0.3482 | 0.3482 | ✅ Pass |
| Lady Marmalade | 0.1644 | 0.1644 | ✅ Pass |
| Urban Eatery Food Court | 0.0074 | 0.0074 | ❌ Filtered Out |
| Bar Isabel | 0.0918 | 0.0918 | ✅ Pass |
| Hotel Quick Checkout Breakfast | 0.0207 | 0.0207 | ✅ Pass |
| 360 Restaurant at CN Tower | 0.3672 | 0.3672 | ✅ Pass |


### Query 005
**Query:** I've been stuck in meetings most of the week. Which days have nature activities where I can actually get outside and see some green space?

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[agg_exists(POI[atom(content =~ "nature")])]`
- **Result:** Selected 4 nodes
- **Time:** 9.94s
- **Tokens:** 7,583 (7,374 / 209)

**Selected Nodes:**

**1. Day**
- **Type:** Day
- **Reasoning:** Day 8 includes a Niagara Falls Day Trip, which is an outdoor scenic adventure and nature activity.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 8`

**2. Day**
- **Type:** Day
- **Reasoning:** Day 6 features a Toronto Islands Ferry and Bike Ride, which is an outdoor nature activity with beaches and gardens.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 6`

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
| Day 1 | 0.9874 | 0.9874 | ✅ Pass |
| Day 2 | 0.2128 | 0.2128 | ✅ Pass |
| Day 3 | 0.7987 | 0.7987 | ✅ Pass |
| Day 4 | 0.6491 | 0.6491 | ✅ Pass |
| Day 5 | 0.0431 | 0.0431 | ✅ Pass |
| Day 6 | 0.9992 | 0.9992 | ✅ Pass |
| Day 7 | 0.9981 | 0.9981 | ✅ Pass |
| Day 8 | 0.9994 | 0.9994 | ✅ Pass |
| Day 9 | 0.9455 | 0.9455 | ✅ Pass |
| Day 10 | 0.8239 | 0.8239 | ✅ Pass |


### Query 006
**Query:** I just checked my spending and I'm way over budget. I need to cut the expensive dinners from the itinerary and find cheaper alternatives later.

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day/Restaurant[atom(content =~ "expensive")]`
- **Result:** Deleted 3 nodes
- **Time:** 12.41s
- **Tokens:** 5,156 (4,863 / 293)

**Deleted Nodes:**

- `Root > Itinerary_Version 1 > Itinerary > Day 5 > Kaiseki Kaji`
- `Root > Itinerary_Version 1 > Itinerary > Day 2 > Alo Restaurant`
- `Root > Itinerary_Version 1 > Itinerary > Day 1 > Canoe Restaurant`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "expensive")`
**Threshold:** `0.01`

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


### Query 007
**Query:** It's definitely going to rain all day on Day 7. Cancel any outdoor activities, I'll figure out replacements.

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day[7]/POI[atom(content =~ "outdoor")]`
- **Result:** Deleted 1 nodes
- **Time:** 6.63s
- **Tokens:** 4,342 (4,143 / 199)

**Deleted Nodes:**

- `Root > Itinerary_Version 1 > Itinerary > Day 7 > Distillery District Walk`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "outdoor")`
**Threshold:** `0.01`

| Node | C1 (outdoor) | Final Score | Result |
|---| --- |---|---|
| Royal Ontario Museum | 0.1170 | 0.1170 | ✅ Pass |
| Distillery District Walk | 0.9981 | 0.9981 | ✅ Pass |
| Royal Ontario Museum | 0.1170 | 0.1170 | ✅ Pass |
| Distillery District Walk | 0.9981 | 0.9981 | ✅ Pass |


### Query 008
**Query:** I actually went to the CN Tower on my last trip to Toronto. Remove any CN Tower activities. I'd rather do something new.

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day/POI[atom(content =~ "CN Tower")]`
- **Result:** Deleted 1 nodes
- **Time:** 22.88s
- **Tokens:** 5,043 (4,791 / 252)

**Deleted Nodes:**

- `Root > Itinerary_Version 1 > Itinerary > Day 10 > CN Tower EdgeWalk`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "CN Tower")`
**Threshold:** `0.01`

| Node | C1 (CN Tower) | Final Score | Result |
|---| --- |---|---|
| YYZ Airport Arrival | 0.0157 | 0.0157 | ✅ Pass |
| Harbourfront Stroll | 0.0028 | 0.0028 | ❌ Filtered Out |
| Client Kickoff Meeting | 0.0271 | 0.0271 | ✅ Pass |
| Strategy Workshop | 0.0544 | 0.0544 | ✅ Pass |
| Stakeholder Presentation | 0.0555 | 0.0555 | ✅ Pass |
| Art Gallery of Ontario | 0.0196 | 0.0196 | ✅ Pass |
| Full-Day Workshop | 0.0777 | 0.0777 | ✅ Pass |
| Bloor Street Shopping | 0.0023 | 0.0023 | ❌ Filtered Out |
| Client Check-in Call | 0.0506 | 0.0506 | ✅ Pass |
| Email Catch-up Block | 0.0082 | 0.0082 | ❌ Filtered Out |
| Networking Drinks | 0.0389 | 0.0389 | ✅ Pass |
| Toronto Islands Ferry and Bike Ride | 0.0229 | 0.0229 | ✅ Pass |
| Ripley's Aquarium | 0.0024 | 0.0024 | ❌ Filtered Out |
| Royal Ontario Museum | 0.0120 | 0.0120 | ✅ Pass |
| Distillery District Walk | 0.0023 | 0.0023 | ❌ Filtered Out |
| Niagara Falls Day Trip | 0.0023 | 0.0023 | ❌ Filtered Out |
| Eaton Centre Shopping | 0.0032 | 0.0032 | ❌ Filtered Out |
| Queen Street West Boutiques | 0.0048 | 0.0048 | ❌ Filtered Out |
| CN Tower EdgeWalk | 0.9995 | 0.9995 | ✅ Pass |
| Airport Snack Stop | 0.0157 | 0.0157 | ✅ Pass |
| YYZ Departure | 0.0597 | 0.0597 | ✅ Pass |
| YYZ Airport Arrival | 0.0157 | 0.0157 | ✅ Pass |
| Harbourfront Stroll | 0.0028 | 0.0028 | ❌ Filtered Out |
| Client Kickoff Meeting | 0.0271 | 0.0271 | ✅ Pass |
| Strategy Workshop | 0.0544 | 0.0544 | ✅ Pass |
| Stakeholder Presentation | 0.0555 | 0.0555 | ✅ Pass |
| Art Gallery of Ontario | 0.0196 | 0.0196 | ✅ Pass |
| Full-Day Workshop | 0.0777 | 0.0777 | ✅ Pass |
| Bloor Street Shopping | 0.0023 | 0.0023 | ❌ Filtered Out |
| Client Check-in Call | 0.0506 | 0.0506 | ✅ Pass |
| Email Catch-up Block | 0.0082 | 0.0082 | ❌ Filtered Out |
| Networking Drinks | 0.0389 | 0.0389 | ✅ Pass |
| Toronto Islands Ferry and Bike Ride | 0.0229 | 0.0229 | ✅ Pass |
| Ripley's Aquarium | 0.0024 | 0.0024 | ❌ Filtered Out |
| Royal Ontario Museum | 0.0120 | 0.0120 | ✅ Pass |
| Distillery District Walk | 0.0023 | 0.0023 | ❌ Filtered Out |
| Niagara Falls Day Trip | 0.0023 | 0.0023 | ❌ Filtered Out |
| Eaton Centre Shopping | 0.0032 | 0.0032 | ❌ Filtered Out |
| Queen Street West Boutiques | 0.0048 | 0.0048 | ❌ Filtered Out |
| CN Tower EdgeWalk | 0.9995 | 0.9995 | ✅ Pass |
| Airport Snack Stop | 0.0157 | 0.0157 | ✅ Pass |
| YYZ Departure | 0.0597 | 0.0597 | ✅ Pass |
| YYZ Airport Arrival | 0.0157 | 0.0157 | ✅ Pass |
| Harbourfront Stroll | 0.0028 | 0.0028 | ❌ Filtered Out |
| Client Kickoff Meeting | 0.0271 | 0.0271 | ✅ Pass |
| Strategy Workshop | 0.0544 | 0.0544 | ✅ Pass |
| Stakeholder Presentation | 0.0555 | 0.0555 | ✅ Pass |
| Art Gallery of Ontario | 0.0196 | 0.0196 | ✅ Pass |
| Full-Day Workshop | 0.0777 | 0.0777 | ✅ Pass |
| Bloor Street Shopping | 0.0023 | 0.0023 | ❌ Filtered Out |
| Client Check-in Call | 0.0506 | 0.0506 | ✅ Pass |
| Email Catch-up Block | 0.0082 | 0.0082 | ❌ Filtered Out |
| Networking Drinks | 0.0389 | 0.0389 | ✅ Pass |
| Toronto Islands Ferry and Bike Ride | 0.0229 | 0.0229 | ✅ Pass |
| Ripley's Aquarium | 0.0024 | 0.0024 | ❌ Filtered Out |
| Royal Ontario Museum | 0.0120 | 0.0120 | ✅ Pass |
| Niagara Falls Day Trip | 0.0023 | 0.0023 | ❌ Filtered Out |
| Eaton Centre Shopping | 0.0032 | 0.0032 | ❌ Filtered Out |
| Queen Street West Boutiques | 0.0048 | 0.0048 | ❌ Filtered Out |
| CN Tower EdgeWalk | 0.9995 | 0.9995 | ✅ Pass |
| Airport Snack Stop | 0.0157 | 0.0157 | ✅ Pass |
| YYZ Departure | 0.0597 | 0.0597 | ✅ Pass |


### Query 009
**Query:** Bad news. my friend who was going to host me at Niagara just tested positive for COVID. I need to cancel the whole Niagara Falls day trip.

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day[POI[atom(content =~ "Niagara Falls")]]`
- **Result:** Deleted 3 nodes
- **Time:** 25.73s
- **Tokens:** 6,785 (6,454 / 331)

**Deleted Nodes:**

- `Root > Itinerary_Version 1 > Itinerary > Day 8`
- `Root > Itinerary_Version 2 > Itinerary > Day 8`
- `Root > Itinerary_Version 3 > Itinerary > Day 8`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "POI[atom(content =~ "Niagara Falls")]")`
**Threshold:** `0.01`

| Node | C1 (POI[atom(content =~ "Niagara Falls")]) | Final Score | Result |
|---| --- |---|---|
| Day 1 | 0.2996 | 0.2996 | ✅ Pass |
| Day 2 | 0.5471 | 0.5471 | ✅ Pass |
| Day 3 | 0.3796 | 0.3796 | ✅ Pass |
| Day 4 | 0.3592 | 0.3592 | ✅ Pass |
| Day 5 | 0.4790 | 0.4790 | ✅ Pass |
| Day 6 | 0.3272 | 0.3272 | ✅ Pass |
| Day 7 | 0.1601 | 0.1601 | ✅ Pass |
| Day 8 | 0.9777 | 0.9777 | ✅ Pass |
| Day 9 | 0.2512 | 0.2512 | ✅ Pass |
| Day 10 | 0.3709 | 0.3709 | ✅ Pass |
| Day 1 | 0.1666 | 0.1666 | ✅ Pass |
| Day 2 | 0.4169 | 0.4169 | ✅ Pass |
| Day 3 | 0.3796 | 0.3796 | ✅ Pass |
| Day 4 | 0.3592 | 0.3592 | ✅ Pass |
| Day 5 | 0.2646 | 0.2646 | ✅ Pass |
| Day 6 | 0.3272 | 0.3272 | ✅ Pass |
| Day 7 | 0.1601 | 0.1601 | ✅ Pass |
| Day 8 | 0.9777 | 0.9777 | ✅ Pass |
| Day 9 | 0.2512 | 0.2512 | ✅ Pass |
| Day 10 | 0.3709 | 0.3709 | ✅ Pass |
| Day 1 | 0.1666 | 0.1666 | ✅ Pass |
| Day 2 | 0.4169 | 0.4169 | ✅ Pass |
| Day 3 | 0.3796 | 0.3796 | ✅ Pass |
| Day 4 | 0.3592 | 0.3592 | ✅ Pass |
| Day 5 | 0.2646 | 0.2646 | ✅ Pass |
| Day 6 | 0.3272 | 0.3272 | ✅ Pass |
| Day 7 | 0.2085 | 0.2085 | ✅ Pass |
| Day 8 | 0.9777 | 0.9777 | ✅ Pass |
| Day 9 | 0.2512 | 0.2512 | ✅ Pass |
| Day 10 | 0.3709 | 0.3709 | ✅ Pass |
| Day 1 | 0.1666 | 0.1666 | ✅ Pass |
| Day 2 | 0.4169 | 0.4169 | ✅ Pass |
| Day 3 | 0.3796 | 0.3796 | ✅ Pass |
| Day 4 | 0.3592 | 0.3592 | ✅ Pass |
| Day 5 | 0.2646 | 0.2646 | ✅ Pass |
| Day 6 | 0.3272 | 0.3272 | ✅ Pass |
| Day 7 | 0.2085 | 0.2085 | ✅ Pass |
| Day 8 | 0.9777 | 0.9777 | ✅ Pass |
| Day 9 | 0.2512 | 0.2512 | ✅ Pass |
| Day 10 | 0.4438 | 0.4438 | ✅ Pass |


### Query 010
**Query:** I'm exhausted. I'm going to take Day 5 as a personal day and skip all the work stuff. Cancel every work-related activity on that day.

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day[5]/POI[atom(content =~ "work related")]`
- **Result:** Deleted 2 nodes
- **Time:** 11.87s
- **Tokens:** 5,293 (4,772 / 521)

**Deleted Nodes:**

- `Root > Itinerary_Version 1 > Itinerary > Day 5 > Email Catch-up Block`
- `Root > Itinerary_Version 1 > Itinerary > Day 5 > Client Check-in Call`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "work related")`
**Threshold:** `0.01`

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


### Query 011
**Query:** I just noticed Day 2 has no breakfastâ€”my first meeting is at 9am and I'll be starving. Add a quick hotel breakfast before the meeting.

#### semantic_xpath
- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day[2]`
- **Result:** Created at Itinerary > Day 2/Restaurant
- **Time:** 5.02s
- **Tokens:** 5,509 (5,328 / 181)

**Created Nodes:**

**Path:** `Itinerary > Day 2/Restaurant`
- **Name:** Hotel Breakfast Buffet
- **Time:** 7:30 AM - 8:30 AM
- **Cost:** CAD 15-25
- **Description:** Quick and convenient breakfast at the hotel buffet before heading to the meeting.
- **Highlights:** Convenient location, Variety of options, Quick service


### Query 012
**Query:** The workshop on Day 3 ends at 11am and then I have nothing until the AGO at noon. Add a coffee break in between. there's a good cafe near the gallery.

#### semantic_xpath
- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day[3]`
- **Result:** Created at Itinerary > Day 3/POI
- **Time:** 5.06s
- **Tokens:** 7,104 (6,899 / 205)

**Created Nodes:**

**Path:** `Itinerary > Day 3/POI`
- **Name:** AGO Coffee Break
- **Time:** 11:00 AM - 11:45 AM
- **Cost:** CAD 10-15
- **Description:** Relaxing coffee break at a nearby cafe before visiting the Art Gallery of Ontario.
- **Highlights:** Proximity to AGO, Relaxing atmosphere, Quality coffee


### Query 013
**Query:** It's actually my wedding anniversary on Day 9. I want to add a special romantic dinner somewhere niceâ€”maybe Scaramouche with the city view.

#### semantic_xpath
- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day[9]`
- **Result:** Created at Itinerary > Day 9/Restaurant
- **Time:** 6.92s
- **Tokens:** 5,968 (5,764 / 204)

**Created Nodes:**

**Path:** `Itinerary > Day 9/Restaurant`
- **Name:** Scaramouche
- **Time:** 7:30 PM - 9:30 PM
- **Cost:** CAD 150-200
- **Description:** Special romantic dinner at Scaramouche with city view, perfect for celebrating a wedding anniversary.
- **Highlights:** City view, Romantic atmosphere, Fine dining


### Query 014
**Query:** My partner is arriving on Day 6 and she's vegetarian. Add a plant-based restaurant for dinner that nightâ€”I've heard Planta is good.

#### semantic_xpath
- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day[6]`
- **Result:** Created at Itinerary > Day 6/Restaurant
- **Time:** 6.36s
- **Tokens:** 7,741 (7,522 / 219)

**Created Nodes:**

**Path:** `Itinerary > Day 6/Restaurant`
- **Name:** Planta
- **Time:** 8:30 PM - 10:00 PM
- **Cost:** CAD 50-70
- **Description:** A trendy plant-based restaurant offering a variety of innovative vegetarian dishes. Perfect for a delightful dinner experience.
- **Highlights:** Plant-based menu, Innovative dishes, Vegan-friendly


### Query 015
**Query:** I completely forgot about souvenirs. Add a stop at Roots or the Hudson's Bay flagship on Day 10 morning before the CN Tower. I need to grab gifts before I fly out.

#### semantic_xpath
- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day[10]`
- **Result:** Created at Itinerary > Day 10/POI
- **Time:** 5.89s
- **Tokens:** 5,904 (5,693 / 211)

**Created Nodes:**

**Path:** `Itinerary > Day 10/POI`
- **Name:** Roots or Hudson's Bay Flagship
- **Time:** 8:30 AM - 9:30 AM
- **Cost:** Varies
- **Description:** Stop at Roots or the Hudson's Bay flagship store to purchase souvenirs and gifts before heading to the CN Tower.
- **Highlights:** Souvenir shopping, Canadian brands

