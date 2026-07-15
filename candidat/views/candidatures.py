"""Applications & interviews."""
import logging

from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .. import app_messages as messages
from ..decorators import candidat_required
from ..forms import CandidatureForm
from ..models import Candidature, NotificationCandidat, Entretien

logger = logging.getLogger(__name__)


def _ids_entretien_futur_passe(candidat, now):
    """IDs de candidatures ayant un entretien futur / passé, pour ce candidat."""
    ids_entretien_futur = set(
        Entretien.objects
        .filter(candidature__candidat=candidat, statut='PLANIFIE', dateEntretien__gt=now)
        .values_list('candidature_id', flat=True)
    )
    ids_entretien_passe = set(
        Entretien.objects
        .filter(candidature__candidat=candidat, statut__in=['PLANIFIE', 'REALISE'], dateEntretien__lte=now)
        .exclude(candidature_id__in=ids_entretien_futur)
        .values_list('candidature_id', flat=True)
    )
    return ids_entretien_futur, ids_entretien_passe


@candidat_required
@require_POST
def postuler(request, offre_id):
    """Traite la soumission d'une candidature à une offre."""
    from entreprise.models import OffreEmploi, StatutOffre

    offre = get_object_or_404(
        OffreEmploi, pk=offre_id, statutOffre=StatutOffre.PUBLIEE,
    )

    # Garde-fou : déjà postulé (hors candidatures retirées) ?
    from referentiel.models import Statut
    if Candidature.objects.filter(candidat=request.candidat, offre=offre).exclude(statut__code='RETIREE').exists():
        messages.warning(request, "Vous avez déjà postulé à cette offre.", extra_tags='candidat')
        return redirect('candidat:offre_detail', offre_id=offre.id)

    form = CandidatureForm(
        request.POST, request.FILES,
        candidat=request.candidat, offre=offre,
    )

    if not form.is_valid():
        offres_similaires = (
            OffreEmploi.objects
            .filter(statutOffre=StatutOffre.PUBLIEE, entreprise=offre.entreprise)
            .exclude(pk=offre.pk)
            .order_by('-datePublication')[:3]
        )
        from datetime import timedelta
        return render(request, 'candidat/offre_detail.html', {
            'offre':                  offre,
            'offres_similaires':      offres_similaires,
            'seuil_recente':          timezone.now() - timedelta(days=7),
            'matching':               None,
            'candidature_existante':  None,
            'candidature_form':       form,
            'ouvrir_formulaire':      True,
        })

    url_portfolio = request.build_absolute_uri(
        reverse('candidat:portfolio_public', kwargs={'candidat_id': request.candidat.id})
    )

    with transaction.atomic():
        Candidature.objects.filter(
            candidat=request.candidat, offre=offre, statut__code='RETIREE',
        ).delete()
        candidature = form.save(commit=False)
        candidature.candidat     = request.candidat
        candidature.offre        = offre
        candidature.urlPortfolio = url_portfolio
        candidature.save()
        candidature.soumettre()

    # ── Auto-envoi du message de l'entreprise lié au statut POSTULEE ─────────
    _envoyer_message_postulee(request, candidature)

    messages.success(
        request,
        f"Candidature envoyée pour « {offre.titre} » — référence {candidature.reference}.",
        extra_tags='candidat',
    )
    return redirect('candidat:offre_detail', offre_id=offre.id)


