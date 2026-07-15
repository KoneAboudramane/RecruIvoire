"""Interview management views — planning, rescheduling, cancellation."""
import logging
from collections import OrderedDict
from datetime import datetime, timedelta

from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.db.models import Q
from django.views.decorators.http import require_POST

from .. import app_messages as messages
from ..models import (
    OffreEmploi, StatutOffre, RoleMembre,
    InvitationEntretien, OffreEmploiRecruteur,
    NotificationRecruteur, Message as MessageModel,
)
from ..decorators import entreprise_required, lecteur_bloque
from ..messagerie import rendre_template
from candidat.models import Candidature, Entretien, NotificationCandidat

from .offres import _offres_visibles

logger = logging.getLogger(__name__)


# ─── Entretiens : planification après acceptation ───────────────────────────

@entreprise_required
def entretiens_liste(request):
    """Liste des OFFRES ayant au moins 1 candidature acceptée ou 1 profil retenu.

    Une offre EXPIRÉE disparaît dès que :
      • tous les candidats acceptés ont un entretien planifié,
      • toutes les dates d'entretien sont passées,
      • aucun profil retenu (InvitationEntretien) n'est encore en attente ou planifié dans le futur.
    """
    from candidat.models import Candidature
    from collections import OrderedDict

    maintenant = timezone.now()

    candidatures = (
        Candidature.objects
        .filter(offre__in=_offres_visibles(request), statut__code='ACCEPTEE')
        .select_related('offre')
        .prefetch_related('entretiens')
        .order_by('offre__titre', '-dateCandidature')
    )

    offres_dict = OrderedDict()
    for c in candidatures:
        infos = offres_dict.setdefault(c.offre.id, {
            'offre':          c.offre,
            'nb_candidats':   0,
            'nb_planifies':   0,
            'nb_a_planifier': 0,
            'nb_profils':     0,
            'a_futur':        False,  # au moins un entretien à venir
        })
        infos['nb_candidats'] += 1
        entretiens = list(c.entretiens.all())
        if entretiens:
            infos['nb_planifies'] += 1
            if any(e.dateEntretien >= maintenant for e in entretiens):
                infos['a_futur'] = True
        else:
            infos['nb_a_planifier'] += 1

    # Profils retenus en attente de planification
    retenus = (
        InvitationEntretien.objects
        .filter(offre__in=_offres_visibles(request), statut=InvitationEntretien.STATUT_EN_ATTENTE)
        .select_related('offre', 'candidat', 'candidat__informationPersonnelle')
        .order_by('offre__titre', '-dateCreation')
    )
    for r in retenus:
        infos = offres_dict.setdefault(r.offre.id, {
            'offre':          r.offre,
            'nb_candidats':   0,
            'nb_planifies':   0,
            'nb_a_planifier': 0,
            'nb_profils':     0,
            'a_futur':        False,
        })
        infos['nb_profils'] += 1

    # Profils retenus déjà planifiés mais avec date future → garder l'offre
    inv_planifies_futur = set(
        InvitationEntretien.objects
        .filter(
            offre__in=_offres_visibles(request),
            statut=InvitationEntretien.STATUT_PLANIFIE,
            dateEntretien__gte=maintenant,
        )
        .values_list('offre_id', flat=True)
    )
    for offre_id in inv_planifies_futur:
        if offre_id in offres_dict:
            offres_dict[offre_id]['a_futur'] = True

    # Filtrage : offre expirée + tout planifié + tout passé → disparaît
    offres = [
        o for o in offres_dict.values()
        if not (
            o['offre'].statutOffre == StatutOffre.EXPIREE
            and o['nb_a_planifier'] == 0
            and o['nb_profils'] == 0
            and not o['a_futur']
        )
    ]

    total      = sum(o['nb_candidats'] for o in offres)
    avec       = sum(o['nb_planifies'] for o in offres)
    sans       = sum(o['nb_a_planifier'] for o in offres)
    nb_retenus = sum(o['nb_profils'] for o in offres)

    return render(request, 'entreprise/entretiens/liste.html', {
        'offres':          offres,
        'nb_offres':       len(offres),
        'total':           total,
        'avec_entretien':  avec,
        'sans_entretien':  sans,
        'nb_retenus':      nb_retenus,
    })


