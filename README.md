# Classification des questions Math en Jeu — préparation des données

Pipeline reproductible qui transforme la banque de questions [Math en Jeu](https://mathenjeu.ca) (981 questions de mathématiques, FR/EN, de la 1re année du primaire à Sec 5) en jeux d'entraînement **propres, audités et sans fuite**. Il sert à prédire trois étiquettes :

- le **domaine et le sous-domaine** (taxonomie de 10 domaines et 59 sous-domaines) ;
- le **niveau scolaire**, sous forme d'intervalle [niveau min, niveau max] ;
- la **complexité** (grille à 3 niveaux).

Il prépare les quatre axes du plan : baseline TF-IDF, transformeur, LLM, validation humaine.

## Démarrage rapide

```bash
pip install -r requirements.txt
# déposer les fichiers bruts MEJ dans data/raw/ (voir data/raw/README.md)
./run_all.sh          # étapes 01 à 08, environ 1 minute
```

## Le plan, colonne « fichiers et champs » remplie

| Axe | Fichiers fusionnés (clé) | Colonnes / exports | Modèle |
|---|---|---|---|
| 1. Vérification, baseline | Full_database ⟗ Iterations_v2 (`e` = `question_id`) + taxonomie | `x_stem_choices` → `y_domain_grp`, `y_sub_grp`, `level_min`, `level_max` ; `data/processed/tfidf/` | TF-IDF (mots 1–2 + caractères 2–5) + régression logistique |
| 2. Classification avancée | Même table + variantes LLM (train uniquement) | `data/processed/hf/*.jsonl`, `label2id.json` | XLM-R base (principal), CamemBERT |
| 3. Comparaison LLM | Test + taxonomie + descriptions officielles des niveaux | `data/processed/llm/` (prompt système, schéma JSON, few-shot) | `gpt-4o-2024-08-06`, zero-shot et few-shot |
| 4. Validation | Prédictions hors pli ⟗ étiquettes MEJ ⟗ signaux d'audit | `data/processed/review/review_queue.csv` → `data/label_corrections.csv` | Revue humaine |

## Pipeline

| Script | Rôle | Sorties |
|---|---|---|
| `01_load.py` | Chargement sans perte, fusion, retrait des textes corrompus | `data/interim/master_raw` |
| `02_eda.py` | Analyse exploratoire | `reports/eda_*`, `reports/figures/` |
| `03_audit_labels.py` | Audit des étiquettes, quasi-doublons, contrôle programme | `reports/label_audit.csv`, `reports/audit_summary.txt` |
| `04_clean_text.py` | Énoncé / choix / explication, LaTeX → texte, variantes | `data/interim/text_clean`, `variations` |
| `04b_resolve_labels.py` | Corrections par règle de convention (naturels / entiers) | `data/label_corrections_auto.csv` |
| `05_build_targets.py` | Cibles, variables, complexité de référence | `data/interim/targets` |
| `06_split.py` | Train / test + 5 plis, groupés par famille de quasi-doublons | `data/interim/splits` |
| `07_export.py` | Exports par modèle, test hors distribution, file de revue | `data/processed/` |
| `08_smoke_baseline.py` | Baseline de contrôle en validation croisée | `reports/smoke_baseline.csv` |

Paramètres dans `common.py` : `LABEL_SOURCE`, `MIN_CLASS_COUNT` (10), `DEDUP_THRESHOLD` (0,85), `TEST_SIZE` (0,15), `N_FOLDS` (5), `SEED` (42).

## Ce que l'audit a révélé

- **Convention naturels / entiers.** 273 des 279 questions « Nombres entiers » ne contiennent aucun nombre négatif, et la plateforme n'emploie cette étiquette qu'une fois sur 326 questions. Elles sont recalées sur la définition du programme (décision D2).
- **41 % des questions** appartiennent à 108 familles de quasi-doublons (gabarits où seul un nombre change). Le découpage les garde dans une même partition.
- **Les ensembles de niveaux sont contigus à 100 %.** Le niveau se modélise donc en intervalle [min, max]. Rien n'est entraînable au-delà de Sec 1 (10 questions ou moins par niveau).
- **Le proxy textuel de complexité est faible** (κ = 0,22 contre l'annotation de référence) : la complexité est confiée au LLM et évaluée sur 120 questions annotées.
- 43 questions inexactes et 2 sans étiquette sont exclues. 4 textes étaient des messages d'erreur serveur.

## Données préparées

936 questions éligibles :

- test gelé de 125 questions, et 811 en train réparties en 5 plis ;
- domaine en 7 classes, sous-domaine en 17 classes ;
- niveau : 312 questions (270 en train, 42 en test) ;
- en plus : 1 533 variantes d'augmentation (train uniquement), 747 questions hors distribution (Sec 1 à Sec 5) et 414 questions dans la file de revue.

## Baseline de contrôle (5 plis, test non ouvert)

| Tâche | Avant corrections | Après corrections D2 |
|---|---|---|
| Domaine, macro-F1 | 0,646 | 0,669 |
| Sous-domaine, macro-F1 / exactitude | 0,576 / 0,646 | 0,636 / 0,757 |
| Niveau min, exactitude / erreur moyenne | 0,676 / 0,64 an | 0,669 / 0,65 an |
| Niveau max, exactitude / erreur moyenne | 0,560 / 0,68 an | 0,558 / 0,66 an |

Entrée `x_stem_choices` dans les deux cas. Le sous-domaine passe de 18 à 17 classes après correction ; détail dans `reports/smoke_baseline*.csv`.

## Documentation

- [`docs/DECISIONS.md`](docs/DECISIONS.md) : les 9 décisions de conception, leurs preuves et leurs sources.
- [`docs/GUIDE.md`](docs/GUIDE.md) : le guide complet d'analyse et de préparation, étape par étape.

## Données

Les fichiers Math en Jeu et les tables qui contiennent le texte des questions ne sont **pas versionnés** (`data/raw/`, `data/interim/`, `data/processed/`). Le dépôt contient le code, la documentation, les rapports agrégés, les corrections d'étiquettes et les annotations (identifiants et étiquettes seulement).
