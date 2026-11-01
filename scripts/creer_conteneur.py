"""
creer_conteneur.py - Génère un conteneur de calcul 20 ft en coque creuse, en IFC4.

Le conteneur est un assemblage (IfcElementAssembly) composé de :
  - 6 pièces de coque : sol, toit, 2 longs murs, 2 murs de bout
  - 1 porte de service percée dans le mur de bout A
  - 8 baies informatiques en une rangée contre le long mur B
Les propriétés de calcul (puissance, GPU, ...) sont portées par l'assemblage.

ATTENTION : la porte et les baies sont ILLUSTRATIVES. Leurs cotes sont des
hypothèses crédibles (baie 19" type 42U de 600 x 1070 mm), pas des données
fabricant. L'agencement interne réel du Policloud n'est pas public.

Usage (depuis la racine du projet, venv activé) :
    python scripts/creer_conteneur.py
"""

import numpy as np                      # matrices 4x4 pour placer les éléments
import ifcopenshell
import ifcopenshell.guid                # identifiants uniques (GlobalId) des relations
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

# Porte de service sur le mur de bout A (cotes illustratives)
PORTE_LARGEUR = 1.0
PORTE_HAUTEUR = 2.0
PORTE_EPAISSEUR = 0.05

# Baies informatiques (cotes illustratives : baie 19" type 42U)
NB_BAIES = 8
BAIE_LARGEUR = 0.6      # le long du conteneur (axe X)
BAIE_PROFONDEUR = 1.07  # en travers du conteneur (axe Y)
BAIE_HAUTEUR = 2.0
JEU_FOND = 0.05         # jeu entre la première baie et le mur de fond

# Grilles de ventilation (entrée d'air) dans le long mur A, côté couloir (cotes illustratives)
NB_GRILLES = 4
GRILLE_LARGEUR = 0.8     # le long du conteneur (axe X)
GRILLE_HAUTEUR = 0.5
GRILLE_EPAISSEUR = 0.05
GRILLE_Z = 1.4           # hauteur du bas de la grille, depuis le dessous du conteneur

# Ventilateurs d'extraction sur le toit, au-dessus des baies (cotes illustratives)
NB_VENTILATEURS = 2
VENTILATEUR_COTE = 0.7   # carré de 0,7 m de côté
VENTILATEUR_HAUTEUR = 0.2
VENTILATEUR_OUVERTURE = 0.5   # trou dans le toit, sous le ventilateur

# Armoire électrique contre le mur de bout A, à côté de la porte (cotes illustratives)
ARMOIRE_PROFONDEUR = 0.4   # le long du conteneur (axe X)
ARMOIRE_LARGEUR = 0.8      # en travers du conteneur (axe Y)
ARMOIRE_HAUTEUR = 2.0

# Extincteur fixé au long mur B, entre la dernière baie et le mur de bout (cotes illustratives)
EXTINCTEUR_COTE = 0.15
EXTINCTEUR_HAUTEUR = 0.55
EXTINCTEUR_Z = 1.0         # hauteur du bas de l'extincteur, depuis le dessous du conteneur
EXTINCTEUR_RETRAIT = 0.55  # distance entre le mur de bout et le centre de l'extincteur

# Luminaires au plafond, le long du couloir (cotes illustratives)
NB_LUMINAIRES = 3
LUMINAIRE_LONGUEUR = 1.2
LUMINAIRE_LARGEUR = 0.1
LUMINAIRE_HAUTEUR = 0.06

NOTE_ILLUSTRATIF = "Cotes illustratives, non issues du fabricant."

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
                type_predefini=None, ranger=True):
    """
    Crée une boîte (dx, dy, dz) comme élément IFC.
    (x, y, z) = centre de la face inférieure de la boîte.
    ranger=False : l'élément n'est pas rattaché au niveau (cas d'une ouverture).
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
    if ranger:
        ifcopenshell.api.spatial.assign_container(
            modele, products=[element], relating_structure=niveau
        )
    return element


def percer(modele, element, ouverture):
    """Relie une ouverture à un élément (mur, dalle) : l'élément est percé (IfcRelVoidsElement)."""
    modele.create_entity(
        "IfcRelVoidsElement", GlobalId=ifcopenshell.guid.new(),
        RelatingBuildingElement=element, RelatedOpeningElement=ouverture,
    )


