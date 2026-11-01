"""
generer_plan.py - Coupe horizontale (plan) d'un modèle IFC, exportée en SVG.

Le script lit le fichier IFC, "coupe" tous les éléments à une hauteur donnée
(1,50 m par défaut) et dessine le résultat vu de dessus : murs, baies, porte.
Un mur percé par une ouverture est dessiné avec son trou.

Limite : il ne sait lire que les éléments extrudés depuis un rectangle, ce qui
est le cas de tout ce que produit scripts/creer_conteneur.py. Il ne lit pas les
maillages faits à la main dans Blender (version 1 du projet).

Usage (depuis la racine du projet, venv activé) :
    python scripts/generer_plan.py
    python scripts/generer_plan.py models/autre.ifc --hauteur 1.2 --sortie docs/plan.svg
"""

import argparse
import os
import re
from collections import Counter

import numpy as np
import ifcopenshell
import ifcopenshell.util.placement
from shapely.geometry import Polygon
from shapely.ops import unary_union

FICHIER_PAR_DEFAUT = "models/compute-container-20ft-v2.ifc"
SORTIE_PAR_DEFAUT = "docs/plan-coupe.svg"

ECHELLE = 150   # pixels par mètre dans le SVG
MARGE = 60      # marge autour du dessin, en pixels

# Couleurs par classe IFC : (remplissage, contour)
STYLES = {
    "IfcWall": ("#9aa0a6", "#202124"),
    "IfcBuildingElementProxy": ("#3c4043", "#202124"),
    "IfcDoor": ("#e8a33d", "#202124"),
    "IfcAirTerminal": ("#4fa3b8", "#202124"),
}
STYLE_PAR_DEFAUT = ("#bdc1c6", "#202124")


def empreinte(element):
    """
    Retourne (polygone_XY, z_min, z_max) pour un élément extrudé depuis un
    rectangle, ou None si l'élément n'a pas cette forme.
    On suppose une extrusion verticale (axe Z), sans élément incliné.
    """
    if element.Representation is None:
        return None
    for representation in element.Representation.Representations:
        for item in representation.Items:
            if not item.is_a("IfcExtrudedAreaSolid"):
                continue
            if not item.SweptArea.is_a("IfcRectangleProfileDef"):
                continue

            # Matrice 4x4 de l'élément dans le monde, puis position de la forme
            matrice = ifcopenshell.util.placement.get_local_placement(element.ObjectPlacement)
            if item.Position is not None:
                matrice = matrice @ ifcopenshell.util.placement.get_axis2placement(item.Position)

            # Les 4 coins du rectangle (dans le plan du profil), passés dans le monde
            demi_x = item.SweptArea.XDim / 2
            demi_y = item.SweptArea.YDim / 2
            coins = [(-demi_x, -demi_y), (demi_x, -demi_y), (demi_x, demi_y), (-demi_x, demi_y)]
            points = [(matrice @ np.array([cx, cy, 0.0, 1.0]))[:2] for cx, cy in coins]

            z_min = float(matrice[2][3])
            z_max = z_min + float(item.Depth)
            return Polygon([(float(p[0]), float(p[1])) for p in points]), z_min, z_max
    return None


def couper(modele, hauteur):
    """Retourne la liste (élément, polygone) des éléments traversés par le plan Z = hauteur."""
    # Ouvertures par mur : {id du mur: [(polygone, z_min, z_max), ...]}
    ouvertures = {}
    for relation in modele.by_type("IfcRelVoidsElement"):
        resultat = empreinte(relation.RelatedOpeningElement)
        if resultat:
            ouvertures.setdefault(relation.RelatingBuildingElement.id(), []).append(resultat)

    formes = []
    for element in modele.by_type("IfcElement"):
        if element.is_a("IfcOpeningElement"):
            continue                        # les ouvertures ne se dessinent pas
        resultat = empreinte(element)
        if resultat is None:
            continue
        polygone, z_min, z_max = resultat
        if not (z_min <= hauteur <= z_max):
            continue                        # l'élément n'est pas traversé par la coupe

        # On retire du mur les ouvertures traversées par la coupe
        for trou, trou_z_min, trou_z_max in ouvertures.get(element.id(), []):
            if trou_z_min <= hauteur <= trou_z_max:
                polygone = polygone.difference(trou)
        if not polygone.is_empty:
            formes.append((element, polygone))
    return formes


def morceaux(geometrie):
    """Un Polygon ou un MultiPolygon, vu comme une liste de polygones."""
    return list(geometrie.geoms) if hasattr(geometrie, "geoms") else [geometrie]


def etiquette(element):
    """Petit texte à afficher sur la forme : B1, B2... pour les baies, Porte pour la porte."""
    correspondance = re.search(r"Baie (\d+)", element.Name or "")
    if correspondance:
        return f"B{correspondance.group(1)}"
    if element.is_a("IfcDoor"):
        return "Porte"
    return ""


