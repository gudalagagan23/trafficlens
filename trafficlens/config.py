"""
TrafficLens settings.

This is the one place that describes the website being studied (its pages,
links and checkout steps) and where files live. Everything else imports it.

Note for readers: this file only holds things the SITE OWNER would know
(the page list, the menu links, the checkout steps). It does NOT hold
the planted problems. Those live in data_generator/ and the hidden
answer key, so the analysis can never "peek" at the answers.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Where the visitor data lives. You can point this at other data with
#   TRAFFICLENS_DATA=/path/to/folder python run_all.py --skip-generate
DATA_DIR = Path(os.environ.get("TRAFFICLENS_DATA", ROOT / "data"))
TRAIN_DIR = ROOT / "data" / "training"        # labelled practice data for the classifier
KEY_DIR = DATA_DIR / "answer_key"             # ONLY evaluation/ may read this
OUT_DIR = ROOT / "outputs"
REPORT_DIR = ROOT / "report"

PRODUCT_NAME = "TrafficLens"
SUBTITLE = "Web Traffic and User Behaviour Intelligence"

SEED = 42
N_DAYS = 21
START_DATE = "2026-09-07"     # a Monday

# ---- The demo shop -----------------------------------------------------
PAGES = [
    "home", "products", "product_detail", "deals", "blog", "about",
    "compare", "size_guide", "reviews",
    "cart", "shipping", "payment", "confirmation",
]
FUNNEL = ["cart", "shipping", "payment", "confirmation"]   # the buying steps
FORM_PAGES = ["shipping", "payment"]
CONTENT_PAGES = ["products", "product_detail", "blog", "reviews", "deals", "about"]
SOURCES = ["search", "direct", "social_x", "email", "referral",
           "promo_ads", "cheap_ads", "ai_assistant"]

# Which page links to which (the site as DESIGNED, like a sitemap).
DESIGNED_LINKS = {
    "home": ["products", "deals", "blog", "about", "product_detail"],
    "products": ["product_detail", "deals", "home", "blog"],
    "product_detail": ["cart", "products", "compare", "size_guide"],
    "deals": ["product_detail", "products", "home"],
    "blog": ["home", "products", "product_detail"],
    "about": ["home", "reviews"],
    "compare": ["product_detail", "products"],
    "size_guide": ["product_detail"],
    "reviews": ["cart", "product_detail", "products"],
    "cart": ["shipping", "products"],
    "shipping": ["payment", "cart"],
    "payment": ["confirmation", "shipping"],
    "confirmation": ["home"],
}

# Where a visitor is in the "buying journey" (used for the goal-focus trait).
STAGE = {
    "home": 0, "products": 1, "deals": 1, "blog": 1, "about": 1,
    "product_detail": 2, "compare": 2, "size_guide": 2, "reviews": 2,
    "cart": 3, "shipping": 4, "payment": 5, "confirmation": 6,
}

VISITOR_TYPES = ["human", "ai_agent", "old_bot", "unknown"]
