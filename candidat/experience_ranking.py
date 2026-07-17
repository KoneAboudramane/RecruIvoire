"""Classement local (sans IA) du contenu d'un CV par pertinence vis-à-vis
d'une offre — réutilise les embeddings sentence-transformers déjà en place
pour le matching sémantique (`matching_semantic.py`), aucun nouveau pipeline
ML. Sert de contexte de lecture seule pour la réécriture IA (`cv_adaptation.py`)
et de bonus gratuit (réordonnancement des compétences).
"""
from __future__ import annotations

import logging

from . import matching_semantic

logger = logging.getLogger(__name__)


def _texte_experience(exp: dict) -> str:
    postes = ' '.join((p.get('titre') or '') for p in (exp.get('postes') or []))
    return ' '.join(p for p in (postes, exp.get('entreprise') or '') if p).strip()


def classer_experiences_par_pertinence(experiences: list, offre, top_n: int = 3) -> list:
    """Renvoie les `top_n` expériences (dicts, format éditeur CV) les plus
    proches sémantiquement de `offre`, dans l'ordre de pertinence décroissante.

    Repli sur les `top_n` premières expériences dans l'ordre source si le
    moteur sémantique est indisponible ou si aucun texte n'est exploitable
    (même philosophie de dégradation gracieuse que `matching_semantic.py`).
    """
    if not experiences:
        return []
    if not matching_semantic.est_disponible():
        return experiences[:top_n]

    textes = [_texte_experience(e) for e in experiences]
    if not any(textes):
        return experiences[:top_n]

    embedding_offre = matching_semantic.embedding_offre(offre)
    if embedding_offre is None:
        return experiences[:top_n]

    # Textes vides encodés quand même (batch unique) — score neutre bas, pas
    # d'erreur, elles finissent simplement en fin de classement.
    vecteurs = matching_semantic.embed([t or ' ' for t in textes])
    if vecteurs is None:
        return experiences[:top_n]

    scores = [float(v @ embedding_offre) for v in vecteurs]
    classees = [exp for _, exp in sorted(zip(scores, experiences), key=lambda t: t[0], reverse=True)]
    return classees[:top_n]


def reordonner_competences(competences: list, offre) -> list:
    """Réordonne les compétences du CV (format éditeur) en mettant en avant
    celles qui matchent l'offre — bonus local sans IA. Compare le libellé de
    chaque compétence à `offre.competencesRequises` (JSON libre) et aux noms
    des `offre.typesCompetence` (référentiel).
    """
    if not competences:
        return competences

    requises = {str(c).strip().lower() for c in (offre.competencesRequises or []) if str(c).strip()}
    try:
        requises |= {tc.nomCompetence.strip().lower() for tc in offre.typesCompetence.all() if tc.nomCompetence}
    except Exception:
        pass
    if not requises:
        return competences

    def _libelle(c: dict) -> str:
        return str(c.get('nom') or '').strip().lower()

    matches    = [c for c in competences if _libelle(c) in requises]
    non_match  = [c for c in competences if _libelle(c) not in requises]
    return matches + non_match
