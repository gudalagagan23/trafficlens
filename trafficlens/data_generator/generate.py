"""
Fake-visitor factory.

We have no real website with real bots, so we MAKE visitors on purpose.
The big advantage: because we create every visitor, we know the true
answer for each one. A hidden "answer key" is saved separately and only
the evaluation step is allowed to read it.

Visitor kinds created here
  human      : real-person style browsing (uneven timing, curvy mouse, mistakes)
  ai_agent   : an AI browsing for a person (focused, fast but varied, retries forms)
  old_bot    : several skill levels:
                 dumb     - no mouse, very fast, same path over and over
                 scraper  - walks through product pages one by one
                 crawler  - declared search-engine bot (Googlebot style)
                 medium   - fakes a little mouse movement
                 smart    - copies human timing and mouse closely (hard to catch)
                 flood    - a burst of dumb bots from one source (the spike)
  novel_bot  : a kind of bot NEVER shown to the classifier during training.
               Used to test whether the system says "Unknown" instead of guessing.

The 12 planted problems are listed in PLAN below.
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import config as C

# ---------------------------------------------------------------------------
# The planted problems (the answer key is built from this)
# ---------------------------------------------------------------------------
PLAN = dict(
    # --- behaviour problems (humans) ---
    dead_end_page="size_guide", dead_end_exit=0.72,
    funnel_step=("shipping", "payment"), funnel_continue=0.30,
    loop_pair=("compare", "product_detail"), loop_share=0.25,
    rage_page="cart", rage_share=0.30,
    hidden_page="reviews",
    type_gap_page="payment", agent_payment_continue=0.05,
    # --- traffic + link problems ---
    expectation_mismatch=("promo_ads", "deals"), expectation_exit=0.70,
    low_quality_source="cheap_ads",
    spike=dict(source="social_x", day=17, hour=14, minutes=20, n=450),
)

HUMAN_SOURCES = ["search", "direct", "social_x", "email", "referral", "promo_ads", "cheap_ads"]
HUMAN_SOURCE_P = [0.34, 0.24, 0.12, 0.08, 0.07, 0.08, 0.07]

# How humans enter the site, depending on where they came from.
ENTRY = {
    "default": {"home": 0.45, "products": 0.15, "product_detail": 0.12, "deals": 0.06,
                "blog": 0.08, "reviews": 0.12, "about": 0.02},
    "promo_ads": {"deals": 0.55, "home": 0.20, "product_detail": 0.20, "products": 0.05},
    "cheap_ads": {"home": 0.80, "products": 0.20},
    "email": {"deals": 0.30, "home": 0.30, "product_detail": 0.30, "products": 0.10},
    "social_x": {"blog": 0.40, "home": 0.30, "product_detail": 0.30},
    "search": {"reviews": 0.20, "product_detail": 0.20, "blog": 0.15, "home": 0.30, "products": 0.15},
    "direct": {"home": 0.60, "products": 0.25, "product_detail": 0.15},
    "referral": {"blog": 0.30, "home": 0.30, "product_detail": 0.20, "reviews": 0.20},
}

# Human page-to-page behaviour (what real people tend to do next).
EXIT_P = {"home": 0.15, "products": 0.12, "product_detail": 0.16, "deals": 0.20,
          "blog": 0.35, "about": 0.30, "compare": 0.12, "size_guide": 0.20, "reviews": 0.14}
NEXT_W = {
    "home": {"products": 0.40, "deals": 0.15, "blog": 0.15, "about": 0.10, "product_detail": 0.20},
    "products": {"product_detail": 0.65, "deals": 0.10, "home": 0.15, "blog": 0.10},
    "product_detail": {"cart": 0.24, "products": 0.50, "compare": 0.13, "size_guide": 0.13},
    "deals": {"product_detail": 0.60, "products": 0.25, "home": 0.15},
    "blog": {"home": 0.25, "products": 0.40, "product_detail": 0.35},
    "about": {"home": 0.65, "reviews": 0.35},
    "compare": {"product_detail": 0.80, "products": 0.20},
    "size_guide": {"product_detail": 1.0},
    "reviews": {"cart": 0.35, "product_detail": 0.40, "products": 0.25},
}
# (median seconds on page, spread) for humans
HUMAN_DWELL = {
    "home": (12, 0.9), "products": (14, 0.9), "product_detail": (35, 0.9), "deals": (18, 0.9),
    "blog": (45, 1.0), "about": (15, 0.9), "compare": (40, 0.8), "size_guide": (20, 0.7),
    "reviews": (50, 0.9), "cart": (25, 0.8), "shipping": (60, 0.7), "payment": (70, 0.6),
    "confirmation": (10, 0.8),
}
DUMB_TEMPLATES = [
    ["home", "products", "product_detail"],
    ["home", "deals", "product_detail", "product_detail"],
    ["products", "product_detail", "cart"],
]
COUNTRY_HUMAN = (["IN", "US", "GB", "DE", "AU", "CA", "SG", "FR", "BR", "OTHER"],
                 [0.38, 0.20, 0.08, 0.06, 0.05, 0.05, 0.04, 0.04, 0.05, 0.05])
COUNTRY_BOT = (["US", "NL", "SG", "DE", "IN", "RU", "CN"],
               [0.30, 0.20, 0.15, 0.10, 0.10, 0.05, 0.10])
HOUR_W = np.array([0.5, 0.3, 0.2, 0.2, 0.3, 0.5, 1.0, 2.0, 3.0, 4.0, 4.5, 5.0,
                   5.0, 4.8, 4.8, 5.0, 5.2, 5.5, 6.0, 6.5, 6.5, 5.5, 3.5, 1.5])
HOUR_W = HOUR_W / HOUR_W.sum()
NIGHT_W = np.array([3, 3, 3, 3, 3, 3, 2, 1, 0.5, 0.5, 0.5, 0.5,
                    0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 1, 1.5, 2.5])
NIGHT_W = NIGHT_W / NIGHT_W.sum()
FLAT_W = np.ones(24) / 24
DAY_FACTOR = [1.0, 1.0, 1.0, 1.0, 1.05, 0.85, 0.8]   # Mon..Sun

VIEW_COLS = ["session_id", "step", "page", "item_id", "t_start", "dwell_s", "mouse_events",
             "mouse_straightness", "touch_events", "clicks", "rage_clicks", "scroll_depth",
             "form_attempts", "form_seconds"]


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def lognorm(rng, median, cv):
    """A positive, right-skewed number (like time spent on a page)."""
    sigma = math.sqrt(math.log(1 + cv ** 2))
    return float(rng.lognormal(math.log(median), sigma))


def pick(rng, names, probs=None):
    return names[int(rng.choice(len(names), p=probs))]


def weighted(rng, weights):
    names = list(weights)
    p = np.array([weights[n] for n in names], float)
    return pick(rng, names, p / p.sum())


def clip(x, lo, hi):
    return max(lo, min(hi, x))


# ---------------------------------------------------------------------------
# How a human walks through the shop
# ---------------------------------------------------------------------------
def human_next(rng, page, source, on):
    if page == "confirmation":
        return "home" if rng.random() < 0.10 else None
    if page == "cart":
        r = rng.random()
        if r < 0.62:
            return "shipping"
        return "products" if r < 0.72 else None
    if page == "shipping":
        cont = PLAN["funnel_continue"] if on else 0.78       # planted: many leave here
        back = 0.15 if on else 0.07
        r = rng.random()
        if r < cont:
            return "payment"
        return "cart" if r < cont + back else None
    if page == "payment":
        r = rng.random()
        if r < 0.85:
            return "confirmation"
        return "shipping" if r < 0.90 else None
    exit_p = EXIT_P[page]
    if on and page == PLAN["dead_end_page"]:
        exit_p = PLAN["dead_end_exit"]                        # planted dead end
    if on and (source, page) == PLAN["expectation_mismatch"]:
        exit_p = PLAN["expectation_exit"]                     # planted mismatch
    if rng.random() < exit_p:
        return None
    return weighted(rng, NEXT_W[page])


def human_path(rng, source, on):
    page = weighted(rng, ENTRY.get(source, ENTRY["default"]))
    path = [page]
    if source == "cheap_ads" and rng.random() < 0.88:         # low quality: leave at once
        return path
    looper = on and rng.random() < PLAN["loop_share"]         # planted loops
    looped = False
    while len(path) < 40:
        if looper and not looped and page == "product_detail":
            for _ in range(int(rng.integers(3, 6))):
                path += ["compare", "product_detail"]
            looped = True
        nxt = human_next(rng, page, source, on)
        if nxt is None:
            break
        path.append(nxt)
        page = nxt
    return path


# ---------------------------------------------------------------------------
# The factory
# ---------------------------------------------------------------------------
class Factory:
    def __init__(self, seed, plan_on):
        self.rng = np.random.default_rng(seed)
        self.on = plan_on
        self.sessions, self.views, self.labels = [], [], []
        self.n = 0

    # -- bookkeeping --------------------------------------------------------
    def _sid(self):
        self.n += 1
        return f"S{self.n:06d}"

    def _session(self, sid, t0, source, country, device, ua, true_type, subtype, fake=0, tag=""):
        self.sessions.append(dict(session_id=sid, start_ts=t0, source=source, country=country,
                                  device_claimed=device, ua_family=ua))
        self.labels.append(dict(session_id=sid, true_type=true_type, subtype=subtype,
                                fake_device=fake, tag=tag))

    def _view(self, sid, step, page, item, t, dwell, mouse, straight, touch, clicks,
              rage, scroll, fa=0, fs=0.0):
        self.views.append((sid, step, page, item, round(t, 2), round(dwell, 2), int(mouse),
                           straight, int(touch), int(clicks), int(rage), round(scroll, 2),
                           int(fa), round(fs, 2)))

    # -- humans -------------------------------------------------------------
    def human(self, t0, source=None):
        rng, on = self.rng, self.on
        source = source or pick(rng, HUMAN_SOURCES, HUMAN_SOURCE_P)
        device = pick(rng, ["desktop", "mobile", "tablet"], [0.42, 0.53, 0.05])
        if device == "desktop":
            ua = pick(rng, ["chrome", "safari", "firefox", "edge"], [0.6, 0.1, 0.15, 0.15])
        else:
            ua = pick(rng, ["safari", "chrome"], [0.5, 0.5])
        country = pick(rng, *COUNTRY_HUMAN)
        path = human_path(rng, source, on)
        sid = self._sid()
        self._session(sid, t0, source, country, device, ua, "human", "human")
        t, item = t0, None
        for i, page in enumerate(path):
            med, cv = HUMAN_DWELL[page]
            if source == "cheap_ads" and len(path) == 1:
                med, cv = 3.0, 0.6
            dwell = clip(lognorm(rng, med, cv), 0.6, 1200)
            if page == "product_detail":
                prev = path[i - 1] if i > 0 else None
                if prev != "compare":
                    item = int(rng.integers(1, 201))
                it = item
            else:
                it = None
            if device == "desktop":
                mouse = max(1, int(dwell * rng.uniform(1.5, 5)))
                touch = 0
                straight = round(clip(rng.normal(0.55, 0.12), 0.2, 0.9), 3)
            else:
                mouse, straight = 0, 0.0
                touch = 1 + int(dwell * rng.uniform(0.2, 1.0))
                # a few real phones simply record nothing (noise)
                if rng.random() < 0.015:
                    touch = 0
            rage = 0
            p = 0.008
            if page == "payment":
                p = 0.03
            if on and page == PLAN["rage_page"]:
                p = PLAN["rage_share"]                       # planted rage clicks
            if rng.random() < p:
                rage = int(rng.integers(3, 8))
            clicks = int(rng.poisson(1.0)) + (1 if i < len(path) - 1 else 0) + rage
            if page in ("cart", "payment", "shipping"):
                scroll = float(rng.beta(2, 3))
            else:
                scroll = float(rng.beta(2, 2))
            fa, fs = 0, 0.0
            if page in C.FORM_PAGES:
                fa = 1 + int(rng.random() < 0.22) + int(rng.random() < 0.05)
                fs = dwell * 0.7
            self._view(sid, i, page, it, t, dwell, mouse, straight, touch, clicks, rage, scroll, fa, fs)
            t += dwell + rng.uniform(0.2, 1.5)

    # -- AI agents ----------------------------------------------------------
    def agent(self, t0):
        rng, on = self.rng, self.on
        source = pick(rng, ["direct", "search", "ai_assistant"], [0.5, 0.35, 0.15])
        ua = pick(rng, ["chrome", "headless"], [0.8, 0.2])
        sid = self._sid()
        self._session(sid, t0, source, pick(rng, ["US", "SG", "IE", "DE", "IN"], [0.45, 0.2, 0.15, 0.1, 0.1]),
                      "desktop", ua, "ai_agent", "agent")
        entry = pick(rng, ["home", "products", "product_detail", "deals"], [0.3, 0.3, 0.35, 0.05])
        path = [entry]
        if entry in ("home", "deals"):
            path.append("products")
        if path[-1] == "products":
            path.append("product_detail")
        for _ in range(int(rng.integers(0, 3))):
            path += ["products", "product_detail"]
        pay_cont = PLAN["agent_payment_continue"] if on else 0.70
        if rng.random() < 0.65:
            path.append("cart")
            if rng.random() < 0.90:
                path.append("shipping")
                if rng.random() < 0.85:
                    path.append("payment")
                    if rng.random() < pay_cont:
                        path.append("confirmation")
        t = t0
        for i, page in enumerate(path):
            dwell = clip(lognorm(rng, 4.5, 0.45), 0.8, 60)
            mouse = max(2, int(dwell * rng.uniform(1, 3)))
            straight = round(clip(rng.normal(0.88, 0.05), 0.7, 0.99), 3)
            scroll = 1.0 if rng.random() < 0.7 else float(rng.uniform(0.8, 1.0))
            clicks = 1 + int(rng.random() < 0.2)
            it = int(rng.integers(1, 201)) if page == "product_detail" else None
            fa, fs = 0, 0.0
            if page in C.FORM_PAGES:
                fa = 1
                # an agent that cannot finish the payment form retries it again and again
                # (this is how agents behave; the site problem only decides how often they fail)
                if page == "payment" and "confirmation" not in path:
                    fa = int(rng.integers(3, 6))
                fs = 2.0 + 3.0 * fa * rng.random()
                dwell = max(dwell, fs)
            self._view(sid, i, page, it, t, dwell, mouse, straight, 0, clicks, 0, scroll, fa, fs)
            t += dwell + rng.uniform(0.05, 0.4)

    # -- old bots -----------------------------------------------------------
    def _bot_common(self, t0, subtype, source, country=None, device="desktop", ua="chrome",
                    fake=0, true_type="old_bot", tag=""):
        rng = self.rng
        sid = self._sid()
        country = country or pick(rng, *COUNTRY_BOT)
        self._session(sid, t0, source, country, device, ua, true_type, subtype, fake, tag)
        return sid

    def dumb(self, t0, flood=False, source=None):
        rng = self.rng
        template = DUMB_TEMPLATES[0 if flood else int(rng.integers(len(DUMB_TEMPLATES)))]
        if flood:      # an attack tool repeats one path; a few variants slip in
            n = 3 if rng.random() < 0.75 else int(rng.integers(4, 7))
        else:
            n = int(rng.integers(3, 11))
        path = [template[i % len(template)] for i in range(n)]
        if flood:
            source = self.on and PLAN["spike"]["source"] or "social_x"
            ua = pick(rng, ["headless", "chrome"], [0.6, 0.4])
        else:
            source = source or pick(rng, ["cheap_ads", "direct", "social_x", "referral"], [0.3, 0.3, 0.2, 0.2])
            ua = pick(rng, ["python", "headless", "curl", "chrome"], [0.35, 0.4, 0.1, 0.15])
        fake = int((not flood) and rng.random() < 0.15)
        device = "mobile" if fake else "desktop"
        sid = self._bot_common(t0, "flood" if flood else "dumb", source, device=device,
                               ua="safari" if fake else ua, fake=fake, tag="spike" if flood else "")
        base, t, item = rng.uniform(0.25, 0.8), t0, int(rng.integers(1, 201))
        for i, page in enumerate(path):
            dwell = base * rng.uniform(0.95, 1.05)
            self._view(sid, i, page, item if page == "product_detail" else None, t, dwell,
                       0, 0.0, 0, int(rng.random() < 0.3), 0, 0.0)
            t += dwell + rng.uniform(0.02, 0.1)

    def scraper(self, t0):
        rng = self.rng
        n = int(rng.integers(30, 121))
        sequential = rng.random() > 0.2
        ua = pick(rng, ["chrome", "headless", "python"], [0.5, 0.3, 0.2])
        sid = self._bot_common(t0, "scraper", pick(rng, ["direct", "referral"], [0.7, 0.3]), ua=ua)
        path = ["home", "products"] + ["product_detail"] * (n - 2)
        item = int(rng.integers(1, 100))
        t = t0
        for i, page in enumerate(path):
            dwell = clip(lognorm(rng, 0.9, 0.25), 0.2, 5)
            it = None
            if page == "product_detail":
                if sequential:
                    item += 1
                else:
                    item = int(rng.integers(1, 5000))
                it = item
            self._view(sid, i, page, it, t, dwell, 0, 0.0, 0, 0, 0, 0.0)
            t += dwell + rng.uniform(0.02, 0.1)

    def crawler(self, t0):
        rng = self.rng
        ua = pick(rng, ["googlebot", "bingbot"], [0.6, 0.4])
        sid = self._bot_common(t0, "crawler", "direct", country="US", ua=ua)
        pool = ["products", "product_detail", "product_detail", "product_detail", "blog", "about",
                "reviews", "deals", "size_guide", "compare"]
        n = int(rng.integers(15, 51))
        path = ["home"] + [pool[int(rng.integers(len(pool)))] for _ in range(n - 1)]
        t = t0
        for i, page in enumerate(path):
            dwell = clip(lognorm(rng, 1.8, 0.3), 0.5, 8)
            it = int(rng.integers(1, 201)) if page == "product_detail" else None
            self._view(sid, i, page, it, t, dwell, 0, 0.0, 0, 0, 0, 0.0)
            t += dwell + rng.uniform(0.1, 0.5)

    def medium(self, t0):
        rng = self.rng
        source = pick(rng, ["cheap_ads", "direct", "search", "social_x"], [0.3, 0.25, 0.25, 0.2])
        path = human_path(rng, source, False)
        path = path[: int(rng.integers(3, 8))]
        fake = int(rng.random() < 0.25)
        sid = self._bot_common(t0, "medium", source, device="mobile" if fake else "desktop",
                               ua="safari" if fake else "chrome", fake=fake)
        t = t0
        for i, page in enumerate(path):
            dwell = clip(lognorm(rng, 3.0, 0.3), 0.8, 30)
            mouse = max(1, int(dwell * rng.uniform(1, 3)))
            straight = round(clip(rng.normal(0.80, 0.08), 0.5, 0.99), 3)
            scroll = 0.0 if rng.random() < 0.5 else float(rng.uniform(0.3, 0.7))
            it = int(rng.integers(1, 201)) if page == "product_detail" else None
            fa = 1 if page in C.FORM_PAGES else 0
            self._view(sid, i, page, it, t, dwell, mouse, straight, 0, 1, 0, scroll, fa, 2.0 * fa)
            t += dwell + rng.uniform(0.1, 0.6)

    def smart(self, t0):
        """Copies humans closely: human-style paths, human-style timing (a bit less
        uneven), curvy mouse. It never buys and never touches forms."""
        rng = self.rng
        source = pick(rng, HUMAN_SOURCES, HUMAN_SOURCE_P)
        path = human_path(rng, source, False)
        if "cart" in path:                       # shoppers' bots stop before checkout
            path = path[: path.index("cart")]
        if len(path) < 2:
            path = path + ["products"]
        fake = int(rng.random() < 0.25)
        sid = self._bot_common(t0, "smart", source, country=pick(rng, *COUNTRY_HUMAN),
                               device="mobile" if fake else "desktop",
                               ua="safari" if fake else "chrome", fake=fake)
        t = t0
        for i, page in enumerate(path):
            med, cv = HUMAN_DWELL[page]
            dwell = clip(lognorm(rng, med * 0.8, cv * 0.65), 1.5, 600)
            mouse = max(1, int(dwell * rng.uniform(1.5, 4.5)))
            straight = round(clip(rng.normal(0.58, 0.10), 0.2, 0.95), 3)
            scroll = float(rng.beta(2, 2))
            clicks = 1 + int(rng.poisson(1.0))
            it = int(rng.integers(1, 201)) if page == "product_detail" else None
            self._view(sid, i, page, it, t, dwell, mouse, straight, 0, clicks, 0, scroll)
            t += dwell + rng.uniform(0.2, 1.2)

    def novel(self, t0):
        """A bot type the classifier has never seen: very long, very regular, perfect
        straight mouse lines, always scrolls exactly half the page."""
        rng = self.rng
        sid = self._bot_common(t0, "slow_drip", pick(rng, ["email", "referral"], [0.5, 0.5]),
                               true_type="novel_bot")
        cycle = ["products", "blog", "about"]
        n = int(rng.integers(8, 16))
        t = t0
        for i in range(n):
            dwell = clip(lognorm(rng, 45, 0.04), 20, 90)
            self._view(sid, i, cycle[i % 3], None, t, dwell, 40, 1.0, 0, 0, 0, 0.5)
            t += dwell + rng.uniform(0.5, 1.0)


# ---------------------------------------------------------------------------
# Scheduling: who visits when
# ---------------------------------------------------------------------------
def _when(rng, day_start, weights):
    hour = int(rng.choice(24, p=weights))
    return day_start + hour * 3600 + float(rng.uniform(0, 3600))


def build_main(seed, n_days, plan_on=True):
    f = Factory(seed, plan_on)
    rng = f.rng
    base = pd.Timestamp(C.START_DATE).timestamp()
    first_dow = pd.Timestamp(C.START_DATE).weekday()
    sp = PLAN["spike"]
    for d in range(n_days):
        ds = base + d * 86400
        fac = DAY_FACTOR[(first_dow + d) % 7]
        for _ in range(rng.poisson(260 * fac)):
            f.human(_when(rng, ds, HOUR_W))
        for _ in range(rng.poisson(16 + 0.7 * d)):
            f.agent(_when(rng, ds, 0.5 * HOUR_W + 0.5 * FLAT_W))
        for _ in range(rng.poisson(18)):
            f.dumb(_when(rng, ds, FLAT_W))
        for _ in range(rng.poisson(3)):
            f.scraper(_when(rng, ds, NIGHT_W))
        for _ in range(rng.poisson(12)):
            f.crawler(_when(rng, ds, FLAT_W))
        for _ in range(rng.poisson(14)):
            f.medium(_when(rng, ds, NIGHT_W))
        for _ in range(rng.poisson(8)):
            f.smart(_when(rng, ds, HOUR_W))
        if 9 <= d <= 20:
            for _ in range(rng.poisson(10)):
                f.novel(_when(rng, ds, FLAT_W))
        if plan_on and d == sp["day"]:
            start = ds + sp["hour"] * 3600
            for _ in range(sp["n"]):
                f.dumb(start + float(rng.uniform(0, sp["minutes"] * 60)), flood=True)
    return f


def build_training(seed):
    """Labelled practice data (like verified sessions from honeypots).
    No planted site problems and NO novel bots."""
    f = Factory(seed, False)
    rng = f.rng
    base = pd.Timestamp(C.START_DATE).timestamp() - 30 * 86400
    plan = [(f.human, 1800, HOUR_W), (f.agent, 800, FLAT_W), (f.dumb, 350, FLAT_W),
            (f.scraper, 80, NIGHT_W), (f.crawler, 200, FLAT_W), (f.medium, 300, NIGHT_W),
            (f.smart, 250, HOUR_W)]
    for fn, count, w in plan:
        for _ in range(count):
            fn(_when(rng, base + int(rng.integers(0, 7)) * 86400, w))
    return f


def _tables(f):
    sess = pd.DataFrame(f.sessions).sort_values("start_ts").reset_index(drop=True)
    sess["start_ts"] = pd.to_datetime(sess["start_ts"], unit="s").dt.strftime("%Y-%m-%d %H:%M:%S")
    views = pd.DataFrame(f.views, columns=VIEW_COLS)
    views = views.sort_values(["session_id", "step"]).reset_index(drop=True)
    labels = pd.DataFrame(f.labels)
    return sess, views, labels


def generate_all(verbose=True):
    C.DATA_DIR.mkdir(parents=True, exist_ok=True)
    C.KEY_DIR.mkdir(parents=True, exist_ok=True)
    C.TRAIN_DIR.mkdir(parents=True, exist_ok=True)

    main = build_main(C.SEED, C.N_DAYS, True)
    sess, views, labels = _tables(main)
    sess.to_csv(C.DATA_DIR / "sessions.csv", index=False)
    views.to_csv(C.DATA_DIR / "pageviews.csv", index=False)
    labels.to_csv(C.KEY_DIR / "labels.csv", index=False)

    sp = PLAN["spike"]
    base = pd.Timestamp(C.START_DATE)
    spike_start = base + pd.Timedelta(days=sp["day"], hours=sp["hour"])
    key = dict(PLAN)
    key["spike"] = dict(sp, start=str(spike_start), end=str(spike_start + pd.Timedelta(minutes=sp["minutes"])))
    key["note"] = ("HIDDEN ANSWER KEY. Only evaluation/ reads this. "
                   "Planted problems and which sessions are really bots.")
    (C.KEY_DIR / "planted.json").write_text(json.dumps(key, indent=2, default=list))

    train = build_training(C.SEED + 1)
    tsess, tviews, tlabels = _tables(train)
    tsess.to_csv(C.TRAIN_DIR / "sessions.csv", index=False)
    tviews.to_csv(C.TRAIN_DIR / "pageviews.csv", index=False)
    tlabels.to_csv(C.TRAIN_DIR / "labels.csv", index=False)

    if verbose:
        print(f"  main data     : {len(sess):,} visits, {len(views):,} page views")
        print(f"  practice data : {len(tsess):,} labelled visits (for training the classifier)")
        print("  true mix      :", labels["true_type"].value_counts().to_dict())
    return sess, views, labels


if __name__ == "__main__":
    generate_all()
