"""
Inférence du modèle ML de matching (chargé depuis disque).

Architecture :
  - Le modèle est entraîné par la commande `python manage.py entrainer_matching`
    et persisté dans `media/ml_models/matching_current.joblib`.
  - Ce module charge le modèle au 1er appel (singleton lazy), puis prédit en
    ~1 ms par appel.
  - Si aucun modèle n'a été entraîné, `est_disponible()` renvoie False et
    `matching.py` retombe sur le scoring à règles + sémantique.

Format du fichier joblib (dict) :
    {
        'modele':            <sklearn estimator>,
        'metadata': {
            'date_entrainement':  ISO datetime,
            'nb_exemples':        int,
            'feature_names':      list[str],
            'metriques':          dict,
            'version':            str,
        }
    }
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


# Chemin du modèle "courant" (rétroportable) — on ne touche jamais aux modèles
# historiques (snapshots datés sauvegardés en parallèle par la commande).
MODELE_PATH = Path(settings.MEDIA_ROOT) / 'ml_models' / 'matching_current.joblib'


# ──────────────────────────────────────────────────────────────────────────────
# Détection sklearn + singleton
# ──────────────────────────────────────────────────────────────────────────────

try:
    import joblib  # type: ignore
    import numpy as np  # type: ignore
    _DEPENDANCES_OK = True
except Exception as e:
    joblib = None  # type: ignore
    np = None  # type: ignore
    _DEPENDANCES_OK = False
    logger.info("joblib/numpy indisponibles (%s) — inférence ML désactivée.", e)


_MODELE = None
_METADATA = None


def _charger():
    """Charge le modèle joblib (singleton). Renvoie None si absent / erreur."""
    global _MODELE, _METADATA
    if _MODELE is not None:
        return _MODELE
    if not _DEPENDANCES_OK:
        return None
    if not MODELE_PATH.exists():
        return None
    try:
        payload = joblib.load(MODELE_PATH)
        _MODELE   = payload.get('modele')
        _METADATA = payload.get('metadata', {})
        logger.info(
            "Modèle de matching chargé : %s exemples, entraîné le %s.",
            _METADATA.get('nb_exemples', '?'),
            _METADATA.get('date_entrainement', '?'),
        )
        return _MODELE
    except Exception as e:
        logger.exception("Échec du chargement du modèle de matching : %s", e)
        return None


def est_disponible() -> bool:
    """Renvoie True si un modèle entraîné est disponible et chargeable."""
    return _charger() is not None


def metadata() -> dict:
    """Métadonnées du modèle chargé (date, nb exemples, métriques)."""
    _charger()
    return dict(_METADATA or {})


def vider_cache() -> None:
    """Recharge le modèle au prochain appel (utile après ré-entraînement)."""
    global _MODELE, _METADATA
    _MODELE = None
    _METADATA = None


# ──────────────────────────────────────────────────────────────────────────────
# Inférence
# ──────────────────────────────────────────────────────────────────────────────

def predire(profil_candidat, offre, embedding_candidat=None) -> Optional[dict]:
    """Prédit le score ML pour un couple (candidat, offre).

    Renvoie le même dict que `matching._score_rules()` pour que l'UI puisse
    le consommer indifféremment :

        {
            'score':    int 0-100,
            'methode':  'ml',
            'criteres': list[dict],   # mêmes critères que rules + critère 'ml_global'
            'confiance': float 0-1,
        }

    Renvoie None si le modèle n'est pas chargeable → fallback rules.
    """
    modele = _charger()
    if modele is None:
        return None

    from .ml_features import construire_features, vecteur
    features, rules_criteres = construire_features(profil_candidat, offre, embedding_candidat)
    X = vecteur(features).reshape(1, -1)

    try:
        y_pred = float(modele.predict(X)[0])
    except Exception as e:
        logger.exception("Échec inference modèle : %s — fallback rules.", e)
        return None

    score = max(0, min(100, int(round(y_pred))))

    # Confiance basée sur la taille du dataset d'entraînement (heuristique)
    nb = (_METADATA or {}).get('nb_exemples', 0)
    if nb >= 500:
        confiance = 0.9
    elif nb >= 200:
        confiance = 0.75
    elif nb >= 50:
        confiance = 0.6
    else:
        confiance = 0.4

    # On enrichit les critères avec un "score ML global" en tête de liste
    # pour informer l'utilisateur que c'est une prédiction.
    criteres_complets = [{
        'cle':    'ml_score',
        'label':  'Score ML',
        'icone':  '🤖',
        'poids':  0,            # informatif, déjà inclus dans le score global
        'score':  score,
        'status': 'success' if score >= 70 else ('partial' if score >= 40 else 'missing'),
        'note':   f"Prédit par le modèle (entraîné sur {nb} candidatures).",
    }, *rules_criteres]

    return {
        'score':     score,
        'methode':   'ml',
        'criteres':  criteres_complets,
        'confiance': confiance,
    }
