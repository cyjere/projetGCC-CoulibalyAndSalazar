"""Lecture des instances SALBP-1 (socle commun, section 5.1 du plan).

Une instance est décrite par la classe `Instance` :
    nom     : identifiant unique, ex. "Mertens_c6"
    n       : nombre de tâches, numérotées de 1 à n
    c       : temps de cycle
    durees  : tuple de n entiers ; la durée de la tâche i est durees[i - 1]
    arcs    : tuple de couples (i, j) = « i précède directement j »

Deux formats de fichiers sont lus, sans jamais modifier les fichiers de data/ :
    * .IN2  (jeu de Scholl)  : n, puis n durées, puis les arcs "i,j", fin "-1,-1".
                               Le temps de cycle n'est pas dans le fichier : il vient
                               de data/instances.csv.
    * .alb  (jeux d'Otto)    : blocs <number of tasks>, <cycle time>, <task times>,
                               <precedence relations>, <end>. Le fichier peut être lu
                               directement dans l'archive .zip téléchargée, avec la
                               notation "archive.zip#chemin/dans/l/archive.alb".
"""
from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Dict, List, Optional, Tuple

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_DATA = RACINE / "data"
FICHIER_LISTE = DOSSIER_DATA / "instances.csv"


@dataclass(frozen=True)
class Instance:
    nom: str
    n: int
    c: int
    durees: Tuple[int, ...]
    arcs: Tuple[Tuple[int, int], ...]
    # Métadonnées issues de data/instances.csv (facultatives)
    optimum: Optional[int] = None
    categorie: str = ""
    source: str = ""

    # ---------- accès pratiques ----------
    def duree(self, i: int) -> int:
        """Durée de la tâche i (numérotée à partir de 1)."""
        return self.durees[i - 1]

    @property
    def taches(self) -> range:
        return range(1, self.n + 1)

    @cached_property
    def predecesseurs(self) -> Dict[int, List[int]]:
        """Prédécesseurs directs de chaque tâche."""
        p: Dict[int, List[int]] = {i: [] for i in self.taches}
        for i, j in self.arcs:
            p[j].append(i)
        return p

    @cached_property
    def successeurs(self) -> Dict[int, List[int]]:
        """Successeurs directs de chaque tâche."""
        s: Dict[int, List[int]] = {i: [] for i in self.taches}
        for i, j in self.arcs:
            s[i].append(j)
        return s

    @cached_property
    def ordre_topologique(self) -> List[int]:
        """Ordre topologique (Kahn, à égalité la plus petite tâche d'abord)."""
        import heapq

        degre = {i: len(self.predecesseurs[i]) for i in self.taches}
        tas = [i for i in self.taches if degre[i] == 0]
        heapq.heapify(tas)
        ordre: List[int] = []
        while tas:
            i = heapq.heappop(tas)
            ordre.append(i)
            for j in self.successeurs[i]:
                degre[j] -= 1
                if degre[j] == 0:
                    heapq.heappush(tas, j)
        if len(ordre) != self.n:
            raise ValueError(f"{self.nom} : le graphe de précédence contient un circuit")
        return ordre

    @cached_property
    def tous_successeurs(self) -> Dict[int, frozenset]:
        """Successeurs directs et indirects (fermeture transitive)."""
        res: Dict[int, frozenset] = {}
        for i in reversed(self.ordre_topologique):
            ens = set(self.successeurs[i])
            for j in self.successeurs[i]:
                ens |= res[j]
            res[i] = frozenset(ens)
        return res

    @cached_property
    def tous_predecesseurs(self) -> Dict[int, frozenset]:
        """Prédécesseurs directs et indirects."""
        res: Dict[int, frozenset] = {}
        for j in self.ordre_topologique:
            ens = set(self.predecesseurs[j])
            for i in self.predecesseurs[j]:
                ens |= res[i]
            res[j] = frozenset(ens)
        return res

    @property
    def taille(self) -> str:
        """Catégorie de taille selon le protocole (section 6 du plan)."""
        if self.n < 30:
            return "petite"
        if self.n <= 100:
            return "moyenne"
        return "grande"

    def verifier_coherence(self) -> None:
        if len(self.durees) != self.n:
            raise ValueError(f"{self.nom} : {len(self.durees)} durées pour n = {self.n}")
        for i, j in self.arcs:
            if not (1 <= i <= self.n and 1 <= j <= self.n) or i == j:
                raise ValueError(f"{self.nom} : arc invalide ({i}, {j})")
        trop_longues = [i for i in self.taches if self.duree(i) > self.c]
        if trop_longues:
            raise ValueError(f"{self.nom} : tâches plus longues que c = {self.c} : {trop_longues}")
        _ = self.ordre_topologique  # lève une erreur en cas de circuit


