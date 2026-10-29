# TrafficLens
### Web Traffic and User Behaviour Intelligence

TrafficLens watches every visitor to a website. It works out **who is visiting** (a human, an AI agent or a bot),
**what they do** on the site, shows how the types differ, flags the odd ones, and tells the site owner
**what the problem is and what to fix first**.

> **Important:** all visitors in this project are **simulated**. There is no real website with real bots here.
> We created every visitor, so we know the true answer for each one and can score the system honestly.

---

## Run it (5 minutes)

You need Python 3.10 or newer.

1. Unzip the folder to your desktop and open it in VS Code (File > Open Folder > `trafficlens`).
2. Open a terminal in that folder and install the libraries:
   ```
   pip install -r requirements.txt
   ```
3. Run the whole project with one command (about 30 seconds):
   ```
   python run_all.py
   ```
4. Open the screen:
   ```
   streamlit run dashboard/app.py
   ```
5. Read the written results in `report/RESULTS.md` (scores) and `report/AGENT_REPORT.md` (the issue list).

The folder already contains finished results, so step 4 works straight away if you only want to look.

---

## What it does, in plain words

| Step | What happens | Folder |
|---|---|---|
| 1 | Makes fake visitors: humans, AI agents, bots of 5 skill levels, and one never-seen bot. Plants 12 problems. Saves a hidden answer key. | `data_generator/` |
| 2 | Turns page views into one record per visitor, with a 9-trait **behaviour fingerprint**. | `pipeline/` |
| 3 | **Web traffic half:** judges every visitor (Human / AI agent / Old bot / Unknown), groups look-alikes, finds spikes, scores traffic sources, spots fake phones, forecasts visits. | `traffic/` |
| 4 | **User behaviour half:** draws a journey graph per visitor type, finds dead ends, checkout leaks, loops, rage clicks, hidden useful pages, and where AI agents fail. Predicts the next page and who will buy. | `behaviour/` |
| 5 | **Link:** where traffic and behaviour meet (for example, visitors from one ad leave at one page). | `link/` |
| 6 | **Agent:** writes the findings in plain words. Every number is checked by code. | `agent/` |
| 7 | **Score page:** planted problems vs found problems. | `evaluation/` |
| 8 | **Screen:** traffic on the left, behaviour on the right. | `dashboard/` |

Also included: a small demo shop (`demo_shop/`), a privacy-safe tracker (`tracker/tracker.js`) and a collector
(`tracker/collector.py`) so you can see how real visits would be recorded.

### The four visitor labels
- **Human**: a person browsing.
- **AI agent**: an AI browsing on behalf of a person. Often a customer, not an attacker.
- **Old bot**: scrapers, crawlers, attack scripts.
- **Unknown**: the system is not sure, or has never seen anything like it. We would rather say "not sure" than guess wrong.

### The 12 planted problems
| Web traffic | User behaviour |
|---|---|
| Dumb bots | Dead-end page |
| Smart bots and AI agents hiding as humans | Funnel drop-off (checkout leak) |
| Scrapers | Loops between two pages |
| Sudden spike from one source | Rage clicks |
| Low-quality source | Hidden useful page |
| Fake device (a "phone" that never touches the screen) | Humans vs AI agents gap |

---

## Results from the included run (simulated data)

- **12 planted problems:** 11 found, 1 partly found (smart bots: 72.7% flagged; the rest pass as human).
- **8 tests (4 traffic, 4 behaviour):** 7 pass, 1 partly (next-page prediction beats counting on top-1 only).
- **Never-seen bot:** 100% sent to Unknown. 3.2% of known visitors wrongly marked Unknown.
- **Real humans flagged:** 2.7% called bots or agents, 4.2% sent to Unknown. They were fast, purposeful browsers.
- **Why clean first:** raw conversion looks like 3.57%, the cleaned number is 5.15%, the true human value is 4.90%.

Read `report/RESULTS.md` for every table, including the guesses we got wrong.

---

## How the agent stays honest
1. It only receives numbers the system calculated.
2. Every number in a sentence is registered when written. If a number was not calculated, the finding is rejected.
3. Every finding has four parts: what happened (with numbers), where, **likely cause (always marked as a guess)**, and the fix.
4. It says "not sure" when the evidence is weak.
5. The chat box answers only from those findings. Without an API key it works offline. To let an AI model write the answers, install `anthropic`, set `ANTHROPIC_API_KEY`, and the chat uses it (this mode is untested).

Run the safety checks any time: `python -m tests.test_checks`
(proves the analysis never opens the answer key, rejects invented numbers, and repeats exactly with the same seed).

---

## Limits (please read)
- **All data is simulated.** The bots and agents were written by us, so they are probably easier to catch than real ones. The practice data and the test data come from the same generator, so scores are optimistic.
- **Two detection rules were adjusted while building, using this same data** (dead end and hidden page). Real data needs fresh calibration.
- **A tracking script only sees visitors who run it.** Bots that never run scripts need server logs.
- **Causes in the report are guesses.** Only the numbers are facts.
- **Not covered:** click fraud, login attacks, payment errors, datacenter IP lists, slow page loads.
- **The live tracker path is only partly tested:** the collector and converter were tested; running the full analysis on real collected visits was not, and needs a few hundred real visits.
- **The AI-model chat mode was not tested** (no API key was available).
- See `report/PRIVACY.md` before using any of this on a real site.

---

## Put it online
See **DEPLOY.md**: create an empty GitHub repo, push this folder, then deploy `streamlit_app.py` on Streamlit Community Cloud. You get your own link.

---

## Use your own data later
1. Run `python tracker/collector.py` and the demo shop (`python demo_shop/build_shop.py`, then `python demo_shop/serve.py`).
2. Browse the shop at http://localhost:8000/demo_shop/index.html. Events are saved to `data/live/events.jsonl`.
3. Convert them: `python -m tracker.live_to_tables`
4. Analyse: `TRAFFICLENS_DATA=data/live python run_all.py --skip-generate` (on Windows PowerShell: `$env:TRAFFICLENS_DATA="data/live"; python run_all.py --skip-generate`)
