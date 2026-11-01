"""
implanter_site.py - Place N conteneurs de calcul sur un site et calcule les totaux.

Les paramètres du site sont lus dans un fichier JSON (dossier sites/) :
nombre d'unités, disposition en grille, emprise par unité, puissance disponible.
Le script génère un fichier IFC avec N conteneurs (chacun avec ses baies et sa porte),
affiche les totaux (puissance, GPU, stockage, emprise) et alerte si la puissance
demandée dépasse la puissance disponible. Les totaux sont aussi écrits dans l'IFC,
sur le site (jeu de propriétés "SiteCalcul").

Si le JSON contient une section "geolocalisation", le script :
  - géoréférence l'IFC (position GPS du site + système de coordonnées UTM) ;
  - exporte un fichier KML à ouvrir dans Google Earth.
Le site est orienté sur la grille UTM : l'axe X du modèle pointe vers l'est, Y vers le nord.
L'origine du modèle est le centre du conteneur n°1.

Les valeurs par conteneur viennent de scripts/creer_conteneur.py (Policloud 100).

Usage (depuis la racine du projet, venv activé) :
    python scripts/implanter_site.py
    python scripts/implanter_site.py sites/gabes-exemple.json
"""

import json
import math
import sys

import ifcopenshell
import ifcopenshell.api.project
import ifcopenshell.api.pset
import ifcopenshell.api.georeference

# On réutilise les fonctions et constantes du script de création du conteneur
from creer_conteneur import (
    creer_structure, creer_conteneur, PROPRIETES,
    LONGUEUR, LARGEUR, HAUTEUR, EPAISSEUR,
)
import geo

FICHIER_PARAMETRES = "sites/exemple-10-unites.json"

# Clés obligatoires du fichier JSON, avec leur type attendu
CLES = {
    "nom": str,
    "nombre_unites": int,
    "colonnes": int,
    "pas_x_m": (int, float),
    "pas_y_m": (int, float),
    "emprise_par_unite_m2": (int, float),
    "puissance_disponible_kw": (int, float),
    "fichier_sortie": str,
}

# Clés de la section optionnelle "geolocalisation"
CLES_GEO = {
    "repere_latitude": (int, float),
    "repere_longitude": (int, float),
    "repere_description": str,
    "decalage_est_m": (int, float),
    "decalage_nord_m": (int, float),
    "altitude_m": (int, float),
    "fichier_kml": str,
}


def verifier_cles(donnees, cles, contexte):
    """Vérifie que chaque clé est présente avec le bon type. Arrête le script sinon."""
    for cle, type_attendu in cles.items():
        if cle not in donnees:
            print(f"Paramètre manquant ({contexte}) : {cle}")
            sys.exit(1)
        if not isinstance(donnees[cle], type_attendu) or isinstance(donnees[cle], bool):
            print(f"Paramètre '{cle}' ({contexte}) : type invalide "
                  f"({type(donnees[cle]).__name__}).")
            sys.exit(1)


def lire_parametres(chemin):
    """Lit et contrôle le fichier JSON. Arrête le script si quelque chose cloche."""
    try:
        with open(chemin, encoding="utf-8") as fichier:
            p = json.load(fichier)
    except (OSError, json.JSONDecodeError) as erreur:
        print(f"Impossible de lire '{chemin}' : {erreur}")
        sys.exit(1)

    verifier_cles(p, CLES, chemin)

    # Valeurs cohérentes
    for cle in ("nombre_unites", "colonnes", "pas_x_m", "pas_y_m",
                "emprise_par_unite_m2", "puissance_disponible_kw"):
        if p[cle] <= 0:
            print(f"Paramètre '{cle}' : doit être strictement positif.")
            sys.exit(1)

    # Les conteneurs ne doivent pas se chevaucher
    if p["pas_x_m"] < LONGUEUR or p["pas_y_m"] < LARGEUR:
        print(f"Pas de grille trop petit : il faut au moins {LONGUEUR} x {LARGEUR} m "
              f"(taille d'un conteneur), reçu {p['pas_x_m']} x {p['pas_y_m']} m.")
        sys.exit(1)

    # Section géolocalisation, facultative
    if "geolocalisation" in p:
        g = p["geolocalisation"]
        verifier_cles(g, CLES_GEO, "geolocalisation")
        if not (0 <= g["repere_latitude"] <= 84):
            print("Latitude du repère : doit être entre 0 et 84 (hémisphère nord).")
            sys.exit(1)
        if not (-180 <= g["repere_longitude"] <= 180):
            print("Longitude du repère : doit être entre -180 et 180.")
            sys.exit(1)
    return p


