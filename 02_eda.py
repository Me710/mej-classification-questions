"""Étape 2 — Analyse exploratoire. Sorties : reports/eda_*.csv, reports/figures/*.png, reports/eda_summary.txt"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from common import FIGURES, LEVELS, LEVEL_YEAR, META_LEVEL, REPORTS, load, split_sections

m = load("master_raw")
tax = load("taxonomy")
dom_name = tax.drop_duplicates("dom_code").set_index("dom_code").domaine_fr.to_dict()
sub_name = tax.set_index("code").sous_domaine_fr.to_dict()
lines = []
def say(*a):
    s = " ".join(str(x) for x in a); print(s); lines.append(s)

# ---------------------------------------------------------------- texte et longueurs
text = m.text_fr_raw.fillna(m.text_en_raw)
parts = text.map(split_sections)
m["stem_words"] = parts.map(lambda p: len(p["stem"].split()))
m["n_choices"] = parts.map(lambda p: len(p["choices"]))
m["has_latex"] = text.str.contains(r"\\\(|\\\[", regex=True)
say("== Texte")
say("mots dans l'énoncé (stem) :", m.stem_words.describe().round(1).to_dict())
say("questions avec LaTeX :", f"{m.has_latex.mean():.1%}")
say("nombre de choix :", m.n_choices.value_counts().sort_index().to_dict())
say("position de la bonne réponse (brut) :", m.correct_pos.value_counts().sort_index().to_dict())

# ---------------------------------------------------------------- domaines / sous-domaines
say("\n== Domaines (base Full_database)")
d = (m.groupby("dom_base", dropna=False)
       .agg(n=("id", "size"), image=("has_image", "mean"), mots=("stem_words", "median"),
            fr=("text_fr_raw", lambda s: s.notna().mean())).reset_index())
d["domaine"] = d.dom_base.map(dom_name)
d["part"] = d.n / d.n.sum()
d = d.sort_values("n", ascending=False)
d.to_csv(REPORTS / "eda_domaines.csv", index=False, encoding="utf-8-sig")
say(d[["dom_base", "domaine", "n", "part", "image", "mots", "fr"]].round(2).to_string(index=False))
missing = sorted(set(tax.dom_code) - set(m.dom_base.dropna()))
say("domaines absents :", [f"{c} {dom_name[c]}" for c in missing])

s = (m.sub_base.value_counts().rename_axis("code").reset_index(name="n")
       .sort_values(["n", "code"], ascending=[False, True], kind="mergesort"))   # ordre déterministe
s["sous_domaine"] = s.code.map(sub_name)
s.to_csv(REPORTS / "eda_sous_domaines.csv", index=False, encoding="utf-8-sig")
say("\n== Sous-domaines :", len(s), "utilisés sur", len(tax),
    "| < 5 ex. :", (s.n < 5).sum(), "| < 10 ex. :", (s.n < 10).sum(), "| ≥ 30 ex. :", (s.n >= 30).sum())
incoh = m[m.sub_base.notna() & m.dom_base.notna() & (m.sub_base.str.split(".").str[0] != m.dom_base)]
say("sous-domaine incohérent avec son domaine (2024) :", len(incoh), incoh.id.tolist()[:10])

# ---------------------------------------------------------------- niveaux
say("\n== Niveaux (Iterations, 328 questions)")
lv = m[m.in_iterations].copy()
counts = pd.Series([x for l in lv.levels for x in l]).value_counts()
lvl = pd.DataFrame({"niveau": LEVELS + [META_LEVEL]})
lvl["n"] = lvl.niveau.map(counts).fillna(0).astype(int)
lvl.to_csv(REPORTS / "eda_niveaux.csv", index=False, encoding="utf-8-sig")
say(lvl.to_string(index=False))
lv["k"] = lv.levels.map(lambda l: len([x for x in l if x != META_LEVEL]))
lv["general"] = lv.levels.map(lambda l: META_LEVEL in l)
def contiguous(l):
    yrs = sorted({LEVEL_YEAR[x] for x in l if x != META_LEVEL})
    return bool(yrs) and yrs == list(range(yrs[0], yrs[-1] + 1))
lv["contigu"] = lv.levels.map(contiguous)
say("niveaux par question (hors 'niveau général') :", lv.k.describe().round(2).to_dict())
say("avec 'niveau général' :", f"{lv.general.mean():.1%}", "| ensembles contigus :", f"{lv.contigu.mean():.1%}")
say("combinaisons distinctes :", lv.levels.map(lambda l: tuple(sorted(l))).nunique())

# ---------------------------------------------------------------- types et images
say("\n== Types de question x domaine")
say(pd.crosstab(m.dom_base, m.qtype.fillna("?")).to_string())
say("\n== Image x domaine (part avec image)")
say(m.groupby("dom_base").has_image.mean().round(2).to_dict())

(REPORTS / "eda_summary.txt").write_text("\n".join(lines), encoding="utf-8")

# ---------------------------------------------------------------- figures
fig, ax = plt.subplots(figsize=(8, 4))
dd = d.dropna(subset=["dom_base"]).sort_values("n")
ax.barh(dd.domaine, dd.n, color="#4a6fa5"); ax.set_xlabel("questions"); ax.set_title("Questions par domaine (base Full_database)")
for y, v in enumerate(dd.n): ax.text(v + 3, y, str(v), va="center", fontsize=8)
fig.tight_layout(); fig.savefig(FIGURES / "domaines.png", dpi=150); plt.close(fig)

fig, ax = plt.subplots(figsize=(8, 4))
ll = lvl[lvl.n > 0]
ax.bar(range(len(ll)), ll.n, color="#4a6fa5"); ax.set_xticks(range(len(ll))); ax.set_xticklabels(ll.niveau, rotation=60, ha="right", fontsize=7)
ax.set_title("Questions disponibles par niveau (multi-étiquette)"); fig.tight_layout(); fig.savefig(FIGURES / "niveaux.png", dpi=150); plt.close(fig)

fig, ax = plt.subplots(figsize=(8, 4))
ax.hist(m.stem_words, bins=40, color="#4a6fa5"); ax.set_xlabel("mots dans l'énoncé"); ax.set_title("Longueur des énoncés")
fig.tight_layout(); fig.savefig(FIGURES / "longueurs.png", dpi=150); plt.close(fig)
