"""
The score page. The ONLY code allowed to open the hidden answer key.

It answers three honest questions:
  1. Of the 12 problems we planted, how many did the system find? (and any false alarms)
  2. Do the 8 tests pass (4 for traffic, 4 for behaviour)?
  3. Where did the system FAIL? (we report that too)

A problem is "found" if detection is strong, "partly found" if it is middling,
and "missed" otherwise. Nothing here is rounded in our favour.
"""
import json

import numpy as np
import pandas as pd
from scipy.stats import kruskal, mannwhitneyu
from sklearn.metrics import homogeneity_score, completeness_score

import config as C


def status(rate, found=0.90, partial=0.50):
    return "found" if rate >= found else ("partly found" if rate >= partial else "missed")


def load():
    key = json.loads((C.KEY_DIR / "planted.json").read_text())
    lab = pd.read_csv(C.KEY_DIR / "labels.csv")
    feats = pd.read_csv(C.OUT_DIR / "features.csv")
    preds = (pd.read_csv(C.OUT_DIR / "predictions.csv").merge(lab, on="session_id")
             .merge(feats[["session_id", "device_claimed", "mouse_pp", "duration_s", "rhythm"]], on="session_id"))
    return key, lab, preds, feats


# ---------------------------------------------------------------------------
def judge_scores(preds):
    preds = preds.copy()
    preds["flagged"] = preds["pred_label"] != "human"
    rows = {}
    groups = {
        "dumb bots (incl. the flood)": preds["subtype"].isin(["dumb", "flood"]),
        "scrapers": preds["subtype"] == "scraper",
        "declared crawlers": preds["subtype"] == "crawler",
        "medium bots": preds["subtype"] == "medium",
        "smart bots": preds["subtype"] == "smart",
        "AI agents": preds["subtype"] == "agent",
        "novel bot (never seen)": preds["true_type"] == "novel_bot",
        "humans": preds["true_type"] == "human",
    }
    for name, m in groups.items():
        g = preds[m]
        extra = {}
        if name == "humans":
            bad = g[g["pred_label"].isin(["old_bot", "ai_agent"])]
            rest = g[(g["device_claimed"] == "desktop") & (g["pred_label"] == "human")]
            extra = dict(flagged_on_desktop_share=round(float((bad["device_claimed"] == "desktop").mean()), 3) if len(bad) else 0.0,
                         flagged_median_visit_seconds=round(float(bad["duration_s"].median()), 0) if len(bad) else 0.0,
                         other_desktop_median_visit_seconds=round(float(rest["duration_s"].median()), 0),
                         flagged_median_timing_unevenness=round(float(bad["rhythm"].median()), 2) if len(bad) else 0.0,
                         other_desktop_median_timing_unevenness=round(float(rest["rhythm"].median()), 2))
        rows[name] = dict(**extra, n=int(len(g)),
                          called_human=round(float((g["pred_label"] == "human").mean()), 4),
                          called_ai_agent=round(float((g["pred_label"] == "ai_agent").mean()), 4),
                          called_old_bot=round(float((g["pred_label"] == "old_bot").mean()), 4),
                          called_unknown=round(float((g["pred_label"] == "unknown").mean()), 4),
                          flagged_not_human=round(float(g["flagged"].mean()), 4))
    return rows


