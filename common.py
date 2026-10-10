"""Constantes, chemins et fonctions partagées par toutes les étapes du pipeline MEJ."""
from __future__ import annotations
import os
import re
from pathlib import Path

import pandas as pd

# --------------------------------------------------------------------------- chemins
PREP = Path(__file__).resolve().parent          # racine du dépôt (dossier prep/)
INTERIM = PREP / "data" / "interim"
PROCESSED = PREP / "data" / "processed"
REPORTS = PREP / "reports"
FIGURES = REPORTS / "figures"
for d in (INTERIM, PROCESSED, REPORTS, FIGURES):
    d.mkdir(parents=True, exist_ok=True)

# Fichiers bruts MEJ (non versionnés) : variable MEJ_RAW_DIR, sinon data/raw/, sinon le dossier parent (Patrice/)
FULL_NAME = "full database - questions - été 2024ish(Full_database).csv"
_candidates = ([Path(os.environ["MEJ_RAW_DIR"]).expanduser()] if os.environ.get("MEJ_RAW_DIR") else []) + \
              [PREP / "data" / "raw", PREP.parent]
RAW_DIR = next((p for p in _candidates if (p / FULL_NAME).exists()), PREP / "data" / "raw")
ROOT = RAW_DIR

RAW_FULL = RAW_DIR / FULL_NAME
RAW_ITER = RAW_DIR / "Quesitons itérées - originales(Iterations_v2).csv"
RAW_TAXO = RAW_DIR / "Domaines et sous-domaines - juin 2024(Feuil1).csv"
RAW_XLSX = RAW_DIR / "questions_generees_fr.xlsx"
RAW_BILI = RAW_DIR / "questions_mathematiques_bilingues.csv"
RAW_PDF_PRIM = RAW_DIR / "Description niveaux primaire.pdf"
RAW_PDF_SEC = RAW_DIR / "Descriptions des niveaux - secondaire.pdf"

# --------------------------------------------------------------------------- paramètres
SEED = 42
TEST_SIZE = 0.15          # part du corpus gelée pour le test final
N_FOLDS = 5               # validation croisée sur le reste
MIN_CLASS_COUNT = 10      # en dessous, une classe est regroupée (voir étape 5)
DEDUP_THRESHOLD = 0.85    # cosinus (n-grammes de caractères) : 0.85 regroupe aussi les questions qui partagent un même scénario
LABEL_SOURCE = "base"     # "base" (final_* de Full_database) ou "plateforme" (group_id / keyword_id) — décision D1 : "base" (voir docs/DECISIONS.md)

# Niveaux dans l'ordre du cursus québécois (index = rang ordinal)
LEVELS = [
    "1e année primaire", "2e année primaire", "3e année primaire",
    "4e année primaire", "5e année primaire", "6e année primaire",
    "1e année secondaire", "2e année secondaire", "3e année secondaire",
    "4e année secondaire - CST", "4e année secondaire - TS", "4e année secondaire - SN",
    "5e année secondaire - CST", "5e année secondaire - TS", "5e année secondaire - SN",
    "Cégep 1", "Cégep 2",
]
LEVEL_RANK = {lvl: i for i, lvl in enumerate(LEVELS)}
# rang « scolaire » commun aux 3 séquences de Sec 4 et Sec 5 (pour min/max ordinaux)
LEVEL_YEAR = {lvl: (i if i < 9 else (9 if lvl.startswith("4e") else 10 if lvl.startswith("5e") else 11))
              for i, lvl in enumerate(LEVELS)}
META_LEVEL = "niveau général"

# --------------------------------------------------------------------------- utilitaires
def read_semicolon_csv(path: Path) -> pd.DataFrame:
    """CSV exportés d'Excel : UTF-8 avec BOM, séparateur ';', champs multilignes entre guillemets."""
    return pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=True)


def norm_code(x) -> str | None:
    """'3', '3.0', 3.0 -> '3' ; '3.10' reste '3.10' ; '3.1 ' -> '3.1'. Les codes sont des chaînes, jamais des floats."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip()
    if not s or s.lower() == "nan":
        return None
    if re.fullmatch(r"\d+\.0", s):
        return s[:-2]
    return s


def norm_ws(s) -> str:
    return re.sub(r"\s+", " ", str(s)).strip() if isinstance(s, str) else ""


_SECTION_RE = re.compile(r"^(QUESTION|ANSWER #\d+|FEEDBACK)\s*$", re.M)


def split_sections(text: str) -> dict:
    """Découpe un énoncé 'QUESTION / ANSWER #k / FEEDBACK' en {stem, choices[], feedback}."""
    out = {"stem": "", "choices": [], "feedback": ""}
    if not isinstance(text, str) or not text.strip():
        return out
    parts = _SECTION_RE.split(text.replace("\r\n", "\n"))
    # parts = [avant, TAG1, contenu1, TAG2, contenu2, ...]
    for tag, body in zip(parts[1::2], parts[2::2]):
        body = body.strip()
        if tag == "QUESTION":
            out["stem"] = body
        elif tag.startswith("ANSWER"):
            out["choices"].append(body)
        elif tag == "FEEDBACK":
            out["feedback"] = body
    return out


def save(df: pd.DataFrame, name: str, folder: Path = INTERIM) -> Path:
    """Sauvegarde en Parquet (types conservés) + CSV UTF-8 BOM (lisible dans Excel)."""
    p = folder / f"{name}.parquet"
    df.to_parquet(p, index=False)
    csv_df = df.copy()
    for c in csv_df.columns:
        if csv_df[c].map(lambda v: isinstance(v, (list, dict))).any():
            csv_df[c] = csv_df[c].map(lambda v: "|".join(map(str, v)) if isinstance(v, list) else v)
    csv_df.to_csv(folder / f"{name}.csv", index=False, encoding="utf-8-sig")
    return p


def load(name: str, folder: Path = INTERIM) -> pd.DataFrame:
    return pd.read_parquet(folder / f"{name}.parquet")

# Nombre négatif : signe moins collé au chiffre, précédé d'un début, d'un espace ou d'une ponctuation ouvrante
# (« 35 - 4 » est une soustraction, « -4 » ou « (-4) » est un négatif), ou vocabulaire explicite.
NEGATIVE_RE = re.compile(r"(?:^|(?<=[\s(\[{=,;:]))[-−–]\d|n[ée]gati[fv]|sous z[ée]ro|negative|below zero", re.I)
# Texte remplacé par un message d'erreur serveur lors de l'export (fichier introuvable)
ERROR_TEXT_RE = re.compile(r'"errno"\s*:|\(errno -?\d+\)|ENOENT')


def has_negative(text) -> bool:
    return bool(NEGATIVE_RE.search(text)) if isinstance(text, str) else False


def is_error_text(text) -> bool:
    return bool(ERROR_TEXT_RE.search(text)) if isinstance(text, str) else False
