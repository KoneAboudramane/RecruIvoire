"""
Extraction de features pour le modèle ML de matching.

Une feature = une variable d'entrée du modèle. Le même module est utilisé :
  • à l'ENTRAÎNEMENT (commande `entrainer_matching`) pour construire le X
  • à l'INFÉRENCE (`matching_ml.predire`) pour scorer une nouvelle (candidat, offre)

Garantir la cohérence des deux est CRUCIAL : si on change FEATURE_NAMES, il
faut ré-entraîner le modèle.

Features incluses (15) :
  - 6 scores rules-based (un par critère, hors affinité)
  - 1 similarité sémantique (embedding @ embedding) × 100
  - 4 caractéristiques structurelles de l'offre
  - 4 caractéristiques structurelles du candidat

Toutes les valeurs sont des floats (sklearn les attend ainsi).
"""

from __future__ import annotations

from typing import Optional

try:
    import numpy as np  # type: ignore
except Exception:
    np = None  # type: ignore


# ──────────────────────────────────────────────────────────────────────────────
# Liste ordonnée des noms de features — DOIT correspondre au modèle entraîné
# ──────────────────────────────────────────────────────────────────────────────

FEATURE_NAMES = [
    # Scores rules-based (chacun 0-100)
    'score_competences',
    'score_localisation',
    'score_experience',
    'score_contrat',
    'score_secteur',
    'score_langues',
    # Sémantique (0-100)
    'similarite_semantique',
    # Structure offre
    'offre_nb_competences',
    'offre_salaire_min',
    'offre_salaire_max',
    'offre_nb_postes',
    # Structure candidat
    'candidat_nb_competences',
    'candidat_nb_langues',
    'candidat_annees_exp',
    'candidat_a_portfolio',
]


# ──────────────────────────────────────────────────────────────────────────────
# Construction du vecteur
# ──────────────────────────────────────────────────────────────────────────────

def construire_features(profil_candidat, offre, embedding_candidat=None) -> dict:
    """Construit le dict de features pour un couple (candidat, offre).

    Args:
        profil_candidat: instance de `matching.ProfilCandidat`
        offre: instance d'`entreprise.OffreEmploi`
        embedding_candidat: numpy array (optionnel) — embedding pré-calculé

    Renvoie un dict {feature_name: float} contenant TOUTES les clés de
    FEATURE_NAMES (jamais de KeyError côté modèle).
    """
    from . import matching, matching_semantic as ms

    # 1. Scores rules par critère (on rappelle chaque fonction critère)
    rules_criteres = [fn(profil_candidat, offre) for fn in matching.CRITERES]
    scores = {c['cle']: c['score'] for c in rules_criteres}

    # 2. Similarité sémantique
    similarite = 0.0
    if embedding_candidat is not None and ms.est_disponible():
        emb_offre = ms.embedding_offre(offre)
        if emb_offre is not None:
            similarite = max(0.0, min(1.0, float(embedding_candidat @ emb_offre))) * 100

    # 3. Structure offre
    nb_comp_offre = 0
    try:
        nb_comp_offre = offre.typesCompetence.count() + len(offre.competencesRequises or [])
    except Exception:
        pass

    return {
        'score_competences':        float(scores.get('competences', 0)),
        'score_localisation':       float(scores.get('localisation', 0)),
        'score_experience':         float(scores.get('experience', 0)),
        'score_contrat':            float(scores.get('contrat', 0)),
        'score_secteur':            float(scores.get('secteur', 0)),
        'score_langues':            float(scores.get('langues', 0)),
        'similarite_semantique':    float(similarite),
        'offre_nb_competences':     float(nb_comp_offre),
        'offre_salaire_min':        float(offre.salaireMin or 0),
        'offre_salaire_max':        float(offre.salaireMax or 0),
        'offre_nb_postes':          float(offre.nombrePostes or 1),
        'candidat_nb_competences':  float(len(profil_candidat.competences_libelle)),
        'candidat_nb_langues':      float(len(profil_candidat.langues_libelle)),
        'candidat_annees_exp':      float(profil_candidat.annees_experience or 0),
        'candidat_a_portfolio':     1.0,  # toujours, depuis Candidature.urlPortfolio auto
    }, rules_criteres


def vecteur(features: dict):
    """Renvoie un vecteur numpy ordonné selon FEATURE_NAMES."""
    if np is None:
        raise RuntimeError("numpy n'est pas installé.")
    return np.array([features.get(k, 0.0) for k in FEATURE_NAMES], dtype=float)


# ──────────────────────────────────────────────────────────────────────────────
# Mapping statut → label (score cible pour la régression)
# ──────────────────────────────────────────────────────────────────────────────

# Encode le « succès » d'une candidature pour le modèle.
# Les statuts non-listés (POSTULEE seul, etc.) sont EXCLUS de l'entraînement
# car ils n'apportent pas de signal final.
LABELS_PAR_STATUT = {
    'EMBAUCHEE':        100.0,  # Succès absolu
    'ACCEPTEE':          85.0,  # Validé par recruteur
    'ENTRETIEN':         70.0,  # En progression haute
    'TEST':              65.0,  # En progression
    'PRESELECTIONNEE':   60.0,  # Short-list
    'VUE':               40.0,  # Vu mais pas avancé
    'REFUSEE':           10.0,  # Échec
    # POSTULEE et RETIREE → exclus (pas de signal exploitable)
}


def label_pour_statut(code_statut: str) -> Optional[float]:
    """Renvoie le label numérique pour un code statut, ou None si à exclure."""
    return LABELS_PAR_STATUT.get(code_statut)
