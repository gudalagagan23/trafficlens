# TrafficLens: results
*Web Traffic and User Behaviour Intelligence*

> **Read this first.** All visitors in this project are SIMULATED. We created them, so we know the true answer for every visitor. These results show the method works on problems we planted. They do not prove it works on any real website.

## 1. The 12 planted problems

**11 found, 1 partly found, 0 missed** (out of 12).

| # | Side | Problem | Planted | Result | Evidence |
|---|---|---|---|---|---|
| 1 | traffic | Dumb bots | about 800 simple bots, including a flood of 450 | **FOUND** | 100.0% of 856 flagged as not human |
| 2 | traffic | Smart bots and AI agents hiding as humans | smart bots that copy humans, plus AI agents | **PARTLY FOUND** | smart bots: 72.7% flagged (27.3% passed as human); AI agents: 100.0% flagged |
| 3 | traffic | Scrapers | product-page scrapers | **FOUND** | 100.0% of 86 flagged |
| 4 | traffic | Sudden spike from one source | 450 visits from social_x in 20 minutes | **FOUND** | window found: True; false spike alarms: 0 |
| 5 | traffic | Low-quality source | cheap_ads (visitors leave at once) | **FOUND** | flagged sources: ['cheap_ads'] |
| 6 | traffic | Fake device | bots that claim to be phones but have no touch | **FOUND** | caught 100.0% of 181 planted; 94.3% of the flagged visits were truly fake |
| 7 | behaviour | Dead-end page | size_guide | **FOUND** | flagged pages: ['size_guide'] |
| 8 | behaviour | Funnel drop-off | shipping -> payment | **FOUND** | flagged steps: ['shipping -> payment'] |
| 9 | behaviour | Loops | compare <-> product_detail | **FOUND** | flagged pairs: [('compare', 'product_detail')] |
| 10 | behaviour | Rage clicks | cart | **FOUND** | flagged pages: ['cart'] |
| 11 | behaviour | Hidden useful page | reviews | **FOUND** | flagged pages: ['reviews'] |
| 12 | behaviour | Human vs AI-agent gap | agents fail at payment | **FOUND** | flagged: [('payment -> confirmation', 0.829), ('shipping -> payment', -0.498)] |

Bonus (link layer): Expectation mismatch (link layer) (promo_ads at deals) - **FOUND**; flagged: [('cheap_ads', 'home'), ('cheap_ads', 'products'), ('promo_ads', 'deals')]

Notes:
- Problem 2: Smart bots are the hardest case. Real browser agents may be harder than the ones simulated here.
- Problem 12: Extra step flagged: shipping -> payment. This is a real difference caused by problem 8 (humans leave at shipping, agents do not), not a false alarm.

## 2. The 8 tests (4 for traffic, 4 for behaviour)

| Test | What | Result | Pass? |
|---|---|---|---|
| Traffic 1 | Grouping with no labels | 19 groups, purity 94.9% | PASS |
| Traffic 2 | Unknown group (never-seen bot) | 100.0% of novel bots sent to Unknown; 3.2% of known visitors wrongly Unknown | PASS |
| Traffic 3 | Traffic forecast vs same-hour-last-week | error 1.041 vs baseline 1.286 (19.1% better) | PASS |
| Traffic 4 | Planted spike found | found: True, false spike alarms: 0 | PASS |
| Behaviour 1 | Fingerprint traits differ as guessed | 9 of 10 of our written guesses were right | PASS |
| Behaviour 2 | Next-page prediction vs counting baseline | top-1 56.7% vs 53.6%; top-3 86.0% vs 86.6% | PARTLY (better on top-1 only) |
| Behaviour 3 | Will-they-buy prediction vs simple rule | AUC 0.6503 vs 0.6183 | PASS |
| Behaviour 4 | Planted behaviour problems found | 6 of 6 found | PASS |

## 3. How the visitor judge did, group by group

