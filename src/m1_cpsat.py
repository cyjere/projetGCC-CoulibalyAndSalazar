"""M1 — Méthode complète : modèle d'affectation directe résolu par OR-Tools CP-SAT.

Modèle (K = nombre de stations candidates, k = 1..K) :
  variables   x[i,k] ∈ {0,1}  = 1 si la tâche i est dans la station k
              y[k]   ∈ {0,1}  = 1 si la station k est utilisée
  contraintes (1) Σ_k x[i,k] = 1                      pour toute tâche i
              (2) Σ_i t_i·x[i,k] ≤ c·y[k]              pour toute station k
              (3) précédences, pour tout arc (i, j) :
                    "somme"  : Σ_k k·x[i,k] ≤ Σ_k k·x[j,k]          (1 contrainte par arc)
                    "cumul"  : x[j,k] ≤ Σ_{l≤k} x[i,l]  pour tout k  (K contraintes par arc,
                               relaxation plus forte, modèle plus gros)
              (4) cassage de symétrie (optionnel) : y[k+1] ≤ y[k]
              (5) Σ_k y[k] ≥ LB  (borne inférieure, toujours ajoutée)
  objectif    minimiser Σ_k y[k]

Taille : n·K + K booléens ; n + K + 1 contraintes, plus |E| (somme) ou |E|·K (cumul),
plus K − 1 avec le cassage de symétrie.

Paramètres étudiés :
  temps_limite : limite de temps en secondes (défaut 60)
  workers      : nombre de workers CP-SAT (défaut 8)
  strategie    : "auto"      recherche automatique de CP-SAT (défaut)
                 "fixe"      FIXED_SEARCH : branchement sur les x[i,k] dans l'ordre
                             topologique des tâches puis des stations, valeur 1 d'abord
                             (revient à essayer de placer chaque tâche au plus tôt)
                 "portfolio" PORTFOLIO_SEARCH
                 Remarque : avec plusieurs workers, CP-SAT fait tourner un portefeuille de
                 stratégies ; l'effet de ce paramètre se lit surtout avec workers = 1.
  symetrie     : True/False — contrainte (4)
  borne_sup    : "h1" (K = meilleure solution de H1) ou "triviale" (K = n)
  precedence   : "somme" ou "cumul" — écriture de la contrainte (3)
  indice_h1    : True/False — la solution H1 est donnée à CP-SAT comme point de départ (hint)

Moteur de secours :
  moteur="highs" résout exactement le même modèle linéaire en nombres entiers avec HiGHS
  (via scipy.optimize.milp). Il sert uniquement à tester le modèle quand OR-Tools n'est pas
  installé ; les paramètres workers, strategie et indice_h1 n'ont alors pas d'effet.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from bornes import borne_inferieure
from h1_rpw import meilleure_solution
from instance import Instance
from resultat import AUCUNE, FAISABLE, OPTIMAL, Resultat

STRATEGIES = ("auto", "fixe", "portfolio")


def _stations_depuis(station_de: Dict[int, int]) -> List[List[int]]:
    """Regroupe les tâches par station et renumérote 1..m sans trou."""
    par_k: Dict[int, List[int]] = {}
    for i, k in station_de.items():
        par_k.setdefault(k, []).append(i)
    return [sorted(par_k[k]) for k in sorted(par_k)]


def taille_modele(inst: Instance, K: int, symetrie: bool, precedence: str) -> Dict[str, int]:
    nb_var = inst.n * K + K
    nb_ctr = inst.n + K + 1 + (len(inst.arcs) if precedence == "somme" else len(inst.arcs) * K)
    if symetrie:
        nb_ctr += K - 1
    return {"K": K, "nb_variables": nb_var, "nb_contraintes": nb_ctr}


def resoudre(inst: Instance, temps_limite: float = 60.0, workers: int = 8, strategie: str = "auto",
             symetrie: bool = True, borne_sup: str = "h1", precedence: str = "somme",
             indice_h1: bool = True, moteur: str = "cpsat", graine: int = 0,
             journal: bool = False) -> Resultat:
    debut = time.perf_counter()
    h1 = meilleure_solution(inst)
    lb = borne_inferieure(inst)
    if borne_sup == "h1":
        K = h1.nb_stations
    elif borne_sup == "triviale":
        K = inst.n
    else:
        raise ValueError("borne_sup doit valoir 'h1' ou 'triviale'")
    if precedence not in ("somme", "cumul"):
        raise ValueError("precedence doit valoir 'somme' ou 'cumul'")
    params: Dict[str, Any] = {"moteur": moteur, "temps_limite": temps_limite, "symetrie": symetrie,
                              "borne_sup": borne_sup, "precedence": precedence}
    if moteur == "cpsat":
        params.update({"workers": workers, "strategie": strategie, "indice_h1": indice_h1})
        statut, station_de, borne, extra = _cpsat(inst, K, lb, temps_limite, workers, strategie, symetrie,
                                                  precedence, h1 if indice_h1 else None, graine, journal)
    elif moteur == "highs":
        statut, station_de, borne, extra = _highs(inst, K, lb, temps_limite, symetrie, precedence, journal)
    else:
        raise ValueError("moteur doit valoir 'cpsat' ou 'highs'")
    temps = time.perf_counter() - debut
    stations = _stations_depuis(station_de) if station_de else []
    infos = taille_modele(inst, K, symetrie, precedence)
    infos.update({"lb": lb, "ub_h1": h1.nb_stations, "borne_solveur": borne})
    infos.update(extra)
    # Si la solution atteint la borne inférieure, l'optimalité est prouvée quel que soit le statut.
    if stations and statut == FAISABLE and len(stations) <= lb:
        statut = OPTIMAL
    return Resultat("M1", inst.nom, statut, len(stations) if stations else None, stations, temps, params, infos)


# ---------------------------------------------------------------------------
# Moteur principal : OR-Tools CP-SAT
# ---------------------------------------------------------------------------
def _cpsat(inst: Instance, K: int, lb: int, temps_limite: float, workers: int, strategie: str,
           symetrie: bool, precedence: str, h1: Optional[Resultat], graine: int, journal: bool):
    from ortools.sat import sat_parameters_pb2
    from ortools.sat.python import cp_model

    SP = sat_parameters_pb2.SatParameters

    m = cp_model.CpModel()
    T, S = list(inst.taches), range(1, K + 1)
    x = {(i, k): m.NewBoolVar(f"x_{i}_{k}") for i in T for k in S}
    y = {k: m.NewBoolVar(f"y_{k}") for k in S}

    for i in T:                                                   # (1)
        m.AddExactlyOne(x[i, k] for k in S)
    for k in S:                                                   # (2)
        m.Add(sum(inst.duree(i) * x[i, k] for i in T) <= inst.c * y[k])
    for (i, j) in inst.arcs:                                      # (3)
        if precedence == "somme":
            m.Add(sum(k * x[i, k] for k in S) <= sum(k * x[j, k] for k in S))
        else:
            for k in S:
                m.Add(x[j, k] <= sum(x[i, l] for l in range(1, k + 1)))
    if symetrie:                                                  # (4)
        for k in range(1, K):
            m.Add(y[k + 1] <= y[k])
    m.Add(sum(y.values()) >= lb)                                  # (5)
    m.Minimize(sum(y.values()))

    if h1 is not None:  # point de départ : la solution H1
        aff = h1.affectation()
        for i in T:
            for k in S:
                m.AddHint(x[i, k], 1 if aff[i] == k else 0)
        for k in S:
            m.AddHint(y[k], 1 if k <= h1.nb_stations else 0)

    if strategie == "fixe":
        ordre = [x[i, k] for i in inst.ordre_topologique for k in S]
        m.AddDecisionStrategy(ordre, cp_model.CHOOSE_FIRST, cp_model.SELECT_MAX_VALUE)

    solveur = cp_model.CpSolver()
    p = solveur.parameters
    p.max_time_in_seconds = float(temps_limite)
    p.num_workers = int(workers)
    p.random_seed = int(graine)
    p.log_search_progress = journal
    if strategie == "fixe":
        p.search_branching = SP.FIXED_SEARCH
    elif strategie == "portfolio":
        p.search_branching = SP.PORTFOLIO_SEARCH
    elif strategie != "auto":
        raise ValueError(f"strategie inconnue : {strategie} (choix : {STRATEGIES})")

    code = solveur.Solve(m)
    if code == cp_model.OPTIMAL:
        statut = OPTIMAL
    elif code == cp_model.FEASIBLE:
        statut = FAISABLE
    else:
        statut = AUCUNE
    station_de: Dict[int, int] = {}
    if code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for i in T:
            for k in S:
                if solveur.BooleanValue(x[i, k]):
                    station_de[i] = k
    extra = {"statut_solveur": solveur.StatusName(code), "branches": solveur.NumBranches(),
             "conflits": solveur.NumConflicts()}
    borne = solveur.BestObjectiveBound() if code in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
    return statut, station_de, borne, extra


# ---------------------------------------------------------------------------
# Moteur de secours : HiGHS (scipy.optimize.milp), même modèle
# ---------------------------------------------------------------------------
def _highs(inst: Instance, K: int, lb: int, temps_limite: float, symetrie: bool, precedence: str,
           journal: bool):
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import lil_matrix

    n = inst.n
    nv = n * K + K

    def X(i: int, k: int) -> int:  # i, k à partir de 1
        return (i - 1) * K + (k - 1)

    def Y(k: int) -> int:
        return n * K + (k - 1)

    lignes: List[Dict[int, float]] = []
    bas: List[float] = []
    haut: List[float] = []

    def ajouter(coefs: Dict[int, float], lo: float, hi: float) -> None:
        lignes.append(coefs); bas.append(lo); haut.append(hi)

    for i in inst.taches:                                          # (1)
        ajouter({X(i, k): 1.0 for k in range(1, K + 1)}, 1, 1)
    for k in range(1, K + 1):                                      # (2)
        co = {X(i, k): float(inst.duree(i)) for i in inst.taches}
        co[Y(k)] = -float(inst.c)
        ajouter(co, -np.inf, 0)
    for (i, j) in inst.arcs:                                       # (3)
        if precedence == "somme":
            co: Dict[int, float] = {}
            for k in range(1, K + 1):
                co[X(i, k)] = co.get(X(i, k), 0) + k
                co[X(j, k)] = co.get(X(j, k), 0) - k
            ajouter(co, -np.inf, 0)
        else:
            for k in range(1, K + 1):
                co = {X(j, k): 1.0}
                for l in range(1, k + 1):
                    co[X(i, l)] = -1.0
                ajouter(co, -np.inf, 0)
    if symetrie:                                                   # (4)
        for k in range(1, K):
            ajouter({Y(k + 1): 1.0, Y(k): -1.0}, -np.inf, 0)
    ajouter({Y(k): 1.0 for k in range(1, K + 1)}, lb, np.inf)     # (5)

    A = lil_matrix((len(lignes), nv))
    for r, co in enumerate(lignes):
        for v, a in co.items():
            A[r, v] = a
    obj = np.zeros(nv)
    obj[n * K:] = 1.0
    res = milp(obj, constraints=LinearConstraint(A.tocsr(), np.array(bas), np.array(haut)),
               integrality=np.ones(nv), bounds=Bounds(0, 1),
               options={"time_limit": float(temps_limite), "disp": journal})
    station_de: Dict[int, int] = {}
    if res.x is not None:
        for i in inst.taches:
            for k in range(1, K + 1):
                if res.x[X(i, k)] > 0.5:
                    station_de[i] = k
    if res.status == 0 and res.x is not None:
        statut = OPTIMAL
    elif res.x is not None:
        statut = FAISABLE
    else:
        statut = AUCUNE
    borne = getattr(res, "mip_dual_bound", None)
    borne = None if borne is None or not np.isfinite(borne) else float(borne)
    extra = {"statut_solveur": f"highs:{res.status}:{res.message}", "noeuds": getattr(res, "mip_node_count", None)}
    return statut, station_de, borne, extra


if __name__ == "__main__":
    import argparse

    from instance import charger
    from verificateur import verifier

    ap = argparse.ArgumentParser(description="Résout une instance avec M1")
    ap.add_argument("instance", nargs="?", default="Mertens_c6")
    ap.add_argument("--moteur", default="cpsat", choices=["cpsat", "highs"])
    ap.add_argument("--temps-limite", type=float, default=60)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--strategie", default="auto", choices=STRATEGIES)
    ap.add_argument("--sans-symetrie", action="store_true")
    ap.add_argument("--borne-sup", default="h1", choices=["h1", "triviale"])
    ap.add_argument("--precedence", default="somme", choices=["somme", "cumul"])
    a = ap.parse_args()
    inst = charger(a.instance)
    r = resoudre(inst, a.temps_limite, a.workers, a.strategie, not a.sans_symetrie, a.borne_sup,
                 a.precedence, moteur=a.moteur)
    print(f"{inst.nom}: {r.statut} {r.nb_stations} stations (optimum {inst.optimum}) en {r.temps_s:.2f}s")
    print("infos :", r.infos)
    print("erreurs :", verifier(inst, r.stations))
