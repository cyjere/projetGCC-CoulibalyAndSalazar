"""Script de benchmark (socle commun) : lance les expériences, vérifie et enregistre les résultats.

Exemples :
    python src/benchmark.py principale                  # H1 (RPW) + M1 (réglages par défaut) sur toutes les instances
    python src/benchmark.py h1_parametres               # toutes les règles de priorité / départages de H1
    python src/benchmark.py m1_parametres               # variations des paramètres de M1 (petites et moyennes instances)
    python src/benchmark.py principale --temps-limite 60 --workers 8 --instances Mertens_c6 Bowman_c20

Chaque expérience écrit resultats/<experience>.csv (une ligne par exécution) et
resultats/solutions/<experience>.jsonl (affectations). Toute solution passe par le
vérificateur commun ; une solution invalide est signalée (valide = 0) et exclue de l'analyse ;
une exécution sans solution (statut AUCUNE) a valide vide et compte comme un échec.
L'option --reprendre saute les exécutions déjà présentes dans le CSV.
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import h1_rpw  # noqa: E402
import m1_cpsat  # noqa: E402
from bornes import borne_inferieure  # noqa: E402
from instance import RACINE, Instance, charger_liste  # noqa: E402
from resultat import Resultat  # noqa: E402
from verificateur import verifier  # noqa: E402

DOSSIER_RES = RACINE / "resultats"
GRAINES = (0, 1, 2, 3, 4)  # au moins 5 graines pour les variantes aléatoires (protocole)

COLONNES = ["experience", "instance", "source", "categorie", "n", "c", "optimum", "lb",
            "methode", "config", "moteur", "params", "graine", "statut", "nb_stations",
            "ecart_opt", "ecart_opt_pct", "ecart_lb", "temps_s", "valide", "erreurs",
            "K", "nb_variables", "nb_contraintes", "borne_solveur"]


def moteur_disponible(demande: str) -> str:
    if demande != "auto":
        return demande
    try:
        import ortools  # noqa: F401
        return "cpsat"
    except ImportError:
        print("ATTENTION : OR-Tools n'est pas installé -> M1 est résolu avec le moteur de secours HiGHS.\n"
              "            Installer OR-Tools (pip install ortools) pour les résultats CP-SAT.", file=sys.stderr)
        return "highs"


# ---------------------------------------------------------------------------
# Définition des expériences : liste de (methode, config, fonction de lancement)
# ---------------------------------------------------------------------------
def taches_principale(a) -> List[Tuple[str, str, Any]]:
    return [
        ("H1", "rpw/indice", lambda inst, g: h1_rpw.resoudre(inst, "rpw", "indice")),
        ("M1", "defaut", lambda inst, g: m1_cpsat.resoudre(
            inst, temps_limite=a.temps_limite, workers=a.workers, moteur=a.moteur)),
    ]


def taches_h1(a) -> List[Tuple[str, str, Any]]:
    res = []
    for regle in h1_rpw.REGLES:
        for dep in h1_rpw.DEPARTAGES:
            if regle == "duree" and dep == "duree":
                continue  # redondant
            res.append(("H1", f"{regle}/{dep}",
                        (lambda r, d: (lambda inst, g: h1_rpw.resoudre(inst, r, d, graine=g)))(regle, dep)))
    return res


def taches_m1(a) -> List[Tuple[str, str, Any]]:
    """Un paramètre varie à la fois autour de la configuration par défaut."""
    base = dict(temps_limite=a.temps_limite, workers=a.workers, strategie="auto", symetrie=True,
                borne_sup="h1", precedence="somme", indice_h1=True, moteur=a.moteur)
    variantes: List[Tuple[str, Dict[str, Any]]] = [
        ("defaut", {}),
        ("sans_symetrie", {"symetrie": False}),
        ("ub_triviale", {"borne_sup": "triviale"}),
        ("precedence_cumul", {"precedence": "cumul"}),
    ]
    if a.moteur == "cpsat":
        variantes += [
            ("sans_indice_h1", {"indice_h1": False}),
            ("workers_1_auto", {"workers": 1, "strategie": "auto"}),
            ("workers_1_fixe", {"workers": 1, "strategie": "fixe"}),
            ("workers_1_portfolio", {"workers": 1, "strategie": "portfolio"}),
            ("workers_4", {"workers": 4}),
            ("temps_10s", {"temps_limite": 10}),
        ]
    res = []
    for nom, delta in variantes:
        kw = {**base, **delta}
        res.append(("M1", nom, (lambda kw: (lambda inst, g: m1_cpsat.resoudre(inst, **kw)))(kw)))
    return res


EXPERIENCES = {"principale": taches_principale, "h1_parametres": taches_h1, "m1_parametres": taches_m1}


def a_graines(methode: str, config: str) -> bool:
    return methode == "H1" and "aleatoire" in config


# ---------------------------------------------------------------------------
def ligne_resultat(exp: str, inst: Instance, config: str, r: Resultat, graine) -> Tuple[Dict[str, Any], Dict]:
    # valide : 1 = solution vérifiée, 0 = solution invalide, vide = pas de solution (statut AUCUNE)
    erreurs = verifier(inst, r.stations, r.nb_stations) if r.nb_stations else []
    valide = not erreurs if r.nb_stations else None
    lb = borne_inferieure(inst)
    m = r.nb_stations if valide else None
    ligne = {
        "experience": exp, "instance": inst.nom, "source": inst.source, "categorie": inst.categorie,
        "n": inst.n, "c": inst.c, "optimum": inst.optimum, "lb": lb, "methode": r.methode, "config": config,
        "moteur": r.params.get("moteur", ""), "params": json.dumps(r.params, ensure_ascii=False),
        "graine": "" if graine is None else graine, "statut": r.statut, "nb_stations": m if m else "",
        "ecart_opt": (m - inst.optimum) if (m and inst.optimum) else "",
        "ecart_opt_pct": round(100 * (m - inst.optimum) / inst.optimum, 3) if (m and inst.optimum) else "",
        "ecart_lb": (m - lb) if m else "", "temps_s": round(r.temps_s, 4), "valide": "" if valide is None else int(valide),
        "erreurs": "" if valide else " | ".join(erreurs)[:300],
        "K": r.infos.get("K", ""), "nb_variables": r.infos.get("nb_variables", ""),
        "nb_contraintes": r.infos.get("nb_contraintes", ""),
        "borne_solveur": r.infos.get("borne_solveur", "") if r.infos.get("borne_solveur") is not None else "",
    }
    sol = {"experience": exp, "instance": inst.nom, "methode": r.methode, "config": config, "graine": graine,
           "statut": r.statut, "valide": valide, "stations": r.stations, "infos": r.infos}
    return ligne, sol


def main(argv: Iterable[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("experience", choices=list(EXPERIENCES))
    ap.add_argument("--instances", nargs="*", help="noms d'instances (défaut : toute la liste)")
    ap.add_argument("--categories", nargs="*", help="petite / moyenne / grande")
    ap.add_argument("--temps-limite", type=float, default=60.0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--moteur", default="auto", choices=["auto", "cpsat", "highs"])
    ap.add_argument("--reprendre", action="store_true", help="ne relance pas les exécutions déjà enregistrées")
    a = ap.parse_args(list(argv) if argv is not None else None)
    a.moteur = moteur_disponible(a.moteur)
    if a.experience == "m1_parametres" and not a.categories and not a.instances:
        a.categories = ["petite", "moyenne"]

    instances = charger_liste(filtre=a.instances)
    if a.categories:
        instances = [i for i in instances if i.categorie in a.categories]
    taches = EXPERIENCES[a.experience](a)

    DOSSIER_RES.mkdir(exist_ok=True)
    (DOSSIER_RES / "solutions").mkdir(exist_ok=True)
    f_csv = DOSSIER_RES / f"{a.experience}.csv"
    f_sol = DOSSIER_RES / "solutions" / f"{a.experience}.jsonl"
    deja = set()
    if a.reprendre and f_csv.exists():
        with open(f_csv, newline="", encoding="utf-8") as f:
            deja = {(l["instance"], l["methode"], l["config"], l["graine"]) for l in csv.DictReader(f)}
        mode = "a"
    else:
        mode = "w"
    with open(f_csv, mode, newline="", encoding="utf-8") as fc, open(f_sol, mode, encoding="utf-8") as fs:
        w = csv.DictWriter(fc, fieldnames=COLONNES)
        if mode == "w" or fc.tell() == 0:
            w.writeheader()
        print(f"# {a.experience} : {len(instances)} instances, moteur M1 = {a.moteur}, "
              f"Python {platform.python_version()}, {platform.machine()}")
        for inst in instances:
            for methode, config, lancer in taches:
                for g in (GRAINES if a_graines(methode, config) else (None,)):
                    if (inst.nom, methode, config, "" if g is None else str(g)) in deja:
                        continue
                    t0 = time.perf_counter()
                    r = lancer(inst, g)
                    ligne, sol = ligne_resultat(a.experience, inst, config, r, g)
                    w.writerow(ligne); fc.flush()
                    fs.write(json.dumps(sol, ensure_ascii=False) + "\n"); fs.flush()
                    print(f"{inst.nom:16s} {methode} {config:22s} g={'' if g is None else g:>2} "
                          f"-> {ligne['nb_stations']!s:>3} (opt {inst.optimum}) {r.statut:11s} "
                          f"{time.perf_counter() - t0:7.2f}s "
                          f"{dict([(1, 'OK'), (0, 'INVALIDE')]).get(ligne['valide'], 'sans solution')}",
                          flush=True)


if __name__ == "__main__":
    main()
