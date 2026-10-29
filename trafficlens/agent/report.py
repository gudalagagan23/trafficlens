"""
The report agent: it explains what the system found, in plain words.

THE RULES (these are enforced by code, not just promised)
  1. It only gets numbers the system calculated (the JSON result files).
  2. Every number in a sentence is registered when it is written. After the
     sentence is built, a checker looks at every number in the text. If any number
     was NOT calculated, the finding is rejected. "No number, no claim."
  3. Every finding has four parts:
        what happened  (with numbers)
        where          (page, source or visitor type)
        likely cause   (always marked "Guess:" - only the numbers are facts)
        what to fix first
  4. Confidence is "high", "medium" or "not sure". Weak or small evidence = "not sure".

This works with NO internet and NO API key. An optional chat helper
(agent/chat.py) can pass the same findings to a language model.
"""
import json
import re

import numpy as np
import pandas as pd

import config as C

NUM = re.compile(r"\d+(?:[.,]\d+)*")


class Facts:
    """Collects every number that is allowed to appear in a finding."""
    def __init__(self):
        self.allowed = set()
        self.evidence = {}

    def _reg(self, text):
        for tok in NUM.findall(text):
            self.allowed.add(tok)

    def n(self, name, value):
        s = f"{int(round(value)):,}"
        self.evidence[name] = int(round(value)); self._reg(s); return s

    def pct(self, name, value, digits=0):
        s = f"{value * 100:.{digits}f}%"
        self.evidence[name] = round(float(value), 4); self._reg(s); return s

    def f1(self, name, value):
        s = f"{value:.1f}"
        self.evidence[name] = round(float(value), 2); self._reg(s); return s

    def txt(self, name, value):
        s = str(value)
        self.evidence[name] = s; self._reg(s); return s

    def check(self, text):
        found = NUM.findall(text)
        bad = [t for t in found if t not in self.allowed]
        return bad


def _confidence(n_main, strong=200, ok=100):
    if n_main >= strong:
        return "high"
    return "medium" if n_main >= ok else "not sure"


def _finding(fid, side, title, what, where, cause, fix, facts, impact, confidence, issue):
    bad = facts.check(what + " " + where + " " + cause + " " + fix)
    return dict(id=fid, side=side, issue=issue, title=title, what_happened=what, where=where,
                likely_cause="Guess: " + cause, fix=fix, impact_visits=int(impact),
                confidence=confidence if not bad else "rejected",
                evidence=facts.evidence, unverified_numbers=bad)


