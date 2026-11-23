"""Analyse des résultats : tableaux de synthèse et graphiques (resultats/ et resultats/figures/).

    python src/analyse.py

Lit les CSV produits par benchmark.py (seules les lignes valides sont utilisées) et écrit :
    resultats/synthese_principale.csv        une ligne par instance (H1 et M1 côte à côte)
    resultats/synthese_categories.csv        par méthode et catégorie de taille
    resultats/synthese_h1_parametres.csv     par configuration de H1 (moyenne et meilleur sur les graines)
    resultats/synthese_m1_parametres.csv     par configuration de M1
    resultats/figures/*.png                  graphiques
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from instance import RACINE  # noqa: E402

RES = RACINE / "resultats"
FIG = RES / "figures"
ORDRE_CAT = ["petite", "moyenne", "grande"]
# Couleur fixe par méthode (palette catégorielle validée, ordre fixe)
COULEURS = {"H1": "#2a78d6", "M1": "#eb6834", "M2": "#1baf7a", "H2": "#eda100"}
ENCRE, ENCRE2, GRILLE = "#0b0b0b", "#52514e", "#e4e3df"
NOM_MOTEUR = {"cpsat": "CP-SAT", "highs": "HiGHS"}


def fr(v: float, nd: int = 1) -> str:
    return f"{v:.{nd}f}".replace(".", ",")


def _style(ax, titre, xlabel="", ylabel=""):
    ax.set_title(titre, loc="left", fontsize=12, color=ENCRE, pad=10)
    ax.set_xlabel(xlabel, color=ENCRE2)
    ax.set_ylabel(ylabel, color=ENCRE2)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRILLE)
    ax.tick_params(colors=ENCRE2)
    ax.grid(axis="y", color=GRILLE, linewidth=0.8)
    ax.set_axisbelow(True)


def lire(nom: str) -> pd.DataFrame | None:
    f = RES / f"{nom}.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f)
    invalides = df[df["valide"] == 0]
    if len(invalides):
        print(f"ATTENTION : {len(invalides)} solution(s) invalide(s) exclue(s) de {f.name}")
    # on garde les exécutions sans solution (valide vide, statut AUCUNE) : elles comptent comme des échecs
    return df[df["valide"] != 0].copy()


# ---------------------------------------------------------------------------
def analyse_principale() -> None:
    df = lire("principale")
    if df is None or df.empty:
        return
    moteur = ", ".join(NOM_MOTEUR.get(m, m) for m in sorted(set(df.loc[df.methode == "M1", "moteur"].dropna().astype(str))))
    base = df.drop_duplicates("instance")[["instance", "source", "categorie", "n", "c", "optimum", "lb"]]
    h1 = df[df.methode == "H1"].set_index("instance")
    m1 = df[df.methode == "M1"].set_index("instance")
    t = base.set_index("instance")
    t["H1_stations"] = h1["nb_stations"]
    t["H1_ecart"] = h1["ecart_opt"]
    t["M1_stations"] = m1["nb_stations"]
    t["M1_ecart"] = m1["ecart_opt"]
    t["M1_temps_s"] = m1["temps_s"].round(2)
    t["M1_statut"] = m1["statut"]
    t["M1_moteur"] = m1["moteur"]
    t = t.reset_index()
    t.to_csv(RES / "synthese_principale.csv", index=False)

    lignes = []
    for meth, sous in df.groupby("methode"):
        for cat in ORDRE_CAT + ["toutes"]:
            s = sous if cat == "toutes" else sous[sous.categorie == cat]
            if s.empty:
                continue
            lignes.append({
                "methode": meth, "categorie": cat, "instances": len(s),
                "sans_solution": int(s.nb_stations.isna().sum()),
                "optimum_atteint": int((s.ecart_opt == 0).sum()),
                "pct_optimum_atteint": round(100 * (s.ecart_opt == 0).mean(), 1),
                "optimalite_prouvee": int((s.statut == "OPTIMAL").sum()),
                "ecart_moyen_stations": round(s.ecart_opt.mean(), 2),
                "ecart_moyen_pct": round(s.ecart_opt_pct.mean(), 2),
                "temps_moyen_s": round(s.temps_s.mean(), 3), "temps_max_s": round(s.temps_s.max(), 3),
            })
    cat = pd.DataFrame(lignes)
    cat.to_csv(RES / "synthese_categories.csv", index=False)
    print(cat.to_string(index=False))

    # Figure 1 : écart moyen à l'optimum (%) par catégorie et par méthode
    fig, ax = plt.subplots(figsize=(7, 3.8), dpi=150)
    meths = [m for m in ("H1", "M1", "M2", "H2") if m in set(cat.methode)]
    larg = 0.8 / len(meths)
    for j, m in enumerate(meths):
        s = cat[(cat.methode == m) & (cat.categorie.isin(ORDRE_CAT))].set_index("categorie").reindex(ORDRE_CAT)
        xs = [i + (j - (len(meths) - 1) / 2) * larg for i in range(len(ORDRE_CAT))]
        lab = m + (f" ({moteur})" if m == "M1" and moteur else "")
        barres = ax.bar(xs, s.ecart_moyen_pct.fillna(0), width=larg - 0.04, color=COULEURS[m], label=lab)
        for b, v, ns in zip(barres, s.ecart_moyen_pct, s.sans_solution):
            if pd.notna(v):
                txt = f"{fr(v)} %" + (f"\n+ {int(ns)} sans sol." if ns else "")
                ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.1, txt, ha="center",
                        va="bottom", fontsize=8, color=ENCRE2)
    ax.set_xticks(range(len(ORDRE_CAT)))
    ax.set_xticklabels([f"{c}\n({int(cat[(cat.methode == meths[0]) & (cat.categorie == c)].instances.sum())} inst.)"
                        for c in ORDRE_CAT])
    _style(ax, "Écart moyen à l’optimum connu (instances résolues)", "", "écart (% de l’optimum)")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG / "fig1_ecart_par_categorie.png")
    plt.close(fig)

    # Figure 2 : temps de M1 selon n (échelle log), forme selon le statut
    s = df[df.methode == "M1"]
    fig, ax = plt.subplots(figsize=(7, 3.8), dpi=150)
    for statut, marq in (("OPTIMAL", "o"), ("FAISABLE", "^"), ("AUCUNE", "x")):
        ss = s[s.statut == statut]
        if len(ss):
            ax.scatter(ss.n, ss.temps_s.clip(lower=1e-3), s=40, marker=marq, color=COULEURS["M1"],
                       edgecolor="white" if marq != "x" else None, linewidth=0.8 if marq != "x" else 1.5, label=f"{statut.lower()} ({len(ss)})")
    lim = s.params.str.extract(r'"temps_limite": ([0-9.]+)')[0].astype(float).max()
    if pd.notna(lim):
        ax.axhline(lim, color=ENCRE2, linestyle="--", linewidth=1)
        ax.text(s.n.max(), lim * 1.15, f"limite {lim:.0f} s", ha="right", fontsize=8, color=ENCRE2)
    ax.set_yscale("log")
    _style(ax, f"Temps de calcul de M1 selon la taille ({moteur})", "nombre de tâches n", "temps (s, échelle log)")
    ax.legend(frameon=False, fontsize=9, loc="lower right", title="statut de M1", title_fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG / "fig2_temps_m1.png")
    plt.close(fig)


def analyse_h1() -> None:
    df = lire("h1_parametres")
    if df is None or df.empty:
        return
    # moyenne puis meilleur sur les graines, par instance et configuration
    par_inst = df.groupby(["config", "instance"]).agg(moy=("ecart_opt_pct", "mean"), meil=("ecart_opt_pct", "min"),
                                                       moy_st=("ecart_opt", "mean"))
    s = par_inst.groupby("config").agg(
        ecart_moyen_pct=("moy", "mean"), ecart_meilleur_pct=("meil", "mean"),
        ecart_moyen_stations=("moy_st", "mean"),
        optimum_toujours_atteint=("moy", lambda v: int((v == 0).sum())), instances=("moy", "size"))
    temps = df.groupby("config").temps_s.mean() * 1000
    s["temps_moyen_ms"] = temps.round(3)
    s = s.round(2).sort_values("ecart_moyen_pct")
    s.to_csv(RES / "synthese_h1_parametres.csv")
    print(s.to_string())

    # Figure 3 : écart moyen par règle de priorité (départage par indice), meilleur sur graines en clair
    regles = ["rpw", "duree", "nb_successeurs", "aleatoire"]
    noms = {"rpw": "RPW", "duree": "plus grande\ndurée", "nb_successeurs": "nombre de\nsuccesseurs",
            "aleatoire": "aléatoire\n(5 graines)"}
    fig, ax = plt.subplots(figsize=(7, 3.8), dpi=150)
    vals = [s.loc[f"{r}/indice", "ecart_moyen_pct"] for r in regles]
    barres = ax.bar(range(len(regles)), vals, width=0.55, color=COULEURS["H1"])
    for b, v in zip(barres, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.1, f"{fr(v, 2)} %", ha="center", fontsize=9, color=ENCRE2)
    ax.set_xticks(range(len(regles)))
    ax.set_xticklabels([noms[r] for r in regles])
    _style(ax, "H1 : écart moyen à l’optimum selon la règle de priorité", "", "écart (% de l’optimum)")
    fig.tight_layout()
    fig.savefig(FIG / "fig3_h1_regles.png")
    plt.close(fig)


def analyse_m1() -> None:
    df = lire("m1_parametres")
    if df is None or df.empty:
        return
    g = df.groupby("config")
    s = pd.DataFrame({
        "instances": g.size(),
        "optimalite_prouvee": g.apply(lambda x: int((x.statut == "OPTIMAL").sum())),
        "optimum_atteint": g.apply(lambda x: int((x.ecart_opt == 0).sum())),
        "sans_solution": g.apply(lambda x: int(x.nb_stations.isna().sum())),
        "ecart_moyen_stations": g.ecart_opt.mean().round(3),
        "temps_moyen_s": g.temps_s.mean().round(2),
        "temps_median_s": g.temps_s.median().round(3),
        "variables_moy": g.nb_variables.mean().round(0),
        "contraintes_moy": g.nb_contraintes.mean().round(0),
        "moteur": g.moteur.first(),
    })
    s.to_csv(RES / "synthese_m1_parametres.csv")
    print(s.to_string())

    fig, ax = plt.subplots(figsize=(7, 3.8), dpi=150)
    ordre = list(s.sort_values("temps_moyen_s").index)
    barres = ax.barh(range(len(ordre)), s.loc[ordre, "temps_moyen_s"], height=0.55, color=COULEURS["M1"])
    for b, c in zip(barres, ordre):
        ax.text(b.get_width(), b.get_y() + b.get_height() / 2,
                f"  {s.loc[c, 'optimalite_prouvee']}/{s.loc[c, 'instances']} prouvés", va="center", fontsize=8,
                color=ENCRE2)
    ax.set_yticks(range(len(ordre)))
    ax.set_yticklabels(ordre)
    ax.invert_yaxis()
    _style(ax, f"M1 : temps moyen par configuration ({NOM_MOTEUR.get(s.moteur.iloc[0], s.moteur.iloc[0])})", "temps moyen (s)", "")
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRILLE, linewidth=0.8)
    fig.tight_layout()
    fig.savefig(FIG / "fig4_m1_parametres.png")
    plt.close(fig)


if __name__ == "__main__":
    FIG.mkdir(parents=True, exist_ok=True)
    analyse_principale()
    analyse_h1()
    analyse_m1()
