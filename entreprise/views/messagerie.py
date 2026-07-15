"""Direct messaging, contact, invitation, and message template views."""
import logging
import json

from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_POST

from .. import app_messages as messages
from ..models import (
    Entreprise, Recruteur, OffreEmploi, OffreEmploiRecruteur,
    RoleMembre, StatutCompte,
    InvitationPostuler, ConversationDirecte, MessageDirect,
    NotificationRecruteur, InvitationEntretien,
    ModeleMessage, Message as MessageModel, PropositionProfil,
)
from ..decorators import (
    entreprise_required, recruteur_required, recruteur_ou_admin_required,
    bloque_roles, lecteur_bloque,
)
from candidat.models import Candidat, Candidature, NotificationCandidat, LogoSite
from .offres import _offres_visibles

logger = logging.getLogger(__name__)


# ── Contact candidat (invitation + messagerie) ───────────────────────────────

@recruteur_ou_admin_required
def api_suggerer_profil(request, candidat_id):
    """GET : liste des collègues de la même entreprise (sauf soi-même).
    POST : suggère le profil candidat à un collègue recruteur.
    """
    from candidat.models import Candidat
    from ..notifications_service import creer_notification_suggestion

    recruteur  = getattr(request, 'recruteur', None)
    entreprise = recruteur.entreprise if recruteur else getattr(request, 'entreprise', None)

    try:
        candidat = Candidat.objects.get(pk=candidat_id, portfolioPublic=True)
    except Candidat.DoesNotExist:
        return JsonResponse({'ok': False, 'message': 'Profil introuvable.'}, status=404)

    if request.method == 'GET':
        qs = Recruteur.objects.filter(entreprise=entreprise, estActif=True)
        if recruteur:
            qs = qs.exclude(pk=recruteur.pk)
        data = [
            {
                'id':  r.pk,
                'nom': (f"{r.prenom} {r.nom}").strip() or r.nomComplet or r.email,
                'role': r.get_roleMembre_display(),
            }
            for r in qs
        ]
        return JsonResponse({'ok': True, 'collegues': data})

    if request.method == 'POST':
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'ok': False, 'message': 'Données invalides.'}, status=400)

        destinataire_id = body.get('destinataire_id')
        note = (body.get('note') or '').strip()[:300]

        try:
            destinataire = Recruteur.objects.get(
                pk=destinataire_id, entreprise=entreprise, estActif=True,
            )
        except Recruteur.DoesNotExist:
            return JsonResponse({'ok': False, 'message': 'Collègue introuvable.'}, status=404)

        # Nom de l'expéditeur : recruteur ou compte admin entreprise
        if recruteur:
            if destinataire.pk == recruteur.pk:
                return JsonResponse({'ok': False, 'message': 'Vous ne pouvez pas vous suggérer à vous-même.'}, status=400)
            nom_exp = (f"{recruteur.prenom} {recruteur.nom}").strip() \
                      or recruteur.nomComplet \
                      or recruteur.email \
                      or "Un collègue"
        else:
            nom_exp = entreprise.raisonSocial or "L'administration"

        creer_notification_suggestion(recruteur, destinataire, candidat, note, nom_exp=nom_exp)
        nom_dest = (f"{destinataire.prenom} {destinataire.nom}").strip() or destinataire.nomComplet
        return JsonResponse({'ok': True, 'message': f'Profil suggéré à {nom_dest} ✓'})

    return JsonResponse({'ok': False}, status=405)


