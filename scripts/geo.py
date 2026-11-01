"""
geo.py - Outils de géolocalisation, sans dépendance externe.

- vers_utm / depuis_utm : conversion WGS84 (latitude, longitude) <-> UTM (est, nord)
- en_dms_ifc            : angle décimal -> (degrés, minutes, secondes, millionièmes) pour l'IFC
- ecrire_kml            : écrit un fichier KML (polygones et points) lisible dans Google Earth

Limite : hémisphère nord uniquement (le faux nord de l'hémisphère sud n'est pas géré).
Précision : de l'ordre du millimètre sur quelques kilomètres (séries de Krüger).
"""

import math
from xml.sax.saxutils import escape

# Ellipsoïde WGS84
A = 6378137.0                 # demi-grand axe, en mètres
F = 1 / 298.257223563         # aplatissement
K0 = 0.9996                   # facteur d'échelle UTM
FAUX_EST = 500000.0           # décalage est appliqué à chaque fuseau

# Constantes dérivées (n = troisième aplatissement)
N = F / (2 - F)
A_RECT = A / (1 + N) * (1 + N**2 / 4 + N**4 / 64)
ALPHA = (N / 2 - 2 * N**2 / 3 + 5 * N**3 / 16,
         13 * N**2 / 48 - 3 * N**3 / 5,
         61 * N**3 / 240)
BETA = (N / 2 - 2 * N**2 / 3 + 37 * N**3 / 96,
        N**2 / 48 + N**3 / 15,
        17 * N**3 / 480)
DELTA = (2 * N - 2 * N**2 / 3 - 2 * N**3,
         7 * N**2 / 3 - 8 * N**3 / 5,
         56 * N**3 / 15)


