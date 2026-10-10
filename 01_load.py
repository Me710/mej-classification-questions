"""Étape 1 — Chargement sans perte et fusion des sources en une table maîtresse brute.

Sorties : data/interim/taxonomy.parquet, level_descriptions.json, master_raw.parquet (+ .csv)
"""
import ast
import json
import re

import pandas as pd

from common import (INTERIM, LEVELS, META_LEVEL, RAW_FULL, RAW_ITER, RAW_PDF_PRIM, RAW_PDF_SEC,
                    RAW_TAXO, is_error_text, norm_code, read_semicolon_csv, save)


# ------------------------------------------------------------------ 1. taxonomie
def load_taxonomy() -> pd.DataFrame:
    raw = pd.read_csv(RAW_TAXO, sep="\t", encoding="utf-8-sig", header=None, dtype=str,
                      names=["num", "domaine", "code", "sous_domaine"])
    split_at = raw.index[raw["num"].fillna("").str.strip() == "ANGLAIS"][0]
    rows = []
    for lang, block in (("fr", raw.iloc[:split_at]), ("en", raw.iloc[split_at + 1:])):
        block = block.dropna(subset=["code"])
        block = block[block["code"].str.match(r"^\d+\.\d+$")]
        for r in block.itertuples():
            rows.append({"lang": lang, "code": r.code.strip(), "domaine": r.domaine.strip(),
                         "sous_domaine": re.sub(r"\s+", " ", r.sous_domaine).strip()})
    tax = pd.DataFrame(rows)
    # Correctif : en FR, « Angles » porte le code 4.2 (doublon de « Temps ») ; l'anglais dit 4.3.
    mask = (tax.lang == "fr") & tax.sous_domaine.str.startswith("Angles")
    tax.loc[mask, "code"] = "4.3"
    tax["dom_code"] = tax.code.str.split(".").str[0]
    assert not tax.duplicated(["lang", "code"]).any(), "codes en double dans la taxonomie"
    wide = (tax.pivot(index="code", columns="lang", values=["domaine", "sous_domaine"]))
    wide.columns = [f"{a}_{b}" for a, b in wide.columns]
    wide = wide.reset_index()
    wide["dom_code"] = wide.code.str.split(".").str[0]
    wide = wide.sort_values("code", key=lambda s: s.map(lambda c: tuple(int(x) for x in c.split("."))))
    return wide.reset_index(drop=True)


# ------------------------------------------------------------------ 2. descriptions des niveaux (PDF)
PDF_HEADINGS = {
    r"1(?:ère|re|e) année": "1e année primaire", r"2(?:ème|e) année": "2e année primaire",
    r"3(?:ème|e) année": "3e année primaire", r"4(?:ème|e) année": "4e année primaire",
    r"5(?:ème|e) année": "5e année primaire", r"6(?:ème|e) année": "6e année primaire",
    r"Secondaire 1": "1e année secondaire", r"Secondaire 2": "2e année secondaire",
    r"Secondaire 3": "3e année secondaire",
    r"CST4": "4e année secondaire - CST", r"TS4": "4e année secondaire - TS", r"SN4": "4e année secondaire - SN",
    r"CST5": "5e année secondaire - CST", r"TS5": "5e année secondaire - TS", r"SN5": "5e année secondaire - SN",
}


def pdf_text(path) -> str:
    try:
        from pypdf import PdfReader
        return "\n".join(p.extract_text() or "" for p in PdfReader(str(path)).pages)
    except Exception:  # repli : poppler
        import subprocess
        return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True).stdout


def load_level_descriptions() -> dict:
    text = re.sub(r"\s+", " ", pdf_text(RAW_PDF_PRIM) + " " + pdf_text(RAW_PDF_SEC))
    pattern = "|".join(f"(?P<g{i}>{h})" for i, h in enumerate(PDF_HEADINGS))
    hits = list(re.finditer(rf"(?:{pattern})(?: \([^)]*\))? ?:", text))
    names = list(PDF_HEADINGS.values())
    out = {}
    for k, m in enumerate(hits):
        gi = next(int(g[1:]) for g, v in m.groupdict().items() if v)
        end = hits[k + 1].start() if k + 1 < len(hits) else len(text)
        out[names[gi]] = text[m.end():end].strip()
    missing = [n for n in names if n not in out]
    if missing:
        print("  ⚠ niveaux sans description :", missing)
    return out


# ------------------------------------------------------------------ 3. infos perdues par la regex
def raw_meta(raw: str) -> dict:
    if not isinstance(raw, str):
        return {"qtype": None, "n_choices_raw": None, "correct_pos": None}
    qtype = re.search(r"type=(\w+)", raw)
    flags = [int(x) for x in re.findall(r"isRight=(\d)", raw)]
    return {"qtype": qtype.group(1) if qtype else None,
            "n_choices_raw": len(flags),
            "correct_pos": flags.index(1) + 1 if 1 in flags else None}