@recruteur_ou_admin_required
@bloque_roles('LECTEUR')
@require_POST
def api_inviter_candidat(request, candidat_id):
    """Envoie une invitation à postuler à un candidat (in-app)."""
    from candidat.models import Candidat, NotificationCandidat
    from django.db.models import Count, Q
    recruteur = getattr(request, 'recruteur', None)
    entreprise = recruteur.entreprise if recruteur else request.entreprise
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'message': 'Données invalides.'}, status=400)

    offre_id = data.get('offre_id')
    message_txt = (data.get('message') or '').strip()[:1000]

    if not offre_id:
        return JsonResponse({'ok': False, 'message': 'Veuillez sélectionner une offre.'})

    candidat = get_object_or_404(Candidat, pk=candidat_id)
    offre = get_object_or_404(OffreEmploi, pk=offre_id, entreprise=entreprise, statutOffre='PUBLIEE')

    with transaction.atomic():
        _, created = InvitationPostuler.objects.get_or_create(
            offre=offre,
            candidat=candidat,
            defaults={'recruteur': recruteur, 'message': message_txt},
        )
        if not created:
            return JsonResponse({'ok': False, 'message': 'Ce candidat a déjà été invité pour cette offre.'})

        NotificationCandidat.objects.create(
            candidat=candidat,
            type=NotificationCandidat.Type.INVITATION,
            titre=f'Invitation à postuler — {offre.titre}',
            message=f'{entreprise.raisonSocial} vous invite à postuler pour « {offre.titre} ». {message_txt}',
            lien=reverse('candidat:invitations'),
        )
    return JsonResponse({'ok': True, 'message': 'Invitation envoyée avec succès.'})


@recruteur_ou_admin_required
@bloque_roles('LECTEUR', 'MANAGER')
@require_POST
def api_demarrer_conversation(request, candidat_id):
    """Crée ou récupère une conversation ; envoie le premier message si contenu fourni."""
    from candidat.models import Candidat, NotificationCandidat
    recruteur = getattr(request, 'recruteur', None)
    entreprise = recruteur.entreprise if recruteur else request.entreprise

    if recruteur is None:
        # Admin principal : utilise le premier recruteur actif de l'entreprise comme porteur FK
        recruteur = entreprise.recruteurs.filter(estActif=True).order_by('pk').first()
        if recruteur is None:
            return JsonResponse({'ok': False, 'message': "Aucun recruteur actif dans l'entreprise."})

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'message': 'Données invalides.'}, status=400)

    contenu = (data.get('contenu') or '').strip()

    candidat = get_object_or_404(Candidat, pk=candidat_id)
    with transaction.atomic():
        conv, _ = ConversationDirecte.objects.get_or_create(
            recruteur=recruteur, candidat=candidat,
            defaults={'date_dernier_message': timezone.now()},
        )

        if contenu:
            msg = MessageDirect.objects.create(
                conversation=conv, expediteur=MessageDirect.EXPEDITEUR_RECRUTEUR, contenu=contenu,
            )
            ConversationDirecte.objects.filter(pk=conv.pk).update(date_dernier_message=msg.date_envoi)

    return JsonResponse({
        'ok': True,
        'conv_id': conv.id,
        'redirect_url': reverse('entreprise:recruteur_conversations') + f'?conv={conv.id}',
        'message': 'Conversation ouverte.',
    })


@recruteur_ou_admin_required
@bloque_roles('LECTEUR', 'MANAGER')
@require_POST
def api_retenir_entretien(request, candidat_id):
    """Retient un profil pour entretien depuis le portfolio.

    Crée un InvitationEntretien (signal d'intérêt) et notifie le candidat
    que son profil a été retenu. La planification effective se fait depuis
    l'espace dédié (/entretiens/).
    """
    from candidat.models import Candidat, NotificationCandidat

    recruteur = getattr(request, 'recruteur', None)
    entreprise = recruteur.entreprise if recruteur else request.entreprise
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'message': 'Données invalides.'}, status=400)

    offre_id = data.get('offre_id')
    if not offre_id:
        return JsonResponse({'ok': False, 'message': 'Veuillez sélectionner une offre.'})

    candidat = get_object_or_404(Candidat, pk=candidat_id)
    offre    = get_object_or_404(OffreEmploi, pk=offre_id, entreprise=entreprise, statutOffre='PUBLIEE')

    with transaction.atomic():
        _, created = InvitationEntretien.objects.get_or_create(
            offre=offre, candidat=candidat,
            defaults={'recruteur': recruteur},
        )
        if not created:
            return JsonResponse({'ok': False, 'message': 'Ce profil est déjà retenu pour cette offre.'})

        NotificationCandidat.objects.create(
            candidat=candidat,
            type=NotificationCandidat.Type.ENTRETIEN,
            titre=f'Votre profil a été retenu — {offre.titre}',
            message=(
                f'{entreprise.raisonSocial} a consulté votre profil et est intéressé(e). '
                f'Vous serez prochainement contacté(e) pour un entretien concernant l\'offre « {offre.titre} ».'
            ),
            lien=reverse('candidat:invitations'),
            offre=offre,
        )
    return JsonResponse({'ok': True, 'message': 'Profil retenu. Le candidat sera notifié.'})


