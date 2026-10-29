"""
Traffic intelligence (Part A) - everything about WHO is visiting.

  1. grouping       : find natural groups of visitors WITHOUT using any labels
                      (a visitor-similarity graph + community detection)
  2. spikes         : sudden bursts of visits from one source
  3. source quality : which sources bring real, engaged visitors
  4. fake devices   : "phones" that never touch the screen
  5. signatures     : plain rules that describe dumb bots and scrapers
  6. forecast       : expected visits per source per hour (and how well we beat a simple guess)

This file never reads the answer key.
"""
import json

import networkx as nx
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

import config as C
from traffic.classifier import FEATURES, _matrix


# ---------------------------------------------------------------------------
# 1. Group visitors with no labels
# ---------------------------------------------------------------------------
def group_visitors(feats, preds, k=20):
    """Link each visitor to the 20 most similar visitors, then let a
    community-finding method discover the groups by itself."""
    X = _matrix(feats)
    Xs = StandardScaler().fit_transform(SimpleImputer(strategy="median").fit_transform(X))
    nn = NearestNeighbors(n_neighbors=k + 1).fit(Xs)
    d, idx = nn.kneighbors(Xs)
    G = nx.Graph()
    G.add_nodes_from(range(len(feats)))
    for i in range(len(feats)):
        for dist, j in zip(d[i, 1:], idx[i, 1:]):
            w = 1.0 / (1.0 + dist)
            if G.has_edge(i, j):
                G[i][j]["weight"] = max(G[i][j]["weight"], w)
            else:
                G.add_edge(i, int(j), weight=w)
    comms = nx.community.louvain_communities(G, weight="weight", resolution=0.1, seed=C.SEED)
    comm_of = np.zeros(len(feats), int)
    for ci, members in enumerate(sorted(comms, key=len, reverse=True)):
        for m in members:
            comm_of[m] = ci
    out = pd.DataFrame({"session_id": feats["session_id"].values, "community": comm_of})
    pl = preds.set_index("session_id")["pred_label"]
    out["pred_label"] = out["session_id"].map(pl)
    summary = []
    for ci, g in out.groupby("community"):
        top = g["pred_label"].value_counts()
        summary.append(dict(community=int(ci), size=int(len(g)), main_label=str(top.index[0]),
                            main_label_share=round(float(top.iloc[0] / len(g)), 3)))
    return out, summary


def similarity_sample(feats, preds, groups, n=700, k=6):
    """A small version of the similarity graph just for drawing."""
    rng = np.random.default_rng(C.SEED)
    idx = np.sort(rng.choice(len(feats), size=min(n, len(feats)), replace=False))
    sub = feats.iloc[idx]
    X = _matrix(sub)
    Xs = StandardScaler().fit_transform(SimpleImputer(strategy="median").fit_transform(X))
    nn = NearestNeighbors(n_neighbors=k + 1).fit(Xs)
    d, nb = nn.kneighbors(Xs)
    edges = sorted({tuple(sorted((int(i), int(j)))) for i in range(len(sub)) for j in nb[i, 1:]})
    lab = preds.set_index("session_id").loc[sub["session_id"], "pred_label"].tolist()
    com = groups.set_index("session_id").loc[sub["session_id"], "community"].tolist()
    return dict(nodes=[dict(id=i, label=lab[i], community=int(com[i])) for i in range(len(sub))],
                edges=[list(e) for e in edges])


