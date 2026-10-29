"""
A tiny local collector. It receives events from tracker.js and saves them to a file.

    python tracker/collector.py          # listens on http://localhost:8765

Each event is one line of JSON in  data/live/events.jsonl.
Standard library only, so there is nothing to install.
"""
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "live" / "events.jsonl"
FIELDS = {"session_id", "step", "page", "t_start", "dwell_s", "mouse_events", "mouse_straightness",
          "touch_events", "clicks", "rage_clicks", "scroll_depth", "form_attempts", "form_seconds",
          "source", "device_claimed", "ua_family", "country"}


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            ev = json.loads(self.rfile.read(n).decode("utf-8"))
            ev = {k: v for k, v in ev.items() if k in FIELDS}      # keep only the known fields
            ev["received_at"] = time.time()
            OUT.parent.mkdir(parents=True, exist_ok=True)
            with open(OUT, "a") as f:
                f.write(json.dumps(ev) + "\n")
            self.send_response(204)
        except Exception:
            self.send_response(400)
        self._cors(); self.end_headers()

    def log_message(self, *a):
        pass


def serve(port=8765):
    print(f"Collector listening on http://localhost:{port}/collect  ->  {OUT}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    serve(int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