@recruteur_ou_admin_required
def recruteur_messages_non_lus(request):
    """Retourne le nombre total de messages candidats non lus pour le recruteur connecté."""
    recruteur = getattr(request, 'recruteur', None)
    if recruteur:
        filtre = {'conversation__recruteur': recruteur}
    else:
        filtre = {'conversation__recruteur__entreprise': request.entreprise}
    nb = MessageDirect.objects.filter(
        **filtre,
        expediteur=MessageDirect.EXPEDITEUR_CANDIDAT,
        lu=False,
    ).count()
    return JsonResponse({'nb': nb})


@recruteur_ou_admin_required
def recruteur_conversations(request):
    from django.db.models import Count, Q, Q as _Q
    recruteur = getattr(request, 'recruteur', None)
    entreprise = recruteur.entreprise if recruteur else request.entreprise

    if recruteur:
        conv_filtre = {'recruteur': recruteur}
        offres_filtre = _Q(creePar=recruteur) | _Q(recruteurs_createurs__recruteur=recruteur)
    else:
        conv_filtre = {'recruteur__entreprise': entreprise}
        offres_filtre = _Q(entreprise=entreprise)

    convs = (
        ConversationDirecte.objects
        .filter(**conv_filtre, supprimee_recruteur=False)
        .select_related('candidat', 'candidat__informationPersonnelle')
        .annotate(nb_non_lus=Count('messages', filter=Q(messages__expediteur='candidat', messages__lu=False)))
        .order_by('-date_dernier_message')
    )
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from django.db.models import Subquery, OuterRef
        last_msg_sq = MessageDirect.objects.filter(
            conversation=OuterRef('pk')
        ).order_by('-date_envoi').values('contenu')[:1]
        convs = convs.annotate(dernier_message=Subquery(last_msg_sq))
        data = []
        for c in convs:
            photo_url = None
            if getattr(c.candidat, 'photoProfil', None) and c.candidat.photoProfil:
                try:
                    photo_url = c.candidat.photoProfil.url
                except Exception:
                    pass
            try:
                ville = c.candidat.informationPersonnelle.ville or ''
            except Exception:
                ville = ''
            data.append({
                'id': c.id,
                'prenom': c.candidat.prenom,
                'nom': c.candidat.nom,
                'nom_complet': f"{c.candidat.prenom} {c.candidat.nom}",
                'initiales': (c.candidat.prenom[:1] + c.candidat.nom[:1]).upper(),
                'photo': photo_url,
                'nb_non_lus': c.nb_non_lus,
                'date': c.date_dernier_message.strftime('%H:%M') if c.date_dernier_message else '',
                'dernier_message': (c.dernier_message or '')[:60],
                'archivee': c.archivee_recruteur,
                'silencieux': c.silencieux_recruteur,
                'candidat_id': c.candidat.id,
                'titre': c.candidat.titreProfessionnel or '',
                'ville': ville,
            })
        offres_list = list(
            OffreEmploi.objects.filter(offres_filtre, statutOffre='PUBLIEE')
            .distinct().values('id', 'titre').order_by('titre')
        )
        return JsonResponse({'conversations': data, 'offres': offres_list})

    import json as _json
    from django.db.models import Subquery, OuterRef
    last_msg_sq = MessageDirect.objects.filter(
        conversation=OuterRef('pk')
    ).order_by('-date_envoi').values('contenu')[:1]
    convs_ann = convs.annotate(dernier_message=Subquery(last_msg_sq))
    convs_json_list = []
    for c in convs_ann:
        photo_url = None
        if getattr(c.candidat, 'photoProfil', None) and c.candidat.photoProfil:
            try:
                photo_url = c.candidat.photoProfil.url
            except Exception:
                pass
        try:
            ville = c.candidat.informationPersonnelle.ville or ''
        except Exception:
            ville = ''
        convs_json_list.append({
            'id': c.id,
            'nom': f"{c.candidat.prenom} {c.candidat.nom}",
            'initiales': (c.candidat.prenom[:1] + c.candidat.nom[:1]).upper(),
            'photo': photo_url,
            'nb_non_lus': c.nb_non_lus,
            'date': c.date_dernier_message.strftime('%H:%M') if c.date_dernier_message else '',
            'dernier_message': (c.dernier_message or '')[:60],
            'url': reverse('entreprise:recruteur_conversation_detail', args=[c.id]),
            'archivee': c.archivee_recruteur,
            'silencieux': c.silencieux_recruteur,
            'candidat_id': c.candidat.id,
            'titre': c.candidat.titreProfessionnel or '',
            'ville': ville,
        })
    offres_list = list(
        OffreEmploi.objects.filter(offres_filtre, statutOffre='PUBLIEE')
        .distinct().values('id', 'titre').order_by('titre')
    )
    convs_json = _json.dumps(convs_json_list)
    offres_json = _json.dumps(offres_list)
    return render(request, 'entreprise/recruteur/conversations.html', {
        'conversations': convs,
        'convs_json': convs_json,
        'offres_json': offres_json,
    })


