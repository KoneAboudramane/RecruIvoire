"""Scoring ATS sémantique CV ↔ Offre via sentence-transformer.

Modèle utilisé : paraphrase-multilingual-MiniLM-L12-v2 (sentence-transformer,
multilingue, embeddings 384D).

Le modèle est chargé au premier appel et conservé en mémoire pour éviter
les rechargements coûteux (lazy singleton — Django ne paye pas le coût au boot).

Les embeddings sont mis en cache en base (JSONField sur Candidat et OffreEmploi)
et recalculés uniquement quand le contenu change (invalidation explicite). Le
scoring en lot (`scorer_candidats`, `scorer_toutes_candidatures`) calcule le
cosinus en Python (`_cosinus`, numpy) plutôt que via l'opérateur SQL natif
pgvector `<=>` (extension serveur indisponible sur l'hébergement cible).
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Optional

import numpy as np
from django.utils import timezone

logger = logging.getLogger(__name__)

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

_model = None
_model_lock = threading.Lock()


def get_model():
    """Charge le sentence-transformer une seule fois (thread-safe)."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer
                try:
                    from sentence_transformers.sentence_transformer.modules import Transformer, Pooling
                except ImportError:
                    from sentence_transformers.models import Transformer, Pooling  # type: ignore
                logger.info("Chargement du modèle ATS %s…", MODEL_NAME)
                try:
                    _model = SentenceTransformer(MODEL_NAME)
                except TypeError as e:
                    logger.warning(
                        "Chargement direct du modèle %s échoué (%s) — "
                        "reconstruction du pipeline word_embedding + Pooling.",
                        MODEL_NAME, e,
                    )
                    word_model = Transformer(MODEL_NAME)
                    dim = (
                        word_model.get_embedding_dimension()
                        if hasattr(word_model, 'get_embedding_dimension')
                        else word_model.get_word_embedding_dimension()
                    )
                    pooling = Pooling(dim, pooling_mode='mean')
                    _model = SentenceTransformer(modules=[word_model, pooling])
                logger.info("Modèle ATS chargé.")
    return _model


# ── Cache des embeddings ─────────────────────────────────────────────────────


def get_embedding_candidat(candidat) -> Optional[list]:
    """Retourne l'embedding du candidat depuis le cache, ou le calcule et le stocke."""
    if candidat.embedding is not None:
        return candidat.embedding
    texte = extraire_texte_candidat(candidat)
    if not texte.strip():
        return None
    emb = get_model().encode(texte).tolist()
    candidat.embedding = emb
    candidat.embedding_updated = timezone.now()
    candidat.save(update_fields=['embedding', 'embedding_updated'])
    return emb


def get_embedding_offre(offre) -> Optional[list]:
    """Retourne l'embedding de l'offre depuis le cache, ou le calcule et le stocke."""
    if offre.embedding is not None:
        return offre.embedding
    texte = extraire_texte_offre(offre)
    if not texte.strip():
        return None
    emb = get_model().encode(texte).tolist()
    offre.embedding = emb
    offre.embedding_updated = timezone.now()
    offre.save(update_fields=['embedding', 'embedding_updated'])
    return emb


def recalculer_embedding_candidat(candidat):
    """Recalcule et stocke l'embedding du candidat immédiatement."""
    texte = extraire_texte_candidat(candidat)
    if not texte.strip():
        candidat.embedding = None
        candidat.embedding_updated = None
    else:
        candidat.embedding = get_model().encode(texte).tolist()
        candidat.embedding_updated = timezone.now()
    candidat.save(update_fields=['embedding', 'embedding_updated'])


def recalculer_embedding_offre(offre):
    """Recalcule et stocke l'embedding de l'offre immédiatement."""
    texte = extraire_texte_offre(offre)
    if not texte.strip():
        offre.embedding = None
        offre.embedding_updated = None
    else:
        offre.embedding = get_model().encode(texte).tolist()
        offre.embedding_updated = timezone.now()
    offre.save(update_fields=['embedding', 'embedding_updated'])


# ── Extraction de texte ──────────────────────────────────────────────────────