# ---------------------------------------------------------------------------
# Lecture des fichiers
# ---------------------------------------------------------------------------
def _ouvrir_texte(chemin: str) -> str:
    """Lit un fichier texte, éventuellement à l'intérieur d'une archive zip.

    `chemin` est relatif à data/ ; la notation "archive.zip#membre" désigne un
    fichier dans une archive.
    """
    if "#" in chemin:
        archive, membre = chemin.split("#", 1)
        with zipfile.ZipFile(DOSSIER_DATA / archive) as z:
            return z.read(membre).decode("latin-1")
    return (DOSSIER_DATA / chemin).read_text(encoding="latin-1")


def lire_in2(texte: str, nom: str, c: int) -> Instance:
    lignes = [l.strip() for l in texte.splitlines() if l.strip()]
    n = int(lignes[0])
    durees = tuple(int(l) for l in lignes[1:n + 1])
    arcs = []
    for l in lignes[n + 1:]:
        i, j = (int(x) for x in l.split(","))
        if i == -1 and j == -1:
            break
        arcs.append((i, j))
    return Instance(nom=nom, n=n, c=c, durees=durees, arcs=tuple(arcs))


def lire_alb(texte: str, nom: str, c: Optional[int] = None) -> Instance:
    blocs: Dict[str, List[str]] = {}
    courant = None
    for l in texte.splitlines():
        l = l.strip()
        if not l:
            continue
        if l.startswith("<") and l.endswith(">"):
            courant = l[1:-1].strip().lower()
            blocs[courant] = []
        elif courant is not None:
            blocs[courant].append(l)
    n = int(blocs["number of tasks"][0])
    c_fichier = int(blocs["cycle time"][0])
    d = {}
    for l in blocs["task times"]:
        i, t = l.split()
        d[int(i)] = int(t)
    durees = tuple(d[i] for i in range(1, n + 1))
    arcs = tuple(tuple(int(x) for x in l.split(",")) for l in blocs.get("precedence relations", []))
    return Instance(nom=nom, n=n, c=c if c else c_fichier, durees=durees, arcs=arcs)  # type: ignore[arg-type]


def lire_fichier(chemin: str, nom: str, c: Optional[int] = None) -> Instance:
    texte = _ouvrir_texte(chemin)
    if chemin.lower().endswith(".alb"):
        return lire_alb(texte, nom, c)
    if c is None:
        raise ValueError("Le format .IN2 ne contient pas le temps de cycle : c est obligatoire")
    return lire_in2(texte, nom, c)


# ---------------------------------------------------------------------------
# Liste des instances (section 5.4 du plan) : data/instances.csv
# Colonnes : nom, source, fichier, c, optimum, categorie
# ---------------------------------------------------------------------------
def charger_liste(fichier: Path = FICHIER_LISTE, filtre: Optional[List[str]] = None) -> List[Instance]:
    """Charge toutes les instances de la liste commune (ou celles dont le nom est dans `filtre`)."""
    res: List[Instance] = []
    with open(fichier, newline="", encoding="utf-8") as f:
        for ligne in csv.DictReader(l for l in f if not l.startswith("#")):
            if filtre and ligne["nom"] not in filtre:
                continue
            inst = lire_fichier(ligne["fichier"], ligne["nom"], int(ligne["c"]))
            opt = ligne.get("optimum", "").strip()
            inst = Instance(
                nom=inst.nom, n=inst.n, c=inst.c, durees=inst.durees, arcs=inst.arcs,
                optimum=int(opt) if opt else None,
                categorie=ligne.get("categorie", "").strip() or inst.taille,
                source=ligne.get("source", "").strip(),
            )
            inst.verifier_coherence()
            res.append(inst)
    return res


def charger(nom: str) -> Instance:
    """Charge une seule instance de la liste par son nom."""
    res = charger_liste(filtre=[nom])
    if not res:
        raise KeyError(f"Instance inconnue : {nom}")
    return res[0]