@entreprise_required
def entretiens_tous(request):
    """Vue d'ensemble : tous les entretiens de l'entreprise, séparés en
    « À venir » (date >= maintenant) et « Historique » (date < maintenant).

    Filtres GET optionnels :
      • offre=<id>     — restreint à une offre
      • statut=<code>  — PLANIFIE / REPORTE / ANNULE / REALISE
    """
    from candidat.models import Entretien

    entretiens_qs = (
        Entretien.objects
        .filter(candidature__offre__in=_offres_visibles(request))
        .select_related(
            'candidature__candidat',
            'candidature__offre',
            'typeEntretienRef',
            'modeRef',
            'createPar',
        )
    )

    # Filtres optionnels
    offre_id_filtre = request.GET.get('offre', '').strip()
    if offre_id_filtre.isdigit():
        entretiens_qs = entretiens_qs.filter(candidature__offre_id=int(offre_id_filtre))

    statut_filtre = request.GET.get('statut', '').strip().upper()
    maintenant = timezone.now()

    # Filtre statut basé sur la date réelle (pas seulement le champ statut)
    if statut_filtre == 'PLANIFIE':
        # Planifié = PLANIFIE en base ET date future
        entretiens_qs = entretiens_qs.filter(statut='PLANIFIE', dateEntretien__gte=maintenant)
    elif statut_filtre == 'REALISE':
        # Réalisé = date passée (PLANIFIE+passé) OU explicitement REALISE
        entretiens_qs = entretiens_qs.filter(
            Q(statut='PLANIFIE', dateEntretien__lt=maintenant) | Q(statut='REALISE')
        )
    elif statut_filtre in ('REPORTE', 'ANNULE'):
        entretiens_qs = entretiens_qs.filter(statut=statut_filtre)

    a_venir    = list(entretiens_qs.filter(dateEntretien__gte=maintenant).order_by('dateEntretien'))
    historique = list(entretiens_qs.filter(dateEntretien__lt=maintenant).order_by('-dateEntretien'))

    # Groupement des entretiens à venir par date (pour vue chronologique)
    from collections import OrderedDict
    a_venir_par_date = OrderedDict()
    for e in a_venir:
        jour = timezone.localtime(e.dateEntretien).date()
        a_venir_par_date.setdefault(jour, []).append(e)

    # Stats basées sur la date réelle
    tous_qs = Entretien.objects.filter(candidature__offre__in=_offres_visibles(request))
    if offre_id_filtre.isdigit():
        tous_qs = tous_qs.filter(candidature__offre_id=int(offre_id_filtre))
    stats_statuts = {
        'planifies': tous_qs.filter(statut='PLANIFIE', dateEntretien__gte=maintenant).count(),
        'reportes':  tous_qs.filter(statut='REPORTE').count(),
        'realises':  tous_qs.filter(
            Q(statut='PLANIFIE', dateEntretien__lt=maintenant) | Q(statut='REALISE')
        ).count(),
        'annules':   tous_qs.filter(statut='ANNULE').count(),
    }

    # Liste des offres ayant au moins 1 entretien — pour le filtre
    offres_avec_entretiens = (
        OffreEmploi.objects
        .filter(entreprise=request.entreprise, candidatures__entretiens__isnull=False)
        .distinct()
        .order_by('titre')
    )

    return render(request, 'entreprise/entretiens/tous.html', {
        'a_venir':                a_venir,
        'a_venir_par_date':       a_venir_par_date,
        'historique':             historique,
        'total_a_venir':          len(a_venir),
        'total_historique':       len(historique),
        'stats_statuts':          stats_statuts,
        'offres_avec_entretiens': offres_avec_entretiens,
        'offre_id_filtre':        offre_id_filtre,
        'statut_filtre':          statut_filtre,
        'today':                  timezone.localdate(),
    })


