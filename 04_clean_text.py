"""Étape 4 — Nettoyage et normalisation du texte.

Pour chaque question : énoncé / choix / explication séparés, LaTeX converti en texte lisible,
et trois variantes d'entrée (stem, stem+choix, stem+choix+explication).
Sorties : data/interim/text_clean.parquet, data/interim/variations.parquet
"""
import re

import pandas as pd

from common import load, norm_ws, save, split_sections

# ------------------------------------------------------------------ LaTeX -> texte
SIMPLE = {
    r"\times": " × ", r"\div": " ÷ ", r"\cdot": " · ", r"\pm": " ± ", r"\leq": " ≤ ", r"\geq": " ≥ ",
    r"\le": " ≤ ", r"\ge": " ≥ ", r"\neq": " ≠ ", r"\approx": " ≈ ", r"\pi": "π", r"\infty": "∞",
    r"\square": " □ ", r"\angle": "∠", r"\triangle": "△", r"\degree": "°", r"\circ": "°",
    r"\%": "%", r"\$": "$", r"\lt": " < ", r"\gt": " > ", r"\rightarrow": " → ", r"\Rightarrow": " ⇒ ",
    r"\ldots": "…", r"\dots": "…", r"\cdots": "…", r"\in": " ∈ ", r"\cup": " ∪ ", r"\cap": " ∩ ",
}
FRAC = re.compile(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
SQRT = re.compile(r"\\sqrt\s*\{([^{}]*)\}")
WRAP = re.compile(r"\\(?:mathbf|textbf|text|textrm|mathrm|mbox|overline|underline|boldsymbol|operatorname)\s*\{([^{}]*)\}")


def latex_to_text(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = re.sub(r"\\[()\[\]]", " ", s)                       # délimiteurs \( \) \[ \]
    for _ in range(4):                                       # fractions et racines imbriquées
        s = FRAC.sub(lambda m: f"{m.group(1).strip()}/{m.group(2).strip()}", s)
        s = SQRT.sub(lambda m: f"√({m.group(1).strip()})", s)
        s = WRAP.sub(lambda m: m.group(1), s)
    s = re.sub(r"\^\s*\{\\circ\}|\^\s*\\circ", "°", s)
    for k in sorted(SIMPLE, key=len, reverse=True):
        s = re.sub(re.escape(k) + r"(?![A-Za-z])", SIMPLE[k], s)
    s = re.sub(r"\\(?:left|right|bf|it|displaystyle|quad|qquad|,|;|!|:)", " ", s)
    s = re.sub(r"\^\{([^{}]*)\}", r"^\1", s)
    s = re.sub(r"_\{([^{}]*)\}", r"_\1", s)
    s = re.sub(r"\\([A-Za-z]+)", r"\1", s)                   # commande inconnue : garder son nom
    s = s.replace("\\ ", " ").replace("{", "").replace("}", "").replace("\\", " ")
    return norm_ws(s)


FEEDBACK_PREFIX = re.compile(
    r"^\s*(?:la\s+(?:bonne\s+r[ée]ponse|r[ée]ponse\s+correcte)\s+est|the\s+(?:right|correct)\s+answer\s+is)"
    r"\s*\(?[A-E]?\)?\s*:?\s*", re.I)


def build(parts: dict) -> dict:
    stem = latex_to_text(parts["stem"])
    choices = [latex_to_text(c) for c in parts["choices"]]
    fb = latex_to_text(FEEDBACK_PREFIX.sub("", parts["feedback"]))
    sc = stem + (" [CHOIX] " + " ; ".join(choices) if choices else "")
    return {"stem": stem, "choices": choices, "feedback": fb,
            "x_stem": stem, "x_stem_choices": sc, "x_full": sc + (" [EXPLICATION] " + fb if fb else "")}


def parse_variations(blob: str) -> list[dict]:
    if not isinstance(blob, str) or "VARIATION" not in blob:
        return []
    chunks = re.split(r"^\s*(?:#+\s*)?\**\s*VARIATION\s+(\d+)\s*\**\s*:?\s*$", blob.replace("\r\n", "\n"), flags=re.M)
    return [{"var_k": int(k), **build(split_sections(body))} for k, body in zip(chunks[1::2], chunks[2::2])]


def main():
    m = load("master_raw")
    rows = []
    for r in m.itertuples():
        fr = build(split_sections(r.text_fr_raw)) if isinstance(r.text_fr_raw, str) else None
        en = build(split_sections(r.text_en_raw)) if isinstance(r.text_en_raw, str) else None
        main_lang, best = ("fr", fr) if fr and fr["stem"] else ("en", en)
        if best is None:                       # aucun texte exploitable (ex. message d'erreur serveur)
            main_lang, best = None, build({"stem": "", "choices": [], "feedback": ""})
        rows.append({
            "id": r.id, "text_lang": main_lang,
            "stem_fr": fr["stem"] if fr else None, "choices_fr": fr["choices"] if fr else None,
            "feedback_fr": fr["feedback"] if fr else None,
            "stem_en": en["stem"] if en else None, "choices_en": en["choices"] if en else None,
            "feedback_en": en["feedback"] if en else None,
            # variantes d'entrée (langue principale = FR, EN en repli)
            "x_stem": best["x_stem"], "x_stem_choices": best["x_stem_choices"], "x_full": best["x_full"],
            "x_stem_choices_en": en["x_stem_choices"] if en else None,
            # version brute avec LaTeX, pour le LLM
            "llm_text_fr": r.text_fr_raw, "llm_text_en": r.text_en_raw,
        })
    t = pd.DataFrame(rows)
    save(t, "text_clean")

    var = []
    for r in m[m.in_iterations].itertuples():
        for lang, blob in (("fr", r.variations_fr), ("en", r.variations_en)):
            for v in parse_variations(blob):
                var.append({"id": r.id, "lang": lang, **v})
    v = pd.DataFrame(var)
    save(v, "variations")

    empty = t[t.x_stem.str.len() < 5]
    leftover = t.x_full.str.contains(r"\\[a-zA-Z]", regex=True).sum()
    print(f"text_clean : {len(t)} questions | langue principale {t.text_lang.value_counts().to_dict()}")
    print(f"énoncés vides ou < 5 caractères : {len(empty)} -> {empty.id.tolist()}")
    print(f"commandes LaTeX résiduelles : {leftover}")
    print(f"variations : {len(v)} lignes ({v.groupby('lang').size().to_dict()}), {v.id.nunique()} questions")
    ex = t[t.llm_text_fr.fillna('').str.contains(r'ANSWER #1\n\\\(\\frac')].iloc[0]
    print("\nexemple brut :", ex.llm_text_fr[:220].replace("\n", " "))
    print("exemple nettoyé :", ex.x_full[:220])


if __name__ == "__main__":
    main()