def percer_et_remplir(modele, mur, ouverture, porte):
    """
    Relie une ouverture à un mur (le mur est percé) et une porte à l'ouverture
    (la porte remplit le trou). On crée les deux relations IFC directement :
    IfcRelVoidsElement (mur -> ouverture) et IfcRelFillsElement (ouverture -> porte).
    """
    percer(modele, mur, ouverture)
    modele.create_entity(
        "IfcRelFillsElement", GlobalId=ifcopenshell.guid.new(),
        RelatingOpeningElement=ouverture, RelatedBuildingElement=porte,
    )


def verifier_dimensions(longueur, largeur, hauteur, epaisseur):
    """Vérifie que la porte, les baies, les grilles et les ventilateurs tiennent dans le conteneur."""
    x_int = longueur / 2 - epaisseur    # demi-longueur intérieure
    y_int = largeur / 2 - epaisseur     # demi-largeur intérieure
    if NB_BAIES * BAIE_LARGEUR + JEU_FOND > 2 * x_int:
        raise ValueError("Trop de baies pour la longueur intérieure du conteneur.")
    if BAIE_PROFONDEUR >= 2 * y_int:
        raise ValueError("Baies trop profondes : plus de place pour le couloir.")
    if BAIE_PROFONDEUR / 2 + PORTE_LARGEUR / 2 > y_int:
        raise ValueError("La porte dépasse du mur de bout.")
    if NB_GRILLES * GRILLE_LARGEUR > 2 * x_int:
        raise ValueError("Trop de grilles pour la longueur du long mur.")
    if GRILLE_Z + GRILLE_HAUTEUR > hauteur - epaisseur:
        raise ValueError("Les grilles dépassent de la hauteur du mur.")
    if NB_VENTILATEURS * VENTILATEUR_COTE > 2 * x_int:
        raise ValueError("Trop de ventilateurs pour la longueur du toit.")
    # Fin de la dernière baie : l'armoire et l'extincteur doivent se trouver après
    fin_baies = -x_int + JEU_FOND + NB_BAIES * BAIE_LARGEUR
    if x_int - ARMOIRE_PROFONDEUR < fin_baies:
        raise ValueError("L'armoire électrique gêne les baies.")
    bas_porte = BAIE_PROFONDEUR / 2 - PORTE_LARGEUR / 2
    if ARMOIRE_LARGEUR > bas_porte + y_int:
        raise ValueError("L'armoire ne tient pas entre le mur et la porte.")
    if x_int - EXTINCTEUR_RETRAIT - EXTINCTEUR_COTE / 2 < fin_baies:
        raise ValueError("L'extincteur gêne les baies.")
    if NB_LUMINAIRES * LUMINAIRE_LONGUEUR > 2 * x_int:
        raise ValueError("Trop de luminaires pour la longueur du plafond.")