@entreprise_required
def entretiens_offre(request, offre_id):
    """Page de planification : candidats acceptés SANS entretien PLANIFIE.

    Règle métier : un candidat ne peut pas être programmé deux fois sur la
    même offre. Seul un entretien au statut REPORTE permet de re-planifier
    (donc on l'autorise dans cette liste). Les entretiens PLANIFIE et REALISE
    sont affichés sur la page « Déjà programmés » via `entretiens_offre_programmes`.
    """
    from candidat.models import Candidature, Entretien
    from referentiel.models import TypeEntretien as TypeEntretienRef, ModeEntretien as ModeEntretienRef
    from ..models import OffreEmploi, ModeleMessage

    offre = get_object_or_404(_offres_visibles(request), pk=offre_id)

    # IDs des candidatures déjà programmées (entretien PLANIFIE existant)
    ids_programmees = set(
        Entretien.objects
        .filter(candidature__offre=offre, statut=Entretien.StatutEntretien.PLANIFIE)
        .values_list('candidature_id', flat=True)
    )

    candidatures = (
        Candidature.objects
        .filter(offre=offre, statut__code='ACCEPTEE')
        .exclude(pk__in=ids_programmees)
        .select_related('candidat', 'offre', 'statut')
        .prefetch_related('entretiens__typeEntretienRef', 'entretiens__modeRef')
        .order_by('-dateCandidature')
    )

    # IDs candidatures avec entretien REPORTE (pour le filtre et la traçabilité)
    ids_reportees = set(
        Entretien.objects
        .filter(candidature__offre=offre, statut=Entretien.StatutEntretien.REPORTE)
        .values_list('candidature_id', flat=True)
    )

    total         = candidatures.count()
    nb_reportes   = sum(1 for c in candidatures if c.id in ids_reportees)
    sans_entretien = total - nb_reportes
    nb_programmes  = len(ids_programmees)

    # Modèles de message actifs liés à un type d'entretien (pour le filtrage côté form).
    # Les modèles sans typeEntretien sont ignorés ici — ils servent à d'autres flows
    # (réponse à candidature) et ne sont pas pertinents pour la planification d'entretien.
    modeles_qs = (
        request.entreprise.modeles_messages
        .filter(est_actif=True, typeEntretien__isnull=False)
        .select_related('statut', 'typeEntretien')
        .order_by('typeEntretien__ordre', 'sujet_modele')
    )

    # Profils retenus depuis portfolio (bouton "Retenir pour entretien")
    profils_retenus = (
        InvitationEntretien.objects
        .filter(offre=offre, statut=InvitationEntretien.STATUT_EN_ATTENTE)
        .select_related('candidat', 'candidat__informationPersonnelle', 'recruteur')
        .order_by('-dateCreation')
    )

    return render(request, 'entreprise/entretiens/detail.html', {
        'offre':            offre,
        'candidatures':     candidatures,
        'total':            total,
        'nb_reportes':      nb_reportes,
        'sans_entretien':   sans_entretien,
        'nb_programmes':    nb_programmes,
        'ids_reportees':    ids_reportees,
        'types_entretien':  TypeEntretienRef.objects.all(),
        'modes_entretien':  ModeEntretienRef.objects.all(),
        'modeles_messages': modeles_qs,
        'profils_retenus':  profils_retenus,
    })


