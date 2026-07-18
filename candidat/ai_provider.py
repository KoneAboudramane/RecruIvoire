"""Point de contact unique avec un LLM externe (Mistral AI).

Isolé dans ce seul module : changer de fournisseur LLM plus tard ne
demande de réécrire que ce fichier, rien côté appelants (`cv_adaptation.py`).

Bascule décidée le 2026-07-17 (venait de Google Gemini) : le tier gratuit
Gemini s'est avéré trop restrictif en usage réel multi-utilisateurs (quota
partagé par toute l'app, 20 req/jour sur `gemini-3.5-flash` — voir
`GEMINI_API_KEY` dans `.env`, conservée en secours manuel). Mistral AI
("La Plateforme", console.mistral.ai) a son propre tier gratuit "Experiment".

Le projet n'a aucune autre intégration LLM — tout le reste (matching,
scoring ATS) tourne sur du ML local (sklearn, sentence-transformers).
"""
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# Réécriture bornée en français (titre + résumé de CV) : la fidélité aux
# faits compte plus que la créativité, pas besoin du modèle "large".
MODELE_ADAPTATION_CV = 'mistral-small-latest'


class LLMUnavailableError(Exception):
    """Le LLM n'a pas pu produire de réponse exploitable (clé absente, panne API,
    sortie refusée/tronquée, JSON invalide)."""


def generer_json(system: str, user_content: str, schema: dict, *, max_tokens: int = 1500) -> dict:
    """Appelle Mistral avec une sortie contrainte par JSON Schema et renvoie le dict résultant.

    Lève `LLMUnavailableError` pour toute erreur (clé API absente, panne réseau/API,
    réponse refusée/tronquée, JSON invalide) — l'appelant n'a qu'un seul type
    d'erreur à gérer.
    """
    if not settings.MISTRAL_API_KEY:
        raise LLMUnavailableError("MISTRAL_API_KEY n'est pas configurée.")

    from mistralai.client import Mistral
    from mistralai.client import errors as mistral_errors
    from mistralai.client.models.jsonschema import JSONSchema
    from mistralai.client.models.responseformat import ResponseFormat

    try:
        client = Mistral(api_key=settings.MISTRAL_API_KEY)
        response = client.chat.complete(
            model=MODELE_ADAPTATION_CV,
            max_tokens=max_tokens,
            messages=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user_content},
            ],
            response_format=ResponseFormat(
                type='json_schema',
                json_schema=JSONSchema(name='cv_adaptation', schema=schema, strict=True),
            ),
        )
    except mistral_errors.SDKError as e:
        raise LLMUnavailableError(f"Erreur API Mistral : {e}") from e

    choix = response.choices or []
    if not choix or choix[0].finish_reason != 'stop':
        motif = choix[0].finish_reason if choix else 'aucune réponse'
        raise LLMUnavailableError(f"Réponse LLM incomplète (finish_reason={motif!r}).")

    contenu = choix[0].message.content if choix[0].message else None
    if not contenu:
        raise LLMUnavailableError("Réponse LLM sans contenu texte exploitable.")

    try:
        return json.loads(contenu)
    except (json.JSONDecodeError, ValueError) as e:
        raise LLMUnavailableError(f"Réponse LLM non-JSON : {e}") from e