@recruteur_ou_admin_required
def recruteur_conversation_detail(request, conv_id):
    # Accès direct (lien notification, email…) → rediriger vers la page rich split-panel
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        url = reverse('entreprise:recruteur_conversations') + f'?conv={conv_id}'
        return redirect(url)

    recruteur = getattr(request, 'recruteur', None)
    if recruteur:
        conv = get_object_or_404(ConversationDirecte, pk=conv_id, recruteur=recruteur)
    else:
        conv = get_object_or_404(ConversationDirecte, pk=conv_id, recruteur__entreprise=request.entreprise)
    conv.messages.filter(expediteur='candidat', lu=False).update(lu=True)
    if recruteur:
        NotificationRecruteur.objects.filter(
            recruteur=recruteur,
            candidat=conv.candidat,
            type=NotificationRecruteur.Type.MESSAGE,
            lue=False,
        ).update(lue=True, dateLecture=timezone.now())
    msgs = conv.messages.all().order_by('date_envoi')
    photo_url = None
    if getattr(conv.candidat, 'photoProfil', None) and conv.candidat.photoProfil:
        try:
            photo_url = conv.candidat.photoProfil.url
        except Exception:
            pass
    return JsonResponse({
        'conv_id': conv.id,
        'prenom': conv.candidat.prenom,
        'nom': conv.candidat.nom,
        'initiales': (conv.candidat.prenom[:1] + conv.candidat.nom[:1]).upper(),
        'photo': photo_url,
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
                'lu': m.lu,
            }
            for m in msgs
        ],
    })


@recruteur_ou_admin_required
@require_POST
def recruteur_api_conv_action(request, conv_id):
    """Archiver / mode silencieux / marquer lu / supprimer une conversation (côté recruteur)."""
    recruteur = getattr(request, 'recruteur', None)
    if recruteur:
        conv = get_object_or_404(ConversationDirecte, pk=conv_id, recruteur=recruteur)
    else:
        conv = get_object_or_404(ConversationDirecte, pk=conv_id, recruteur__entreprise=request.entreprise)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'message': 'Données invalides.'}, status=400)

    action = data.get('action', '')

    if action == 'archiver':
        conv.archivee_recruteur = not conv.archivee_recruteur
        conv.save(update_fields=['archivee_recruteur'])
        return JsonResponse({'ok': True, 'archivee': conv.archivee_recruteur})

    if action == 'silencieux':
        conv.silencieux_recruteur = not conv.silencieux_recruteur
        conv.save(update_fields=['silencieux_recruteur'])
        return JsonResponse({'ok': True, 'silencieux': conv.silencieux_recruteur})

    if action == 'marquer_lu':
        conv.messages.filter(expediteur='candidat', lu=False).update(lu=True)
        return JsonResponse({'ok': True})

    if action == 'supprimer':
        conv.supprimee_recruteur = True
        conv.save(update_fields=['supprimee_recruteur'])
        return JsonResponse({'ok': True})

    return JsonResponse({'ok': False, 'message': 'Action inconnue.'}, status=400)


