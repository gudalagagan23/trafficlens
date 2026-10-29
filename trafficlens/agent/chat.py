"""
The chat box.

Mode 1 (default, offline, no key needed):
  Matches your question to the verified findings and answers only from them.
  If nothing matches, it says "I'm not sure" instead of guessing.

Mode 2 (optional): a language model.
  Set the environment variable ANTHROPIC_API_KEY and install `anthropic`.
  The model is given ONLY the findings and told to quote their numbers.
  NOTE: this mode could not be tested in the build environment (no API key there).
"""
import json
import os
import re

import config as C

SYNONYMS = {
    "spike": ["spike", "jump", "surge", "sudden", "burst", "flood", "attack", "peak"],
    "dumb_bots": ["bot", "bots", "script", "automated", "simple"],
    "smart_bots_agents": ["hiding", "smart", "agent", "agents", "unknown", "human-like", "fake human", "pretend"],
    "scrapers": ["scraper", "scrapers", "scrape", "copy", "copying", "prices", "catalogue"],
    "low_quality_source": ["source", "quality", "ads", "ad", "cheap", "worst", "traffic source"],
    "fake_device": ["device", "phone", "mobile", "touch", "fake device"],
    "crawlers": ["crawler", "googlebot", "search engine", "good bot", "seo"],
    "dead_end": ["dead", "end", "stuck", "size", "trap"],
    "funnel_drop": ["funnel", "checkout", "drop", "leave", "abandon", "shipping", "buyers", "cart"],
    "loops": ["loop", "loops", "back and forth", "bounce between", "compare", "confused"],
    "rage_clicks": ["rage", "click", "clicking", "frustrated", "coupon", "button"],
    "hidden_page": ["hidden", "reviews", "useful", "buried"],
    "type_gap": ["agent", "agents", "ai", "payment", "gap", "fail"],
    "expectation_mismatch": ["promo", "deals", "expectation", "mismatch", "ad promise"],
    "dirty_averages": ["average", "averages", "bounce", "conversion", "distort", "numbers", "report"],
}


STOP = {"is", "are", "a", "an", "the", "at", "from", "to", "and", "of", "in", "on", "for", "with",
        "between", "bring", "brings", "visitors", "visitor", "many", "some", "what", "why", "how",
        "which", "did", "does", "this", "that", "our", "my", "me", "can", "you", "tell", "about"}


def _load():
    return json.loads((C.OUT_DIR / "findings.json").read_text())


def _fmt(f):
    return (f"{f['title']} (confidence: {f['confidence']})\n"
            f"- What happened: {f['what_happened']}\n- Where: {f['where']}\n"
            f"- {f['likely_cause']}\n- Fix first: {f['fix']}")


def answer(question: str, findings=None) -> str:
    findings = findings or _load()
    ok = [f for f in findings if f["confidence"] != "rejected"]
    q = question.lower()
    words = set(re.findall(r"[a-z\-]+", q))

    if re.search(r"fix (first|now)|priorit|top fix|what should i (do|fix)", q):
        t = sorted([f for f in ok if f["side"] == "traffic"], key=lambda f: -f["impact_visits"])[:3]
        b = sorted([f for f in ok if f["side"] == "behaviour"], key=lambda f: -f["impact_visits"])[:3]
        return ("Top fixes, ranked by how many visits they affect.\n\nWeb traffic:\n"
                + "\n".join(f"- {f['title']}: {f['fix']}" for f in t)
                + "\n\nUser behaviour:\n" + "\n".join(f"- {f['title']}: {f['fix']}" for f in b))

    scored = []
    for f in ok:
        title_words = {w for w in re.findall(r"[a-z_]+", f["title"].lower()) if len(w) >= 4 and w not in STOP}
        keys = set(SYNONYMS.get(f["issue"], [])) | title_words
        score = sum(1 for k in keys if (" " in k and k in q) or k in words)
        if score:
            scored.append((score, f))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return ("I'm not sure. I can only answer from what the system calculated. "
                "Try asking about a spike, bots, a traffic source, a page, checkout, or what to fix first.")
    return "\n\n".join(_fmt(f) for _, f in scored[:2])


SYSTEM = ("You are the TrafficLens analyst. Answer ONLY from the findings JSON. Quote the numbers exactly. "
          "If the findings do not contain the answer, say you are not sure. Mark causes as guesses. "
          "Use simple words.")


def ask_llm(question: str, findings=None, model=None):
    """Optional. Returns None when no API key / library is available."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import anthropic
    except ImportError:
        return None
    findings = findings or _load()
    client = anthropic.Anthropic(api_key=key)
    msg = client.messages.create(
        model=model or os.environ.get("TRAFFICLENS_MODEL", "claude-sonnet-5-5"),
        max_tokens=600, system=SYSTEM,
        messages=[{"role": "user", "content": f"FINDINGS:\n{json.dumps(findings)}\n\nQUESTION: {question}"}])
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def reply(question: str) -> str:
    return ask_llm(question) or answer(question)


if __name__ == "__main__":
    for q in ["why did traffic jump?", "which source is worst?", "what should I fix first?", "what is the weather?"]:
        print("Q:", q)
        print(answer(q)[:400], "\n")
