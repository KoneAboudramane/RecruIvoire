"""In-app notifications."""
import json
import logging

from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from ..decorators import candidat_required
from ..models import NotificationCandidat

logger = logging.getLogger(__name__)


@require_POST
def api_matching_toggle(request):
    """Active / désactive le matching pour la session courante."""
    from .. import matching as matching_mod
    candidat = getattr(request, 'candidat', None)
    if not matching_mod.peut_utiliser_matching(candidat):
        return JsonResponse(
            {'ok': False, 'message': 'Connectez-vous pour utiliser le matching.'},
            status=403,
        )
    if matching_mod.est_opt_in(request):
        matching_mod.desactiver_pour_session(request)
    else:
        matching_mod.activer_pour_session(request)
    return JsonResponse({'ok': True, 'actif': matching_mod.est_opt_in(request)})


@candidat_required
def notifications_page(request):
    """Page dédiée listant toutes les notifications du candidat connecté."""
    notifs = (
        NotificationCandidat.objects
        .filter(candidat=request.candidat)
        .select_related('offre', 'offre__entreprise')
        .order_by('-dateCreation')
    )
    nb_non_lues = notifs.filter(lue=False).count()
    return render(request, 'candidat/notifications.html', {
        'notifications':    notifs,
        'nb_non_lues':      nb_non_lues,
        'alertes_actives':  request.candidat.alertesActives,
    })


@candidat_required
def api_notifications_lister(request):
    """JSON : liste des notifications (limite 20 par défaut, paginable)."""
    try:
        limit = max(1, min(50, int(request.GET.get('limit', 20))))
    except (ValueError, TypeError):
        limit = 20
    qs = (
        NotificationCandidat.objects
        .filter(candidat=request.candidat)
        .select_related('offre', 'offre__entreprise')
        .order_by('-dateCreation')[:limit]
    )

    items = []
    for n in qs:
        items.append({
            'id':          n.id,
            'type':        n.type,
            'titre':       n.titre,
            'message':     n.message,
            'lien':        n.lien,
            'score':       n.score,
            'lue':         n.lue,
            'date':        n.dateCreation.isoformat(),
            'offre_titre': n.offre.titre if n.offre else '',
            'entreprise':  n.offre.entreprise.raisonSocial if (n.offre and n.offre.entreprise) else '',
        })
    nb_non_lues = (
        NotificationCandidat.objects.filter(candidat=request.candidat, lue=False).count()
        if request.candidat.notificationsInApp else 0
    )
    return JsonResponse({
        'ok':          True,
        'items':       items,
        'nb_non_lues': nb_non_lues,
    })


@candidat_required
@require_POST
def api_notifications_lire(request, pk):
    """Marque une notification comme lue."""
    try:
        notif = NotificationCandidat.objects.get(pk=pk, candidat=request.candidat)
    except NotificationCandidat.DoesNotExist:
        return JsonResponse({'ok': False, 'message': 'Notification introuvable.'}, status=404)
    notif.marquer_lue()
    return JsonResponse({'ok': True})


@candidat_required
@require_POST
def api_notifications_toutes_lues(request):
    """Marque toutes les notifications du candidat comme lues."""
    NotificationCandidat.objects.filter(
        candidat=request.candidat, lue=False,
    ).update(lue=True, dateLecture=timezone.now())
    return JsonResponse({'ok': True})


@candidat_required
@require_POST
def api_notifications_supprimer(request, pk):
    """Supprime une notification du candidat."""
    deleted, _ = NotificationCandidat.objects.filter(
        pk=pk, candidat=request.candidat,
    ).delete()
    return JsonResponse({'ok': bool(deleted)})


@candidat_required
@require_POST
def api_notifications_supprimer_toutes(request):
    """Supprime TOUTES les notifications du candidat connecté."""
    deleted, _ = NotificationCandidat.objects.filter(candidat=request.candidat).delete()
    return JsonResponse({'ok': True, 'supprimees': deleted})


@candidat_required
@require_POST
def api_notifications_pref_email(request):
    """Active/désactive l'opt-in email pour les notifications."""
    try:
        data = json.loads(request.body or '{}')
    except (json.JSONDecodeError, ValueError):
        data = {}
    actif = bool(data.get('actif', False))
    request.candidat.notificationsOffresEmail = actif
    request.candidat.save(update_fields=['notificationsOffresEmail'])
    return JsonResponse({'ok': True, 'actif': actif})


@candidat_required
@require_POST
def api_notifications_pref_inapp(request):
    """Active/désactive les notifications in-app (badge + création)."""
    try:
        data = json.loads(request.body or '{}')
    except (json.JSONDecodeError, ValueError):
        data = {}
    actif = bool(data.get('actif', True))
    request.candidat.notificationsInApp = actif
    request.candidat.save(update_fields=['notificationsInApp'])
    return JsonResponse({'ok': True, 'actif': actif})


