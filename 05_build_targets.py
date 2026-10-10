"""Étape 5 — Construction des cibles et des variables d'appoint.

Sorties : data/interim/targets.parquet, data/processed/label_maps.json, reports/annotation_complexite.csv
"""
import json
import re

import numpy as np
import pandas as pd

from common import (LABEL_SOURCE, LEVEL_YEAR, LEVELS, META_LEVEL, MIN_CLASS_COUNT, PREP, PROCESSED, REPORTS, SEED,
                    load, save)

m = load("master_raw")
t = load("text_clean")
tax = load("taxonomy")
df = m.merge(t[["id", "x_stem", "x_stem_choices", "stem_fr", "stem_en"]], on="id")

# ------------------------------------------------------------ 1. éligibilité à l'entraînement
reason = pd.Series("", index=df.index)
reason[df.dom_base.isna()] += "sans_etiquette;"
reason[df.exact_fr.eq(False) | df.exact_en.eq(False)] += "inexact;"
reason[df.x_stem.str.len() < 5] += "enonce_vide;"
df["exclude_reason"] = reason.str.rstrip(";")
df["train_eligible"] = df.exclude_reason.eq("")

# ------------------------------------------------------------ 2. domaine / sous-domaine
if LABEL_SOURCE == "plateforme":
    df["y_domain"] = df.dom_plat.fillna(df.dom_base)
    df["y_sub"] = df.sub_plat.fillna(df.sub_base)
else:
    df["y_domain"] = df.dom_base
    df["y_sub"] = df.sub_base
df["label_source"] = LABEL_SOURCE

# corrections d'étiquettes : automatiques (04b, règle de convention) puis manuelles (revue humaine, prioritaires)
#   data/label_corrections_auto.csv  et  data/label_corrections.csv  (colonnes id, sous_domaine_corrige)
df["label_corrected"] = False
df["label_correction_rule"] = ""
for path, tag in ((PROCESSED.parent / "label_corrections_auto.csv", "auto"),
                  (PROCESSED.parent / "label_corrections.csv", "manuelle")):
    if not path.exists():
        continue
    corr = pd.read_csv(path, dtype=str, encoding="utf-8-sig").dropna(subset=["sous_domaine_corrige"])
    rule = corr.regle if "regle" in corr else pd.Series(tag, index=corr.index)
    rule_map = dict(zip(corr.id.astype(int), rule))
    corr = corr.assign(id=corr.id.astype(int)).set_index("id").sous_domaine_corrige.str.strip()
    hit = df.id.isin(corr.index)
    df.loc[hit, "y_sub"] = df.loc[hit, "id"].map(corr)
    df.loc[hit, "y_domain"] = df.loc[hit, "y_sub"].str.split(".").str[0]
    df.loc[hit, "label_corrected"] = True
    df.loc[hit, "label_correction_rule"] = df.loc[hit, "id"].map(rule_map).map(lambda r: f"{tag}:{r}" if tag == "auto" else tag)
    print(f"corrections {tag} appliquées : {hit.sum()}")

elig = df[df.train_eligible]
dom_counts = elig.y_domain.value_counts()
rare_dom = set(dom_counts[dom_counts < MIN_CLASS_COUNT].index)
df["y_domain_grp"] = df.y_domain.where(~df.y_domain.isin(rare_dom), "AUTRE")
# si le regroupement « AUTRE » reste sous le seuil, il est quand même gardé (signalé au rapport)

sub_counts = elig.y_sub.value_counts()
def group_sub(code):
    if pd.isna(code):
        return None
    if sub_counts.get(code, 0) >= MIN_CLASS_COUNT:
        return code
    d = code.split(".")[0]
    return f"{d}.x" if d not in rare_dom else "AUTRE"
df["y_sub_grp"] = df.y_sub.map(group_sub)
bucket = df[df.train_eligible].y_sub_grp.value_counts()
small_buckets = bucket[bucket < MIN_CLASS_COUNT].index
df.loc[df.y_sub_grp.isin(small_buckets) & df.y_sub_grp.str.endswith(".x"), "y_sub_grp"] = "AUTRE"

# ------------------------------------------------------------ 3. niveau : multi-étiquette ET intervalle ordinal
def slug(lvl):
    return re.sub(r"[^a-z0-9]+", "_", lvl.lower().replace("é", "e").replace("è", "e")).strip("_")
for lvl in LEVELS:
    df[f"lvl_{slug(lvl)}"] = df.levels.map(lambda l, lvl=lvl: (lvl in l) if isinstance(l, (list, np.ndarray)) else np.nan)
df["lvl_general"] = df.levels.map(lambda l: (META_LEVEL in l) if isinstance(l, (list, np.ndarray)) else np.nan)
years = df.levels.map(lambda l: sorted({LEVEL_YEAR[x] for x in l if x != META_LEVEL}) if isinstance(l, (list, np.ndarray)) else None)
df["level_min"] = years.map(lambda y: y[0] if y else np.nan)
df["level_max"] = years.map(lambda y: y[-1] if y else np.nan)
YEAR_NAME = {0: "1P", 1: "2P", 2: "3P", 3: "4P", 4: "5P", 5: "6P", 6: "S1", 7: "S2", 8: "S3", 9: "S4", 10: "S5", 11: "Cégep"}