def build():
    tr = json.loads((C.OUT_DIR / "traffic_results.json").read_text())
    be = json.loads((C.OUT_DIR / "behaviour_results.json").read_text())
    ln = json.loads((C.OUT_DIR / "link_results.json").read_text())
    pr = json.loads((C.OUT_DIR / "prediction_results.json").read_text())
    feats = pd.read_csv(C.OUT_DIR / "features.csv")
    ids = json.loads((C.OUT_DIR / "traffic_ids.json").read_text())
    total = tr["totals"]["visits"]
    out = []

    # ----------------------------------------------------------- TRAFFIC
    # T1 dumb bots
    f = Facts()
    d = tr["signatures"]["dumb_signature"]
    if d:
        sub = feats[feats["session_id"].isin(ids["dumb_signature"])]
        out.append(_finding(
            "T1", "traffic", "Simple bots are visiting",
            f"{f.n('visits', d)} visits ({f.pct('share_of_all', d / total)} of all traffic) had no mouse or touch activity, "
            f"moved through pages in about {f.f1('median_seconds_per_page', float(np.median(np.exp(sub['speed']) - 1)))} seconds each, "
            f"and kept almost perfectly even timing.",
            "Top sources: " + ", ".join(f"{k} ({f.n('src_' + k, v)} visits)" for k, v in sub["source"].value_counts().head(3).items()) + ".",
            "simple scripts or attack tools that fetch pages without a real browser.",
            "Rate-limit or challenge these visits, and leave them out of your reports so averages stay honest.",
            f, d, _confidence(d), "dumb_bots"))

    # T2 smart bots and agents
    f = Facts()
    t = tr["totals"]
    agents, unknown = t.get("ai_agent", 0), t.get("unknown", 0)
    pred = pd.read_csv(C.OUT_DIR / "predictions.csv")
    unk_src = feats[feats["session_id"].isin(pred.loc[pred["pred_label"] == "unknown", "session_id"])]["source"].value_counts().head(3)
    out.append(_finding(
        "T2", "traffic", "Some visitors may be hiding as humans",
        f"{f.n('agents', agents)} visits were labelled AI agents. Another {f.n('unknown', unknown)} visits "
        f"({f.pct('unknown_share', unknown / total, 1)}) could not be sorted with confidence and were marked Unknown.",
        "Unknown visits by source: " + ", ".join(f"{k} ({f.n('unk_' + k, v)})" for k, v in unk_src.items()) + ".",
        "some Unknown visits are bots that copy human mouse movement and timing. Others are real people with unusual habits. This system cannot tell these apart for sure.",
        "Review the Unknown list, keep Unknown visits out of conversion numbers, and ask agent makers for a verifiable identity.",
        f, unknown + agents, "not sure", "smart_bots_agents"))

    # T3 scrapers
    f = Facts()
    sc = tr["signatures"]["scraper_signature"]
    if sc:
        sub = feats[feats["session_id"].isin(ids["scraper_signature"])]
        out.append(_finding(
            "T3", "traffic", "Scrapers are copying product pages",
            f"{f.n('visits', sc)} visits opened product pages one by one in number order, "
            f"reading a median of {f.n('median_pages', float(sub['n_pages'].median()))} pages each at about {f.n('pages_per_min', float(sub['pages_per_min'].median()))} pages a minute.",
            "Product detail pages.",
            "someone is copying your prices or catalogue.",
            "Limit how fast one visitor can open product pages, and consider hiding prices from unknown visitors.",
            f, sc * float(sub["n_pages"].median()), _confidence(sc, 50, 20), "scrapers"))

    # T4 spike
    for i, w in enumerate(tr["spikes"], 1):
        f = Facts()
        out.append(_finding(
            f"T4.{i}" if len(tr["spikes"]) > 1 else "T4", "traffic", f"Sudden spike from {w['source']}",
            f"Between {f.txt('start', w['start'])} and {f.txt('end', w['end'])}, {w['source']} sent {f.n('visits', w['visits'])} visits. "
            f"That equals {f.f1('days_of_usual_traffic', w['days_of_usual_traffic'])} days of its usual traffic (about {f.n('usual_per_day', w['usual_visits_per_day'])} visits a day). "
            f"{f.pct('same_path', w['same_path_share'])} followed the exact same path and {f.pct('non_human', w['flagged_non_human_share'])} were judged not human.",
            f"Source: {w['source']}.",
            "an automated flood, possibly bought or fake traffic.",
            "Block or rate-limit this source for now, exclude the window from reports, and check any ads or posts that point here.",
            f, w["visits"], _confidence(w["visits"]), "spike"))

    # T5 low quality sources
    q = pd.DataFrame(ln["source_quality"])
    scored = q.dropna(subset=["quality_score"])
    med = float(scored["quality_score"].median())
    for r in scored[scored["low_quality"] == True].itertuples():
        f = Facts()
        out.append(_finding(
            "T5", "traffic", f"{r.source} brings low-quality visitors",
            f"{r.source} sent {f.n('visits', r.visits)} visits. Only {f.pct('human_share', r.human_share)} were judged human, "
            f"and {f.pct('human_bounce', r.human_bounce_rate)} of those humans left after one page. "
            f"Its quality score is {f.f1('score', r.quality_score)} out of {f.n('scale', 100)}, against a median of {f.f1('median_score', med)} for all sources.",
            f"Source: {r.source}.",
            "the audience or the promise of this source does not match your site, or part of it is bot traffic.",
            "Pause or cut spend on this source until it improves, and test a different landing page for it.",
            f, r.visits * (1 - r.human_share * (1 - r.human_bounce_rate)), _confidence(r.visits), "low_quality_source"))

    # T6 fake devices
    f = Facts()
    fd = tr["fake_devices"]
    if fd["count"]:
        top_src = max(fd["by_source"], key=fd["by_source"].get)
        out.append(_finding(
            "T6", "traffic", "Visitors pretending to be phones",
            f"{f.n('visits', fd['count'])} visits ({f.pct('share', fd['share_of_all'], 1)}) claimed to be a phone or tablet but never produced a single touch. "
            f"{f.pct('non_human', fd['flagged_non_human_share'])} of them were judged not human. The most common source was {top_src} ({f.n('top_source_visits', fd['by_source'][top_src])} visits).",
            "Visitors claiming mobile devices.",
            "bots that fake a phone browser label but run on a computer or server.",
            "Treat a phone label with zero touch as a strong bot warning, and challenge those visits.",
            f, fd["count"], _confidence(fd["count"]), "fake_device"))

    # info: crawlers
    f = Facts()
    cr = tr["signatures"]["declared_crawlers"]
    if cr:
        out.append(_finding(
            "T7", "traffic", "Search-engine crawlers are visiting (usually fine)",
            f"{f.n('visits', cr)} visits ({f.pct('share', cr / total, 1)}) openly declared themselves as search-engine crawlers.",
            "Crawlers read many pages and never buy.",
            "normal indexing by search engines. A declared name can be faked, so it should be verified.",
            "Keep these allowed, but verify them, and keep them out of human conversion numbers.",
            f, cr, _confidence(cr), "crawlers"))

    # ----------------------------------------------------------- BEHAVIOUR
    iss = be["issues"]
    H = be["types"]["human"]
    nh = H["sessions"]
    for r in iss["dead_ends"]:
        f = Facts()
        out.append(_finding(
            "B1", "behaviour", f"{r['page']} is a dead end",
            f"{f.pct('exit_rate', r['exit_rate'])} of human visits to {r['page']} ended there. Other non-checkout pages usually lose "
            f"{f.pct('typical', r['typical_exit_rate'])}, so this is {f.f1('times_typical', r['times_typical'])} times higher. It was visited {f.n('visits', r['visits'])} times.",
            f"Page: {r['page']}.",
            "the page gives no clear next step, or it does not answer what the visitor came for.",
            f"Add a clear next step on {r['page']} (a button back to the product or to the cart).",
            f, r["visits"] * r["exit_rate"], _confidence(r["visits"]), "dead_end"))
    for r in iss["funnel_leaks"]:
        f = Facts()
        out.append(_finding(
            "B2", "behaviour", f"Many buyers leave at {r['step']}",
            f"Of {f.n('reached', r['reached_from'])} humans who reached {r['from_step']}, only {f.n('continued', r['reached_to'])} "
            f"({f.pct('continue_rate', r['continue_rate'])}) went on to {r['to_step']}.",
            f"Checkout step: {r['step']}.",
            "an unexpected cost, a long form, or a confusing step.",
            f"Test a shorter {r['from_step']} form, show costs earlier, and watch how many continue.",
            f, r["reached_from"] - r["reached_to"], _confidence(r["reached_from"]), "funnel_drop"))
    for r in iss["loops"]:
        f = Facts()
        a, b = r["pages"]
        out.append(_finding(
            "B3", "behaviour", f"Visitors bounce between {a} and {b}",
            f"{f.n('looping', r['looping_sessions'])} of {f.n('both', r['sessions_with_both'])} human visits that touched both pages "
            f"({f.pct('loop_rate', r['loop_rate'])}) went back and forth between them again and again.",
            f"Pages: {a} and {b}.",
            "visitors cannot decide, or they cannot find the answer they need on either page.",
            f"Put the key comparison facts directly on {b}, so people do not need to keep going back to {a}.",
            f, r["looping_sessions"], _confidence(r["sessions_with_both"]), "loops"))
    for r in iss["rage_clicks"]:
        f = Facts()
        out.append(_finding(
            "B4", "behaviour", f"Rage clicking on {r['page']}",
            f"On {f.pct('rate', r['rate'])} of human views of {r['page']} ({f.n('rage_views', r['rage_views'])} of {f.n('views', r['views'])}), the visitor clicked the same spot three or more times in a hurry.",
            f"Page: {r['page']}.",
            "something that looks clickable does not respond (for example a coupon or apply button).",
            f"Check every button on {r['page']} for a delay or error, and show a clear response when it is clicked.",
            f, r["rage_views"], _confidence(r["views"]), "rage_clicks"))
    for r in iss["hidden_pages"]:
        f = Facts()
        out.append(_finding(
            "B5", "behaviour", f"{r['page']} is useful but hidden",
            f"Only {f.n('links_in', r['links_in'])} page on your site links to {r['page']} (rank {f.n('designed_rank', r['designed_rank'])} of {f.n('pages', len(C.PAGES))} by links). "
            f"Still, {f.pct('direct', r['arrive_directly_share'])} of its {f.n('visits', r['visits'])} visits started right there, and visitors who saw it bought "
            f"{f.f1('lift', r['conversion_lift'])} times as often as the average human.",
            f"Page: {r['page']}.",
            "people search for it on their own because it answers a buying question.",
            f"Link to {r['page']} from product pages and the cart, so more people see it.",
            f, r["visits"], _confidence(r["visits"]), "hidden_page"))
    for r in iss["type_gap"]:
        if r["gap"] <= 0:
            continue                   # only "agents fail where humans pass" is reported as the gap issue
        f = Facts()
        out.append(_finding(
            "B6", "behaviour", f"AI agents fail at {r['step']}",
            f"At {r['step']}, {f.pct('human_rate', r['human_rate'])} of humans continued but only {f.pct('agent_rate', r['agent_rate'])} of AI agents did "
            f"(humans: {f.n('human_n', r['human_n'])}, agents: {f.n('agent_n', r['agent_n'])}).",
            f"Checkout step: {r['step']}.",
            "the form or button is hard for automated browsers to use, so customers who shop through an AI assistant cannot finish.",
            "Test the page with an AI browser agent, and make form fields clearly labelled and simple.",
            f, r["agent_n"], _confidence(r["agent_n"], 100, 30), "type_gap"))

    # ----------------------------------------------------------- LINK
    for r in ln["expectation_mismatches"]:
        if r["source"] == "cheap_ads":
            continue                 # already covered by the low-quality source finding
        f = Facts()
        out.append(_finding(
            "L1", "link", f"{r['source']} visitors leave at {r['page']}",
            f"{f.pct('exit_rate', r['exit_rate'])} of human visits from {r['source']} ended at {r['page']}, against {f.pct('others', r['others_exit_rate'])} for visitors from all other sources "
            f"({f.n('visits', r['visits'])} visits).",
            f"Source {r['source']}, page {r['page']}.",
            "the promise made by this source does not match what the page shows.",
            f"Make the {r['page']} page match the {r['source']} message, or change the message.",
            f, r["visits"] * r["difference"], _confidence(r["visits"]), "expectation_mismatch"))
    f = Facts()
    da = be["dirty_averages"]
    out.append(_finding(
        "L2", "link", "Bots and agents distort your averages",
        f"Counting everyone, the bounce rate is {f.pct('raw_bounce', da['everyone']['bounce_rate'], 1)} and conversion is {f.pct('raw_conv', da['everyone']['conversion'], 1)}. "
        f"Counting only visitors judged human, bounce rate is {f.pct('clean_bounce', da['cleaned_humans']['bounce_rate'], 1)} and conversion is {f.pct('clean_conv', da['cleaned_humans']['conversion'], 1)}.",
        "Whole site.",
        "non-human visits are mixed into your normal numbers.",
        "Report on cleaned (human-only) numbers, and show bots and agents separately.",
        f, total - nh, "high", "dirty_averages"))
    return out


