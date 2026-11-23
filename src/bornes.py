"""Bornes inférieures du SALBP-1 (section 2 du plan).

LB1 = ceil(somme des durées / c)
LB2 = nombre de tâches de durée > c/2  +  ceil(nombre de tâches de durée = c/2 / 2)
      (deux tâches de durée > c/2 ne partagent jamais une station ; deux tâches
       de durée exactement c/2 peuvent en partager une : elles comptent pour 1/2)
LB  = max(LB1, LB2)

La borne supérieure UB est la meilleure solution de H1 (voir h1_rpw.meilleure_solution).
"""
from __future__ import annotations

from instance import Instance


def lb1(inst: Instance) -> int:
    return -(-sum(inst.durees) // inst.c)  # division entière arrondie au supérieur


def lb2(inst: Instance) -> int:
    grandes = sum(1 for t in inst.durees if 2 * t > inst.c)
    moities = sum(1 for t in inst.durees if 2 * t == inst.c)
    return grandes + (moities + 1) // 2


def borne_inferieure(inst: Instance) -> int:
    return max(lb1(inst), lb2(inst))
