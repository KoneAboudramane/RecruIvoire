"""
Similarité sémantique candidat ↔ offre via sentence-transformers.

Modèle utilisé : `paraphrase-multilingual-MiniLM-L12-v2`
  - 118M paramètres, FR / EN natif (et 48 autres langues)
  - ~480 Mo (téléchargé 1× par HuggingFace dans le cache utilisateur)
  - Encodage : ~50-100 ms / texte côté CPU

Stratégie de performance :
  - **Singleton lazy** : le modèle ne charge qu'au 1er appel (5 s la 1ʳᵉ fois).
  - **Batch encode** : `embed(list_de_textes)` est bien plus rapide que N appels.
  - **Cache offre** : `embedding_offre(offre)` mémorise par `offre.pk` (dict module).
    Mémoire : 384 floats × N offres ≈ 1,5 Ko/offre — négligeable.
  - **Embedding candidat** : calculé 1× au `__init__` du Matcher, réutilisé pour
    toutes les offres scorées dans la même requête.

Graceful degradation :
  - Si `sentence-transformers` n'est PAS installé, `est_disponible()` renvoie False ;
    le moteur `matching.py` saute le critère sémantique (score neutre 60).
  - Aucune erreur visible côté utilisateur.

Installation côté serveur :

    pip install sentence-transformers

Au 1er usage : ~480 Mo téléchargés depuis huggingface.co, mis en cache dans
``%USERPROFILE%/.cache/huggingface/`` (Windows) ou ``~/.cache/huggingface/`` (Unix).
"""  # noqa: W605

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

NOM_MODELE = 'paraphrase-multilingual-MiniLM-L12-v2'

# ──────────────────────────────────────────────────────────────────────────────
# Détection de la dépendance + singleton modèle
# ──────────────────────────────────────────────────────────────────────────────

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    import numpy as np  # type: ignore
    _DEPENDANCES_OK = True
except Exception as e:
    SentenceTransformer = None  # type: ignore
    np = None                    # type: ignore
    _DEPENDANCES_OK = False
    logger.info("sentence-transformers indisponible (%s) — matching sémantique désactivé.", e)


_MODELE = None  # singleton, chargé au 1er appel


def est_disponible() -> bool:
    """Renvoie True si le moteur sémantique peut être utilisé."""
    return _DEPENDANCES_OK


def _get_modele():
    """Charge le modèle au 1er appel (lazy)."""
    global _MODELE
    if _MODELE is None:
        if not _DEPENDANCES_OK:
            return None
        logger.info("Chargement du modèle %s…", NOM_MODELE)
        _MODELE = SentenceTransformer(NOM_MODELE)
        logger.info("Modèle chargé.")
    return _MODELE


# ──────────────────────────────────────────────────────────────────────────────
# Encodage
# ──────────────────────────────────────────────────────────────────────────────

def embed(textes: list) -> Optional['np.ndarray']:
    """Encode un BATCH de textes en vecteurs normalisés (cosinus = dot product).

    Renvoie None si la dépendance est indisponible.
    """
    if not _DEPENDANCES_OK:
        return None
    modele = _get_modele()
    if modele is None:
        return None
    # normalize_embeddings=True → ||v|| = 1, donc cosinus(a,b) = a @ b
    return modele.encode(textes, normalize_embeddings=True, show_progress_bar=False)


def similarite(text_a: str, text_b: str) -> float:
    """Cosinus de similarité entre 2 textes, dans [0, 1] (approx).

    Renvoie 0.0 si indisponible ou textes vides.
    """
    if not (text_a and text_b) or not _DEPENDANCES_OK:
        return 0.0
    embs = embed([text_a, text_b])
    if embs is None:
        return 0.0
    return float(embs[0] @ embs[1])


# ──────────────────────────────────────────────────────────────────────────────
# Construction des textes représentatifs
# ──────────────────────────────────────────────────────────────────────────────

