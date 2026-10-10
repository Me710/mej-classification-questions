"""Étape 3 — Audit des étiquettes et de la qualité. Ne corrige rien : signale.

Sorties : reports/label_audit.csv (1 ligne/question, colonnes flag_*), reports/audit_confusion_sous_domaines.csv,
          reports/audit_summary.txt, data/interim/dup_clusters.parquet (utilisé par l'étape 6)
"""
import re
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from common import (DEDUP_THRESHOLD, LEVEL_YEAR, RAW_BILI, RAW_XLSX, REPORTS, has_negative, load, norm_ws, save,
                    split_sections)

m = load("master_raw")
out = []
def say(*a):
    s = " ".join(str(x) for x in a); print(s); out.append(s)

text = m.text_fr_raw.fillna(m.text_en_raw)
parts = text.map(split_sections)
stem_choices = parts.map(lambda p: norm_ws(p["stem"] + " || " + " | ".join(p["choices"])))
flags = pd.DataFrame({"id": m.id, "link_fr": m.link_fr, "dom_base": m.dom_base, "sub_base": m.sub_base,
                      "dom_plat": m.dom_plat, "sub_plat": m.sub_plat})

# ------------------------------------------------ 1. base vs plateforme
p = m[m.sub_plat.notna() & m.sub_base.notna()]
say("== 1. Base (final_*) vs plateforme (Iterations)")
say(f"domaine : {(p.dom_plat == p.dom_base).mean():.1%} d'accord sur {len(p)} questions")
say(f"sous-domaine : {(p.sub_plat == p.sub_base).mean():.1%} d'accord")
conf = Counter(zip(p.sub_plat, p.sub_base))
cm = pd.DataFrame([(a, b, n) for (a, b), n in conf.items() if a != b], columns=["plateforme", "base", "n"]).sort_values(["n", "plateforme", "base"], ascending=[False, True, True], kind="mergesort")
cm.to_csv(REPORTS / "audit_confusion_sous_domaines.csv", index=False, encoding="utf-8-sig")
say("principaux désaccords (plateforme -> base) :", cm.head(6).values.tolist())
flags["flag_conflict_dom"] = (m.dom_plat.notna() & m.dom_base.notna() & (m.dom_plat != m.dom_base))
flags["flag_conflict_sub"] = (m.sub_plat.notna() & m.sub_base.notna() & (m.sub_plat != m.sub_base))

# ------------------------------------------------ 2. règle de bon sens : « Nombres entiers » sans nombre négatif
m["has_negative"] = (m.text_fr_raw.map(has_negative) | m.text_en_raw.map(has_negative))
ent = m[m.sub_base.isin(["1.2", "2.3"])]
say("\n== 2. Cohérence sémantique « Nombres entiers » (1.2, 2.3)")
say(f"{len(ent)} questions étiquetées 'entiers' dans la base ; {ent.has_negative.mean():.1%} contiennent un nombre négatif")
nat = m[m.sub_base.isin(["1.1", "2.1"])]
say(f"pour comparaison, 'naturels' (1.1, 2.1) : {len(nat)} questions, {nat.has_negative.mean():.1%} avec un négatif")
flags["flag_entiers_sans_negatif"] = m.sub_base.isin(["1.2", "2.3"]) & ~m.has_negative
# Programme (PFEQ) : les nombres entiers relatifs relèvent du 3e cycle du primaire (5e-6e année) ;
# une question « entiers » dont le niveau maximal est ≤ 4e année contredit le programme.
lvl_max = m.levels.map(lambda l: max((LEVEL_YEAR[x] for x in l if x in LEVEL_YEAR), default=None) if isinstance(l, (list, np.ndarray)) else None)
flags["flag_entiers_avant_3e_cycle"] = m.sub_base.isin(["1.2", "2.3"]) & lvl_max.notna() & (lvl_max.fillna(99) <= 3)
say(f"plateforme : {m.sub_plat.isin(['1.2', '2.3']).sum()} question(s) 'entiers' sur {m.sub_plat.notna().sum()} étiquetées")
say(f"'entiers' dont le niveau max est ≤ 4e année (contraire au programme) : {flags.flag_entiers_avant_3e_cycle.sum()}")

