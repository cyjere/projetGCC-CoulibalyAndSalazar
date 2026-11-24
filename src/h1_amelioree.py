"""H1 améliorée — variantes constructives pour SALBP-1.

Ce module conserve l'architecture de H1 (construction station par station).
Il ne réalise PAS de recherche locale : celle-ci appartient à H2 dans le projet.

Règles proposées :
- rpw : poids positionnel classique ;
- rpw_normalise : RPW divisé par la somme des durées (mise à l'échelle) ;
- profondeur : longueur du plus long chemin depuis une tâche source ;
- mixte : combinaison min-max normalisée de RPW, nombre de successeurs et profondeur ;
- duree, nb_successeurs, aleatoire : règles de référence.

Le paramètre poids_remplissage ajoute un terme favorisant les tâches qui remplissent
mieux le temps résiduel de la station. Il est compris entre 0 et 1.
"""

from __future__ import annotations

import random
import time
from typing import Dict, List, Optional, Tuple

from instance import Instance
from resultat import HEURISTIQUE, Resultat

REGLES = (
    "rpw",
    "rpw_normalise",
    "duree",
    "nb_successeurs",
    "profondeur",
    "mixte",
    "aleatoire",
)
DEPARTAGES = ("indice", "duree", "remplissage", "aleatoire")


def _normaliser(valeurs: Dict[int, float]) -> Dict[int, float]:
    """Normalisation min-max dans [0, 1]. Une variable constante vaut 0."""
    minimum = min(valeurs.values())
    maximum = max(valeurs.values())
    if maximum == minimum:
        return {i: 0.0 for i in valeurs}
    return {i: (v - minimum) / (maximum - minimum) for i, v in valeurs.items()}


def _profondeurs(inst: Instance) -> Dict[int, float]:
    """Longueur en arcs du plus long chemin depuis une tâche source."""
    profondeur = {}
    for i in inst.ordre_topologique:
        preds = inst.predecesseurs[i]
        profondeur[i] = 0.0 if not preds else 1.0 + max(profondeur[p] for p in preds)
    return profondeur


def composantes_priorite(inst: Instance) -> Dict[str, Dict[int, float]]:
    """Calcule les indicateurs structurels utilisés par les règles de priorité."""
    rpw = {
        i: float(inst.duree(i) + sum(inst.duree(j) for j in inst.tous_successeurs[i]))
        for i in inst.taches
    }
    succ = {i: float(len(inst.tous_successeurs[i])) for i in inst.taches}
    duree = {i: float(inst.duree(i)) for i in inst.taches}
    profondeur = _profondeurs(inst)
    return {
        "rpw": rpw,
        "successeurs": succ,
        "duree": duree,
        "profondeur": profondeur,
        "rpw_norm": _normaliser(rpw),
        "successeurs_norm": _normaliser(succ),
        "duree_norm": _normaliser(duree),
        "profondeur_norm": _normaliser(profondeur),
    }


def priorites(
    inst: Instance,
    regle: str,
    rng: random.Random,
    alpha: float = 0.60,
    beta: float = 0.25,
    gamma: float = 0.15,
) -> Dict[int, float]:
    """Retourne un score où une valeur élevée signifie une priorité élevée.

    Pour `mixte`, alpha/beta/gamma pondèrent respectivement RPW, nombre de
    successeurs et profondeur. Les trois coefficients doivent sommer à 1.
    """
    if regle not in REGLES:
        raise ValueError(f"Règle inconnue : {regle}. Choix : {REGLES}")

    if regle == "aleatoire":
        return {i: rng.random() for i in inst.taches}

    comp = composantes_priorite(inst)
    if regle == "rpw":
        return comp["rpw"]
    if regle == "rpw_normalise":
        return comp["rpw_norm"]
    if regle == "duree":
        return comp["duree"]
    if regle == "nb_successeurs":
        return comp["successeurs"]
    if regle == "profondeur":
        return comp["profondeur_norm"]
    if regle == "mixte":
        if any(x < 0 for x in (alpha, beta, gamma)):
            raise ValueError("Les coefficients alpha, beta et gamma doivent être positifs.")
        if abs(alpha + beta + gamma - 1.0) > 1e-9:
            raise ValueError("Pour la règle mixte, alpha + beta + gamma doit valoir 1.")
        return {
            i: (
                alpha * comp["rpw_norm"][i]
                + beta * comp["successeurs_norm"][i]
                + gamma * comp["profondeur_norm"][i]
            )
            for i in inst.taches
        }
    raise AssertionError("Cas de règle non traité")


