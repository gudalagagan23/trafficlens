"""
Turn collected live events into the same two tables the rest of the project uses.

    python -m tracker.live_to_tables
    TRAFFICLENS_DATA=data/live python run_all.py --skip-generate

You need a few hundred real visits before the analysis is meaningful.
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data" / "live"


def convert():
    rows = [json.loads(l) for l in (LIVE / "events.jsonl").read_text().splitlines() if l.strip()]
    ev = pd.DataFrame(rows).sort_values(["session_id", "step"])
    ev["step"] = ev.groupby("session_id").cumcount()
    first = ev.groupby("session_id").first().reset_index()
    sessions = pd.DataFrame({
        "session_id": first["session_id"],
        "start_ts": pd.to_datetime(first["t_start"], unit="s").dt.strftime("%Y-%m-%d %H:%M:%S"),
        "source": first["source"], "country": first["country"].replace("", "UNKNOWN"),
        "device_claimed": first["device_claimed"], "ua_family": first["ua_family"]})
    views = pd.DataFrame({
        "session_id": ev["session_id"], "step": ev["step"], "page": ev["page"], "item_id": None,
        "t_start": ev["t_start"], "dwell_s": ev["dwell_s"].round(2), "mouse_events": ev["mouse_events"],
        "mouse_straightness": ev["mouse_straightness"].round(3), "touch_events": ev["touch_events"],
        "clicks": ev["clicks"], "rage_clicks": ev["rage_clicks"], "scroll_depth": ev["scroll_depth"].round(2),
        "form_attempts": ev["form_attempts"], "form_seconds": ev["form_seconds"].round(2)})
    sessions.sort_values("start_ts").to_csv(LIVE / "sessions.csv", index=False)
    views.to_csv(LIVE / "pageviews.csv", index=False)
    print(f"wrote {len(sessions)} sessions and {len(views)} page views to {LIVE}")


if __name__ == "__main__":
    convert()
