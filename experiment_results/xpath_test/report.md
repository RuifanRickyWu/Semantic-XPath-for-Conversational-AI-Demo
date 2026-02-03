# Experiment Report: xpath_test

## Summary

| Query ID | Pipeline | Operation | XPath / Logic | Result | Tokens (Total) | Time (s) |
|---|---|---|---|---|---|---|
| 001 | semantic_xpath | READ | `/Itinerary/Day[not(agg_exists(POI[(atom(content =...` | Selected 2 nodes | 5,730 (5,567 / 163) | 26.84 |
| 002 | semantic_xpath | READ | `/Itinerary/Day[7]/POI[atom(content =~ "outdoor")]` | Selected 1 nodes | 4,149 (3,992 / 157) | 5.42 |
| 003 | semantic_xpath | READ | `/Itinerary/Day[6]/POI[atom(content =~ "fun for a ...` | Selected 2 nodes | 4,226 (4,037 / 189) | 5.56 |
| 004 | semantic_xpath | READ | `(/Itinerary/Day/Restaurant[atom(content =~ "expen...` | Selected 0 nodes | 3,921 (3,838 / 83) | 10.04 |
| 005 | semantic_xpath | READ | `/Itinerary/Day[agg_exists(POI[atom(content =~ "nature")])]` | Selected 4 nodes | 5,807 (5,599 / 208) | 10.79 |
| 006 | semantic_xpath | READ | `/Itinerary/Day/POI[(atom(content =~ "breakfast") ...` | Selected 0 nodes | 4,417 (4,319 / 98) | 10.91 |
| 007 | semantic_xpath | DELETE | `/Itinerary/Day/Restaurant[atom(content =~ "dinner...` | Deleted 3 nodes | 4,814 (4,464 / 350) | 18.04 |
| 008 | semantic_xpath | DELETE | `/Itinerary/Day/POI[atom(content =~ "outdoor")]` | Deleted 1 nodes | 4,652 (4,473 / 179) | 9.07 |
| 009 | semantic_xpath | DELETE | `/Itinerary/Day/POI[atom(content =~ "CN Tower")]` | Deleted 1 nodes | 4,149 (3,989 / 160) | 8.36 |
| 010 | semantic_xpath | DELETE | `/Itinerary/Day/POI[atom(content =~ "Niagara Falls")]` | Deleted 1 nodes | 4,505 (4,324 / 181) | 12.01 |
| 011 | semantic_xpath | DELETE | `/Itinerary/Day[5]/POI[atom(content =~ "work related")]` | Deleted 3 nodes | 4,475 (4,196 / 279) | 14.72 |
| 012 | semantic_xpath | CREATE | `/Itinerary/Day[2]` | Created at Itinerary > Day 2/POI | 4,670 (4,484 / 186) | 6.69 |
| 013 | semantic_xpath | CREATE | `/Itinerary/Day` | Created at Root > Itinerary_Version 7 > Itinera... | 5,783 (5,555 / 228) | 7.76 |
| 014 | semantic_xpath | CREATE | `/Itinerary/Day[10]` | Created at Itinerary > Day 10/POI | 4,826 (4,632 / 194) | 5.17 |

