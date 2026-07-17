"""Orchestrateur pur : adapte le titre + résumé d'un CV au vocabulaire d'une
offre via un LLM, avec garde-fous anti-hallucination.

Ne touche jamais à la base de données ni au cache — fonction pure, facile à
tester unitairement. Le CV et l'offre sont chargés par l'appelant
(`candidat/tasks.py::adapter_cv_ia`), et le dict renvoyé est ensuite passé
tel quel comme `cv_initial` à l'éditeur existant (même format que
`candidat/cv.py::_cv_to_dict`) — le candidat le relit et le sauvegarde via
le flux `sauvegarder_cv` déjà en place, inchangé.
"""
from __future__ import annotations

import logging

from . import experience_ranking
from .ai_provider import LLMUnavailableError, generer_json
from .cv import _cv_to_dict

logger = logging.getLogger(__name__)

TITRE_MAX_LEN  = 200
PROFIL_MAX_LEN = 800
NB_EXPERIENCES_CONTEXTE = 3

_SCHEMA = {
    'type': 'object',
    'properties': {
        'titre':  {'type': 'string'},
        'profil': {'type': 'string'},
    },
    'required': ['titre', 'profil'],
    'additionalProperties': False,
}

_SYSTEM_PROMPT = """Tu es un assistant de rédaction de CV pour la plateforme RecrutePro. Tu reformules UNIQUEMENT le titre professionnel et l'accroche/profil d'un candidat pour qu'ils utilisent le vocabulaire et les priorités de l'offre d'emploi fournie — sans jamais changer le sens des faits.

Règles strictes (anti-invention) :
- Tu ne dois JAMAIS inventer, ajouter ou sous-entendre une compétence, un poste, un employeur, une date, un diplôme ou une réalisation qui n'est pas explicitement présent dans le contenu source fourni.
- Tu ne dois PAS affirmer que le candidat possède une compétence de l'offre si elle n'apparaît pas dans son profil source.
- Tu ne dois PAS inventer de chiffres/métriques (%, montants, effectifs) absents du texte source.
- Les expériences listées en contexte te sont données uniquement pour t'aider à rendre le profil plus concret et crédible — tu peux t'en inspirer, mais tu ne les modifies pas et tu ne les renvoies pas.
- Reformule le contenu VRAI existant ; ne crée pas de contenu nouveau.
- Reste concis : titre ≤ 120 caractères, profil ≤ 800 caractères.
- Réponds en français, dans le même registre que le CV source.
- Si le profil source est vide, propose une accroche neutre basée uniquement sur le titre professionnel et les expériences fournies en contexte — sans inventer de contenu."""


def _texte_secteur_offre(offre) -> str:
    try:
        if offre.entreprise and offre.entreprise.secteurActiviteRef:
            return offre.entreprise.secteurActiviteRef.nomSecteur or ''
    except Exception:
        pass
    return ''


def _competences_offre(offre) -> list:
    noms = [str(c).strip() for c in (offre.competencesRequises or []) if str(c).strip()]
    try:
        noms += [tc.nomCompetence for tc in offre.typesCompetence.all() if tc.nomCompetence]
    except Exception:
        pass
    return noms


def _construire_user_content(cv_dict: dict, offre, experiences_contexte: list) -> str:
    import json as _json

    contexte_experiences = [
        {
            'entreprise': exp.get('entreprise') or '',
            'postes':     [p.get('titre') or '' for p in (exp.get('postes') or [])],
            'periode':    f"{exp.get('debut') or ''} - {exp.get('fin') or ('present' if exp.get('enCours') else '')}",
        }
        for exp in experiences_contexte
    ]

    payload = {
        'offre': {
            'titre':                offre.titre or '',
            'secteur':               _texte_secteur_offre(offre),
            'missions':              offre.missions or '',
            'profil_recherche':      offre.profilRecherche or '',
            'competences_requises':  _competences_offre(offre),
        },
        'cv_source': {
            'titre_actuel':               cv_dict.get('titre') or '',
            'profil_actuel':              cv_dict.get('profil') or '',
            'experiences_contexte':       contexte_experiences,
        },
    }
    return _json.dumps(payload, ensure_ascii=False)


def _valider_et_appliquer(reponse: dict, cv_dict: dict) -> dict:
    """Applique la réponse LLM validée sur une COPIE du dict CV — ne touche
    jamais à autre chose que `titre`/`profil`."""
    if not isinstance(reponse, dict) or not reponse.get('titre') or not reponse.get('profil'):
        raise LLMUnavailableError("Réponse LLM incomplète (titre/profil manquant).")

    resultat = dict(cv_dict)
    resultat['titre']  = str(reponse['titre'])[:TITRE_MAX_LEN]
    resultat['profil'] = str(reponse['profil'])[:PROFIL_MAX_LEN]
    return resultat


def adapter_cv_pour_offre(cv, offre) -> dict:
    """Construit un dict `cv_initial` (même format que `_cv_to_dict`) avec le
    titre et le profil réécrits pour coller au vocabulaire de `offre`.

    Le reste du CV (expériences, formations, langues...) est recopié tel
    quel depuis le CV source ; les compétences sont réordonnées localement
    (sans IA) par pertinence. `nomCv` est modifié pour indiquer clairement
    qu'il s'agit d'une copie adaptée, jamais le CV source lui-même.
    """
    cv_dict = _cv_to_dict(cv)

    experiences_contexte = experience_ranking.classer_experiences_par_pertinence(
        cv_dict.get('experiences') or [], offre, top_n=NB_EXPERIENCES_CONTEXTE,
    )
    user_content = _construire_user_content(cv_dict, offre, experiences_contexte)

    reponse  = generer_json(_SYSTEM_PROMPT, user_content, _SCHEMA)
    resultat = _valider_et_appliquer(reponse, cv_dict)

    resultat['competences'] = experience_ranking.reordonner_competences(
        resultat.get('competences') or [], offre,
    )

    nom_source = (cv.nomCv or cv.titre or 'CV').strip()
    resultat['nomCv'] = f"{nom_source} — adapté {offre.titre}"[:200]

    return resultat
