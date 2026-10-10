# Décisions de conception

Patrice n'ayant pas pu trancher les questions ouvertes, chaque décision ci-dessous a été prise à partir des données, du programme québécois et de sources publiques. Chacune est **réversible** : les étiquettes d'origine restent dans la table maîtresse et chaque paramètre se change dans `common.py` ou par un fichier de corrections.

| # | Question | Décision | Paramètre / fichier |
|---|---|---|---|
| D1 | Source d'étiquettes de référence | La base (`final_*` de Full_database), corrigée par D2 | `LABEL_SOURCE = "base"` |
| D2 | Convention « Nombres naturels » / « Nombres entiers » | Définition du programme : entiers = nombres positifs **et négatifs** | `04b_resolve_labels.py` |
| D3 | Définition de la complexité | Absolue, grille à 3 niveaux, référence de 120 questions annotées | `annotations/` |
| D4 | Niveaux des 653 questions avec image | Pas de source disponible : niveau entraîné et évalué sur les 312 questions texte | — |
| D5 | Fichiers synthétiques | xlsx = test hors distribution (747 questions) ; bilingue écarté | `data/processed/ood/` |
| D6 | « GPT 4.0 » du plan | GPT-4o, instantané daté `gpt-4o-2024-08-06`, température 0, sortie JSON | `data/processed/llm/` |
| D7 | Transformeur | XLM-R base en principal, CamemBERT en comparaison | — |
| D8 | Livrable et données | Dépôt GitHub privé ; données MEJ non versionnées | `.gitignore`, `data/raw/README.md` |
| D9 | Textes corrompus | 4 textes remplacés par un message d'erreur serveur (questions 456, 518, 550, 2867) traités comme manquants | `01_load.py` |

## D1 — Source d'étiquettes : la base

- La base couvre 979 questions ; la plateforme (`group_id` / `keyword_id`) n'en couvre que 326, toutes sans image.
- Sur le domaine, les deux sources s'accordent à 96,3 % : le domaine de la base est fiable.
- Sur le sous-domaine, elles ne s'accordent qu'à 56,4 %, et le désaccord est presque entièrement une question de convention (D2).
- Les colonnes `final_*` ne sont pas une révision indépendante : elles reprennent l'étiquette française, avec l'anglaise en repli (99,9 % identiques).

## D2 — Convention naturels / entiers : celle du programme

**Règle :** une question n'est classée « Nombres entiers » (1.2 ou 2.3) que si elle contient au moins un nombre négatif ou le vocabulaire correspondant. Sinon elle relève des « Nombres naturels » (1.1 ou 2.1), et le domaine de la base est conservé.

Justification :

- Dans la *Progression des apprentissages* (mathématique, primaire), la section « Nombres entiers » utilise le vocabulaire « nombre négatif, nombre positif ». Les nombres naturels y sont bornés par cycle : 1 000, 100 000, puis 1 000 000.
- Dans la base, seules 6 des 279 questions « entiers » (2,2 %) contiennent un nombre négatif. Exemples : « Place en ordre croissant : 2, 0, -10, 3 », températures sous zéro.
- La plateforme n'emploie l'étiquette « entiers » qu'**une fois sur 326 questions**.
- 13 questions « entiers » ont un niveau maximal ≤ 4e année, alors que les entiers relatifs relèvent du 3e cycle (5e et 6e année).

Application (`04b_resolve_labels.py`, sortie `data/label_corrections_auto.csv`) :

| Preuves | Corrections |
|---|---|
| Texte seul (aucun négatif) | 152 |
| Texte + plateforme | 108 |
| Texte + plateforme + programme | 13 |
| **Total** | **273** |

Les 147 corrections portant sur une question avec image, sans confirmation de la plateforme, sont marquées `a_verifier` : un nombre négatif pourrait figurer dans l'image. Une correction manuelle (`data/label_corrections.csv`) l'emporte toujours sur une correction automatique. Pour désactiver les corrections automatiques : `APPLY_AUTO_CORRECTIONS = False` dans `common.py`.

Effet sur la baseline de contrôle (TF-IDF + régression logistique, 5 plis, entrée `x_stem_choices`) : l'exactitude passe de 0,646 à 0,757 sur le sous-domaine, et le macro-F1 de 0,576 à 0,636. La comparaison n'est pas strictement à l'identique : 17 classes après correction contre 18 avant, et un découpage recalculé.

## D3 — Complexité : absolue, grille à 3 niveaux

| Niveau | Définition |
|---|---|
| 1 — faible | Une notion, une opération, données explicites |
| 2 — moyenne | 2 ou 3 étapes, ou une conversion / représentation intermédiaire |
| 3 — élevée | Plusieurs notions combinées, ou modélisation d'une situation |