@recruteur_ou_admin_required
@bloque_roles('LECTEUR', 'MANAGER')
@require_POST
def recruteur_api_envoyer_message(request, conv_id):
    from candidat.models import NotificationCandidat
    recruteur = getattr(request, 'recruteur', None)
    if recruteur:
        conv = get_object_or_404(ConversationDirecte, pk=conv_id, recruteur=recruteur)
    else:
        conv = get_object_or_404(ConversationDirecte, pk=conv_id, recruteur__entreprise=request.entreprise)

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

    with transaction.atomic():
        msg = MessageDirect.objects.create(
            conversation=conv, expediteur=MessageDirect.EXPEDITEUR_RECRUTEUR,
            contenu=contenu, type_msg=type_msg,
            fichier=fichier if fichier else None, nom_fichier=nom_fichier,
        )
        ConversationDirecte.objects.filter(pk=conv.pk).update(date_dernier_message=msg.date_envoi)

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
            'lu': False,
        },
    })


@recruteur_required
@require_POST
def recruteur_api_msg_action(request, msg_id):
    """Supprimer ou épingler un message (côté recruteur)."""
    from django.utils import timezone as tz
    msg = get_object_or_404(MessageDirect, pk=msg_id, conversation__recruteur=request.recruteur)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'message': 'Données invalides.'}, status=400)

    action = data.get('action', '')

    if action == 'supprimer':
        if msg.expediteur != MessageDirect.EXPEDITEUR_RECRUTEUR:
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


# ── Proposition tracking ─────────────────────────────────────────────────────

@entreprise_required
@lecteur_bloque
@require_POST
def proposition_marquer_par_couple(request, offre_id, candidat_id, action):
    """Variante front-friendly : on identifie la PropositionProfil par
    (offre_id, candidat_id) plutôt que par son PK direct.

    Pratique pour le JS de la page détail qui ne manipule que ces deux IDs.
    """
    from ..models import PropositionProfil

    valides = {'vu', 'contacte', 'invite', 'ignore'}
    if action not in valides:
        return JsonResponse({'erreur': f"Action invalide : {action}"}, status=400)

    proposition = get_object_or_404(
        PropositionProfil,
        offre_id=offre_id, candidat_id=candidat_id,
        offre__in=_offres_visibles(request),
    )
    proposition.marquer_action(action)

    return JsonResponse({
        'ok':     True,
        'action': proposition.action,
    })


# ─── Message groupé : envoyer un même message à plusieurs candidats ──────────

