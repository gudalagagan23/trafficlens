"""
User behaviour intelligence (Part B) - what do visitors DO on the site?

IMPORTANT ORDER: this runs on visitors the traffic half judged to be HUMAN.
Mixing bots in would ruin every finding (bots make dead ends, loops and
bounce rates look different from what real people do).

Contents
  - journey graph per visitor type (pages are dots, moves are lines)
  - graph methods: PageRank, bridge pages (betweenness), shortest path, communities
  - 6 issue detectors: dead end, funnel drop-off, loops, rage clicks,
                       hidden useful page, human-vs-agent gap
  - the behaviour fingerprint comparison between visitor types

This file never reads the answer key. Thresholds are general rules
(for example "exit rate far above the other pages"), not tuned to any one page.
"""
import json
from collections import Counter, defaultdict

import networkx as nx
import numpy as np
import pandas as pd

import config as C

TRAITS = ["exploring", "depth", "backtracking", "recovery", "speed", "rhythm",
          "reading", "form_handling", "goal_focus"]
TRAIT_NAMES = {
    "exploring": "Exploring", "depth": "Depth", "backtracking": "Backtracking",
    "recovery": "Recovery", "speed": "Speed", "rhythm": "Uneven timing",
    "reading": "Reading time", "form_handling": "Form tries", "goal_focus": "Goal focus",
}


def sequences(views, ids):
    v = views[views["session_id"].isin(set(ids))].sort_values(["session_id", "step"])
    return v.groupby("session_id")["page"].apply(list)


# ---------------------------------------------------------------------------
# Journey graph
# ---------------------------------------------------------------------------
def designed_graph():
    G = nx.DiGraph()
    for a, outs in C.DESIGNED_LINKS.items():
        for b in outs:
            G.add_edge(a, b)
    return G


def journey_graph(seqs):
    """Build the real journey graph from a list of page-sequences."""
    edges, entries, exits, visits = Counter(), Counter(), Counter(), Counter()
    for pages in seqs:
        entries[pages[0]] += 1
        exits[pages[-1]] += 1
        for p in pages:
            visits[p] += 1
        for a, b in zip(pages[:-1], pages[1:]):
            edges[(a, b)] += 1
    G = nx.DiGraph()
    for p in C.PAGES:
        G.add_node(p, visits=visits[p], entries=entries[p], exits=exits[p])
    for (a, b), w in edges.items():
        G.add_edge(a, b, weight=w, dist=1.0 / w)
    return G


def graph_metrics(G, seqs):
    n = len(seqs)
    entry = {p: G.nodes[p]["entries"] / max(n, 1) for p in G}
    pers = {p: max(entry[p], 1e-6) for p in G}
    pr = nx.pagerank(G, alpha=0.85, weight="weight", personalization=pers) if G.number_of_edges() else {p: 0 for p in G}
    bt = nx.betweenness_centrality(G, weight="dist", normalized=True) if G.number_of_edges() else {p: 0 for p in G}
    U = nx.Graph()
    for a, b, d in G.edges(data=True):
        w = d["weight"] + (G[b][a]["weight"] if G.has_edge(b, a) else 0)
        if U.has_edge(a, b):
            continue
        U.add_edge(a, b, weight=w)
    comms = nx.community.louvain_communities(U, weight="weight", seed=C.SEED) if U.number_of_edges() else []
    comm = {}
    for i, c in enumerate(sorted(comms, key=len, reverse=True)):
        for p in c:
            comm[p] = i
    out = {}
    for p in G:
        vis = G.nodes[p]["visits"]
        out[p] = dict(visits=int(vis), entries=int(G.nodes[p]["entries"]), exits=int(G.nodes[p]["exits"]),
                      exit_rate=round(G.nodes[p]["exits"] / vis, 4) if vis else 0.0,
                      pagerank=round(pr[p], 5), betweenness=round(bt[p], 5), community=comm.get(p, -1))
    return out


