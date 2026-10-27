"""
lire_ifc.py - Lecture d'un fichier IFC avec IfcOpenShell.

Affiche, pour chaque élément du modèle :
  - son nom et sa classe IFC
  - sa position (X, Y, Z)
  - ses dimensions (longueur, largeur, hauteur)

Usage (depuis la racine du projet, venv activé) :
    python scripts/lire_ifc.py
    python scripts/lire_ifc.py models/autre-fichier.ifc
"""

import sys                          # pour lire les arguments de la ligne de commande
import ifcopenshell                 # bibliothèque principale pour lire/écrire l'IFC
import ifcopenshell.geom            # calcul de la géométrie (pour les dimensions)
import ifcopenshell.util.placement  # calcul de la position d'un élément

# Chemin du fichier IFC : par défaut, celui du projet Policloud
CHEMIN_PAR_DEFAUT = "models/policloud-container-20ft.ifc"


def lire_position(element):
    """Retourne la position (x, y, z) de l'élément, en unités du modèle (mètres ici)."""
    # get_local_placement renvoie une matrice 4x4 ; la dernière colonne contient la position
    matrice = ifcopenshell.util.placement.get_local_placement(element.ObjectPlacement)
    return float(matrice[0][3]), float(matrice[1][3]), float(matrice[2][3])


def lire_dimensions(element):
    """Retourne les dimensions (dx, dy, dz) de la boîte englobante de l'élément."""
    reglages = ifcopenshell.geom.settings()
    # On construit la géométrie 3D de l'élément à partir de sa représentation IFC
    forme = ifcopenshell.geom.create_shape(reglages, element)
    sommets = forme.geometry.verts  # liste à plat : x1, y1, z1, x2, y2, z2, ...

    # On sépare les coordonnées X, Y et Z (un sommet = 3 valeurs consécutives)
    xs = sommets[0::3]
    ys = sommets[1::3]
    zs = sommets[2::3]

    # Dimension = valeur max - valeur min sur chaque axe
    return max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)


def main():
    # 1. Choix du fichier : argument fourni, sinon chemin par défaut
    chemin = sys.argv[1] if len(sys.argv) > 1 else CHEMIN_PAR_DEFAUT

    # 2. Ouverture du fichier IFC (erreur claire si le fichier est introuvable)
    try:
        modele = ifcopenshell.open(chemin)
    except Exception as erreur:
        print(f"Impossible d'ouvrir '{chemin}' : {erreur}")
        sys.exit(1)

    print(f"Fichier : {chemin}")
    print(f"Schéma IFC : {modele.schema}")

    # 3. Liste de tous les produits (IfcProduct) qui ont une géométrie
    #    On ignore la structure spatiale (site, bâtiment, niveau) : pas de forme 3D
    elements = [
        e for e in modele.by_type("IfcElement")
        if e.Representation is not None
    ]
    print(f"Éléments avec géométrie : {len(elements)}\n")

    # 4. Affichage des informations de chaque élément
    for element in elements:
        x, y, z = lire_position(element)
        dx, dy, dz = lire_dimensions(element)
        print(f"Nom        : {element.Name}")
        print(f"Classe IFC : {element.is_a()}")
        print(f"Position   : X={x:.3f}  Y={y:.3f}  Z={z:.3f}")
        print(f"Dimensions : {dx:.3f} x {dy:.3f} x {dz:.3f}")
        print("-" * 40)


# Point d'entrée : exécute main() seulement si le fichier est lancé directement
if __name__ == "__main__":
    main()
