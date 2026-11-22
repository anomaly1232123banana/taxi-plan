# Taxi Plan Dashboard: Design

Date: 2026-11-23 · Status: draft, waiting for approval

## 1. Intent

The user's father drives a taxi in Sydney and struggles to find fares. Younger people use Uber. His real customers are:

1. **People aged 45+**, and
2. **Workers on Cabcharge**: their employer pays, so the taxi is free for them.

We want a phone dashboard that tells him **where to be and when** over his next 5 working days. It does this by finding the biggest crowds of his kind of customer as they come out of events, offices, cruise terminals and so on, and turning that into a plan of roughly 2-hour blocks.

Success means he opens one bookmark at home, in the car or parked at a rank, and immediately sees where to go next, without struggling to read it (his eyesight is poor).

## 2. Users and usage

- **Driver (father):** only reads Chinese (the UI is in English for now, so his son can check the code; Chinese comes later). Very poor eyesight. Uses an ordinary phone browser before leaving home, while driving (phone in a cradle) and while parked.
- **Owner (son):** runs the scan on his own Windows laptop, which is always on, and reads and maintains the code.
- **Shift:** starts 12:00 pm and usually ends 12–1 am, with overtime until 2–3 am. He works **Monday to Saturday and never on Sundays**. He's based around the city/CBD, but will go up to about **50 minutes' drive from the CBD** (Olympic Park, Parramatta and beyond) for a crowd he's sure of.

## 3. Goals

- G1. A daily scan of the **next 5 working days** (skipping Sundays; a Saturday-night shift running past midnight into Sunday counts as Saturday).
- G2. Each place gets a **time**, **address**, **short description**, **when the crowd comes out**, crowd **size and age**, **where to wait**, and a **Taxi Score from 0 to 100**.
- G3. A **plan for each day** in roughly 2-hour blocks from 12 pm to 3 am. It picks the best place for each block, makes sure he can actually drive from one stop to the next in time, and shows **quiet** blocks honestly.
- G4. Sources covered:
  - big events (concerts, sport, theatre, opera, festivals, conferences, races)
  - **office finish times at companies that use Cabcharge heavily** (KPMG-style firms)
  - **cruise ships**
  - **hotels**
  - **casinos** (The Star, Crown)
  - **RSL and leagues clubs**
  - **private hospitals** (low priority)
  - **rain** and **train trackwork or strikes**, used to boost the score of whatever is affected
- G5. Light on the owner's **Claude subscription**: accurate, but using as little of it as possible.
- G6. Ready for Chinese later: every piece of UI text lives in one file.

## 4. Non-goals (explicitly not built)

