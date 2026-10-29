"""All charts in one place. Each function returns a matplotlib figure."""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

import config as C

COL = {"human": "#2a6fdb", "ai_agent": "#8b5cf6", "old_bot": "#e0563a", "unknown": "#8a8f98"}
NAME = {"human": "Human", "ai_agent": "AI agent", "old_bot": "Old bot", "unknown": "Unknown"}
INK, MUTED, GRID = "#1f2430", "#6b7280", "#e5e7eb"

SHORT = {"product_detail": "product\ndetail", "size_guide": "size\nguide", "confirmation": "confirm"}

# A fixed picture of the shop so every journey graph lines up and can be compared.
POS = {
    "about": (-3.2, 4.4), "home": (0, 4.4), "blog": (3.2, 4.4),
    "reviews": (-3.6, 2.9), "products": (0, 3.0), "deals": (3.6, 2.9),
    "compare": (-3.0, 1.5), "product_detail": (0, 1.5), "size_guide": (3.0, 1.5),
    "cart": (-4.2, 0), "shipping": (-1.4, 0), "payment": (1.4, 0), "confirmation": (4.2, 0),
}


def _style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def fig_journey(res, kind="human", flagged_dead=(), flagged_hidden=(), size=(8.6, 5.2)):
    t = res["types"].get(kind)
    fig, ax = plt.subplots(figsize=size)
    ax.set_axis_off()
    if not t:
        ax.text(0.5, 0.5, "No visitors of this type", ha="center", transform=ax.transAxes)
        return fig
    m = t["metrics"]
    maxw = max([e["weight"] for e in t["edges"]] + [1])
    for e in t["edges"]:
        a, b = POS[e["source"]], POS[e["target"]]
        if e["weight"] < 0.01 * maxw:
            continue
        rad = 0.18 if (e["target"], e["source"]) in {(x["source"], x["target"]) for x in t["edges"]} else 0.0
        ax.annotate("", xy=b, xytext=a, arrowprops=dict(
            arrowstyle="-|>", color=COL.get(kind, MUTED), alpha=0.18 + 0.6 * (e["weight"] / maxw) ** 0.5,
            lw=0.5 + 5 * (e["weight"] / maxw) ** 0.6, connectionstyle=f"arc3,rad={rad}", shrinkA=18, shrinkB=18))
    vmax = max(v["visits"] for v in m.values()) or 1
    for p, (x, y) in POS.items():
        v = m[p]
        size_pt = 900 + 2300 * (v["visits"] / vmax) ** 0.7
        edge, lw = "white", 1.2
        if p in flagged_dead:
            edge, lw = "#d92d20", 3.2
        elif p in flagged_hidden:
            edge, lw = "#12a150", 3.2
        er = v["exit_rate"]
        face = plt.cm.Blues(0.25 + 0.55 * min(v["visits"] / vmax, 1)) if kind == "human" else plt.cm.Purples(0.25 + 0.55 * min(v["visits"] / vmax, 1)) if kind == "ai_agent" else plt.cm.Oranges(0.25 + 0.55 * min(v["visits"] / vmax, 1))
        ax.scatter([x], [y], s=size_pt, color=face, edgecolor=edge, linewidth=lw, zorder=3)
        ax.text(x, y, SHORT.get(p, p.replace("_", "\n")), ha="center", va="center", fontsize=7.4, color=INK, zorder=4, fontweight="medium")
        ax.text(x, y - 0.62 - 0.16 * (v["visits"] / vmax) ** 0.5, f"exit {er:.0%}", ha="center", va="top", fontsize=6.8,
                color="#d92d20" if p in flagged_dead else MUTED, zorder=4)
    ax.set_xlim(-5.4, 5.4)
    ax.set_ylim(-1.2, 5.2)
    ax.set_title(f"How {NAME.get(kind, kind).lower()} visitors move through the shop  ({t['sessions']:,} visits)",
                 fontsize=11, color=INK, loc="left")
    fig.text(0.01, 0.01, "Bigger dot = more visits. Thicker line = more people made that move. Red ring = dead end. Green ring = hidden useful page.",
             fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    return fig


def fig_similarity(sample, size=(7.2, 5.2)):
    G = nx.Graph()
    for n in sample["nodes"]:
        G.add_node(n["id"], **n)
    G.add_edges_from(sample["edges"])
    pos = nx.spring_layout(G, seed=C.SEED, k=0.22, iterations=80)
    fig, ax = plt.subplots(figsize=size)
    ax.set_axis_off()
    nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.10, width=0.5, edge_color=MUTED)
    for lab, c in COL.items():
        nodes = [n["id"] for n in sample["nodes"] if n["label"] == lab]
        if nodes:
            nx.draw_networkx_nodes(G, pos, nodelist=nodes, node_color=c, node_size=16, ax=ax, alpha=0.9, linewidths=0,
                                   label=f"{NAME[lab]} ({len(nodes)})")
    ax.legend(loc="lower left", fontsize=8, frameon=False, markerscale=1.6)
    ax.set_title("Visitors linked to look-alikes (a sample of 700)", fontsize=11, color=INK, loc="left")
    fig.tight_layout()
    return fig


