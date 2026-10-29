"""Serve the demo shop at http://localhost:8000  (the tracker is loaded from ../tracker/)."""
import functools
import http.server
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
print("Demo shop: http://localhost:8000/demo_shop/index.html   (Ctrl+C to stop)")
http.server.ThreadingHTTPServer(("0.0.0.0", 8000), handler).serve_forever()
