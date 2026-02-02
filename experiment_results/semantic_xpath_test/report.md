# Experiment Report: semantic_xpath_test

## Summary

| Query ID | Pipeline       | Operation | XPath / Logic                                                | Result                                  | Tokens (Total)      | Time (s) |
| -------- | -------------- | --------- | ------------------------------------------------------------ | --------------------------------------- | ------------------- | -------- |
| 001      | semantic_xpath | READ      | `/Itinerary/Day[not(agg_exists(POI[atom(content =~...`       | Selected 1 nodes                        | 3,971 (3,810 / 161) | 27.11    |
| 002      | semantic_xpath | READ      | `/Itinerary/Day[@index='7']/POI[atom(content =~ "outdoor")]` | Selected 1 nodes                        | 2,589 (2,481 / 108) | 4.96     |
| 003      | semantic_xpath | READ      | `/Itinerary/Day[@index='6']/POI[atom(content =~ "f...`       | Selected 2 nodes                        | 2,671 (2,522 / 149) | 4.54     |
| 004      | semantic_xpath | READ      | `/Itinerary/Day/Restaurant[atom(content =~ "really...`       | Selected 3 nodes                        | 3,593 (3,401 / 192) | 10.72    |
| 005      | semantic_xpath | READ      | `/Itinerary/Day[agg_exists(POI[atom(content =~ "nature")])]` | Selected 4 nodes                        | 6,156 (5,946 / 210) | 10.08    |
| 006      | semantic_xpath | DELETE    | `/Itinerary/Day/Restaurant[atom(content =~ "expensive")]`    | Deleted 3 nodes                         | 3,731 (3,434 / 297) | 11.22    |
| 007      | semantic_xpath | DELETE    | `/Itinerary/Day[@index='7']/POI[atom(content =~ "outdoor")]` | Deleted 1 nodes                         | 2,641 (2,479 / 162) | 3.57     |
| 008      | semantic_xpath | DELETE    | `/Itinerary/Day/POI[atom(content =~ "CN Tower")]`            | Deleted 1 nodes                         | 3,537 (3,386 / 151) | 8.85     |
| 009      | semantic_xpath | DELETE    | `/Itinerary/Day[agg_exists(POI[atom(content =~ "Ni...`       | Deleted 1 nodes                         | 5,731 (5,548 / 183) | 8.49     |
| 010      | semantic_xpath | DELETE    | `/Itinerary/Day[@index='5']/POI[atom(content =~ "w...`       | Deleted 3 nodes                         | 2,813 (2,590 / 223) | 4.04     |
| 011      | semantic_xpath | CREATE    | `/Itinerary/Day[@index='2']`                                 | Created at Itinerary > Day 2/Restaurant | 3,135 (2,947 / 188) | 3.89     |
| 012      | semantic_xpath | CREATE    | `/Itinerary/Day[@index='3']`                                 | Created at Itinerary > Day 3/POI        | 3,372 (3,169 / 203) | 3.95     |
| 013      | semantic_xpath | CREATE    | `/Itinerary/Day[@index='9']`                                 | Created at Itinerary > Day 9/Restaurant | 3,277 (3,073 / 204) | 3.68     |
| 014      | semantic_xpath | CREATE    | `/Itinerary/Day[@index='6']`                                 | Created at Itinerary > Day 6/Restaurant | 3,362 (3,175 / 187) | 3.09     |
| 015      | semantic_xpath | CREATE    | `/Itinerary/Day[@index='10']`                                | Created at Itinerary > Day 10/POI       | 2,996 (2,798 / 198) | 2.77     |

## Detailed Results

### Query 001

**Query:** My college friend lives in Mississauga, about an hour from downtown. I need a day without any work commitments or flights.

#### semantic_xpath

- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[not(agg_exists(POI[atom(content =~ "work")])) AND not(agg_exists(POI[atom(content =~ "flight")]))]`
- **Result:** Selected 1 nodes
- **Time:** 27.11s
- **Tokens:** 3,971 (3,810 / 161)

**Selected Nodes:**

**1. Day**

- **Type:** Day
- **Reasoning:** Day 9 has no work commitments or flights and includes leisure activities like brunch, shopping, and dinner.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 9`