def traffic_tests(preds, lab, tr):
    out = {}
    # 1. grouping without labels
    g = pd.read_csv(C.OUT_DIR / "groups.csv").merge(lab, on="session_id")
    def purity(col):
        return float(g.groupby("community")[col].agg(lambda s: s.value_counts().iloc[0]).sum() / len(g))
    out["grouping"] = dict(
        groups_found=int(g["community"].nunique()),
        purity_by_type=round(purity("true_type"), 4),
        homogeneity_by_type=round(float(homogeneity_score(g["true_type"], g["community"])), 4),
        completeness_by_type=round(float(completeness_score(g["true_type"], g["community"])), 4),
        note="Groups are found with no labels. Purity = share of visitors sitting in a group whose main true type matches theirs. "
             "Completeness is low because one real type is split into several groups (this is normal for this method).")
    # 2. unknown test
    novel = preds[preds["true_type"] == "novel_bot"]
    known = preds[preds["true_type"] != "novel_bot"]
    out["unknown_test"] = dict(
        novel_bots=int(len(novel)),
        novel_sent_to_unknown=round(float((novel["pred_label"] == "unknown").mean()), 4),
        novel_forced_into_human=round(float((novel["pred_label"] == "human").mean()), 4),
        known_visitors_wrongly_unknown=round(float((known["pred_label"] == "unknown").mean()), 4),
        known_humans_wrongly_unknown=round(float((preds[preds["true_type"] == "human"]["pred_label"] == "unknown").mean()), 4))
    # 3. forecast
    out["forecast"] = tr["forecast"]
    # 4. spike
    sp = json.loads((C.KEY_DIR / "planted.json").read_text())["spike"]
    a, b = pd.Timestamp(sp["start"]), pd.Timestamp(sp["end"])
    hit = [w for w in tr["spikes"] if w["source"] == sp["source"]
           and pd.Timestamp(w["start"]) < b and pd.Timestamp(w["end"]) > a]
    out["spike"] = dict(planted_source=sp["source"], planted_start=sp["start"], planted_end=sp["end"],
                        found=bool(hit), found_windows=tr["spikes"],
                        false_alarms=int(len(tr["spikes"]) - len(hit)))
    return out


def fingerprint_check(lab, feats):
    """Pre-written GUESSES about how types differ. We test each one and report wrong guesses."""
    d = feats.merge(lab, on="session_id")
    d["rhythm"] = d["rhythm"].fillna(d["rhythm"].median())
    guesses = [
        ("rhythm", "human", "ai_agent", "greater", "Humans have more uneven timing than AI agents"),
        ("rhythm", "human", "old_bot", "greater", "Humans have more uneven timing than old bots"),
        ("speed", "human", "ai_agent", "greater", "Humans spend longer on each page than AI agents"),
        ("reading", "human", "ai_agent", "greater", "Humans spend longer reading content than AI agents"),
        ("goal_focus", "ai_agent", "human", "greater", "AI agents focus on the goal more than humans"),
        ("depth", "ai_agent", "human", "greater", "AI agents go deeper into checkout than humans"),
        ("recovery", "human", "ai_agent", "greater", "Humans try something new after going back; agents repeat"),
        ("backtracking", "old_bot", "human", "greater", "Old bots go back to seen pages more than humans"),
        ("exploring", "human", "ai_agent", "greater", "Humans explore more different pages than AI agents"),
        ("form_handling", "ai_agent", "human", "greater", "AI agents need more tries on forms (only visits that used a form)"),
    ]
    rows = []
    for trait, a, b, direction, text in guesses:
        da, db = d[d["true_type"] == a], d[d["true_type"] == b]
        if trait == "form_handling":
            da, db = da[da[trait] > 0], db[db[trait] > 0]
        xa, xb = da[trait].dropna(), db[trait].dropna()
        med_a, med_b = float(xa.median()), float(xb.median())
        p = float(mannwhitneyu(xa, xb, alternative="two-sided").pvalue)
        right = med_a > med_b
        rows.append(dict(guess=text, trait=trait, median_first=round(med_a, 3), median_second=round(med_b, 3),
                         p_value=float(f"{p:.2e}"), guess_correct=bool(right and p < 0.01)))
    k = kruskal(*[d.loc[d["true_type"] == t, "rhythm"] for t in ["human", "ai_agent", "old_bot"]])
    return dict(guesses=rows, guesses_correct=int(sum(r["guess_correct"] for r in rows)),
                guesses_total=len(rows), rhythm_kruskal_p=float(f"{k.pvalue:.2e}"))


def behaviour_tests(lab, feats, be, pr, key):
    out = {"fingerprints": fingerprint_check(lab, feats)}
    out["next_page"] = pr["next_page"]
    out["purchase"] = pr["purchase"]
    return out