def fig_fingerprint(fp, size=(5.6, 5.2)):
    traits = ["exploring", "depth", "backtracking", "recovery", "speed", "rhythm", "reading", "form_handling", "goal_focus"]
    labels = ["Exploring", "Depth", "Backtracking", "Recovery", "Speed\n(time/page)", "Uneven\ntiming", "Reading\ntime", "Form\ntries", "Goal\nfocus"]
    ang = np.linspace(0, 2 * np.pi, len(traits), endpoint=False)
    ang = np.concatenate([ang, ang[:1]])
    fig = plt.figure(figsize=size)
    ax = fig.add_subplot(111, polar=True)
    for kind in ["human", "ai_agent", "old_bot"]:
        if kind not in fp:
            continue
        v = [fp[kind]["radar"][t] for t in traits]
        v += v[:1]
        ax.plot(ang, v, color=COL[kind], lw=2, label=f"{NAME[kind]} ({fp[kind]['n']:,})")
        ax.fill(ang, v, color=COL[kind], alpha=0.12)
    ax.set_xticks(ang[:-1])
    ax.set_xticklabels(labels, fontsize=8, color=INK)
    ax.set_yticks([0.25, 0.5, 0.75])
    ax.set_yticklabels([])
    ax.set_ylim(0, 1)
    ax.grid(color=GRID)
    ax.spines["polar"].set_color(GRID)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=3, fontsize=8, frameon=False)
    ax.set_title("Behaviour fingerprint (typical visitor of each type)", fontsize=11, color=INK, pad=22)
    fig.subplots_adjust(left=0.16, right=0.84, top=0.86, bottom=0.12)
    return fig


def fig_funnel(res, size=(6.2, 3.8)):
    steps = res["types"]["human"]["funnel"]["steps"]
    labels = [f"{s['from_step']}\n→ {s['to_step']}" for s in steps]
    x = np.arange(len(steps))
    fig, ax = plt.subplots(figsize=size)
    w = 0.36
    h = [s["continue_rate"] or 0 for s in steps]
    ax.bar(x - w / 2, h, w, color=COL["human"], label="Humans")
    if "ai_agent" in res["types"]:
        a = [s["continue_rate"] or 0 for s in res["types"]["ai_agent"]["funnel"]["steps"]]
        ax.bar(x + w / 2, a, w, color=COL["ai_agent"], label="AI agents")
        for xi, v in zip(x + w / 2, a):
            ax.text(xi, v + 0.02, f"{v:.0%}", ha="center", fontsize=8, color=INK)
    for xi, v in zip(x - w / 2, h):
        ax.text(xi, v + 0.02, f"{v:.0%}", ha="center", fontsize=8, color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8.5)
    ax.set_ylim(0, 1.12)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1])
    ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
    ax.legend(frameon=False, fontsize=8.5)
    ax.set_title("Share who continue to the next checkout step", fontsize=11, color=INK, loc="left")
    _style(ax)
    fig.tight_layout()
    return fig


def fig_traffic(hourly, spikes, upto=None, size=(7.2, 3.3)):
    h = hourly.copy()
    h["hour"] = pd.to_datetime(h["hour"])
    cols = [c for c in h.columns if c != "hour"]
    h["total"] = h[cols].sum(axis=1)
    if upto is not None:
        h = h[h["hour"] < upto]
    fig, ax = plt.subplots(figsize=size)
    ax.plot(h["hour"], h["total"], color=COL["human"], lw=1.1)
    ax.fill_between(h["hour"], h["total"], color=COL["human"], alpha=0.10)
    for w in spikes:
        a, b = pd.Timestamp(w["start"]), pd.Timestamp(w["end"])
        if upto is not None and a >= upto:
            continue
        ax.axvspan(a - pd.Timedelta(hours=1), b + pd.Timedelta(hours=1), color="#d92d20", alpha=0.25)
        top = float(h["total"].max())
        ax.annotate(f"spike: {w['source']}\n{w['visits']} visits", xy=(a, top), xytext=(a - pd.Timedelta(days=3.2), top * 0.92),
                    fontsize=8.5, color="#b42318", arrowprops=dict(arrowstyle="-", color="#b42318", lw=0.8))
    ax.set_ylabel("visits per hour", fontsize=9, color=MUTED)
    ax.set_title("Visits per hour", fontsize=11, color=INK, loc="left")
    _style(ax)
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


