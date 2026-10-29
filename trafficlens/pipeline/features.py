"""
Turn raw page views into ONE ROW PER VISITOR.

Each row has two kinds of information:
  1. quick "signals" (mouse, touch, clicks, scroll, browser claims)
  2. the 8-trait BEHAVIOUR FINGERPRINT (how the visitor explores and decides)

The 8 traits
  exploring     how many different pages they looked at (out of all pages)
  depth         how far into the buying steps they got (cart, shipping, payment...)
  backtracking  how often they went back to a page they had already seen
  recovery      after going back, do they try something NEW (1.0) or repeat (0.0)?
  speed         how quickly they move (log of the middle time on a page)
  rhythm        how UNEVEN their timing is (humans are uneven, many bots are not)
  reading       time spent on content pages (log)
  form_handling how many tries they need on forms (shipping / payment)
  goal_focus    share of steps that move forward toward buying

Privacy: nothing here is text a person typed. Only counts and timings.
"""
import numpy as np
import pandas as pd

import config as C

AUTOMATION_UA = {"headless", "python", "curl"}
CRAWLER_UA = {"googlebot", "bingbot"}
DEPTH_STAGE = {"cart": 1, "shipping": 2, "payment": 3, "confirmation": 4}


def _one(g):
    pages = g["page"].tolist()
    n = len(pages)
    dwell = g["dwell_s"].to_numpy(float)
    mouse = g["mouse_events"].to_numpy(float)
    touch = g["touch_events"].to_numpy(float)
    clicks = g["clicks"].to_numpy(float)
    scroll = g["scroll_depth"].to_numpy(float)
    straight = g["mouse_straightness"].to_numpy(float)
    items = g["item_id"].to_numpy(float)

    duration = float(dwell.sum())

    # --- backtracking and recovery -------------------------------------
    back = 0
    seen = set()
    for i, p in enumerate(pages):
        if i > 0 and p in seen:
            back += 1
        seen.add(p)
    backtracking = back / (n - 1) if n > 1 else 0.0
    ping, new_route = 0, 0
    for i in range(2, n):
        if pages[i] == pages[i - 2] and pages[i] != pages[i - 1]:    # A -> B -> A
            ping += 1
            if i + 1 < n:
                new_route += int(pages[i + 1] != pages[i - 1])
            else:
                new_route += 1       # session ended: no repeat happened
    recovery = new_route / ping if ping else 1.0

    # --- goal focus ------------------------------------------------------
    stages = [C.STAGE[p] for p in pages]
    fwd = sum(1 for i in range(1, n) if stages[i] > stages[i - 1])
    goal_focus = fwd / (n - 1) if n > 1 else 0.0

    depth = max([DEPTH_STAGE.get(p, 0) for p in pages]) / 4.0

    # --- timing ----------------------------------------------------------
    rhythm = float(np.std(dwell) / np.mean(dwell)) if n >= 3 and np.mean(dwell) > 0 else np.nan
    content = [d for p, d in zip(pages, dwell) if p in C.CONTENT_PAGES]
    reading = float(np.log1p(np.mean(content))) if content else 0.0

    form_rows = g[g["page"].isin(C.FORM_PAGES)]
    form_handling = float(form_rows["form_attempts"].mean()) if len(form_rows) else 0.0

    # --- scraping hint: walking product ids one by one -------------------
    seq_pairs, pd_pairs = 0, 0
    for i in range(1, n):
        if pages[i] == "product_detail" and pages[i - 1] == "product_detail":
            if not np.isnan(items[i]) and not np.isnan(items[i - 1]):
                pd_pairs += 1
                seq_pairs += int(abs(items[i] - items[i - 1]) == 1)
    item_seq = seq_pairs / pd_pairs if pd_pairs else 0.0

    m = mouse > 0
    return dict(
        n_pages=n, duration_s=duration,
        pages_per_min=min(n / (max(duration, 1.0) / 60.0), 600.0),
        mouse_pp=float(mouse.mean()), touch_pp=float(touch.mean()), click_pp=float(clicks.mean()),
        touch_total=float(touch.sum()), mouse_total=float(mouse.sum()),
        scroll_mean=float(scroll.mean()), scroll_std=float(scroll.std()),
        straightness=float(np.nanmean(straight[m])) if m.any() else 0.0,
        item_seq_share=item_seq, single_page=int(n == 1),
        rage_total=float(g["rage_clicks"].sum()),
        exploring=len(set(pages)) / len(C.PAGES), depth=depth, backtracking=backtracking,
        recovery=recovery, speed=float(np.log1p(np.median(dwell))), rhythm=rhythm,
        reading=reading, form_handling=form_handling, goal_focus=goal_focus,
    )


def build_features(sessions: pd.DataFrame, views: pd.DataFrame) -> pd.DataFrame:
    views = views.sort_values(["session_id", "step"])
    rows = []
    for sid, g in views.groupby("session_id", sort=False):
        r = _one(g)
        r["session_id"] = sid
        rows.append(r)
    f = pd.DataFrame(rows)
    f = sessions.merge(f, on="session_id", how="inner")
    f["ua_automation"] = f["ua_family"].isin(AUTOMATION_UA).astype(int)
    f["declared_crawler"] = f["ua_family"].isin(CRAWLER_UA).astype(int)
    # claims to be a phone/tablet but never produced a single touch
    f["device_mismatch"] = ((f["device_claimed"].isin(["mobile", "tablet"])) & (f["touch_total"] == 0)).astype(int)
    f["start_ts"] = pd.to_datetime(f["start_ts"])
    return f


def load_main():
    s = pd.read_csv(C.DATA_DIR / "sessions.csv")
    v = pd.read_csv(C.DATA_DIR / "pageviews.csv")
    return s, v


def load_training():
    s = pd.read_csv(C.TRAIN_DIR / "sessions.csv")
    v = pd.read_csv(C.TRAIN_DIR / "pageviews.csv")
    lab = pd.read_csv(C.TRAIN_DIR / "labels.csv")
    return s, v, lab


def run(verbose=True):
    C.OUT_DIR.mkdir(parents=True, exist_ok=True)
    s, v = load_main()
    f = build_features(s, v)
    f.to_csv(C.OUT_DIR / "features.csv", index=False)
    ts, tv, tl = load_training()
    tf = build_features(ts, tv).merge(tl, on="session_id")
    tf.to_csv(C.OUT_DIR / "training_features.csv", index=False)
    if verbose:
        print(f"  built {len(f):,} visitor records (+ {len(tf):,} practice records)")
    return f, tf


if __name__ == "__main__":
    run()