def _envoyer_message_postulee(request, candidature):
    """Déclenche automatiquement le modèle de message « POSTULEE » de
    l'entreprise destinataire (s'il existe) à la création d'une candidature."""
    try:
        from entreprise.models import ModeleMessage, Message as MessageRecruteur
        from entreprise.messagerie import rendre_template
        from entreprise.models import RoleMembre
        from ..models import NotificationCandidat

        offre = candidature.offre
        entreprise = offre.entreprise

        modele = (
            ModeleMessage.objects
            .filter(
                entreprise=entreprise,
                statut__code='POSTULEE',
                est_actif=True,
            )
            .select_related('statut')
            .first()
        )

        msg = None
        if modele is not None:
            recruteur = (
                offre.creePar
                or entreprise.recruteurs.filter(roleMembre=RoleMembre.ADMIN).first()
                or entreprise.recruteurs.first()
            )
            if recruteur is not None:
                contexte = {
                    'candidat':    candidature.candidat,
                    'offre':       offre,
                    'entreprise':  entreprise,
                    'recruteur':   recruteur,
                    'candidature': candidature,
                }
                sujet_rendu = rendre_template(modele.sujet_modele, **contexte)
                corps_rendu = rendre_template(modele.corps_message, **contexte)
                msg = MessageRecruteur.objects.create(
                    candidat       = candidature.candidat,
                    recruteur      = recruteur,
                    candidature    = candidature,
                    modele_message = modele,
                    modele_utilise = modele.sujet_modele,
                    sujet          = sujet_rendu,
                    contenu        = corps_rendu,
                )

        from entreprise.models import NotificationRecruteur, RoleMembre
        candidat = candidature.candidat
        recruteur_dest = (
            offre.creePar
            or entreprise.recruteurs.filter(roleMembre=RoleMembre.ADMIN).first()
            or entreprise.recruteurs.first()
        )
        notif_kwargs = {
            'type':      NotificationRecruteur.Type.CANDIDATURE,
            'titre':     f"📩 Nouvelle candidature — {offre.titre}",
            'message':   f"{candidat.prenom} {candidat.nom} a postulé à votre offre.",
            'lien':      reverse('entreprise:candidatures_offre', args=[offre.id]),
            'offre':     offre,
            'candidat':  candidat,
        }
        with transaction.atomic():
            NotificationCandidat.objects.update_or_create(
                candidat = candidature.candidat,
                type     = NotificationCandidat.Type.CANDIDATURE,
                offre    = offre,
                defaults = {
                    'titre':            f"📥 Candidature envoyée — {offre.titre}",
                    'message':          f"Votre candidature chez {entreprise.raisonSocial} a bien été enregistrée.",
                    'lien':             f"{reverse('candidat:mes_candidatures')}?offre={offre.id}",
                    'lue':              False,
                    'messageRecruteur': msg,
                },
            )
            if recruteur_dest:
                NotificationRecruteur.objects.create(recruteur=recruteur_dest, **notif_kwargs)
            else:
                NotificationRecruteur.objects.create(entreprise=entreprise, **notif_kwargs)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Auto-envoi du message POSTULEE a échoué")


@candidat_required
def mes_candidatures(request):
    """Liste des candidatures du candidat connecté avec stats, filtres et timeline."""
    from django.db.models import Q

    candidat = request.candidat

    qs = (
        Candidature.objects
        .filter(candidat=candidat)
        .select_related('offre', 'offre__entreprise', 'statut')
        .prefetch_related(
            'historiques__ancienStatut',
            'historiques__nouveauStatut',
            'messages__recruteur',
            'entretiens',
        )
    )

    from django.utils import timezone as tz
    now = tz.now()
    ids_entretien_futur, ids_entretien_passe = _ids_entretien_futur_passe(candidat, now)

    etat = (request.GET.get('etat') or '').strip().lower()
    if not etat:
        etat = 'en_cours'
    if etat == 'en_cours':
        qs = qs.filter(statut__estPositif__isnull=True, statut__estFinal=False)
    elif etat == 'positives':
        qs = qs.filter(statut__estPositif=True).exclude(pk__in=ids_entretien_futur)
    elif etat == 'negatives':
        qs = qs.filter(statut__estPositif=False)
    elif etat == 'entretiens':
        qs = qs.filter(pk__in=ids_entretien_futur)
    elif etat == 'total':
        pass

    offre_filtre = None
    offre_param = (request.GET.get('offre') or '').strip()
    if offre_param.isdigit():
        from entreprise.models import OffreEmploi
        offre_filtre = OffreEmploi.objects.filter(pk=int(offre_param)).first()
        if offre_filtre:
            qs = qs.filter(offre=offre_filtre)

    if not offre_filtre:
        from django.db.models import Q
        qs = qs.filter(
            Q(statut__estFinal=False) | Q(pk__in=ids_entretien_futur)
        ).exclude(pk__in=ids_entretien_passe)

    candidatures = list(qs.order_by('-dateCandidature'))

    from django.db.models import Q
    actives = (
        Candidature.objects
        .filter(candidat=candidat)
        .filter(Q(statut__estFinal=False) | Q(pk__in=ids_entretien_futur))
        .exclude(pk__in=ids_entretien_passe)
        .select_related('statut')
    )
    positives_qs = actives.filter(statut__estPositif=True).exclude(pk__in=ids_entretien_futur)
    stats = {
        'total':      actives.count(),
        'en_cours':   actives.filter(statut__estPositif__isnull=True).count(),
        'positives':  positives_qs.count(),
        'negatives':  actives.filter(statut__estPositif=False).count(),
        'entretiens': len(ids_entretien_futur - ids_entretien_passe),
    }

    return render(request, 'candidat/mes_candidatures.html', {
        'candidatures': candidatures,
        'stats':        stats,
        'etat_actif':   etat,
        'offre_filtre': offre_filtre,
    })