### Query 002

**Query:** The weather forecast shows heavy rain on Day 7. I want to check which activities are outdoors that I might need to reschedule.

#### semantic_xpath

- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[@index='7']/POI[atom(content =~ "outdoor")]`
- **Result:** Selected 1 nodes
- **Time:** 4.96s
- **Tokens:** 2,589 (2,481 / 108)

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

### Query 003

**Query:** My sister and nephew are joining me on Day 6. He's 10 years old. What activities do I already have planned that would be fun for a kid?

#### semantic_xpath

- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[@index='6']/POI[atom(content =~ "fun for a kid")]`
- **Result:** Selected 2 nodes
- **Time:** 4.54s
- **Tokens:** 2,671 (2,522 / 149)

**Selected Nodes:**

**1. Ripley's Aquarium**

- **Name:** Ripley's Aquarium
- **Type:** POI
- **Time:** 3:30 PM - 5:30 PM
- **Cost:** CAD 45
- **Description:** World-class aquarium with underwater tunnel and interactive exhibits. Indoor family attraction perfect for kids. Sharks, jellyfish, and touch tanks.
- **Highlights:** Indoor attraction, Kid-friendly family activity, Marine life
- **Reasoning:** Ripley's Aquarium is a kid-friendly indoor attraction with interactive exhibits, perfect for a 10-year-old.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 6 > Ripley's Aquarium`

**2. Toronto Islands Ferry and Bike Ride**

- **Name:** Toronto Islands Ferry and Bike Ride
- **Type:** POI
- **Time:** 10:30 AM - 1:30 PM
- **Cost:** CAD 35
- **Description:** Ferry ride to Toronto Islands followed by bike rental and exploration. Outdoor nature activity with beaches, gardens, and stunning skyline views. Perfect for families and kids.
- **Highlights:** Outdoor nature, Kid-friendly family activity, Bike riding, Beach access
- **Reasoning:** Toronto Islands Ferry and Bike Ride is an outdoor activity that includes a ferry ride and bike rental, which is fun and suitable for kids.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 6 > Toronto Islands Ferry and Bike Ride`

### Query 004

**Query:** I'm putting together my expense report. Can you show me all the restaurants I've booked that are really expensive

#### semantic_xpath

- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day/Restaurant[atom(content =~ "really expensive")]`
- **Result:** Selected 3 nodes
- **Time:** 10.72s
- **Tokens:** 3,593 (3,401 / 192)

**Selected Nodes:**

**1. Alo Restaurant**

- **Name:** Alo Restaurant
- **Type:** Restaurant
- **Time:** 7:00 PM - 9:30 PM
- **Cost:** CAD 300-400
- **Description:** Three Michelin-starred French tasting menu. Extremely expensive and exclusive fine dining. Intimate 8-course experience with wine pairings. Very formal and upscale.
- **Highlights:** Expensive Michelin dining, Upscale French cuisine, Formal atmosphere
- **Reasoning:** Alo Restaurant is described as extremely expensive with a cost of CAD 300-400, fitting the 'really expensive' criteria.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 2 > Alo Restaurant`

**2. Kaiseki Kaji**

- **Name:** Kaiseki Kaji
- **Type:** Restaurant
- **Time:** 8:00 PM - 10:00 PM
- **Cost:** CAD 250-350
- **Description:** Exquisite Japanese kaiseki dining experience. Very expensive omakase with seasonal courses. Intimate and formal setting.
- **Highlights:** Expensive Japanese dining, Upscale omakase, Formal atmosphere
- **Reasoning:** Kaiseki Kaji is described as very expensive with a cost of CAD 250-350, fitting the 'really expensive' criteria.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 5 > Kaiseki Kaji`

**3. Canoe Restaurant**

- **Name:** Canoe Restaurant
- **Type:** Restaurant
- **Time:** 7:30 PM - 9:00 PM
- **Cost:** CAD 150-200
- **Description:** Upscale Canadian cuisine on the 54th floor of TD Tower. Expensive fine dining with panoramic city views. Elegant and formal atmosphere.
- **Highlights:** Expensive fine dining, City skyline views, Upscale atmosphere
- **Reasoning:** Canoe Restaurant is described as expensive with a cost of CAD 150-200, which is on the lower end but still fits the 'expensive' criteria.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 1 > Canoe Restaurant`