- Airport (he avoids the taxi queue there)
- Taxi rank data (the owner said not to bother)
- A Refresh button, or scans started from the phone
- Read-aloud / voice
- Accounts or logins
- Paid APIs of any kind (no Anthropic API key, no paid maps or traffic service)
- Live traffic
- Chinese translation now (the structure must allow it, but translating isn't part of this build)
- A breakdown of how each score was calculated (the card shows only the score number)

## 5. Anti-goals (failures even if it technically works)

- **Stale data shown as fresh.** If today's scan failed, he must be able to see that.
- **The page breaking mid-shift.** The phone must never depend on the laptop being reachable.
- **Sending him 50 minutes out for an uncertain crowd.** Far-away stops need a higher bar.
- **Text he can't read.**
- **Using up the owner's Claude usage.**
- **Making up events or details and showing them as fact.** Anything the AI estimates must be based on a real listing.

## 6. Constraints

- Runs on the owner's Windows 11 laptop. Installed: Python 3.13, Node, git and Claude Code CLI 2.1.x. Not installed: the GitHub CLI (`gh`).
- AI work uses **Claude Code headless (`claude -p`) on the owner's Claude subscription**, with **Sonnet** for the daily scan.
- Hosting is **GitHub Pages**, which is free. The site, and therefore the repo, is public, so the repo must not contain personal details (no names, phone numbers or home address).
- The owner will need to create a free GitHub account and a free **Ticketmaster developer key**. The build should walk them through both.
- One scan a day at **10:00 am Sydney time**, started by Windows Task Scheduler.
- All times are in **Australia/Sydney** time, including daylight saving.

## 7. Approaches considered

| | Approach | Trade-off |
|---|---|---|
| **1 (chosen)** | **Hybrid.** A Python script pulls free structured sources plus fixed researched lists. Claude Sonnet only *estimates* missing facts (age, size, finish time, paid fare, spending, where to wait) for **new** events, and makes a few capped searches to fill gaps. Plain Python does the scoring and the plan. | Least use of the Claude subscription, gives the same result for the same input, and is easy to test. More code than option 2. |
| 2 | Claude does everything in one run (search, score, plan). | Least code, but uses the most of the subscription, results change from day to day, and the formula can't be tested. |
| 3 | No AI: scrapers plus rule-based guesses. | Free, but the age guesses are poor and it breaks whenever a venue changes its website. |

The owner picked **1**.

## 8. Decided design

### 8.1 Pipeline (runs daily at 10:00)

```
Task Scheduler 10:00
  -> scan.py
       1. collect    free sources -> raw candidates (name, venue, address, start time, source url)
       2. estimate   new candidates only -> one batched `claude -p --model sonnet` call -> estimates (cached)
       3. gapfill    capped Claude web search for big venues the feeds miss (e.g. Opera House, ICC Sydney conferences)
       4. score      Python formula (weights in weights.json)
       5. plan       Python: 2h blocks, drive-time reachability, quiet blocks + fallbacks
       6. write      site/plan.json (+ generated_at, status)
       7. publish    git commit + push site/ to GitHub Pages
```

Sources:

| Source | Type | Where it comes from |
|---|---|---|
| Ticketmaster Discovery API | live feed (free key) | concerts, sport, theatre in the Sydney area |
| Cruise schedule | live | Port Authority NSW published schedule |
| Race days | live | Racing NSW calendar (Randwick, Rosehill, etc.) |
| Weather (rain) | live | a free forecast with no key needed (e.g. Open-Meteo) |
| Trackwork and strikes | live | Transport for NSW planned trackwork pages |
| Major venues not on Ticketmaster | Claude gap-fill | Opera House, ICC Sydney, theatres |
| Cabcharge offices | **fixed list** | researched once at build time: company, address, rough staff count, how heavily they use Cabcharge, normal and late finish times, weekdays only |
| Hotels, casinos, RSL clubs, private hospitals | **fixed list** | researched once: name, address, area, busy times; used as steady spots and fallbacks |
| Drive times | **fixed table** | about 15 areas (CBD, Barangaroo, Darling Harbour, Circular Quay/The Rocks, Moore Park, Randwick, Olympic Park, Parramatta, Rosehill, North Sydney, Chatswood, Macquarie Park, Rooty Hill, Canterbury, Pyrmont), with a peak-hour multiplier (4–7 pm, roughly ×1.5) and a late-night one (after 9 pm, roughly ×0.8) |

**Cost control:**
- Claude estimates are cached by event, so each estimate is made once.
- Each day there is **one** batched estimate call plus **one** gap-fill call with a hard limit on searches and turns.
- Fixed lists use no Claude at all day to day.

**Trust boundary:** Claude's output is checked strictly against a JSON schema, and anything that fails is dropped or retried once. Gap-fill events must come with a source URL.

**Failure handling:**
- Any failure in one source is logged, and the scan carries on without it.
- If the whole scan fails, the previous `plan.json` stays published, and the page shows it as stale.

### 8.2 Taxi Score (0–100)

The owner approved these weights, which live in `weights.json` so they can be tuned:

| Factor | Points | How it scores |
|---|---|---|
| Age of crowd | 35 | median age, straight lines between these points: ≤22 → 0.1, 30 → 0.25, 40 → 0.55, 45 → 0.85, ≥50 → 1.0 |
| Someone else pays (Cabcharge, corporate) | 25 | 0–1, from the fixed list or the Claude estimate |
| Crowd size | 20 | `clamp(log10(n/200) / log10(400), 0, 1)`, so 200 people = 0 and 80,000 = 1 |
| Spending power | 10 | 0–1 (ticket price, how upmarket the venue is) |
| Late finish | 10 | exit at 22:00 or later = 1, from 21:00 to before 22:00 = 0.5, otherwise 0 |

- **Boosts:** rain in that time window ×1.15, and trackwork or a strike affecting that area ×1.2. The score never goes above 100.
- **Excluded:** anything whose crowd comes out outside 12 pm–3 am, or on a Sunday's shift.
- **Reference examples the owner approved. These are the regression tests for the formula** (each must land within ±1):

| Example | Median age | Pays | Size | Spending | Exit | Score |
|---|---|---|---|---|---|---|
| Opera House opera | 58 | 0.15 | 2,000 | 1.0 | 22:15 | 66 |
| KPMG Barangaroo office finish | 40 | 1.0 | 3,000 | 0.7 | 18:00 | 60 |
| Olympic Park rave | 22 | 0 | 20,000 | 0.15 | 01:00 | 30 |

### 8.2a What becomes a candidate (my calls, from the conversation)

- **Events** from the feeds and gap-fill are candidates, including shows held at RSL clubs.
- **Offices** (fixed list) are weekday-only candidates at two times:
  - the **normal finish** (about 5–6:30 pm), with the full crowd
  - a **late finish** (about 8–10 pm), with a smaller crowd but "someone else pays" at full strength, since that's when Cabcharge is typically used
- **Cruise ships:** passengers getting off at 7–10 am is before his shift, so it's ignored. On a **departure day** the candidate is "boarding": exit window 12–3 pm, in the 12–2 block, with the address set to the terminal (Overseas Passenger Terminal or White Bay). The description tells him to pick passengers up at city hotels heading to the terminal.
- **Hotels, casinos, RSL/leagues clubs and private hospitals** from the fixed lists are **fallbacks only**. They appear in quiet blocks and never compete for a block. The owner described them as "smaller priority places" to try when nothing big is on.

### 8.3 Plan (itinerary)

- **Blocks:** 12–2, 2–4, 4–6, 6–8, 8–10 pm, 10–12, 12–2 am, 2–3 am.
- A candidate goes into the block that contains its **exit time** (when the crowd comes out), not its start time.
- Each day's plan **maximises the total score** across its blocks. A stop only counts as reachable if the drive time from the previous chosen stop fits between the two exit times (allowing about 20–30 minutes to load a fare at the previous stop).
- **Threshold:** a block is "big" only if its best candidate scores **40 or more**. Otherwise it's a **quiet** block.
- **Far-away rule (my call):** a stop more than 30 minutes' drive from the CBD needs a score of **55 or more**, in line with "50 minutes is the most, and only if I'm sure".
- **Quiet block text:** "Free time until {time} ({next big stop})", followed by "Or try nearby:" and the 2–3 closest steady spots (hotels, casinos, clubs, hospitals) near the next big stop.

### 8.4 Phone page

These were picked by the owner in the visual mockups. The reference is `.superpowers/brainstorm/*/content/full-ui.html`.

- **Layout:** one long scroll. At the top is the **Go Now** card (the block for the current time; before 12 pm it's the first block; after 3 am it's the next working day), then **rest of today**, then each following working day with a heading (for example "TUE 24 NOV").
- **Colours:** black background, bright yellow accents, a green score badge (yellow for mid scores). Very large text: titles about 30–38 px, body text at least 20 px. Buttons are large.
- **Closed card:** time block, name, score number, when people come out, and on the Go Now card also a one-line description.
- **Open card** (expands in place, tap again to close):
  - description
  - address
  - start and end time
  - crowd size and ages
  - where to wait
  - drive time
  - a big **Navigate (Maps)** button that opens Google Maps directions to the address
- **Quiet block:** a dashed box showing the free-time text and nearby fallbacks.
- **Header:** the date and "✓ Updated 10:02am" in green. It turns **red** ("⚠ Old plan, from Mon 10:02am") when `generated_at` is earlier than the **most recent 10:00 scan that should have finished**, or when the status isn't ok. Allow a 45-minute grace period, so the cut-off is the latest 10:45 that has already passed. Yesterday's plan is therefore still **green from midnight to 10:45 am**, which avoids a false alarm every night during the 12–3 am overtime.
- **No Refresh button.** The page loads `plan.json` (bypassing the cache) when it opens and whenever it comes back into view, and works out Go Now from the phone's clock.
- **"min from you"** is a rough distance estimate from the phone's location, and only appears if he allows location access. Otherwise the card shows the drive time from the previous stop.
- It can be added to the phone's home screen so it opens like an app.
- **Tech:** plain HTML, CSS and JS, with no framework and no build step. All UI text is in one strings file (`en` now, `zh` later). Event descriptions are written by Claude, so when Chinese comes the prompt's output language will switch too.

### 8.5 Build process the owner asked for

- Implementation subagents run on **Sonnet**. Planning, critical thinking and review run on **Opus**.
- After the build, a **bug-finding code reviewer** and a separate **improvement reviewer** look at everything. Their findings go into one fix list, the fixes are made, and the loop repeats a few times until it's ready to ship.

## 9. Left to the builder

- File layout, module names, and the exact JSON schemas for `plan.json` and the cache
- The exact venue, office, hotel and club lists (research them, and mark them as estimates)
- How each source is parsed, and fallbacks when a source changes
- How `site/` gets onto GitHub Pages (for example a `gh-pages` branch or a Pages-only repo)
- The exact Task Scheduler setup (including running a missed start as soon as possible)
- The test framework (Python's built-in `unittest` is fine), and a check that the page renders with a sample `plan.json`
- Small visual details within the decided look