# ------------------------------------------------------------ 4. variables d'appoint (aussi proxys de complexité)
src = df.x_stem_choices.fillna("")
stem = df.x_stem.fillna("")
nums = src.map(lambda s: [float(x.replace(" ", "").replace(",", ".")) for x in re.findall(r"\d{1,3}(?:[  ]\d{3})+|\d+(?:[.,]\d+)?", s)])
df["f_words_stem"] = stem.str.split().str.len()
df["f_sentences"] = stem.str.count(r"[.?!](?:\s|$)").clip(lower=1)
df["f_n_numbers"] = nums.map(len)
df["f_log_max_number"] = nums.map(lambda l: np.log10(max(l) + 1) if l else 0.0)
df["f_has_fraction"] = src.str.contains(r"\d\s*/\s*\d")
df["f_has_decimal"] = src.str.contains(r"\d[.,]\d")
df["f_has_percent"] = src.str.contains("%")
df["f_n_ops"] = src.str.count(r"[+×÷=<>≤≥√^]|\s[-−]\s")
df["f_qtype"] = df.qtype.fillna("INCONNU")

# score provisoire de complexité = moyenne de z-scores, puis tertiles. À REMPLACER par l'annotation humaine.
cols = ["f_words_stem", "f_sentences", "f_n_numbers", "f_log_max_number", "f_n_ops"]
z = df[cols].apply(lambda c: (np.log1p(c) - np.log1p(c).mean()) / np.log1p(c).std())
df["cx_proxy_score"] = z.mean(axis=1)
df["cx_proxy"] = pd.qcut(df.cx_proxy_score.rank(method="first"), 3, labels=["faible", "moyenne", "élevée"]).astype(str)

# annotation de référence (annotations/complexite_annotateur*.csv) : moyenne arrondie si plusieurs annotateurs
gold_files = sorted((PREP / "annotations").glob("complexite_annotateur*.csv"))
if gold_files:
    g = pd.concat([pd.read_csv(f, encoding="utf-8-sig")[["id", "complexite"]] for f in gold_files])
    gold = g.groupby("id").complexite.mean().round().astype(int)
    df["cx_gold"] = df.id.map(gold)
    from sklearn.metrics import cohen_kappa_score
    both = df.dropna(subset=["cx_gold"])
    proxy_num = both.cx_proxy.map({"faible": 1, "moyenne": 2, "élevée": 3})
    k = cohen_kappa_score(both.cx_gold.astype(int), proxy_num, weights="quadratic")
    print(f"complexité : {len(both)} questions annotées {both.cx_gold.value_counts().sort_index().to_dict()} "
          f"| kappa pondéré proxy vs annotation = {k:.2f}")
else:
    df["cx_gold"] = np.nan

# échantillon à annoter par deux personnes (stratifié domaine x tertile)
pool = df[df.train_eligible]
sample = (pool.groupby(["y_domain_grp", "cx_proxy"], group_keys=False)
              .apply(lambda g: g.sample(min(len(g), 6), random_state=SEED)))
if len(sample) < 120:
    rest = pool.drop(sample.index).sample(120 - len(sample), random_state=SEED)
    sample = pd.concat([sample, rest])
ann = sample[["id", "link_fr", "y_domain_grp", "x_stem_choices"]].copy()
ann["annotateur_1"] = ""
ann["annotateur_2"] = ""
ann["commentaire"] = ""
ann.sample(frac=1, random_state=SEED).to_csv(REPORTS / "annotation_complexite.csv", index=False, encoding="utf-8-sig")

keep = ["id", "train_eligible", "exclude_reason", "label_source", "label_corrected", "label_correction_rule", "y_domain", "y_domain_grp", "y_sub", "y_sub_grp",
        "dom_base", "sub_base", "dom_plat", "sub_plat", "level_min", "level_max", "lvl_general"] + \
       [c for c in df.columns if c.startswith("lvl_") and c != "lvl_general"] + \
       [c for c in df.columns if c.startswith("f_")] + ["cx_proxy_score", "cx_proxy", "cx_gold", "has_image", "in_iterations"]
save(df[keep], "targets")

maps = {
    "domain": {c: tax[tax.dom_code == c].domaine_fr.iloc[0] for c in sorted(df.y_domain.dropna().unique(), key=int)},
    "domain_grp": sorted(df.y_domain_grp.dropna().unique(), key=lambda c: (c == "AUTRE", c)),
    "sub_grp": sorted(df.y_sub_grp.dropna().unique(), key=lambda c: (c == "AUTRE", c)),
    "sub_names": tax.set_index("code").sous_domaine_fr.to_dict(),
    "level_year": YEAR_NAME,
    "rare_domains_merged": sorted(rare_dom),
}
(PROCESSED / "label_maps.json").write_text(json.dumps(maps, ensure_ascii=False, indent=2), encoding="utf-8")

e = df[df.train_eligible]
print("exclusions :", df.exclude_reason.replace("", "—").value_counts().to_dict())
print(f"éligibles : {len(e)}")
print("y_domain_grp :", e.y_domain_grp.value_counts().to_dict())
print(f"y_sub : {e.y_sub.nunique()} classes -> y_sub_grp : {e.y_sub_grp.nunique()} classes")
print("y_sub_grp :", e.y_sub_grp.value_counts().to_dict())
lv = e[e.in_iterations]
print(f"niveaux : {len(lv)} questions éligibles")
print("level_min :", lv.level_min.map(YEAR_NAME).value_counts().to_dict())
print("level_max :", lv.level_max.map(YEAR_NAME).value_counts().to_dict())
print("intervalles (min, max) :", lv.groupby(["level_min", "level_max"]).size().rename(lambda x: x).to_dict())
print("cx_proxy x domaine :\n", pd.crosstab(e.y_domain_grp, e.cx_proxy))
print("annotation : ", len(ann), "questions ->", REPORTS / "annotation_complexite.csv")