### Query 005

**Query:** I've been stuck in meetings most of the week. Which days have nature activities where I can actually get outside and see some green space?

#### semantic_xpath

- **Operation:** READ
- **Logic/XPath:** `/Itinerary/Day[agg_exists(POI[atom(content =~ "nature")])]`
- **Result:** Selected 4 nodes
- **Time:** 10.08s
- **Tokens:** 6,156 (5,946 / 210)

**Selected Nodes:**

**1. Day**

- **Type:** Day
- **Reasoning:** Day 8 includes a full-day excursion to Niagara Falls, which is an outdoor scenic adventure and nature activity.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 8`

**2. Day**

- **Type:** Day
- **Reasoning:** Day 6 features a ferry ride to Toronto Islands with bike rental and exploration, which is an outdoor nature activity.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 6`

**3. Day**

- **Type:** Day
- **Reasoning:** Day 1 includes a Harbourfront Stroll, which is an outdoor activity with lake views and fresh air.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 1`

**4. Day**

- **Type:** Day
- **Reasoning:** Day 7 includes a Distillery District Walk, which is an outdoor walking experience through a historic area.
- **Path:** `Root > Itinerary_Version 1 > Itinerary > Day 7`

### Query 006

**Query:** I just checked my spending and I'm way over budget. I need to cut the expensive dinners from the itinerary and find cheaper alternatives later.

#### semantic_xpath

- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day/Restaurant[atom(content =~ "expensive")]`
- **Result:** Deleted 3 nodes
- **Time:** 11.22s
- **Tokens:** 3,731 (3,434 / 297)

**Deleted Nodes:**

- `Root > Itinerary_Version 1 > Itinerary > Day 5 > Kaiseki Kaji`
- `Root > Itinerary_Version 1 > Itinerary > Day 2 > Alo Restaurant`
- `Root > Itinerary_Version 1 > Itinerary > Day 1 > Canoe Restaurant`

### Query 007

**Query:** It's definitely going to rain all day on Day 7. Cancel any outdoor activities, I'll figure out replacements.

#### semantic_xpath

- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day[@index='7']/POI[atom(content =~ "outdoor")]`
- **Result:** Deleted 1 nodes
- **Time:** 3.57s
- **Tokens:** 2,641 (2,479 / 162)

**Deleted Nodes:**

- `Root > Itinerary_Version 2 > Itinerary > Day 7 > Distillery District Walk`

### Query 008

**Query:** I actually went to the CN Tower on my last trip to Toronto. Remove any CN Tower activities. I'd rather do something new.

#### semantic_xpath

- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day/POI[atom(content =~ "CN Tower")]`
- **Result:** Deleted 1 nodes
- **Time:** 8.85s
- **Tokens:** 3,537 (3,386 / 151)

**Deleted Nodes:**

- `Root > Itinerary_Version 3 > Itinerary > Day 10 > CN Tower EdgeWalk`

### Query 009

**Query:** Bad news. my friend who was going to host me at Niagara just tested positive for COVID. I need to cancel the whole Niagara Falls day trip.

#### semantic_xpath

- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day[agg_exists(POI[atom(content =~ "Niagara Falls")])]`
- **Result:** Deleted 1 nodes
- **Time:** 8.49s
- **Tokens:** 5,731 (5,548 / 183)

**Deleted Nodes:**

- `Root > Itinerary_Version 4 > Itinerary > Day 8`

### Query 010

**Query:** I'm exhausted. I'm going to take Day 5 as a personal day and skip all the work stuff. Cancel every work-related activity on that day.

#### semantic_xpath

- **Operation:** DELETE
- **Logic/XPath:** `/Itinerary/Day[@index='5']/POI[atom(content =~ "work related")]`
- **Result:** Deleted 3 nodes
- **Time:** 4.04s
- **Tokens:** 2,813 (2,590 / 223)

**Deleted Nodes:**

- `Root > Itinerary_Version 5 > Itinerary > Day 5 > Email Catch-up Block`
- `Root > Itinerary_Version 5 > Itinerary > Day 5 > Client Check-in Call`
- `Root > Itinerary_Version 5 > Itinerary > Day 5 > Networking Drinks`

### Query 011

**Query:** I just noticed Day 2 has no breakfastâ€”my first meeting is at 9am and I'll be starving. Add a quick hotel breakfast before the meeting.

#### semantic_xpath

- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day[@index='2']`
- **Result:** Created at Itinerary > Day 2/Restaurant
- **Time:** 3.89s
- **Tokens:** 3,135 (2,947 / 188)

