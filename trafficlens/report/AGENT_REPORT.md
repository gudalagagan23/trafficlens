# TrafficLens: issue report
*Web Traffic and User Behaviour Intelligence*

Every number below was calculated by the system. Causes are guesses and are marked as such.

## Top fixes

**Web traffic**
- Scrapers are copying product pages: Limit how fast one visitor can open product pages, and consider hiding prices from unknown visitors.
- Some visitors may be hiding as humans: Review the Unknown list, keep Unknown visits out of conversion numbers, and ask agent makers for a verifiable identity.
- Simple bots are visiting: Rate-limit or challenge these visits, and leave them out of your reports so averages stay honest.

**User behaviour**
- Visitors bounce between compare and product_detail: Put the key comparison facts directly on product_detail, so people do not need to keep going back to compare.
- Many buyers leave at shipping -> payment: Test a shorter shipping form, show costs earlier, and watch how many continue.
- reviews is useful but hidden: Link to reviews from product pages and the cart, so more people see it.

**Traffic and behaviour together**
- Bots and agents distort your averages: Report on cleaned (human-only) numbers, and show bots and agents separately.
- promo_ads visitors leave at deals: Make the deals page match the promo_ads message, or change the message.

---

## All findings

### Web traffic

**T3. Scrapers are copying product pages**  (confidence: high)

- **What happened:** 71 visits opened product pages one by one in number order, reading a median of 68 pages each at about 65 pages a minute.
- **Where:** Product detail pages.
- **Likely cause:** Guess: someone is copying your prices or catalogue.
- **Fix first:** Limit how fast one visitor can open product pages, and consider hiding prices from unknown visitors.

**T2. Some visitors may be hiding as humans**  (confidence: not sure)

- **What happened:** 535 visits were labelled AI agents. Another 347 visits (4.6%) could not be sorted with confidence and were marked Unknown.
- **Where:** Unknown visits by source: search (88), email (73), referral (68).
- **Likely cause:** Guess: some Unknown visits are bots that copy human mouse movement and timing. Others are real people with unusual habits. This system cannot tell these apart for sure.
- **Fix first:** Review the Unknown list, keep Unknown visits out of conversion numbers, and ask agent makers for a verifiable identity.

**T1. Simple bots are visiting**  (confidence: high)

- **What happened:** 858 visits (11% of all traffic) had no mouse or touch activity, moved through pages in about 0.5 seconds each, and kept almost perfectly even timing.
- **Where:** Top sources: social_x (520 visits), cheap_ads (124 visits), direct (123 visits).
- **Likely cause:** Guess: simple scripts or attack tools that fetch pages without a real browser.
- **Fix first:** Rate-limit or challenge these visits, and leave them out of your reports so averages stay honest.

**T5. cheap_ads brings low-quality visitors**  (confidence: high)

- **What happened:** cheap_ads sent 632 visits. Only 60% were judged human, and 91% of those humans left after one page. Its quality score is 23.4 out of 100, against a median of 72.3 for all sources.
- **Where:** Source: cheap_ads.
- **Likely cause:** Guess: the audience or the promise of this source does not match your site, or part of it is bot traffic.
- **Fix first:** Pause or cut spend on this source until it improves, and test a different landing page for it.

**T4. Sudden spike from social_x**  (confidence: high)

- **What happened:** Between 2026-09-24 14:00:00 and 2026-09-24 14:30:00, social_x sent 452 visits. That equals 12.6 days of its usual traffic (about 36 visits a day). 72% followed the exact same path and 100% were judged not human.
- **Where:** Source: social_x.
- **Likely cause:** Guess: an automated flood, possibly bought or fake traffic.
- **Fix first:** Block or rate-limit this source for now, exclude the window from reports, and check any ads or posts that point here.

**T7. Search-engine crawlers are visiting (usually fine)**  (confidence: high)

- **What happened:** 265 visits (3.5%) openly declared themselves as search-engine crawlers.
- **Where:** Crawlers read many pages and never buy.
- **Likely cause:** Guess: normal indexing by search engines. A declared name can be faked, so it should be verified.
- **Fix first:** Keep these allowed, but verify them, and keep them out of human conversion numbers.

