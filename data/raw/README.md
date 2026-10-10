# Données brutes (non versionnées)

Les fichiers Math en Jeu ne sont pas dans le dépôt : ils contiennent le texte intégral des questions, propriété de MEJ.
Placez-les ici (`data/raw/`), ou indiquez leur dossier avec la variable `MEJ_RAW_DIR` :

| Fichier | Contenu |
|---|---|
| `full database - questions - été 2024ish(Full_database).csv` | 981 questions, textes FR/EN, domaine et sous-domaine |
| `Quesitons itérées - originales(Iterations_v2).csv` | 328 questions, niveaux, étiquettes plateforme, variantes LLM |
| `Domaines et sous-domaines - juin 2024(Feuil1).csv` | Taxonomie (10 domaines, 59 sous-domaines) |
| `Description niveaux primaire.pdf`, `Descriptions des niveaux - secondaire.pdf` | Descriptions des 15 niveaux |
| `questions_generees_fr.xlsx` | 756 questions synthétiques (test hors distribution) |
| `questions_mathematiques_bilingues.csv` | 150 questions synthétiques (écartées) |

```bash
export MEJ_RAW_DIR=~/Documents/Patrice   # optionnel si les fichiers sont dans data/raw/
./run_all.sh
```