def extraire_texte_candidat(candidat) -> str:
    """Concatène les champs textuels d'un Candidat pour scoring."""
    parts = [
        candidat.titreProfessionnel,
        candidat.profilCV,
        candidat.biographie,
        candidat.secteurActivite,
    ]
    return "\n".join(p for p in parts if p)


def extraire_texte_offre(offre) -> str:
    """Concatène les champs textuels d'une OffreEmploi pour scoring."""
    competences = offre.competencesRequises or []
    if isinstance(competences, str):
        try:
            competences = json.loads(competences)
        except (ValueError, TypeError):
            competences = [competences]
    competences_txt = ", ".join(str(c) for c in competences) if competences else ""

    parts = [
        offre.titre,
        offre.missions,
        offre.profilRecherche,
        ("Compétences requises : " + competences_txt) if competences_txt else "",
        offre.niveauEtudeRequis,
    ]
    return "\n".join(p for p in parts if p)


# ── Calibrage ────────────────────────────────────────────────────────────────

_BORNES_DEFAUT = (0.20, 0.75)
_bornes_cache = None

def _charger_bornes() -> tuple[float, float]:
    global _bornes_cache
    if _bornes_cache is not None:
        return _bornes_cache
    from pathlib import Path
    from django.conf import settings
    fichier = Path(settings.MEDIA_ROOT) / 'ml_models' / 'bornes_ats.json'
    if fichier.exists():
        try:
            data = json.loads(fichier.read_text())
            _bornes_cache = (float(data['borne_basse']), float(data['borne_haute']))
            return _bornes_cache
        except (KeyError, ValueError, json.JSONDecodeError):
            pass
    _bornes_cache = _BORNES_DEFAUT
    return _bornes_cache


def _calibrer(cosinus: float) -> tuple[float, str]:
    """Convertit un cosinus brut en (score 0-100, niveau)."""
    borne_basse, borne_haute = _charger_bornes()
    score = (cosinus - borne_basse) / (borne_haute - borne_basse) * 100.0
    score = max(0.0, min(100.0, score))
    if score >= 80:
        niveau = "EXCELLENT"
    elif score >= 60:
        niveau = "BON"
    elif score >= 40:
        niveau = "MOYEN"
    else:
        niveau = "FAIBLE"
    return round(score, 1), niveau