def path_lengths(seqs):
    """Steps real converters took from entry to the confirmation page,
    compared with the shortest route the site's own links allow."""
    D = designed_graph()
    shortest = {}
    for p in C.PAGES:
        if p != "confirmation":
            try:
                shortest[p] = nx.shortest_path_length(D, p, "confirmation")
            except nx.NetworkXNoPath:
                pass
    actual, ideal = [], []
    for pages in seqs:
        if "confirmation" in pages:
            k = pages.index("confirmation")
            actual.append(k)
            if pages[0] in shortest:
                ideal.append(shortest[pages[0]])
    if not actual:
        return dict(converters=0)
    return dict(converters=len(actual), median_actual_steps=float(np.median(actual)),
                median_shortest_steps=float(np.median(ideal)) if ideal else None)


# ---------------------------------------------------------------------------
# The 6 issue detectors
# ---------------------------------------------------------------------------
def robust_z(values):
    v = np.array(values, float)
    med = np.median(v)
    mad = np.median(np.abs(v - med)) * 1.4826 or 1e-9
    return (v - med) / mad


def detect_dead_ends(metrics, min_visits=100):
    """A dead end is a NON-checkout page where more than half of everyone who
    arrives leaves, and that is at least twice what is normal on the other pages."""
    elig = [p for p, m in metrics.items() if p not in C.FUNNEL and m["visits"] >= min_visits]
    typical = float(np.median([metrics[p]["exit_rate"] for p in elig])) if elig else 0.0
    out = []
    for p in elig:
        r = metrics[p]["exit_rate"]
        if r >= 0.50 and r >= 2 * typical:
            out.append(dict(page=p, exit_rate=r, visits=metrics[p]["visits"],
                            typical_exit_rate=round(typical, 3), times_typical=round(r / typical, 1) if typical else None))
    return sorted(out, key=lambda r: -r["exit_rate"])


def funnel(seqs):
    steps = C.FUNNEL
    reached = {s: sum(1 for pg in seqs if s in pg) for s in steps}
    rows = []
    for a, b in zip(steps[:-1], steps[1:]):
        rate = reached[b] / reached[a] if reached[a] else None
        rows.append(dict(from_step=a, to_step=b, reached_from=int(reached[a]), reached_to=int(reached[b]),
                         continue_rate=round(rate, 4) if rate is not None else None))
    return dict(reached=reached, steps=rows)


def detect_funnel_leaks(f, min_reach=100, cut=0.50):
    return sorted([dict(step=f"{r['from_step']} -> {r['to_step']}", **r) for r in f["steps"]
                   if r["continue_rate"] is not None and r["reached_from"] >= min_reach and r["continue_rate"] < cut],
                  key=lambda r: r["continue_rate"])


def detect_loops(seqs, min_pair_sessions=50, min_triples=3, cut=0.25):
    """A loop is A -> B -> A -> B ... A pair is flagged when a large share of the
    visitors who touched both pages bounced between them again and again."""
    both, loopy = Counter(), Counter()
    for pages in seqs:
        trip = Counter()
        for i in range(2, len(pages)):
            if pages[i] == pages[i - 2] and pages[i] != pages[i - 1]:
                trip[tuple(sorted((pages[i], pages[i - 1])))] += 1
        sets = set(pages)
        for pair in {(a, b) for a in sets for b in sets if a < b}:
            both[pair] += 1
        for pair, c in trip.items():
            if c >= min_triples:
                loopy[pair] += 1
    out = []
    for pair, n in both.items():
        if n >= min_pair_sessions and loopy[pair] / n >= cut:
            out.append(dict(pages=list(pair), sessions_with_both=int(n), looping_sessions=int(loopy[pair]),
                            loop_rate=round(loopy[pair] / n, 3)))
    return sorted(out, key=lambda r: -r["loop_rate"])