@entreprise_required
@lecteur_bloque
@require_POST
def entretien_planifier(request, candidature_id):
    """Crée un Entretien pour une candidature acceptée."""
    from candidat.models import Candidature, Entretien
    from datetime import datetime

    candidature = get_object_or_404(
        Candidature.objects.select_related('offre', 'statut'),
        pk=candidature_id,
        offre__in=_offres_visibles(request),
    )
    rec = getattr(request, 'recruteur', None)
    if rec is not None and rec.roleMembre not in (RoleMembre.RH, RoleMembre.MANAGER, RoleMembre.ADMIN):
        messages.error(request, "Réservé aux RH et Managers.")
        return redirect('entreprise:entretiens')

    if not candidature.statut or candidature.statut.code != 'ACCEPTEE':
        messages.error(request, "La candidature doit être acceptée pour planifier un entretien.")
        return redirect('entreprise:entretiens')

    date_str = (request.POST.get('dateEntretien') or '').strip()
    heure_str = (request.POST.get('heure') or '').strip()
    if not date_str or not heure_str:
        messages.error(request, "Date et heure sont obligatoires.")
        return redirect('entreprise:entretiens')

    try:
        date_combine = datetime.fromisoformat(f'{date_str}T{heure_str}')
    except ValueError:
        messages.error(request, "Date ou heure invalide.")
        return redirect('entreprise:entretiens')

    if timezone.is_naive(date_combine):
        date_combine = timezone.make_aware(date_combine)

    if date_combine <= timezone.now():
        messages.error(request, "La date de l'entretien doit être dans le futur.")
        return redirect('entreprise:entretiens')

    duree_raw = (request.POST.get('duree') or '60').strip()
    try:
        duree = max(15, min(480, int(duree_raw)))
    except ValueError:
        duree = 60

    mode = (request.POST.get('mode') or 'PRESENTIEL').strip().upper()
    if mode not in ('PRESENTIEL', 'VISIO', 'TELEPHONIQUE'):
        mode = 'PRESENTIEL'

    type_choices = {c[0] for c in Entretien.TypeEntretien.choices}
    type_entretien = (request.POST.get('typeEntretien') or 'RH').strip().upper()
    if type_entretien not in type_choices:
        type_entretien = 'RH'

    # Notification candidat (Message)
    from ..models import Message as MessageModel
    sujet = f"Entretien planifié pour « {candidature.offre.titre} »"
    mode_lib = dict([('PRESENTIEL', 'Présentiel'), ('VISIO', 'Visioconférence'),
                     ('TELEPHONIQUE', 'Téléphonique')]).get(mode, mode)
    corps = (
        f"Bonjour {candidature.candidat.prenom},\n\n"
        f"Nous avons le plaisir de vous convier à un entretien pour le poste "
        f"« {candidature.offre.titre} ».\n\n"
        f"📅 Date : {date_combine:%A %d %B %Y à %H:%M}\n"
        f"⏱️ Durée : {duree} minutes\n"
        f"📍 Mode : {mode_lib}\n"
    )
    if (request.POST.get('lieu') or '').strip():
        corps += f"📌 Lieu / Lien : {request.POST.get('lieu').strip()}\n"
    if (request.POST.get('notes') or '').strip():
        corps += f"\nNotes : {request.POST.get('notes').strip()}\n"
    corps += f"\nÀ très bientôt,\n{request.entreprise}"

    from candidat.models import NotificationCandidat
    lien_filtre = f"{reverse('candidat:mes_candidatures')}?offre={candidature.offre_id}"

    with transaction.atomic():
        Entretien.objects.create(
            candidature   = candidature,
            dateEntretien = date_combine,
            duree         = duree,
            mode          = mode,
            typeEntretien = type_entretien,
            lieu          = (request.POST.get('lieu') or '').strip()[:300],
            notes         = (request.POST.get('notes') or '').strip(),
            createPar     = rec,
        )

        msg_cree = MessageModel.objects.create(
            candidat       = candidature.candidat,
            recruteur      = rec,
            candidature    = candidature,
            sujet          = sujet,
            contenu        = corps,
            modele_utilise = '(planification entretien)',
        )

        # Notification cloche pour le candidat — lien filtré sur l'offre
        NotificationCandidat.objects.update_or_create(
            candidat = candidature.candidat,
            type     = NotificationCandidat.Type.CANDIDATURE,
            offre    = candidature.offre,
            defaults = {
                'titre':            f"📅 Entretien planifié — {candidature.offre.titre}",
                'message':          f"{date_combine:%A %d %B à %H:%M} · {mode_lib}",
                'lien':             lien_filtre,
                'lue':              False,
                'messageRecruteur': msg_cree,
            },
        )

    messages.success(
        request,
        f"Entretien planifié pour {candidature.candidat.prenom} {candidature.candidat.nom} "
        f"le {date_combine:%d/%m/%Y à %H:%M}.",
    )
    return redirect('entreprise:entretiens')


