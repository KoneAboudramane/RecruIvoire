"""Adaptation IA de la lettre de motivation à une offre — déclenchement,
statut (polling), ouverture de l'éditeur préremplli.

Miroir de `candidat/views/cv_ai.py` — mêmes principes (thread arrière-plan,
polling, quota quotidien, garde-fous). La vérification des compétences
manquantes AVANT génération (`verifier_avant_adaptation_cv_ia`) est
générique (candidat + offre, rien de spécifique au CV) et donc réutilisée
telle quelle, sans duplication.
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
from ..models import ModeleLettre

logger = logging.getLogger(__name__)

QUOTA_QUOTIDIEN_LETTRE_IA = 5  # ajustable — contrôle de coût API, distinct du quota CV


def _cache_keys(candidat_id, offre_id):
    base = f'{candidat_id}_{offre_id}'
    return {
        'lock':   f'lettre_ia_computing_{base}',
        'status': f'lettre_ia_status_{base}',
        'result': f'lettre_ia_result_{base}',
    }


def _quota_key(candidat_id):
    return f'lettre_ia_quota_{candidat_id}_{date.today().isoformat()}'


@candidat_required
@require_POST
@ratelimit(key='user', rate='10/m', method='POST', block=False)
def lancer_adaptation_lettre_ia(request, offre_id):
    """Déclenche l'adaptation IA de la lettre de motivation (thread arrière-plan)."""
    if getattr(request, 'limited', False):
        return JsonResponse(
            {'ok': False, 'message': 'Trop de tentatives, réessayez dans une minute.'},
            status=429,
        )

    from entreprise.models import OffreEmploi
    from recrutement.background import lancer_en_arriere_plan
    from ..tasks import adapter_lettre_ia

    if not OffreEmploi.objects.filter(pk=offre_id).exists():
        return JsonResponse({'ok': False, 'message': 'Offre introuvable.'}, status=404)

    quota_key = _quota_key(request.candidat.pk)
    utilises  = cache.get(quota_key, 0)
    if utilises >= QUOTA_QUOTIDIEN_LETTRE_IA:
        return JsonResponse({
            'ok': False,
            'message': f"Limite quotidienne d'adaptations IA atteinte ({QUOTA_QUOTIDIEN_LETTRE_IA}/jour).",
        }, status=429)

    keys = _cache_keys(request.candidat.pk, offre_id)
    if not cache.add(keys['lock'], True, 120):
        # Un calcul est déjà en cours pour ce couple (candidat, offre) — idempotent.
        return JsonResponse({'ok': True, 'already_running': True})

    cache.set(quota_key, utilises + 1, 86400)
    cache.set(keys['status'], {'status': 'computing', 'message': ''}, 600)

    lancer_en_arriere_plan(adapter_lettre_ia, request.candidat.pk, offre_id)

    return JsonResponse({'ok': True})


@candidat_required
def statut_adaptation_lettre_ia(request, offre_id):
    """Poll : renvoie le statut de l'adaptation en cours pour cette offre."""
    keys = _cache_keys(request.candidat.pk, offre_id)

    statut = cache.get(keys['status'])
    if not statut:
        return JsonResponse({'status': 'computing'})
    if statut.get('status') == 'ready':
        return JsonResponse({
            'status': 'ready',
            'redirect_url': reverse('candidat:creer_lettre_depuis_adaptation', args=[offre_id]),
        })
    return JsonResponse(statut)


@candidat_required
def creer_lettre_depuis_adaptation(request, offre_id):
    """Ouvre l'éditeur de lettre préremplli avec le corps adapté par l'IA.

    Rend exactement le même template/contexte que `lettreMo.py::creer_lettre`,
    avec `lettre_initial` sourcé depuis le cache (au lieu de None) —
    `lettreId: None` dans ce dict force la création d'une nouvelle lettre à
    la sauvegarde (`sauvegarder_lettre` reste totalement inchangé). Le modèle
    (design) reprend celui de la lettre la plus récente du candidat s'il en
    a une, sinon le premier modèle actif.
    """
    import json as _json

    keys = _cache_keys(request.candidat.pk, offre_id)
    lettre_initial = cache.get(keys['result'])
    if lettre_initial is None:
        messages.error(request, "La lettre adaptée n'est plus disponible, relancez l'adaptation.")
        return redirect('candidat:offre_detail', offre_id=offre_id)

    lettre_recente = (
        request.candidat.lettres.filter(archive=False, modele__actif=True)
        .select_related('modele').order_by('-dateModification').first()
    )
    modele = lettre_recente.modele if lettre_recente else ModeleLettre.objects.filter(actif=True).order_by('ordre', 'nom').first()
    if not modele:
        messages.error(request, 'Aucun modèle de lettre disponible.')
        return redirect('candidat:offre_detail', offre_id=offre_id)

    modeles = ModeleLettre.objects.filter(actif=True).order_by('ordre', 'nom')
    modeles_json = _json.dumps([
        {
            'id':      m.id,
            'nom':     m.nom,
            'slug':    m.slug,
            'couleur': m.couleur,
            'premium': m.premium,
            'famille': m.famille,
            'apercu':  m.apercu.url if m.apercu else None,
        }
        for m in modeles
    ], ensure_ascii=False)

    c  = request.candidat
    ip = getattr(c, 'informationPersonnelle', None)

    def _f(direct, legacy=''):
        return direct or legacy or ''

    candidat_info = {
        'prenom':     _f(c.prenom,    ip.prenom     if ip else ''),
        'nom':        _f(c.nom,       ip.nom        if ip else ''),
        'email':      _f(c.email,     ip.email      if ip else ''),
        'telephone':  _f(c.telephone, ip.telephone  if ip else ''),
        'adresse':    _f(c.adresse,   ip.adresse    if ip else ''),
        'codePostal': _f('',          ip.codePostal if ip else ''),
        'ville':      _f('',          ip.ville      if ip else ''),
    }

    return render(request, 'candidat/lettreMo/creer_lettre.html', {
        'modele':               modele,
        'modeles':               modeles,
        'modeles_json':          modeles_json,
        'candidat_info':         candidat_info,
        'lettre_initial':        lettre_initial,
        # Affiche "Postuler avec cette lettre" apres sauvegarde (creer_lettre.html).
        'offre_id_adaptation':   offre_id,
    })
