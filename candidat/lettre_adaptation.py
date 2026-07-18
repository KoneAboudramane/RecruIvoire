"""Orchestrateur pur : génère le corps d'une lettre de motivation adaptée à
une offre, à partir du profil COMPLET du candidat, avec garde-fous
anti-hallucination renforcés par rapport à `cv_adaptation.py`.

Différence clé avec le CV : une lettre de motivation est un texte libre
persuasif, pas des données structurées reformulées. Le risque d'invention
(motivations plaquées, faits inventés sur l'entreprise) est donc plus élevé.
Le schéma de sortie du LLM ne contient qu'UN SEUL champ (`corps`) — tout le
reste (destinataire, entreprise, objet, dates) est construit en Python à
partir de données réelles (l'offre, l'entreprise), jamais par le LLM.

Ne touche jamais à la base de données ni au cache — fonction pure, facile à
tester unitairement. Le candidat et l'offre sont chargés par l'appelant
(`candidat/tasks.py::adapter_lettre_ia`), le dict renvoyé est passé tel quel
comme `lettre_initial` à l'éditeur existant (même format que
`lettreMo.py::creer_lettre`) — le candidat le relit et le sauvegarde via le
flux `sauvegarder_lettre` déjà en place, inchangé.
"""
from __future__ import annotations

import logging

from . import experience_ranking
from .ai_provider import LLMUnavailableError, generer_json
from .cv_adaptation import _competences_offre, _texte_secteur_offre
from .cv_initial import build_cv_initial

logger = logging.getLogger(__name__)

CORPS_MAX_LEN   = 2200  # ~350-400 mots, format lettre standard
NB_EXPERIENCES  = 2     # une lettre argumente sur 1-2 expériences cles, pas un CV exhaustif

_SCHEMA = {
    'type': 'object',
    'properties': {
        'corps': {'type': 'string'},
    },
    'required': ['corps'],
    'additionalProperties': False,
}

_SYSTEM_PROMPT = """Tu es un assistant de rédaction de lettres de motivation pour la plateforme RecrutePro. Tu rédiges UNIQUEMENT le corps d'une lettre de motivation, en t'appuyant strictement sur les faits fournis — jamais sur des faits inventés.

Règles strictes (anti-invention, PLUS strictes que pour un CV car ceci est un texte libre et persuasif) :
- Tu ne dois JAMAIS inventer, ajouter ou sous-entendre une compétence, un poste, un employeur, une date, un diplôme, une réalisation ou un chiffre qui n'est pas explicitement présent dans le contenu source fourni.
- Tu ne dois PAS affirmer que le candidat possède une compétence de l'offre si elle n'apparaît pas dans son profil source.
- Tu ne dois PAS inventer de motivation personnelle envers l'entreprise que le candidat n'a pas exprimée (pas de "je suis passionné par votre entreprise depuis toujours", pas de connaissance prétendue de la culture d'entreprise) — reste sur des motivations générales et raisonnables, ancrées dans le secteur/les missions décrites par l'offre.
- Tu ne dois PAS inventer de chiffres/métriques (%, montants, effectifs, durées précises) absents du texte source.
- Appuie-toi UNIQUEMENT sur les expériences et compétences fournies pour justifier l'adéquation au poste — ne cite que ce qui est explicitement donné.
- Le texte doit rester en français, registre formel (vouvoiement), sans salutation d'ouverture ni formule de politesse finale (elles sont ajoutées séparément par l'éditeur) — uniquement le corps argumentatif, en 2 à 4 paragraphes.
- Longueur raisonnable : entre 150 et 350 mots.
- Si le profil source est très pauvre en contenu utilisable, reste sobre et général plutôt que d'inventer des détails pour combler."""


def _construire_user_content(candidat_nom: str, offre, experiences_retenues: list) -> str:
    import json as _json

    experiences_txt = [
        {
            'entreprise': exp.get('entreprise') or '',
            'postes':     [p.get('titre') or '' for p in (exp.get('postes') or [])],
            'periode':    f"{exp.get('debut') or ''} - {exp.get('fin') or ('present' if exp.get('enCours') else '')}",
        }
        for exp in experiences_retenues
    ]

    payload = {
        'offre': {
            'titre':               offre.titre or '',
            'entreprise':          offre.entreprise.raisonSocial if offre.entreprise else '',
            'secteur':              _texte_secteur_offre(offre),
            'missions':             offre.missions or '',
            'profil_recherche':     offre.profilRecherche or '',
            'competences_requises': _competences_offre(offre),
        },
        'candidat': {
            'titre_professionnel': candidat_nom,
            'experiences':         experiences_txt,
        },
    }
    return _json.dumps(payload, ensure_ascii=False)


def _valider(reponse: dict) -> str:
    if not isinstance(reponse, dict) or not reponse.get('corps'):
        raise LLMUnavailableError("Réponse LLM incomplète (corps manquant).")
    return str(reponse['corps'])[:CORPS_MAX_LEN]


def adapter_lettre_pour_offre(candidat, offre) -> dict:
    """Construit un dict `lettre_initial` (même format que consommé par
    `creer_lettre.html`) avec un corps de lettre rédigé pour `offre`.

    Seul `corps` est généré par le LLM. Tout le reste (destinataire,
    entreprise, objet, date) est construit à partir de données réelles :
      - `entreprise`/`villeEntreprise`/`lieu` : nom et ville réels de
        l'entreprise qui recrute (`offre.entreprise`), jamais inventés.
      - `objet` : formule standard construite en Python à partir du titre
        réel de l'offre — pas besoin d'IA pour une phrase purement factuelle.
      - `nomDestinataire`/`posteDestinataire`/`titreDestinataire` : laissés
        VIDES — on ne connaît pas le nom du recruteur qui traitera la
        candidature, mieux vaut laisser le candidat les compléter que
        d'inventer un contact fictif.
    """
    cv_dict = build_cv_initial(candidat)

    experiences_retenues = experience_ranking.classer_experiences_par_pertinence(
        cv_dict.get('experiences') or [], offre, top_n=NB_EXPERIENCES,
    )
    candidat_nom = candidat.titreProfessionnel or ''
    user_content = _construire_user_content(candidat_nom, offre, experiences_retenues)

    reponse = generer_json(_SYSTEM_PROMPT, user_content, _SCHEMA)
    corps   = _valider(reponse)

    entreprise_nom  = offre.entreprise.raisonSocial if offre.entreprise else ''
    ville_entreprise = offre.ville or (offre.entreprise.ville if offre.entreprise else '') or ''

    return {
        'lettreId':          None,   # force la creation d'une nouvelle lettre a la sauvegarde
        'nomLettre':         f"Lettre — {offre.titre}"[:200],
        'titreDestinataire': '',
        'nomDestinataire':   '',
        'posteDestinataire': '',
        'posteDestId':       None,
        'entreprise':        entreprise_nom,
        'entrepriseId':      None,
        'paysNom':           '',
        'paysId':            None,
        'villeEntreprise':   ville_entreprise,
        'villeEntrepriseId': None,
        'lieu':              ville_entreprise,
        'dateLettre':        '',
        'objet':             f"Candidature au poste de {offre.titre}"[:255],
        'corps':             corps,
        'formuleConge':      "Veuillez agréer, [titre] [nom], l'expression de mes salutations distinguées.",
    }