**T6. Visitors pretending to be phones**  (confidence: medium)

- **What happened:** 192 visits (2.5%) claimed to be a phone or tablet but never produced a single touch. 98% of them were judged not human. The most common source was direct (57 visits).
- **Where:** Visitors claiming mobile devices.
- **Likely cause:** Guess: bots that fake a phone browser label but run on a computer or server.
- **Fix first:** Treat a phone label with zero touch as a strong bot warning, and challenge those visits.

### User behaviour

**B3. Visitors bounce between compare and product_detail**  (confidence: high)

- **What happened:** 850 of 1,254 human visits that touched both pages (68%) went back and forth between them again and again.
- **Where:** Pages: compare and product_detail.
- **Likely cause:** Guess: visitors cannot decide, or they cannot find the answer they need on either page.
- **Fix first:** Put the key comparison facts directly on product_detail, so people do not need to keep going back to compare.

**B2. Many buyers leave at shipping -> payment**  (confidence: high)

- **What happened:** Of 811 humans who reached shipping, only 289 (36%) went on to payment.
- **Where:** Checkout step: shipping -> payment.
- **Likely cause:** Guess: an unexpected cost, a long form, or a confusing step.
- **Fix first:** Test a shorter shipping form, show costs earlier, and watch how many continue.

**B5. reviews is useful but hidden**  (confidence: high)

- **What happened:** Only 1 page on your site links to reviews (rank 13 of 13 by links). Still, 87% of its 494 visits started right there, and visitors who saw it bought 1.9 times as often as the average human.
- **Where:** Page: reviews.
- **Likely cause:** Guess: people search for it on their own because it answers a buying question.
- **Fix first:** Link to reviews from product pages and the cart, so more people see it.

**B1. size_guide is a dead end**  (confidence: high)

- **What happened:** 71% of human visits to size_guide ended there. Other non-checkout pages usually lose 22%, so this is 3.3 times higher. It was visited 639 times.
- **Where:** Page: size_guide.
- **Likely cause:** Guess: the page gives no clear next step, or it does not answer what the visitor came for.
- **Fix first:** Add a clear next step on size_guide (a button back to the product or to the cart).

**B4. Rage clicking on cart**  (confidence: high)

- **What happened:** On 28% of human views of cart (432 of 1,516), the visitor clicked the same spot three or more times in a hurry.
- **Where:** Page: cart.
- **Likely cause:** Guess: something that looks clickable does not respond (for example a coupon or apply button).
- **Fix first:** Check every button on cart for a delay or error, and show a clear response when it is clicked.

**B6. AI agents fail at payment -> confirmation**  (confidence: high)

- **What happened:** At payment -> confirmation, 88% of humans continued but only 5% of AI agents did (humans: 289, agents: 259).
- **Where:** Checkout step: payment -> confirmation.
- **Likely cause:** Guess: the form or button is hard for automated browsers to use, so customers who shop through an AI assistant cannot finish.
- **Fix first:** Test the page with an AI browser agent, and make form fields clearly labelled and simple.

### Traffic and behaviour together

**L2. Bots and agents distort your averages**  (confidence: high)

- **What happened:** Counting everyone, the bounce rate is 19.0% and conversion is 3.6%. Counting only visitors judged human, bounce rate is 25.3% and conversion is 5.1%.
- **Where:** Whole site.
- **Likely cause:** Guess: non-human visits are mixed into your normal numbers.
- **Fix first:** Report on cleaned (human-only) numbers, and show bots and agents separately.

**L1. promo_ads visitors leave at deals**  (confidence: high)

- **What happened:** 76% of human visits from promo_ads ended at deals, against 21% for visitors from all other sources (257 visits).
- **Where:** Source promo_ads, page deals.
- **Likely cause:** Guess: the promise made by this source does not match what the page shows.
- **Fix first:** Make the deals page match the promo_ads message, or change the message.
