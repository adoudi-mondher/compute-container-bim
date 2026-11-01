# compute-container-bim

Maquette BIM d'un conteneur de calcul (20 ft), générée et enrichie par scripts Python.

> Projet personnel d'apprentissage, indépendant. Non affilié à Policloud ni à Antimatter.
> Les données d'exemple proviennent des spécifications publiques du modèle Policloud 100
> (policloud.com, consulté le 27/10/2026).

![Conteneur généré par script, toit masqué : baies, armoire, extincteur, luminaires, grilles et ventilateurs, dans Blender avec Bonsai](docs/coupe-blender.png)

## Pourquoi ce projet

**BIM (Building Information Modeling)** : maquette numérique 3D dont chaque objet porte des
données exploitables. Ici, un conteneur de calcul n'est pas qu'une forme : il connaît sa
puissance, son nombre de GPU, son stockage et son emprise au sol.

L'objectif est de relier la géométrie d'une unité de calcul modulaire à ses caractéristiques
de puissance de calcul, puis d'automatiser par script ce qui se fait d'habitude à la main.

## Ce que le projet contient aujourd'hui

**Version 1 : volume simple, fait à la main**
- Un modèle IFC4 d'un conteneur 20 ft (6,058 x 2,438 x 2,591 m), créé avec Blender et Bonsai.
  C'est un bloc plein, sans détail interne.
- `scripts/ajouter_proprietes.py` : ajoute un jeu de propriétés `Policloud` au conteneur
  (puissance max, GPU, vCPU, stockage, plage de température, emprise au sol, refroidissement)
  et enregistre le résultat dans un nouveau fichier, sans toucher à l'original.

**Version 2 : coque creuse, entièrement générée par code**
- `scripts/creer_conteneur.py` : crée de zéro un fichier IFC4 avec la hiérarchie
  projet / site / bâtiment / niveau, puis un conteneur composé de 6 pièces (sol, toit,
  2 longs murs, 2 murs de bout, parois de 10 cm), regroupées sous un `IfcElementAssembly`.
  Les propriétés de calcul sont portées par l'assemblage.
- Une porte de service (1,0 x 2,0 m) dans un mur de bout : le mur est percé
  (`IfcOpeningElement` + `IfcRelVoidsElement`) puis rempli par la porte (`IfcRelFillsElement`).
- 8 baies informatiques illustratives (0,6 x 1,07 x 2,0 m, format 42U) alignées contre un long mur.
- Refroidissement par air : 4 grilles de ventilation (`IfcAirTerminal`) dans l'autre long mur,
  côté couloir, et 2 ventilateurs d'extraction (`IfcFan`) sur le toit, au-dessus des baies. Les
  murs et le toit sont percés sous chaque équipement.
- Équipements du couloir, côté porte : une armoire électrique (`IfcElectricDistributionBoard`),
  un extincteur (`IfcFireSuppressionTerminal`, type `USERDEFINED` car IFC4 n'a pas de type
  extincteur) et 3 luminaires (`IfcLightFixture`) au plafond.
- Un chemin de câbles (`IfcCableCarrierSegment`) sous le toit, au-dessus des baies et de
  l'armoire : c'est par là que passerait l'alimentation des baies.
- La fonction `creer_conteneur(...)` prend une position (x, y, z) : elle pourra être appelée
  plusieurs fois pour placer plusieurs unités.

**Plan en coupe**
- `scripts/generer_plan.py` : coupe le modèle IFC à une hauteur donnée (1,50 m par défaut) et
  dessine le plan vu de dessus en SVG : murs, baies B1 à B8, porte, grilles, armoire,
  extincteur, échelle graphique et dimensions hors tout. Il ne lit que les éléments extrudés depuis un rectangle, ce qui est le
  cas de tout ce que produit `creer_conteneur.py`.

![Plan en coupe horizontale à 1,50 m](docs/plan-coupe.svg)

**Implantation d'un site**
- `scripts/implanter_site.py` : place N conteneurs en grille sur un site, à partir d'un fichier
  de paramètres JSON (dossier `sites/`) : nombre d'unités, colonnes, pas de la grille, emprise
  par unité, puissance disponible.
- Calcule les totaux du site : puissance, GPU, vCPU, stockage, emprise. Ils sont aussi écrits
  dans l'IFC, sur le site (jeu de propriétés `SiteCalcul`).
- Contrôles automatiques : alerte si la puissance demandée dépasse la puissance disponible, ou
  si la grille est plus serrée que l'emprise annoncée par le fabricant.