@entreprise_required
@bloque_roles('LECTEUR', 'MANAGER')
def message_groupe_envoyer(request, offre_id):
    """Envoi d'un message à un groupe de candidats d'une offre.

    Cibles possibles :
      • toutes les candidatures de l'offre
      • candidatures filtrées par statut (POSTULEE, ENTRETIEN, …)
      • sélection manuelle (POST `candidatures[]`)

    Réservé aux RH/MANAGER (les rôles qui décident des candidatures) et au
    compte entreprise principal. ADMIN recruteur en lecture seule pour rester
    cohérent avec la politique « ADMIN supervise mais ne tranche pas ».
    """
    from candidat.models import Candidature
    from ..models import Message as MessageModel, ModeleMessage
    from ..messagerie import rendre_template

    offre = get_object_or_404(_offres_visibles(request), pk=offre_id)

    rec = getattr(request, 'recruteur', None)
    peut_envoyer = (rec is None) or (rec.roleMembre in (RoleMembre.RH, RoleMembre.MANAGER))
    if not peut_envoyer:
        messages.error(request, "Seuls les RH et Managers peuvent envoyer des messages aux candidats.")
        return redirect('entreprise:candidatures_offre', offre_id=offre.pk)

    candidatures = (
        Candidature.objects
        .filter(offre=offre)
        .select_related('candidat', 'statut')
        .order_by('-dateCandidature')
    )

    modeles = list(
        request.entreprise.modeles_messages
        .filter(est_actif=True)
        .select_related('statut')
        .order_by('statut__ordre', 'sujet_modele')
    )

    erreurs = {}
    if request.method == 'POST':
        cible  = (request.POST.get('cible') or 'tous').strip()
        statut_code = (request.POST.get('statut_code') or '').strip()
        ids_selectionnes = request.POST.getlist('candidatures[]')
        modele_id = (request.POST.get('modele_id') or '').strip()
        piece_jointe = request.FILES.get('piece_jointe')

        # Le modèle est OBLIGATOIRE (le recruteur ne peut pas saisir de
        # message libre — il choisit forcément un modèle créé par l'admin).
        modele = None
        if modele_id.isdigit():
            modele = next((m for m in modeles if m.id == int(modele_id)), None)
        if modele is None:
            erreurs['modele_id'] = "Vous devez choisir un modèle de message."

        # Détermination de l'audience
        if cible == 'statut' and statut_code:
            audience = candidatures.filter(statut__code=statut_code)
        elif cible == 'selection' and ids_selectionnes:
            audience = candidatures.filter(pk__in=ids_selectionnes)
        else:
            cible = 'tous'
            audience = candidatures
        audience = list(audience)

        if not audience:
            erreurs['cible'] = "Aucun candidat ne correspond à la cible choisie."

        if not erreurs:
            cree = 0
            for c in audience:
                contexte = {
                    'candidat':    c.candidat,
                    'offre':       c.offre,
                    'entreprise':  request.entreprise,
                    'recruteur':   rec,
                    'candidature': c,
                }
                MessageModel.objects.create(
                    candidat       = c.candidat,
                    recruteur      = rec,
                    candidature    = c,
                    modele_message = modele,
                    modele_utilise = modele.sujet_modele,
                    sujet          = rendre_template(modele.sujet_modele,  **contexte),
                    contenu        = rendre_template(modele.corps_message, **contexte),
                    piece_jointe   = piece_jointe,
                )
                cree += 1
            messages.success(request, f"Message envoyé à {cree} candidat(s).")
            return redirect('entreprise:candidatures_offre', offre_id=offre.pk)
    else:
        modele_id = ''
        # Si on arrive avec ?candidatures=1&candidatures=2 → cible "selection" pré-cochée
        ids_get = request.GET.getlist('candidatures')
        if ids_get:
            cible = 'selection'
            statut_code = ''
            ids_selectionnes = [i for i in ids_get if i.isdigit()]
        else:
            cible = 'tous'
            statut_code = ''
            ids_selectionnes = []

    return render(request, 'entreprise/messages/envoyer_groupe.html', {
        'offre':              offre,
        'candidatures':       candidatures,
        'modeles':            modeles,
        'erreurs':            erreurs,
        'cible':              cible,
        'statut_code':        statut_code,
        'modele_id':          modele_id,
        'ids_selectionnes':   ids_selectionnes,
    })


# ─── Modèles de message : CRUD admin entreprise ───────────────────────────────

def _est_admin_entreprise(request):
    """Vrai si l'utilisateur connecté est admin de l'entreprise.

    Compte entreprise principal (pas de recruteur) ou recruteur ADMIN.
    """
    rec = getattr(request, 'recruteur', None)
    return rec is None or rec.roleMembre == RoleMembre.ADMIN


@entreprise_required
def modeles_messages_liste(request):
    if not _est_admin_entreprise(request):
        messages.error(request, "Seul l'administrateur de l'entreprise peut gérer les modèles de message.")
        return redirect('entreprise:tableau_bord' if not request.recruteur else 'entreprise:recruteur_tableau_bord')

    tri = request.GET.get('tri', 'recent')
    if tri == 'nom':
        order = 'sujet_modele'
    elif tri == 'actif':
        order = '-est_actif'
    else:
        order = '-date_modification'

    modeles = request.entreprise.modeles_messages.select_related(
        'statut', 'typeEntretien', 'creePar'
    ).order_by(order)

    return render(request, 'entreprise/modeles_messages/liste.html', {
        'modeles': modeles,
        'total':   modeles.count(),
        'tri':     tri,
    })


