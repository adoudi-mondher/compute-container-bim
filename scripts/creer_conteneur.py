"""
creer_conteneur.py - Génère un conteneur de calcul 20 ft en coque creuse, en IFC4.

Le conteneur est un assemblage (IfcElementAssembly) de 6 pièces :
  sol, toit, 2 longs murs, 2 murs de bout.
Les propriétés de calcul (puissance, GPU, ...) sont portées par l'assemblage.

Usage (depuis la racine du projet, venv activé) :
    python scripts/creer_conteneur.py
"""

import numpy as np                      # matrices 4x4 pour placer les éléments
import ifcopenshell
import ifcopenshell.api.root            # création d'entités (IfcWall, IfcSlab, ...)
import ifcopenshell.api.project         # création du fichier et du projet
import ifcopenshell.api.unit            # unités (mètres)
import ifcopenshell.api.context         # contextes de représentation 3D
import ifcopenshell.api.aggregate       # hiérarchie site > bâtiment > niveau, assemblages
import ifcopenshell.api.spatial         # rattachement d'un élément à un niveau
import ifcopenshell.api.geometry        # formes 3D et placement
import ifcopenshell.api.pset            # jeux de propriétés

FICHIER_SORTIE = "models/compute-container-20ft-v2.ifc"

# Dimensions extérieures d'un conteneur ISO 20 ft, en mètres
LONGUEUR = 6.058
LARGEUR = 2.438
HAUTEUR = 2.591
EPAISSEUR = 0.10    # épaisseur des parois (simplifiée)

# Caractéristiques du Policloud 100 (spécifications publiques du fabricant)
PROPRIETES = {
    "Modele": "Policloud 100",
    "ConteneurPieds": 20,
    "PuissanceMaxKW": 100.0,
    "NombreGPU": 104,
    "vCPUMin": 6000,
    "StockagePB": 2.0,
    "TemperatureMinC": -40.0,
    "TemperatureMaxC": 45.0,
    "EmpriseSolM2": 50.0,
    "RefroidissementEau": False,
    "Source": "https://www.policloud.com/#policloud-specifications",
}


def creer_structure(modele):
    """Crée projet, site, bâtiment et niveau. Retourne (niveau, contexte_3D)."""
    projet = ifcopenshell.api.root.create_entity(
        modele, ifc_class="IfcProject", name="Compute Container BIM"
    )
    # Unités explicitement en mètres. Sans argument, IfcOpenShell choisit les
    # millimètres : les positions seraient converties mais pas les profils.
    ifcopenshell.api.unit.assign_unit(
        modele,
        length={"is_metric": True, "raw": "METERS"},
        area={"is_metric": True, "raw": "SQUARE_METRE"},
        volume={"is_metric": True, "raw": "CUBIC_METRE"},
    )

    # Contexte "Model" puis sous-contexte "Body" : c'est là que vit la géométrie 3D
    contexte = ifcopenshell.api.context.add_context(modele, context_type="Model")
    corps = ifcopenshell.api.context.add_context(
        modele, context_type="Model", context_identifier="Body",
        target_view="MODEL_VIEW", parent=contexte,
    )

    site = ifcopenshell.api.root.create_entity(modele, ifc_class="IfcSite", name="Site")
    batiment = ifcopenshell.api.root.create_entity(
        modele, ifc_class="IfcBuilding", name="Bâtiment"
    )
    niveau = ifcopenshell.api.root.create_entity(
        modele, ifc_class="IfcBuildingStorey", name="Niveau 0"
    )

    # Hiérarchie : projet > site > bâtiment > niveau
    ifcopenshell.api.aggregate.assign_object(modele, products=[site], relating_object=projet)
    ifcopenshell.api.aggregate.assign_object(modele, products=[batiment], relating_object=site)
    ifcopenshell.api.aggregate.assign_object(modele, products=[niveau], relating_object=batiment)
    return niveau, corps


