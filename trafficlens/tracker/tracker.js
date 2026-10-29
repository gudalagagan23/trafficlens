/*
 * TrafficLens tracker  (privacy by design)
 *
 * WHAT IT RECORDS (patterns only):
 *   how long the visitor stayed, how many mouse movements and touches, how straight the
 *   mouse path was, number of clicks, bursts of angry clicks, how far they scrolled,
 *   how many times a form was submitted, and the traffic source.
 *
 * WHAT IT NEVER RECORDS:
 *   anything typed. It never reads input values, keystrokes, passwords or card numbers.
 *
 * Add it to a page with:   <script src="tracker.js"></script>
 * Events go to http://localhost:8765/collect  (see tracker/collector.py).
 */
(function () {
  var ENDPOINT = window.TRAFFICLENS_ENDPOINT || "http://localhost:8765/collect";
  var store = window.sessionStorage;

  // one anonymous id per browser tab session (random, not linked to a person)
  var sid = store.getItem("tl_sid");
  if (!sid) { sid = "L" + Math.random().toString(36).slice(2, 10); store.setItem("tl_sid", sid); }
  var step = parseInt(store.getItem("tl_step") || "0", 10);
  store.setItem("tl_step", String(step + 1));
  var source = store.getItem("tl_src");
  if (!source) {
    var q = new URLSearchParams(location.search).get("utm_source");
    var ref = document.referrer ? new URL(document.referrer).hostname : "";
    source = q || (ref && ref !== location.hostname ? "referral" : "direct");
    store.setItem("tl_src", source);
  }

  var start = performance.now(), startEpoch = Date.now() / 1000;
  var mouse = 0, touch = 0, clicks = 0, rage = 0, maxScroll = 0, formAttempts = 0, formSecs = 0, formStart = null;
  var pathLen = 0, lastX = null, lastY = null, firstX = null, firstY = null, lastMove = 0;
  var clickLog = [];

  document.addEventListener("mousemove", function (e) {
    var now = performance.now();
    if (now - lastMove < 50) return;               // sample 20 times a second at most
    lastMove = now;
    mouse++;
    if (lastX !== null) pathLen += Math.hypot(e.clientX - lastX, e.clientY - lastY);
    else { firstX = e.clientX; firstY = e.clientY; }
    lastX = e.clientX; lastY = e.clientY;
  }, { passive: true });

  document.addEventListener("touchstart", function () { touch++; }, { passive: true });

  document.addEventListener("click", function (e) {
    clicks++;
    var now = performance.now();
    clickLog.push({ t: now, x: e.clientX, y: e.clientY });
    clickLog = clickLog.filter(function (c) { return now - c.t < 1000; });
    var near = clickLog.filter(function (c) { return Math.hypot(c.x - e.clientX, c.y - e.clientY) < 30; });
    if (near.length === 3) rage += 3; else if (near.length > 3) rage += 1;   // an angry-click burst
  }, true);

  window.addEventListener("scroll", function () {
    var h = Math.max(document.documentElement.scrollHeight - innerHeight, 1);
    maxScroll = Math.max(maxScroll, Math.min(scrollY / h, 1));
  }, { passive: true });

  // forms: we only count tries and time, never look at what was typed
  document.addEventListener("focusin", function (e) {
    if (e.target.closest && e.target.closest("form") && formStart === null) formStart = performance.now();
  });
  document.addEventListener("submit", function () {
    formAttempts++;
    if (formStart !== null) { formSecs += (performance.now() - formStart) / 1000; formStart = null; }
  }, true);

  function uaFamily() {
    var u = navigator.userAgent.toLowerCase();
    if (/headless/.test(u)) return "headless";
    if (/googlebot/.test(u)) return "googlebot";
    if (/bingbot/.test(u)) return "bingbot";
    if (/curl|python|wget/.test(u)) return "python";
    if (/edg\//.test(u)) return "edge";
    if (/firefox/.test(u)) return "firefox";
    if (/chrome/.test(u)) return "chrome";
    if (/safari/.test(u)) return "safari";
    return "other";
  }
  function device() {
    var u = navigator.userAgent.toLowerCase();
    if (/ipad|tablet/.test(u)) return "tablet";
    if (/mobi|android|iphone/.test(u)) return "mobile";
    return "desktop";
  }

  var sent = false;
  function send() {
    if (sent) return; sent = true;
    var straight = (pathLen > 0 && firstX !== null) ? Math.min(Math.hypot(lastX - firstX, lastY - firstY) / pathLen, 1) : 0;
    var page = location.pathname.split("/").pop().replace(".html", "") || "home";
    var body = JSON.stringify({
      session_id: sid, step: step, page: page, t_start: startEpoch,
      dwell_s: (performance.now() - start) / 1000,
      mouse_events: mouse, mouse_straightness: straight, touch_events: touch,
      clicks: clicks, rage_clicks: rage, scroll_depth: maxScroll,
      form_attempts: formAttempts, form_seconds: formSecs,
      source: source, device_claimed: device(), ua_family: uaFamily(), country: ""
    });
    if (navigator.sendBeacon) navigator.sendBeacon(ENDPOINT, new Blob([body], { type: "text/plain" }));
    else fetch(ENDPOINT, { method: "POST", body: body, keepalive: true });
  }
  window.addEventListener("pagehide", send);
  document.addEventListener("visibilitychange", function () { if (document.visibilityState === "hidden") send(); });
})();
