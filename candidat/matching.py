"""
Moteur de matching candidat ↔ offre d'emploi.

Architecture en deux temps :

1. **Rules-based (actif aujourd'hui)** : score pondéré déterministe calculé à
   partir des champs du `Candidat` et de l'`OffreEmploi`. Chaque critère
   contribue à hauteur de son poids dans une note globale 0-100.

2. **ML (à brancher quand la table Candidature aura des labels)** : la fonction
   `_score_ml(...)` retourne `None` aujourd'hui — elle est appelée AVANT le
   moteur de règles et celles-ci servent de repli (fallback) tant que le modèle
   n'est pas disponible/fiable. Quand vous aurez la table Candidature avec un
   statut final (EMBAUCHEE / REFUSEE / etc.), créez `candidat/matching_ml.py`
   avec :

       - un script d'entraînement (`python manage.py entrainer_matching`)
       - un loader `charger_modele()` qui renvoie le modèle joblib
       - implémentez `_score_ml(profil, offre)` ci-dessous

   Le reste du code (vues, templates) ne changera pas.

Usage typique :

    from candidat.matching import Matcher

    matcher = Matcher(candidat)              # extrait le profil 1 seule fois
    for offre in offres_qs:
        resultat = matcher.scorer(offre)      # appelé en boucle (rapide)
        # resultat = {'score': int, 'methode': 'rules'|'ml', 'criteres': [...]}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Optional


# ──────────────────────────────────────────────────────────────────────────────
# Configuration des poids (doit sommer à 100)
# ──────────────────────────────────────────────────────────────────────────────

POIDS = {
    'affinite':     20,   # similarité sémantique CV ↔ offre (sentence-transformers)
    'competences':  25,
    'localisation': 15,
    'experience':   15,
    'contrat':      10,
    'secteur':      10,
    'langues':       5,
}
assert sum(POIDS.values()) == 100, "Les poids doivent sommer à 100."

# Seuil de confiance ML : si la prédiction ML est moins fiable que ça, on
# retombe sur le score à règles. Utilisé une fois que `_score_ml` sera branché.
SEUIL_CONFIANCE_ML = 0.55

# Clé de session utilisée pour mémoriser l'opt-in du candidat (toggle UI)
SESSION_KEY_OPT_IN = 'matching_actif'


# ──────────────────────────────────────────────────────────────────────────────
# Gating opt-in / premium
# ──────────────────────────────────────────────────────────────────────────────

def est_opt_in(request) -> bool:
    """Vrai si le candidat a explicitement activé le matching pour sa session."""
    return bool(request.session.get(SESSION_KEY_OPT_IN, False))


def activer_pour_session(request) -> None:
    request.session[SESSION_KEY_OPT_IN] = True


def desactiver_pour_session(request) -> None:
    request.session[SESSION_KEY_OPT_IN] = False


def peut_utiliser_matching(candidat) -> bool:
    """Retourne True si le candidat a le droit d'utiliser le matching.

    Pour l'instant : tous les candidats authentifiés y ont accès. Lorsque vous
    voudrez en faire une feature Premium, modifiez UNIQUEMENT cette fonction :

        return bool(candidat) and getattr(candidat, 'premium', False)

    Le reste du code (vues, templates) reste inchangé.
    """
    return bool(candidat)


def matching_actif(request) -> bool:
    """Réponse unique « doit-on calculer/afficher le matching pour cette requête ? »

    Combine les trois conditions :
      1. Un candidat est connecté
      2. Il a le droit (peut_utiliser_matching → check premium futur)
      3. Il a opté pour l'activation dans sa session
    """
    candidat = getattr(request, 'candidat', None)
    return (
        peut_utiliser_matching(candidat) and est_opt_in(request)
    )


# ──────────────────────────────────────────────────────────────────────────────
# Extraction du profil candidat (fait UNE seule fois par requête)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ProfilCandidat:
    """Snapshot des données utiles du candidat pour le scoring.

    On normalise tout en lower-case + on collecte les compétences/langues une
    seule fois pour éviter les requêtes répétées en boucle d'offres.
    """
    candidat_id: int
    ville: str = ''
    pays: str = ''
    region: str = ''
    secteur: str = ''
    annees_experience: Optional[int] = None
    contrat_recherche_id: Optional[int] = None
    contrat_recherche_label: str = ''
    type_mobilite: str = ''
    competences_libelle: set = field(default_factory=set)   # noms normalisés (lower)
    competences_ref_ids: set = field(default_factory=set)   # IDs TypeCompetence
    langues_libelle: set = field(default_factory=set)
    langues_ref_ids: set = field(default_factory=set)


def extraire_profil(candidat) -> ProfilCandidat:
    """Construit un ProfilCandidat à partir d'une instance Candidat.

    Tolérant aux champs vides / relations manquantes (informationPersonnelle
    legacy, typeMobilite optionnel, etc.).
    """
    info = getattr(candidat, 'informationPersonnelle', None)
    ville = (info.ville or '').strip() if info else ''
    pays  = (info.pays  or '').strip() if info else ''

    # Région via le référentiel (best-effort, ne casse pas si Ville absente)
    region = ''
    if ville:
        try:
            from referentiel.models import Ville as VilleRef
            v = (
                VilleRef.objects
                .filter(nomVille__iexact=ville)
                .only('region', 'pays__nomPays')
                .select_related('pays')
                .first()
            )
            if v:
                region = (v.region or '').strip()
                if not pays and v.pays:
                    pays = v.pays.nomPays
        except Exception:
            pass

    # Années d'expérience déduites de datePremierEmploi (champ "année du
    # premier emploi", ex: 2018). On laisse None si non renseigné.
    annees_exp = None
    if candidat.datePremierEmploi:
        try:
            annees_exp = max(0, datetime.now().year - int(candidat.datePremierEmploi))
        except (TypeError, ValueError):
            annees_exp = None

    # Compétences (libellé normalisé + ID référentiel quand dispo)
    comp_libelle, comp_ref = set(), set()
    for c in candidat.competences.all():
        if c.typeCompetence:
            comp_ref.add(c.typeCompetence_id)
            comp_libelle.add(c.typeCompetence.nomCompetence.lower())
        if c.nomLibre:
            comp_libelle.add(c.nomLibre.strip().lower())

    # Langues
    lang_libelle, lang_ref = set(), set()
    for l in candidat.languesParlees.all():
        if l.langue:
            lang_ref.add(l.langue_id)
            lang_libelle.add(l.langue.nomLangue.lower())
        if l.nomLibre:
            lang_libelle.add(l.nomLibre.strip().lower())

    # Contrat recherché
    contrat_id = candidat.typeContratRecherche_id if hasattr(candidat, 'typeContratRecherche_id') else None
    contrat_label = ''
    if candidat.typeContratRecherche:
        contrat_label = (getattr(candidat.typeContratRecherche, 'nomContrat', '') or '').strip().lower()

    # Type de mobilité (texte du libellé via FK ou ancien CharField legacy)
    mobilite = ''
    if candidat.typeMobilite:
        mobilite = (getattr(candidat.typeMobilite, 'libelle', '') or
                    getattr(candidat.typeMobilite, 'nom', '') or '').strip().lower()

    return ProfilCandidat(
        candidat_id              = candidat.id,
        ville                    = ville,
        pays                     = pays,
        region                   = region,
        secteur                  = (candidat.secteurActivite or '').strip().lower(),
        annees_experience        = annees_exp,
        contrat_recherche_id     = contrat_id,
        contrat_recherche_label  = contrat_label,
        type_mobilite            = mobilite,
        competences_libelle      = comp_libelle,
        competences_ref_ids      = comp_ref,
        langues_libelle          = lang_libelle,
        langues_ref_ids          = lang_ref,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Critères de scoring (chacun renvoie un score 0-100 + une note explicative)
# ──────────────────────────────────────────────────────────────────────────────

def _critere_competences(profil: ProfilCandidat, offre) -> dict:
    """Compétences candidat ∩ compétences requises.

    On combine deux sources côté offre :
      - `typesCompetence` (M2M référentiel) → matching par ID
      - `competencesRequises` (JSON libre)  → matching par libellé normalisé
    """
    requis_ids     = set(offre.typesCompetence.values_list('id', flat=True))
    requis_libelle = {
        str(c).strip().lower()
        for c in (offre.competencesRequises or [])
        if str(c).strip()
    }
    # On ajoute aussi les libellés des refs (pour matcher contre nomLibre candidat)
    if requis_ids:
        try:
            from referentiel.models import TypeCompetence
            requis_libelle |= {
                n.lower()
                for n in TypeCompetence.objects.filter(id__in=requis_ids).values_list('nomCompetence', flat=True)
            }
        except Exception:
            pass

    total = len(requis_ids) + len(requis_libelle - {n for n in requis_libelle})  # simple |∪|
    # Calcul propre du dénominateur : union par libellé (plus stable)
    total = max(len(requis_libelle), len(requis_ids))

    if total == 0:
        # L'offre ne précise pas de compétences requises → on neutralise
        return {
            'cle': 'competences', 'label': 'Compétences', 'icone': '🧩',
            'poids': POIDS['competences'], 'score': 60,
            'status': 'partial',
            'note': "L'offre ne précise pas de compétences — score neutre.",
        }

    matches_ids     = profil.competences_ref_ids & requis_ids
    matches_libelle = profil.competences_libelle & requis_libelle
    nb_matches = max(len(matches_ids), len(matches_libelle))
    ratio = min(1.0, nb_matches / total)
    score = int(round(ratio * 100))

    if ratio >= 0.75:
        status, note = 'success', f"Vous maîtrisez {nb_matches} des {total} compétences demandées."
    elif ratio >= 0.4:
        status, note = 'partial', f"Vous maîtrisez {nb_matches} des {total} compétences demandées."
    else:
        status, note = 'missing', (
            "Compétences à compléter pour ce poste."
            if nb_matches == 0
            else f"Seulement {nb_matches} des {total} compétences demandées sont dans votre profil."
        )

    return {
        'cle': 'competences', 'label': 'Compétences', 'icone': '🧩',
        'poids': POIDS['competences'], 'score': score,
        'status': status, 'note': note,
    }


def competences_manquantes(candidat, offre, limite: int = 8) -> list:
    """Compétences demandées par `offre` absentes du profil de `candidat`.

    Purement informatif (utilisé par l'adaptation IA de CV pour suggérer au
    candidat des pistes, jamais pour modifier automatiquement son CV — voir
    `cv_adaptation.py`, garde-fou anti-invention). Réutilise `extraire_profil`,
    même logique de matching que `_critere_competences` mais conserve la
    casse d'origine des libellés pour un affichage propre.
    """
    profil = extraire_profil(candidat)

    labels = {}  # libellé normalisé (lower) -> libellé d'affichage (casse d'origine)
    for c in (offre.competencesRequises or []):
        txt = str(c).strip()
        if txt:
            labels.setdefault(txt.lower(), txt)
    requis_ids = set(offre.typesCompetence.values_list('id', flat=True))
    if requis_ids:
        try:
            from referentiel.models import TypeCompetence
            for nom in TypeCompetence.objects.filter(id__in=requis_ids).values_list('nomCompetence', flat=True):
                nom = (nom or '').strip()
                if nom:
                    labels.setdefault(nom.lower(), nom)
        except Exception:
            pass

    manquantes = sorted(set(labels) - profil.competences_libelle)
    return [labels[cle] for cle in manquantes][:limite]


def _critere_localisation(profil: ProfilCandidat, offre) -> dict:
    """Match localisation : même ville > même région > même pays > ailleurs.

    La mobilité du candidat (s'il est ouvert au national/international) bonifie
    légèrement le score quand la ville ne correspond pas.
    """
    ville_o = (offre.ville or '').strip().lower()
    pays_o  = (offre.pays  or '').strip().lower()
    ville_c = profil.ville.lower()
    pays_c  = profil.pays.lower()

    score, note, status = 0, '', 'missing'

    if ville_c and ville_o and ville_c == ville_o:
        score, status, note = 100, 'success', f"Offre dans votre ville ({offre.ville})."
    elif profil.region and ville_o:
        # Si la ville de l'offre fait partie de votre région
        try:
            from referentiel.models import Ville as VilleRef
            meme_region = VilleRef.objects.filter(
                nomVille__iexact=ville_o, region__iexact=profil.region
            ).exists()
        except Exception:
            meme_region = False
        if meme_region:
            score, status, note = 75, 'success', f"Offre dans votre région ({profil.region})."
        elif pays_c and pays_o and pays_c == pays_o:
            score, status, note = 45, 'partial', f"Offre dans votre pays ({offre.pays})."
        else:
            score, status, note = 10, 'missing', "Offre hors de votre zone géographique."
    elif pays_c and pays_o and pays_c == pays_o:
        score, status, note = 45, 'partial', f"Offre dans votre pays ({offre.pays})."
    elif not (ville_c or pays_c):
        score, status, note = 50, 'partial', "Renseignez votre ville pour affiner ce score."
    else:
        score, status, note = 10, 'missing', "Offre hors de votre zone géographique."

    # Bonus si mobilité large
    if score < 70 and any(k in profil.type_mobilite for k in ('national', 'international', 'monde')):
        score = min(100, score + 25)
        note += " (Mobilité élargie prise en compte.)"

    return {
        'cle': 'localisation', 'label': 'Localisation', 'icone': '📍',
        'poids': POIDS['localisation'], 'score': score,
        'status': status, 'note': note,
    }


def _critere_experience(profil: ProfilCandidat, offre) -> dict:
    """Compare l'expérience du candidat au minimum demandé par l'offre.

    `offre.experienceRequise` est un CharField avec des choices "0_1", "1_3",
    "3_5", "5_10", "10_PLUS" (ou approchant). On extrait l'entier de borne basse.
    """
    requis_min = None
    val = (offre.experienceRequise or '').strip().upper()
    if val:
        # Heuristique : on prend le premier nombre rencontré
        import re
        m = re.match(r'(\d+)', val)
        if m:
            requis_min = int(m.group(1))

    if requis_min is None:
        return {
            'cle': 'experience', 'label': 'Expérience', 'icone': '⏳',
            'poids': POIDS['experience'], 'score': 70,
            'status': 'partial',
            'note': "L'offre ne précise pas d'expérience requise.",
        }

    if profil.annees_experience is None:
        return {
            'cle': 'experience', 'label': 'Expérience', 'icone': '⏳',
            'poids': POIDS['experience'], 'score': 40,
            'status': 'partial',
            'note': "Renseignez votre année de premier emploi pour affiner.",
        }

    if profil.annees_experience >= requis_min:
        return {
            'cle': 'experience', 'label': 'Expérience', 'icone': '⏳',
            'poids': POIDS['experience'], 'score': 100,
            'status': 'success',
            'note': f"Vos {profil.annees_experience} ans couvrent les {requis_min} ans demandés.",
        }
    # Sous-couverture : score proportionnel
    ratio = profil.annees_experience / max(1, requis_min)
    score = int(round(min(1.0, ratio) * 80))  # cap à 80 si sous-min
    return {
        'cle': 'experience', 'label': 'Expérience', 'icone': '⏳',
        'poids': POIDS['experience'], 'score': score,
        'status': 'partial' if score >= 40 else 'missing',
        'note': f"Vos {profil.annees_experience} ans pour {requis_min} ans demandés.",
    }


def _critere_contrat(profil: ProfilCandidat, offre) -> dict:
    """Type de contrat recherché par le candidat == proposé par l'offre."""
    if not profil.contrat_recherche_id and not profil.contrat_recherche_label:
        return {
            'cle': 'contrat', 'label': 'Type de contrat', 'icone': '📄',
            'poids': POIDS['contrat'], 'score': 60,
            'status': 'partial',
            'note': "Précisez votre contrat recherché dans votre profil.",
        }

    # Match via FK référentiel si dispo, sinon via choices texte
    match = False
    if offre.contrat_id and profil.contrat_recherche_id:
        match = (offre.contrat_id == profil.contrat_recherche_id)
    elif profil.contrat_recherche_label:
        offre_label = (offre.get_typeContrat_display() or offre.typeContrat or '').lower()
        match = profil.contrat_recherche_label in offre_label or offre_label in profil.contrat_recherche_label

    if match:
        return {
            'cle': 'contrat', 'label': 'Type de contrat', 'icone': '📄',
            'poids': POIDS['contrat'], 'score': 100,
            'status': 'success',
            'note': f"Type de contrat aligné ({offre.get_typeContrat_display()}).",
        }
    return {
        'cle': 'contrat', 'label': 'Type de contrat', 'icone': '📄',
        'poids': POIDS['contrat'], 'score': 25,
        'status': 'missing',
        'note': f"L'offre propose un {offre.get_typeContrat_display()} (vous cherchez autre chose).",
    }


def _critere_secteur(profil: ProfilCandidat, offre) -> dict:
    """Match textuel entre le secteur du candidat et celui de l'entreprise."""
    secteur_o = ''
    if offre.entreprise and offre.entreprise.secteurActiviteRef:
        secteur_o = (offre.entreprise.secteurActiviteRef.nomSecteur or '').strip().lower()

    if not profil.secteur or not secteur_o:
        return {
            'cle': 'secteur', 'label': "Secteur d'activité", 'icone': '🏭',
            'poids': POIDS['secteur'], 'score': 60,
            'status': 'partial',
            'note': "Secteur non précisé — score neutre.",
        }

    if profil.secteur == secteur_o:
        return {
            'cle': 'secteur', 'label': "Secteur d'activité", 'icone': '🏭',
            'poids': POIDS['secteur'], 'score': 100,
            'status': 'success',
            'note': f"Secteur identique ({offre.entreprise.secteurActiviteRef.nomSecteur}).",
        }
    # Match partiel : mot commun
    mots_c = set(profil.secteur.split())
    mots_o = set(secteur_o.split())
    if mots_c & mots_o:
        return {
            'cle': 'secteur', 'label': "Secteur d'activité", 'icone': '🏭',
            'poids': POIDS['secteur'], 'score': 55,
            'status': 'partial',
            'note': f"Secteur proche ({offre.entreprise.secteurActiviteRef.nomSecteur}).",
        }
    return {
        'cle': 'secteur', 'label': "Secteur d'activité", 'icone': '🏭',
        'poids': POIDS['secteur'], 'score': 15,
        'status': 'missing',
        'note': f"Secteur différent ({offre.entreprise.secteurActiviteRef.nomSecteur}).",
    }


def _critere_langues(profil: ProfilCandidat, offre) -> dict:
    """Intersection des langues du candidat avec celles demandées par l'offre."""
    requis_ids = set(offre.langues.values_list('id', flat=True))
    requis_libelle = set()
    if requis_ids:
        try:
            from referentiel.models import Langue
            requis_libelle = {
                n.lower()
                for n in Langue.objects.filter(id__in=requis_ids).values_list('nomLangue', flat=True)
            }
        except Exception:
            pass

    total = max(len(requis_ids), len(requis_libelle))
    if total == 0:
        return {
            'cle': 'langues', 'label': 'Langues', 'icone': '🌐',
            'poids': POIDS['langues'], 'score': 70,
            'status': 'partial',
            'note': "Aucune langue requise.",
        }

    nb_matches = max(
        len(profil.langues_ref_ids & requis_ids),
        len(profil.langues_libelle & requis_libelle),
    )
    ratio = min(1.0, nb_matches / total)
    score = int(round(ratio * 100))
    status = 'success' if ratio >= 0.75 else ('partial' if ratio >= 0.5 else 'missing')
    return {
        'cle': 'langues', 'label': 'Langues', 'icone': '🌐',
        'poids': POIDS['langues'], 'score': score,
        'status': status,
        'note': f"{nb_matches} langue(s) sur {total} couverte(s).",
    }


def _critere_affinite(profil: ProfilCandidat, offre, embedding_candidat=None) -> dict:
    """Similarité sémantique entre le texte du candidat et celui de l'offre.

    Utilise un modèle pré-entraîné (sentence-transformers, MiniLM-L12 multilingue).
    `embedding_candidat` est pré-calculé par le Matcher pour éviter de ré-encoder
    le candidat à chaque appel. Si la dépendance n'est pas installée, on renvoie
    un score neutre (60) pour ne pas pénaliser l'utilisateur.
    """
    from . import matching_semantic as ms

    if not ms.est_disponible():
        return {
            'cle': 'affinite', 'label': 'Affinité sémantique', 'icone': '🧠',
            'poids': POIDS['affinite'], 'score': 60,
            'status': 'partial',
            'note': "Module sémantique non installé — score neutre.",
        }

    if embedding_candidat is None:
        return {
            'cle': 'affinite', 'label': 'Affinité sémantique', 'icone': '🧠',
            'poids': POIDS['affinite'], 'score': 50,
            'status': 'partial',
            'note': "Profil insuffisant pour calculer l'affinité (complétez votre CV).",
        }

    embedding_offre = ms.embedding_offre(offre)
    if embedding_offre is None:
        return {
            'cle': 'affinite', 'label': 'Affinité sémantique', 'icone': '🧠',
            'poids': POIDS['affinite'], 'score': 50,
            'status': 'partial',
            'note': "L'offre manque de contenu textuel pour le calcul.",
        }

    # Cosinus de 2 vecteurs normalisés ∈ [-1, 1] — la plupart du temps [0, 1]
    cos = float(embedding_candidat @ embedding_offre)
    # Mappe [0, 1] → [0, 100] avec un peu de boost (les cosinus de textes
    # courts en français tournent souvent autour de 0.3-0.6).
    score = int(round(max(0.0, min(1.0, cos)) * 100))

    if score >= 70:
        status = 'success'
        note = "Votre profil correspond très bien au descriptif du poste."
    elif score >= 45:
        status = 'partial'
        note = "Affinité modérée entre votre profil et l'offre."
    else:
        status = 'missing'
        note = "Votre profil semble assez éloigné de cette offre."

    return {
        'cle': 'affinite', 'label': 'Affinité sémantique', 'icone': '🧠',
        'poids': POIDS['affinite'], 'score': score,
        'status': status, 'note': note,
    }


CRITERES = [
    _critere_competences,
    _critere_localisation,
    _critere_experience,
    _critere_contrat,
    _critere_secteur,
    _critere_langues,
]


# ──────────────────────────────────────────────────────────────────────────────
# Scoring : règles + hook ML
# ──────────────────────────────────────────────────────────────────────────────

def _score_rules(profil: ProfilCandidat, offre, embedding_candidat=None) -> dict:
    """Score à règles : somme pondérée des critères → 0-100.

    `embedding_candidat` est passé par le Matcher (pré-calculé 1× par requête)
    et utilisé par le critère d'affinité sémantique. Si None, on saute le
    critère sémantique en lui donnant un score neutre.
    """
    criteres = [fn(profil, offre) for fn in CRITERES]
    criteres.append(_critere_affinite(profil, offre, embedding_candidat))
    # score global = Σ (poids_i × score_i) / 100
    total = sum(c['score'] * c['poids'] for c in criteres) / 100
    return {
        'score':    int(round(total)),
        'methode':  'rules',
        'criteres': criteres,
    }


def _score_ml(profil: ProfilCandidat, offre, embedding_candidat=None) -> Optional[dict]:
    """Inference ML — utilise le modèle persisté par `entrainer_matching` si dispo.

    Logique :
      1. Si aucun modèle entraîné → renvoie None → fallback rules.
      2. Sinon prédit le score 0-100 + confiance basée sur la taille du dataset.
      3. Si confiance < SEUIL_CONFIANCE_ML → on retombe sur les règles (le
         modèle est jugé trop peu fiable pour passer devant les règles).

    Le détail des critères (utilisé par l'UI pour la barre de progression) est
    construit côté `matching_ml.predire()` à partir des fonctions rules — donc
    l'UI reste identique quelle que soit la méthode active.
    """
    try:
        from . import matching_ml
    except Exception:
        return None
    if not matching_ml.est_disponible():
        return None
    result = matching_ml.predire(profil, offre, embedding_candidat)
    if result is None:
        return None
    if result.get('confiance', 0) < SEUIL_CONFIANCE_ML:
        return None
    return result


# ──────────────────────────────────────────────────────────────────────────────
# API publique
# ──────────────────────────────────────────────────────────────────────────────

class Matcher:
    """Wrapper léger pour scorer plusieurs offres avec UN profil candidat.

    Extrait le profil candidat une seule fois (requêtes M2M sur compétences /
    langues) PLUS l'embedding sémantique (1× par requête HTTP), puis offre une
    méthode `scorer(offre)` rapide pour la boucle.
    """

    def __init__(self, candidat):
        self.profil = extraire_profil(candidat)
        # Pré-calcule l'embedding du candidat une seule fois (lazy : ne charge
        # le modèle que si la dépendance est installée).
        try:
            from . import matching_semantic as ms
            self._embedding_candidat = ms.embedding_candidat(candidat) if ms.est_disponible() else None
        except Exception:
            self._embedding_candidat = None

    def scorer(self, offre) -> dict:
        # ML d'abord (si confiance suffisante), fallback rules sinon
        result = _score_ml(self.profil, offre, self._embedding_candidat)
        if result is not None:
            return result
        return _score_rules(self.profil, offre, self._embedding_candidat)

    def scorer_plusieurs(self, offres: Iterable) -> list:
        """Renvoie une liste de dicts {offre, **result}."""
        out = []
        for offre in offres:
            r = self.scorer(offre)
            r['offre'] = offre
            out.append(r)
        return out


def score_matching(candidat, offre) -> dict:
    """Helper one-shot (ne pas utiliser en boucle — préférer `Matcher`)."""
    return Matcher(candidat).scorer(offre)


def calculer_toutes_offres_scorees(candidat) -> list:
    """Calcule le score de matching du candidat pour TOUTES les offres publiées.

    Contrairement à `calculer_offres_recommandees` (pool limité à 50, top 6
    pour la page d'accueil), celle-ci score l'intégralité des offres publiées
    — utilisée pour la page "Toutes les offres" quand le matching est activé.
    Isolée pour être appelable depuis une tâche Celery
    (`candidat/tasks.py::calculer_matching_offres`) : le calcul sémantique +
    ML est trop lent pour tourner dans le cycle requête/réponse HTTP.

    Renvoie une liste de tuples `(offre, score)`, triée par score décroissant.
    """
    from entreprise.models import OffreEmploi, StatutOffre

    offres = list(
        OffreEmploi.objects
        .filter(statutOffre=StatutOffre.PUBLIEE)
        .select_related(
            'entreprise', 'entreprise__secteurActiviteRef',
            'contrat', 'modeTravailRef', 'anneesExperience',
        )
        .prefetch_related('typesCompetence', 'langues')
        .order_by('-datePublication', '-dateCreation')
    )
    try:
        matcher = Matcher(candidat)
        scored = []
        for offre in offres:
            try:
                r = matcher.scorer(offre)
                scored.append((offre, r['score']))
            except Exception:
                scored.append((offre, 0))
        scored.sort(key=lambda x: -x[1])
    except Exception:
        scored = [(o, 0) for o in offres]
    return scored


def calculer_offres_recommandees(candidat, taille_pool: int = 50, top_n: int = 6) -> list:
    """Calcule les `top_n` offres les plus pertinentes pour un candidat.

    Isolé de la vue `accueil` pour être appelable depuis une tâche Celery
    (`candidat/tasks.py::calculer_recommandations_accueil`) — le calcul
    sémantique + ML est trop lent pour tourner dans le cycle requête/réponse
    HTTP à chaque expiration de cache (voir discussion perf accueil).

    Renvoie une liste de tuples `(offre, score)`, triée par score décroissant.
    """
    from entreprise.models import OffreEmploi, StatutOffre

    offres_pool = list(
        OffreEmploi.objects
        .filter(statutOffre=StatutOffre.PUBLIEE)
        .select_related('entreprise', 'contrat', 'modeTravailRef', 'anneesExperience')
        .prefetch_related('typesCompetence', 'langues')
        .order_by('-datePublication', '-dateCreation', '-pk')[:taille_pool]
    )
    try:
        matcher = Matcher(candidat)
        scored = []
        for offre in offres_pool:
            try:
                r = matcher.scorer(offre)
                scored.append((offre, r['score']))
            except Exception:
                scored.append((offre, 0))
        scored.sort(key=lambda x: -x[1])
    except Exception:
        scored = [(o, 0) for o in offres_pool]
    return scored[:top_n]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers UI
# ──────────────────────────────────────────────────────────────────────────────

def couleur_score(score: int) -> str:
    """Renvoie un code couleur HEX selon le score (utilisé dans les templates)."""
    if score >= 80:
        return '#009A44'      # vert
    if score >= 60:
        return '#F77F00'      # orange
    if score >= 40:
        return '#EAB308'      # jaune
    return '#94A3B8'          # gris


def libelle_score(score: int) -> str:
    """Étiquette courte associée au score (formulation accessible)."""
    if score >= 80:
        return 'Très adapté à votre profil'
    if score >= 60:
        return 'Adapté à votre profil'
    if score >= 40:
        return 'Moyennement adapté'
    return 'Peu adapté à votre profil'
