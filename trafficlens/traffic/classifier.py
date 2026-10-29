"""
The visitor judge.

Every visitor gets one label: human, ai_agent, old_bot, or unknown.

How it decides
  1. A model learns from LABELLED PRACTICE visits (verified humans, agents and bots).
  2. For each new visitor it gives a confidence for each type.
  3. "unknown" is used in two situations:
       - NOVEL   : the visitor looks unlike anything seen in practice data
                   (far from its nearest practice visitors).
       - UNSURE  : the model's best guess is weak (confidence below 55%).
  We would rather say "not sure" than guess wrong.

Why a safety reference set matters
  The model is trained ONCE on a fixed, verified practice set. It does not keep
  learning from live traffic, so a huge bot attack cannot teach it that bots are normal.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

import config as C

FEATURES = [
    "n_pages", "duration_s", "pages_per_min", "mouse_pp", "straightness", "touch_pp",
    "click_pp", "scroll_mean", "scroll_std", "ua_automation", "declared_crawler",
    "device_mismatch", "item_seq_share", "single_page",
    "exploring", "depth", "backtracking", "recovery", "speed", "rhythm", "reading",
    "form_handling", "goal_focus",
]
LOG_COLS = ["n_pages", "duration_s", "pages_per_min"]
CONF_MIN = 0.55       # below this, we say "unknown"
NOVEL_PERCENTILE = 99  # how far from practice data counts as "never seen before"
K = 5


def _matrix(df):
    X = df[FEATURES].copy()
    for c in LOG_COLS:
        X[c] = np.log1p(X[c])
    return X


def _group_label(row):
    return {"human": "human", "ai_agent": "ai_agent"}.get(row, "old_bot")


class Judge:
    def fit(self, train: pd.DataFrame):
        y = train["true_type"].map(_group_label)
        X = _matrix(train)
        self.imp = SimpleImputer(strategy="median").fit(X)
        Xi = self.imp.transform(X)
        self.scaler = StandardScaler().fit(Xi)
        self.model = RandomForestClassifier(
            n_estimators=300, min_samples_leaf=2, class_weight="balanced",
            random_state=C.SEED, n_jobs=-1).fit(Xi, y)
        Xs = self.scaler.transform(Xi)
        self.nn = NearestNeighbors(n_neighbors=K + 1).fit(Xs)
        d, _ = self.nn.kneighbors(Xs)               # d[:,0] is the point itself
        self.threshold = float(np.percentile(d[:, K], NOVEL_PERCENTILE))
        return self

    def predict(self, feats: pd.DataFrame) -> pd.DataFrame:
        Xi = self.imp.transform(_matrix(feats))
        proba = self.model.predict_proba(Xi)
        classes = list(self.model.classes_)
        best = proba.argmax(axis=1)
        conf = proba.max(axis=1)
        d, _ = self.nn.kneighbors(self.scaler.transform(Xi), n_neighbors=K)
        novelty = d[:, -1]
        novel = novelty > self.threshold
        unsure = conf < CONF_MIN
        label = np.array([classes[i] for i in best], dtype=object)
        reason = np.full(len(feats), "", dtype=object)
        reason[unsure] = "unsure"
        reason[novel] = "novel"               # novel wins if both are true
        label[novel | unsure] = "unknown"
        out = pd.DataFrame({
            "session_id": feats["session_id"].values,
            "pred_label": label,
            "best_guess": [classes[i] for i in best],
            "confidence": conf.round(3),
            "novelty": novelty.round(3),
            "unknown_reason": reason,
        })
        for i, c in enumerate(classes):
            out[f"p_{c}"] = proba[:, i].round(3)
        return out


def run(verbose=True):
    feats = pd.read_csv(C.OUT_DIR / "features.csv")
    train = pd.read_csv(C.OUT_DIR / "training_features.csv")
    judge = Judge().fit(train)
    preds = judge.predict(feats)
    preds.to_csv(C.OUT_DIR / "predictions.csv", index=False)
    if verbose:
        print("  visitor labels:", preds["pred_label"].value_counts().to_dict())
    return judge, preds


if __name__ == "__main__":
    run()
