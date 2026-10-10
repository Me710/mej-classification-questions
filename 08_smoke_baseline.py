"""Étape 8 (contrôle) — Baseline TF-IDF + régression logistique en validation croisée sur les 5 plis.

But : vérifier que les exports s'utilisent tels quels et fixer un plancher de référence.
Le test reste fermé : il ne sert qu'à la toute fin.
Sortie : reports/smoke_baseline.csv
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error
from sklearn.pipeline import make_pipeline, make_union
from sklearn.feature_extraction.text import TfidfVectorizer

from common import PROCESSED, REPORTS, SEED

tr = pd.read_csv(PROCESSED / "tfidf" / "train.csv", encoding="utf-8-sig", dtype={"y_domain_grp": str, "y_sub_grp": str})


def model():
    feats = make_union(TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=2, sublinear_tf=True),
                       TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True))
    return make_pipeline(feats, LogisticRegression(max_iter=3000, C=5, class_weight="balanced", random_state=SEED))


def cv(df, text_col, y_col, ordinal=False):
    scores = []
    for k in range(5):
        a, b = df[df.fold != k], df[df.fold == k]
        clf = model().fit(a[text_col], a[y_col].astype(str))
        p = clf.predict(b[text_col])
        if ordinal:
            yt, yp = b[y_col].astype(float).values, p.astype(float)
            scores.append((accuracy_score(yt, yp), mean_absolute_error(yt, yp)))
        else:
            scores.append((f1_score(b[y_col].astype(str), p, average="macro"), accuracy_score(b[y_col].astype(str), p)))
    s = np.array(scores)
    return s.mean(0), s.std(0)


rows = []
for task, y in (("domaine", "y_domain_grp"), ("sous-domaine", "y_sub_grp")):
    for col in ("x_stem", "x_stem_choices", "x_full"):
        (f1, acc), (f1s, accs) = cv(tr, col, y)
        rows.append({"tâche": task, "entrée": col, "macro_F1": f"{f1:.3f} ± {f1s:.3f}", "exactitude": f"{acc:.3f} ± {accs:.3f}"})
lv = tr[tr.level_min.notna()]
for y in ("level_min", "level_max"):
    (acc, mae), (accs, maes) = cv(lv, "x_stem_choices", y, ordinal=True)
    rows.append({"tâche": y, "entrée": "x_stem_choices", "macro_F1": "", "exactitude": f"{acc:.3f} ± {accs:.3f}",
                 "MAE_annees": f"{mae:.2f} ± {maes:.2f}"})
# plancher naïf : toujours la classe majoritaire
maj = {y: tr[y].value_counts(normalize=True).iloc[0] for y in ("y_domain_grp", "y_sub_grp")}
res = pd.DataFrame(rows)
res.to_csv(REPORTS / "smoke_baseline.csv", index=False, encoding="utf-8-sig")
print(res.to_string(index=False))
print("classe majoritaire (exactitude) :", {k: round(v, 3) for k, v in maj.items()})
