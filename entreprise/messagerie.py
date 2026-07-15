"""Helpers pour le rendu de variables dans les modèles de message.

Sécurité : on n'utilise PAS le moteur de template Django (qui peut exécuter
des balises). On effectue un simple remplacement de placeholders
`{{ chemin.attribut }}` par leurs valeurs, en n'autorisant que des chemins
d'attributs simples (pas d'appels de méthode, pas d'accès aux dunders).
"""

import re


_PLACEHOLDER_RE = re.compile(r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s*\}\}')


def _resolve(chemin: str, contexte: dict):
    """Résout `'candidat.prenom'` en `contexte['candidat'].prenom` (lecture seule).

    Supporte aussi les contextes dict imbriqués (ex : `entretien.date` quand
    `entretien` est un dict {'date':..., 'heure':...}). On essaie d'abord
    l'accès attribut, puis l'accès clé si le segment est absent.
    """
    parts = chemin.split('.')
    racine = contexte.get(parts[0])
    if racine is None:
        return ''
    obj = racine
    for attr in parts[1:]:
        if attr.startswith('_'):
            return ''  # interdit l'accès aux dunders / privés
        # Accès attribut sur un objet OU clé sur un dict
        if isinstance(obj, dict):
            obj = obj.get(attr)
        else:
            obj = getattr(obj, attr, None)
        if obj is None:
            return ''
    return str(obj)


def rendre_template(texte: str, **contexte) -> str:
    """Remplace les `{{ var.attr }}` par leurs valeurs depuis le contexte.

    Args:
        texte: chaîne contenant des placeholders.
        **contexte: les objets nommés à exposer (candidat=..., offre=..., etc.).

    Returns:
        Le texte rendu, avec les placeholders remplacés. Les placeholders
        non résolus sont remplacés par une chaîne vide.
    """
    if not texte:
        return ''
    def _sub(match):
        return _resolve(match.group(1), contexte)
    return _PLACEHOLDER_RE.sub(_sub, texte)


# Liste des variables disponibles affichée à l'utilisateur (admin) lors
# de la création du modèle. Format : chemin → description.
#
# Les variables `entretien.*` ne sont passées au contexte que par le flow
# de planification d'entretien (`entretiens_planifier_bulk`) ; elles
# n'apparaissent donc dans le form que pour les modèles liés à un
# `typeEntretien`.
VARIABLES_DISPONIBLES = {
    # ── Toujours disponibles ───────────────────────────────────────────────
    'candidat.prenom':             "Prénom du candidat",
    'candidat.nom':                "Nom du candidat",
    'candidat.email':              "Email du candidat",
    'candidat.titreProfessionnel': "Titre professionnel du candidat",
    'offre.titre':                 "Titre de l'offre",
    'offre.reference':             "Référence de l'offre",
    'offre.ville':                 "Ville de l'offre",
    'entreprise.raisonSocial':     "Raison sociale de l'entreprise",
    'entreprise.siteWeb':          "Site web de l'entreprise",
    'recruteur.prenom':            "Prénom du recruteur",
    'recruteur.nom':               "Nom du recruteur",
    'recruteur.nomComplet':        "Nom complet du recruteur",
    'recruteur.email':             "Email du recruteur",
    'candidature.reference':       "Référence de la candidature",
    # ── Uniquement pour les modèles liés à un type d'entretien ─────────────
    'entretien.date':              "Date de l'entretien (ex : « lundi 20 mai 2026 »)",
    'entretien.heure':             "Heure de l'entretien (ex : « 09:00 »)",
    'entretien.duree':             "Durée prévue en minutes (ex : « 60 »)",
    'entretien.mode':              "Mode (Présentiel / Visioconférence / Téléphonique)",
    'entretien.lieu':              "Adresse, lien Meet/Zoom ou numéro de téléphone",
}

# Sous-ensembles utiles pour les vues qui veulent afficher les variables
# dans le form en les groupant.
VARIABLES_ENTRETIEN = {
    k: v for k, v in VARIABLES_DISPONIBLES.items() if k.startswith('entretien.')
}
VARIABLES_GENERIQUES = {
    k: v for k, v in VARIABLES_DISPONIBLES.items() if not k.startswith('entretien.')
}