# ---------------------------------------------------------------------------
# 2. Spikes
# ---------------------------------------------------------------------------
def detect_spikes(sessions, views, preds, min_count=25, z_cut=6.0):
    """Count visits per source in 15-minute slots. Compare each slot with the
    median of the SAME slot on the other days. A far-above-normal slot is a spike."""
    s = sessions.copy()
    s["ts"] = pd.to_datetime(s["start_ts"])
    t0 = s["ts"].min().normalize()
    s["slot"] = ((s["ts"] - t0).dt.total_seconds() // 900).astype(int)
    n_slots = int(s["slot"].max()) + 1
    n_days = int(np.ceil(n_slots / 96))
    pl = preds.set_index("session_id")["pred_label"]
    paths = views.groupby("session_id")["page"].apply(lambda x: ">".join(x))
    s["path"] = s["session_id"].map(paths)
    s["pred_label"] = s["session_id"].map(pl)
    flagged = []
    for src, g in s.groupby("source"):
        counts = np.zeros(n_days * 96)
        for slot, c in g.groupby("slot").size().items():
            counts[slot] = c
        grid = counts.reshape(n_days, 96)
        for day in range(n_days):
            others = np.delete(grid, day, axis=0)
            expected = np.median(others, axis=0)
            z = (grid[day] - expected) / np.sqrt(expected + 1.0)
            for slot in np.where((z >= z_cut) & (grid[day] >= min_count))[0]:
                flagged.append((src, day * 96 + int(slot), float(grid[day][slot]), float(expected[slot]), float(z[slot])))
    if not flagged:
        return []
    fl = pd.DataFrame(flagged, columns=["source", "slot", "count", "expected", "z"]).sort_values(["source", "slot"])
    windows, cur = [], None
    for r in fl.itertuples():
        if cur and r.source == cur["source"] and r.slot <= cur["last"] + 1:
            cur["last"] = r.slot
            cur["count"] += r.count
            cur["expected"] += r.expected
            cur["zmax"] = max(cur["zmax"], r.z)
        else:
            if cur:
                windows.append(cur)
            cur = dict(source=r.source, first=r.slot, last=r.slot, count=r.count,
                       expected=r.expected, zmax=r.z)
    windows.append(cur)
    out = []
    for w in windows:
        a = t0 + pd.Timedelta(seconds=w["first"] * 900)
        b = t0 + pd.Timedelta(seconds=(w["last"] + 1) * 900)
        inside = s[(s["source"] == w["source"]) & (s["ts"] >= a) & (s["ts"] < b)]
        top = inside["path"].value_counts()
        # how many days of this source's usual traffic arrived in this short window
        src_rows = s[s["source"] == w["source"]]
        other = src_rows[~((src_rows["ts"] >= a) & (src_rows["ts"] < b))]
        daily_normal = len(other) / n_days
        out.append(dict(
            source=w["source"], start=str(a), end=str(b), visits=int(w["count"]),
            normal_visits=round(float(w["expected"]), 1),
            times_normal=round(float(w["count"] / max(w["expected"], 1.0)), 1),
            days_of_usual_traffic=round(float(w["count"] / max(daily_normal, 1.0)), 1),
            usual_visits_per_day=round(float(daily_normal), 1),
            same_path_share=round(float(top.iloc[0] / len(inside)), 3) if len(inside) else 0.0,
            flagged_non_human_share=round(float((inside["pred_label"] != "human").mean()), 3),
            peak_z=round(float(w["zmax"]), 1),
        ))
    return out


# ---------------------------------------------------------------------------
# 3. Source quality
# ---------------------------------------------------------------------------
def source_quality(feats, preds):
    d = feats.merge(preds[["session_id", "pred_label"]], on="session_id")
    d["converted"] = (d["depth"] >= 1.0).astype(int)
    rows = []
    for src, g in d.groupby("source"):
        h = g[g["pred_label"] == "human"]
        human_share = len(h) / len(g)
        bounce = float(h["single_page"].mean()) if len(h) else 1.0
        depth = float(h["depth"].mean()) if len(h) else 0.0
        conv = float(h["converted"].mean()) if len(h) else 0.0
        score = 100 * (0.30 * human_share + 0.25 * (1 - bounce)
                       + 0.25 * min(depth / 0.25, 1.0) + 0.20 * min(conv / 0.03, 1.0))
        if len(h) < 30:           # almost no humans: a human-quality score would mislead
            score = np.nan
        rows.append(dict(source=src, visits=int(len(g)), human_share=round(human_share, 3),
                         bot_or_agent_share=round(float(g["pred_label"].isin(["old_bot", "ai_agent"]).mean()), 3),
                         unknown_share=round(float((g["pred_label"] == "unknown").mean()), 3),
                         human_bounce_rate=round(bounce, 3), human_depth=round(depth, 3),
                         human_conversion=round(conv, 4), quality_score=round(score, 1)))
    q = pd.DataFrame(rows).sort_values("quality_score", na_position="last")
    med = q["quality_score"].median()
    mad = float((q["quality_score"] - med).abs().median()) or 1.0
    q["z"] = ((q["quality_score"] - med) / (1.4826 * mad)).round(2)
    q["low_quality"] = (q["z"] <= -1.5) & (q["visits"] >= 100)
    q["note"] = np.where(q["quality_score"].isna(), "almost no human visitors (agents/bots only)", "")
    return q


# ---------------------------------------------------------------------------
# 4/5. Fake devices and simple "signatures"
# ---------------------------------------------------------------------------
def fake_devices(feats, preds):
    d = feats.merge(preds[["session_id", "pred_label"]], on="session_id")
    m = d[d["device_mismatch"] == 1]
    return dict(count=int(len(m)),
                share_of_all=round(float(len(m) / len(d)), 4),
                by_source={k: int(v) for k, v in m["source"].value_counts().items()},
                flagged_non_human_share=round(float((m["pred_label"] != "human").mean()), 3) if len(m) else 0.0,
                session_ids=m["session_id"].tolist())


def signatures(feats):
    """Plain-English rules that describe the simplest bots. Used for the report."""
    dumb = feats[(feats["mouse_pp"] == 0) & (feats["touch_pp"] == 0) & (feats["n_pages"] >= 3)
                 & (np.exp(feats["speed"]) - 1 < 1.5) & (feats["rhythm"] < 0.2)]
    scr = feats[(feats["item_seq_share"] > 0.6) & (feats["n_pages"] >= 25)]
    crawl = feats[feats["declared_crawler"] == 1]
    return dict(
        dumb_signature=dict(count=int(len(dumb)), session_ids=dumb["session_id"].tolist()),
        scraper_signature=dict(count=int(len(scr)), session_ids=scr["session_id"].tolist()),
        declared_crawlers=dict(count=int(len(crawl)), session_ids=crawl["session_id"].tolist()),
    )


# ---------------------------------------------------------------------------
# 6. Forecast: expected visits per source per hour
# ---------------------------------------------------------------------------
def forecast(sessions, spike_windows):
    s = sessions.copy()
    s["ts"] = pd.to_datetime(s["start_ts"])
    t0 = s["ts"].min().normalize()
    s["hour_idx"] = ((s["ts"] - t0).dt.total_seconds() // 3600).astype(int)
    n_hours = int(s["hour_idx"].max()) + 1
    n_hours -= n_hours % 168                       # whole weeks only
    srcs = sorted(s["source"].unique())
    rows = []
    for src in srcs:
        cnt = np.zeros(n_hours)
        for h, c in s[s["source"] == src].groupby("hour_idx").size().items():
            if h < n_hours:
                cnt[h] = c
        for h in range(168, n_hours):
            prev = [cnt[h - 168 * k] for k in range(1, h // 168 + 1)]
            rows.append(dict(source=src, hour_idx=h, hour=h % 24, dow=(h // 24) % 7,
                             actual=cnt[h], last_week=cnt[h - 168], prev_mean=float(np.mean(prev)),
                             week=h // 168))
    df = pd.DataFrame(rows)
    df["src_code"] = df["source"].map({s_: i for i, s_ in enumerate(srcs)})
    # hours inside a flagged spike are not "normal", so they are left out of scoring
    df["spike_hour"] = False
    for w in spike_windows:
        a = (pd.Timestamp(w["start"]) - t0).total_seconds() / 3600
        b = (pd.Timestamp(w["end"]) - t0).total_seconds() / 3600
        df.loc[(df["source"] == w["source"]) & (df["hour_idx"] >= int(a)) & (df["hour_idx"] <= int(np.ceil(b))), "spike_hour"] = True
    last_week = df["week"].max()
    train = df[(df["week"] < last_week) & (~df["spike_hour"])]
    test = df[df["week"] == last_week].copy()
    X = ["hour", "dow", "src_code", "last_week", "prev_mean"]
    model = GradientBoostingRegressor(n_estimators=200, max_depth=3, learning_rate=0.05,
                                      subsample=0.8, random_state=C.SEED).fit(train[X], train["actual"])
    test["model"] = np.clip(model.predict(test[X]), 0, None)
    test["baseline"] = test["last_week"]
    scored = test[~test["spike_hour"]]
    mae_b = float((scored["actual"] - scored["baseline"]).abs().mean())
    mae_m = float((scored["actual"] - scored["model"]).abs().mean())
    metrics = dict(mae_baseline=round(mae_b, 3), mae_model=round(mae_m, 3),
                   improvement_pct=round(100 * (mae_b - mae_m) / mae_b, 1) if mae_b else 0.0,
                   model_wins=bool(mae_m < mae_b), hours_scored=int(len(scored)),
                   test_week=int(last_week) + 1)
    test["time"] = (t0 + pd.to_timedelta(test["hour_idx"], unit="h")).astype(str)
    return test[["source", "time", "actual", "baseline", "model", "spike_hour"]], metrics


# ---------------------------------------------------------------------------
def run(verbose=True):
    s = pd.read_csv(C.DATA_DIR / "sessions.csv")
    v = pd.read_csv(C.DATA_DIR / "pageviews.csv")
    feats = pd.read_csv(C.OUT_DIR / "features.csv")
    preds = pd.read_csv(C.OUT_DIR / "predictions.csv")

    groups, group_summary = group_visitors(feats, preds)
    groups.to_csv(C.OUT_DIR / "groups.csv", index=False)
    (C.OUT_DIR / "similarity_sample.json").write_text(json.dumps(similarity_sample(feats, preds, groups)))

    spikes = detect_spikes(s, v, preds)
    quality = source_quality(feats, preds)
    quality.to_csv(C.OUT_DIR / "source_quality.csv", index=False)
    fd = fake_devices(feats, preds)
    sig = signatures(feats)
    fc, fc_metrics = forecast(s, spikes)
    fc.to_csv(C.OUT_DIR / "forecast.csv", index=False)

    d = feats.merge(preds[["session_id", "pred_label"]], on="session_id")
    d["day"] = pd.to_datetime(d["start_ts"]).dt.date.astype(str)
    daily = d.groupby(["day", "pred_label"]).size().unstack(fill_value=0).reset_index()
    daily.to_csv(C.OUT_DIR / "daily_type_counts.csv", index=False)
    hourly = s.assign(hour=pd.to_datetime(s["start_ts"]).dt.floor("h")).groupby(["hour", "source"]).size().unstack(fill_value=0)
    hourly.reset_index().to_csv(C.OUT_DIR / "hourly_by_source.csv", index=False)

    counts = preds["pred_label"].value_counts().to_dict()
    res = dict(
        totals=dict(visits=int(len(preds)), **{k: int(v_) for k, v_ in counts.items()}),
        groups=group_summary, spikes=spikes, fake_devices={k: v_ for k, v_ in fd.items() if k != "session_ids"},
        signatures={k: v_["count"] for k, v_ in sig.items()},
        forecast=fc_metrics,
        crawler_share=round(float(feats["declared_crawler"].mean()), 4),
    )
    (C.OUT_DIR / "traffic_results.json").write_text(json.dumps(res, indent=2))
    # ids kept separately for evaluation (it is allowed to compare them with the key)
    (C.OUT_DIR / "traffic_ids.json").write_text(json.dumps(
        dict(fake_devices=fd["session_ids"], **{k: v_["session_ids"] for k, v_ in sig.items()})))
    if verbose:
        print(f"  found {len(group_summary)} natural visitor groups; {len(spikes)} spike(s)")
        for w in spikes:
            print(f"   spike: {w['source']} {w['start']} -> {w['end']}  {w['visits']} visits (= {w['days_of_usual_traffic']} days of usual traffic)")
        print("  forecast error: baseline", fc_metrics["mae_baseline"], "| model", fc_metrics["mae_model"])
        print("  lowest quality source:", quality.iloc[0]["source"], quality.iloc[0]["quality_score"])
    return res


if __name__ == "__main__":
    run()
