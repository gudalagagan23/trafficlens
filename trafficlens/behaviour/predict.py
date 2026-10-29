"""
Predictions on HUMAN visitors. Each one is compared with a simple baseline.
If the smarter model does not win, the result says so plainly.

  1. NEXT PAGE
       baseline : "people on page X usually go to page Y" (just counting)
       model    : gradient boosting that also looks at the last 2 pages, the step number,
                  device, traffic source, time on page, scrolling and rage clicks
  2. WILL THEY BUY (from only the first 3 pages)
       baseline : a rule - "did they reach the cart in the first 3 pages?"
       model    : gradient boosting on the first-3-pages features

Training uses the EARLIER 70% of visitors; testing uses the LATER 30%
(so we test on the future, not on shuffled data).
"""
import json

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import OrdinalEncoder

import config as C


def _human_views(views, sessions, preds):
    ids = preds.loc[preds["pred_label"] == "human", "session_id"]
    s = sessions[sessions["session_id"].isin(ids)].copy()
    s["start_ts"] = pd.to_datetime(s["start_ts"])
    s = s.sort_values("start_ts")
    v = views[views["session_id"].isin(ids)].sort_values(["session_id", "step"])
    return s, v


# ---------------------------------------------------------------------------
def next_page(sessions, views):
    rows = []
    sess = sessions.set_index("session_id")
    for sid, g in views.groupby("session_id", sort=False):
        pages = g["page"].tolist()
        dw, sc, rg = g["dwell_s"].tolist(), g["scroll_depth"].tolist(), g["rage_clicks"].tolist()
        src, dev = sess.at[sid, "source"], sess.at[sid, "device_claimed"]
        for i, p in enumerate(pages):
            rows.append(dict(session_id=sid, current=p,
                             prev=pages[i - 1] if i >= 1 else "START",
                             prev2=pages[i - 2] if i >= 2 else "START",
                             step=i, device=dev, source=src, dwell=dw[i], scroll=sc[i], rage=rg[i],
                             target=pages[i + 1] if i + 1 < len(pages) else "EXIT"))
    d = pd.DataFrame(rows)
    order = sessions.sort_values("start_ts")["session_id"].tolist()
    cut = order[int(len(order) * 0.7)]
    train_ids, test_ids = set(order[:int(len(order) * 0.7)]), set(order[int(len(order) * 0.7):])
    tr, te = d[d["session_id"].isin(train_ids)], d[d["session_id"].isin(test_ids)]

    # baseline: most common next page for each current page
    best = tr.groupby("current")["target"].agg(lambda x: x.value_counts().index[0])
    base_pred = te["current"].map(best).fillna("EXIT")
    base_acc = float((base_pred == te["target"]).mean())

    cat = ["current", "prev", "prev2", "device", "source"]
    num = ["step", "dwell", "scroll", "rage"]
    enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1).fit(tr[cat])
    def X(df):
        return np.hstack([enc.transform(df[cat]), df[num].to_numpy(float)])
    model = HistGradientBoostingClassifier(max_iter=80, learning_rate=0.1, max_depth=4,
                                           categorical_features=list(range(len(cat))),
                                           random_state=C.SEED)
    # unseen categories are -1, which a categorical feature cannot take, so shift by one
    Xtr, Xte = X(tr), X(te)
    Xtr[:, :len(cat)] += 1
    Xte[:, :len(cat)] += 1
    model.fit(Xtr, tr["target"])
    proba = model.predict_proba(Xte)
    classes = model.classes_
    pred = classes[proba.argmax(axis=1)]
    acc = float((pred == te["target"].to_numpy()).mean())
    top3 = np.argsort(-proba, axis=1)[:, :3]
    hit3 = np.mean([t in classes[row] for t, row in zip(te["target"], top3)])
    # top-3 for baseline = top-3 most common next pages for that page
    order3 = tr.groupby("current")["target"].agg(lambda x: list(x.value_counts().index[:3]))
    base_hit3 = float(np.mean([t in order3.get(c, []) for c, t in zip(te["current"], te["target"])]))
    return dict(train_steps=int(len(tr)), test_steps=int(len(te)),
                baseline_accuracy=round(base_acc, 4), model_accuracy=round(acc, 4),
                baseline_top3=round(base_hit3, 4), model_top3=round(float(hit3), 4),
                model_wins=bool(acc > base_acc),
                gain_points=round(100 * (acc - base_acc), 2))


