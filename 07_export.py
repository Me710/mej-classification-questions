"""Étape 7 — Exports prêts à l'emploi, un par famille de modèles.

processed/questions_master.(parquet|csv)  table maîtresse complète (1 ligne = 1 question, tout est traçable)
processed/tfidf/{train,test}.csv          baseline TF-IDF + régression logistique
processed/hf/{train,test}.jsonl           CamemBERT / XLM-R (+ augment_train.jsonl, label2id.json)
processed/llm/                            prompt système, test, réservoir few-shot, schéma de sortie
processed/review/review_queue.csv         file de revue humaine initiale (axe Validation)
processed/ood/xlsx_niveaux.jsonl          test hors distribution (questions synthétiques, Sec 1 à Sec 5)
"""
import json

import pandas as pd

from common import LEVEL_YEAR, PROCESSED, RAW_XLSX, REPORTS, SEED, load, save

m = load("master_raw")
t = load("text_clean")
tg = load("targets")
sp = load("splits")
audit = pd.read_csv(REPORTS / "label_audit.csv", encoding="utf-8-sig")
desc = json.loads((PROCESSED.parent / "interim" / "level_descriptions.json").read_text(encoding="utf-8"))
maps = json.loads((PROCESSED / "label_maps.json").read_text(encoding="utf-8"))
tax = load("taxonomy")

flag_cols = [c for c in audit.columns if c.startswith("flag_")] + ["n_flags"]
master = (m[["id", "link_fr", "has_image", "qtype", "text_fr_source", "text_en_source", "exact_fr", "exact_en",
             "group_id", "keyword_id", "levels"]]
          .merge(t.drop(columns=["llm_text_fr", "llm_text_en"]), on="id")
          .merge(tg.drop(columns=["has_image"]), on="id")
          .merge(sp, on="id")
          .merge(audit[["id"] + flag_cols], on="id"))
save(master, "questions_master", PROCESSED)

lvl_cols = [c for c in master.columns if c.startswith("lvl_") and c != "lvl_general"]
dom2id = {c: i for i, c in enumerate(maps["domain_grp"])}
sub2id = {c: i for i, c in enumerate(maps["sub_grp"])}
use = master[master.split.isin(["train", "test"])].copy()

# ---------------------------------------------------------------- TF-IDF
(PROCESSED / "tfidf").mkdir(exist_ok=True)
tf_cols = ["id", "fold", "text_lang", "x_stem", "x_stem_choices", "x_full", "has_image", "f_qtype",
           "y_domain_grp", "y_sub_grp", "level_min", "level_max", "lvl_general"] + lvl_cols
for s in ("train", "test"):
    use[use.split == s][tf_cols].to_csv(PROCESSED / "tfidf" / f"{s}.csv", index=False, encoding="utf-8-sig")

# ---------------------------------------------------------------- Transformers (JSONL)
(PROCESSED / "hf").mkdir(exist_ok=True)
def rec(r, text):
    return {"id": int(r.id), "fold": int(r.fold), "text": text, "lang": r.text_lang,
            "has_image": bool(r.has_image),
            "label_domain": dom2id[r.y_domain_grp], "label_sub": sub2id[r.y_sub_grp],
            "level_min": None if pd.isna(r.level_min) else int(r.level_min),
            "level_max": None if pd.isna(r.level_max) else int(r.level_max),
            "levels_multi_hot": None if pd.isna(r.level_min) else [int(bool(getattr(r, c))) for c in lvl_cols]}
for s in ("train", "test"):
    with open(PROCESSED / "hf" / f"{s}.jsonl", "w", encoding="utf-8") as f:
        for r in use[use.split == s].itertuples():
            f.write(json.dumps(rec(r, r.x_stem_choices), ensure_ascii=False) + "\n")

var = load("variations").merge(use[["id", "split"]], on="id")
var = var[var.split == "train"]                       # JAMAIS de variantes de questions de test
n_aug = 0
with open(PROCESSED / "hf" / "augment_train.jsonl", "w", encoding="utf-8") as f:
    src = use.set_index("id")
    for v in var.itertuples():
        r = src.loc[v.id]
        d = rec(r.rename(None).to_frame().T.assign(id=v.id).itertuples().__next__(), v.x_stem_choices)
        d.update({"lang": v.lang, "variation": int(v.var_k), "source_id": int(v.id)})
        f.write(json.dumps(d, ensure_ascii=False) + "\n"); n_aug += 1
(PROCESSED / "hf" / "label2id.json").write_text(json.dumps(
    {"domain": dom2id, "sub": sub2id, "level_columns": lvl_cols, "level_year": maps["level_year"]},
    ensure_ascii=False, indent=2), encoding="utf-8")

# ---------------------------------------------------------------- LLM
llm = PROCESSED / "llm"; llm.mkdir(exist_ok=True)
taxo_lines = []
for d, g in tax.groupby("dom_code", sort=False):
    taxo_lines.append(f"{d}. {g.domaine_fr.iloc[0]}")
    taxo_lines += [f"   {r.code} {r.sous_domaine_fr}" for r in g.itertuples()]
schema = {"type": "object", "required": ["domaine", "sous_domaine", "niveau_min", "niveau_max", "complexite", "justification"],
          "properties": {"domaine": {"type": "string", "description": "code du domaine, ex. '5'"},
                         "sous_domaine": {"type": "string", "description": "code du sous-domaine, ex. '5.3'"},
                         "niveau_min": {"type": "string", "enum": list(desc.keys())},
                         "niveau_max": {"type": "string", "enum": list(desc.keys())},
                         "complexite": {"type": "integer", "enum": [1, 2, 3]},
                         "justification": {"type": "string", "description": "2 phrases maximum"}}}