## Detailed Results
### Query 001
**Query:** My friend lives in Mississauga, about an hour from downtown. What days are without any work commitments or flights?

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[not(agg_exists(POI[(atom(content =~ "work") OR atom(content =~ "flight"))]))]`
- **Result:** Selected 2 nodes
- **Time:** 26.84s
- **Tokens:** 5,730 (5,567 / 163)

**Selected Nodes:**

1. **Day** ->  ({'index': '9'})
2. **Day** ->  ({'index': '8'})

**Scoring Analysis:**

**Predicate:** `not(agg_exists(POI[atom(content =~ "(atom(content =~ "work") OR atom(content =~ "flight"))")]))`
**Threshold:** `0.1`

| Node | C1 ((atom(content =~ "work") OR atom(content =~ "flight"))) | Final Score | Result |
|---| --- |---|---|
| Day 1 | 0.2915 | 0.7085 | ✅ Pass |
| Day 2 | 0.5003 | 0.4997 | ✅ Pass |
| Day 3 | 0.7008 | 0.2992 | ✅ Pass |
| Day 4 | 0.6402 | 0.3598 | ✅ Pass |
| Day 5 | 0.2510 | 0.7490 | ✅ Pass |
| Day 6 | 0.6788 | 0.3212 | ✅ Pass |
| Day 7 | 0.7837 | 0.2163 | ✅ Pass |
| Day 8 | 0.3242 | 0.6758 | ✅ Pass |
| Day 9 | 0.2505 | 0.7495 | ✅ Pass |
| Day 10 | 0.4383 | 0.5617 | ✅ Pass |


### Query 002
**Query:** The weather forecast shows heavy rain on Day 7. Which activities are outdoors that I might need to reschedule?

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[7]/POI[atom(content =~ "outdoor")]`
- **Result:** Selected 1 nodes
- **Time:** 5.42s
- **Tokens:** 4,149 (3,992 / 157)

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

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[6]/POI[atom(content =~ "fun for a 10-year-old")]`
- **Result:** Selected 2 nodes
- **Time:** 5.56s
- **Tokens:** 4,226 (4,037 / 189)

**Selected Nodes:**

1. **POI** -> Ripley's Aquarium (3:30 PM - 5:30 PM, CAD 45, Ferry and Walk, {})
2. **POI** -> Toronto Islands Ferry and Bike Ride (10:30 AM - 1:30 PM, CAD 35, Walk and Ferry, {})

**Scoring Analysis:**

**Predicate:** `atom(content =~ "fun for a 10-year-old")`
**Threshold:** `0.1`

| Node | C1 (fun for a 10-year-old) | Final Score | Result |
|---| --- |---|---|
| Toronto Islands Ferry and Bike Ride | 0.4252 | 0.4252 | ✅ Pass |
| Ripley's Aquarium | 0.7523 | 0.7523 | ✅ Pass |


### Query 004
**Query:** I'm putting together my expense report. What are the most expensive restaurants I've booked?

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `(/Itinerary/Day/Restaurant[atom(content =~ "expensive")])[-1]`
- **Result:** Selected 0 nodes
- **Time:** 10.04s
- **Tokens:** 3,921 (3,838 / 83)

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

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[agg_exists(POI[atom(content =~ "nature")])]`
- **Result:** Selected 4 nodes
- **Time:** 10.79s
- **Tokens:** 5,807 (5,599 / 208)

**Selected Nodes:**

1. **Day** ->  ({'index': '8'})
2. **Day** ->  ({'index': '6'})
3. **Day** ->  ({'index': '7'})
4. **Day** ->  ({'index': '1'})

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

#### semantic_xpath
- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day/POI[(atom(content =~ "breakfast") AND atom(content =~ "shopping"))]`
- **Result:** Selected 0 nodes
- **Time:** 10.91s
- **Tokens:** 4,417 (4,319 / 98)

**Scoring Analysis:**

**Predicate:** `atom(content =~ "(atom(content =~ "breakfast") AND atom(content =~ "shopping"))")`
**Threshold:** `0.1`

| Node | C1 ((atom(content =~ "breakfast") AND atom(content =~ "shopping"))) | Final Score | Result |
|---| --- |---|---|
| YYZ Airport Arrival | 0.0033 | 0.0033 | ❌ Filtered Out |
| Harbourfront Stroll | 0.0349 | 0.0349 | ❌ Filtered Out |
| Client Kickoff Meeting | 0.0151 | 0.0151 | ❌ Filtered Out |
| Strategy Workshop | 0.0127 | 0.0127 | ❌ Filtered Out |
| Stakeholder Presentation | 0.0277 | 0.0277 | ❌ Filtered Out |
| Art Gallery of Ontario | 0.3191 | 0.3191 | ✅ Pass |
| Full-Day Workshop | 0.0416 | 0.0416 | ❌ Filtered Out |
| Bloor Street Shopping | 0.1851 | 0.1851 | ✅ Pass |
| Client Check-in Call | 0.0193 | 0.0193 | ❌ Filtered Out |
| Email Catch-up Block | 0.0038 | 0.0038 | ❌ Filtered Out |
| Networking Drinks | 0.0144 | 0.0144 | ❌ Filtered Out |
| Toronto Islands Ferry and Bike Ride | 0.0729 | 0.0729 | ❌ Filtered Out |
| Ripley's Aquarium | 0.2331 | 0.2331 | ✅ Pass |
| Royal Ontario Museum | 0.3083 | 0.3083 | ✅ Pass |
| Distillery District Walk | 0.0816 | 0.0816 | ❌ Filtered Out |
| Niagara Falls Day Trip | 0.1061 | 0.1061 | ✅ Pass |
| Eaton Centre Shopping | 0.5271 | 0.5271 | ✅ Pass |
| Queen Street West Boutiques | 0.2786 | 0.2786 | ✅ Pass |
| CN Tower EdgeWalk | 0.0835 | 0.0835 | ❌ Filtered Out |
| Airport Snack Stop | 0.0549 | 0.0549 | ❌ Filtered Out |
| YYZ Departure | 0.0183 | 0.0183 | ❌ Filtered Out |


### Query 007
**Query:** I just checked my spending and I'm way over budget. Cut the expensive dinners from the itinerary and I'll find cheaper alternatives later.

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day/Restaurant[atom(content =~ "dinner") AND atom(content =~ "expensive")]`
- **Result:** Deleted 3 nodes
- **Time:** 18.04s
- **Tokens:** 4,814 (4,464 / 350)

