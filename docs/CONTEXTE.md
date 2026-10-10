# Analyse du contexte

> **En bref.** Le projet audite puis prédit les étiquettes des 981 questions de mathématiques de la plateforme québécoise Math en Jeu (MEJ) : domaine et sous-domaine, niveau scolaire, complexité. Les données sont petites et déséquilibrées, et une partie des étiquettes est incohérente. Ce document explique le contexte, ce que contiennent les fichiers, ce qu'ils révèlent et pourquoi le pipeline est construit ainsi.

Les décisions de conception sont détaillées dans [`DECISIONS.md`](DECISIONS.md) et la méthode, étape par étape, dans [`GUIDE.md`](GUIDE.md).

---

## Sommaire

1. [Le projet](#1-le-projet)
2. [Le plan de travail](#2-le-plan-de-travail)
3. [Inventaire des données](#3-inventaire-des-données)
4. [Ce que révèlent les données](#4-ce-que-révèlent-les-données)
5. [Questions ouvertes et réponses retenues](#5-questions-ouvertes-et-réponses-retenues)
6. [Risques et limites](#6-risques-et-limites)
7. [Prochaines étapes](#7-prochaines-étapes)
8. [Glossaire](#8-glossaire)

---

## 1. Le projet

**Math en Jeu** ([mathenjeu.ca](https://mathenjeu.ca)) est une plateforme éducative québécoise de questions de mathématiques, en français et en anglais. Les questions sont surtout à choix multiples, mais il y a aussi des vrai/faux et des réponses courtes. Elles couvrent le programme québécois, de la 1re année du primaire à la 5e secondaire, y compris les trois séquences CST, TS et SN.

Chaque question doit porter trois étiquettes :

| Étiquette | Valeurs | Utilité pour la plateforme |
|---|---|---|
| Domaine / sous-domaine | 10 domaines, 59 sous-domaines (taxonomie MEJ, juin 2024) | Proposer des questions par thème |
| Niveau scolaire | De la 1re année du primaire à Sec 5 (15 niveaux + « niveau général ») | Adapter les questions à l'élève |
| Complexité | À définir (aucune étiquette n'existe) | Graduer la difficulté |

L'objectif du projet a deux faces : **vérifier** les étiquettes existantes et **prédire** automatiquement celles des nouvelles questions. Les cas douteux doivent être signalés à un humain, jamais corrigés aveuglément.

## 2. Le plan de travail

Le plan initial (tableau partagé le 3 octobre 2026) compte quatre axes. Sa première colonne, « fichiers à fusionner et champs à utiliser », était vide. La voici remplie.

| Axe | Objectif | Modèles / méthodes | Rôle dans le projet | Fichiers et champs (colonne remplie) |
|---|---|---|---|---|
| **1. Vérification et amélioration** | Vérifier la cohérence des étiquettes existantes : niveau, domaine, complexité | TF-IDF + régression logistique | Modèle de référence (baseline) | `Full_database` ⟗ `Iterations_v2` sur `e` = `question_id`, plus la taxonomie. Entrée : énoncé + choix (`x_stem_choices`). Cibles : `final categorie`, `final sous_categorie`, `availability` |
| **2. Classification avancée** | Prédire automatiquement les étiquettes | RoBERTa → **XLM-R / CamemBERT** (corpus français) | Exploiter le sens des questions | Même table, plus les variantes LLM d'Iterations, en entraînement seulement |
| **3. Comparaison avec un LLM** | Tester une approche par instructions | GPT « 4.0 » → **`gpt-4o-2024-08-06`**, zero-shot et few-shot | Comparer avec les modèles supervisés | Questions de test, taxonomie et descriptions officielles des 15 niveaux dans le prompt ; sortie JSON |
| **4. Validation** | Repérer les classifications problématiques | Étiquette prédite contre étiquette MEJ | Signaler les divergences pour une validation humaine | Prédictions hors pli des axes 1 à 3, étiquettes de la base et de la plateforme, signaux d'audit, lien `LIEN FR` vers chaque question |

## 3. Inventaire des données

| Fichier | Lignes | Contenu | Rôle | Verdict |
|---|---|---|---|---|
| `full database - questions - été 2024ish(Full_database).csv` | 981 | Énoncés FR (937) et EN (570) avec choix et explication ; domaine et sous-domaine ; indicateurs `IMAGE` et `exactitude` | Corpus principal | Socle |
| `Quesitons itérées - originales(Iterations_v2).csv` | 328 | Les 328 questions sans image, avec leurs **niveaux** (`availability`), les étiquettes de la plateforme (`group_id`, `keyword_id`) et 3 variantes LLM FR/EN par question | Seule source de niveaux, augmentation | Indispensable |
| `Domaines et sous-domaines - juin 2024(Feuil1).csv` | 59 + 59 | Taxonomie FR et EN | Référentiel des classes | Code 4.2 en double (corrigé) |
| `Description niveaux primaire.pdf`, `Descriptions des niveaux - secondaire.pdf` | 15 niveaux | Ce que l'élève sait faire à chaque niveau | Prompt du LLM, grille de complexité | Utile |
| `questions_generees_fr.xlsx` | 756 | Questions synthétiques sur les 15 niveaux | Test hors distribution | 9 lignes corrompues, biais de position |
| `questions_mathematiques_bilingues.csv` | 150 | Prototype synthétique, 20 questions uniques | — | Écarté |

## 4. Ce que révèlent les données

### 4.1 Un corpus petit, court et déséquilibré

- **981 questions** au total, dont **936** sont utilisables pour l'entraînement : 43 ont un contenu inexact, 2 n'ont pas d'étiquette.
- Énoncés **très courts** : 11 mots en médiane. Les choix de réponse portent donc une part du signal et font partie de l'entrée.
- **Trois domaines font 81 %** des questions : Opérations (331), Sens des nombres (265), Probabilité (195). Le domaine **Fonctions n'a aucune question**, et 20 sous-domaines sur 59 ne sont jamais utilisés.
- **Deux tiers des questions (66,6 %) s'appuient sur une image** que les modèles texte ne voient pas. C'est le cas de 87 % des questions de Géométrie et de Statistique.
- **39 questions n'existent qu'en anglais**, dont 12 des 23 questions de Statistique.
- Le **LaTeX** apparaît dans 54 % des questions et doit être converti en texte lisible.

### 4.2 Le niveau scolaire n'est connu que pour un tiers des questions

- Les 18 colonnes de niveaux de `Full_database` sont **entièrement vides**. Seules les 328 questions d'Iterations ont un niveau.
- Les ensembles de niveaux sont **contigus dans 100 % des cas**. Une question qui vaut pour la 3e et la 5e année vaut aussi pour la 4e. Le niveau se modélise donc comme un **intervalle [min, max]**, et seules 26 combinaisons existent.
- Au-delà de Sec 1, il y a **10 questions au plus par niveau**. Aucun modèle supervisé ne peut apprendre Sec 2 à Sec 5 avec MEJ.

### 4.3 Les étiquettes existantes se contredisent

| Constat | Chiffre |
|---|---|
| Accord sur le **domaine** entre la base (`final_*`) et la plateforme | 96,3 % (326 questions) |
| Accord sur le **sous-domaine** | **56,4 %** seulement |
| Questions « Nombres entiers » qui contiennent vraiment un nombre négatif | **6 sur 279** (2,2 %) |
| Questions que la plateforme étiquette « entiers » | **1 sur 326** |
| Questions dont l'étiquette FR diffère de l'étiquette EN | 37 sur 512 (7,2 %) |
| Questions appartenant à une famille de quasi-doublons (gabarits où seul un nombre change) | **405 (41 %)**, dans 108 familles |
| Questions aux sous-domaines divergents au sein d'une même famille | 122 |

Exemple parlant : cinq questions « Au comptoir postal… 100 timbres par feuille… », où seul le nombre de timbres change, sont réparties entre **quatre sous-domaines**, dont « figures planes ».

La colonne `final_*` n'est pas une révision indépendante : elle reprend l'étiquette française, avec l'anglaise en repli. La vraie source de désaccord est une **convention** : la base classe « Nombres entiers » des questions sans aucun nombre négatif, alors que le programme québécois réserve ce terme aux nombres positifs **et** négatifs.

### 4.4 Autres problèmes de qualité

- **43 questions** sont marquées `exactitude = FAUX` (contenu mathématique erroné). Elles sont exclues de l'entraînement.
- **4 textes** (questions 456, 518, 550 et 2867) sont des messages d'erreur du serveur (`ENOENT`) et non des questions.
- **Fichier xlsx** : 9 lignes ont leurs colonnes décalées par le caractère `|` des valeurs absolues. La bonne réponse est en position B dans 44,6 % des cas, et en position D dans seulement 3,3 %.
- **Fichier bilingue** : la bonne réponse est absente des choix dans 48 cas sur 150, et des questions de 2e année sont étiquetées SN5.
- Les **variantes LLM** d'Iterations (1 863) n'ont jamais été vérifiées : il faut contrôler qu'elles conservent le concept, donc l'étiquette.

## 5. Questions ouvertes et réponses retenues

Les questions ouvertes ont été tranchées à partir des données, du programme québécois et de sources publiques. Chaque choix est réversible (paramètre ou fichier de corrections). Le détail est dans [`DECISIONS.md`](DECISIONS.md).

| Question | Réponse retenue |
|---|---|
| Quelle étiquette fait foi ? | La base (`final_*`), corrigée par la convention ci-dessous |
| « Naturels » ou « entiers » ? | Convention du programme : 273 questions sans nombre négatif reclassées en « naturels » (147 à vérifier, car elles ont une image) |
| Comment définir la complexité ? | Grille absolue à 3 niveaux, 120 questions de référence annotées ; complexité prédite par le LLM |
| Que faire des niveaux manquants ? | Entraîner et évaluer le niveau sur les 312 questions texte seulement |
| À quoi servent les fichiers synthétiques ? | xlsx = test hors distribution (747 questions) ; bilingue écarté |
| Quel LLM ? | `gpt-4o-2024-08-06`, température 0, sortie JSON |

**Effet mesuré** sur la baseline de contrôle (5 plis) : la correction de la convention fait passer l'exactitude du sous-domaine de 0,646 à 0,757, et le macro-F1 de 0,576 à 0,636.

## 6. Risques et limites

| Risque | Conséquence | Atténuation |
|---|---|---|
| Deux tiers des questions dépendent d'une image | Plafond de performance des modèles texte | Scores rapportés séparément selon `has_image` ; piste future : modèle multimodal |
| Petit volume (environ 800 questions d'entraînement) | Forte variance d'un pli à l'autre (± 0,05 de macro-F1) | Validation croisée à 5 plis, plusieurs graines, test ouvert une seule fois |
| Étiquettes bruitées | Le modèle apprend le bruit | Audit, corrections tracées, revue humaine priorisée |
| Quasi-doublons | Scores gonflés si un gabarit est à la fois en train et en test | Découpage groupé par famille |
| Niveaux du secondaire absents | Aucune prédiction supervisée au-delà de Sec 1 | LLM guidé par les descriptions officielles, test sur le xlsx |
| Corrections automatiques sur des questions avec image | Un nombre négatif peut se trouver dans l'image | 147 cas marqués `a_verifier`, en tête de la revue |
| Disponibilité du modèle LLM | Résultats non reproductibles | Version datée, vérifiée avant chaque exécution et consignée |

## 7. Prochaines étapes

1. Relire les 147 corrections `a_verifier`, puis le reste de `review_queue.csv`.
2. Faire une deuxième annotation de complexité sur les 120 questions et mesurer l'accord (kappa).
3. Entraîner l'axe 1, puis l'axe 2 (XLM-R), puis l'axe 3 (gpt-4o), sur les mêmes plis.
4. Combiner les prédictions hors pli pour produire la file de revue de l'axe 4.
5. Ouvrir le test une seule fois, à la fin, avec des intervalles de confiance.

## 8. Glossaire

| Terme | Définition |
|---|---|
| **MEJ** | Math en Jeu, la plateforme dont proviennent les questions |
| **PFEQ** | Programme de formation de l'école québécoise ; sa *Progression des apprentissages* définit les notions par cycle |
| **CST / TS / SN** | Les trois séquences de mathématiques en 4e et 5e secondaire : Culture, société et technique ; Technico-sciences ; Sciences naturelles |
| **Base / plateforme** | Les deux sources d'étiquettes : colonnes `final_*` de Full_database, et `group_id` / `keyword_id` d'Iterations |
| **Quasi-doublons** | Questions presque identiques (similarité ≥ 0,85), souvent issues d'un même gabarit |
| **Pli** | Une des 5 parts de la validation croisée ; chaque question sert une fois à valider |
| **Hors pli** | Prédiction faite par un modèle qui n'a pas vu la question pendant son entraînement |
| **Macro-F1** | Moyenne du F1 de chaque classe ; une classe rare pèse autant qu'une classe fréquente |
| **Kappa (κ)** | Mesure d'accord entre deux annotateurs, corrigée du hasard (1 = accord parfait, 0 = hasard) |
| **Hors distribution (OOD)** | Données d'une autre provenance, utilisées pour tester la robustesse du modèle |
