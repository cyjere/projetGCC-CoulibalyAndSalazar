"""Remplit la présentation mi-parcours avec les résultats de resultats/ (à relancer après chaque campagne).

    python src/benchmark.py principale && python src/analyse.py && python src/maj_presentation.py

Met à jour, dans docs/SALBP_Presentation_Mi_Parcours.pptx :
  * diapo « M1 : affectation directe » : la ligne « État » ;
  * diapo « Premiers résultats : M1 et H1 » : le tableau (instances représentatives) et la note dessous ;
  * diapo « Premiers résultats : vue d'ensemble » (créée si absente) : figure 1 et constats chiffrés.
Le script est idempotent : on peut le relancer autant de fois que nécessaire.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.util import Emu

sys.path.insert(0, str(Path(__file__).resolve().parent))
from instance import RACINE  # noqa: E402

PPTX = RACINE / "docs" / "SALBP_Presentation_Mi_Parcours.pptx"
RES = RACINE / "resultats"
REPRESENTATIVES = ["Jackson_c7", "Buxey_c27", "Gunther_c41", "Warnecke_c54", "Arcus2_c5755", "Scholl_c1394"]
TITRE_SYNTHESE = "Premiers résultats : vue d’ensemble"
STATUT_FR = {"OPTIMAL": "optimal", "FAISABLE": "faisable", "AUCUNE": "aucune"}


def fr(x: float, nd: int = 1) -> str:
    return f"{x:.{nd}f}".replace(".", ",")


def slide_par_titre(prs, debut):
    for s in prs.slides:
        for sh in s.shapes:
            if sh.has_text_frame and sh.text_frame.text.strip().startswith(debut):
                return s
    return None


def shape(slide, nom):
    return next(s for s in slide.shapes if s.name == nom)


def ecrire(tf, lignes):
    """Remplace le texte d'un cadre en gardant le format du premier run de chaque paragraphe modèle."""
    paras = tf.paragraphs
    modele = copy.deepcopy(paras[0]._p)
    for p in paras[1:]:
        p._p.getparent().remove(p._p)
    p0 = tf.paragraphs[0]
    for i, txt in enumerate(lignes):
        if i == 0:
            p = p0
        else:
            el = copy.deepcopy(modele)
            tf._txBody.append(el)
            p = tf.paragraphs[-1]
        runs = p.runs
        for r in runs[1:]:
            r._r.getparent().remove(r._r)
        if runs:
            runs[0].text = txt
        else:
            p.add_run().text = txt


def cellule(cell, txt, entete=False):
    """Écrit dans une cellule du tableau au format du modèle (Calibri 11 pt)."""
    from pptx.dml.color import RGBColor
    from pptx.util import Pt

    p = cell.text_frame.paragraphs[0]
    for r in p.runs[1:]:
        r._r.getparent().remove(r._r)
    run = p.runs[0] if p.runs else p.add_run()
    run.text = txt
    if not entete:
        f = run.font
        f.size, f.italic, f.name = Pt(11), False, "Calibri"
        f.color.rgb = RGBColor(0x26, 0x32, 0x38)