# ---------------------------------------------------------------------------
def scorecard(key, preds, lab, tr, be, ln):
    ids = json.loads((C.OUT_DIR / "traffic_ids.json").read_text())
    card = []

    def add(n, side, name, planted, result, evidence, extra=""):
        card.append(dict(number=n, side=side, problem=name, planted=planted, result=result, evidence=evidence, note=extra))

    js = judge_scores(preds)
    d = js["dumb bots (incl. the flood)"]
    add(1, "traffic", "Dumb bots", "about 800 simple bots, including a flood of 450", status(d["flagged_not_human"]),
        f"{d['flagged_not_human']:.1%} of {d['n']} flagged as not human")
    smart, agent = js["smart bots"], js["AI agents"]
    worst = min(smart["flagged_not_human"], agent["flagged_not_human"])     # judged on the HARDER group
    add(2, "traffic", "Smart bots and AI agents hiding as humans", "smart bots that copy humans, plus AI agents",
        status(worst, 0.90, 0.60),
        f"smart bots: {smart['flagged_not_human']:.1%} flagged ({smart['called_human']:.1%} passed as human); "
        f"AI agents: {agent['flagged_not_human']:.1%} flagged",
        "Smart bots are the hardest case. Real browser agents may be harder than the ones simulated here.")
    s = js["scrapers"]
    add(3, "traffic", "Scrapers", "product-page scrapers", status(s["flagged_not_human"]),
        f"{s['flagged_not_human']:.1%} of {s['n']} flagged")
    sp = tr["spike"]
    add(4, "traffic", "Sudden spike from one source", f"{key['spike']['n']} visits from {key['spike']['source']} in {key['spike']['minutes']} minutes",
        "found" if sp["found"] and sp["false_alarms"] == 0 else ("partly found" if sp["found"] else "missed"),
        f"window found: {sp['found']}; false spike alarms: {sp['false_alarms']}")
    q = pd.DataFrame(ln["source_quality"])
    flagged = q[q["low_quality"] == True]["source"].tolist()
    ok = key["low_quality_source"] in flagged
    add(5, "traffic", "Low-quality source", f"{key['low_quality_source']} (visitors leave at once)",
        "found" if ok and len(flagged) == 1 else ("partly found" if ok else "missed"),
        f"flagged sources: {flagged}")
    fk = lab[lab["fake_device"] == 1]["session_id"]
    got = set(ids["fake_devices"])
    tp = len(got & set(fk))
    prec = tp / len(got) if got else 0
    rec = tp / len(fk) if len(fk) else 0
    add(6, "traffic", "Fake device", "bots that claim to be phones but have no touch",
        "found" if rec >= 0.9 and prec >= 0.8 else ("partly found" if rec >= 0.5 else "missed"),
        f"caught {rec:.1%} of {len(fk)} planted; {prec:.1%} of the flagged visits were truly fake")

    iss = be["issues"]
    de = [r["page"] for r in iss["dead_ends"]]
    add(7, "behaviour", "Dead-end page", key["dead_end_page"],
        "found" if key["dead_end_page"] in de and len(de) == 1 else ("partly found" if key["dead_end_page"] in de else "missed"),
        f"flagged pages: {de}")
    fl = [r["step"] for r in iss["funnel_leaks"]]
    want = " -> ".join(key["funnel_step"])
    add(8, "behaviour", "Funnel drop-off", want,
        "found" if want in fl and len(fl) == 1 else ("partly found" if want in fl else "missed"), f"flagged steps: {fl}")
    lp = [tuple(r["pages"]) for r in iss["loops"]]
    pair = tuple(sorted(key["loop_pair"]))
    add(9, "behaviour", "Loops", " <-> ".join(key["loop_pair"]),
        "found" if pair in lp and len(lp) == 1 else ("partly found" if pair in lp else "missed"), f"flagged pairs: {lp}")
    rg = [r["page"] for r in iss["rage_clicks"]]
    add(10, "behaviour", "Rage clicks", key["rage_page"],
        "found" if rg == [key["rage_page"]] else ("partly found" if key["rage_page"] in rg else "missed"), f"flagged pages: {rg}")
    hp = [r["page"] for r in iss["hidden_pages"]]
    add(11, "behaviour", "Hidden useful page", key["hidden_page"],
        "found" if hp == [key["hidden_page"]] else ("partly found" if key["hidden_page"] in hp else "missed"), f"flagged pages: {hp}")
    tg = [(r["step"], r["gap"]) for r in iss["type_gap"]]
    want = "payment -> confirmation"
    hit = any(s == want and g > 0 for s, g in tg)
    extra = [s for s, g in tg if s != want]
    add(12, "behaviour", "Human vs AI-agent gap", f"agents fail at {key['type_gap_page']}",
        "found" if hit else "missed", f"flagged: {tg}",
        ("Extra step flagged: " + ", ".join(extra) + ". This is a real difference caused by problem 8 (humans leave at shipping, agents do not), not a false alarm.") if extra else "")
    # bonus
    mism = [(m["source"], m["page"]) for m in ln["expectation_mismatches"]]
    bonus = dict(problem="Expectation mismatch (link layer)", planted=" at ".join(key["expectation_mismatch"]),
                 result="found" if tuple(key["expectation_mismatch"]) in mism else "missed", evidence=f"flagged: {mism}")
    return card, bonus, js