def texte_offre(offre) -> str:
    """Concatène les champs textuels de l'offre pour l'embedding."""
    parts = [
        getattr(offre, 'titre', '') or '',
        getattr(offre, 'missions', '') or '',
        getattr(offre, 'profilRecherche', '') or '',
    ]
    # Compétences requises (JSON libre)
    for c in (offre.competencesRequises or []):
        if str(c).strip():
            parts.append(str(c).strip())
    # Compétences M2M référentiel
    try:
        for tc in offre.typesCompetence.all():
            if tc.nomCompetence:
                parts.append(tc.nomCompetence)
    except Exception:
        pass
    # Secteur d'activité de l'entreprise
    try:
        if offre.entreprise and offre.entreprise.secteurActiviteRef:
            parts.append(offre.entreprise.secteurActiviteRef.nomSecteur or '')
    except Exception:
        pass
    return ' • '.join(p for p in parts if p)


def texte_candidat(candidat) -> str:
    """Concatène les champs textuels du candidat (CV) pour l'embedding."""
    parts = [
        getattr(candidat, 'titreProfessionnel', '') or '',
        getattr(candidat, 'profilCV', '') or '',
        getattr(candidat, 'biographie', '') or '',
        getattr(candidat, 'secteurActivite', '') or '',
    ]
    # Compétences
    try:
        for c in candidat.competences.all():
            if c.typeCompetence and c.typeCompetence.nomCompetence:
                parts.append(c.typeCompetence.nomCompetence)
            elif c.nomLibre:
                parts.append(c.nomLibre)
    except Exception:
        pass
    # Expériences professionnelles : intitulé + entreprise + description
    try:
        for exp in candidat.experiencesProfessionnelles.all():
            if exp.entrepriseLibre:
                parts.append(exp.entrepriseLibre)
            elif exp.entreprise:
                parts.append(str(exp.entreprise))
            if exp.description:
                parts.append(exp.description)
            # postes occupés
            for poste in exp.postes.all():
                if poste.titreLibre:
                    parts.append(poste.titreLibre)
                elif poste.poste:
                    parts.append(poste.poste.nomPoste or '')
    except Exception:
        pass
    # Formations : intitulé/diplôme
    try:
        for f in candidat.formations.all():
            if getattr(f, 'titreLibre', ''):
                parts.append(f.titreLibre)
            if getattr(f, 'description', ''):
                parts.append(f.description)
    except Exception:
        pass
    return ' • '.join(p for p in parts if p)


# ──────────────────────────────────────────────────────────────────────────────
# Cache des embeddings offre (par offre.pk)
# ──────────────────────────────────────────────────────────────────────────────
# Mémoire-friendly : on garde les 1024 dernières offres encodées.
@lru_cache(maxsize=1024)
def _embedding_offre_par_pk(offre_pk: int, signature: str):
    """Helper interne — la signature force l'invalidation si le titre change."""
    # On ré-importe dans la fonction pour éviter import circulaire
    from entreprise.models import OffreEmploi
    offre = (
        OffreEmploi.objects
        .filter(pk=offre_pk)
        .select_related('entreprise__secteurActiviteRef')
        .prefetch_related('typesCompetence')
        .first()
    )
    if not offre:
        return None
    texte = texte_offre(offre)
    if not texte:
        return None
    arr = embed([texte])
    return arr[0] if arr is not None else None


def embedding_offre(offre):
    """Renvoie l'embedding numpy d'une offre (avec cache lru)."""
    if not _DEPENDANCES_OK:
        return None
    # Signature courte basée sur le titre — change → invalide le cache
    sig = (getattr(offre, 'titre', '') or '')[:60]
    return _embedding_offre_par_pk(offre.pk, sig)


def embedding_candidat(candidat):
    """Renvoie l'embedding d'un candidat (calculé à la demande)."""
    if not _DEPENDANCES_OK:
        return None
    texte = texte_candidat(candidat)
    if not texte:
        return None
    arr = embed([texte])
    return arr[0] if arr is not None else None


def invalider_cache_offres() -> None:
    """À appeler après mise à jour massive d'offres (admin, batch)."""
    _embedding_offre_par_pk.cache_clear()
