# Projet SALBP-1 — Équilibrage de lignes d’assemblage

M2 IA — Université Claude Bernard Lyon 1 — Cours « Combinatoire, Complexité et Graphes » (M. N’Diaye)
Binôme : Yennipena Jérémie COULIBALY et Antoine SALAZAR

Minimiser le nombre de stations d’une ligne d’assemblage pour un temps de cycle fixé (SALBP-1),
avec deux méthodes complètes (CP-SAT) et deux méthodes incomplètes, comparées sur les jeux de Scholl et d’Otto.

| Méthode | Fichier | État |
|---|---|---|
| H1 — heuristique constructive (RPW et autres règles de priorité) | `src/h1_rpw.py` | fait |
| M1 — CP-SAT, affectation directe x[i,k] | `src/m1_cpsat.py` | fait |
| M2 — CP-SAT, indice de station et fenêtres [Eᵢ, Lᵢ] | — | après la présentation mi-parcours |
| H2 — recherche locale | — | après la présentation mi-parcours |

## Installation

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Python ≥ 3.10. Sans OR-Tools, M1 bascule automatiquement sur un moteur de secours (HiGHS via SciPy)
qui résout exactement le même modèle ; la colonne `moteur` des résultats l’indique.

## Lancer

```bash
python src/test_socle.py                      # tests rapides (lecture, bornes, vérificateur, H1, M1)
python src/h1_rpw.py Tonge_c160               # H1 sur une instance, toutes les règles
python src/m1_cpsat.py Tonge_c160 --temps-limite 60 --workers 8

python src/benchmark.py principale            # H1 (RPW) + M1 par défaut, 28 instances (≈ 10 min)
python src/benchmark.py h1_parametres         # règles de priorité × départages, 5 graines (quelques secondes)
python src/benchmark.py m1_parametres --temps-limite 30   # variations de M1, petites et moyennes instances
python src/analyse.py                         # tableaux de synthèse + graphiques
python src/maj_presentation.py                # recopie les résultats dans la présentation mi-parcours
```

Options utiles du benchmark : `--instances Mertens_c6 Tonge_c160`, `--categories petite moyenne`,
`--temps-limite 60`, `--workers 8`, `--moteur cpsat|highs`, `--reprendre` (saute ce qui est déjà fait).

## Organisation

| Dossier | Contenu |
|---|---|
| `data/` | Instances téléchargées, non modifiées, et `instances.csv` (liste commune : nom, source, fichier, c, optimum, catégorie) |
| `src/instance.py` | Lecture `.IN2` (Scholl) et `.alb` (Otto, lu directement dans le `.zip`) → classe `Instance` |
| `src/resultat.py` | Format commun `Resultat` renvoyé par toutes les méthodes |
| `src/verificateur.py` | Vérificateur commun (affectation unique, capacité, précédences, stations non vides) |
| `src/bornes.py` | LB1, LB2, borne inférieure |
| `src/benchmark.py` | Expériences `principale`, `h1_parametres`, `m1_parametres` → `resultats/<expérience>.csv` |
| `src/analyse.py` | Synthèses CSV et figures dans `resultats/figures/` |
| `resultats/` | Résultats bruts, solutions (`solutions/*.jsonl`), synthèses, figures |
| `docs/` | Plan, rapport, présentations |

## Résultats actuels

Les résultats présents dans `resultats/` ont été produits **sans OR-Tools** : M1 y est résolu par le
moteur de secours HiGHS (colonne `moteur = highs`). Pour obtenir les chiffres CP-SAT de la présentation :

```bash
pip install ortools
python src/benchmark.py principale && python src/benchmark.py m1_parametres --temps-limite 30
python src/analyse.py && python src/maj_presentation.py
```