def creer_boite(modele, corps, niveau, classe_ifc, nom, dx, dy, dz, x, y, z,
                type_predefini=None):
    """
    Crée une boîte (dx, dy, dz) comme élément IFC.
    (x, y, z) = centre de la face inférieure de la boîte.
    Retourne l'élément créé.
    """
    element = ifcopenshell.api.root.create_entity(
        modele, ifc_class=classe_ifc, name=nom, predefined_type=type_predefini
    )

    # Forme : rectangle centré sur l'origine (dx par dy), extrudé vers le haut sur dz
    profil = modele.create_entity(
        "IfcRectangleProfileDef", ProfileType="AREA", XDim=dx, YDim=dy
    )
    forme = ifcopenshell.api.geometry.add_profile_representation(
        modele, context=corps, profile=profil, depth=dz
    )
    ifcopenshell.api.geometry.assign_representation(
        modele, product=element, representation=forme
    )

    # Position : matrice 4x4 avec la translation (x, y, z) dans la dernière colonne
    matrice = np.eye(4)
    matrice[:, 3] = (x, y, z, 1.0)
    ifcopenshell.api.geometry.edit_object_placement(
        modele, product=element, matrix=matrice
    )

    # Rattachement au niveau
    ifcopenshell.api.spatial.assign_container(
        modele, products=[element], relating_structure=niveau
    )
    return element


def creer_conteneur(modele, corps, niveau, nom, longueur, largeur, hauteur,
                    epaisseur, x=0.0, y=0.0, z=0.0):
    """
    Crée un conteneur creux (assemblage de 6 pièces) dont le centre de la face
    inférieure est en (x, y, z). Retourne l'assemblage.
    """
    e = epaisseur
    boite = lambda classe, n, dx, dy, dz, px, py, pz, t=None: creer_boite(
        modele, corps, niveau, classe, f"{nom} - {n}",
        dx, dy, dz, x + px, y + py, z + pz, t,
    )

    pieces = [
        # Sol et toit : pleine surface, épaisseur e
        boite("IfcSlab", "Sol", longueur, largeur, e, 0, 0, 0, "FLOOR"),
        boite("IfcSlab", "Toit", longueur, largeur, e, 0, 0, hauteur - e, "ROOF"),
        # Deux longs murs (côtés), entre le sol et le toit
        boite("IfcWall", "Mur long A", longueur, e, hauteur - 2 * e,
              0, (largeur - e) / 2, e),
        boite("IfcWall", "Mur long B", longueur, e, hauteur - 2 * e,
              0, -(largeur - e) / 2, e),
        # Deux murs de bout, plus étroits pour s'insérer entre les longs murs
        boite("IfcWall", "Mur de bout A", e, largeur - 2 * e, hauteur - 2 * e,
              (longueur - e) / 2, 0, e),
        boite("IfcWall", "Mur de bout B", e, largeur - 2 * e, hauteur - 2 * e,
              -(longueur - e) / 2, 0, e),
    ]

    # Assemblage parent : le conteneur est UN objet logique composé de 6 parties
    assemblage = ifcopenshell.api.root.create_entity(
        modele, ifc_class="IfcElementAssembly", name=nom
    )
    ifcopenshell.api.spatial.assign_container(
        modele, products=[assemblage], relating_structure=niveau
    )
    ifcopenshell.api.aggregate.assign_object(
        modele, products=pieces, relating_object=assemblage
    )

    # Propriétés de calcul portées par l'assemblage
    pset = ifcopenshell.api.pset.add_pset(modele, product=assemblage, name="Policloud")
    ifcopenshell.api.pset.edit_pset(modele, pset=pset, properties=PROPRIETES)
    return assemblage


def main():
    modele = ifcopenshell.api.project.create_file(version="IFC4")
    niveau, corps = creer_structure(modele)

    creer_conteneur(
        modele, corps, niveau, "Container 20ft",
        LONGUEUR, LARGEUR, HAUTEUR, EPAISSEUR,
    )

    modele.write(FICHIER_SORTIE)
    print(f"Fichier créé : {FICHIER_SORTIE}")
    print(f"Murs : {len(modele.by_type('IfcWall'))}, "
          f"dalles : {len(modele.by_type('IfcSlab'))}, "
          f"assemblages : {len(modele.by_type('IfcElementAssembly'))}")


if __name__ == "__main__":
    main()
