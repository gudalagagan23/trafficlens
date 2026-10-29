"""
Builds the demo shop: 13 small HTML pages that match the site map in config.py.
Every page loads the tracker. Run:

    python demo_shop/build_shop.py     # makes the pages
    python demo_shop/serve.py          # opens http://localhost:8000
    python tracker/collector.py        # in a second window: receives the events
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config as C

OUT = Path(__file__).resolve().parent
TITLES = {
    "home": "Welcome to the demo shop", "products": "All products", "product_detail": "Trail runner shoe",
    "deals": "This week's deals", "blog": "Running tips", "about": "About us", "compare": "Compare shoes",
    "size_guide": "Size guide", "reviews": "Customer reviews", "cart": "Your cart", "shipping": "Shipping details",
    "payment": "Payment", "confirmation": "Thank you for your order",
}
FORMS = {
    "shipping": '<form onsubmit="event.preventDefault(); location.href=\'payment.html\'"><input placeholder="Address"> <input placeholder="City"> <button>Continue</button></form>',
    "payment": '<form onsubmit="event.preventDefault(); location.href=\'confirmation.html\'"><input placeholder="Card (demo only, do not type real data)"> <button>Pay</button></form>',
    "cart": '<p><input placeholder="Coupon code"> <button>Apply</button></p>',
}
CSS = "body{font-family:system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 16px;color:#1f2430}nav a{margin-right:14px}h1{font-size:22px}footer{margin-top:60px;color:#6b7280;font-size:12px}"


def build():
    for page in C.PAGES:
        links = " ".join(f'<a href="{t}.html">{t.replace("_", " ")}</a>' for t in C.DESIGNED_LINKS[page])
        html = (f"<!doctype html><html><head><meta charset='utf-8'><title>{TITLES[page]}</title><style>{CSS}</style></head><body>"
                f"<h1>{TITLES[page]}</h1><nav>{links}</nav>{FORMS.get(page, '')}"
                f"<p style='height:900px'>Demo page. Scroll down to test scroll tracking.</p>"
                f"<footer>TrafficLens demo shop. The tracker records patterns (timing, mouse, scrolling), never what you type.</footer>"
                f"<script src='../tracker/tracker.js'></script></body></html>")
        (OUT / f"{page}.html").write_text(html)
    (OUT / "index.html").write_text((OUT / "home.html").read_text())
    print(f"built {len(C.PAGES)} pages in {OUT}")


if __name__ == "__main__":
    build()