def rank(findings):
    ok = [x for x in findings if x["confidence"] != "rejected"]
    pick = lambda side: sorted([x for x in ok if x["side"] == side], key=lambda x: -x["impact_visits"])
    return dict(traffic=pick("traffic")[:3], behaviour=pick("behaviour")[:3], link=pick("link"))


def to_markdown(findings):
    top = rank(findings)
    L = [f"# {C.PRODUCT_NAME}: issue report", f"*{C.SUBTITLE}*", "",
         "Every number below was calculated by the system. Causes are guesses and are marked as such.", ""]
    L += ["## Top fixes", "", "**Web traffic**"]
    for x in top["traffic"]:
        L.append(f"- {x['title']}: {x['fix']}")
    L += ["", "**User behaviour**"]
    for x in top["behaviour"]:
        L.append(f"- {x['title']}: {x['fix']}")
    L += ["", "**Traffic and behaviour together**"]
    for x in top["link"]:
        L.append(f"- {x['title']}: {x['fix']}")
    L += ["", "---", "", "## All findings", ""]
    for side, name in [("traffic", "Web traffic"), ("behaviour", "User behaviour"), ("link", "Traffic and behaviour together")]:
        L += [f"### {name}", ""]
        for x in sorted([y for y in findings if y["side"] == side], key=lambda y: -y["impact_visits"]):
            L += [f"**{x['id']}. {x['title']}**  (confidence: {x['confidence']})", "",
                  f"- **What happened:** {x['what_happened']}", f"- **Where:** {x['where']}",
                  f"- **Likely cause:** {x['likely_cause']}", f"- **Fix first:** {x['fix']}", ""]
    return "\n".join(L)


def run(verbose=True):
    findings = build()
    (C.OUT_DIR / "findings.json").write_text(json.dumps(findings, indent=2))
    C.REPORT_DIR.mkdir(exist_ok=True)
    (C.REPORT_DIR / "AGENT_REPORT.md").write_text(to_markdown(findings))
    if verbose:
        bad = [x["id"] for x in findings if x["confidence"] == "rejected"]
        print(f"  wrote {len(findings)} findings; rejected for unverified numbers: {bad or 'none'}")
    return findings


if __name__ == "__main__":
    run()
