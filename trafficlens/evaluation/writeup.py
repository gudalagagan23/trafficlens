"""Turns evaluation.json into report/RESULTS.md, in plain words."""
import config as C

ICON = {"found": "FOUND", "partly found": "PARTLY FOUND", "missed": "MISSED"}


def pct(x, d=1):
    return f"{x * 100:.{d}f}%"


def write_results(res):
    sc, t, b, js = res["scorecard"], res["traffic_tests"], res["behaviour_tests"], res["judge"]
    s = res["summary"]
    L = [f"# {C.PRODUCT_NAME}: results", f"*{C.SUBTITLE}*", "",
         "> **Read this first.** All visitors in this project are SIMULATED. We created them, so we know the true answer for every visitor. "
         "These results show the method works on problems we planted. They do not prove it works on any real website.", "",
         "## 1. The 12 planted problems", "",
         f"**{s['found']} found, {s['partly']} partly found, {s['missed']} missed** (out of {s['total']}).", "",
         "| # | Side | Problem | Planted | Result | Evidence |", "|---|---|---|---|---|---|"]
    for c in sc:
        L.append(f"| {c['number']} | {c['side']} | {c['problem']} | {c['planted']} | **{ICON[c['result']]}** | {c['evidence']} |")
    L += ["", f"Bonus (link layer): {res['bonus']['problem']} ({res['bonus']['planted']}) - **{ICON[res['bonus']['result']]}**; {res['bonus']['evidence']}", ""]
    notes = [c for c in sc if c["note"]]
    if notes:
        L += ["Notes:"] + [f"- Problem {c['number']}: {c['note']}" for c in notes] + [""]

    # ---- tests
    g, u, f, sp = t["grouping"], t["unknown_test"], t["forecast"], t["spike"]
    fp, npg, pur = b["fingerprints"], b["next_page"], b["purchase"]
    n_beh = [c for c in sc if c["side"] == "behaviour"]
    tests = [
        ("Traffic 1", "Grouping with no labels", f"{g['groups_found']} groups, purity {pct(g['purity_by_type'])}", g["purity_by_type"] >= 0.85),
        ("Traffic 2", "Unknown group (never-seen bot)",
         f"{pct(u['novel_sent_to_unknown'])} of novel bots sent to Unknown; {pct(u['known_visitors_wrongly_unknown'])} of known visitors wrongly Unknown",
         u["novel_sent_to_unknown"] >= 0.8 and u["known_visitors_wrongly_unknown"] <= 0.10),
        ("Traffic 3", "Traffic forecast vs same-hour-last-week",
         f"error {f['mae_model']} vs baseline {f['mae_baseline']} ({f['improvement_pct']}% better)", f["model_wins"]),
        ("Traffic 4", "Planted spike found", f"found: {sp['found']}, false spike alarms: {sp['false_alarms']}", sp["found"] and sp["false_alarms"] == 0),
        ("Behaviour 1", "Fingerprint traits differ as guessed", f"{fp['guesses_correct']} of {fp['guesses_total']} of our written guesses were right", fp["guesses_correct"] >= 7),
        ("Behaviour 2", "Next-page prediction vs counting baseline",
         f"top-1 {pct(npg['model_accuracy'])} vs {pct(npg['baseline_accuracy'])}; top-3 {pct(npg['model_top3'])} vs {pct(npg['baseline_top3'])}",
         True if (npg["model_wins"] and npg["model_top3"] > npg["baseline_top3"]) else ("PARTLY" if npg["model_wins"] else False)),
        ("Behaviour 3", "Will-they-buy prediction vs simple rule",
         f"AUC {pur['model_auc']} vs {pur['baseline_auc']}", pur["model_wins"]),
        ("Behaviour 4", "Planted behaviour problems found", f"{sum(c['result'] == 'found' for c in n_beh)} of {len(n_beh)} found", all(c["result"] == "found" for c in n_beh)),
    ]
    L += ["## 2. The 8 tests (4 for traffic, 4 for behaviour)", "", "| Test | What | Result | Pass? |", "|---|---|---|---|"]
    for a, bb, c, ok in tests:
        L.append(f"| {a} | {bb} | {c} | {'PARTLY (better on top-1 only)' if ok == 'PARTLY' else ('PASS' if ok else 'NOT PASSED')} |")
    L.append("")

    # ---- judge table
    L += ["## 3. How the visitor judge did, group by group", "",
          "| Real visitor kind | Visits | Called human | Called AI agent | Called old bot | Called Unknown |", "|---|---|---|---|---|---|"]
    for name, r in js.items():
        L.append(f"| {name} | {r['n']} | {pct(r['called_human'])} | {pct(r['called_ai_agent'])} | {pct(r['called_old_bot'])} | {pct(r['called_unknown'])} |")
    L.append("")

    # ---- fingerprint guesses
    L += ["## 4. Fingerprint guesses: right and wrong", "", "| Our written guess | Median (first) | Median (second) | p-value | Guess right? |", "|---|---|---|---|---|"]
    for r in fp["guesses"]:
        L.append(f"| {r['guess']} | {r['median_first']} | {r['median_second']} | {r['p_value']} | {'yes' if r['guess_correct'] else '**NO**'} |")
    L.append("")

    # ---- dirty averages
    d = res["dirty_averages"]
    L += ["## 5. Why clean the traffic first", "",
          "| Measure | Everyone (raw) | Visitors judged human | The real human value |", "|---|---|---|---|",
          f"| Bounce rate | {pct(d['everyone']['bounce_rate'])} | {pct(d['cleaned']['bounce_rate'])} | {pct(d['true_humans']['bounce_rate'])} |",
          f"| Pages per visit | {d['everyone']['mean_pages']} | {d['cleaned']['mean_pages']} | {d['true_humans']['mean_pages']} |",
          f"| Conversion | {pct(d['everyone']['conversion'], 2)} | {pct(d['cleaned']['conversion'], 2)} | {pct(d['true_humans']['conversion'], 2)} |", ""]

    # ---- failures
    h, sm, ag = js["humans"], js["smart bots"], js["AI agents"]
    L += ["## 6. Where the system is weak (said plainly)", ""]
    L.append(f"- **Real humans get flagged.** {pct(h['called_old_bot'] + h['called_ai_agent'])} of real humans were called bots or agents and "
             f"{pct(h['called_unknown'])} were sent to Unknown. Of the humans called bots, {pct(h['flagged_on_desktop_share'], 0)} were on desktop. "
             f"They moved faster and more evenly than other desktop humans: median visit {h['flagged_median_visit_seconds']:.0f} seconds vs "
             f"{h['other_desktop_median_visit_seconds']:.0f}, timing unevenness {h['flagged_median_timing_unevenness']} vs {h['other_desktop_median_timing_unevenness']}. "
             f"(Likely reason: quick, purposeful browsing looks like a smart bot.)")
    L.append(f"- **Smart bots slip through.** {pct(sm['called_human'])} of smart bots were accepted as human, and {pct(sm['called_unknown'])} landed in Unknown.")
    if not npg["model_wins"] or npg["model_top3"] <= npg["baseline_top3"]:
        L.append(f"- **The next-page model is only a little better than counting.** Top-3 accuracy: model {pct(npg['model_top3'])} vs baseline {pct(npg['baseline_top3'])}.")
    else:
        L.append(f"- The next-page model beats counting by {npg['gain_points']} points on top-1 accuracy. That is a small gain.")
    L.append(f"- **Buying prediction is modest.** AUC {pur['model_auc']} (0.5 is a coin flip). Only {pct(pur['buy_rate_in_test'])} of visitors buy, so it is hard.")
    wrong = [r["guess"] for r in fp["guesses"] if not r["guess_correct"]]
    if wrong:
        L.append("- **Our guesses that were wrong:** " + "; ".join(wrong) + ".")
    L.append(f"- **Groups are over-split.** {g['groups_found']} groups were found for 4 real kinds of visitor. Purity is high but one real kind is spread over many groups.")
    L += ["", "## 7. Limits of this whole project", "",
          "- All data is simulated. The simulated bots and agents were written by us, so they are probably easier to spot than real ones.",
          "- Detection thresholds were adjusted while building, using this same simulated data. Real data would need fresh calibration.",
          "- A tracking script only sees visitors who run it. Bots that never run scripts need server logs.",
          "- Causes in the agent report are guesses. Only the numbers are facts.",
          "- Click fraud, login attacks, payment errors, datacenter lists and slow page loads are not covered.",
          "- Privacy: only patterns are recorded (counts, timings, positions). Never typed text.", ""]
    (C.REPORT_DIR / "RESULTS.md").write_text("\n".join(L))
