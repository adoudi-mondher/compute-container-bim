# compute-container-bim

Maquette BIM d'un conteneur de calcul (20 ft), enrichie et pilotée par scripts Python.

> Projet personnel d'apprentissage, indépendant. Non affilié à Policloud ni à Antimatter.
> Les données d'exemple proviennent des spécifications publiques du modèle Policloud 100
> (policloud.com, consulté le 27/10/2026).

## Pourquoi ce projet

**BIM (Building Information Modeling)** : maquette numérique 3D dont chaque objet porte des
données exploitables. Ici, un conteneur de calcul n'est pas qu'une forme : il connaît sa
puissance, son nombre de GPU, son stockage et son emprise au sol.

L'objectif est de relier la géométrie d'une unité de calcul modulaire à ses caractéristiques
de puissance de calcul, puis d'automatiser par script ce qui se fait d'habitude à la main.

## Ce que le projet contient aujourd'hui

- Un modèle IFC4 d'un conteneur 20 ft (6,058 x 2,438 x 2,591 m), créé avec Blender et Bonsai.
  Il s'agit d'un volume simple, sans détail interne.
- `scripts/lire_ifc.py` : lit un fichier IFC et affiche pour chaque élément son nom, sa classe
  IFC, sa position et ses dimensions.
- `scripts/ajouter_proprietes.py` : ajoute un jeu de propriétés `Policloud` au conteneur
  (puissance max, GPU, vCPU, stockage, plage de température, emprise au sol, refroidissement)
  et enregistre le résultat dans un nouveau fichier, sans toucher à l'original.

## Structure

```
compute-container-bim/
├── scripts/
│   ├── lire_ifc.py
│   └── ajouter_proprietes.py
├── models/
│   ├── policloud-container-20ft.ifc          modèle d'origine
│   └── policloud-container-20ft-enrichi.ifc  modèle avec propriétés
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
# Lire le modèle
python scripts/lire_ifc.py

# Lire un autre fichier
python scripts/lire_ifc.py models/policloud-container-20ft-enrichi.ifc

# Ajouter les propriétés de calcul
python scripts/ajouter_proprietes.py
```

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

- Le modèle 3D est un volume simplifié : l'agencement interne réel n'est pas public.
- Les scripts ont été testés uniquement sur ce modèle.
- Les valeurs sont celles annoncées par le fabricant, non vérifiées de façon indépendante.

## Pistes suivantes

- Conteneur en coque creuse (sol, parois, toit) avec portes, sous un élément parent unique.
- Implantation de N unités sur un terrain (50 m² par unité) avec calcul automatique de la
  puissance totale, du nombre de GPU et de l'emprise du site.
- Contrôles automatiques (propriétés obligatoires, cohérence des dimensions).

## Outils

Blender 5.2 LTS, Bonsai 0.9 (extension BIM), IfcOpenShell 0.9, Python 3.12.