@entreprise_required
def entretiens_offre_programmes(request, offre_id):
    """Liste tous les entretiens d'une offre, séparés en à-venir et historique."""
    from candidat.models import Entretien
    from ..models import OffreEmploi

    offre = get_object_or_404(_offres_visibles(request), pk=offre_id)
    maintenant = timezone.now()

    qs = (
        Entretien.objects
        .filter(candidature__offre=offre)
        .exclude(statut=Entretien.StatutEntretien.REPORTE)   # REPORTE → retourne dans "À planifier"
        .select_related('candidature__candidat', 'candidature__offre', 'typeEntretienRef', 'modeRef', 'createPar')
    )

    # À venir : date future ET statut PLANIFIE
    a_venir = list(
        qs.filter(
            dateEntretien__gte=maintenant,
            statut=Entretien.StatutEntretien.PLANIFIE,
        ).order_by('dateEntretien')
    )
    # Historique : REALISE, ANNULE, ou date passée
    historique = list(
        qs.exclude(pk__in=[e.pk for e in a_venir]).order_by('-dateEntretien')
    )

    return render(request, 'entreprise/entretiens/detail_programmes.html', {
        'offre':      offre,
        'a_venir':    a_venir,
        'historique': historique,
        'total':      len(a_venir) + len(historique),
    })


