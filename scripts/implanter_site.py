"""
implanter_site.py - Place N conteneurs de calcul sur un site et calcule les totaux.

Les paramètres du site sont lus dans un fichier JSON (dossier sites/) :
nombre d'unités, disposition en grille, emprise par unité, puissance disponible.
Le script génère un fichier IFC avec N conteneurs (chacun avec ses baies et sa porte),
affiche les totaux (puissance, GPU, stockage, emprise) et alerte si la puissance
demandée dépasse la puissance disponible. Les totaux sont aussi écrits dans l'IFC,
sur le site (jeu de propriétés "SiteCalcul").

Les valeurs par conteneur viennent de scripts/creer_conteneur.py (Policloud 100).

Usage (depuis la racine du projet, venv activé) :
    python scripts/implanter_site.py
    python scripts/implanter_site.py sites/autre-site.json
"""

import json
import math
import sys

import ifcopenshell
import ifcopenshell.api.project
import ifcopenshell.api.pset

# On réutilise les fonctions et constantes du script de création du conteneur
from creer_conteneur import (
    creer_structure, creer_conteneur, PROPRIETES,
    LONGUEUR, LARGEUR, HAUTEUR, EPAISSEUR,
)

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


def lire_parametres(chemin):
    """Lit et contrôle le fichier JSON. Arrête le script si quelque chose cloche."""
    try:
        with open(chemin, encoding="utf-8") as fichier:
            p = json.load(fichier)
    except (OSError, json.JSONDecodeError) as erreur:
        print(f"Impossible de lire '{chemin}' : {erreur}")
        sys.exit(1)

    # Clés présentes et du bon type
    for cle, type_attendu in CLES.items():
        if cle not in p:
            print(f"Paramètre manquant dans '{chemin}' : {cle}")
            sys.exit(1)
        if not isinstance(p[cle], type_attendu) or isinstance(p[cle], bool):
            print(f"Paramètre '{cle}' : type invalide ({type(p[cle]).__name__}).")
            sys.exit(1)

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


def implanter(p):
    """Crée le modèle IFC avec N conteneurs en grille. Retourne le modèle."""
    modele = ifcopenshell.api.project.create_file(version="IFC4")
    niveau, corps = creer_structure(modele)

    for i in range(p["nombre_unites"]):
        colonne = i % p["colonnes"]     # position dans la ligne
        ligne = i // p["colonnes"]      # numéro de la ligne
        creer_conteneur(
            modele, corps, niveau, f"Container 20ft - {i + 1:02d}",
            LONGUEUR, LARGEUR, HAUTEUR, EPAISSEUR,
            x=colonne * p["pas_x_m"], y=ligne * p["pas_y_m"],
        )
    return modele


def ecrire_totaux(modele, totaux):
    """Écrit les totaux dans l'IFC, sur le site (jeu de propriétés SiteCalcul)."""
    site = modele.by_type("IfcSite")[0]
    pset = ifcopenshell.api.pset.add_pset(modele, product=site, name="SiteCalcul")
    ifcopenshell.api.pset.edit_pset(modele, pset=pset, properties=totaux)


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
    modele.write(parametres["fichier_sortie"])

    print(f"Fichier créé : {parametres['fichier_sortie']}")
    afficher(parametres, totaux)


if __name__ == "__main__":
    main()