# ------------------------------------------------ 3. FR vs EN dans la base
fe = m[m.sub_orig_fr.notna() & m.sub_orig_en.notna()]
flags["flag_fr_en"] = m.sub_orig_fr.notna() & m.sub_orig_en.notna() & (m.sub_orig_fr != m.sub_orig_en)
say(f"\n== 3. Étiquette FR vs EN : {(fe.sub_orig_fr != fe.sub_orig_en).sum()} désaccords sur {len(fe)} ({(fe.sub_orig_fr != fe.sub_orig_en).mean():.1%})")

# ------------------------------------------------ 4. hiérarchie, manquants, exactitude
flags["flag_hierarchie"] = m.sub_base.notna() & m.dom_base.notna() & (m.sub_base.str.split(".").str[0] != m.dom_base)
flags["flag_sans_etiquette"] = m.dom_base.isna()
flags["flag_inexact"] = m.exact_fr.eq(False) | m.exact_en.eq(False)
say(f"\n== 4. Hiérarchie incohérente : {flags.flag_hierarchie.sum()} | sans étiquette : {flags.flag_sans_etiquette.sum()} "
    f"| exactitude FAUX (FR ou EN) : {flags.flag_inexact.sum()}")

# ------------------------------------------------ 5. doublons et quasi-doublons
vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1, sublinear_tf=True)
X = vec.fit_transform(stem_choices.str.lower())
S = cosine_similarity(X, dense_output=False).tocoo()
parent = list(range(len(m)))
def find(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]; i = parent[i]
    return i
pairs = [(i, j, v) for i, j, v in zip(S.row, S.col, S.data) if i < j and v >= DEDUP_THRESHOLD]
for i, j, _ in pairs:
    parent[find(i)] = find(j)
cluster = np.array([find(i) for i in range(len(m))])
m["dup_cluster"] = pd.Series(cluster).map({c: k for k, c in enumerate(pd.unique(cluster))}).values
size = m.groupby("dup_cluster").id.transform("size")
lab_conf = m.groupby("dup_cluster").sub_base.transform(lambda s: s.dropna().nunique() > 1)
flags["dup_cluster"] = m.dup_cluster
flags["dup_size"] = size
flags["flag_doublon_conflit"] = (size > 1) & lab_conf
say(f"\n== 5. Quasi-doublons (cosinus ≥ {DEDUP_THRESHOLD}) : {len(pairs)} paires, "
    f"{(size > 1).sum()} questions dans {m[size > 1].dup_cluster.nunique()} groupes, "
    f"dont {flags.flag_doublon_conflit.sum()} questions dans des groupes aux sous-domaines différents")
ex = m[(size > 1) & lab_conf].groupby("dup_cluster").head(2)
for _, r in ex.head(4).iterrows():
    say(f"   q{r.id} [{r.sub_base}] {stem_choices[_][:110]}")
save(m[["id", "dup_cluster"]], "dup_clusters")

# ------------------------------------------------ 6. fichiers synthétiques
say("\n== 6. Fichiers synthétiques")
x = pd.read_excel(RAW_XLSX, dtype=str)
bad = ~x["Réponse Correcte"].isin(list("ABCD"))
say(f"xlsx : {len(x)} lignes, {bad.sum()} lignes corrompues (colonnes décalées par '|'), "
    f"position de la bonne réponse {x.loc[~bad, 'Réponse Correcte'].value_counts(normalize=True).round(3).to_dict()}")
b = pd.read_csv(RAW_BILI, encoding="utf-8-sig", dtype=str)
inch = b.apply(lambda r: r["Bonne réponse (FR)"] in r["Choix de réponse (FR)"].split(";"), axis=1)
say(f"bilingue : {len(b)} lignes, {b['Question (FR)'].nunique()} questions uniques, bonne réponse absente des choix : {(~inch).sum()}")

flag_cols = [c for c in flags.columns if c.startswith("flag_")]
flags["n_flags"] = flags[flag_cols].sum(axis=1)
flags.to_csv(REPORTS / "label_audit.csv", index=False, encoding="utf-8-sig")
say("\n== Bilan : questions avec au moins un signal :", int((flags.n_flags > 0).sum()), "/", len(flags))
say(flags[flag_cols].sum().to_string())
(REPORTS / "audit_summary.txt").write_text("\n".join(out), encoding="utf-8")