@entreprise_required
def modele_message_detail(request, pk):
    """Lecture seule d'un modèle de message — visualisation sans modification."""
    from ..models import ModeleMessage

    modele = get_object_or_404(
        ModeleMessage.objects.select_related('statut', 'typeEntretien', 'creePar'),
        pk=pk,
        entreprise=request.entreprise,
    )
    return render(request, 'entreprise/modeles_messages/detail.html', {
        'modele': modele,
        'peut_modifier': _est_admin_entreprise(request),
    })


@entreprise_required
def modele_message_creer(request):
    from ..models import ModeleMessage
    from referentiel.models import Statut, TypeEntretien as TypeEntretienRef

    if not _est_admin_entreprise(request):
        messages.error(request, "Action réservée à l'administrateur de l'entreprise.")
        return redirect('entreprise:modeles_messages')

    # Statuts proposés : on suit le référentiel (statuts actifs uniquement)
    statuts          = list(Statut.objects.filter(estActif=True).order_by('ordre'))
    statuts_ids      = {str(s.id) for s in statuts}
    types_entretien  = list(TypeEntretienRef.objects.all())
    types_ids        = {str(t.id) for t in types_entretien}

    erreurs = {}
    valeurs = {
        'contexte':           (request.POST.get('contexte') or 'STATUT').strip().upper(),
        'statut_id':          request.POST.get('statut_id', '').strip(),
        'typeEntretien_id':   request.POST.get('typeEntretien_id', '').strip(),
        'sujet_modele':       request.POST.get('sujet_modele', '').strip(),
        'corps_message':      request.POST.get('corps_message', '').strip(),
        'est_actif':          request.POST.get('est_actif') == 'on' if request.method == 'POST' else True,
    }

    if request.method == 'POST':
        if valeurs['contexte'] not in ('STATUT', 'ENTRETIEN'):
            erreurs['contexte'] = "Choisissez le contexte d'utilisation du modèle."
        if not valeurs['sujet_modele']:
            erreurs['sujet_modele'] = "Le sujet est obligatoire."
        if not valeurs['corps_message']:
            erreurs['corps_message'] = "Le corps du message est obligatoire."

        # Validation exclusive selon le contexte choisi
        if valeurs['contexte'] == 'STATUT':
            if valeurs['statut_id'] not in statuts_ids:
                erreurs['statut_id'] = "Sélectionnez un statut valide."
        elif valeurs['contexte'] == 'ENTRETIEN':
            if valeurs['typeEntretien_id'] not in types_ids:
                erreurs['typeEntretien_id'] = "Sélectionnez un type d'entretien valide."

        if not erreurs and request.entreprise.modeles_messages.filter(
            sujet_modele__iexact=valeurs['sujet_modele']
        ).exists():
            erreurs['sujet_modele'] = "Un modèle avec ce sujet existe déjà."

        if not erreurs:
            if valeurs['contexte'] == 'STATUT':
                statut_id, type_id = int(valeurs['statut_id']), None
            else:
                statut_id, type_id = None, int(valeurs['typeEntretien_id'])
            ModeleMessage.objects.create(
                entreprise=request.entreprise,
                statut_id=statut_id,
                typeEntretien_id=type_id,
                sujet_modele=valeurs['sujet_modele'],
                corps_message=valeurs['corps_message'],
                variables_disponibles='',
                est_actif=valeurs['est_actif'],
                creePar=getattr(request, 'recruteur', None),
            )
            messages.success(request, f"Modèle « {valeurs['sujet_modele']} » créé.")
            return redirect('entreprise:modeles_messages')

    from ..messagerie import VARIABLES_GENERIQUES, VARIABLES_ENTRETIEN
    return render(request, 'entreprise/modeles_messages/form.html', {
        'modele':              None,
        'valeurs':             valeurs,
        'erreurs':             erreurs,
        'statuts':             statuts,
        'types_entretien':     types_entretien,
        'vars_generiques':     VARIABLES_GENERIQUES,
        'vars_entretien':      VARIABLES_ENTRETIEN,
    })


