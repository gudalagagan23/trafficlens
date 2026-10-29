"""
Safety checks. Run them with:   python -m tests.test_checks

1. NO PEEKING   : only evaluation/ (and the data generator that writes it) may touch the answer key.
2. NUMBER CHECK : the report agent must reject a sentence that contains an invented number.
3. DETERMINISM  : the same seed must make the same fake visitors.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_peeking():
    allowed = {"evaluation", "data_generator", "tests"}
    bad = []
    for py in ROOT.rglob("*.py"):
        rel = py.relative_to(ROOT)
        top = rel.parts[0]
        if top in allowed or rel.name in ("config.py", "run_all.py"):
            continue
        text = py.read_text()
        # practice labels (TRAIN_DIR) are allowed: that is how the judge learns.
        # The hidden answer key (KEY_DIR / planted.json) and the generator are not.
        if re.search(r"KEY_DIR|answer_key|planted\.json|data_generator", text):
            bad.append(str(rel))
    assert not bad, f"These files look at the answer key: {bad}"


def test_number_check_rejects_invented_numbers():
    import sys
    sys.path.insert(0, str(ROOT))
    from agent.report import Facts
    f = Facts()
    ok = f"{f.n('visits', 452)} visits came from one source"
    assert f.check(ok) == []
    assert f.check("About 999 visits came from one source") == ["999"]


def test_same_seed_same_visitors():
    import sys
    sys.path.insert(0, str(ROOT))
    from data_generator.generate import build_training
    a, b = build_training(7), build_training(7)
    assert a.views[:50] == b.views[:50] and len(a.sessions) == len(b.sessions)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