def ecrire_svg(formes, hauteur, chemin_sortie):
    """Dessine les formes en SVG (X vers la droite, Y vers le haut du plan)."""
    x_min, y_min, x_max, y_max = unary_union([p for _, p in formes]).bounds

    def pixel(x, y):
        # Le SVG a son axe Y vers le bas : on inverse pour que Y soit vers le haut
        return MARGE + (x - x_min) * ECHELLE, MARGE + (y_max - y) * ECHELLE

    largeur_px = (x_max - x_min) * ECHELLE + 2 * MARGE
    hauteur_px = (y_max - y_min) * ECHELLE + 2 * MARGE + 60

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largeur_px:.0f}" '
        f'height="{hauteur_px:.0f}" viewBox="0 0 {largeur_px:.0f} {hauteur_px:.0f}" '
        f'font-family="sans-serif">',
        f'<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{MARGE}" y="30" font-size="16" fill="#202124">'
        f'Coupe horizontale à Z = {hauteur:.2f} m</text>',
    ]

    # Les éléments les plus grands d'abord, pour que les petits restent visibles
    for element, polygone in sorted(formes, key=lambda f: -f[1].area):
        remplissage, contour = STYLES.get(element.is_a(), STYLE_PAR_DEFAUT)
        for morceau in morceaux(polygone):
            points = " ".join(
                f"{pixel(x, y)[0]:.1f},{pixel(x, y)[1]:.1f}" for x, y in morceau.exterior.coords
            )
            svg.append(
                f'<polygon points="{points}" fill="{remplissage}" '
                f'stroke="{contour}" stroke-width="1.5"/>'
            )
        # À petite échelle, les étiquettes se chevauchent : on ne les dessine que si lisibles
        texte = etiquette(element) if ECHELLE >= 60 else ""
        if texte:
            cx, cy = pixel(polygone.centroid.x, polygone.centroid.y)
            couleur = "#ffffff" if element.is_a("IfcBuildingElementProxy") else "#202124"
            ancrage = "middle"
            if element.is_a("IfcDoor"):
                # La porte est trop fine pour contenir son texte : on l'écrit à côté
                cx -= 12
                ancrage = "end"
            svg.append(
                f'<text x="{cx:.1f}" y="{cy:.1f}" font-size="13" fill="{couleur}" '
                f'text-anchor="{ancrage}" dominant-baseline="middle">{texte}</text>'
            )

    # Échelle graphique : une barre de 1 m, et dimensions hors tout
    bas = hauteur_px - 28
    svg.append(
        f'<line x1="{MARGE}" y1="{bas}" x2="{MARGE + ECHELLE}" y2="{bas}" '
        f'stroke="#202124" stroke-width="3"/>'
    )
    svg.append(f'<text x="{MARGE + ECHELLE + 10}" y="{bas + 4}" font-size="12" fill="#202124">1 m</text>')
    svg.append(
        f'<text x="{largeur_px - MARGE}" y="{bas + 4}" font-size="12" fill="#202124" '
        f'text-anchor="end">Hors tout : {x_max - x_min:.3f} x {y_max - y_min:.3f} m</text>'
    )
    svg.append("</svg>")

    dossier = os.path.dirname(chemin_sortie)
    if dossier:
        os.makedirs(dossier, exist_ok=True)
    with open(chemin_sortie, "w", encoding="utf-8") as fichier:
        fichier.write("\n".join(svg))


def main():
    global ECHELLE   # modifiée par l'option --echelle
    parseur = argparse.ArgumentParser(description="Coupe en plan d'un fichier IFC, en SVG.")
    parseur.add_argument("fichier", nargs="?", default=FICHIER_PAR_DEFAUT, help="fichier IFC à couper")
    parseur.add_argument("--hauteur", type=float, default=1.5, help="hauteur de coupe en mètres")
    parseur.add_argument("--sortie", default=SORTIE_PAR_DEFAUT, help="fichier SVG à écrire")
    parseur.add_argument("--echelle", type=float, default=ECHELLE, help="pixels par mètre")
    args = parseur.parse_args()
    ECHELLE = args.echelle

    try:
        modele = ifcopenshell.open(args.fichier)
    except Exception as erreur:
        print(f"Impossible d'ouvrir '{args.fichier}' : {erreur}")
        raise SystemExit(1)

    formes = couper(modele, args.hauteur)
    if not formes:
        print(f"Aucun élément à Z = {args.hauteur} m (ou formes non extrudées depuis un rectangle).")
        raise SystemExit(1)

    ecrire_svg(formes, args.hauteur, args.sortie)

    par_classe = Counter(element.is_a() for element, _ in formes)
    print(f"Coupe à Z = {args.hauteur:.2f} m : {len(formes)} éléments coupés")
    for classe, nombre in sorted(par_classe.items()):
        print(f"  {classe} : {nombre}")
    print(f"Plan écrit : {args.sortie}")


if __name__ == "__main__":
    main()