def construire(
    inst: Instance,
    regle: str = "rpw",
    departage: str = "indice",
    graine: Optional[int] = None,
    poids_remplissage: float = 0.0,
    alpha: float = 0.60,
    beta: float = 0.25,
    gamma: float = 0.15,
) -> List[List[int]]:
    """Construit une solution réalisable en respectant les précédences.

    `poids_remplissage=0` désactive le critère. Sinon, le score candidat est :
        (1 - poids_remplissage) * priorité_normalisée
        + poids_remplissage * adéquation_au_temps_restant

    L'adéquation vaut 1 lorsque la tâche remplit exactement le temps restant.
    """
    if departage not in DEPARTAGES:
        raise ValueError(f"Départage inconnu : {departage}. Choix : {DEPARTAGES}")
    if not 0.0 <= poids_remplissage <= 1.0:
        raise ValueError("poids_remplissage doit être compris entre 0 et 1.")

    rng = random.Random(graine)
    prio_brute = priorites(inst, regle, rng, alpha, beta, gamma)
    prio = _normaliser(prio_brute)

    # Valeurs aléatoires tirées une seule fois : résultats reproductibles par graine.
    alea = {i: rng.random() for i in inst.taches}
    nb_pred_restants = {i: len(inst.predecesseurs[i]) for i in inst.taches}
    disponibles = {i for i in inst.taches if nb_pred_restants[i] == 0}

    stations: List[List[int]] = [[]]
    reste = inst.c
    places = 0

    while places < inst.n:
        candidats = [i for i in disponibles if inst.duree(i) <= reste]

        if not candidats:
            if not stations[-1]:
                # Une tâche plus longue que le cycle ou un graphe incohérent
                # doit être détecté explicitement plutôt que boucler sans fin.
                raise ValueError(
                    f"{inst.nom}: aucune tâche admissible dans une station vide. "
                    "Vérifier les durées, le cycle et le graphe de précédence."
                )
            stations.append([])
            reste = inst.c
            continue

        def cle(i: int) -> Tuple[float, ...]:
            adequation = 1.0 - (reste - inst.duree(i)) / inst.c
            score = (
                (1.0 - poids_remplissage) * prio[i]
                + poids_remplissage * adequation
            )
            if departage == "indice":
                return (score, -i)
            if departage == "duree":
                return (score, float(inst.duree(i)), -i)
            if departage == "remplissage":
                return (score, adequation, -i)
            return (score, alea[i])

        i = max(candidats, key=cle)
        stations[-1].append(i)
        reste -= inst.duree(i)
        disponibles.remove(i)
        places += 1

        for j in inst.successeurs[i]:
            nb_pred_restants[j] -= 1
            if nb_pred_restants[j] == 0:
                disponibles.add(j)

    return stations


def resoudre(
    inst: Instance,
    regle: str = "rpw",
    departage: str = "indice",
    graine: Optional[int] = None,
    poids_remplissage: float = 0.0,
    alpha: float = 0.60,
    beta: float = 0.25,
    gamma: float = 0.15,
) -> Resultat:
    debut = time.perf_counter()
    stations = construire(
        inst, regle, departage, graine, poids_remplissage, alpha, beta, gamma
    )
    temps = time.perf_counter() - debut
    params = {
        "regle": regle,
        "departage": departage,
        "poids_remplissage": poids_remplissage,
        "alpha": alpha,
        "beta": beta,
        "gamma": gamma,
    }
    if regle == "aleatoire" or departage == "aleatoire":
        params["graine"] = graine
    return Resultat(
        "H1_AMELIOREE", inst.nom, HEURISTIQUE, len(stations), stations, temps, params
    )


if __name__ == "__main__":
    import sys
    from instance import charger
    from verificateur import verifier

    instance = charger(sys.argv[1] if len(sys.argv) > 1 else "Mertens_c6")
    for rule in ("rpw", "rpw_normalise", "profondeur", "mixte"):
        result = resoudre(instance, regle=rule)
        errors = verifier(instance, result.stations, result.nb_stations)
        print(
            f"{instance.nom} | {rule:16s} | {result.nb_stations} stations "
            f"| validation={'OK' if not errors else errors}"
        )
