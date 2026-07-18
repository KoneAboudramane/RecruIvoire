"""Tâches de calcul lancées en arrière-plan pour le candidat.

Le worker web (Daphne) ne doit jamais bloquer une réponse HTTP sur un calcul
sémantique + ML (chargement du modèle, encodage, prédiction) — ces fonctions
sont appelées via `recrutement.background.lancer_en_arriere_plan()` (thread
démon) plutôt qu'en synchrone dans la vue.
"""

import logging

logger = logging.getLogger(__name__)


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


def adapter_cv_ia(candidat_id, offre_id):
    """Génère, à partir du profil COMPLET du candidat, un CV adapté au
    vocabulaire de l'offre `offre_id` via un LLM (`cv_adaptation.adapter_cv_pour_offre`).

    Écrit le résultat sous plusieurs clés de cache (voir `candidat/views/cv_ai.py`
    pour le déclenchement et le polling) :
      - `cv_ia_result_{candidat_id}_{offre_id}` : dict `cv_initial` prêt à
        préremplir l'éditeur, TTL 10 min.
      - `cv_ia_status_{candidat_id}_{offre_id}` : `{'status': 'ready'|'error', 'message': ...}`.

    L'écart de compétences (`matching.competences_manquantes`) est vérifié
    en amont, de façon synchrone, AVANT le déclenchement de cette tâche —
    voir `views/cv_ai.py::verifier_avant_adaptation_cv_ia` — pas recalculé ici.

    Contrairement aux autres tâches de ce module, celle-ci gère elle-même
    ses erreurs (au lieu de laisser `background.py` les avaler en silence) :
    la vue de polling doit toujours pouvoir lire un statut final, jamais
    rester bloquée sur "computing" après un échec.
    """
    from django.core.cache import cache
    from .models import Candidat
    from entreprise.models import OffreEmploi
    from .cv_adaptation import adapter_cv_pour_offre

    status_key = f'cv_ia_status_{candidat_id}_{offre_id}'
    result_key = f'cv_ia_result_{candidat_id}_{offre_id}'
    lock_key   = f'cv_ia_computing_{candidat_id}_{offre_id}'

    try:
        candidat = Candidat.objects.get(pk=candidat_id)
        offre = (
            OffreEmploi.objects
            .select_related('entreprise__secteurActiviteRef')
            .prefetch_related('typesCompetence')
            .get(pk=offre_id)
        )

        adapted = adapter_cv_pour_offre(candidat, offre)

        cache.set(result_key, adapted, 600)
        cache.set(status_key, {'status': 'ready', 'message': ''}, 600)
    except (Candidat.DoesNotExist, OffreEmploi.DoesNotExist):
        cache.set(status_key, {
            'status': 'error',
            'message': "Cette offre n'est plus disponible.",
        }, 600)
    except Exception:
        logger.exception(
            "Adaptation IA du CV a échoué (candidat=%s offre=%s)",
            candidat_id, offre_id,
        )
        cache.set(status_key, {
            'status': 'error',
            'message': "L'adaptation a échoué. Réessayez dans un instant.",
        }, 600)
    finally:
        cache.delete(lock_key)


def adapter_lettre_ia(candidat_id, offre_id):
    """Génère, à partir du profil COMPLET du candidat, le corps d'une lettre
    de motivation adaptée à l'offre `offre_id` via un LLM
    (`lettre_adaptation.adapter_lettre_pour_offre`).

    Même pattern de clés de cache que `adapter_cv_ia`, préfixe `lettre_ia_`
    (namespace distinct — CV et lettre peuvent être générés indépendamment
    pour la même offre) :
      - `lettre_ia_result_{candidat_id}_{offre_id}` : dict `lettre_initial`.
      - `lettre_ia_status_{candidat_id}_{offre_id}` : `{'status': 'ready'|'error', 'message': ...}`.
    """
    from django.core.cache import cache
    from .models import Candidat
    from entreprise.models import OffreEmploi
    from .lettre_adaptation import adapter_lettre_pour_offre

    status_key = f'lettre_ia_status_{candidat_id}_{offre_id}'
    result_key = f'lettre_ia_result_{candidat_id}_{offre_id}'
    lock_key   = f'lettre_ia_computing_{candidat_id}_{offre_id}'

    try:
        candidat = Candidat.objects.get(pk=candidat_id)
        offre = (
            OffreEmploi.objects
            .select_related('entreprise__secteurActiviteRef')
            .prefetch_related('typesCompetence')
            .get(pk=offre_id)
        )

        adapted = adapter_lettre_pour_offre(candidat, offre)

        cache.set(result_key, adapted, 600)
        cache.set(status_key, {'status': 'ready', 'message': ''}, 600)
    except (Candidat.DoesNotExist, OffreEmploi.DoesNotExist):
        cache.set(status_key, {
            'status': 'error',
            'message': "Cette offre n'est plus disponible.",
        }, 600)
    except Exception:
        logger.exception(
            "Adaptation IA de la lettre a échoué (candidat=%s offre=%s)",
            candidat_id, offre_id,
        )
        cache.set(status_key, {
            'status': 'error',
            'message': "L'adaptation a échoué. Réessayez dans un instant.",
        }, 600)
    finally:
        cache.delete(lock_key)