def fig_types_daily(daily, upto_day=None, size=(7.2, 3.1)):
    d = daily.copy()
    if upto_day is not None:
        d = d.iloc[:upto_day]
    fig, ax = plt.subplots(figsize=size)
    bottom = np.zeros(len(d))
    x = np.arange(len(d))
    for kind in ["human", "ai_agent", "old_bot", "unknown"]:
        if kind in d.columns:
            ax.bar(x, d[kind].to_numpy(), bottom=bottom, color=COL[kind], label=NAME[kind], width=0.8)
            bottom += d[kind].to_numpy()
    ax.set_xticks(x[::2])
    ax.set_xticklabels([f"day {i + 1}" for i in x[::2]], fontsize=8)
    ax.legend(frameon=False, ncol=4, fontsize=8.5, loc="upper left")
    ax.set_title("Who visits each day", fontsize=11, color=INK, loc="left")
    ax.set_ylim(0, max(bottom.max() * 1.25, 1))
    _style(ax)
    fig.tight_layout()
    return fig


def fig_sources(q, size=(6.2, 3.2)):
    d = q.dropna(subset=["quality_score"]).sort_values("quality_score")
    fig, ax = plt.subplots(figsize=size)
    colors = ["#d92d20" if bool(l) else COL["human"] for l in d["low_quality"]]
    ax.barh(d["source"], d["quality_score"], color=colors)
    for y, v in enumerate(d["quality_score"]):
        ax.text(v + 1, y, f"{v:.0f}", va="center", fontsize=8.5, color=INK)
    ax.set_xlim(0, 100)
    ax.set_title("Source quality score (0-100, red = low)", fontsize=11, color=INK, loc="left")
    _style(ax)
    ax.yaxis.grid(False)
    ax.xaxis.grid(True, color=GRID)
    fig.tight_layout()
    return fig


def fig_forecast(fc, source, size=(7.2, 3.0)):
    d = fc[fc["source"] == source].copy()
    d["time"] = pd.to_datetime(d["time"])
    fig, ax = plt.subplots(figsize=size)
    ax.plot(d["time"], d["actual"], color=INK, lw=1.2, label="Actual")
    ax.plot(d["time"], d["baseline"], color="#f79009", lw=1, ls="--", label="Same hour last week")
    ax.plot(d["time"], d["model"], color=COL["human"], lw=1.3, label="Model forecast")
    sp = d[d["spike_hour"]]
    if len(sp):
        ax.scatter(sp["time"], sp["actual"], color="#d92d20", s=20, zorder=3, label="Spike hours (not scored)")
    ax.legend(frameon=False, fontsize=8, ncol=4, loc="upper left")
    ax.set_title(f"Forecast vs actual: {source}", fontsize=11, color=INK, loc="left")
    _style(ax)
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


def fig_page_gap(gap, size=(6.2, 3.8)):
    d = pd.DataFrame(gap).sort_values("difference")
    fig, ax = plt.subplots(figsize=size)
    colors = [COL["ai_agent"] if v > 0 else COL["human"] for v in d["difference"]]
    ax.barh(d["page"], d["difference"] * 100, color=colors)
    ax.axvline(0, color=MUTED, lw=0.8)
    ax.set_xlabel("← humans visit more        AI agents visit more →\n(share of all page visits, percentage points)", fontsize=8.5, color=MUTED)
    ax.set_title("Where humans and AI agents differ", fontsize=11, color=INK, loc="left")
    _style(ax)
    ax.yaxis.grid(False)
    fig.tight_layout()
    return fig


def save_all(out_dir):
    """Save the main pictures as PNG files (used in the report folder)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    be = json.loads((C.OUT_DIR / "behaviour_results.json").read_text())
    tr = json.loads((C.OUT_DIR / "traffic_results.json").read_text())
    sample = json.loads((C.OUT_DIR / "similarity_sample.json").read_text())
    q = pd.read_csv(C.OUT_DIR / "source_quality.csv")
    daily = pd.read_csv(C.OUT_DIR / "daily_type_counts.csv")
    hourly = pd.read_csv(C.OUT_DIR / "hourly_by_source.csv")
    dead = [r["page"] for r in be["issues"]["dead_ends"]]
    hid = [r["page"] for r in be["issues"]["hidden_pages"]]
    figs = {
        "journey_human": fig_journey(be, "human", dead, hid),
        "journey_agent": fig_journey(be, "ai_agent"),
        "similarity_graph": fig_similarity(sample),
        "fingerprint": fig_fingerprint(be["fingerprints"]),
        "funnel": fig_funnel(be),
        "traffic_hourly": fig_traffic(hourly, tr["spikes"]),
        "visitors_per_day": fig_types_daily(daily),
        "source_quality": fig_sources(q),
        "page_gap": fig_page_gap(be["tables"]["page_gap"]),
    }
    for name, f in figs.items():
        f.savefig(out_dir / f"{name}.png", dpi=130, facecolor="white")
        plt.close(f)
    return list(figs)