system = (
    "Tu es conseiller pédagogique en mathématiques au Québec. Tu classes des questions de la plateforme Math en Jeu.\n\n"
    "## Taxonomie (choisis exactement un domaine et un sous-domaine de ce domaine)\n" + "\n".join(taxo_lines) +
    "\n\n## Niveaux scolaires (choisis l'intervalle [niveau_min, niveau_max] où la question est appropriée)\n" +
    "\n".join(f"- {k} : {v}" for k, v in desc.items()) +
    "\n\n## Complexité\n1 = une notion, une opération, données explicites ; 2 = 2 ou 3 étapes ou une représentation "
    "intermédiaire ; 3 = plusieurs notions combinées ou modélisation d'une situation.\n\n"
    "Certaines questions s'appuient sur une image que tu ne vois pas : raisonne sur le texte disponible.\n"
    "Réponds UNIQUEMENT par un objet JSON conforme au schéma fourni.")
(llm / "system_prompt_fr.txt").write_text(system, encoding="utf-8")
(llm / "output_schema.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
raw = m.set_index("id")
def user_msg(i):
    txt = raw.loc[i, "text_fr_raw"] if isinstance(raw.loc[i, "text_fr_raw"], str) else raw.loc[i, "text_en_raw"]
    img = " (cette question est accompagnée d'une image)" if raw.loc[i, "has_image"] else ""
    return f"Question{img} :\n{txt}"
with open(llm / "test.jsonl", "w", encoding="utf-8") as f:
    for r in use[use.split == "test"].itertuples():
        f.write(json.dumps({"id": int(r.id), "user": user_msg(r.id)}, ensure_ascii=False) + "\n")
clean_train = use[(use.split == "train") & (use.n_flags == 0)]
pool = clean_train.groupby("y_sub_grp", group_keys=False).apply(lambda g: g.sample(min(2, len(g)), random_state=SEED))
with open(llm / "fewshot_pool.jsonl", "w", encoding="utf-8") as f:
    for r in pool.itertuples():
        f.write(json.dumps({"id": int(r.id), "user": user_msg(r.id),
                            "assistant": {"domaine": r.y_domain, "sous_domaine": r.y_sub}}, ensure_ascii=False) + "\n")

# ---------------------------------------------------------------- file de revue initiale
(PROCESSED / "review").mkdir(exist_ok=True)
rq = master[master.n_flags > 0].copy()
rq["signaux"] = rq[[c for c in flag_cols if c != "n_flags"]].apply(lambda r: ", ".join(c[5:] for c, v in r.items() if v), axis=1)
rq = rq.sort_values(["n_flags", "dup_cluster"], ascending=[False, True])
rq[["id", "link_fr", "n_flags", "signaux", "dom_base", "sub_base", "dom_plat", "sub_plat", "dup_cluster",
    "split", "x_stem_choices"]].assign(decision="", sous_domaine_corrige="", commentaire="") \
  .to_csv(PROCESSED / "review" / "review_queue.csv", index=False, encoding="utf-8-sig")

# ---------------------------------------------------------------- test hors distribution (décision D5)
XLSX_LEVEL = {"1ère année": "1e année primaire", "2e année": "2e année primaire", "3e année": "3e année primaire",
              "4e année": "4e année primaire", "5e année": "5e année primaire", "6e année": "6e année primaire",
              "Sec. 1": "1e année secondaire", "Sec. 2": "2e année secondaire", "Sec. 3": "3e année secondaire",
              "CST4": "4e année secondaire - CST", "TS4": "4e année secondaire - TS", "SN4": "4e année secondaire - SN",
              "CST5": "5e année secondaire - CST", "TS5": "5e année secondaire - TS", "SN5": "5e année secondaire - SN"}
(PROCESSED / "ood").mkdir(exist_ok=True)
x = pd.read_excel(RAW_XLSX, dtype=str)
x = x[x["Réponse Correcte"].isin(list("ABCD"))].copy()          # retire les 9 lignes décalées par « | »
x["niveau"] = x.Niveau.map(XLSX_LEVEL)
assert x.niveau.notna().all(), "niveau xlsx non reconnu"
n_ood = 0
with open(PROCESSED / "ood" / "xlsx_niveaux.jsonl", "w", encoding="utf-8") as f:
    for i, r in x.iterrows():
        opts = [r[f"Option {k}"] for k in "ABCD"]
        f.write(json.dumps({"ood_id": int(i), "niveau": r.niveau, "level_year": LEVEL_YEAR[r.niveau], "matiere": r["Matière"],
                            "text": f"{r.Question} [CHOIX] " + " ; ".join(map(str, opts)),
                            "user": "Question :\nQUESTION\n" + r.Question + "\n" +
                                    "\n".join(f"ANSWER #{k + 1}\n{o}" for k, o in enumerate(opts))}, ensure_ascii=False) + "\n")
        n_ood += 1

print(f"master : {len(master)} lignes x {master.shape[1]} colonnes")
print(f"ood : {n_ood} questions synthétiques ({x.niveau.nunique()} niveaux)")
print(f"tfidf : train {(use.split == 'train').sum()}, test {(use.split == 'test').sum()}")
print(f"hf : augment_train {n_aug} variantes (questions de train uniquement)")
print(f"llm : prompt système {len(system)} caractères, test {(use.split == 'test').sum()}, few-shot {len(pool)}")
print(f"revue : {len(rq)} questions signalées")