def main():
    tax = load_taxonomy()
    save(tax, "taxonomy")
    desc = load_level_descriptions()
    (INTERIM / "level_descriptions.json").write_text(json.dumps(desc, ensure_ascii=False, indent=2), encoding="utf-8")

    full = read_semicolon_csv(RAW_FULL).rename(columns={"e": "id"})
    it = read_semicolon_csv(RAW_ITER).rename(columns={"question_id": "id"})
    assert full.id.is_unique and it.id.is_unique
    assert set(it.id) <= set(full.id), "Iterations contient des id absents de la base"

    # libellés plateforme -> codes (keyword_id est tronqué à 64 caractères dans l'export)
    fr = tax.dropna(subset=["sous_domaine_fr"])
    lookup = {(r.domaine_fr, r.sous_domaine_fr[:60]): r.code for r in fr.itertuples()}
    dom_lookup = {r.domaine_fr: r.dom_code for r in fr.itertuples()}
    it["sub_plat"] = [lookup.get((g.strip(), re.sub(r"\s+", " ", k).strip()[:60])) for g, k in zip(it.group_id, it.keyword_id)]
    it["dom_plat"] = it.group_id.str.strip().map(dom_lookup)
    it["levels"] = it.availability.map(ast.literal_eval)

    m = full.merge(it[["id", "availability", "levels", "group_id", "keyword_id", "dom_plat", "sub_plat",
                       "FR", "EN", "VARIATIONS_FR", "VARIATIONS"]], on="id", how="left")
    # textes remplacés par un message d'erreur serveur (ENOENT) : traités comme manquants
    err_ids = set()
    for col in ("Enonce_regex_FR", "Enonce_regex_EN", "FR", "EN", "Enonce_FR", "Enonce_EN"):
        bad = m[col].map(is_error_text)
        err_ids |= set(m.loc[bad, "id"])
        m.loc[bad, col] = None
    meta = m["Enonce_FR"].fillna(m["Enonce_EN"]).map(raw_meta).apply(pd.Series)  # EN brut en repli

    master = pd.DataFrame({
        "id": m.id.astype(int),
        "link_fr": m["LIEN FR"],
        "has_image": m.IMAGE.eq("Oui"),
        # texte : la base d'abord, Iterations en complément
        "text_fr_raw": m.Enonce_regex_FR.fillna(m.FR),
        "text_en_raw": m.Enonce_regex_EN.fillna(m.EN),
        "text_fr_source": m.Enonce_regex_FR.notna().map({True: "full", False: "iterations"}).where(m.Enonce_regex_FR.notna() | m.FR.notna()),
        "text_en_source": m.Enonce_regex_EN.notna().map({True: "full", False: "iterations"}).where(m.Enonce_regex_EN.notna() | m.EN.notna()),
        "qtype": meta.qtype, "n_choices_raw": meta.n_choices_raw, "correct_pos": meta.correct_pos,
        "exact_fr": m["exactitude FR"].map({"VRAI": True, "FAUX": False}),
        "exact_en": m["exactitude EN"].map({"VRAI": True, "FAUX": False}),
        # étiquettes : trois jeux, gardés côte à côte. final_* = étiquette FR, EN en repli (consolidation été 2024)
        "dom_base": m["final categorie"].map(norm_code),
        "sub_base": m["final sous_categorie"].map(norm_code),
        "dom_orig_fr": m["categorie FR num"].map(norm_code),
        "sub_orig_fr": m["sous_categorie FR num"].map(norm_code),
        "sub_orig_en": m["sous_categorie EN num"].map(norm_code),
        "dom_plat": m.dom_plat, "sub_plat": m.sub_plat,
        "group_id": m.group_id, "keyword_id": m.keyword_id,
        "levels": m.levels.map(lambda v: v if isinstance(v, list) else None),
        "variations_fr": m.VARIATIONS_FR, "variations_en": m.VARIATIONS,
    })
    master["in_iterations"] = master.levels.notna()
    master["had_error_text"] = master.id.astype(str).isin(err_ids)
    save(master, "master_raw")

    print(f"taxonomie : {tax.dom_code.nunique()} domaines, {len(tax)} sous-domaines")
    print(f"descriptions de niveaux : {len(desc)}/15")
    print(f"master_raw : {len(master)} questions, {master.in_iterations.sum()} avec niveaux")
    print("texte FR :", master.text_fr_source.value_counts(dropna=False).to_dict())
    print("texte EN :", master.text_en_source.value_counts(dropna=False).to_dict())
    print("types :", master.qtype.value_counts(dropna=False).to_dict())
    print("textes d'erreur serveur retirés (ENOENT) :", sorted(int(i) for i in err_ids))


if __name__ == "__main__":
    main()