@entreprise_required
@lecteur_bloque
@require_POST
def entretiens_planifier_bulk(request, offre_id):
    """Planifie des entretiens en créneaux successifs pour plusieurs candidatures."""
    from candidat.models import Candidature, Entretien, NotificationCandidat
    from referentiel.models import TypeEntretien as TypeEntretienRef, ModeEntretien as ModeEntretienRef
    from ..models import OffreEmploi, Message as MessageModel
    from datetime import datetime, timedelta

    offre = get_object_or_404(_offres_visibles(request), pk=offre_id)

    rec = getattr(request, 'recruteur', None)
    if rec is not None and rec.roleMembre not in (RoleMembre.RH, RoleMembre.MANAGER, RoleMembre.ADMIN):
        messages.error(request, "Réservé aux RH et Managers.")
        return redirect('entreprise:entretiens_offre', offre_id=offre.id)

    ids      = request.POST.getlist('candidatures')
    inv_ids  = request.POST.getlist('invitations')
    if not ids and not inv_ids:
        messages.error(request, "Aucun candidat sélectionné.")
        return redirect('entreprise:entretiens_offre', offre_id=offre.id)

    date_str  = (request.POST.get('dateEntretien') or '').strip()
    heure_str = (request.POST.get('heure') or '').strip()
    if not date_str or not heure_str:
        messages.error(request, "Date et heure de début sont obligatoires.")
        return redirect('entreprise:entretiens_offre', offre_id=offre.id)

    try:
        debut = datetime.fromisoformat(f'{date_str}T{heure_str}')
    except ValueError:
        messages.error(request, "Date ou heure invalide.")
        return redirect('entreprise:entretiens_offre', offre_id=offre.id)

    if timezone.is_naive(debut):
        debut = timezone.make_aware(debut)

    if debut <= timezone.now():
        messages.error(request, "La date de début doit être dans le futur.")
        return redirect('entreprise:entretiens_offre', offre_id=offre.id)

    try:
        duree = max(15, min(480, int((request.POST.get('duree') or '60').strip())))
    except ValueError:
        duree = 60

    pas_minutes = duree

    mode_ref = ModeEntretienRef.objects.filter(pk=request.POST.get('modeRef')).first()
    if mode_ref is None:
        mode_ref = ModeEntretienRef.objects.filter(code='PRESENTIEL').first()
    type_ref = TypeEntretienRef.objects.filter(pk=request.POST.get('typeEntretienRef')).first()
    if type_ref is None:
        type_ref = TypeEntretienRef.objects.filter(code='RH').first()

    # Sync vers les champs legacy
    mode_code = mode_ref.code if mode_ref else 'PRESENTIEL'
    type_code = type_ref.code if type_ref else 'RH'

    # Modèle de message choisi par le recruteur (optionnel)
    from ..messagerie import rendre_template
    modele_id = (request.POST.get('modele_id') or '').strip()
    modele = None
    if modele_id.isdigit():
        modele = (
            request.entreprise.modeles_messages
            .filter(pk=int(modele_id), est_actif=True)
            .select_related('statut')
            .first()
        )

    lieu  = (request.POST.get('lieu') or '').strip()[:300]
    notes = (request.POST.get('notes') or '').strip()

    candidatures = list(
        Candidature.objects
        .filter(pk__in=ids, offre=offre, statut__code='ACCEPTEE')
        .select_related('candidat', 'offre')
        .order_by('candidat__nom', 'candidat__prenom')
    )

    mode_lib = mode_ref.libelle if mode_ref else mode_code

    n = 0
    with transaction.atomic():
        for idx, candidature in enumerate(candidatures):
            date_combine = debut + timedelta(minutes=pas_minutes * idx)

            Entretien.objects.create(
                candidature      = candidature,
                dateEntretien    = date_combine,
                duree            = duree,
                mode             = mode_code,
                modeRef          = mode_ref,
                typeEntretien    = type_code,
                typeEntretienRef = type_ref,
                lieu             = lieu,
                notes            = notes,
                createPar        = rec,
            )

            # Message candidat — via modèle choisi par le recruteur, sinon fallback générique
            if modele is not None:
                contexte_tpl = {
                    'candidat':    candidature.candidat,
                    'offre':       candidature.offre,
                    'entreprise':  request.entreprise,
                    'recruteur':   rec,
                    'candidature': candidature,
                    'entretien': {
                        'date':  date_format(date_combine, 'l j F Y'),
                        'heure': date_format(date_combine, 'H:i'),
                        'duree': duree,
                        'mode':  mode_lib,
                        'lieu':  lieu,
                    },
                }
                sujet_rendu = rendre_template(modele.sujet_modele, **contexte_tpl)
                corps_rendu = rendre_template(modele.corps_message, **contexte_tpl)
                msg_cree = MessageModel.objects.create(
                    candidat       = candidature.candidat,
                    recruteur      = rec,
                    candidature    = candidature,
                    modele_message = modele,
                    modele_utilise = modele.sujet_modele,
                    sujet          = sujet_rendu,
                    contenu        = corps_rendu,
                )
            else:
                corps = (
                    f"Bonjour {candidature.candidat.prenom},\n\n"
                    f"Nous avons le plaisir de vous convier à un entretien pour le poste "
                    f"« {candidature.offre.titre} ».\n\n"
                    f"📅 Date : {date_combine:%A %d %B %Y à %H:%M}\n"
                    f"⏱️ Durée : {duree} minutes\n"
                    f"📍 Mode : {mode_lib}\n"
                )
                if lieu:
                    corps += f"📌 Lieu / Lien : {lieu}\n"
                if notes:
                    corps += f"\nNotes : {notes}\n"
                corps += f"\nÀ très bientôt,\n{request.entreprise}"

                msg_cree = MessageModel.objects.create(
                    candidat       = candidature.candidat,
                    recruteur      = rec,
                    candidature    = candidature,
                    sujet          = f"Entretien planifié pour « {candidature.offre.titre} »",
                    contenu        = corps,
                    modele_utilise = '(planification entretien — global)',
                )

            # Notification cloche
            lien_filtre = f"{reverse('candidat:mes_candidatures')}?offre={candidature.offre_id}"
            NotificationCandidat.objects.update_or_create(
                candidat = candidature.candidat,
                type     = NotificationCandidat.Type.CANDIDATURE,
                offre    = candidature.offre,
                defaults = {
                    'titre':            f"📅 Entretien planifié — {candidature.offre.titre}",
                    'message':          f"{date_combine:%A %d %B à %H:%M} · {mode_lib}",
                    'lien':             lien_filtre,
                    'lue':              False,
                    'messageRecruteur': msg_cree,
                },
            )
            n += 1

        # ── Profils retenus (InvitationEntretien) ───────────────────────────────
        invitations = list(
            InvitationEntretien.objects
            .filter(pk__in=inv_ids, offre=offre, statut=InvitationEntretien.STATUT_EN_ATTENTE)
            .select_related('candidat', 'offre')
            .order_by('candidat__nom', 'candidat__prenom')
        )

        for idx, inv in enumerate(invitations):
            date_combine = debut + timedelta(minutes=pas_minutes * (n + idx))
            inv.dateEntretien = date_combine
            inv.duree         = duree
            inv.mode          = mode_code
            inv.lieu          = lieu
            inv.notes         = notes
            inv.statut        = InvitationEntretien.STATUT_PLANIFIE
            inv.save(update_fields=['dateEntretien', 'duree', 'mode', 'lieu', 'notes', 'statut'])

            corps_inv = (
                f"Bonjour {inv.candidat.prenom},\n\n"
                f"Votre profil a été sélectionné pour un entretien concernant le poste "
                f"« {inv.offre.titre} ».\n\n"
                f"📅 Date : {date_combine:%A %d %B %Y à %H:%M}\n"
                f"⏱️ Durée : {duree} minutes\n"
                f"📍 Mode : {mode_lib}\n"
            )
            if lieu:
                corps_inv += f"📌 Lieu / Lien : {lieu}\n"
            if notes:
                corps_inv += f"\nNotes : {notes}\n"
            corps_inv += f"\nÀ très bientôt,\n{request.entreprise}"

            from ..models import Message as MessageModel
            msg_inv = MessageModel.objects.create(
                candidat       = inv.candidat,
                recruteur      = rec,
                sujet          = f"Entretien planifié — {inv.offre.titre}",
                contenu        = corps_inv,
                modele_utilise = '(planification profil retenu)',
            )

            NotificationCandidat.objects.update_or_create(
                candidat = inv.candidat,
                type     = NotificationCandidat.Type.ENTRETIEN,
                offre    = inv.offre,
                defaults = {
                    'titre':            f"📅 Entretien planifié — {inv.offre.titre}",
                    'message':          f"{date_combine:%A %d %B à %H:%M} · {mode_lib}",
                    'lien':             reverse('candidat:invitations'),
                    'lue':              False,
                    'messageRecruteur': msg_inv,
                },
            )

    total_planifies = n + len(invitations)
    if total_planifies:
        messages.success(
            request,
            f"{total_planifies} entretien{'s' if total_planifies > 1 else ''} planifié{'s' if total_planifies > 1 else ''} "
            f"en créneaux de {duree} min à partir du {debut:%d/%m/%Y à %H:%M}.",
        )
    else:
        messages.warning(request, "Aucun candidat éligible parmi ceux sélectionnés.")

    return redirect('entreprise:entretiens_offre', offre_id=offre.id)


