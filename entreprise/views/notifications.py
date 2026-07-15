"""Vues notifications — app entreprise."""

import logging
from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..decorators import entreprise_required, recruteur_ou_admin_required
from ..models import NotificationRecruteur, OffreEmploi
from candidat.models import Candidature, Entretien

logger = logging.getLogger(__name__)


# ─── Notifications recruteur (cloche navbar) ─────────────────────────────────

def _filtre_destinataire(qs, request):
    """Restreint un QuerySet de NotificationRecruteur au destinataire courant.

    * Si connecté en tant que Recruteur -> notifs personnelles.
    * Sinon (compte admin Entreprise) -> notifs adressées à l'Entreprise elle-même.
    """
    recruteur = getattr(request, 'recruteur', None)
    if recruteur:
        return qs.filter(recruteur=recruteur)
    return qs.filter(entreprise=request.entreprise, recruteur__isnull=True)


@entreprise_required
def api_stats_tableau_bord(request):
    """JSON -- données analytiques du tableau de bord (polling côté client).

    Remplace l'ancien flux SSE : pas de process persistant possible sur un
    hébergement mutualisé (Passenger/WSGI, pas d'ASGI). Le client interroge
    cette route à intervalle régulier (voir tableau_bord.html).
    """
    entreprise = request.entreprise
    today = timezone.localdate()
    date_debut_30j = today - timedelta(days=29)

    cand_par_jour = (
        Candidature.objects
        .filter(offre__entreprise=entreprise, dateCandidature__date__gte=date_debut_30j)
        .annotate(jour=TruncDate('dateCandidature'))
        .values('jour')
        .annotate(nb=Count('id'))
        .order_by('jour')
    )
    cand_dict = {row['jour']: row['nb'] for row in cand_par_jour}
    jours_30  = [date_debut_30j + timedelta(days=i) for i in range(30)]

    statuts_qs = (
        Candidature.objects
        .filter(offre__entreprise=entreprise)
        .values('statut__libelle')
        .annotate(nb=Count('id'))
        .order_by('-nb')
    )

    offres_qs = (
        OffreEmploi.objects
        .filter(entreprise=entreprise)
        .values('statutOffre')
        .annotate(nb=Count('id'))
    )
    smap = {o['statutOffre']: o['nb'] for o in offres_qs}

    cand_7j = Candidature.objects.filter(
        offre__entreprise=entreprise,
        dateCandidature__date__gte=today - timedelta(days=7),
    ).count()

    nb_recues    = Candidature.objects.filter(offre__entreprise=entreprise).count()
    nb_traitees  = Candidature.objects.filter(offre__entreprise=entreprise).exclude(statut__code='POSTULEE').exclude(statut__isnull=True).count()
    nb_planifies = Candidature.objects.filter(offre__entreprise=entreprise, entretiens__isnull=False).distinct().count()
    nb_realises  = Entretien.objects.filter(candidature__offre__entreprise=entreprise, statut=Entretien.StatutEntretien.REALISE).values('candidature').distinct().count()

    top_offres = (
        Candidature.objects.filter(offre__entreprise=entreprise)
        .values('offre__titre').annotate(nb=Count('id')).order_by('-nb')[:5]
    )

    return JsonResponse({
        'cand_labels':    [j.strftime('%d/%m') for j in jours_30],
        'cand_data':      [cand_dict.get(j, 0) for j in jours_30],
        'statuts_labels': [s['statut__libelle'] or 'En attente' for s in statuts_qs],
        'statuts_data':   [s['nb'] for s in statuts_qs],
        'offres_data':    [
            smap.get('PUBLIEE',   0),
            smap.get('BROUILLON', 0),
            smap.get('EXPIREE',   0),
            smap.get('POURVUE',   0),
            smap.get('FERMEE',    0),
        ],
        'cand_7j':        cand_7j,
        'funnel_data':    [nb_recues, nb_traitees, nb_planifies, nb_realises],
        'top_labels':     [o['offre__titre'] for o in top_offres],
        'top_data':       [o['nb'] for o in top_offres],
    })


@entreprise_required
def notifications_page(request):
    """Page complète : historique de toutes les notifications (lues + non lues).

    Affiche les notifs avec filtres (Toutes / Non lues / Profils / Système) et
    actions (marquer lue / supprimer).
    """
    return render(request, 'entreprise/notifications.html')