- L'échantillon stratifié de 120 questions a été annoté une première fois par Claude, selon cette grille (`annotations/complexite_annotateur1.csv`) : 67 questions de niveau 1, 46 de niveau 2, 7 de niveau 3.
- Le proxy textuel `cx_proxy` ne s'accorde qu'à **κ = 0,22** (kappa pondéré quadratique) avec cette annotation. Il est rejeté comme cible : il mesure la longueur du texte, et les questions de géométrie, dont le contenu est dans l'image, y passent pour « faciles ».
- La complexité de toutes les questions est donc demandée au LLM (axe 3), puis évaluée contre ces 120 annotations.
- Le niveau 3 est rare (6 %). Pour un classifieur supervisé, je recommande une cible binaire : « une étape » (1) contre « plusieurs étapes » (2 et 3).
- Une deuxième annotation humaine (`annotations/complexite_annotateur2.csv`) est prise en compte automatiquement : moyenne arrondie des annotateurs.

## D4 — Niveaux des questions avec image

Les pages publiques de Math en Jeu n'affichent ni niveau ni catégorie (vérifié sur la question 1). Le niveau est donc entraîné et évalué sur les 312 questions texte éligibles seulement. Pour les questions avec image, les modèles produisent des prédictions de niveau non évaluées, à signaler comme telles dans tout rapport.

Remarque : l'indicateur `IMAGE` ne signale pas toujours une image dans l'énoncé. Pour la question 1, l'image se trouve dans la rétroaction.

## D5 — Fichiers synthétiques

- `questions_generees_fr.xlsx` : après retrait des 9 lignes décalées par le caractère `|`, il reste **747 questions couvrant les 15 niveaux**. Elles forment un test hors distribution, seule source pour Sec 2 à Sec 5. Elles ne servent jamais à l'entraînement : réponses générées et position de la bonne réponse biaisée (B 44,6 %, D 3,3 %).
- `questions_mathematiques_bilingues.csv` : écarté. Il compte 20 questions uniques pour 150 lignes, et la bonne réponse est absente des choix dans 48 cas.

## D6 — Modèle LLM

Le plan mentionne « GPT 4.0 », lu comme GPT-4o.

- Les retraits de modèles de février 2026 concernent ChatGPT et pas l'API ([OpenAI, Help Center](https://help.openai.com/en/articles/20001051-retiring-gpt-4o-and-other-chatgpt-models)).
- Côté API, seul `chatgpt-4o-latest` a été retiré, le 16 février 2026 ([VentureBeat](https://venturebeat.com/ai/openai-is-ending-api-access-to-fan-favorite-gpt-4o-model-in-february-2026)).

Décision :

- Utiliser l'instantané daté `gpt-4o-2024-08-06`, qui accepte les sorties structurées, à température 0, avec le schéma `output_schema.json`.
- Vérifier sa disponibilité avant exécution (`GET /v1/models`). S'il n'est plus disponible, prendre le modèle le plus proche et le consigner.
- Noter le modèle et la date d'exécution dans chaque résultat.

## D7 — Transformeur

- XLM-R base est le modèle principal : il lit les 43 questions disponibles seulement en anglais et les 933 variantes anglaises.
- CamemBERT sert de comparaison sur le français seul.
- RoBERTa, cité dans le plan, est entraîné sur l'anglais et ne convient pas à un corpus français.

## D8 — Livrable et politique des données

- Le code, la documentation et les rapports agrégés sont versionnés dans un dépôt GitHub **privé**.
- Les fichiers bruts Math en Jeu et les tables qui contiennent le texte des questions (`data/raw/`, `data/interim/`, `data/processed/`) ne sont pas versionnés : ce contenu appartient à MEJ. Voir `data/raw/README.md`.

## Sources

- [Progression des apprentissages — Mathématique, primaire (MEQ, 2009)](https://laurier.cssdm.gouv.qc.ca/files/PDA_PFEQ_mathematique-primaire_2009.pdf)
- [Programme de formation de l'école québécoise — Mathématique, primaire](https://www.quebec.ca/education/prescolaire-primaire-et-secondaire/programmes-formations-evaluation/programme-formation-ecole-quebecoise/primaire/mathematique)
- [OpenAI — Retiring GPT-4o and other ChatGPT models](https://help.openai.com/en/articles/20001051-retiring-gpt-4o-and-other-chatgpt-models)
- [VentureBeat — OpenAI is ending API access to chatgpt-4o-latest in February 2026](https://venturebeat.com/ai/openai-is-ending-api-access-to-fan-favorite-gpt-4o-model-in-february-2026)
- [Math en Jeu — exemple de page de question](https://mathenjeu.ca/question/1?lg=fr)
