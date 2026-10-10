# Revue des étiquettes et annotation de la complexité

> **Pour qui ?** Enseignants, conseillers pédagogiques ou membres de l'équipe qui relisent les étiquettes ou annotent la complexité. Aucune compétence en programmation n'est nécessaire, sauf pour la dernière étape (relancer le pipeline), qui tient en une commande.

---

## 1. Relire les étiquettes douteuses

### Le fichier à relire

`data/processed/review/review_queue.csv` est produit par `./run_all.sh` et s'ouvre dans Excel. Il contient les 414 questions signalées par l'audit. Les **147 corrections automatiques à vérifier** sont en tête (colonne `a_verifier` = VRAI).

| Colonne | Signification |
|---|---|
| `id`, `link_fr` | Numéro de la question et lien vers sa page Math en Jeu (pour voir l'image) |
| `a_verifier` | VRAI si une correction automatique a été faite sur une question avec image |
| `signaux` | Pourquoi la question est signalée (voir le tableau ci-dessous) |
| `sub_base`, `sub_plat` | Sous-domaine selon la base et selon la plateforme |
| `y_sub` | Sous-domaine actuellement retenu, après correction automatique éventuelle |
| `preuves_correction_auto` | Preuves de la correction : `texte`, `plateforme`, `programme` |
| `x_stem_choices` | Énoncé et choix de réponse |
| `decision`, `sous_domaine_corrige`, `commentaire` | **À remplir** |

### Les signaux

| Signal | Ce qu'il veut dire |
|---|---|
| `entiers_sans_negatif` | Étiquetée « Nombres entiers » sans aucun nombre négatif |
| `conflict_sub`, `conflict_dom` | La base et la plateforme ne donnent pas le même sous-domaine ou domaine |
| `doublon_conflit` | Des questions quasi identiques portent des sous-domaines différents |
| `inexact` | Contenu mathématique marqué faux |
| `fr_en` | L'étiquette de la version française diffère de celle de la version anglaise |
| `entiers_avant_3e_cycle` | « Entiers » sur une question de la 1re à la 4e année, alors que les entiers relatifs arrivent au 3e cycle |
| `hierarchie` | Le sous-domaine n'appartient pas au domaine indiqué |

### Comment décider

Pour chaque ligne :

1. Ouvrir le lien `link_fr` et regarder la question avec son image.
2. Remplir `decision` avec l'un des trois choix :
   - `garder` : l'étiquette retenue (`y_sub`) est juste ;
   - `corriger` : écrire le bon code dans `sous_domaine_corrige` (par exemple `2.1`) ;
   - `ambigue` : la question relève vraiment de deux sous-domaines ; l'expliquer dans `commentaire`.

**Deux règles pour les frontières les plus fréquentes :**

- **Naturels ou entiers ?** « Entiers » (1.2, 2.3) seulement si la question contient un nombre négatif : température sous zéro, droite numérique avec des négatifs, etc. Sinon « naturels » (1.1, 2.1).
- **Sens ou opérations ?** Si la question demande de **lire, écrire, comparer, ordonner ou représenter** un nombre, c'est le domaine 1. Si elle demande de **calculer** (additionner, multiplier, simplifier, trouver un terme), c'est le domaine 2. Cette règle tranche aussi entre 1.3 et 2.4 pour les fractions.

### Sous-domaines les plus utilisés

| Code | Sous-domaine | Code | Sous-domaine |
|---|---|---|---|
| 1.1 | Nombres naturels (sens et écriture) | 2.1 | Nombres naturels (opérations) |
| 1.2 | Nombres entiers (sens et écriture) | 2.2 | Suites logiques |
| 1.3 | Fractions, proportions, décimaux, pourcentages (sens) | 2.3 | Nombres entiers (opérations) |
| 3.1 | Figures planes | 2.4 | Fractions, proportions, décimaux, pourcentages (opérations) |
| 3.2 | Solides | 4.1 | Longueur, surface, volume, masse, température |
| 3.8 | Calcul d'aire | 5.2 | Dénombrement des possibilités |
| 6.5 | Représentation des données (statistique) | 5.3 | Calcul des probabilités |

La taxonomie complète (59 sous-domaines) est dans le fichier `Domaines et sous-domaines - juin 2024`.

### Réintégrer les corrections

1. Copier les lignes `corriger` dans un nouveau fichier `data/label_corrections.csv`, avec deux colonnes : `id` et `sous_domaine_corrige`.
2. Relancer `./run_all.sh`.

Une correction manuelle l'emporte toujours sur une correction automatique, et l'étiquette d'origine reste conservée dans la table.

Format attendu (les valeurs ci-dessous sont un exemple, pas des corrections validées) :

```csv
id,sous_domaine_corrige
574,1.3
508,2.1
```

---

## 2. Annoter la complexité

### La grille

| Niveau | Définition | Exemple tiré du corpus |
|---|---|---|
| **1 — faible** | Une seule notion, une opération, données explicites | « Compare ces nombres : 78 □ 89 » (question 343) |
| **2 — moyenne** | 2 ou 3 étapes, ou une conversion ou représentation intermédiaire | « Mia prend 3 œufs dans une douzaine : quelle fraction de la boîte ? » (question 766) |
| **3 — élevée** | Plusieurs notions combinées, ou modélisation d'une situation | « Le grand-père a 66 ans, deux fois l'âge de tante Minia, qui a trois fois l'âge de Sêdami… » (question 71) |

La complexité est **absolue** : on juge la question elle-même, pas le niveau de l'élève. Une question avec image se juge en ouvrant son lien.

### Procédure

1. Ouvrir `reports/annotation_complexite.csv` (120 questions, produit par `./run_all.sh`).
2. Annoter **à l'aveugle** : ne pas consulter `annotations/complexite_annotateur1.csv`.
3. Enregistrer le résultat dans `annotations/complexite_annotateur2.csv`, avec les colonnes `id`, `complexite` (1, 2 ou 3) et `annotateur`.
4. Relancer `./run_all.sh`. Le script calcule l'accord (kappa) et utilise la moyenne arrondie des annotateurs comme référence.

Un kappa d'au moins 0,6 indique une grille assez claire. En dessous, on discute les désaccords et on précise la grille avant d'aller plus loin.
