"""H1 — Heuristique constructive par règle de priorité (RPW et variantes).

Principe (orienté station) :
  on ouvre la station 1 ; tant qu'il reste des tâches,
    * une tâche est *disponible* si tous ses prédécesseurs directs sont déjà
      placés (dans une station précédente ou dans la station ouverte) et si sa
      durée tient dans le temps restant de la station ouverte ;
    * on place la tâche disponible de plus forte priorité ;
    * si aucune tâche n'est disponible, on ferme la station et on en ouvre une nouvelle.

Paramètres étudiés :
  regle     : "rpw"            poids positionnel = t_i + somme des durées de tous les successeurs
              "duree"          plus grande durée t_i
              "nb_successeurs" nombre de successeurs directs et indirects
              "aleatoire"      priorité tirée au hasard (graine)
  departage : règle de départage des égalités de priorité
              "indice"    plus petit numéro de tâche
              "duree"     plus grande durée, puis plus petit numéro
              "aleatoire" ordre tiré au hasard (graine)
  graine    : graine aléatoire (utile seulement si regle ou departage = "aleatoire")

Complexité : O(n^2) dans cette implémentation simple (au plus n placements,
chacun parcourant les tâches disponibles), plus O(n·|E|) pour calculer les
poids positionnels via la fermeture transitive.
"""
from __future__ import annotations

import random
import time
from typing import Dict, List, Optional, Tuple

from instance import Instance
from resultat import HEURISTIQUE, Resultat

REGLES = ("rpw", "duree", "nb_successeurs", "aleatoire")
DEPARTAGES = ("indice", "duree", "aleatoire")


def priorites(inst: Instance, regle: str, rng: random.Random) -> Dict[int, float]:
    if regle == "rpw":
        return {i: inst.duree(i) + sum(inst.duree(j) for j in inst.tous_successeurs[i]) for i in inst.taches}
    if regle == "duree":
        return {i: inst.duree(i) for i in inst.taches}
    if regle == "nb_successeurs":
        return {i: len(inst.tous_successeurs[i]) for i in inst.taches}
    if regle == "aleatoire":
        return {i: rng.random() for i in inst.taches}
    raise ValueError(f"Règle de priorité inconnue : {regle} (choix : {REGLES})")


def _cles(inst: Instance, regle: str, departage: str, rng: random.Random) -> Dict[int, Tuple]:
    """Clé de tri : plus grande = plus prioritaire."""
    prio = priorites(inst, regle, rng)
    if departage == "indice":
        return {i: (prio[i], -i) for i in inst.taches}
    if departage == "duree":
        return {i: (prio[i], inst.duree(i), -i) for i in inst.taches}
    if departage == "aleatoire":
        return {i: (prio[i], rng.random()) for i in inst.taches}
    raise ValueError(f"Départage inconnu : {departage} (choix : {DEPARTAGES})")


def construire(inst: Instance, regle: str = "rpw", departage: str = "indice",
               graine: Optional[int] = None) -> List[List[int]]:
    """Construit une solution et renvoie la liste des stations."""
    rng = random.Random(graine)
    cle = _cles(inst, regle, departage, rng)
    nb_pred_restants = {i: len(inst.predecesseurs[i]) for i in inst.taches}
    liberees = {i for i in inst.taches if nb_pred_restants[i] == 0}  # prédécesseurs tous placés
    stations: List[List[int]] = [[]]
    reste = inst.c
    places = 0
    while places < inst.n:
        candidates = [i for i in liberees if inst.duree(i) <= reste]
        if not candidates:
            stations.append([])
            reste = inst.c
            continue
        i = max(candidates, key=cle.__getitem__)
        stations[-1].append(i)
        reste -= inst.duree(i)
        liberees.remove(i)
        places += 1
        for j in inst.successeurs[i]:
            nb_pred_restants[j] -= 1
            if nb_pred_restants[j] == 0:
                liberees.add(j)
    return stations


def resoudre(inst: Instance, regle: str = "rpw", departage: str = "indice",
             graine: Optional[int] = None) -> Resultat:
    debut = time.perf_counter()
    stations = construire(inst, regle, departage, graine)
    temps = time.perf_counter() - debut
    params = {"regle": regle, "departage": departage}
    if regle == "aleatoire" or departage == "aleatoire":
        params["graine"] = graine
    return Resultat("H1", inst.nom, HEURISTIQUE, len(stations), stations, temps, params)


def meilleure_solution(inst: Instance) -> Resultat:
    """Meilleure des trois règles déterministes : sert de borne supérieure UB pour M1."""
    debut = time.perf_counter()
    meilleur: Optional[Resultat] = None
    for regle in ("rpw", "duree", "nb_successeurs"):
        r = resoudre(inst, regle, "indice")
        if meilleur is None or r.nb_stations < meilleur.nb_stations:  # type: ignore[operator]
            meilleur = r
    assert meilleur is not None
    meilleur.temps_s = time.perf_counter() - debut
    meilleur.params = {"regle": "meilleure(rpw,duree,nb_successeurs)", "regle_retenue": meilleur.params["regle"],
                       "departage": "indice"}
    return meilleur


if __name__ == "__main__":
    import sys

    from instance import charger
    from verificateur import verifier

    inst = charger(sys.argv[1] if len(sys.argv) > 1 else "Mertens_c6")
    for regle in REGLES:
        r = resoudre(inst, regle, "indice", graine=0)
        print(f"{inst.nom} {regle:15s} -> {r.nb_stations} stations "
              f"(optimum {inst.optimum}) erreurs={verifier(inst, r.stations)}")
