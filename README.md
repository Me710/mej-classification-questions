# Classification des questions Math en Jeu

**Auditer, nettoyer et préparer les 981 questions de la plateforme [Math en Jeu](https://mathenjeu.ca) pour entraîner des modèles qui prédisent leur domaine, leur niveau scolaire et leur complexité.**

Le dépôt contient un pipeline reproductible en une commande, l'audit complet des étiquettes existantes, les décisions de conception justifiées, et des jeux de données prêts pour trois familles de modèles : TF-IDF, transformeurs et LLM.

---

## Par où commencer ?

| Vous êtes… | Vous voulez… | Lisez |
|---|---|---|
| **Responsable du projet** | Comprendre le contexte, les constats et les choix faits | [Analyse du contexte](docs/CONTEXTE.md), puis [Décisions](docs/DECISIONS.md) |
| **Data scientist** | Entraîner et évaluer les modèles | [Démarrage rapide](#démarrage-rapide), [Données produites](#données-produites), puis [Guide complet](docs/GUIDE.md) |
| **Réviseur ou annotateur** | Relire les étiquettes douteuses ou annoter la complexité | [Revue et annotation](docs/REVUE_ET_ANNOTATION.md) |
| **Développeur** | Modifier ou étendre le pipeline | [Pipeline](#pipeline), [Paramètres](#paramètres), [Reproductibilité](#reproductibilité) |

---

## Sommaire

- [Le projet en 30 secondes](#le-projet-en-30-secondes)
- [Démarrage rapide](#démarrage-rapide)
- [Structure du dépôt](#structure-du-dépôt)
- [Pipeline](#pipeline)
- [Données produites](#données-produites)
- [Résultats clés](#résultats-clés)
- [Décisions de conception](#décisions-de-conception)
- [Revue humaine et annotation](#revue-humaine-et-annotation)
- [Paramètres](#paramètres)
- [Reproductibilité](#reproductibilité)
- [Données et confidentialité](#données-et-confidentialité)
- [Feuille de route](#feuille-de-route)
- [FAQ](#faq)

---

## Le projet en 30 secondes

- **Les données :** 981 questions de mathématiques en français et en anglais, de la 1re année du primaire à Sec 5 (séquences CST, TS et SN), classées selon une taxonomie de 10 domaines et 59 sous-domaines.
- **Le problème :** les étiquettes sont incomplètes et parfois contradictoires.
  - Le niveau scolaire n'est connu que pour un tiers des questions.
  - Aucune étiquette de complexité n'existe.
  - Les deux sources d'étiquettes ne s'accordent qu'à 56 % sur le sous-domaine.
- **Le plan, en quatre axes :**

| Axe | Méthode | Rôle |
|---|---|---|
| 1. Vérification | TF-IDF + régression logistique | Modèle de référence (baseline) |
| 2. Classification avancée | XLM-R (CamemBERT en comparaison) | Exploiter le sens des questions |
| 3. Comparaison LLM | `gpt-4o-2024-08-06`, zero-shot et few-shot | Couvrir les niveaux du secondaire, absents des données |
| 4. Validation | Prédictions hors pli comparées aux étiquettes MEJ | Envoyer les divergences en revue humaine |

Le détail est dans l'[analyse du contexte](docs/CONTEXTE.md).

## Démarrage rapide

**Prérequis :** Python 3.10 à 3.13 et les fichiers bruts Math en Jeu, qui ne sont pas versionnés (voir [`data/raw/README.md`](data/raw/README.md)).

```bash
git clone https://github.com/Me710/mej-classification-questions.git
cd mej-classification-questions
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Fichiers bruts : les copier dans data/raw/, ou indiquer leur dossier
export MEJ_RAW_DIR=~/Documents/Patrice

./run_all.sh        # étapes 01 à 08, environ 1 minute
```

En fin d'exécution, `data/processed/` contient les jeux d'entraînement et `reports/` les rapports d'analyse et la baseline.

## Structure du dépôt

```text
mej-classification-questions/
├── README.md                    ← vous êtes ici
├── run_all.sh                   ← lance tout le pipeline
├── requirements.txt             ← versions exactes des dépendances
├── common.py                    ← chemins, paramètres, fonctions partagées
├── 01_load.py … 08_smoke_baseline.py, 04b_resolve_labels.py   ← étapes du pipeline
├── docs/
│   ├── CONTEXTE.md              ← analyse du contexte (commencer ici)
│   ├── DECISIONS.md             ← 9 décisions de conception, preuves et sources
│   ├── GUIDE.md                 ← guide complet, étape par étape
│   ├── REVUE_ET_ANNOTATION.md   ← consignes pour réviseurs et annotateurs
│   └── img/                     ← figures du guide
├── annotations/
│   └── complexite_annotateur1.csv     ← 120 questions annotées (id + niveau 1–3)
├── data/
│   ├── raw/                     ← fichiers MEJ (non versionnés)
│   ├── label_corrections_auto.csv     ← corrections automatiques (convention naturels / entiers)
│   ├── label_corrections.csv    ← corrections manuelles, à créer après la revue
│   ├── interim/                 ← tables de travail (générées, non versionnées)
│   └── processed/               ← jeux prêts à l'emploi (générés, non versionnés)
└── reports/                     ← analyses, audit, baseline, figures (versionnés)
```

## Pipeline

Chaque étape lit la sortie de la précédente. Aucune ne modifie les fichiers bruts.

| Étape | Script | Ce qu'elle fait | Sortie principale |
|---|---|---|---|
| 1 | `01_load.py` | Lecture sans perte, fusion des sources, retrait des textes corrompus | `data/interim/master_raw` |
| 2 | `02_eda.py` | Analyse exploratoire : distributions, longueurs, langues, images | `reports/eda_*`, `reports/figures/` |
| 3 | `03_audit_labels.py` | Audit des étiquettes, quasi-doublons, cohérence avec le programme | `reports/label_audit.csv` |
| 3 bis | `04b_resolve_labels.py` | Corrections par convention (naturels / entiers), preuves tracées | `data/label_corrections_auto.csv` |
| 4 | `04_clean_text.py` | Énoncé, choix et explication séparés ; LaTeX converti en texte | `data/interim/text_clean` |
| 5 | `05_build_targets.py` | Cibles (domaine, sous-domaine, intervalle de niveaux, complexité) | `data/interim/targets` |
| 6 | `06_split.py` | Train / test + 5 plis, groupés par famille de quasi-doublons | `data/interim/splits` |
| 7 | `07_export.py` | Un export par famille de modèles, plus la file de revue | `data/processed/` |
| 8 | `08_smoke_baseline.py` | Baseline de contrôle en validation croisée | `reports/smoke_baseline.csv` |

`run_all.sh` exécute 04 avant 04b : le nettoyage du texte n'est pas utilisé par les corrections, l'ordre est donc sans effet.

## Données produites

Tout est dans `data/processed/`. Tous les exports partagent les mêmes identifiants, partitions et plis, ce qui permet de comparer les modèles sur exactement les mêmes questions.

| Dossier / fichier | Contenu | Pour |
|---|---|---|
| `questions_master.parquet` / `.csv` | 981 questions × 81 colonnes : textes, étiquettes d'origine et corrigées, cibles, variables, partition, signaux d'audit | Référence |
| `tfidf/train.csv`, `tfidf/test.csv` | 811 / 125 questions, 3 variantes d'entrée, toutes les cibles, `fold` | Axe 1 |
| `hf/train.jsonl`, `hf/test.jsonl`, `hf/label2id.json` | Texte, étiquettes entières, niveaux, `fold` | Axe 2 |
| `hf/augment_train.jsonl` | 1 533 variantes LLM de questions de train uniquement | Axe 2 (augmentation) |
| `llm/` | Prompt système (taxonomie + 15 niveaux + grille de complexité), schéma JSON, 125 questions de test, 34 exemples few-shot | Axe 3 |
| `ood/xlsx_niveaux.jsonl` | 747 questions synthétiques couvrant les 15 niveaux | Test hors distribution |
| `review/review_queue.csv` | 414 questions signalées, à relire | Axe 4 |

**Cibles :** domaine (7 classes), sous-domaine (17 classes), niveau sous forme d'intervalle (`level_min`, `level_max`) plus 17 colonnes multi-hot, complexité (`cx_gold` sur 120 questions de référence).

## Résultats clés

**Ce que l'audit a révélé** (détails dans l'[analyse du contexte](docs/CONTEXTE.md#4-ce-que-révèlent-les-données)) :

- 273 des 279 questions « Nombres entiers » ne contiennent aucun nombre négatif.
- 41 % des questions appartiennent à des familles de quasi-doublons. Un découpage aléatoire gonflerait les scores.
- Les ensembles de niveaux sont contigus dans 100 % des cas, donc modélisables en intervalle. Rien n'est entraînable au-delà de Sec 1.
- L'estimation de complexité tirée du texte ne s'accorde qu'à κ = 0,22 avec l'annotation de référence.

**Baseline de contrôle** (TF-IDF + régression logistique, 5 plis, test non ouvert, entrée `x_stem_choices`) :

| Tâche | Avant correction | Après correction |
|---|---|---|
| Domaine — macro-F1 | 0,646 | **0,669** |
| Sous-domaine — macro-F1 / exactitude | 0,576 / 0,646 | **0,636 / 0,757** |
| Niveau min — exactitude / erreur moyenne | 0,676 / 0,64 an | 0,669 / 0,65 an |
| Niveau max — exactitude / erreur moyenne | 0,560 / 0,68 an | 0,558 / 0,66 an |

Ce sont des **planchers à battre**, pas des résultats finaux. Le sous-domaine passe de 18 à 17 classes après correction.

## Décisions de conception

Neuf décisions ont été prises à partir des données, du programme québécois et de sources publiques. Chacune est réversible. Le détail est dans [`docs/DECISIONS.md`](docs/DECISIONS.md).

| # | Sujet | Décision |
|---|---|---|
| D1 | Étiquette de référence | Base (`final_*`), corrigée par D2 |
| D2 | Naturels / entiers | Convention du programme ; 273 questions reclassées, dont 147 à vérifier (image) |
| D3 | Complexité | Grille absolue à 3 niveaux ; 120 questions de référence ; prédite par le LLM |
| D4 | Niveaux des questions avec image | Entraînement et évaluation sur les 312 questions texte |
| D5 | Fichiers synthétiques | xlsx = test hors distribution ; bilingue écarté |
| D6 | LLM | `gpt-4o-2024-08-06`, température 0, sortie JSON |
| D7 | Transformeur | XLM-R en principal, CamemBERT en comparaison |
| D8 | Livrable | Dépôt privé, données MEJ non versionnées |
| D9 | Textes corrompus | 4 messages d'erreur serveur traités comme manquants |

## Revue humaine et annotation

Le pipeline ne déclare jamais une étiquette fausse à lui seul : il la signale. Les décisions humaines sont réinjectées par deux fichiers simples :

| Tâche | Fichier à remplir | Effet après `./run_all.sh` |
|---|---|---|
| Corriger une étiquette | `data/label_corrections.csv` (`id`, `sous_domaine_corrige`) | Prioritaire sur les corrections automatiques ; l'étiquette d'origine est conservée |
| Annoter la complexité | `annotations/complexite_annotateur2.csv` (`id`, `complexite`, `annotateur`) | Calcule l'accord inter-annotateurs et met à jour la référence |

Les consignes pas à pas sont dans [`docs/REVUE_ET_ANNOTATION.md`](docs/REVUE_ET_ANNOTATION.md).

## Paramètres

Tous les paramètres sont dans `common.py`.

| Paramètre | Valeur | Rôle |
|---|---|---|
| `LABEL_SOURCE` | `"base"` | Source d'étiquettes : `"base"` ou `"plateforme"` |
| `APPLY_AUTO_CORRECTIONS` | `True` | Appliquer ou non les corrections automatiques de l'étape 3 bis |
| `MIN_CLASS_COUNT` | `10` | En dessous, une classe est regroupée |
| `DEDUP_THRESHOLD` | `0.85` | Similarité à partir de laquelle deux questions sont des quasi-doublons |
| `TEST_SIZE` | `0.15` | Part visée pour le test gelé |
| `N_FOLDS` | `5` | Nombre de plis de validation croisée |
| `SEED` | `42` | Graine aléatoire |
| `MEJ_RAW_DIR` (variable d'environnement) | — | Dossier des fichiers bruts, si ce n'est pas `data/raw/` |

## Reproductibilité

- Les versions des dépendances sont **épinglées** dans `requirements.txt`. Avec pandas 3 ou scikit-learn 1.9, le découpage change légèrement.
- Les tris et le hasard sont **déterministes** (graine fixe, tris stables).
- Vérification faite : un clone propre, avec ces versions, reproduit **à l'identique** le découpage (125 / 811), la baseline et les rapports versionnés.

## Données et confidentialité

Les fichiers Math en Jeu et toutes les tables qui contiennent le texte des questions (`data/raw/`, `data/interim/`, `data/processed/`) **ne sont pas versionnés** : ce contenu appartient à MEJ. Le dépôt ne contient que du code, de la documentation, des rapports agrégés, des corrections d'étiquettes et des annotations (identifiants et niveaux seulement).

## Feuille de route

- [x] Audit des données et des étiquettes
- [x] Pipeline de préparation reproductible
- [x] Décisions de conception documentées
- [x] Baseline de contrôle
- [ ] Revue des 147 corrections à vérifier
- [ ] Deuxième annotation de complexité
- [ ] Axe 1 : baseline complète avec analyse d'erreurs
- [ ] Axe 2 : XLM-R et CamemBERT
- [ ] Axe 3 : gpt-4o zero-shot et few-shot
- [ ] Axe 4 : file de revue fondée sur les prédictions hors pli
- [ ] Évaluation finale sur le test

## FAQ

**Pourquoi le test ne fait-il pas exactement 15 % ?**
Les familles de quasi-doublons ne sont jamais coupées en deux. La plus grande compte 42 questions, ce qui empêche d'atteindre 15 % exactement : le test fait 125 questions (13,4 %).

**Puis-je revenir aux étiquettes d'origine ?**
Oui. Mettez `APPLY_AUTO_CORRECTIONS = False` dans `common.py`, puis relancez `./run_all.sh` : seules les corrections manuelles restent appliquées. Dans tous les cas, les colonnes `sub_base` et `dom_base` gardent l'étiquette d'origine.

**Pourquoi ne pas utiliser RoBERTa, comme prévu dans le plan ?**
RoBERTa est entraîné sur l'anglais. XLM-R et CamemBERT sont ses équivalents multilingue et français.

**Le LLM voit-il les images ?**
Non, le prompt est textuel. Il est prévenu quand une question est accompagnée d'une image. Un modèle multimodal est une piste pour la suite.