@entreprise_required
def modele_message_modifier(request, pk):
    from ..models import ModeleMessage
    from referentiel.models import Statut, TypeEntretien as TypeEntretienRef

    if not _est_admin_entreprise(request):
        messages.error(request, "Action réservée à l'administrateur de l'entreprise.")
        return redirect('entreprise:modeles_messages')

    modele = get_object_or_404(ModeleMessage, pk=pk, entreprise=request.entreprise)
    statuts          = list(Statut.objects.filter(estActif=True).order_by('ordre'))
    statuts_ids      = {str(s.id) for s in statuts}
    types_entretien  = list(TypeEntretienRef.objects.all())
    types_ids        = {str(t.id) for t in types_entretien}

    erreurs = {}
    if request.method == 'POST':
        valeurs = {
            'contexte':         (request.POST.get('contexte') or 'STATUT').strip().upper(),
            'statut_id':        request.POST.get('statut_id', '').strip(),
            'typeEntretien_id': request.POST.get('typeEntretien_id', '').strip(),
            'sujet_modele':     request.POST.get('sujet_modele', '').strip(),
            'corps_message':    request.POST.get('corps_message', '').strip(),
            'est_actif':        request.POST.get('est_actif') == 'on',
        }
    else:
        # Contexte initial déduit du modèle existant
        contexte_init = 'ENTRETIEN' if modele.typeEntretien_id else 'STATUT'
        valeurs = {
            'contexte':         contexte_init,
            'statut_id':        str(modele.statut_id) if modele.statut_id else '',
            'typeEntretien_id': str(modele.typeEntretien_id) if modele.typeEntretien_id else '',
            'sujet_modele':     modele.sujet_modele,
            'corps_message':    modele.corps_message,
            'est_actif':        modele.est_actif,
        }

    if request.method == 'POST':
        if valeurs['contexte'] not in ('STATUT', 'ENTRETIEN'):
            erreurs['contexte'] = "Choisissez le contexte d'utilisation du modèle."
        if not valeurs['sujet_modele']:
            erreurs['sujet_modele'] = "Le sujet est obligatoire."
        if not valeurs['corps_message']:
            erreurs['corps_message'] = "Le corps du message est obligatoire."

        if valeurs['contexte'] == 'STATUT':
            if valeurs['statut_id'] not in statuts_ids:
                erreurs['statut_id'] = "Sélectionnez un statut valide."
        elif valeurs['contexte'] == 'ENTRETIEN':
            if valeurs['typeEntretien_id'] not in types_ids:
                erreurs['typeEntretien_id'] = "Sélectionnez un type d'entretien valide."

        if not erreurs and request.entreprise.modeles_messages.filter(
            sujet_modele__iexact=valeurs['sujet_modele']
        ).exclude(pk=modele.pk).exists():
            erreurs['sujet_modele'] = "Un autre modèle avec ce sujet existe déjà."

        if not erreurs:
            if valeurs['contexte'] == 'STATUT':
                modele.statut_id        = int(valeurs['statut_id'])
                modele.typeEntretien_id = None
            else:
                modele.statut_id        = None
                modele.typeEntretien_id = int(valeurs['typeEntretien_id'])
            modele.sujet_modele     = valeurs['sujet_modele']
            modele.corps_message    = valeurs['corps_message']
            modele.est_actif        = valeurs['est_actif']
            modele.save()
            messages.success(request, f"Modèle « {modele.sujet_modele} » mis à jour.")
            return redirect('entreprise:modeles_messages')

    from ..messagerie import VARIABLES_GENERIQUES, VARIABLES_ENTRETIEN
    return render(request, 'entreprise/modeles_messages/form.html', {
        'modele':              modele,
        'valeurs':             valeurs,
        'erreurs':             erreurs,
        'statuts':             statuts,
        'types_entretien':     types_entretien,
        'vars_generiques':     VARIABLES_GENERIQUES,
        'vars_entretien':      VARIABLES_ENTRETIEN,
    })


@entreprise_required
@require_POST
def modele_message_supprimer(request, pk):
    from ..models import ModeleMessage

    if not _est_admin_entreprise(request):
        messages.error(request, "Action réservée à l'administrateur de l'entreprise.")
        return redirect('entreprise:modeles_messages')

    modele = get_object_or_404(ModeleMessage, pk=pk, entreprise=request.entreprise)
    sujet  = modele.sujet_modele
    modele.delete()
    messages.success(request, f"Modèle « {sujet} » supprimé.")
    return redirect('entreprise:modeles_messages')