@entreprise_required
@lecteur_bloque
@require_POST
def entretien_reporter(request, entretien_id):
    """Passe un entretien PLANIFIE en REPORTE.

    Le candidat reste dans le vivier « à planifier » pour cette offre, et
    une cloche le prévient. L'ancien entretien reste en base (audit).
    """
    from candidat.models import Entretien, NotificationCandidat

    entretien = get_object_or_404(
        Entretien.objects.select_related('candidature__offre', 'candidature__candidat'),
        pk=entretien_id,
        candidature__offre__in=_offres_visibles(request),
    )
    rec = getattr(request, 'recruteur', None)
    if rec is not None and rec.roleMembre not in (RoleMembre.RH, RoleMembre.MANAGER, RoleMembre.ADMIN):
        messages.error(request, "Réservé aux RH et Managers.")
        return redirect('entreprise:entretiens')

    if entretien.statut != Entretien.StatutEntretien.PLANIFIE:
        messages.error(request, "Seul un entretien planifié peut être reporté.")
        return redirect('entreprise:entretiens_offre_programmes', offre_id=entretien.candidature.offre_id)

    candidature = entretien.candidature
    with transaction.atomic():
        entretien.statut = Entretien.StatutEntretien.REPORTE
        entretien.save(update_fields=['statut', 'dateModification'])

        # Notification cloche — le candidat est prévenu du report
        NotificationCandidat.objects.update_or_create(
            candidat = candidature.candidat,
            type     = NotificationCandidat.Type.CANDIDATURE,
            offre    = candidature.offre,
            defaults = {
                'titre':   f"↩ Entretien reporté — {candidature.offre.titre}",
                'message': "Votre entretien a été reporté. Nous reviendrons vers vous avec une nouvelle date.",
                'lien':    f"{reverse('candidat:mes_candidatures')}?offre={candidature.offre_id}",
                'lue':     False,
            },
        )

    messages.success(
        request,
        f"Entretien de {candidature.candidat.prenom} {candidature.candidat.nom} reporté. "
        f"Le candidat est de nouveau disponible pour replanification.",
    )
    return redirect('entreprise:entretiens_offre', offre_id=candidature.offre_id)