# ---------------------------------------------------------------------------
def purchase(sessions, views):
    sess = sessions.set_index("session_id")
    rows = []
    for sid, g in views.groupby("session_id", sort=False):
        pages = g["page"].tolist()
        if len(pages) < 3:
            continue
        first = g.iloc[:3]
        r = dict(session_id=sid, bought=int("confirmation" in pages),
                 device=sess.at[sid, "device_claimed"], source=sess.at[sid, "source"],
                 entry=pages[0], dwell_mean=float(first["dwell_s"].mean()),
                 scroll_mean=float(first["scroll_depth"].mean()), rage=float(first["rage_clicks"].sum()))
        for p in C.PAGES:
            r[f"seen_{p}"] = int(p in pages[:3])
        rows.append(r)
    d = pd.DataFrame(rows)
    order = sessions.sort_values("start_ts")["session_id"].tolist()
    pos = {s: i for i, s in enumerate(order)}
    d["pos"] = d["session_id"].map(pos)
    cutoff = len(order) * 0.7
    tr, te = d[d["pos"] < cutoff], d[d["pos"] >= cutoff]
    cat = ["device", "source", "entry"]
    enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1).fit(tr[cat])
    num = [c for c in d.columns if c.startswith("seen_")] + ["dwell_mean", "scroll_mean", "rage"]
    def X(df):
        return np.hstack([enc.transform(df[cat]), df[num].to_numpy(float)])
    model = GradientBoostingClassifier(n_estimators=150, max_depth=3, learning_rate=0.05,
                                       subsample=0.8, random_state=C.SEED).fit(X(tr), tr["bought"])
    p_model = model.predict_proba(X(te))[:, 1]
    rule = te["seen_cart"].to_numpy(float)
    prior = float(tr["bought"].mean())
    out = dict(train_sessions=int(len(tr)), test_sessions=int(len(te)),
               buy_rate_in_test=round(float(te["bought"].mean()), 4),
               baseline_auc=round(float(roc_auc_score(te["bought"], rule)), 4),
               model_auc=round(float(roc_auc_score(te["bought"], p_model)), 4),
               baseline_avg_precision=round(float(average_precision_score(te["bought"], rule)), 4),
               model_avg_precision=round(float(average_precision_score(te["bought"], p_model)), 4),
               always_no_accuracy=round(1 - float(te["bought"].mean()), 4),
               prior_buy_rate=round(prior, 4))
    out["model_wins"] = bool(out["model_auc"] > out["baseline_auc"])
    return out


def run(verbose=True):
    s = pd.read_csv(C.DATA_DIR / "sessions.csv")
    v = pd.read_csv(C.DATA_DIR / "pageviews.csv")
    p = pd.read_csv(C.OUT_DIR / "predictions.csv")
    hs, hv = _human_views(v, s, p)
    res = dict(next_page=next_page(hs, hv), purchase=purchase(hs, hv))
    (C.OUT_DIR / "prediction_results.json").write_text(json.dumps(res, indent=2))
    if verbose:
        n, b = res["next_page"], res["purchase"]
        print(f"  next page : baseline {n['baseline_accuracy']:.1%}  model {n['model_accuracy']:.1%}  (top-3: {n['baseline_top3']:.1%} vs {n['model_top3']:.1%})")
        print(f"  will buy  : baseline AUC {b['baseline_auc']}  model AUC {b['model_auc']}")
    return res


if __name__ == "__main__":
    run()
