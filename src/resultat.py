"""Format commun des résultats renvoyés par toutes les méthodes (section 5.2 du plan)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

# Statuts possibles
OPTIMAL = "OPTIMAL"          # méthode complète : optimalité prouvée
FAISABLE = "FAISABLE"        # méthode complète : solution trouvée, optimalité non prouvée
AUCUNE = "AUCUNE"            # aucune solution dans la limite de temps
HEURISTIQUE = "HEURISTIQUE"  # méthode incomplète
STATUTS = (OPTIMAL, FAISABLE, AUCUNE, HEURISTIQUE)


@dataclass
class Resultat:
    methode: str                       # "H1", "M1", ...
    instance: str                      # nom de l'instance
    statut: str                        # un des STATUTS
    nb_stations: int | None            # None si aucune solution
    stations: List[List[int]]          # stations[k] = tâches de la station k+1
    temps_s: float                     # temps de calcul (secondes, horloge murale)
    params: Dict[str, Any] = field(default_factory=dict)  # paramètres utilisés
    infos: Dict[str, Any] = field(default_factory=dict)   # infos libres (borne du solveur, taille du modèle…)

    def __post_init__(self) -> None:
        if self.statut not in STATUTS:
            raise ValueError(f"Statut inconnu : {self.statut}")

    def affectation(self) -> Dict[int, int]:
        """Dictionnaire tâche -> numéro de station (à partir de 1)."""
        return {i: k + 1 for k, st in enumerate(self.stations) for i in st}