- Exemple : `sites/exemple-10-unites.json` (10 unités, soit 1 MW).

![Plan en coupe d'un site de 10 conteneurs](docs/plan-site.svg)

**Outil de contrôle**
- `scripts/lire_ifc.py` : lit un fichier IFC et affiche pour chaque élément son nom, sa classe
  IFC, sa position et ses dimensions.

## Structure

```
compute-container-bim/
├── scripts/
│   ├── lire_ifc.py
│   ├── ajouter_proprietes.py
│   ├── creer_conteneur.py
│   ├── generer_plan.py
│   ├── implanter_site.py
│   └── geo.py
├── sites/
│   └── exemple-10-unites.json
├── models/
│   ├── policloud-container-20ft.ifc          v1 : bloc, fait à la main
│   ├── policloud-container-20ft-enrichi.ifc  v1 avec propriétés
│   ├── compute-container-20ft-v2.ifc         v2 : coque creuse, générée par script
│   └── site-exemple-10-unites.ifc            site de 10 conteneurs
├── docs/
│   ├── coupe-blender.png
│   ├── plan-coupe.svg
│   ├── plan-plafond.svg
│   └── plan-site.svg
├── LICENSE
├── requirements.txt
└── README.md
```

## Installation

Prérequis : Python 3.12 (testé avec 3.12.10).

```bash
python -m venv .venv
source .venv/Scripts/activate    # Git Bash sous Windows
pip install -r requirements.txt
```

## Utilisation

```bash
# Générer la coque creuse (écrase models/compute-container-20ft-v2.ifc)
python scripts/creer_conteneur.py

# Contrôler le résultat
python scripts/lire_ifc.py models/compute-container-20ft-v2.ifc

# Générer le plan en coupe (SVG)
python scripts/generer_plan.py
python scripts/generer_plan.py --hauteur 2.22 --sortie docs/plan-plafond.svg   # coupe au niveau du chemin de câbles

# Implanter 10 conteneurs sur un site (paramètres dans sites/exemple-10-unites.json)
python scripts/implanter_site.py

# Plan du site (échelle réduite, car le site fait environ 46 m de large)
python scripts/generer_plan.py models/site-exemple-10-unites.ifc --echelle 20 --sortie docs/plan-site.svg

# Ajouter les propriétés de calcul à la version 1
python scripts/ajouter_proprietes.py
```

Les fichiers `.ifc` s'ouvrent dans Blender avec l'extension Bonsai (*Open IFC Project*).
Pour modifier le modèle, relancer le script plutôt qu'enregistrer depuis Blender : Bonsai
réécrit le fichier IFC.

## Propriétés ajoutées (jeu `Policloud`)

| Propriété | Valeur |
|---|---|
| Modele | Policloud 100 |
| ConteneurPieds | 20 |
| PuissanceMaxKW | 100.0 |
| NombreGPU | 104 |
| vCPUMin | 6000 |
| StockagePB | 2.0 |
| TemperatureMinC / MaxC | -40.0 / 45.0 |
| EmpriseSolM2 | 50.0 (dégagements inclus) |
| RefroidissementEau | False |

## Limites connues

- La coque est une représentation simplifiée : parois de 10 cm, une seule porte, pas de
  ventilation ni de climatisation.
- L'agencement interne (baies, porte, ventilation, armoire, extincteur, luminaires, chemin de câbles) est
  **illustratif** : cotes de racks standard 42U et d'équipements courants, non issues du
  fabricant, dont l'agencement n'est pas public.
- Avec les ventilateurs, la hauteur hors tout dépasse le gabarit ISO (2,791 m contre 2,591 m) :
  en réalité, ils seraient démontables pour le transport.
- La porte est un simple panneau, sans sens d'ouverture : aucun contrôle de conflit avec
  l'armoire.
- `generer_plan.py` ne lit pas les maillages faits à la main (version 1).
- Le calcul de puissance est linéaire (N x puissance d'une unité) : il ne tient compte ni des
  pertes, ni du refroidissement, ni du réseau, et n'applique aucune marge de sécurité.
- Les scripts ont été testés uniquement sur ces modèles.
- Les valeurs sont celles annoncées par le fabricant, non vérifiées de façon indépendante.

## Pistes suivantes

- Marge de sécurité configurable sur la puissance disponible.
- Contrôles automatiques (propriétés obligatoires, cohérence des dimensions).

## Outils

Blender 5.2 LTS, Bonsai 0.9 (extension BIM), IfcOpenShell 0.9, Python 3.12.

## Licence

MIT, voir le fichier `LICENSE`.
