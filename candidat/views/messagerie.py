"""Direct messaging & invitations."""
import json
import logging

from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from .. import app_messages as messages
from ..decorators import candidat_required
from ..models import NotificationCandidat

logger = logging.getLogger(__name__)


@candidat_required
def api_messages_non_lus_candidat(request):
    """Retourne le nombre de messages recruteur non lus pour le candidat connecté."""
    from entreprise.models import MessageDirect
    nb = MessageDirect.objects.filter(
        conversation__candidat=request.candidat,
        expediteur=MessageDirect.EXPEDITEUR_RECRUTEUR,
        lu=False,
    ).count()
    return JsonResponse({'nb': nb})


@candidat_required
def conversations_liste(request):
    from entreprise.models import ConversationDirecte
    from django.db.models import Count, Q
    convs = (
        ConversationDirecte.objects
        .filter(candidat=request.candidat, supprimee_candidat=False)
        .select_related('recruteur', 'recruteur__entreprise')
        .annotate(nb_non_lus=Count('messages', filter=Q(messages__expediteur='recruteur', messages__lu=False)))
        .order_by('-date_dernier_message')
    )
    from django.db.models import Subquery, OuterRef
    from entreprise.models import MessageDirect as MsgDirect
    last_msg_sq = MsgDirect.objects.filter(
        conversation=OuterRef('pk')
    ).order_by('-date_envoi').values('contenu')[:1]
    convs = convs.annotate(dernier_message=Subquery(last_msg_sq))
    data = []
    for c in convs:
        logo_url = None
        if c.recruteur.entreprise and getattr(c.recruteur.entreprise, 'logoEntreprise', None) and c.recruteur.entreprise.logoEntreprise:
            try:
                logo_url = c.recruteur.entreprise.logoEntreprise.url
            except Exception:
                pass
        data.append({
            'id': c.id,
            'recruteur_prenom': c.recruteur.prenom,
            'recruteur_nom': c.recruteur.nom,
            'entreprise': c.recruteur.entreprise.raisonSocial if c.recruteur.entreprise else '',
            'initiale': (c.recruteur.entreprise.raisonSocial[:1].upper() if c.recruteur.entreprise else '?'),
            'logo': logo_url,
            'nb_non_lus': c.nb_non_lus,
            'date': c.date_dernier_message.strftime('%H:%M') if c.date_dernier_message else '',
            'dernier_message': (c.dernier_message or '')[:60],
            'archivee': c.archivee_candidat,
            'silencieux': c.silencieux_candidat,
            'entreprise_id': c.recruteur.entreprise.id if c.recruteur.entreprise else None,
        })
    return JsonResponse({'conversations': data})


@candidat_required
def conversation_detail(request, conv_id):
    from entreprise.models import ConversationDirecte
    conv = get_object_or_404(ConversationDirecte, pk=conv_id, candidat=request.candidat)
    conv.messages.filter(expediteur='recruteur', lu=False).update(lu=True)
    msgs = conv.messages.all().order_by('date_envoi')
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        logo_url = None
        if conv.recruteur.entreprise and getattr(conv.recruteur.entreprise, 'logoEntreprise', None) and conv.recruteur.entreprise.logoEntreprise:
            try:
                logo_url = conv.recruteur.entreprise.logoEntreprise.url
            except Exception:
                pass
        return JsonResponse({
            'conv_id': conv.id,
            'recruteur_prenom': conv.recruteur.prenom,
            'recruteur_nom': conv.recruteur.nom,
            'entreprise': conv.recruteur.entreprise.raisonSocial if conv.recruteur.entreprise else '',
            'initiale': (conv.recruteur.entreprise.raisonSocial[:1].upper() if conv.recruteur.entreprise else '?'),
            'logo': logo_url,
            'messages': [
                {
                    'id': m.id, 'expediteur': m.expediteur,
                    'contenu': '' if m.supprime else m.contenu,
                    'heure': m.date_envoi.strftime('%H:%M'),
                    'date_envoi': m.date_envoi.isoformat(),
                    'type_msg': m.type_msg,
                    'fichier_url': request.build_absolute_uri(m.fichier.url) if m.fichier and not m.supprime else None,
                    'nom_fichier': m.nom_fichier,
                    'supprime': m.supprime,
                    'epingle': m.epingle,
                }
                for m in msgs
            ],
        })
    return redirect('candidat:accueil')


