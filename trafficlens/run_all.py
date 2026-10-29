"""
Run the whole TrafficLens project with ONE command:

    python run_all.py                 # make fake visitors, analyse, score, draw charts
    python run_all.py --skip-generate # reuse the data already in data/ (or your own data)

Then open the screen with:

    streamlit run dashboard/app.py
"""
import argparse
import sys
import time

import config as C


def step(n, total, title):
    print(f"\n[{n}/{total}] {title}")
    return time.time()


def done(t):
    print(f"      done in {time.time() - t:.1f}s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-generate", action="store_true", help="reuse existing data instead of making fake visitors")
    args = ap.parse_args()
    total = 9
    C.OUT_DIR.mkdir(exist_ok=True)
    C.REPORT_DIR.mkdir(exist_ok=True)
    print(f"{C.PRODUCT_NAME}: {C.SUBTITLE}")

    if not args.skip_generate:
        t = step(1, total, "Making fake visitors (humans, AI agents, bots) and planting 12 problems")
        from data_generator.generate import generate_all
        generate_all()
        done(t)
    else:
        print("\n[1/9] Skipping data generation (using the data already in place)")

    t = step(2, total, "Turning raw page views into one record per visitor (with the behaviour fingerprint)")
    from pipeline import features
    features.run()
    done(t)

    t = step(3, total, "TRAFFIC: judging every visitor (Human / AI agent / Old bot / Unknown)")
    from traffic import classifier
    classifier.run()
    done(t)

    t = step(4, total, "TRAFFIC: groups, spikes, source quality, fake devices, forecast")
    from traffic import analysis as traffic_analysis
    traffic_analysis.run()
    done(t)

    t = step(5, total, "BEHAVIOUR: journey graphs and the 6 behaviour issues (human visitors only)")
    from behaviour import analysis as behaviour_analysis
    behaviour_analysis.run()
    done(t)

    t = step(6, total, "BEHAVIOUR: predictions compared with simple baselines")
    from behaviour import predict
    predict.run()
    done(t)

    t = step(7, total, "LINK: where traffic and behaviour meet")
    from link import analysis as link_analysis
    link_analysis.run()
    done(t)

    t = step(8, total, "AGENT: writing the findings (every number is checked)")
    from agent import report
    report.run()
    done(t)

    t = step(9, total, "SCORE PAGE: planted problems vs found problems, and charts")
    from evaluation import score
    score.run()
    from dashboard import plots
    plots.save_all(C.REPORT_DIR / "figures")
    done(t)

    print("\nAll done. Open the screen with:\n    streamlit run dashboard/app.py")
    print("Read the results in:  report/RESULTS.md   and   report/AGENT_REPORT.md")


if __name__ == "__main__":
    sys.exit(main())
