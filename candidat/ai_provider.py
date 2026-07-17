"""Point de contact unique avec un LLM externe (Google Gemini).

Isolé dans ce seul module : changer de fournisseur LLM plus tard ne
demande de réécrire que ce fichier, rien côté appelants (`cv_adaptation.py`).

Choix Gemini Flash : tier gratuit généreux (~1500 requêtes/jour sur Flash),
largement suffisant pour ce projet — le vrai plafond pratique est le quota
logiciel `QUOTA_QUOTIDIEN_CV_IA` (candidat/views/cv_ai.py), pas Gemini.

Le projet n'a aucune autre intégration LLM — tout le reste (matching,
scoring ATS) tourne sur du ML local (sklearn, sentence-transformers).
"""
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# Alias pointant vers le dernier modele Flash-Lite GA — quota gratuit propre
# (separe de gemini-flash-latest, teste le 2026-07-17 : gemini-flash-latest
# n'a que 20 requetes/jour gratuites sur ce compte, largement insuffisant ;
# Flash-Lite convient de toute facon mieux a cette tache courte et bornee).
MODELE_ADAPTATION_CV = 'gemini-flash-lite-latest'


class LLMUnavailableError(Exception):
    """Le LLM n'a pas pu produire de réponse exploitable (clé absente, panne API,
    sortie refusée/tronquée, JSON invalide)."""


def generer_json(system: str, user_content: str, schema: dict, *, max_tokens: int = 1500) -> dict:
    """Appelle Gemini avec une sortie contrainte par JSON Schema et renvoie le dict résultant.

    Lève `LLMUnavailableError` pour toute erreur (clé API absente, panne réseau/API,
    réponse refusée/tronquée, JSON invalide) — l'appelant n'a qu'un seul type
    d'erreur à gérer.
    """
    if not settings.GEMINI_API_KEY:
        raise LLMUnavailableError("GEMINI_API_KEY n'est pas configurée.")

    from google import genai
    from google.genai import errors as genai_errors
    from google.genai import types

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(
            model=MODELE_ADAPTATION_CV,
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
                response_mime_type='application/json',
                response_json_schema=schema,
                # Reformulation courte et bornee : pas besoin de "reflexion" —
                # sans ca, les tokens de thinking grignotent max_output_tokens
                # et tronquent la reponse (FinishReason.MAX_TOKENS).
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
    except genai_errors.APIError as e:
        raise LLMUnavailableError(f"Erreur API Gemini : {e}") from e

    candidats = response.candidates or []
    if not candidats or candidats[0].finish_reason != types.FinishReason.STOP:
        motif = candidats[0].finish_reason if candidats else 'aucune réponse'
        raise LLMUnavailableError(f"Réponse LLM incomplète (finish_reason={motif!r}).")

    if not response.text:
        raise LLMUnavailableError("Réponse LLM sans contenu texte exploitable.")

    try:
        return json.loads(response.text)
    except (json.JSONDecodeError, ValueError) as e:
        raise LLMUnavailableError(f"Réponse LLM non-JSON : {e}") from e
