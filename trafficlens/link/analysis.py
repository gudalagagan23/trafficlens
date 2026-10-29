"""
The link layer: where WEB TRAFFIC and USER BEHAVIOUR meet.

Neither half alone can answer these:
  - "Visitors from source X leave at page Y far more than everyone else."
     (a traffic fact + a behaviour fact together)
  - "Humans finish checkout, agents do not." (visitor type + journey step)
  - "Which sources bring visitors who actually go deep and buy?"

Reads only the outputs of the two halves. Never reads the answer key.
"""
import json

import numpy as np
import pandas as pd

import config as C


def source_page_exits(views, sessions, preds, min_visits=80):
    """For each (source, landing page): how often do humans from this source leave
    right at that page, compared with all other humans on that page?"""
    h_ids = set(preds.loc[preds["pred_label"] == "human", "session_id"])
    v = views[views["session_id"].isin(h_ids)].sort_values(["session_id", "step"])
    src = sessions.set_index("session_id")["source"]
    last = v.groupby("session_id").tail(1).set_index("session_id")["page"]
    v = v.assign(source=v["session_id"].map(src))
    v["is_exit"] = v.index.isin(v.groupby("session_id").tail(1).index)
    page_overall = v.groupby("page")["is_exit"].mean()
    rows = []
    for (s, p), g in v.groupby(["source", "page"]):
        if len(g) < min_visits:
            continue
        # compare with everyone ELSE on that page
        other = v[(v["page"] == p) & (v["source"] != s)]
        other_rate = float(other["is_exit"].mean()) if len(other) else float("nan")
        rate = float(g["is_exit"].mean())
        rows.append(dict(source=s, page=p, visits=int(len(g)), exit_rate=round(rate, 3),
                         others_exit_rate=round(other_rate, 3),
                         ratio=round(rate / other_rate, 2) if other_rate else None,
                         difference=round(rate - other_rate, 3)))
    t = pd.DataFrame(rows)
    t["mismatch"] = (t["difference"] >= 0.25) & (t["ratio"] >= 2.0)
    return t.sort_values("difference", ascending=False)


def per_source_journey(views, sessions, preds):
    h_ids = set(preds.loc[preds["pred_label"] == "human", "session_id"])
    v = views[views["session_id"].isin(h_ids)]
    src = sessions.set_index("session_id")["source"]
    out = {}
    for s, ids in src[src.index.isin(h_ids)].groupby(src[src.index.isin(h_ids)]):
        vv = v[v["session_id"].isin(set(ids.index))]
        n = vv["session_id"].nunique()
        pages = vv.groupby("session_id")["page"].apply(list)
        last = pages.apply(lambda x: x[-1])
        out[s] = dict(humans=int(n),
                      top_exit_pages=[dict(page=p, share=round(float(c / n), 3)) for p, c in last.value_counts().head(3).items()],
                      bounce_rate=round(float(np.mean([len(x) == 1 for x in pages])), 3),
                      conversion=round(float(np.mean(["confirmation" in x for x in pages])), 4),
                      mean_pages=round(float(np.mean([len(x) for x in pages])), 2))
    return out


def run(verbose=True):
    s = pd.read_csv(C.DATA_DIR / "sessions.csv")
    v = pd.read_csv(C.DATA_DIR / "pageviews.csv")
    p = pd.read_csv(C.OUT_DIR / "predictions.csv")
    q = pd.read_csv(C.OUT_DIR / "source_quality.csv")
    beh = json.loads((C.OUT_DIR / "behaviour_results.json").read_text())

    sp = source_page_exits(v, s, p)
    sp.to_csv(C.OUT_DIR / "source_page_exits.csv", index=False)
    mism = sp[sp["mismatch"]].to_dict("records")
    res = dict(
        source_by_journey=per_source_journey(v, s, p),
        expectation_mismatches=mism,
        human_vs_agent_checkout=dict(
            human=beh["types"]["human"]["funnel"]["steps"],
            ai_agent=beh["types"]["ai_agent"]["funnel"]["steps"] if "ai_agent" in beh["types"] else [],
        ),
        source_quality=q.to_dict("records"),
    )
    (C.OUT_DIR / "link_results.json").write_text(json.dumps(res, indent=2, default=str))
    if verbose:
        print("  source-vs-page mismatches:", [(m["source"], m["page"], m["exit_rate"], m["others_exit_rate"]) for m in mism])
    return res


if __name__ == "__main__":
    run()
