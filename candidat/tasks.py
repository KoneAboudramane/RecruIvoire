"""Tâches Celery pour le candidat.

Le worker web (Daphne) ne doit jamais bloquer une réponse HTTP sur un calcul
sémantique + ML (chargement du modèle, encodage, prédiction) — ce module
délègue ce calcul à un worker Celery séparé.
"""
from celery import shared_task


@shared_task
def calculer_recommandations_accueil(candidat_id):
    """Recalcule les offres recommandées d'un candidat pour la page d'accueil.

    Écrit le résultat sous deux clés de cache :
      - `accueil_reco_{id}`       : résultat "frais", TTL court (30 min) —
        c'est celle que la vue `accueil` lit en priorité.
      - `accueil_reco_stale_{id}` : dernier résultat connu, TTL long (7 j) —
        sert de repli affiché pendant qu'un nouveau calcul est en cours,
        pour ne jamais retomber sur du générique si on a déjà une
        personnalisation valable.
    """
    from django.core.cache import cache
    from .models import Candidat
    from .matching import calculer_offres_recommandees

    try:
        candidat = Candidat.objects.get(pk=candidat_id)
    except Candidat.DoesNotExist:
        return

    offres_reco = calculer_offres_recommandees(candidat)

    cache.set(f'accueil_reco_{candidat.pk}', offres_reco, 1800)
    cache.set(f'accueil_reco_stale_{candidat.pk}', offres_reco, 60 * 60 * 24 * 7)
    cache.delete(f'accueil_reco_computing_{candidat.pk}')


@shared_task
def calculer_matching_offres(candidat_id):
    """Recalcule le score de matching d'un candidat pour TOUTES les offres publiées.

    Alimente la page "Toutes les offres" (bouton "Matching intelligent"), sur
    le même principe que `calculer_recommandations_accueil` ci-dessus :

      - `matching_offres_{id}`       : résultat "frais", TTL court (30 min) —
        lu en priorité par la vue `offres`.
      - `matching_offres_stale_{id}` : dernier résultat connu, TTL long (7 j) —
        repli affiché pendant qu'un nouveau calcul est en cours.
    """
    from django.core.cache import cache
    from .models import Candidat
    from .matching import calculer_toutes_offres_scorees

    try:
        candidat = Candidat.objects.get(pk=candidat_id)
    except Candidat.DoesNotExist:
        return

    offres_scorees = calculer_toutes_offres_scorees(candidat)

    cache.set(f'matching_offres_{candidat.pk}', offres_scorees, 1800)
    cache.set(f'matching_offres_stale_{candidat.pk}', offres_scorees, 60 * 60 * 24 * 7)
    cache.delete(f'matching_offres_computing_{candidat.pk}')