**Deleted Nodes:**

- `Root > Itinerary_Version 1 > Itinerary > Day 2 > Alo Restaurant`
- `Root > Itinerary_Version 1 > Itinerary > Day 5 > Kaiseki Kaji`
- `Root > Itinerary_Version 1 > Itinerary > Day 1 > Canoe Restaurant`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "dinner") AND atom(content =~ "expensive")`
**Threshold:** `0.1`

| Node | C1 (dinner) | C2 (expensive) | Final Score | Result |
|---| --- | --- |---|---|
| Canoe Restaurant | 0.9970 | 0.9978 | 0.9970 | ✅ Pass |
| Alo Restaurant | 0.9983 | 0.9982 | 0.9982 | ✅ Pass |
| Hotel Continental Breakfast | 0.0005 | 0.1213 | 0.0005 | ❌ Filtered Out (dinner) |
| FRANK Restaurant at AGO | 0.7769 | 0.9310 | 0.7769 | ✅ Pass |
| Pai Northern Thai | 0.9966 | 0.9373 | 0.9373 | ✅ Pass |
| Quick Grab Coffee | 0.0007 | 0.4355 | 0.0007 | ❌ Filtered Out (dinner) |
| Lee Restaurant | 0.9978 | 0.9826 | 0.9826 | ✅ Pass |
| Mildred's Temple Kitchen | 0.0021 | 0.9468 | 0.0021 | ❌ Filtered Out (dinner) |
| Kaiseki Kaji | 0.9973 | 0.9987 | 0.9973 | ✅ Pass |
| Sunset Grill | 0.0024 | 0.3724 | 0.0024 | ❌ Filtered Out (dinner) |
| Island Cafe Picnic Lunch | 0.0032 | 0.7898 | 0.0032 | ❌ Filtered Out (dinner) |
| The Keg Steakhouse | 0.9988 | 0.7176 | 0.7176 | ✅ Pass |
| Fran's Restaurant | 0.0013 | 0.5388 | 0.0013 | ❌ Filtered Out (dinner) |
| Eataly Toronto | 0.0093 | 0.9085 | 0.0093 | ❌ Filtered Out (dinner) |
| Cluny Bistro | 0.9986 | 0.9631 | 0.9631 | ✅ Pass |
| Elements on the Falls | 0.9731 | 0.9610 | 0.9610 | ✅ Pass |
| Antler Kitchen | 0.9977 | 0.9850 | 0.9850 | ✅ Pass |
| Lady Marmalade | 0.0015 | 0.9775 | 0.0015 | ❌ Filtered Out (dinner) |
| Urban Eatery Food Court | 0.0022 | 0.1900 | 0.0022 | ❌ Filtered Out (dinner) |
| Bar Isabel | 0.9914 | 0.8872 | 0.8872 | ✅ Pass |
| Hotel Quick Checkout Breakfast | 0.0011 | 0.6455 | 0.0011 | ❌ Filtered Out (dinner) |
| 360 Restaurant at CN Tower | 0.0157 | 0.9896 | 0.0157 | ❌ Filtered Out (dinner) |


### Query 008
**Query:** It's definitely going to rain all day on Day 7. Cancel any outdoor activities, I'll figure out replacements.

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day/POI[atom(content =~ "outdoor")]`
- **Result:** Deleted 1 nodes
- **Time:** 9.07s
- **Tokens:** 4,652 (4,473 / 179)