@candidat_required
def historique_candidatures(request):
    """Historique : candidatures clôturées ou dont l'entretien est passé."""
    from django.core.paginator import Paginator
    from django.utils import timezone as tz
    from django.db.models import Q

    candidat = request.candidat
    now = tz.now()

    ids_entretien_futur, ids_entretien_passe = _ids_entretien_futur_passe(candidat, now)

    qs = (
        Candidature.objects
        .filter(candidat=candidat)
        .filter(Q(statut__estFinal=True) | Q(pk__in=ids_entretien_passe))
        .exclude(pk__in=ids_entretien_futur)
        .select_related(
            'offre', 'offre__entreprise', 'offre__contrat',
            'offre__modeTravailRef', 'statut',
        )
        .prefetch_related(
            'historiques__ancienStatut',
            'historiques__nouveauStatut',
            'entretiens',
        )
    )

    statut_code = (request.GET.get('statut') or '').strip().upper()
    if statut_code == 'ENTRETIEN_PASSE':
        qs = qs.filter(pk__in=ids_entretien_passe)
    elif statut_code in ('RETIREE', 'REFUSEE'):
        qs = qs.filter(statut__code=statut_code)

    base = (
        Candidature.objects.filter(candidat=candidat)
        .filter(Q(statut__estFinal=True) | Q(pk__in=ids_entretien_passe))
        .exclude(pk__in=ids_entretien_futur)
    )
    stats = {
        'total':            base.count(),
        'retirees':         base.filter(statut__code='RETIREE').count(),
        'refusees':         base.filter(statut__code='REFUSEE').count(),
        'entretien_passe':  len(ids_entretien_passe),
    }

    paginator = Paginator(qs.order_by('-dateCandidature'), 20)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'candidat/historique_candidatures.html', {
        'candidatures': page_obj,
        'page_obj':     page_obj,
        'stats':        stats,
        'statut_actif': statut_code,
    })


@candidat_required
def entretien_ics(request, entretien_id):
    """Génère un fichier .ics pour ajouter l'entretien au calendrier."""
    from datetime import timedelta

    ent = get_object_or_404(
        Entretien, pk=entretien_id, candidature__candidat=request.candidat,
    )
    debut = ent.dateEntretien
    fin = debut + timedelta(minutes=ent.duree)
    type_label = ent.typeEntretienRef.libelle if ent.typeEntretienRef else ent.get_typeEntretien_display()
    entreprise = ent.candidature.offre.entreprise.raisonSocial
    offre = ent.candidature.offre.titre

    ics = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//RecrutePro//Entretien//FR\r\n"
        "BEGIN:VEVENT\r\n"
        f"DTSTART:{debut.strftime('%Y%m%dT%H%M%SZ')}\r\n"
        f"DTEND:{fin.strftime('%Y%m%dT%H%M%SZ')}\r\n"
        f"SUMMARY:{type_label} — {entreprise}\r\n"
        f"DESCRIPTION:Entretien pour le poste : {offre}\r\n"
        f"LOCATION:{ent.lieu}\r\n"
        "STATUS:CONFIRMED\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )

    response = HttpResponse(ics, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="entretien_{ent.pk}.ics"'
    return response


@candidat_required
def entretien_contacter(request, entretien_id):
    """Redirige vers la conversation avec le recruteur qui a planifié l'entretien."""
    from entreprise.models import ConversationDirecte

    ent = get_object_or_404(
        Entretien, pk=entretien_id, candidature__candidat=request.candidat,
    )
    recruteur = ent.createPar
    if not recruteur:
        messages.warning(request, "Aucun recruteur associé à cet entretien.")
        return redirect('candidat:mes_candidatures')

    conv, _ = ConversationDirecte.objects.get_or_create(
        recruteur=recruteur, candidat=request.candidat,
    )
    return redirect('candidat:conversation_detail', conv_id=conv.pk)


@candidat_required
@require_POST
def retirer_candidature(request, candidature_id):
    """Le candidat retire sa candidature (statut -> RETIREE)."""
    candidature = get_object_or_404(
        Candidature, pk=candidature_id, candidat=request.candidat,
    )
    motif = (request.POST.get('motif') or '').strip()
    if candidature.retirer(motif=motif):
        messages.success(
            request,
            f"Candidature « {candidature.offre.titre} » retirée.",
        )
    else:
        messages.warning(
            request,
            "Cette candidature ne peut plus être retirée.",
        )
    return redirect('candidat:mes_candidatures')