@recruteur_ou_admin_required
def suggestions_recues(request):
    """Page dédiée aux suggestions de profils reçues et envoyées."""
    import re as _re
    from ..models import NotificationRecruteur
    recruteur  = getattr(request, 'recruteur', None)
    entreprise = recruteur.entreprise if recruteur else request.entreprise

    base_qs = NotificationRecruteur.objects.filter(
        type=NotificationRecruteur.Type.SUGGESTION_COLLEGUE,
    ).select_related('candidat', 'expediteur', 'recruteur')

    tri = request.GET.get('tri', 'recent')
    if tri == 'ancien':
        ordre_recues = ('dateCreation',)
    elif tri == 'non_lues':
        ordre_recues = ('lue', '-dateCreation')   # False=0 -> non-lues en premier
    else:
        ordre_recues = ('-dateCreation',)

    if recruteur:
        recues   = list(base_qs.filter(recruteur=recruteur).order_by(*ordre_recues))
        envoyees = list(base_qs.filter(expediteur=recruteur).order_by('-dateCreation'))
    else:
        recues   = list(base_qs.filter(recruteur__entreprise=entreprise).order_by(*ordre_recues))
        envoyees = list(base_qs.filter(expediteur__entreprise=entreprise).order_by('-dateCreation'))

    # Backfill expediteur_nom pour les anciennes notifications (avant migration 0029)
    to_save = []
    for notif in recues + envoyees:
        if not notif.expediteur_nom:
            nom = ''
            if notif.expediteur:
                nom = (f"{notif.expediteur.prenom} {notif.expediteur.nom}").strip() \
                      or notif.expediteur.nomComplet \
                      or notif.expediteur.email \
                      or ''
            if not nom:
                m = _re.match(r'^👥\s+(.+?)\s+vous suggère un profil', notif.titre or '')
                nom = m.group(1) if m else ''
            if nom:
                notif.expediteur_nom = nom
                to_save.append(notif)
    if to_save:
        NotificationRecruteur.objects.bulk_update(to_save, ['expediteur_nom'])

    non_lues = sum(1 for n in recues if not n.lue)

    return render(request, 'entreprise/suggestions.html', {
        'recues':          recues,
        'envoyees':        envoyees,
        'total_recues':    len(recues),
        'total_envoyees':  len(envoyees),
        'non_lues':        non_lues,
        'tri':             tri,
    })


@entreprise_required
@require_POST
def notification_supprimer(request, notification_id):
    """Supprime définitivement une notification (du destinataire courant)."""
    from ..models import NotificationRecruteur

    qs = _filtre_destinataire(
        NotificationRecruteur.objects.filter(pk=notification_id),
        request,
    )
    notif = qs.first()
    if not notif:
        return JsonResponse({'erreur': 'Notification introuvable.'}, status=404)
    notif.delete()
    return JsonResponse({'ok': True})


@entreprise_required
def notifications_liste(request):
    """Retourne les notifications du destinataire courant (Recruteur ou Entreprise admin).

    GET params :
      * non_lues : si '1', filtre sur lue=False
      * limit    : nombre max (défaut 20, max 50)
    """
    from ..models import NotificationRecruteur

    qs = _filtre_destinataire(
        NotificationRecruteur.objects.select_related('offre', 'candidat'),
        request,
    )

    if request.GET.get('non_lues') == '1':
        qs_items = qs.filter(lue=False)
    else:
        qs_items = qs

    try:
        limit = min(int(request.GET.get('limit', 20)), 50)
    except (TypeError, ValueError):
        limit = 20

    nb_non_lues = qs.filter(lue=False).count()

    items = []
    for n in qs_items.order_by('-dateCreation')[:limit]:
        items.append({
            'id':            n.id,
            'type':          n.type,
            'titre':         n.titre,
            'message':       n.message,
            'lien':          n.lien,
            'score':         n.score,
            'lue':           n.lue,
            'dateCreation':  n.dateCreation.isoformat(),
            'offre_id':      n.offre_id,
            'offre_titre':   n.offre.titre if n.offre else None,
            'candidat_id':   n.candidat_id,
            'candidat_nom':  f"{n.candidat.prenom} {n.candidat.nom}".strip() if n.candidat else None,
            'photo_url':     n.candidat.photoProfil.url if (n.candidat and n.candidat.photoProfil) else '',
        })

    return JsonResponse({
        'items':      items,
        'nb_non_lues': nb_non_lues,
        'total':      len(items),
    })


@entreprise_required
@require_POST
def notification_marquer_lue(request, notification_id):
    """Marque une notification comme lue (du destinataire courant uniquement)."""
    from ..models import NotificationRecruteur

    qs = _filtre_destinataire(
        NotificationRecruteur.objects.filter(pk=notification_id),
        request,
    )
    notif = qs.first()
    if not notif:
        return JsonResponse({'erreur': 'Notification introuvable.'}, status=404)
    notif.marquer_lue()
    return JsonResponse({'ok': True})


@entreprise_required
@require_POST
def notifications_tout_marquer_lues(request):
    """Marque toutes les notifications non lues comme lues (destinataire courant)."""
    from ..models import NotificationRecruteur

    qs = _filtre_destinataire(
        NotificationRecruteur.objects.filter(lue=False),
        request,
    )
    n = qs.update(lue=True, dateLecture=timezone.now())
    return JsonResponse({'ok': True, 'marquees': n})


@entreprise_required
@require_POST
def notifications_tout_supprimer(request):
    """Supprime TOUTES les notifications du destinataire courant (Recruteur ou compte Entreprise)."""
    from ..models import NotificationRecruteur

    qs = _filtre_destinataire(NotificationRecruteur.objects.all(), request)
    n, _ = qs.delete()
    return JsonResponse({'ok': True, 'supprimees': n})