def creer_conteneur(modele, corps, niveau, nom, longueur, largeur, hauteur,
                    epaisseur, x=0.0, y=0.0, z=0.0):
    """
    Crée un conteneur creux (coque + porte + baies + ventilation + équipements) dont le centre de la face
    inférieure est en (x, y, z). Retourne l'assemblage.
    """
    verifier_dimensions(longueur, largeur, hauteur, epaisseur)

    e = epaisseur
    x_int = longueur / 2 - e    # demi-longueur intérieure
    y_int = largeur / 2 - e     # demi-largeur intérieure

    boite = lambda classe, n, dx, dy, dz, px, py, pz, t=None: creer_boite(
        modele, corps, niveau, classe, f"{nom} - {n}",
        dx, dy, dz, x + px, y + py, z + pz, t,
    )

    # --- Coque : 6 pièces ---
    sol = boite("IfcSlab", "Sol", longueur, largeur, e, 0, 0, 0, "FLOOR")
    toit = boite("IfcSlab", "Toit", longueur, largeur, e, 0, 0, hauteur - e, "ROOF")
    mur_long_a = boite("IfcWall", "Mur long A", longueur, e, hauteur - 2 * e,
                       0, (largeur - e) / 2, e)
    mur_long_b = boite("IfcWall", "Mur long B", longueur, e, hauteur - 2 * e,
                       0, -(largeur - e) / 2, e)
    # Murs de bout plus étroits pour s'insérer entre les longs murs
    x_bout = (longueur - e) / 2
    mur_bout_a = boite("IfcWall", "Mur de bout A", e, largeur - 2 * e, hauteur - 2 * e,
                       x_bout, 0, e)
    mur_bout_b = boite("IfcWall", "Mur de bout B", e, largeur - 2 * e, hauteur - 2 * e,
                       -x_bout, 0, e)
    pieces = [sol, toit, mur_long_a, mur_long_b, mur_bout_a, mur_bout_b]

    # --- Baies : une rangée contre le long mur B, à partir du fond (X négatif) ---
    y_baie = -y_int + BAIE_PROFONDEUR / 2
    for i in range(NB_BAIES):
        x_baie = -x_int + JEU_FOND + BAIE_LARGEUR / 2 + i * BAIE_LARGEUR
        baie = boite("IfcBuildingElementProxy", f"Baie {i + 1} (illustratif)",
                     BAIE_LARGEUR, BAIE_PROFONDEUR, BAIE_HAUTEUR, x_baie, y_baie, e)
        baie.Description = NOTE_ILLUSTRATIF
        pieces.append(baie)

    # --- Porte de service : au milieu du couloir, dans le mur de bout A ---
    y_porte = BAIE_PROFONDEUR / 2   # le couloir va de -y_int + profondeur à +y_int
    # L'ouverture est plus épaisse que le mur pour que le trou traverse complètement
    ouverture = creer_boite(
        modele, corps, niveau, "IfcOpeningElement", f"{nom} - Ouverture porte",
        2 * e, PORTE_LARGEUR, PORTE_HAUTEUR,
        x + x_bout, y + y_porte, z + e, "OPENING", ranger=False,
    )
    porte = boite("IfcDoor", "Porte de service (illustratif)",
                  PORTE_EPAISSEUR, PORTE_LARGEUR, PORTE_HAUTEUR,
                  x_bout, y_porte, e, "DOOR")
    porte.OverallWidth = PORTE_LARGEUR
    porte.OverallHeight = PORTE_HAUTEUR
    porte.Description = NOTE_ILLUSTRATIF
    percer_et_remplir(modele, mur_bout_a, ouverture, porte)
    pieces.append(porte)

    # --- Grilles de ventilation : entrée d'air dans le long mur A (côté couloir) ---
    y_mur_a = (largeur - e) / 2
    case_grille = 2 * x_int / NB_GRILLES        # largeur de la zone de chaque grille
    for i in range(NB_GRILLES):
        x_grille = -x_int + (i + 0.5) * case_grille
        trou = creer_boite(
            modele, corps, niveau, "IfcOpeningElement", f"{nom} - Ouverture grille {i + 1}",
            GRILLE_LARGEUR, 2 * e, GRILLE_HAUTEUR,
            x + x_grille, y + y_mur_a, z + GRILLE_Z, "OPENING", ranger=False,
        )
        grille = boite("IfcAirTerminal", f"Grille de ventilation {i + 1} (illustratif)",
                       GRILLE_LARGEUR, GRILLE_EPAISSEUR, GRILLE_HAUTEUR,
                       x_grille, y_mur_a, GRILLE_Z, "GRILLE")
        grille.Description = NOTE_ILLUSTRATIF
        percer_et_remplir(modele, mur_long_a, trou, grille)
        pieces.append(grille)

    # --- Ventilateurs d'extraction : sur le toit, au-dessus des baies ---
    case_vent = 2 * x_int / NB_VENTILATEURS
    for i in range(NB_VENTILATEURS):
        x_vent = -x_int + (i + 0.5) * case_vent
        # Trou dans le toit (traverse toute l'épaisseur de la dalle), sous le ventilateur
        trou = creer_boite(
            modele, corps, niveau, "IfcOpeningElement", f"{nom} - Ouverture ventilateur {i + 1}",
            VENTILATEUR_OUVERTURE, VENTILATEUR_OUVERTURE, 2 * e,
            x + x_vent, y + y_baie, z + hauteur - 1.5 * e, "OPENING", ranger=False,
        )
        percer(modele, toit, trou)
        ventilateur = boite("IfcFan", f"Ventilateur d'extraction {i + 1} (illustratif)",
                            VENTILATEUR_COTE, VENTILATEUR_COTE, VENTILATEUR_HAUTEUR,
                            x_vent, y_baie, hauteur, "TUBEAXIAL")
        ventilateur.Description = NOTE_ILLUSTRATIF
        pieces.append(ventilateur)

    # --- Armoire électrique : contre le mur de bout A, entre le long mur B et la porte ---
    bas_porte = y_porte - PORTE_LARGEUR / 2
    armoire = boite("IfcElectricDistributionBoard", "Armoire électrique (illustratif)",
                    ARMOIRE_PROFONDEUR, ARMOIRE_LARGEUR, ARMOIRE_HAUTEUR,
                    x_int - ARMOIRE_PROFONDEUR / 2, (-y_int + bas_porte) / 2, e,
                    "DISTRIBUTIONBOARD")
    armoire.Description = NOTE_ILLUSTRATIF
    pieces.append(armoire)

    # --- Extincteur : fixé au long mur B, entre la dernière baie et le mur de bout ---
    # IFC4 n'a pas de type "extincteur" : on utilise USERDEFINED avec un type texte.
    extincteur = boite("IfcFireSuppressionTerminal", "Extincteur (illustratif)",
                       EXTINCTEUR_COTE, EXTINCTEUR_COTE, EXTINCTEUR_HAUTEUR,
                       x_int - EXTINCTEUR_RETRAIT, -y_int + EXTINCTEUR_COTE / 2, EXTINCTEUR_Z,
                       "USERDEFINED")
    extincteur.ObjectType = "Extincteur"
    extincteur.Description = NOTE_ILLUSTRATIF
    pieces.append(extincteur)

    # --- Luminaires : sous le toit, au milieu du couloir (même Y que la porte) ---
    case_lum = 2 * x_int / NB_LUMINAIRES
    for i in range(NB_LUMINAIRES):
        luminaire = boite("IfcLightFixture", f"Luminaire {i + 1} (illustratif)",
                          LUMINAIRE_LONGUEUR, LUMINAIRE_LARGEUR, LUMINAIRE_HAUTEUR,
                          -x_int + (i + 0.5) * case_lum, y_porte,
                          hauteur - e - LUMINAIRE_HAUTEUR, "DIRECTIONSOURCE")
        luminaire.Description = NOTE_ILLUSTRATIF
        pieces.append(luminaire)

    # Assemblage parent : le conteneur est UN objet logique composé de ses parties
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
          f"portes : {len(modele.by_type('IfcDoor'))}, "
          f"ouvertures : {len(modele.by_type('IfcOpeningElement'))}, "
          f"baies : {len(modele.by_type('IfcBuildingElementProxy'))}, "
          f"grilles : {len(modele.by_type('IfcAirTerminal'))}, "
          f"ventilateurs : {len(modele.by_type('IfcFan'))}, "
          f"armoires : {len(modele.by_type('IfcElectricDistributionBoard'))}, "
          f"extincteurs : {len(modele.by_type('IfcFireSuppressionTerminal'))}, "
          f"luminaires : {len(modele.by_type('IfcLightFixture'))}, "
          f"assemblages : {len(modele.by_type('IfcElementAssembly'))}")


if __name__ == "__main__":
    main()