@entreprise_required
@lecteur_bloque
@require_POST
def entretien_annuler(request, entretien_id):
    """Annule un entretien (statut → ANNULE) — soft delete, conserve la trace.

    Le candidat est notifié et redevient planifiable (puisque l'entretien
    n'est plus au statut PLANIFIE).
    """
    from candidat.models import Entretien, NotificationCandidat

    entretien = get_object_or_404(
        Entretien.objects.select_related('candidature__offre', 'candidature__candidat'),
        pk=entretien_id,
        candidature__offre__in=_offres_visibles(request),
    )
    rec = getattr(request, 'recruteur', None)
    if rec is not None and rec.roleMembre not in (RoleMembre.RH, RoleMembre.MANAGER, RoleMembre.ADMIN):
        messages.error(request, "Réservé aux RH et Managers.")
        return redirect('entreprise:entretiens')

    if entretien.statut == Entretien.StatutEntretien.ANNULE:
        messages.info(request, "Cet entretien est déjà annulé.")
        return redirect('entreprise:entretiens_offre_programmes', offre_id=entretien.candidature.offre_id)

    candidature = entretien.candidature
    with transaction.atomic():
        entretien.statut = Entretien.StatutEntretien.ANNULE
        entretien.save(update_fields=['statut', 'dateModification'])

        NotificationCandidat.objects.update_or_create(
            candidat = candidature.candidat,
            type     = NotificationCandidat.Type.CANDIDATURE,
            offre    = candidature.offre,
            defaults = {
                'titre':   f"✕ Entretien annulé — {candidature.offre.titre}",
                'message': "Votre entretien a été annulé. Nous vous tiendrons informé(e) de la suite.",
                'lien':    f"{reverse('candidat:mes_candidatures')}?offre={candidature.offre_id}",
                'lue':     False,
            },
        )

    messages.success(
        request,
        f"Entretien de {candidature.candidat.prenom} {candidature.candidat.nom} annulé.",
    )
    return redirect('entreprise:entretiens_offre_programmes', offre_id=candidature.offre_id)


@entreprise_required
@lecteur_bloque
@require_POST
def entretien_marquer_realise(request, entretien_id):
    """Marque un entretien PLANIFIE ou REPORTE comme REALISE."""
    from candidat.models import Entretien, NotificationCandidat

    entretien = get_object_or_404(
        Entretien, pk=entretien_id,
        candidature__offre__in=_offres_visibles(request),
    )
    rec = getattr(request, 'recruteur', None)
    if rec and rec.roleMembre not in (RoleMembre.RH, RoleMembre.MANAGER, RoleMembre.ADMIN):
        messages.error(request, "Action réservée aux RH, Manager et Admin.")
        return redirect('entreprise:entretiens_tous')

    if entretien.statut not in ('PLANIFIE', 'REPORTE'):
        messages.error(request, "Cet entretien ne peut pas être marqué réalisé.")
        return redirect('entreprise:entretiens_tous')

    candidature = entretien.candidature
    try:
        with transaction.atomic():
            entretien.statut = 'REALISE'
            entretien.save(update_fields=['statut'])

            NotificationCandidat.objects.create(
                candidat=candidature.candidat,
                type=NotificationCandidat.Type.ENTRETIEN,
                titre="✓ Entretien réalisé",
                message=f"Votre entretien pour « {candidature.offre.titre} » a été marqué comme réalisé.",
                lien=reverse('candidat:mes_candidatures') + f'?offre={candidature.offre_id}',
            )
    except Exception:
        pass

    messages.success(
        request,
        f"Entretien de {candidature.candidat.prenom} {candidature.candidat.nom} marqué comme réalisé.",
    )
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or ''
    return redirect(next_url or 'entreprise:entretiens_tous')