def zone_utm(longitude):
    """Numéro de fuseau UTM (1 à 60) d'une longitude en degrés."""
    return int((longitude + 180) // 6) + 1


def meridien_central(zone):
    """Longitude du méridien central du fuseau, en degrés."""
    return (zone - 1) * 6 - 180 + 3


def vers_utm(latitude, longitude, zone=None):
    """(latitude, longitude) en degrés -> (est, nord, zone) en mètres."""
    if latitude < 0:
        raise ValueError("Hémisphère sud non géré.")
    if zone is None:
        zone = zone_utm(longitude)
    phi = math.radians(latitude)
    dlam = math.radians(longitude - meridien_central(zone))

    # Latitude "conforme", puis coordonnées sur la sphère de Gauss
    e = 2 * math.sqrt(N) / (1 + N)
    t = math.sinh(math.atanh(math.sin(phi)) - e * math.atanh(e * math.sin(phi)))
    xi_p = math.atan2(t, math.cos(dlam))
    eta_p = math.atanh(math.sin(dlam) / math.sqrt(1 + t * t))

    # Correction par la série de Krüger
    xi = xi_p + sum(ALPHA[j - 1] * math.sin(2 * j * xi_p) * math.cosh(2 * j * eta_p)
                    for j in (1, 2, 3))
    eta = eta_p + sum(ALPHA[j - 1] * math.cos(2 * j * xi_p) * math.sinh(2 * j * eta_p)
                      for j in (1, 2, 3))
    return FAUX_EST + K0 * A_RECT * eta, K0 * A_RECT * xi, zone


def depuis_utm(est, nord, zone):
    """(est, nord) en mètres -> (latitude, longitude) en degrés."""
    xi = nord / (K0 * A_RECT)
    eta = (est - FAUX_EST) / (K0 * A_RECT)

    xi_p = xi - sum(BETA[j - 1] * math.sin(2 * j * xi) * math.cosh(2 * j * eta)
                    for j in (1, 2, 3))
    eta_p = eta - sum(BETA[j - 1] * math.cos(2 * j * xi) * math.sinh(2 * j * eta)
                      for j in (1, 2, 3))

    chi = math.asin(math.sin(xi_p) / math.cosh(eta_p))
    phi = chi + sum(DELTA[j - 1] * math.sin(2 * j * chi) for j in (1, 2, 3))
    lam = math.radians(meridien_central(zone)) + math.atan2(math.sinh(eta_p), math.cos(xi_p))
    return math.degrees(phi), math.degrees(lam)


def en_dms_ifc(valeur):
    """
    Angle décimal -> (degrés, minutes, secondes, millionièmes de seconde), format de
    IfcCompoundPlaneAngleMeasure. Le signe est porté par chaque composante.
    """
    signe = -1 if valeur < 0 else 1
    total = round(abs(valeur) * 3600 * 1_000_000)      # tout en millionièmes de seconde
    degres, reste = divmod(total, 3600 * 1_000_000)
    minutes, reste = divmod(reste, 60 * 1_000_000)
    secondes, micro = divmod(reste, 1_000_000)
    return (signe * degres, signe * minutes, signe * secondes, signe * micro)


# ---------------------------------------------------------------- KML

def kml_polygone(nom, description, anneau, style):
    """Un polygone KML. 'anneau' = liste de (longitude, latitude), sans répéter le 1er point."""
    points = anneau + [anneau[0]]                       # un anneau KML est fermé
    coordonnees = " ".join(f"{lon:.8f},{lat:.8f},0" for lon, lat in points)
    return (f"<Placemark><name>{escape(nom)}</name>"
            f"<description>{escape(description)}</description>"
            f"<styleUrl>#{style}</styleUrl>"
            f"<Polygon><tessellate>1</tessellate><outerBoundaryIs><LinearRing>"
            f"<coordinates>{coordonnees}</coordinates>"
            f"</LinearRing></outerBoundaryIs></Polygon></Placemark>")


def kml_point(nom, description, longitude, latitude, style):
    """Un point KML (épingle)."""
    return (f"<Placemark><name>{escape(nom)}</name>"
            f"<description>{escape(description)}</description>"
            f"<styleUrl>#{style}</styleUrl>"
            f"<Point><coordinates>{longitude:.8f},{latitude:.8f},0</coordinates></Point>"
            f"</Placemark>")


def kml_ligne(nom, description, points, style):
    """Une ligne KML (route, piste). 'points' = liste de (longitude, latitude)."""
    coordonnees = " ".join(f"{lon:.8f},{lat:.8f},0" for lon, lat in points)
    return (f"<Placemark><name>{escape(nom)}</name>"
            f"<description>{escape(description)}</description>"
            f"<styleUrl>#{style}</styleUrl>"
            f"<LineString><tessellate>1</tessellate>"
            f"<coordinates>{coordonnees}</coordinates></LineString></Placemark>")


# Styles KML. Les couleurs sont au format aabbggrr (alpha, bleu, vert, rouge).
STYLES_KML = (
    '<Style id="conteneur"><LineStyle><color>ff202124</color><width>1.5</width></LineStyle>'
    '<PolyStyle><color>cc43403c</color></PolyStyle></Style>'
    '<Style id="emprise"><LineStyle><color>ff3da3e8</color><width>1.5</width></LineStyle>'
    '<PolyStyle><fill>0</fill></PolyStyle></Style>'
    '<Style id="repere"><IconStyle><scale>1.1</scale></IconStyle></Style>'
    '<Style id="pente0"><LineStyle><width>0</width></LineStyle><PolyStyle><color>aa327d2e</color></PolyStyle></Style>'
    '<Style id="pente1"><LineStyle><width>0</width></LineStyle><PolyStyle><color>aa1ac1e8</color></PolyStyle></Style>'
    '<Style id="pente2"><LineStyle><width>0</width></LineStyle><PolyStyle><color>aa1a82e8</color></PolyStyle></Style>'
    '<Style id="pente3"><LineStyle><width>0</width></LineStyle><PolyStyle><color>aa3c3cd9</color></PolyStyle></Style>'
    '<Style id="route"><LineStyle><color>ff3c3cd9</color><width>3</width></LineStyle></Style>'
    '<Style id="piste"><LineStyle><color>ff00d7ff</color><width>2</width></LineStyle></Style>'
    '<Style id="batiment"><LineStyle><color>ffffffff</color><width>1</width></LineStyle>'
    '<PolyStyle><color>aa3c3cd9</color></PolyStyle></Style>'
)


def ecrire_kml(chemin, nom, description, dossiers):
    """
    Écrit un fichier KML.
    dossiers : liste de (nom_du_dossier, [elements_kml]) ; les éléments viennent de
    kml_polygone / kml_point.
    """
    morceaux = ['<?xml version="1.0" encoding="UTF-8"?>',
                '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
                f"<name>{escape(nom)}</name>",
                f"<description>{escape(description)}</description>",
                STYLES_KML]
    for nom_dossier, elements in dossiers:
        morceaux.append(f"<Folder><name>{escape(nom_dossier)}</name>")
        morceaux.extend(elements)
        morceaux.append("</Folder>")
    morceaux.append("</Document></kml>")
    with open(chemin, "w", encoding="utf-8") as fichier:
        fichier.write("\n".join(morceaux))
