"""Tests rapides du socle commun, de H1 et de M1 :  python src/test_socle.py

Vérifie la lecture de toutes les instances, les bornes (LB ≤ optimum), le vérificateur
(il doit refuser des solutions fausses construites exprès), H1 (solution valide, ≥ optimum)
et M1 sur de petites instances (optimum retrouvé et prouvé).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import h1_rpw  # noqa: E402
import m1_cpsat  # noqa: E402
from bornes import borne_inferieure, lb1, lb2  # noqa: E402
from instance import Instance, charger, charger_liste  # noqa: E402
from verificateur import verifier  # noqa: E402


def test_lecture_et_bornes() -> None:
    insts = charger_liste()
    assert len(insts) >= 15
    for i in insts:
        assert i.optimum is None or borne_inferieure(i) <= i.optimum, i.nom
    m = charger("Mertens_c6")
    assert (m.n, m.c, m.durees) == (7, 6, (1, 5, 4, 3, 5, 6, 5))
    assert (1, 2) in m.arcs and lb1(m) == 5 and lb2(m) == 6


def test_verificateur() -> None:
    inst = Instance("jouet", 3, 10, (6, 5, 4), ((1, 2),))
    assert verifier(inst, [[1, 3], [2]]) == []
    assert verifier(inst, [[1, 2], [3]])            # capacité dépassée (11 > 10)
    assert verifier(inst, [[2], [1, 3]])            # précédence 1 -> 2 violée
    assert verifier(inst, [[1], [2]])               # tâche 3 manquante
    assert verifier(inst, [[1, 3], [2, 3]])         # tâche 3 placée deux fois
    assert verifier(inst, [[1, 3], [], [2]])        # station vide
    assert verifier(inst, [[1, 3], [2]], nb_annonce=3)


def test_h1() -> None:
    for inst in charger_liste():
        for regle in h1_rpw.REGLES:
            r = h1_rpw.resoudre(inst, regle, "indice", graine=0)
            assert verifier(inst, r.stations, r.nb_stations) == [], (inst.nom, regle)
            assert inst.optimum is None or r.nb_stations >= inst.optimum


def test_m1() -> None:
    try:
        import ortools  # noqa: F401
        moteur = "cpsat"
    except ImportError:
        moteur = "highs"
    for nom in ("Mertens_c6", "Jackson_c7", "Mansoor_c48", "Otto20_59"):
        inst = charger(nom)
        for sym in (True, False):
            for prec in ("somme", "cumul"):
                r = m1_cpsat.resoudre(inst, temps_limite=30, workers=2, symetrie=sym, precedence=prec, moteur=moteur)
                assert verifier(inst, r.stations, r.nb_stations) == [], nom
                assert r.statut == "OPTIMAL" and r.nb_stations == inst.optimum, (nom, r.statut, r.nb_stations)
    if moteur == "cpsat":
        inst = charger("Jackson_c7")
        for strat in m1_cpsat.STRATEGIES:
            r = m1_cpsat.resoudre(inst, temps_limite=30, workers=1, strategie=strat)
            assert r.statut == "OPTIMAL" and r.nb_stations == inst.optimum, strat
    print(f"  (M1 testé avec le moteur {moteur})")


if __name__ == "__main__":
    for f in (test_lecture_et_bornes, test_verificateur, test_h1, test_m1):
        f()
        print(f"OK  {f.__name__}")