**Deleted Nodes:**

- `Root > Itinerary_Version 2 > Itinerary > Day 7 > Distillery District Walk`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "outdoor")`
**Threshold:** `0.1`

| Node | C1 (outdoor) | Final Score | Result |
|---| --- |---|---|
| YYZ Airport Arrival | 0.1437 | 0.1437 | ✅ Pass |
| Harbourfront Stroll | 0.9976 | 0.9976 | ✅ Pass |
| Client Kickoff Meeting | 0.6113 | 0.6113 | ✅ Pass |
| Strategy Workshop | 0.6112 | 0.6112 | ✅ Pass |
| Stakeholder Presentation | 0.8928 | 0.8928 | ✅ Pass |
| Art Gallery of Ontario | 0.0910 | 0.0910 | ❌ Filtered Out |
| Full-Day Workshop | 0.9698 | 0.9698 | ✅ Pass |
| Bloor Street Shopping | 0.4604 | 0.4604 | ✅ Pass |
| Client Check-in Call | 0.0902 | 0.0902 | ❌ Filtered Out |
| Email Catch-up Block | 0.0536 | 0.0536 | ❌ Filtered Out |
| Networking Drinks | 0.1775 | 0.1775 | ✅ Pass |
| Toronto Islands Ferry and Bike Ride | 0.9992 | 0.9992 | ✅ Pass |
| Ripley's Aquarium | 0.2240 | 0.2240 | ✅ Pass |
| Royal Ontario Museum | 0.1170 | 0.1170 | ✅ Pass |
| Distillery District Walk | 0.9981 | 0.9981 | ✅ Pass |
| Niagara Falls Day Trip | 0.9995 | 0.9995 | ✅ Pass |
| Eaton Centre Shopping | 0.0141 | 0.0141 | ❌ Filtered Out |
| Queen Street West Boutiques | 0.9987 | 0.9987 | ✅ Pass |
| CN Tower EdgeWalk | 0.9965 | 0.9965 | ✅ Pass |
| Airport Snack Stop | 0.5182 | 0.5182 | ✅ Pass |
| YYZ Departure | 0.6466 | 0.6466 | ✅ Pass |


### Query 009
**Query:** I actually went to the CN Tower on my last trip to Toronto. Remove any CN Tower activities. I'd rather do something new.

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day/POI[atom(content =~ "CN Tower")]`
- **Result:** Deleted 1 nodes
- **Time:** 8.36s
- **Tokens:** 4,149 (3,989 / 160)

**Deleted Nodes:**

- `Root > Itinerary_Version 3 > Itinerary > Day 10 > CN Tower EdgeWalk`

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
| Niagara Falls Day Trip | 0.0023 | 0.0023 | ❌ Filtered Out |
| Eaton Centre Shopping | 0.0032 | 0.0032 | ❌ Filtered Out |
| Queen Street West Boutiques | 0.0048 | 0.0048 | ❌ Filtered Out |
| CN Tower EdgeWalk | 0.9995 | 0.9995 | ✅ Pass |
| Airport Snack Stop | 0.0157 | 0.0157 | ❌ Filtered Out |
| YYZ Departure | 0.0597 | 0.0597 | ❌ Filtered Out |


