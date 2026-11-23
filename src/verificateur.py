"""Vérificateur commun (section 5.3 du plan).

Toute solution passe ici avant d'être enregistrée. On contrôle :
  1. chaque tâche est placée exactement une fois (et aucune tâche inconnue) ;
  2. la charge de chaque station est au plus c ;
  3. pour chaque arc (i, j), station(i) <= station(j) ;
  4. aucune station vide (les stations sont numérotées 1..m sans trou) ;
  5. le nombre de stations annoncé correspond à la solution.
La fonction est volontairement indépendante du code des méthodes.
"""
from __future__ import annotations

from typing import List, Optional

from instance import Instance


def verifier(inst: Instance, stations: List[List[int]], nb_annonce: Optional[int] = None) -> List[str]:
    """Renvoie la liste des erreurs (liste vide = solution valide)."""
    erreurs: List[str] = []
    station_de = {}
    for k, st in enumerate(stations, start=1):
        if not st:
            erreurs.append(f"station {k} vide")
        for i in st:
            if not (1 <= i <= inst.n):
                erreurs.append(f"tâche inconnue {i} en station {k}")
            elif i in station_de:
                erreurs.append(f"tâche {i} placée deux fois (stations {station_de[i]} et {k})")
            else:
                station_de[i] = k
        charge = sum(inst.duree(i) for i in st if 1 <= i <= inst.n)
        if charge > inst.c:
            erreurs.append(f"station {k} : charge {charge} > c = {inst.c}")
    manquantes = [i for i in inst.taches if i not in station_de]
    if manquantes:
        erreurs.append(f"tâches non placées : {manquantes[:10]}{'…' if len(manquantes) > 10 else ''}")
    for i, j in inst.arcs:
        if i in station_de and j in station_de and station_de[i] > station_de[j]:
            erreurs.append(f"précédence violée : {i} (station {station_de[i]}) avant {j} (station {station_de[j]})")
    if nb_annonce is not None and nb_annonce != len(stations):
        erreurs.append(f"nombre de stations annoncé {nb_annonce} ≠ {len(stations)}")
    return erreurs


def est_valide(inst: Instance, stations: List[List[int]], nb_annonce: Optional[int] = None) -> bool:
    return not verifier(inst, stations, nb_annonce)