def detect_rage(views, ids, min_views=100, cut=0.10):
    v = views[views["session_id"].isin(set(ids))]
    g = v.groupby("page").agg(views=("rage_clicks", "size"), rage=("rage_clicks", lambda x: int((x >= 3).sum())))
    g["rate"] = g["rage"] / g["views"]
    out = [dict(page=p, views=int(r.views), rage_views=int(r.rage), rate=round(float(r.rate), 3))
           for p, r in g.iterrows() if r.views >= min_views and r.rate >= cut]
    table = {p: round(float(r.rate), 4) for p, r in g.iterrows()}
    return sorted(out, key=lambda r: -r["rate"]), table


def detect_hidden(real_metrics, seqs, min_visits=100):
    """A hidden useful page: the site barely links to it, visitors find it on their
    own (arrive straight on it), and visitors who see it buy much more often.
    PageRank on the designed links vs the real journeys is reported as supporting evidence."""
    D = designed_graph()
    dpr = nx.pagerank(D, alpha=0.85)
    d_rank = {p: r for r, p in enumerate(sorted(dpr, key=lambda x: -dpr[x]), 1)}
    r_rank = {p: r for r, p in enumerate(sorted(real_metrics, key=lambda x: -real_metrics[x]["pagerank"]), 1)}
    n = len(seqs)
    overall = sum(1 for pg in seqs if "confirmation" in pg) / max(n, 1)
    bottom = len(C.PAGES) - 3            # "few doors" = among the 4 least-linked-to pages
    out, table = [], {}
    for p, m in real_metrics.items():
        saw = [pg for pg in seqs if p in pg]
        conv = sum(1 for pg in saw if "confirmation" in pg) / len(saw) if saw else 0.0
        lift = conv / overall if overall else 0.0
        own = m["entries"] / m["visits"] if m["visits"] else 0.0
        table[p] = dict(designed_rank=d_rank[p], real_rank=r_rank[p], links_in=int(D.in_degree(p)),
                        arrive_directly_share=round(own, 3),
                        conversion_if_seen=round(conv, 4), conversion_lift=round(lift, 2))
        if (p not in C.FUNNEL and m["visits"] >= min_visits and d_rank[p] >= bottom
                and own >= 0.5 and lift >= 1.5):
            out.append(dict(page=p, designed_rank=d_rank[p], real_rank=r_rank[p], links_in=int(D.in_degree(p)),
                            arrive_directly_share=round(own, 3), visits=m["visits"],
                            conversion_lift=round(lift, 2), conversion_if_seen=round(conv, 4),
                            overall_conversion=round(overall, 4)))
    return sorted(out, key=lambda r: -r["conversion_lift"]), table


def detect_type_gap(f_human, f_agent, min_reach=30, cut=0.30):
    out = []
    for h, a in zip(f_human["steps"], f_agent["steps"]):
        if h["continue_rate"] is None or a["continue_rate"] is None:
            continue
        gap = h["continue_rate"] - a["continue_rate"]
        if h["reached_from"] >= min_reach and a["reached_from"] >= min_reach and abs(gap) >= cut:
            out.append(dict(step=f"{h['from_step']} -> {h['to_step']}", human_rate=h["continue_rate"],
                            agent_rate=a["continue_rate"], gap=round(gap, 3),
                            human_n=h["reached_from"], agent_n=a["reached_from"]))
    return sorted(out, key=lambda r: -abs(r["gap"]))


def page_gap_table(seq_h, seq_a):
    """Where humans and agents spend their visits differently."""
    def share(seqs):
        c = Counter(p for pg in seqs for p in pg)
        t = sum(c.values()) or 1
        return {p: c[p] / t for p in C.PAGES}
    sh, sa = share(seq_h), share(seq_a)
    return [dict(page=p, human_visit_share=round(sh[p], 4), agent_visit_share=round(sa[p], 4),
                 difference=round(sa[p] - sh[p], 4)) for p in C.PAGES]