### Query 010
**Query:** Bad news. my friend who was going to host me at Niagara just tested positive for COVID. I need to cancel the Niagara Falls trip.

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day/POI[atom(content =~ "Niagara Falls")]`
- **Result:** Deleted 1 nodes
- **Time:** 12.01s
- **Tokens:** 4,505 (4,324 / 181)

**Deleted Nodes:**

- `Root > Itinerary_Version 4 > Itinerary > Day 8 > Niagara Falls Day Trip`

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
| Niagara Falls Day Trip | 0.9997 | 0.9997 | ✅ Pass |
| Eaton Centre Shopping | 0.0097 | 0.0097 | ❌ Filtered Out |
| Queen Street West Boutiques | 0.0145 | 0.0145 | ❌ Filtered Out |
| Airport Snack Stop | 0.0360 | 0.0360 | ❌ Filtered Out |
| YYZ Departure | 0.1150 | 0.1150 | ✅ Pass |


### Query 011
**Query:** I'm exhausted. I'm going to take Day 5 as a personal day and skip all the work stuff. Cancel every work-related activity on that day.

#### semantic_xpath
- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day[5]/POI[atom(content =~ "work related")]`
- **Result:** Deleted 3 nodes
- **Time:** 14.72s
- **Tokens:** 4,475 (4,196 / 279)

**Deleted Nodes:**

- `Root > Itinerary_Version 5 > Itinerary > Day 5 > Email Catch-up Block`
- `Root > Itinerary_Version 5 > Itinerary > Day 5 > Client Check-in Call`
- `Root > Itinerary_Version 5 > Itinerary > Day 5 > Networking Drinks`

**Scoring Analysis:**

**Predicate:** `atom(content =~ "work related")`
**Threshold:** `0.1`

| Node | C1 (work related) | Final Score | Result |
|---| --- |---|---|
| Client Check-in Call | 0.9999 | 0.9999 | ✅ Pass |
| Email Catch-up Block | 0.9999 | 0.9999 | ✅ Pass |
| Networking Drinks | 0.9996 | 0.9996 | ✅ Pass |


### Query 012
**Query:** I just noticed Day 2 has no breakfast, my first meeting is at 9am and I'll be starving. Add a quick hotel breakfast before the meeting.

#### semantic_xpath
- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day[2]`
- **Result:** Created at Itinerary > Day 2/POI
- **Time:** 6.69s
- **Tokens:** 4,670 (4,484 / 186)

**Created Nodes:**

**Path:** `Itinerary > Day 2/POI`
- **Name:** Hotel Breakfast
- **Time:** 7:30 AM - 8:30 AM
- **Cost:** Included in stay
- **Description:** Quick breakfast at the hotel buffet to start the day before the meeting.
- **Highlights:** Convenient, Quick meal, Buffet options


### Query 013
**Query:** The workshop on Day 3 ends at 11am and then I have nothing until the AGO at noon. Add a coffee break in between. there's a good cafe near the gallery.

#### semantic_xpath
- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day`
- **Result:** Created at Root > Itinerary_Version 7 > Itinerary > Day 3/POI
- **Time:** 7.76s
- **Tokens:** 5,783 (5,555 / 228)

**Created Nodes:**

**Path:** `Root > Itinerary_Version 7 > Itinerary > Day 3/POI`
- **Name:** Coffee Break at Cafe near AGO
- **Time:** 11:00 AM - 11:45 AM
- **Cost:** CAD 10-15
- **Description:** Relaxing coffee break at a nearby cafe before visiting the Art Gallery of Ontario. Perfect for unwinding after the morning presentation.
- **Highlights:** Proximity to AGO, Relaxing atmosphere, Quality coffee


### Query 014
**Query:** I completely forgot about souvenirs. Add a stop at Roots or the Hudson's Bay flagship on Day 10 morning before the CN Tower. I need to grab gifts before I fly out.

#### semantic_xpath
- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day[10]`
- **Result:** Created at Itinerary > Day 10/POI
- **Time:** 5.17s
- **Tokens:** 4,826 (4,632 / 194)

**Created Nodes:**

**Path:** `Itinerary > Day 10/POI`
- **Name:** Roots or Hudson's Bay Flagship
- **Time:** 9:00 AM - 10:00 AM
- **Cost:** CAD 50-100
- **Description:** Visit to Roots or Hudson's Bay flagship store to purchase souvenirs and gifts before departure.
- **Highlights:** Canadian souvenirs, Gift shopping

