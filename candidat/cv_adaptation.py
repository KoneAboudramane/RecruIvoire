"""Orchestrateur pur : assemble un CV taillé pour une offre à partir de
TOUT le profil du candidat (pas seulement d'un CV existant), avec titre et
résumé réécrits par un LLM, garde-fous anti-hallucination.

Un candidat peut avoir plusieurs CV au contenu différent, chacun n'étant
qu'un sous-ensemble de son profil complet (`Candidat.rubriques`). Plutôt que
de demander au candidat de choisir un CV et rester limité à son contenu, on
repart directement du profil complet (`cv_initial.build_cv_initial`, la même
source que la création d'un nouveau CV) et on sélectionne localement (sans
IA) les expériences/projets les plus pertinents pour l'offre — aucun CV
existant n'est requis en entrée.

Ne touche jamais à la base de données ni au cache — fonction pure, facile à
tester unitairement. Le candidat et l'offre sont chargés par l'appelant
(`candidat/tasks.py::adapter_cv_ia`), et le dict renvoyé est ensuite passé
tel quel comme `cv_initial` à l'éditeur existant (même format que
`candidat/cv_initial.py::build_cv_initial`) — le candidat le relit et le
sauvegarde via le flux `sauvegarder_cv` déjà en place, inchangé.
"""
from __future__ import annotations

import logging

from . import experience_ranking
from .ai_provider import LLMUnavailableError, generer_json
from .cv_initial import build_cv_initial
from .matching import competences_manquantes

logger = logging.getLogger(__name__)

TITRE_MAX_LEN    = 200
PROFIL_MAX_LEN   = 800
NB_EXPERIENCES   = 4  # nombre d'expériences retenues dans le CV assemblé
NB_PROJETS       = 3  # nombre de projets retenus dans le CV assemblé

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
- Les expériences et projets fournis sont ceux retenus dans le CV — appuie-toi dessus pour rendre le profil concret et crédible, mais tu ne les modifies pas et tu ne les renvoies pas (seuls titre/profil sont dans ta sortie).
- Reformule le contenu VRAI existant ; ne crée pas de contenu nouveau.
- Reste concis : titre ≤ 120 caractères, profil ≤ 800 caractères.
- Réponds en français, dans le même registre que le CV source.
- Si le profil source est vide, propose une accroche neutre basée uniquement sur le titre professionnel et les expériences/projets fournis — sans inventer de contenu."""


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


def _construire_user_content(cv_dict: dict, offre, experiences_retenues: list, projets_retenus: list) -> str:
    import json as _json

    experiences_txt = [
        {
            'entreprise': exp.get('entreprise') or '',
            'postes':     [p.get('titre') or '' for p in (exp.get('postes') or [])],
            'periode':    f"{exp.get('debut') or ''} - {exp.get('fin') or ('present' if exp.get('enCours') else '')}",
        }
        for exp in experiences_retenues
    ]
    projets_txt = [
        {'nom': p.get('nom') or '', 'description': p.get('desc') or ''}
        for p in projets_retenus
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
            'titre_actuel':   cv_dict.get('titre') or '',
            'profil_actuel':  cv_dict.get('profil') or '',
            # Ces expériences/projets sont ceux retenus dans le CV assemblé
            # (pas un extrait — le candidat les verra tels quels dans
            # l'éditeur). Fournis pour que le profil réécrit s'appuie dessus.
            'experiences':    experiences_txt,
            'projets':        projets_txt,
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


def adapter_cv_pour_offre(candidat, offre) -> dict:
    """Construit un dict `cv_initial` assemblé à partir du profil COMPLET du
    `candidat` (`build_cv_initial`), avec titre/profil réécrits pour coller
    au vocabulaire de `offre`. Aucun CV existant requis en entrée.

    Sélection locale (sans IA, jamais d'invention) :
      - expériences  : les `NB_EXPERIENCES` plus pertinentes pour l'offre
      - projets      : les `NB_PROJETS` plus pertinents pour l'offre
      - compétences  : toutes conservées, réordonnées par pertinence
      - formations, langues, centres d'intérêt, bénévolat : conservés tels quels

    Les compétences demandées par l'offre mais absentes du profil sont
    proposées comme SUGGESTIONS dans l'éditeur (même mécanisme que les
    suggestions profil↔CV déjà existant, `cv.py::_compute_suggestions`) —
    le candidat les ajoute lui-même, un clic à la fois, s'il les possède
    réellement. Jamais ajoutées automatiquement au CV.
    """
    cv_dict = build_cv_initial(candidat)

    experiences_retenues = experience_ranking.classer_experiences_par_pertinence(
        cv_dict.get('experiences') or [], offre, top_n=NB_EXPERIENCES,
    )
    projets_retenus = experience_ranking.classer_projets_par_pertinence(
        cv_dict.get('projets') or [], offre, top_n=NB_PROJETS,
    )
    user_content = _construire_user_content(cv_dict, offre, experiences_retenues, projets_retenus)

    reponse  = generer_json(_SYSTEM_PROMPT, user_content, _SCHEMA)
    resultat = _valider_et_appliquer(reponse, cv_dict)

    resultat['experiences'] = experiences_retenues
    resultat['projets']     = projets_retenus
    resultat['competences'] = experience_ranking.reordonner_competences(
        resultat.get('competences') or [], offre,
    )
    resultat['nomCv'] = f"CV — {offre.titre}"[:200]

    resultat.setdefault('suggestions', {})
    resultat['suggestions']['competences'] = [
        # `source: 'offre'` distingue ces suggestions (compétence demandée par
        # l'offre, absente du profil) des suggestions profil↔CV classiques
        # (`cv.py::_compute_suggestions`, un élément du profil absent DE CE
        # CV) — l'éditeur les affiche différemment (voir `_suggestions_panel.html`)
        # pour ne pas laisser croire que ces compétences sont déjà acquises.
        {'id': f'offre-{i}', 'nom': nom, 'niveau': None, 'visiblePortfolio': True, 'source': 'offre'}
        for i, nom in enumerate(competences_manquantes(candidat, offre))
    ]

    return resultat
