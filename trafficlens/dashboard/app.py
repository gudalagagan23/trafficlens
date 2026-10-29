"""
TrafficLens dashboard.   Start it with:   streamlit run dashboard/app.py

  Top      : live counts per visitor type + alerts
  Left     : WEB TRAFFIC   (similarity graph, sources, visits over time)
  Right    : USER BEHAVIOUR (journey graph, checkout funnel)
  Middle   : the fingerprint comparison and the human-vs-agent gap
  Bottom   : the agent's issue list and a chat box
  Tab 3    : the score page (planted problems vs found problems)

The "replay" slider in the sidebar plays the simulated 21 days forward, so you can
watch the spike appear. (A truly live feed needs the tracker + collector in tracker/.)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

import config as C
from agent import chat
from dashboard import plots

st.set_page_config(page_title=f"{C.PRODUCT_NAME}", page_icon="🔎", layout="wide")


@st.cache_data
def load():
    o = C.OUT_DIR
    need = ["traffic_results.json", "behaviour_results.json", "findings.json", "predictions.csv"]
    if not all((o / n).exists() for n in need):
        return None
    d = dict(
        tr=json.loads((o / "traffic_results.json").read_text()),
        be=json.loads((o / "behaviour_results.json").read_text()),
        ln=json.loads((o / "link_results.json").read_text()),
        pr=json.loads((o / "prediction_results.json").read_text()),
        findings=json.loads((o / "findings.json").read_text()),
        sample=json.loads((o / "similarity_sample.json").read_text()),
        quality=pd.read_csv(o / "source_quality.csv"),
        daily=pd.read_csv(o / "daily_type_counts.csv"),
        hourly=pd.read_csv(o / "hourly_by_source.csv"),
        forecast=pd.read_csv(o / "forecast.csv"),
        preds=pd.read_csv(o / "predictions.csv"),
        sessions=pd.read_csv(C.DATA_DIR / "sessions.csv", usecols=["session_id", "start_ts", "source"]),
        evaluation=json.loads((o / "evaluation.json").read_text()) if (o / "evaluation.json").exists() else None,
    )
    return d


@st.cache_resource(show_spinner=False)
def fig_cached(name, arg=None):
    """Draw each unchanging picture once and reuse it (keeps the free hosting tier fast)."""
    be, d = D["be"], D
    if name == "similarity":
        return plots.fig_similarity(d["sample"])
    if name == "sources":
        return plots.fig_sources(d["quality"])
    if name == "forecast":
        return plots.fig_forecast(d["forecast"], arg)
    if name == "journey":
        dead = [r["page"] for r in be["issues"]["dead_ends"]] if arg == "human" else ()
        hid = [r["page"] for r in be["issues"]["hidden_pages"]] if arg == "human" else ()
        return plots.fig_journey(be, arg, dead, hid)
    if name == "funnel":
        return plots.fig_funnel(be)
    if name == "fingerprint":
        return plots.fig_fingerprint(be["fingerprints"])
    if name == "gap":
        return plots.fig_page_gap(be["tables"]["page_gap"])


D = load()
st.markdown(f"## 🔎 {C.PRODUCT_NAME}")
st.caption(C.SUBTITLE + "  ·  all visitors here are simulated")
if D is None:
    st.error("No results yet. Run  `python run_all.py`  first, then reopen this page.")
    st.stop()

# ------------------------------------------------------------------ replay
t0 = pd.to_datetime(D["sessions"]["start_ts"]).min().normalize()
st.sidebar.header("Replay")
day = st.sidebar.slider("Show traffic up to day", 1, C.N_DAYS, C.N_DAYS)
upto = t0 + pd.Timedelta(days=day)
st.sidebar.caption("Move the slider to watch the 21 days unfold.")
st.sidebar.divider()
kind = st.sidebar.radio("Journey graph for", ["human", "ai_agent", "old_bot"],
                        format_func=lambda k: plots.NAME[k])
src_choice = st.sidebar.selectbox("Forecast for source", sorted(D["forecast"]["source"].unique()))
st.sidebar.divider()
st.sidebar.caption("Causes in the findings are guesses. Only numbers are facts.")

S = D["sessions"].copy()
S["ts"] = pd.to_datetime(S["start_ts"])
seen = S[S["ts"] < upto].merge(D["preds"][["session_id", "pred_label"]], on="session_id")
counts = seen["pred_label"].value_counts()
visible_spikes = [w for w in D["tr"]["spikes"] if pd.Timestamp(w["start"]) < upto]

c = st.columns(5)
c[0].metric("Visits so far", f"{len(seen):,}")
for col, k in zip(c[1:], ["human", "ai_agent", "old_bot", "unknown"]):
    n = int(counts.get(k, 0))
    col.metric(plots.NAME[k], f"{n:,}", f"{n / max(len(seen), 1):.0%} of visits", delta_color="off")
for w in visible_spikes:
    st.error(f"⚠️ Spike: **{w['source']}** sent **{w['visits']}** visits between {w['start']} and {w['end']} "
             f"({w['days_of_usual_traffic']} days of its usual traffic; {w['same_path_share']:.0%} followed one path).")

tab1, tab2, tab3 = st.tabs(["Live view", "Findings and chat", "Score page"])

# ================================================================== TAB 1
with tab1:
    left, right = st.columns(2, gap="large")
    be = D["be"]
    dead = [r["page"] for r in be["issues"]["dead_ends"]]
    hid = [r["page"] for r in be["issues"]["hidden_pages"]]
    with left:
        st.subheader("Web traffic")
        st.caption("Who is visiting, from where, and is it real?")
        st.pyplot(plots.fig_traffic(D["hourly"], D["tr"]["spikes"], upto=upto))
        st.pyplot(plots.fig_types_daily(D["daily"], upto_day=day))
        st.pyplot(fig_cached("similarity"))
        st.pyplot(fig_cached("sources"))
        st.pyplot(fig_cached("forecast", src_choice))
    with right:
        st.subheader("User behaviour")
        st.caption("What do visitors do on the site, and where do they struggle?")
        st.pyplot(fig_cached("journey", kind))
        st.pyplot(fig_cached("funnel"))
        st.markdown("**Issues found on human visitors**")
        iss = be["issues"]
        st.markdown(
            f"- Dead end: {', '.join(r['page'] for r in iss['dead_ends']) or 'none'}\n"
            f"- Checkout leak: {', '.join(r['step'] for r in iss['funnel_leaks']) or 'none'}\n"
            f"- Loops: {', '.join(' ↔ '.join(r['pages']) for r in iss['loops']) or 'none'}\n"
            f"- Rage clicks: {', '.join(r['page'] for r in iss['rage_clicks']) or 'none'}\n"
            f"- Hidden useful page: {', '.join(r['page'] for r in iss['hidden_pages']) or 'none'}")

    st.divider()
    st.subheader("How the types differ")
    m1, m2 = st.columns(2, gap="large")
    with m1:
        st.pyplot(fig_cached("fingerprint"))
    with m2:
        st.pyplot(fig_cached("gap"))
        st.caption("Purple bars: pages AI agents use more than humans. Blue bars: pages humans use more.")

# ================================================================== TAB 2
with tab2:
    st.subheader("What the system found")
    top = None
    from agent import report as R
    top = R.rank(D["findings"])
    a, b = st.columns(2)
    with a:
        st.markdown("**Top 3 web traffic fixes**")
        for x in top["traffic"]:
            st.markdown(f"- **{x['title']}**: {x['fix']}")
    with b:
        st.markdown("**Top 3 user behaviour fixes**")
        for x in top["behaviour"]:
            st.markdown(f"- **{x['title']}**: {x['fix']}")
    st.markdown("**Traffic and behaviour together**")
    for x in top["link"]:
        st.markdown(f"- **{x['title']}**: {x['fix']}")
    st.divider()
    for side, name in [("traffic", "Web traffic"), ("behaviour", "User behaviour"), ("link", "Traffic and behaviour together")]:
        st.markdown(f"#### {name}")
        for x in sorted([y for y in D["findings"] if y["side"] == side], key=lambda y: -y["impact_visits"]):
            with st.expander(f"{x['id']}  ·  {x['title']}   (confidence: {x['confidence']})"):
                st.markdown(f"**What happened:** {x['what_happened']}")
                st.markdown(f"**Where:** {x['where']}")
                st.markdown(f"**{x['likely_cause']}**")
                st.markdown(f"**Fix first:** {x['fix']}")
    st.divider()
    st.subheader("Ask the analyst")
    st.caption("Answers come only from the findings above. If it does not know, it says so.")
    if "msgs" not in st.session_state:
        st.session_state.msgs = [("assistant", "Ask me about a spike, bots, a source, a page, checkout, or 'what should I fix first?'")]
    for role, text in st.session_state.msgs:
        with st.chat_message(role):
            st.text(text)
    q = st.chat_input("Why did traffic jump? Which source is worst?")
    if q:
        st.session_state.msgs.append(("user", q))
        st.session_state.msgs.append(("assistant", chat.reply(q)))
        st.rerun()

# ================================================================== TAB 3
with tab3:
    ev = D["evaluation"]
    if not ev:
        st.info("No score page yet. It needs the hidden answer key that comes with simulated data.")
    else:
        s = ev["summary"]
        st.subheader("Planted problems vs found problems")
        st.markdown(f"**{s['found']} found · {s['partly']} partly found · {s['missed']} missed** (of {s['total']})")
        card = pd.DataFrame(ev["scorecard"])[["number", "side", "problem", "planted", "result", "evidence"]]
        st.dataframe(card, hide_index=True)
        st.subheader("Visitor judge, group by group")
        j = pd.DataFrame(ev["judge"]).T[["n", "called_human", "called_ai_agent", "called_old_bot", "called_unknown"]]
        st.dataframe(j.style.format({c: "{:.1%}" for c in j.columns if c != "n"}))
        st.info("All data is simulated, so these results show the method works on problems we planted. See report/RESULTS.md for the full test list and weak points.")
