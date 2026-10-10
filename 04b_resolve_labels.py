"""Étape 4b — Résolution automatique des étiquettes par règle de convention (décision D2 du guide).

Convention retenue (Programme de formation de l'école québécoise, Progression des apprentissages) :
« Nombres entiers » = nombres positifs ET négatifs (section D, vocabulaire « nombre négatif, nombre positif »).
Une question sans aucun nombre négatif relève donc des « Nombres naturels ».

Preuves indépendantes enregistrées pour chaque correction :
  - plateforme : l'étiquette Iterations dit déjà « naturels » (la plateforme n'emploie « entiers » qu'une fois sur 326) ;
  - programme  : le niveau maximal de la question est ≤ 4e année, avant l'arrivée des entiers relatifs au 3e cycle ;
  - texte      : aucun nombre négatif dans l'énoncé, les choix ou l'explication (FR et EN).
Les questions avec image sans preuve « plateforme » restent marquées a_verifier : un négatif peut se cacher dans l'image.
Le domaine de la base est conservé (96 % d'accord avec la plateforme) : 1.2 -> 1.1 et 2.3 -> 2.1.

Sortie : data/label_corrections_auto.csv (lu par 05_build_targets.py ; les corrections manuelles l'emportent)
"""
import numpy as np
import pandas as pd

from common import LEVEL_YEAR, PREP, has_negative, load

m = load("master_raw")
neg = m.text_fr_raw.map(has_negative) | m.text_en_raw.map(has_negative)
lvl_max = m.levels.map(lambda l: max((LEVEL_YEAR[x] for x in l if x in LEVEL_YEAR), default=np.nan)
                       if isinstance(l, (list, np.ndarray)) else np.nan)

TO_NAT = {"1.2": "1.1", "2.3": "2.1"}
TO_ENT = {v: k for k, v in TO_NAT.items()}
rows = []
for i, r in m.iterrows():
    if r.sub_base in TO_NAT and not neg[i]:
        target, rule = TO_NAT[r.sub_base], "pfeq_entiers_sans_negatif"
    elif r.sub_base in TO_ENT and neg[i]:
        target, rule = TO_ENT[r.sub_base], "pfeq_naturels_avec_negatif"
    else:
        continue
    proofs = ["texte"]
    if isinstance(r.sub_plat, str) and r.sub_plat == target:
        proofs.append("plateforme")
    if not np.isnan(lvl_max[i]) and lvl_max[i] <= 3:
        proofs.append("programme")
    rows.append({"id": int(r.id), "sous_domaine_avant": r.sub_base, "sous_domaine_corrige": target, "regle": rule,
                 "preuves": "+".join(proofs), "has_image": bool(r.has_image),
                 "a_verifier": bool(r.has_image) and "plateforme" not in proofs})

out = pd.DataFrame(rows)
out.to_csv(PREP / "data" / "label_corrections_auto.csv", index=False, encoding="utf-8-sig")
print(f"corrections automatiques : {len(out)}")
print("par règle :", out.regle.value_counts().to_dict())
print("par preuves :", out.preuves.value_counts().to_dict())
print(f"à vérifier (image, sans confirmation plateforme) : {out.a_verifier.sum()}")