@candidat_required
@require_POST
def api_alertes_master_toggle(request):
    """Active/désactive le système d'alertes emploi personnalisées (master switch)."""
    try:
        data = json.loads(request.body or '{}')
    except (json.JSONDecodeError, ValueError):
        data = {}
    actif = bool(data.get('actif', True))
    request.candidat.alertesActives = actif
    request.candidat.save(update_fields=['alertesActives'])
    return JsonResponse({'ok': True, 'actif': actif})


@candidat_required
@require_POST
def api_recommandations_toggle(request):
    """Active/désactive les recommandations automatiques (ML matching)."""
    try:
        data = json.loads(request.body or '{}')
    except (json.JSONDecodeError, ValueError):
        data = {}
    actif = bool(data.get('actif', True))
    request.candidat.recommandationsActives = actif
    request.candidat.save(update_fields=['recommandationsActives'])
    return JsonResponse({'ok': True, 'actif': actif})


@candidat_required
@require_GET
def api_alertes_liste(request):
    """Retourne la liste des alertes emploi du candidat."""
    from ..models import AlerteEmploi
    alertes = request.candidat.alertesEmploi.select_related('secteur').all()
    data = [
        {
            'id':          a.id,
            'motsCles':    a.motsCles,
            'typeContrat': a.typeContrat,
            'secteur':     a.secteur.nomSecteur if a.secteur else '',
            'secteurId':   a.secteur_id,
            'ville':       a.ville,
            'salaireMin':  a.salaireMin,
            'active':      a.active,
            'creeLe':      a.creeLe.strftime('%d/%m/%Y'),
        }
        for a in alertes
    ]
    return JsonResponse({'ok': True, 'alertes': data})


CONTRATS_VALIDES = {'CDI', 'CDD', 'STAGE', 'ALTERNANCE', 'FREELANCE'}


@candidat_required
@require_POST
def api_alerte_creer(request):
    """Crée une nouvelle alerte emploi personnalisée (critères multi-valeurs)."""
    from ..models import AlerteEmploi
    try:
        data = json.loads(request.body or '{}')
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'erreur': 'JSON invalide'}, status=400)

    if request.candidat.alertesEmploi.filter(active=True).count() >= 10:
        return JsonResponse(
            {'ok': False, 'erreur': 'Maximum 10 alertes actives autorisées.'}, status=400
        )

    # Postes : liste de noms → stockés en CSV dans motsCles
    postes = [p.strip()[:100] for p in (data.get('postes') or []) if isinstance(p, str) and p.strip()]
    mots_cles = ', '.join(postes)[:500]

    # Contrats : liste de codes validés
    contrats_raw = data.get('contrats') or []
    type_contrat = [c for c in contrats_raw if isinstance(c, str) and c.upper() in CONTRATS_VALIDES]

    # Villes : liste de noms
    villes_raw = data.get('villes') or []
    ville_list = [v.strip()[:100] for v in villes_raw if isinstance(v, str) and v.strip()][:10]

    # Salaire min
    salaire_min = data.get('salaireMin') or None
    if salaire_min is not None:
        try:
            salaire_min = int(salaire_min)
        except (ValueError, TypeError):
            salaire_min = None

    if not any([mots_cles, type_contrat, ville_list, salaire_min]):
        return JsonResponse({'ok': False, 'erreur': 'Au moins un critère est requis.'}, status=400)

    alerte = AlerteEmploi.objects.create(
        candidat=request.candidat,
        motsCles=mots_cles,
        typeContrat=type_contrat,
        ville=ville_list,
        salaireMin=salaire_min,
    )
    # Activer le système d'alertes si ce n'est pas déjà le cas
    if not request.candidat.alertesActives:
        request.candidat.alertesActives = True
        request.candidat.save(update_fields=['alertesActives'])

    return JsonResponse({
        'ok': True,
        'alerte': {
            'id':          alerte.id,
            'motsCles':    alerte.motsCles,
            'typeContrat': alerte.typeContrat,
            'secteur':     '',
            'secteurId':   None,
            'ville':       alerte.ville,
            'salaireMin':  alerte.salaireMin,
            'active':      alerte.active,
            'creeLe':      alerte.creeLe.strftime('%d/%m/%Y'),
        },
    })


@candidat_required
@require_POST
def api_alerte_supprimer(request, alerte_id):
    """Supprime une alerte emploi."""
    from ..models import AlerteEmploi
    deleted, _ = AlerteEmploi.objects.filter(
        candidat=request.candidat, id=alerte_id
    ).delete()
    return JsonResponse({'ok': True, 'supprimee': deleted > 0})


@candidat_required
@require_POST
def api_alerte_toggle(request, alerte_id):
    """Active ou désactive une alerte emploi."""
    from ..models import AlerteEmploi
    try:
        data = json.loads(request.body or '{}')
    except (json.JSONDecodeError, ValueError):
        data = {}
    actif   = bool(data.get('actif', True))
    updated = AlerteEmploi.objects.filter(
        candidat=request.candidat, id=alerte_id
    ).update(active=actif)
    return JsonResponse({'ok': True, 'actif': actif, 'updated': updated})