def main() -> None:
    synth = pd.read_csv(RES / "synthese_principale.csv")
    cat = pd.read_csv(RES / "synthese_categories.csv")
    moteur = ", ".join(sorted(set(synth.M1_moteur.dropna())))
    nom_moteur = "CP-SAT" if moteur == "cpsat" else "HiGHS (moteur de secours)" if moteur == "highs" else moteur
    tot = cat[cat.categorie == "toutes"].set_index("methode")
    N = int(tot.loc["H1", "instances"])
    h1, m1 = tot.loc["H1"], tot.loc["M1"]
    lim = 60

    prs = Presentation(PPTX)

    # --- Diapo M1 : état
    s = slide_par_titre(prs, "M1 : affectation directe")
    t = shape(s, "Text 17")
    ecrire(t.text_frame, ["Minimiser Σ yₖ", "",
                          f"État : implémenté et testé. {int(m1.optimalite_prouvee)}/{N} instances résolues "
                          f"à l’optimalité prouvée en moins de {lim} s ({nom_moteur})."])

    # --- Diapo tableau
    s = slide_par_titre(prs, "Premiers résultats : M1 et H1")
    tab = next(sh for sh in s.shapes if sh.has_table).table
    lignes = synth.set_index("instance").loc[REPRESENTATIVES].reset_index()
    for r, (_, l) in enumerate(lignes.iterrows(), start=1):
        vals = [l.instance.rsplit("_c", 1)[0],
                str(int(l.n)), str(int(l.c)), str(int(l.optimum)),
                str(int(l.M1_stations)) if pd.notna(l.M1_stations) else "—",
                fr(l.M1_temps_s, 2), STATUT_FR.get(l.M1_statut, l.M1_statut),
                str(int(l.H1_stations))]
        for k, v in enumerate(vals):
            cellule(tab.cell(r, k), v)
    cellule(tab.cell(0, 0), "Instance", entete=True)
    note = shape(s, "Text 3")
    ecrire(note.text_frame, [
        f"Sélection de 6 instances sur {N} (tableau complet : resultats/synthese_principale.csv). "
        f"M1 : {nom_moteur}, limite {lim} s ; H1 : règle RPW. Toutes les solutions ont passé le vérificateur."])
    for r in note.text_frame.paragraphs[0].runs:
        r.font.italic = True

    # --- Diapo de synthèse (créée si absente)
    s_syn = slide_par_titre(prs, TITRE_SYNTHESE)
    if s_syn is None:
        s_syn = creer_slide_synthese(prs, s)
    pic = [sh for sh in s_syn.shapes if sh.shape_type == 13]
    for p in pic:
        p._element.getparent().remove(p._element)
    s_syn.shapes.add_picture(str(RES / "figures" / "fig1_ecart_par_categorie.png"), Emu(457200), Emu(1234440),
                             width=Emu(5120640))
    corps = shape(s_syn, "Retenir corps")
    h1_ms = cat[(cat.methode == "H1") & (cat.categorie == "toutes")].temps_moyen_s.iloc[0] * 1000
    ecrire(corps.text_frame, [
        f"H1 atteint l’optimum sur {int(h1.optimum_atteint)}/{N} instances, écart moyen "
        f"{fr(h1.ecart_moyen_pct)} % (< {max(1, round(h1_ms + 0.5))} ms en moyenne).",
        f"M1 atteint l’optimum sur {int(m1.optimum_atteint)}/{N} et le prouve sur "
        f"{int(m1.optimalite_prouvee)}/{N} ; écart moyen {fr(m1.ecart_moyen_pct)} %.",
        texte_echecs(synth),
    ])
    prs.save(PPTX)
    print(f"Présentation mise à jour : {PPTX} (moteur M1 : {nom_moteur})")


def texte_echecs(synth: pd.DataFrame) -> str:
    e = synth[synth.M1_statut != "OPTIMAL"].sort_values("n")
    if e.empty:
        return "M1 prouve l’optimalité sur toutes les instances."
    noms = ", ".join(i.split("_")[0] for i in e.instance)
    return f"Optimalité non prouvée en {60} s : {noms} (toutes avec n ≥ {int(e.n.min())})."


def creer_slide_synthese(prs, s_tab):
    """Nouvelle diapo après le tableau : titre + étiquette « Ensemble » + figure + carte « À retenir »."""
    s = prs.slides.add_slide(s_tab.slide_layout)
    for ph in list(s.placeholders):
        if ph.placeholder_format.type != 13:  # garder le numéro de diapo
            ph._element.getparent().remove(ph._element)
    arbre = s.shapes._spTree
    for sh in s_tab.shapes:
        if sh.name in ("Text 1", "speaker", "Text 2", "Slide Number Placeholder 0"):
            arbre.append(copy.deepcopy(sh._element))
    shape(s, "Text 1").text_frame.paragraphs[0].runs[0].text = TITRE_SYNTHESE
    # Carte « À retenir » copiée de la diapo « Complexité et bornes » (troisième carte)
    s_cartes = slide_par_titre(prs, "Complexité et bornes")
    dx = 5852160 - shape(s_cartes, "Shape 13").left
    for nom, nouveau in (("Shape 13", "Retenir fond"), ("Text 16", "Retenir titre"), ("Text 17", "Retenir corps")):
        el = copy.deepcopy(shape(s_cartes, nom)._element)
        arbre.append(el)
        sh = s.shapes[-1]
        sh.name = nouveau
        sh.left = sh.left + dx - (502920 if nom == "Text 16" else 0)
        sh.width = 2834640 if nom == "Shape 13" else 2468880
    shape(s, "Retenir titre").text_frame.paragraphs[0].runs[0].text = "À retenir"
    # placer la diapo juste après le tableau
    lst = prs.slides._sldIdLst
    ids = list(lst)
    pos = [i for i, sl in enumerate(prs.slides) if sl == s_tab][0]
    el = ids[-1]
    lst.remove(el)
    lst.insert(pos + 1, el)
    # notes
    ns = s.notes_slide
    if ns.notes_text_frame is None and s_tab.has_notes_slide:
        for sh in s_tab.notes_slide.placeholders:
            if sh.placeholder_format.type == 2:  # corps des notes
                ns.shapes._spTree.append(copy.deepcopy(sh._element))
    if ns.notes_text_frame is not None:
        ns.notes_text_frame.text = ("Commenter la figure : écart moyen à l’optimum par taille d’instance "
                                           "pour H1 et M1, puis les trois constats chiffrés.")
    return s


if __name__ == "__main__":
    main()