**Created Nodes:**

**Path:** `Itinerary > Day 2/Restaurant`

- **Name:** Hotel Breakfast Buffet
- **Time:** 7:30 AM - 8:30 AM
- **Cost:** CAD 15-20
- **Description:** Quick breakfast at the hotel buffet to start the day before the meeting.
- **Highlights:** Convenient location, Variety of options

### Query 012

**Query:** The workshop on Day 3 ends at 11am and then I have nothing until the AGO at noon. Add a coffee break in between. there's a good cafe near the gallery.

#### semantic_xpath

- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day[@index='3']`
- **Result:** Created at Itinerary > Day 3/POI
- **Time:** 3.95s
- **Tokens:** 3,372 (3,169 / 203)

**Created Nodes:**

**Path:** `Itinerary > Day 3/POI`

- **Name:** Coffee Break at The Gallery Cafe
- **Time:** 11:15 AM - 11:45 AM
- **Cost:** CAD 10-15
- **Description:** Relaxing coffee break at a cafe near the Art Gallery of Ontario. Perfect spot to unwind and recharge before exploring the gallery.
- **Highlights:** Convenient location, Relaxing atmosphere

### Query 013

**Query:** It's actually my wedding anniversary on Day 9. I want to add a special romantic dinner somewhere niceâ€”maybe Scaramouche with the city view.

#### semantic_xpath

- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day[@index='9']`
- **Result:** Created at Itinerary > Day 9/Restaurant
- **Time:** 3.68s
- **Tokens:** 3,277 (3,073 / 204)

**Created Nodes:**

**Path:** `Itinerary > Day 9/Restaurant`

- **Name:** Scaramouche
- **Time:** 7:00 PM - 9:00 PM
- **Cost:** CAD 150-200
- **Description:** Special romantic dinner at Scaramouche with city view. Perfect for celebrating a wedding anniversary with exquisite cuisine and a stunning backdrop.
- **Highlights:** Romantic atmosphere, City view, Exquisite cuisine

### Query 014

**Query:** My partner is arriving on Day 6 and she's vegetarian. Add a plant-based restaurant for dinner that nightâ€”I've heard Planta is good.

#### semantic_xpath

- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day[@index='6']`
- **Result:** Created at Itinerary > Day 6/Restaurant
- **Time:** 3.09s
- **Tokens:** 3,362 (3,175 / 187)

**Created Nodes:**

**Path:** `Itinerary > Day 6/Restaurant`

- **Name:** Planta
- **Time:** 7:00 PM - 8:30 PM
- **Cost:** CAD 50-70
- **Description:** Chic plant-based restaurant offering innovative vegetarian and vegan dishes. Perfect for a healthy and delicious dinner.
- **Highlights:** Plant-based menu, Vegan options, Chic atmosphere

### Query 015

**Query:** I completely forgot about souvenirs. Add a stop at Roots or the Hudson's Bay flagship on Day 10 morning before the CN Tower. I need to grab gifts before I fly out.

#### semantic_xpath

- **Operation:** CREATE
- **Logic/XPath:** `/Itinerary/Day[@index='10']`
- **Result:** Created at Itinerary > Day 10/POI
- **Time:** 2.77s
- **Tokens:** 2,996 (2,798 / 198)

**Created Nodes:**

**Path:** `Itinerary > Day 10/POI`

- **Name:** Roots or Hudson's Bay Flagship
- **Time:** 9:00 AM - 10:00 AM
- **Cost:** Varies
- **Description:** Stop at Roots or the Hudson's Bay flagship to purchase souvenirs and gifts before heading to the CN Tower.
- **Highlights:** Canadian souvenirs, Iconic brands