| Real visitor kind | Visits | Called human | Called AI agent | Called old bot | Called Unknown |
|---|---|---|---|---|---|
| dumb bots (incl. the flood) | 856 | 0.0% | 0.0% | 100.0% | 0.0% |
| scrapers | 86 | 0.0% | 0.0% | 100.0% | 0.0% |
| declared crawlers | 265 | 0.0% | 0.0% | 99.6% | 0.4% |
| medium bots | 302 | 0.3% | 0.0% | 99.7% | 0.0% |
| smart bots | 187 | 27.3% | 0.0% | 61.5% | 11.2% |
| AI agents | 536 | 0.0% | 99.8% | 0.0% | 0.2% |
| novel bot (never seen) | 106 | 0.0% | 0.0% | 0.0% | 100.0% |
| humans | 5224 | 93.1% | 0.0% | 2.7% | 4.2% |

## 4. Fingerprint guesses: right and wrong

| Our written guess | Median (first) | Median (second) | p-value | Guess right? |
|---|---|---|---|---|
| Humans have more uneven timing than AI agents | 0.529 | 0.388 | 8.89e-163 | yes |
| Humans have more uneven timing than old bots | 0.529 | 0.042 | 0.0 | yes |
| Humans spend longer on each page than AI agents | 3.259 | 1.721 | 2.07e-242 | yes |
| Humans spend longer reading content than AI agents | 3.466 | 1.754 | 6.66e-182 | yes |
| AI agents focus on the goal more than humans | 0.75 | 0.333 | 6.77e-112 | yes |
| AI agents go deeper into checkout than humans | 0.5 | 0.0 | 8.06e-94 | yes |
| Humans try something new after going back; agents repeat | 1.0 | 0.5 | 8.11e-33 | yes |
| Old bots go back to seen pages more than humans | 0.4 | 0.0 | 7.67e-44 | yes |
| Humans explore more different pages than AI agents | 0.231 | 0.308 | 1.36e-26 | **NO** |
| AI agents need more tries on forms (only visits that used a form) | 2.5 | 1.0 | 3.26e-85 | yes |

## 5. Why clean the traffic first

| Measure | Everyone (raw) | Visitors judged human | The real human value |
|---|---|---|---|
| Bounce rate | 19.0% | 25.3% | 24.8% |
| Pages per visit | 7.14 | 5.71 | 5.59 |
| Conversion | 3.57% | 5.15% | 4.90% |

## 6. Where the system is weak (said plainly)

- **Real humans get flagged.** 2.7% of real humans were called bots or agents and 4.2% were sent to Unknown. Of the humans called bots, 100% were on desktop. They moved faster and more evenly than other desktop humans: median visit 52 seconds vs 154, timing unevenness 0.54 vs 0.74. (Likely reason: quick, purposeful browsing looks like a smart bot.)
- **Smart bots slip through.** 27.3% of smart bots were accepted as human, and 11.2% landed in Unknown.
- **The next-page model is only a little better than counting.** Top-3 accuracy: model 86.0% vs baseline 86.6%.
- **Buying prediction is modest.** AUC 0.6503 (0.5 is a coin flip). Only 7.4% of visitors buy, so it is hard.
- **Our guesses that were wrong:** Humans explore more different pages than AI agents.
- **Groups are over-split.** 19 groups were found for 4 real kinds of visitor. Purity is high but one real kind is spread over many groups.

## 7. Limits of this whole project

- All data is simulated. The simulated bots and agents were written by us, so they are probably easier to spot than real ones.
- Detection thresholds were adjusted while building, using this same simulated data. Real data would need fresh calibration.
- A tracking script only sees visitors who run it. Bots that never run scripts need server logs.
- Causes in the agent report are guesses. Only the numbers are facts.
- Click fraud, login attacks, payment errors, datacenter lists and slow page loads are not covered.
- Privacy: only patterns are recorded (counts, timings, positions). Never typed text.