def calculer_totaux(p):
    """Calcule les totaux du site à partir du nombre d'unités."""
    n = p["nombre_unites"]
    lignes = math.ceil(n / p["colonnes"])
    colonnes_utilisees = min(n, p["colonnes"])
    puissance = n * PROPRIETES["PuissanceMaxKW"]
    return {
        "NombreUnites": n,
        "PuissanceTotaleKW": puissance,
        "PuissanceDisponibleKW": float(p["puissance_disponible_kw"]),
        "MargeKW": p["puissance_disponible_kw"] - puissance,
        "NombreGPUTotal": n * PROPRIETES["NombreGPU"],
        "vCPUMinTotal": n * PROPRIETES["vCPUMin"],
        "StockageTotalPB": n * PROPRIETES["StockagePB"],
        # Emprise "réglementaire" du fabricant (dégagements inclus) et emprise de la grille
        "EmpriseFabricantM2": n * p["emprise_par_unite_m2"],
        "EmpriseGrilleM2": colonnes_utilisees * p["pas_x_m"] * lignes * p["pas_y_m"],
        "SurfaceConteneursM2": round(n * LONGUEUR * LARGEUR, 2),
    }


def positions(p):
    """Position (x, y) du centre de chaque conteneur, en mètres, dans le repère du site."""
    return [((i % p["colonnes"]) * p["pas_x_m"],    # colonne dans la ligne
             (i // p["colonnes"]) * p["pas_y_m"])   # numéro de la ligne
            for i in range(p["nombre_unites"])]


def implanter(p):
    """Crée le modèle IFC avec N conteneurs en grille. Retourne le modèle."""
    modele = ifcopenshell.api.project.create_file(version="IFC4")
    niveau, corps = creer_structure(modele)

    # Nom et description du site, repris du fichier de paramètres
    site = modele.by_type("IfcSite")[0]
    site.Name = p["nom"]
    site.Description = p.get("description")

    for i, (x, y) in enumerate(positions(p)):
        creer_conteneur(
            modele, corps, niveau, f"Container 20ft - {i + 1:02d}",
            LONGUEUR, LARGEUR, HAUTEUR, EPAISSEUR, x=x, y=y,
        )
    return modele


def ecrire_totaux(modele, totaux):
    """Écrit les totaux dans l'IFC, sur le site (jeu de propriétés SiteCalcul)."""
    site = modele.by_type("IfcSite")[0]
    pset = ifcopenshell.api.pset.add_pset(modele, product=site, name="SiteCalcul")
    ifcopenshell.api.pset.edit_pset(modele, pset=pset, properties=totaux)


# ---------------------------------------------------------------- géolocalisation

def calculer_origine(g):
    """
    Position de l'origine du modèle (centre du conteneur n°1) : le repère, décalé en
    mètres vers l'est et le nord sur la grille UTM. Retourne un dictionnaire.
    """
    est_ref, nord_ref, zone = geo.vers_utm(g["repere_latitude"], g["repere_longitude"])
    est = est_ref + g["decalage_est_m"]
    nord = nord_ref + g["decalage_nord_m"]
    latitude, longitude = geo.depuis_utm(est, nord, zone)
    return {"zone": zone, "est": est, "nord": nord,
            "latitude": latitude, "longitude": longitude,
            "altitude": float(g["altitude_m"])}


def georeferencer(modele, origine):
    """Écrit dans l'IFC la position GPS du site et le système de coordonnées UTM."""
    epsg = f"EPSG:326{origine['zone']:02d}"             # WGS 84 / UTM nord, ex. EPSG:32632

    # Position GPS du site (angles en degrés, minutes, secondes, millionièmes)
    site = modele.by_type("IfcSite")[0]
    site.RefLatitude = geo.en_dms_ifc(origine["latitude"])
    site.RefLongitude = geo.en_dms_ifc(origine["longitude"])
    site.RefElevation = origine["altitude"]

    # Lien entre le repère local du modèle et le système de coordonnées projeté
    ifcopenshell.api.georeference.add_georeferencing(modele, name=epsg)
    ifcopenshell.api.georeference.edit_georeferencing(
        modele,
        projected_crs={
            "Name": epsg,
            "GeodeticDatum": "WGS84",
            "MapProjection": "UTM",
            "MapZone": f"{origine['zone']}N",
        },
        coordinate_operation={
            "Eastings": origine["est"],                 # position de l'origine du modèle
            "Northings": origine["nord"],
            "OrthogonalHeight": origine["altitude"],
            "XAxisAbscissa": 1.0,                       # axe X du modèle = est de la grille
            "XAxisOrdinate": 0.0,
            "Scale": 1.0,                               # facteur d'échelle UTM négligé
        },
    )
    return epsg


def point_vers_gps(origine, x, y):
    """Point (x, y) du repère du site -> (longitude, latitude) en degrés."""
    latitude, longitude = geo.depuis_utm(origine["est"] + x, origine["nord"] + y,
                                         origine["zone"])
    return longitude, latitude


def rectangle_gps(origine, cx, cy, dx, dy):
    """Les 4 coins d'un rectangle (centre cx, cy ; taille dx par dy), en (longitude, latitude)."""
    coins = [(-dx / 2, -dy / 2), (dx / 2, -dy / 2), (dx / 2, dy / 2), (-dx / 2, dy / 2)]
    return [point_vers_gps(origine, cx + ox, cy + oy) for ox, oy in coins]


def exporter_kml(p, g, origine):
    """Écrit le KML : conteneurs, emprises de 50 m2 et repère, pour Google Earth."""
    conteneurs, emprises = [], []
    for i, (x, y) in enumerate(positions(p)):
        nom = f"Unité {i + 1:02d}"
        description = (f"Conteneur 20 ft - {PROPRIETES['PuissanceMaxKW']:.0f} kW, "
                       f"{PROPRIETES['NombreGPU']} GPU ({PROPRIETES['Modele']}, "
                       f"valeurs annoncées par le fabricant).")
        conteneurs.append(geo.kml_polygone(
            nom, description, rectangle_gps(origine, x, y, LONGUEUR, LARGEUR), "conteneur"))
        emprises.append(geo.kml_polygone(
            f"Emprise {i + 1:02d}", f"Emprise de {p['emprise_par_unite_m2']:.0f} m2 par unité.",
            rectangle_gps(origine, x, y, p["pas_x_m"], p["pas_y_m"]), "emprise"))

    repere = geo.kml_point(
        "Repère", g["repere_description"],
        g["repere_longitude"], g["repere_latitude"], "repere")
    origine_kml = geo.kml_point(
        "Origine du site (unité 01)", p["description"],
        origine["longitude"], origine["latitude"], "repere")

    geo.ecrire_kml(
        g["fichier_kml"], p["nom"], p["description"],
        [("Conteneurs", conteneurs), ("Emprises", emprises),
         ("Repères", [repere, origine_kml])])


def afficher_geo(origine, epsg, g):
    """Affiche la position calculée."""
    print(f"\n--- Géolocalisation (hypothétique) ---")
    print(f"Repère            : {g['repere_latitude']:.5f}, {g['repere_longitude']:.5f}")
    print(f"Décalage          : {g['decalage_est_m']:.0f} m vers l'est, "
          f"{g['decalage_nord_m']:.0f} m vers le nord")
    print(f"Origine du site   : {origine['latitude']:.6f}, {origine['longitude']:.6f}")
    print(f"UTM               : {epsg}, est {origine['est']:.1f} m, nord {origine['nord']:.1f} m")
    print(f"KML               : {g['fichier_kml']}")


def afficher(p, totaux):
    """Affiche le récapitulatif et les alertes."""
    print(f"\n=== {p['nom']} ===")
    print(f"Unités            : {totaux['NombreUnites']} "
          f"({p['colonnes']} par ligne, pas {p['pas_x_m']} x {p['pas_y_m']} m)")
    print(f"Puissance         : {totaux['PuissanceTotaleKW']:.0f} kW "
          f"(disponible : {totaux['PuissanceDisponibleKW']:.0f} kW, "
          f"marge : {totaux['MargeKW']:.0f} kW)")
    print(f"GPU               : {totaux['NombreGPUTotal']}")
    print(f"vCPU (minimum)    : {totaux['vCPUMinTotal']}")
    print(f"Stockage          : {totaux['StockageTotalPB']:.1f} PB")
    print(f"Emprise fabricant : {totaux['EmpriseFabricantM2']:.0f} m2 "
          f"({p['emprise_par_unite_m2']:.0f} m2 par unité)")
    print(f"Emprise grille    : {totaux['EmpriseGrilleM2']:.0f} m2")
    print(f"Surface conteneurs: {totaux['SurfaceConteneursM2']:.1f} m2")

    # Contrôles
    alerte = False
    if totaux["MargeKW"] < 0:
        print(f"\nALERTE : puissance demandée supérieure de {-totaux['MargeKW']:.0f} kW "
              f"à la puissance disponible.")
        alerte = True
    if totaux["EmpriseGrilleM2"] < totaux["EmpriseFabricantM2"]:
        print("\nALERTE : la grille est plus serrée que l'emprise annoncée par le fabricant "
              "(dégagements possiblement insuffisants).")
        alerte = True
    if not alerte:
        print("\nContrôles OK : puissance disponible suffisante, emprise cohérente.")


def main():
    chemin = sys.argv[1] if len(sys.argv) > 1 else FICHIER_PARAMETRES
    parametres = lire_parametres(chemin)

    totaux = calculer_totaux(parametres)
    modele = implanter(parametres)
    ecrire_totaux(modele, totaux)

    # Géolocalisation facultative
    origine = epsg = None
    g = parametres.get("geolocalisation")
    if g:
        origine = calculer_origine(g)
        epsg = georeferencer(modele, origine)
        exporter_kml(parametres, g, origine)

    modele.write(parametres["fichier_sortie"])
    print(f"Fichier créé : {parametres['fichier_sortie']}")
    afficher(parametres, totaux)
    if g:
        afficher_geo(origine, epsg, g)


if __name__ == "__main__":
    main()