def _cosinus(a, b) -> float:
    """Similarité cosinus entre deux vecteurs (listes ou np.array)."""
    a, b = np.asarray(a), np.asarray(b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


# ── Scoring ──────────────────────────────────────────────────────────────────


def score_textes(cv_text: str, offre_text: str) -> dict:
    """Calcule la similarité sémantique entre un texte CV et un texte d'offre."""
    cv_text = (cv_text or "").strip()
    offre_text = (offre_text or "").strip()
    if not cv_text or not offre_text:
        return {
            "score": 0.0,
            "cosinus": 0.0,
            "niveau": "FAIBLE",
            "modele": MODEL_NAME,
            "warning": "Texte CV ou texte offre vide.",
        }

    model = get_model()
    emb_cv = model.encode(cv_text)
    emb_off = model.encode(offre_text)
    sim = _cosinus(emb_cv, emb_off)
    score, niveau = _calibrer(sim)

    return {
        "score": score,
        "cosinus": round(sim, 4),
        "niveau": niveau,
        "modele": MODEL_NAME,
    }


def score_candidature(candidature) -> dict:
    """Score une Candidature en utilisant les embeddings cachés."""
    emb_cv = get_embedding_candidat(candidature.candidat)
    emb_offre = get_embedding_offre(candidature.offre)

    if emb_cv is None or emb_offre is None:
        score, niveau, sim = 0.0, "FAIBLE", 0.0
    else:
        sim = _cosinus(emb_cv, emb_offre)
        score, niveau = _calibrer(sim)

    return {
        "candidature_id": candidature.id,
        "candidat": f"{candidature.candidat.prenom} {candidature.candidat.nom}",
        "offre": candidature.offre.titre,
        "score": score,
        "cosinus": round(sim, 4),
        "niveau": niveau,
        "modele": MODEL_NAME,
    }


def scorer_candidats(offre, candidats) -> list[dict]:
    """Score en lot des Candidat contre une offre, avec cache des embeddings.

    Les candidats dont l'embedding est déjà en base ne sont pas ré-encodés.
    Seuls ceux sans cache passent par le modèle, puis leur embedding est stocké.
    `Candidat.embedding` est un JSONField (pas de VectorField/pgvector — l'extension
    serveur n'est pas disponible sur l'hébergement cible), donc le cosinus est
    calculé en Python (`_cosinus`) plutôt que via l'opérateur SQL natif `<=>`.
    """
    candidats = list(candidats)
    if not candidats:
        return []

    emb_offre = get_embedding_offre(offre)
    if emb_offre is None:
        return []

    # Séparer les candidats avec/sans cache
    a_encoder = []
    for c in candidats:
        if c.embedding is None:
            texte = extraire_texte_candidat(c)
            a_encoder.append((c, texte))

    # Encoder en batch ceux qui n'ont pas de cache
    if a_encoder:
        textes = [t for _, t in a_encoder]
        model = get_model()
        embs = model.encode(textes, batch_size=8, show_progress_bar=False)
        now = timezone.now()
        for (cand, _), emb in zip(a_encoder, embs):
            cand.embedding = emb.tolist()
            cand.embedding_updated = now
            cand.save(update_fields=['embedding', 'embedding_updated'])

    resultats = []
    for cand in candidats:
        if cand.embedding is None:
            score, niveau, sim = 0.0, "FAIBLE", 0.0
        else:
            sim = _cosinus(cand.embedding, emb_offre)
            score, niveau = _calibrer(sim)

        ville = ''
        info = getattr(cand, 'informationPersonnelle', None)
        if info and info.ville:
            ville = info.ville

        resultats.append({
            "candidat_id": cand.id,
            "candidat":    f"{cand.prenom} {cand.nom}",
            "ville":       ville,
            "titre":       cand.titreProfessionnel or '',
            "score":       score,
            "cosinus":     round(sim, 4),
            "niveau":      niveau,
        })

    resultats.sort(key=lambda r: r["score"], reverse=True)
    return resultats


def scorer_toutes_candidatures(offre, candidatures) -> list[dict]:
    """Score en lot toutes les candidatures d'une offre, avec cache des embeddings.

    Cosinus calculé en Python (`_cosinus`) — voir `scorer_candidats` pour le
    détail du raisonnement (JSONField, pas de VectorField/pgvector).
    """
    candidatures = list(candidatures)
    if not candidatures:
        return []

    emb_offre = get_embedding_offre(offre)
    if emb_offre is None:
        return []

    # Séparer les candidats avec/sans cache
    a_encoder = []
    for c in candidatures:
        if c.candidat.embedding is None:
            texte = extraire_texte_candidat(c.candidat)
            a_encoder.append((c.candidat, texte))

    if a_encoder:
        textes = [t for _, t in a_encoder]
        model = get_model()
        embs = model.encode(textes, batch_size=8, show_progress_bar=False)
        now = timezone.now()
        for (cand, _), emb in zip(a_encoder, embs):
            cand.embedding = emb.tolist()
            cand.embedding_updated = now
            cand.save(update_fields=['embedding', 'embedding_updated'])

    resultats = []
    for cand in candidatures:
        emb_cand = cand.candidat.embedding
        if emb_cand is None:
            score, niveau, sim = 0.0, "FAIBLE", 0.0
        else:
            sim = _cosinus(emb_cand, emb_offre)
            score, niveau = _calibrer(sim)
        resultats.append({
            "candidature_id": cand.id,
            "candidat_id":    cand.candidat_id,
            "candidat":       f"{cand.candidat.prenom} {cand.candidat.nom}",
            "reference":      cand.reference,
            "score":          score,
            "cosinus":        round(sim, 4),
            "niveau":         niveau,
        })

    resultats.sort(key=lambda r: r["score"], reverse=True)
    return resultats