# ---------------------------------------------------------------------------
# Fingerprints
# ---------------------------------------------------------------------------
def fingerprints(feats, preds):
    d = feats.merge(preds[["session_id", "pred_label"]], on="session_id")
    d["rhythm"] = d["rhythm"].fillna(d["rhythm"].median())
    scale = d[TRAITS].std().replace(0, 1)
    lo, hi = d[TRAITS].quantile(0.05), d[TRAITS].quantile(0.95)
    out = {}
    for label, g in d.groupby("pred_label"):
        med = g[TRAITS].median()
        out[label] = dict(n=int(len(g)),
                          median={t: round(float(med[t]), 3) for t in TRAITS},
                          radar={t: round(float(np.clip((med[t] - lo[t]) / ((hi[t] - lo[t]) or 1), 0, 1)), 3) for t in TRAITS})
    return out


# ---------------------------------------------------------------------------
def run(verbose=True):
    views = pd.read_csv(C.DATA_DIR / "pageviews.csv")
    feats = pd.read_csv(C.OUT_DIR / "features.csv")
    preds = pd.read_csv(C.OUT_DIR / "predictions.csv")
    labels = preds.set_index("session_id")["pred_label"]
    res = dict(types={}, issues={})
    seqs_by = {}
    all_ids = preds["session_id"].tolist()
    for name, ids in [("human", labels[labels == "human"].index), ("ai_agent", labels[labels == "ai_agent"].index),
                      ("old_bot", labels[labels == "old_bot"].index), ("everyone", all_ids)]:
        seqs = sequences(views, ids)
        seqs_by[name] = seqs.tolist()
        if len(seqs) == 0:
            continue
        G = journey_graph(seqs.tolist())
        m = graph_metrics(G, seqs.tolist())
        res["types"][name] = dict(
            sessions=int(len(seqs)), metrics=m, path_lengths=path_lengths(seqs.tolist()),
            edges=[dict(source=a, target=b, weight=int(d["weight"])) for a, b, d in G.edges(data=True)],
            funnel=funnel(seqs.tolist()),
            bounce_rate=round(float(np.mean([len(p) == 1 for p in seqs])), 4),
            mean_pages=round(float(np.mean([len(p) for p in seqs])), 2),
            conversion=round(float(np.mean(["confirmation" in p for p in seqs])), 4),
        )
    H = res["types"]["human"]
    human_ids = labels[labels == "human"].index
    rage, rage_table = detect_rage(views, human_ids)
    hidden, hidden_table = detect_hidden(H["metrics"], seqs_by["human"])
    res["issues"] = dict(
        dead_ends=detect_dead_ends(H["metrics"]),
        funnel_leaks=detect_funnel_leaks(H["funnel"]),
        loops=detect_loops(seqs_by["human"]),
        rage_clicks=rage,
        hidden_pages=hidden,
        type_gap=detect_type_gap(H["funnel"], res["types"]["ai_agent"]["funnel"]) if "ai_agent" in res["types"] else [],
    )
    res["tables"] = dict(rage_rate_by_page=rage_table, hidden_table=hidden_table,
                         page_gap=page_gap_table(seqs_by["human"], seqs_by.get("ai_agent", [])))
    res["fingerprints"] = fingerprints(feats, preds)
    # how much bots distort the averages
    res["dirty_averages"] = dict(
        everyone=dict(bounce_rate=res["types"]["everyone"]["bounce_rate"], mean_pages=res["types"]["everyone"]["mean_pages"],
                      conversion=res["types"]["everyone"]["conversion"]),
        cleaned_humans=dict(bounce_rate=H["bounce_rate"], mean_pages=H["mean_pages"], conversion=H["conversion"]),
    )
    (C.OUT_DIR / "behaviour_results.json").write_text(json.dumps(res, indent=2))
    if verbose:
        iss = res["issues"]
        print("  dead ends     :", [r["page"] for r in iss["dead_ends"]])
        print("  funnel leaks  :", [r["step"] for r in iss["funnel_leaks"]])
        print("  loops         :", [tuple(r["pages"]) for r in iss["loops"]])
        print("  rage clicks   :", [r["page"] for r in iss["rage_clicks"]])
        print("  hidden pages  :", [r["page"] for r in iss["hidden_pages"]])
        print("  human-agent gap:", [r["step"] for r in iss["type_gap"]])
    return res


if __name__ == "__main__":
    run()
