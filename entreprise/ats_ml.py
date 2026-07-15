"""
Inférence du modèle ML de re-ranking ATS pour les profils proposés au recruteur.

Architecture :
  • Modèle entraîné par `python manage.py entrainer_ats` à partir des
    `PropositionProfil` (signal : actions du recruteur — vu / contacté /
    invité / ignoré).
  • Persisté dans `media/ml_models/ats_current.joblib`.
  • Singleton lazy : chargé au 1er appel, ~1 ms par inférence.
  • Si aucun modèle n'a encore été entraîné, `est_disponible()` renvoie False
    et le fallback rules-based (score sentence-transformer brut) reste utilisé.

Format du fichier joblib :
    {
        'modele':   <sklearn estimator>,
        'metadata': {
            'date_entrainement': ISO datetime,
            'nb_exemples':       int,
            'feature_names':     list[str],
            'metriques':         dict,
            'version':           str,
        }
    }

Le modèle prend en entrée un vecteur de features dérivé du couple
(offre, candidat, score_ats_brut) et renvoie une prédiction 0-100
représentant la probabilité d'intérêt du recruteur.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


MODELE_PATH = Path(settings.MEDIA_ROOT) / 'ml_models' / 'ats_current.joblib'


# ──────────────────────────────────────────────────────────────────────────────
# Détection des dépendances + singleton modèle
# ──────────────────────────────────────────────────────────────────────────────

try:
    import joblib  # type: ignore
    import numpy as np  # type: ignore
    _DEPS_OK = True
except Exception as e:
    joblib = None  # type: ignore
    np = None  # type: ignore
    _DEPS_OK = False
    logger.info("joblib/numpy indisponibles (%s) — re-ranking ATS désactivé.", e)


_MODELE = None
_METADATA = None


def _charger():
    """Charge le modèle joblib une seule fois (singleton)."""
    global _MODELE, _METADATA
    if _MODELE is not None:
        return _MODELE
    if not _DEPS_OK:
        return None
    if not MODELE_PATH.exists():
        return None
    try:
        payload = joblib.load(MODELE_PATH)
        _MODELE   = payload.get('modele')
        _METADATA = payload.get('metadata', {})
        logger.info(
            "Modèle ATS chargé : %s exemples, entraîné le %s.",
            _METADATA.get('nb_exemples', '?'),
            _METADATA.get('date_entrainement', '?'),
        )
        return _MODELE
    except Exception as e:
        logger.exception("Échec du chargement du modèle ATS : %s", e)
        return None


def est_disponible() -> bool:
    """Vrai si un modèle ATS entraîné est chargeable."""
    return _charger() is not None


def metadata() -> dict:
    _charger()
    return dict(_METADATA or {})


def vider_cache() -> None:
    """Force le rechargement au prochain appel (après ré-entraînement)."""
    global _MODELE, _METADATA
    _MODELE = None
    _METADATA = None


# ──────────────────────────────────────────────────────────────────────────────
# Features (cohérent avec entrainer_ats)
# ──────────────────────────────────────────────────────────────────────────────

FEATURE_NAMES = [
    'score_ats_brut',              # 0-100, score sentence-transformer
    'cosinus',                     # -1..1
    'nb_competences_communes',     # int
    'nb_competences_candidat',     # int
    'nb_competences_offre',        # int
    'meme_ville',                  # 0/1
    'meme_pays',                   # 0/1
    'meme_secteur',                # 0/1
    'annees_experience_candidat',  # int (0 si inconnu)
    'candidat_a_portfolio',        # 0/1 (déjà filtré, mais info utile)
]


def construire_features(offre, candidat, score_ats_brut: float, cosinus: float) -> dict:
    """Construit le dict de features pour un couple (offre, candidat)."""
    from datetime import datetime

    # Compétences
    try:
        comp_offre_ids = set(offre.typesCompetence.values_list('id', flat=True))
    except Exception:
        comp_offre_ids = set()
    try:
        comp_cand_ids = {
            c.typeCompetence_id for c in candidat.competences.all()
            if c.typeCompetence_id
        }
    except Exception:
        comp_cand_ids = set()

    # Localisation
    info = getattr(candidat, 'informationPersonnelle', None)
    ville_c = ((info.ville or '') if info else '').strip().lower()
    pays_c  = ((info.pays  or '') if info else '').strip().lower()
    ville_o = (offre.ville or '').strip().lower()
    pays_o  = (offre.pays  or '').strip().lower()

    # Secteur
    secteur_c = (candidat.secteurActivite or '').strip().lower()
    secteur_o = ''
    if offre.entreprise and offre.entreprise.secteurActiviteRef:
        secteur_o = (offre.entreprise.secteurActiviteRef.nomSecteur or '').strip().lower()

    # Années d'expérience
    annees_exp = 0
    if candidat.datePremierEmploi:
        try:
            annees_exp = max(0, datetime.now().year - int(candidat.datePremierEmploi))
        except (TypeError, ValueError):
            annees_exp = 0

    return {
        'score_ats_brut':              float(score_ats_brut),
        'cosinus':                     float(cosinus),
        'nb_competences_communes':     float(len(comp_cand_ids & comp_offre_ids)),
        'nb_competences_candidat':     float(len(comp_cand_ids)),
        'nb_competences_offre':        float(len(comp_offre_ids)),
        'meme_ville':                  1.0 if (ville_c and ville_c == ville_o) else 0.0,
        'meme_pays':                   1.0 if (pays_c and pays_c == pays_o) else 0.0,
        'meme_secteur':                1.0 if (secteur_c and secteur_c == secteur_o) else 0.0,
        'annees_experience_candidat':  float(annees_exp),
        'candidat_a_portfolio':        1.0 if candidat.portfolioPublic else 0.0,
    }


def vecteur(features: dict):
    """Renvoie le vecteur numpy ordonné selon FEATURE_NAMES."""
    if np is None:
        return None
    return np.array([features[name] for name in FEATURE_NAMES], dtype=float)


# ──────────────────────────────────────────────────────────────────────────────
# Re-ranking
# ──────────────────────────────────────────────────────────────────────────────

def reranker(offre, candidats: list, scores: list) -> list:
    """Re-classe les résultats du scoring brut en fonction du modèle ML.

    Args:
        offre: instance `OffreEmploi`
        candidats: liste de `Candidat` (même ordre que `scores`)
        scores: liste de dicts retournés par `ats_predict.scorer_candidats()`

    Returns:
        La même liste de scores, ré-triée par score décroissant, avec :
          • `score`     remplacé par le score ML prédit (0-100)
          • `score_ats` ajouté pour conserver le score brut original
          • `methode`   = 'ml' (vs 'rules' si fallback)

    Si le modèle n'est pas chargeable, renvoie `scores` tel quel.
    """
    modele = _charger()
    if modele is None:
        return scores

    par_id = {c.id: c for c in candidats}

    X_list = []
    valides = []
    for r in scores:
        cand = par_id.get(r['candidat_id'])
        if cand is None:
            continue
        feat = construire_features(offre, cand, r['score'], r.get('cosinus', 0))
        v = vecteur(feat)
        if v is None:
            continue
        X_list.append(v)
        valides.append(r)

    if not X_list:
        return scores

    try:
        X = np.vstack(X_list)
        y_pred = modele.predict(X)
    except Exception as e:
        logger.exception("Inference ATS ML échouée : %s — fallback rules.", e)
        return scores

    nb = (_METADATA or {}).get('nb_exemples', 0)
    if nb >= 200:
        confiance = 0.9
    elif nb >= 100:
        confiance = 0.75
    elif nb >= 30:
        confiance = 0.6
    else:
        confiance = 0.4

    # Si confiance faible : on mixe brut + ML (50/50) plutôt que de remplacer
    alpha = max(0.5, confiance)  # poids du ML

    for r, y in zip(valides, y_pred):
        score_ml = max(0.0, min(100.0, float(y)))
        r['score_ats'] = r['score']
        r['score']    = round(alpha * score_ml + (1 - alpha) * r['score_ats'], 1)
        r['methode']  = 'ml'

    valides.sort(key=lambda r: r['score'], reverse=True)
    return valides