@candidat_required
@require_POST
def cand_api_conv_action(request, conv_id):
    """Archiver / mode silencieux / marquer lu / supprimer une conversation (côté candidat)."""
    import json as _json
    from entreprise.models import ConversationDirecte
    conv = get_object_or_404(ConversationDirecte, pk=conv_id, candidat=request.candidat)
    try:
        data = _json.loads(request.body)
    except (ValueError, _json.JSONDecodeError):
        return JsonResponse({'ok': False, 'message': 'Données invalides.'}, status=400)

    action = data.get('action', '')

    if action == 'archiver':
        conv.archivee_candidat = not conv.archivee_candidat
        conv.save(update_fields=['archivee_candidat'])
        return JsonResponse({'ok': True, 'archivee': conv.archivee_candidat})

    if action == 'silencieux':
        conv.silencieux_candidat = not conv.silencieux_candidat
        conv.save(update_fields=['silencieux_candidat'])
        return JsonResponse({'ok': True, 'silencieux': conv.silencieux_candidat})

    if action == 'marquer_lu':
        conv.messages.filter(expediteur='recruteur', lu=False).update(lu=True)
        return JsonResponse({'ok': True})

    if action == 'supprimer':
        conv.supprimee_candidat = True
        conv.save(update_fields=['supprimee_candidat'])
        return JsonResponse({'ok': True})

    return JsonResponse({'ok': False, 'message': 'Action inconnue.'}, status=400)


@candidat_required
@require_POST
def api_envoyer_message_candidat(request, conv_id):
    from entreprise.models import ConversationDirecte, MessageDirect
    conv = get_object_or_404(ConversationDirecte, pk=conv_id, candidat=request.candidat)

    if request.content_type and 'multipart' in request.content_type:
        contenu = (request.POST.get('contenu') or '').strip()
        fichier = request.FILES.get('fichier')
    else:
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'ok': False, 'message': 'Données invalides.'}, status=400)
        contenu = (data.get('contenu') or '').strip()
        fichier = None

    if not contenu and not fichier:
        return JsonResponse({'ok': False, 'message': 'Le message ne peut pas être vide.'})

    if fichier and fichier.size > 15 * 1024 * 1024:
        return JsonResponse({'ok': False, 'message': 'Fichier trop volumineux (max 15 Mo).'})

    type_msg = MessageDirect.TYPE_TEXTE
    nom_fichier = ''
    if fichier:
        mt = fichier.content_type or ''
        if mt.startswith('image/'):
            type_msg = MessageDirect.TYPE_IMAGE
        elif mt.startswith('audio/'):
            type_msg = MessageDirect.TYPE_AUDIO
        else:
            type_msg = MessageDirect.TYPE_FICHIER
        nom_fichier = fichier.name

    msg = MessageDirect.objects.create(
        conversation=conv, expediteur=MessageDirect.EXPEDITEUR_CANDIDAT,
        contenu=contenu, type_msg=type_msg,
        fichier=fichier if fichier else None, nom_fichier=nom_fichier,
    )
    ConversationDirecte.objects.filter(pk=conv.pk).update(date_dernier_message=msg.date_envoi)

    from entreprise.models import NotificationRecruteur
    NotificationRecruteur.objects.filter(
        recruteur=conv.recruteur,
        candidat=conv.candidat,
        type=NotificationRecruteur.Type.MESSAGE,
        lue=False,
    ).delete()
    NotificationRecruteur.objects.create(
        recruteur=conv.recruteur,
        candidat=conv.candidat,
        type=NotificationRecruteur.Type.MESSAGE,
        titre=f'Nouveau message de {conv.candidat.prenom} {conv.candidat.nom}',
        message=contenu[:200],
        lien=reverse('entreprise:recruteur_conversations') + f'?conv={conv.id}',
    )

    return JsonResponse({
        'ok': True,
        'msg': {
            'id': msg.id, 'expediteur': msg.expediteur,
            'contenu': msg.contenu, 'heure': msg.date_envoi.strftime('%H:%M'),
            'date_envoi': msg.date_envoi.isoformat(),
            'type_msg': msg.type_msg,
            'fichier_url': request.build_absolute_uri(msg.fichier.url) if msg.fichier else None,
            'nom_fichier': msg.nom_fichier,
            'supprime': False,
            'epingle': False,
        },
    })