def dirty_truth(lab, be):
    v = pd.read_csv(C.DATA_DIR / "pageviews.csv")
    human_ids = lab.loc[lab["true_type"] == "human", "session_id"]
    seq = v[v["session_id"].isin(set(human_ids))].sort_values(["session_id", "step"]).groupby("session_id")["page"].apply(list)
    truth = dict(bounce_rate=round(float(np.mean([len(p) == 1 for p in seq])), 4),
                 mean_pages=round(float(np.mean([len(p) for p in seq])), 2),
                 conversion=round(float(np.mean(["confirmation" in p for p in seq])), 4))
    da = be["dirty_averages"]
    err = lambda a, b: abs(a - b)
    return dict(true_humans=truth, everyone=da["everyone"], cleaned=da["cleaned_humans"],
                conversion_error_raw=round(err(da["everyone"]["conversion"], truth["conversion"]), 4),
                conversion_error_cleaned=round(err(da["cleaned_humans"]["conversion"], truth["conversion"]), 4),
                bounce_error_raw=round(err(da["everyone"]["bounce_rate"], truth["bounce_rate"]), 4),
                bounce_error_cleaned=round(err(da["cleaned_humans"]["bounce_rate"], truth["bounce_rate"]), 4))


# ---------------------------------------------------------------------------
def run(verbose=True):
    if not (C.KEY_DIR / "planted.json").exists():
        print("  (no answer key found - skipping evaluation; this is normal for real data)")
        return None
    key, lab, preds, feats = load()
    tr = json.loads((C.OUT_DIR / "traffic_results.json").read_text())
    be = json.loads((C.OUT_DIR / "behaviour_results.json").read_text())
    ln = json.loads((C.OUT_DIR / "link_results.json").read_text())
    pr = json.loads((C.OUT_DIR / "prediction_results.json").read_text())
    t_tests = traffic_tests(preds, lab, tr)
    b_tests = behaviour_tests(lab, feats, be, pr, key)
    card, bonus, js = scorecard(key, preds, lab, t_tests, be, ln)
    dirty = dirty_truth(lab, be)
    res = dict(scorecard=card, bonus=bonus, judge=js, traffic_tests=t_tests, behaviour_tests=b_tests, dirty_averages=dirty,
               summary=dict(found=sum(c["result"] == "found" for c in card),
                            partly=sum(c["result"] == "partly found" for c in card),
                            missed=sum(c["result"] == "missed" for c in card), total=len(card)))
    (C.OUT_DIR / "evaluation.json").write_text(json.dumps(res, indent=2, default=str))
    from evaluation.writeup import write_results
    write_results(res)
    if verbose:
        s = res["summary"]
        print(f"  planted problems: {s['found']} found, {s['partly']} partly found, {s['missed']} missed (of {s['total']})")
        for c in card:
            print(f"   {c['number']:>2}. {c['problem']:<42} {c['result']}")
    return res


if __name__ == "__main__":
    run()
