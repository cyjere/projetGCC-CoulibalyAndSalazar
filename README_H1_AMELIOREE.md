# Ajout Git — H1 améliorée (SALBP-1)

Ce dossier contient trois scripts à copier dans le dossier `src/` du dépôt existant : (je les ai déjà ajoutés)

- `h1_amelioree.py` : heuristique constructive avec nouvelles priorités et critère de remplissage ;
- `benchmark_h1_amelioree.py` : protocole d'expérimentation et enregistrement des résultats ;
- `analyse_h1_amelioree.py` : synthèses statistiques et graphiques.

La version existante `h1_rpw.py` n'est pas modifiée. La recherche locale n'est pas incluse :
elle correspond à H2 dans le projet.

## 1. Installation

Les scripts réutilisent les modules du projet :

- `instance.py`
- `resultat.py`
- `verificateur.py`
- `bornes.py` (facultatif pour l'affichage de l'écart à la borne)

Ils utilisent les bibliothèques déjà nécessaires au projet : `pandas` et `matplotlib`
pour l'analyse. Aucun solveur supplémentaire n'est requis pour H1 améliorée.

## 2. Copier les fichiers

Copier les trois fichiers `.py` dans `src/`.

Ne pas remplacer `h1_rpw.py`.

## 3. Tester une instance

Depuis la racine du dépôt :

```bash
python src/h1_amelioree.py Mertens_c6
```

## 4. Lancer le benchmark

Sur toutes les instances :

```bash
python src/benchmark_h1_amelioree.py
```

Sur quelques instances pour vérifier rapidement :

```bash
python src/benchmark_h1_amelioree.py --instances Mertens_c6 Bowman_c20
```

Avec 30 graines pour les variantes aléatoires :

```bash
python src/benchmark_h1_amelioree.py --graines 30
```

Pour reprendre un benchmark interrompu :

```bash
python src/benchmark_h1_amelioree.py --reprendre
```

Le benchmark enregistre :
- `resultats/h1_amelioree.csv`
- `resultats/solutions/h1-amelioree.jsonl`

Les solutions passent toutes par le vérificateur commun. Une solution invalide est marquée
`valide=0`.

## 5. Analyser les résultats

```bash
python src/analyse_h1_amelioree.py
```

Fichiers produits :
- `resultats/synthese_h1_amelioree.csv`
- `resultats/synthese_h1_amelioree_par_instance.csv`
- `resultats/comparaison_h1_reference.csv` si `resultats/principale.csv` est disponible
- graphiques dans `resultats/figures/`

## 6. Choix méthodologiques de cette première version

### Règle mixte

Le score mixte est :

\[
P_i = 0.60\,\widetilde{RPW}_i
+ 0.25\,\widetilde{NS}_i
+ 0.15\,\widetilde{Prof}_i
\]

où les trois composantes sont normalisées par min-max sur les tâches de l'instance.
Les coefficients sont des valeurs initiales de test, pas des paramètres optimaux établis.

### Critère de remplissage

Pour une tâche admissible \(i\), avec temps résiduel \(R\) et durée \(t_i\) :

\[
F_i = 1 - \frac{R-t_i}{C}
\]

Le score de sélection est :

\[
P_i^* = (1-\lambda)\widetilde P_i + \lambda F_i,
\quad 0 \leq \lambda \leq 1.
\]

À \(\lambda=0\), le remplissage est désactivé. Les valeurs de lambda sont des valeurs
expérimentales à comparer.

### Limites connues

- La variante « profondeur » utilise la longueur du plus long chemin depuis une source.
  Elle représente une caractéristique structurelle simple, pas une mesure complète de
  criticité au sens de la théorie de l'ordonnancement.
- Le critère de remplissage est une heuristique de sélection locale ; il ne garantit pas
  une réduction du nombre total de stations.
- Les coefficients du score mixte et le poids de remplissage doivent être évalués sur les
  instances de validation, sans choisir les paramètres sur le seul jeu de test.
- Cette version ne fait ni échange ni déplacement de tâches après construction. Cela relève
  de H2 (recherche locale).
- Le lien expérimental avec M1 (borne supérieure et indice CP-SAT) n'est pas encore activé :
  `m1_cpsat.py` continue d'utiliser la fonction H1 de référence. Il faudra une modification
  explicite et contrôlée de M1 pour étudier l'apport de H1 améliorée à M1.

## 7. Recommandation pour le protocole

Commencer par un petit sous-ensemble pour vérifier l'intégration, puis lancer le benchmark
complet. Comparer les variantes sur les mêmes instances. Pour les variantes aléatoires,
présenter moyenne, médiane, meilleur résultat et dispersion ; ne pas comparer seulement le
meilleur tirage à une exécution déterministe.