@candidat_required
@require_POST
def cand_api_msg_action(request, msg_id):
    """Supprimer ou épingler un message (côté candidat)."""
    from django.utils import timezone as tz
    from entreprise.models import ConversationDirecte, MessageDirect
    msg = get_object_or_404(MessageDirect, pk=msg_id, conversation__candidat=request.candidat)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'message': 'Données invalides.'}, status=400)

    action = data.get('action', '')

    if action == 'supprimer':
        if msg.expediteur != MessageDirect.EXPEDITEUR_CANDIDAT:
            return JsonResponse({'ok': False, 'message': 'Non autorisé.'}, status=403)
        delta = tz.now() - msg.date_envoi
        if delta.total_seconds() > 86400:
            return JsonResponse({'ok': False, 'message': 'Message trop ancien pour être supprimé.'}, status=403)
        msg.supprime = True
        msg.contenu = ''
        msg.save(update_fields=['supprime', 'contenu'])
        return JsonResponse({'ok': True})

    if action == 'epingler':
        msg.epingle = not msg.epingle
        msg.save(update_fields=['epingle'])
        return JsonResponse({'ok': True, 'epingle': msg.epingle})

    return JsonResponse({'ok': False, 'message': 'Action inconnue.'}, status=400)


# ─── Offres favorites ────────────────────────────────────────────────────────

@candidat_required
def mes_favoris(request):
    from ..models import OffreFavori
    favoris = (
        OffreFavori.objects
        .filter(candidat=request.candidat)
        .select_related('offre', 'offre__entreprise', 'offre__entreprise__secteurActiviteRef')
        .order_by('-date_ajout')
    )
    ids_favoris = set(favoris.values_list('offre_id', flat=True))
    return render(request, 'candidat/favoris.html', {
        'favoris': favoris,
        'ids_favoris': ids_favoris,
    })


@candidat_required
@require_POST
def api_toggle_favori(request, offre_id):
    from entreprise.models import OffreEmploi
    from ..models import OffreFavori
    offre = get_object_or_404(OffreEmploi, pk=offre_id)
    fav, created = OffreFavori.objects.get_or_create(
        candidat=request.candidat, offre=offre,
    )
    if not created:
        fav.delete()
    return JsonResponse({'ok': True, 'favori': created})


# ─── Invitations à postuler ──────────────────────────────────────────────────

@candidat_required
def invitations(request):
    from entreprise.models import InvitationPostuler
    filtre = request.GET.get('filtre', 'toutes')

    qs = (
        InvitationPostuler.objects
        .filter(candidat=request.candidat)
        .select_related('offre', 'offre__entreprise', 'offre__contrat',
                        'offre__modeTravailRef', 'recruteur')
        .order_by('-date_envoi')
    )

    nb_en_attente = qs.filter(statut=InvitationPostuler.STATUT_EN_ATTENTE).count()
    nb_acceptees  = qs.filter(statut=InvitationPostuler.STATUT_ACCEPTEE).count()
    nb_ignorees   = qs.filter(statut=InvitationPostuler.STATUT_IGNOREE).count()

    if filtre == 'en_attente':
        invs = qs.filter(statut=InvitationPostuler.STATUT_EN_ATTENTE)
    elif filtre == 'acceptees':
        invs = qs.filter(statut=InvitationPostuler.STATUT_ACCEPTEE)
    elif filtre == 'ignorees':
        invs = qs.filter(statut=InvitationPostuler.STATUT_IGNOREE)
    else:
        invs = qs

    return render(request, 'candidat/invitations.html', {
        'invitations':   invs,
        'filtre':        filtre,
        'nb_en_attente': nb_en_attente,
        'nb_acceptees':  nb_acceptees,
        'nb_ignorees':   nb_ignorees,
        'total':         nb_en_attente + nb_acceptees + nb_ignorees,
    })


@candidat_required
@require_POST
def invitation_repondre(request, inv_id, action):
    from entreprise.models import InvitationPostuler
    inv = get_object_or_404(
        InvitationPostuler,
        pk=inv_id,
        candidat=request.candidat,
        statut=InvitationPostuler.STATUT_EN_ATTENTE,
    )
    if action == 'accepter':
        inv.statut = InvitationPostuler.STATUT_ACCEPTEE
        inv.save()
        return redirect('candidat:postuler', offre_id=inv.offre_id)
    elif action == 'ignorer':
        inv.statut = InvitationPostuler.STATUT_IGNOREE
        inv.save()
    return redirect(reverse('candidat:profil') + '?onglet=invitations')
