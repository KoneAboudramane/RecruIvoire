"""Adaptation IA du CV à une offre — déclenchement, statut (polling),
ouverture de l'éditeur préremplli.

Le contenu vient du profil COMPLET du candidat (pas d'un CV existant choisi
— voir `cv_adaptation.py`), donc aucune sélection de CV n'est nécessaire côté
UI : un clic suffit.

Suit le pattern async déjà en place pour les recommandations d'accueil
(`candidat/tasks.py` + `recrutement/background.py`) : la vue de déclenchement
ne bloque jamais sur l'appel LLM, elle lance un thread et répond
immédiatement ; le client sonde `statut_adaptation_cv_ia` jusqu'à obtenir
un statut final.
"""
import logging
from datetime import date

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from .. import app_messages as messages
from ..decorators import candidat_required
from ..models import ModeleCV

logger = logging.getLogger(__name__)

QUOTA_QUOTIDIEN_CV_IA = 5  # ajustable — contrôle de coût API


def _cache_keys(candidat_id, offre_id):
    base = f'{candidat_id}_{offre_id}'
    return {
        'lock':   f'cv_ia_computing_{base}',
        'status': f'cv_ia_status_{base}',
        'result': f'cv_ia_result_{base}',
    }


def _quota_key(candidat_id):
    return f'cv_ia_quota_{candidat_id}_{date.today().isoformat()}'


@candidat_required
def verifier_avant_adaptation_cv_ia(request, offre_id):
    """Vérification synchrone (aucun appel LLM, donc rapide et gratuite) :
    compétences demandées par l'offre absentes du profil du candidat.

    Appelée par le client AVANT de déclencher l'adaptation IA (coûteuse en
    quota), pour que le candidat en soit informé et confirme explicitement
    s'il souhaite continuer malgré l'écart — voir `matching.competences_manquantes`.
    """
    from entreprise.models import OffreEmploi
    from ..matching import competences_manquantes

    offre = (
        OffreEmploi.objects
        .filter(pk=offre_id)
        .select_related('entreprise__secteurActiviteRef')
        .prefetch_related('typesCompetence')
        .first()
    )
    if not offre:
        return JsonResponse({'ok': False, 'message': 'Offre introuvable.'}, status=404)

    gaps = competences_manquantes(request.candidat, offre)
    return JsonResponse({'ok': True, 'competences_manquantes': gaps})


@candidat_required
@require_POST
@ratelimit(key='user', rate='10/m', method='POST', block=False)
def lancer_adaptation_cv_ia(request, offre_id):
    """Déclenche l'adaptation IA d'un CV à une offre (thread arrière-plan)."""
    if getattr(request, 'limited', False):
        return JsonResponse(
            {'ok': False, 'message': 'Trop de tentatives, réessayez dans une minute.'},
            status=429,
        )

    from entreprise.models import OffreEmploi
    from recrutement.background import lancer_en_arriere_plan
    from ..tasks import adapter_cv_ia

    if not OffreEmploi.objects.filter(pk=offre_id).exists():
        return JsonResponse({'ok': False, 'message': 'Offre introuvable.'}, status=404)

    quota_key = _quota_key(request.candidat.pk)
    utilises  = cache.get(quota_key, 0)
    if utilises >= QUOTA_QUOTIDIEN_CV_IA:
        return JsonResponse({
            'ok': False,
            'message': f"Limite quotidienne d'adaptations IA atteinte ({QUOTA_QUOTIDIEN_CV_IA}/jour).",
        }, status=429)

    keys = _cache_keys(request.candidat.pk, offre_id)
    if not cache.add(keys['lock'], True, 120):
        # Un calcul est déjà en cours pour ce couple (candidat, offre) — idempotent.
        return JsonResponse({'ok': True, 'already_running': True})

    cache.set(quota_key, utilises + 1, 86400)
    cache.set(keys['status'], {'status': 'computing', 'message': ''}, 600)

    lancer_en_arriere_plan(adapter_cv_ia, request.candidat.pk, offre_id)

    return JsonResponse({'ok': True})


@candidat_required
def statut_adaptation_cv_ia(request, offre_id):
    """Poll : renvoie le statut de l'adaptation en cours pour cette offre."""
    keys = _cache_keys(request.candidat.pk, offre_id)

    statut = cache.get(keys['status'])
    if not statut:
        return JsonResponse({'status': 'computing'})
    if statut.get('status') == 'ready':
        return JsonResponse({
            'status': 'ready',
            'redirect_url': reverse('candidat:creer_cv_depuis_adaptation', args=[offre_id]),
        })
    return JsonResponse(statut)


@candidat_required
def creer_cv_depuis_adaptation(request, offre_id):
    """Ouvre l'éditeur CV préremplli avec le contenu adapté par l'IA.

    Rend exactement le même template/contexte que `cv.py::creer_cv`, avec
    `cv_initial` sourcé depuis le cache (au lieu de `build_cv_initial`) et
    `cv_id: None` pour forcer la création d'un nouveau CV à la sauvegarde
    (`sauvegarder_cv` reste totalement inchangé). Le modèle (design) reprend
    celui du CV le plus récent du candidat s'il en a un, sinon le premier
    modèle actif — le contenu n'en dépend pas.
    """
    from ..niveau_resolver import niveaux_for_editor

    keys = _cache_keys(request.candidat.pk, offre_id)
    cv_initial = cache.get(keys['result'])
    if cv_initial is None:
        messages.error(request, "Le CV adapté n'est plus disponible, relancez l'adaptation.")
        return redirect('candidat:offre_detail', offre_id=offre_id)

    cv_recent = (
        request.candidat.cvs.filter(archive=False, modele__actif=True)
        .select_related('modele').order_by('-dateModification').first()
    )
    modele = cv_recent.modele if cv_recent else ModeleCV.objects.filter(actif=True).order_by('ordre', 'nom').first()
    if not modele:
        messages.error(request, 'Aucun modèle de CV disponible.')
        return redirect('candidat:offre_detail', offre_id=offre_id)

    modeles = ModeleCV.objects.filter(actif=True).order_by('ordre', 'nom')
    return render(request, f"candidat/cv/modeles/{modele.fichier}.html", {
        'modele':               modele,
        'modeles':              modeles,
        'cv_initial':           cv_initial,
        'candidat_id':          request.candidat.id,
        'cv_id':                None,
        'niveaux_ref':          niveaux_for_editor(),
        # Affiche "Postuler avec ce CV" apres sauvegarde (candidat/templates/candidat/cv/_form_panel.html).
        'offre_id_adaptation':  offre_id,
    })
