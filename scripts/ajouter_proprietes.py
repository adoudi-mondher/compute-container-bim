"""
ajouter_proprietes.py - Ajoute un jeu de propriétés "Policloud" au conteneur.

Lit models/policloud-container-20ft.ifc, ajoute les caractéristiques publiques
du modèle Policloud 100 (source : policloud.com), puis enregistre le résultat
dans un NOUVEAU fichier (l'original n'est jamais modifié).

Usage (depuis la racine du projet, venv activé) :
    python scripts/ajouter_proprietes.py
"""

import sys
import ifcopenshell
import ifcopenshell.api.pset       # API pour créer/modifier des jeux de propriétés
import ifcopenshell.util.element   # pour relire les propriétés existantes

FICHIER_ENTREE = "models/policloud-container-20ft.ifc"
FICHIER_SORTIE = "models/policloud-container-20ft-enrichi.ifc"

# Nom du jeu de propriétés. Il ne commence pas par "Pset_" car ce préfixe est
# réservé aux jeux standards de l'IFC ; le nôtre est personnalisé.
NOM_PSET = "Policloud"

# Caractéristiques du Policloud 100 (données publiques du fabricant)
PROPRIETES = {
    "Modele": "Policloud 100",
    "ConteneurPieds": 20,           # conteneur 20 ft
    "PuissanceMaxKW": 100.0,        # puissance max en kW
    "NombreGPU": 104,
    "vCPUMin": 6000,                # le site indique "> 6 000"
    "StockagePB": 2.0,              # stockage en pétaoctets
    "TemperatureMinC": -40.0,       # plage de fonctionnement
    "TemperatureMaxC": 45.0,
    "EmpriseSolM2": 50.0,           # emprise au sol (dégagements inclus)
    "RefroidissementEau": False,    # pas de refroidissement à eau
    "Source": "https://www.policloud.com/#policloud-specifications",
}


def main():
    # 1. Ouverture du modèle
    try:
        modele = ifcopenshell.open(FICHIER_ENTREE)
    except Exception as erreur:
        print(f"Impossible d'ouvrir '{FICHIER_ENTREE}' : {erreur}")
        sys.exit(1)

    # 2. Recherche du conteneur (le seul IfcBuildingElementProxy du modèle)
    conteneurs = modele.by_type("IfcBuildingElementProxy")
    if len(conteneurs) != 1:
        print(f"Attendu : 1 conteneur, trouvé : {len(conteneurs)}. Arrêt.")
        sys.exit(1)
    conteneur = conteneurs[0]

    # 3. Réutilise le jeu de propriétés s'il existe déjà (évite les doublons
    #    si on relance le script), sinon le crée
    psets = ifcopenshell.util.element.get_psets(conteneur)
    if NOM_PSET in psets:
        pset = modele.by_id(psets[NOM_PSET]["id"])
    else:
        pset = ifcopenshell.api.pset.add_pset(
            modele, product=conteneur, name=NOM_PSET
        )

    # 4. Écriture des propriétés dans le jeu
    ifcopenshell.api.pset.edit_pset(modele, pset=pset, properties=PROPRIETES)

    # 5. Enregistrement dans un nouveau fichier
    modele.write(FICHIER_SORTIE)
    print(f"Fichier enregistré : {FICHIER_SORTIE}\n")

    # 6. Vérification : relecture des propriétés dans le fichier écrit
    verification = ifcopenshell.open(FICHIER_SORTIE)
    element = verification.by_type("IfcBuildingElementProxy")[0]
    resultat = ifcopenshell.util.element.get_psets(element).get(NOM_PSET, {})
    print(f"Propriétés '{NOM_PSET}' de '{element.Name}' :")
    for cle, valeur in resultat.items():
        if cle != "id":  # "id" est un champ technique ajouté par la bibliothèque
            print(f"  {cle} = {valeur}")


if __name__ == "__main__":
    main()
