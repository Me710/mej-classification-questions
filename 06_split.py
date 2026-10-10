"""Étape 6 — Découpage train / test + 5 plis de validation croisée, SANS FUITE.

Règles : (1) une famille de quasi-doublons (dup_cluster) ne traverse jamais deux partitions ;
(2) le même découpage sert à toutes les tâches (domaine, sous-domaine, niveau) ;
(3) les variantes LLM héritent de la partition de leur question d'origine.
Sortie : data/interim/splits.parquet
"""
import warnings

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from common import N_FOLDS, SEED, TEST_SIZE, load, save

warnings.filterwarnings("ignore", category=UserWarning)
tg = load("targets").merge(load("dup_clusters"), on="id")
e = tg[tg.train_eligible].reset_index(drop=True)

# clé de stratification : sous-domaine regroupé + borne basse du niveau quand elle existe
lvl = e.level_min.map(lambda v: "NA" if pd.isna(v) else ("L01" if v <= 1 else "L2" if v == 2 else "L34" if v <= 4 else "L5+"))
strat = (e.y_sub_grp + "|" + lvl).values
groups = e.dup_cluster.values


def best_test_fold(n_splits: int):
    """Teste plusieurs graines et garde le pli de test dont la distribution colle le mieux au global."""
    best, best_gap = None, 9e9
    glob = pd.Series(e.y_sub_grp).value_counts(normalize=True)
    glob_d = pd.Series(e.y_domain_grp).value_counts(normalize=True)
    for seed in range(SEED, SEED + 100):
        sgkf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
        for tr, te in sgkf.split(e, strat, groups):
            dist = e.y_sub_grp.iloc[te].value_counts(normalize=True).reindex(glob.index, fill_value=0)
            dist_d = e.y_domain_grp.iloc[te].value_counts(normalize=True).reindex(glob_d.index, fill_value=0)
            missing = (dist == 0).sum() + (dist_d == 0).sum()  # chaque classe absente du test est lourdement pénalisée
            lv = e.level_min.iloc[te].notna().mean() - e.level_min.notna().mean()
            gap = ((dist - glob).abs().sum() + (dist_d - glob_d).abs().sum() + missing
                   + abs(len(te) / len(e) - TEST_SIZE) * 2 + abs(lv))
            if gap < best_gap:
                best, best_gap = (tr, te), gap
    return best, best_gap


(train_idx, test_idx), gap = best_test_fold(round(1 / TEST_SIZE))
e["split"] = "train"
e.loc[test_idx, "split"] = "test"

e["fold"] = -1
tr = e[e.split == "train"]
sgkf = StratifiedGroupKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)
for k, (_, va) in enumerate(sgkf.split(tr, strat[tr.index], groups[tr.index])):
    e.loc[tr.index[va], "fold"] = k

out = tg[["id"]].merge(e[["id", "split", "fold", "dup_cluster"]], on="id", how="left")
out["split"] = out.split.fillna("exclu")
out["fold"] = out.fold.fillna(-1).astype(int)
save(out, "splits")

# ------------------------------------------------------------------ contrôles
leak = e.groupby("dup_cluster").split.nunique().gt(1).sum()
leak_f = e[e.split == "train"].groupby("dup_cluster").fold.nunique().gt(1).sum()
print(f"écart de distribution du test (L1) : {gap:.3f}")
print("partitions :", out.split.value_counts().to_dict(), "| plis :", e[e.split == 'train'].fold.value_counts().sort_index().to_dict())
print(f"familles de quasi-doublons à cheval train/test : {leak} | à cheval entre plis : {leak_f}")
tab = pd.crosstab(e.y_domain_grp, e.split, normalize="columns").round(3)
print("domaine par partition :\n", tab)
print("sous-domaines absents du test :", sorted(set(e.y_sub_grp) - set(e[e.split == 'test'].y_sub_grp)))
lv = e[e.level_min.notna()]
print("niveau (questions avec niveaux) :", lv.split.value_counts().to_dict())
print("level_min par partition :\n", pd.crosstab(lv.level_min, lv.split))
print("image par partition :", e.groupby("split").has_image.mean().round(3).to_dict())
