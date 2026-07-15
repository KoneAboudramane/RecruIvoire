"""Application (candidature) management views."""
import logging
import json

from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Q, Exists, OuterRef, Prefetch
from django.views.decorators.http import require_POST

from .. import app_messages as messages
from ..models import (
    Entreprise, Recruteur, OffreEmploi, OffreEmploiRecruteur,
    StatutOffre, RoleMembre,
)
from ..decorators import entreprise_required, lecteur_bloque, bloque_roles
from candidat.models import Candidature
from .offres import _offres_visibles, _archiver_si_offre_traitee, _rattraper_offres_expirees, _sync_compteur_offres

logger = logging.getLogger(__name__)


@entreprise_required
def candidatures_par_offre(request):
    """Vue d'ensemble des offres avec leurs candidatures."""
    from candidat.models import Candidature
    from django.db.models import Case, When, IntegerField, Value

    entreprise = request.entreprise

    offres_a_traiter = _rattraper_offres_expirees(entreprise)
    if offres_a_traiter:
        nb = len(offres_a_traiter)
        titres = ', '.join(f'« {o.titre} »' for o in offres_a_traiter[:3])
        if nb > 3:
            titres += f' et {nb - 3} autre(s)'
        messages.info(
            request,
            f"📋 {nb} offre(s) sont arrivées à échéance et prêtes à être "
            f"évaluées : {titres}.",
        )
    rec = getattr(request, 'recruteur', None)

    recruteurs_entreprise = list(
        entreprise.recruteurs.filter(estActif=True).order_by('prenom', 'nom')
    )

    est_admin = (rec is None) or (rec.roleMembre == RoleMembre.ADMIN)
    scope = (request.GET.get('scope') or 'mes').strip().lower()
    if scope not in ('mes', 'entreprise', 'recruteur'):
        scope = 'mes'
    if not est_admin:
        scope = 'mes'

    recruteur_filtre_id = (request.GET.get('recruteur') or '').strip()
    recruteur_filtre = None
    if scope == 'recruteur' and recruteur_filtre_id.isdigit():
        recruteur_filtre = next(
            (r for r in recruteurs_entreprise if r.id == int(recruteur_filtre_id)),
            None,
        )
        if recruteur_filtre is None:
            scope = 'mes'

    pending_exists = Candidature.objects.filter(
        offre=OuterRef('pk'),
    ).exclude(statut__estFinal=True)

    offres_qs = (
        OffreEmploi.objects
        .filter(entreprise=entreprise)
        .annotate(
            nb_cand=Count('candidatures'),
            a_pending=Exists(pending_exists),
        )
        .filter(
            Q(statutOffre=StatutOffre.PUBLIEE)
            | Q(statutOffre=StatutOffre.EXPIREE, a_pending=True)
        )
        .prefetch_related(
            Prefetch(
                'candidatures',
                queryset=Candidature.objects
                    .select_related('candidat', 'statut')
                    .order_by('-dateCandidature'),
            ),
        )
    )

    if scope == 'entreprise':
        pass
    elif scope == 'recruteur' and recruteur_filtre is not None:
        offres_qs = offres_qs.filter(creePar=recruteur_filtre)
    else:
        scope = 'mes'
        if rec is not None:
            offres_qs = offres_qs.filter(creePar=rec)
        else:
            offres_qs = offres_qs.filter(creePar__isnull=True)

    total_offres        = offres_qs.count()
    nb_offres_postulees = offres_qs.filter(nb_cand__gt=0).count()
    nb_offres_non_post  = total_offres - nb_offres_postulees

    filtre = (request.GET.get('filtre') or 'toutes').strip().lower()
    if filtre not in ('toutes', 'postulees', 'non_postulees'):
        filtre = 'toutes'

    if filtre == 'postulees':
        offres = offres_qs.filter(nb_cand__gt=0)
    elif filtre == 'non_postulees':
        offres = offres_qs.filter(nb_cand=0)
    else:
        offres = offres_qs

    tri = (request.GET.get('tri') or 'date_recent').strip().lower()
    tris_valides = {
        'nom_asc':     ('titre',),
        'nom_desc':    ('-titre',),
        'date_recent': ('-dateCreation',),
        'date_ancien': ('dateCreation',),
    }
    if tri not in tris_valides:
        tri = 'date_recent'
    offres = offres.annotate(
        priorite=Case(
            When(statutOffre=StatutOffre.EXPIREE, a_pending=True, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
    ).order_by('priorite', *tris_valides[tri])

    q = (request.GET.get('q') or '').strip()
    if q:
        from recrutement.search import fts_filter
        offres = fts_filter(offres, q,
                            vector_fields=['titre', 'missions'],
                            fallback_lookups=['titre__icontains'])

    return render(request, 'entreprise/candidatures.html', {
        'offres':              offres,
        'filtre':              filtre,
        'tri':                 tri,
        'q':                   q,
        'total_offres':        total_offres,
        'nb_offres_postulees': nb_offres_postulees,
        'nb_offres_non_post':  nb_offres_non_post,
        'scope':                scope,
        'recruteur_filtre':     recruteur_filtre,
        'recruteurs_entreprise': recruteurs_entreprise,
    })


@entreprise_required
def candidatures_offre(request, offre_id):
    """Liste des candidatures d'une offre precise."""
    from candidat.models import Candidature

    offre = get_object_or_404(_offres_visibles(request), pk=offre_id)

    tri = request.GET.get('tri', 'date_recent')
    tri_map = {
        'date_recent': '-dateCandidature',
        'date_ancien': 'dateCandidature',
        'nom_az':      'candidat__nom',
        'nom_za':      '-candidat__nom',
    }
    order_field = tri_map.get(tri, '-dateCandidature')

    candidatures = (
        Candidature.objects
        .filter(offre=offre)
        .select_related('candidat', 'statut')
        .order_by(order_field)
    )

    total       = candidatures.count()
    en_attente  = candidatures.filter(statut__code='POSTULEE').count()
    acceptees   = candidatures.filter(statut__code__in=['ACCEPTEE', 'EMBAUCHEE']).count()
    refusees    = candidatures.filter(statut__code='REFUSEE').count()
    nb_eligibles    = candidatures.exclude(statut__estFinal=True).count()
    offre_finalisee = total > 0 and nb_eligibles == 0
    nb_decisions_prises = candidatures.filter(
        statut__code__in=['ACCEPTEE', 'REFUSEE'],
    ).count()

    modeles_actifs = list(
        request.entreprise.modeles_messages
        .filter(est_actif=True)
        .select_related('statut')
        .order_by('statut__ordre', 'sujet_modele')
    )
    modeles_acceptation = [m for m in modeles_actifs if m.statut and m.statut.code == 'ACCEPTEE']
    modeles_refus       = [m for m in modeles_actifs if m.statut and m.statut.code == 'REFUSEE']

    return render(request, 'entreprise/candidatures_offre.html', {
        'offre':                offre,
        'candidatures':         candidatures,
        'total':                total,
        'en_attente':           en_attente,
        'acceptees':            acceptees,
        'refusees':             refusees,
        'nb_eligibles':         nb_eligibles,
        'offre_finalisee':      offre_finalisee,
        'nb_decisions_prises':  nb_decisions_prises,
        'modeles_acceptation':  modeles_acceptation,
        'modeles_refus':        modeles_refus,
        'tri':          tri,
        'tri_options':  [
            ('date_recent', 'Date ↓'),
            ('date_ancien', 'Date ↑'),
            ('nom_az',      'Nom A→Z'),
            ('nom_za',      'Nom Z→A'),
        ],
    })


@entreprise_required
@lecteur_bloque
@require_POST
def candidature_decision(request, candidature_id):
    """Met a jour le statut d'une candidature (accepter / refuser)."""
    from candidat.models import Candidature, HistoriqueStatut
    from referentiel.models import Statut

    candidature = get_object_or_404(
        Candidature.objects.select_related('offre__entreprise', 'statut', 'candidat'),
        pk=candidature_id,
        offre__in=_offres_visibles(request),
    )

    rec = getattr(request, 'recruteur', None)
    if rec is not None and rec.roleMembre not in (RoleMembre.RH, RoleMembre.MANAGER, RoleMembre.ADMIN):
        messages.error(
            request,
            "Vous n'avez pas les droits pour accepter ou refuser une candidature. "
            "Cette action est réservée aux RH, Managers et Administrateurs.",
        )
        return redirect('entreprise:candidatures')

    decision    = (request.POST.get('decision') or '').strip().upper()
    commentaire = (request.POST.get('commentaire') or '').strip()

    mapping = {
        'ACCEPTER': 'ACCEPTEE',
        'REFUSER':  'REFUSEE',
    }
    code_cible = mapping.get(decision)
    if not code_cible:
        messages.error(request, "Décision invalide.")
        return redirect('entreprise:candidatures')

    statut_cible = Statut.objects.filter(code=code_cible).first()
    if not statut_cible:
        messages.error(request, "Statut cible introuvable dans le référentiel.")
        return redirect('entreprise:candidatures')

    if candidature.statut_id == statut_cible.id:
        messages.info(request, "La candidature est déjà dans ce statut.")
        return redirect('entreprise:candidatures')

    # ── Envoi optionnel d'un message au candidat via un modele ───────────────
    from ..models import ModeleMessage, Message as MessageModel
    from ..messagerie import rendre_template
    modele_id = (request.POST.get('modele_id') or '').strip()
    message_envoye = False
    modele = None
    if modele_id.isdigit():
        modele = ModeleMessage.objects.filter(
            pk=int(modele_id),
            entreprise=request.entreprise,
            est_actif=True,
        ).first()

    from candidat.models import NotificationCandidat
    if code_cible == 'ACCEPTEE':
        titre_notif = f"✅ Candidature acceptée — {candidature.offre.titre}"
    else:
        titre_notif = f"📋 Candidature non retenue — {candidature.offre.titre}"

    with transaction.atomic():
        HistoriqueStatut.creer(
            candidature=candidature,
            nouveau=statut_cible,
            ancien=candidature.statut,
            commentaire=commentaire or f'Décision : {statut_cible.libelle} (par {request.recruteur}).',
        )

        msg_cree = None
        if modele:
            contexte = {
                'candidat':    candidature.candidat,
                'offre':       candidature.offre,
                'entreprise':  request.entreprise,
                'recruteur':   request.recruteur,
                'candidature': candidature,
            }
            sujet_rendu   = rendre_template(modele.sujet_modele,  **contexte)
            corps_rendu   = rendre_template(modele.corps_message, **contexte)
            msg_cree = MessageModel.objects.create(
                candidat       = candidature.candidat,
                recruteur      = request.recruteur,
                candidature    = candidature,
                modele_message = modele,
                modele_utilise = modele.sujet_modele,
                sujet          = sujet_rendu,
                contenu        = corps_rendu,
                piece_jointe   = request.FILES.get('piece_jointe'),
            )
            message_envoye = True

        NotificationCandidat.objects.update_or_create(
            candidat = candidature.candidat,
            type     = NotificationCandidat.Type.CANDIDATURE,
            offre    = candidature.offre,
            defaults = {
                'titre':            titre_notif,
                'message':          f"Votre dossier pour {candidature.offre.titre}.",
                'lien':             f"{reverse('candidat:mes_candidatures')}?offre={candidature.offre_id}",
                'lue':              False,
                'messageRecruteur': msg_cree,
            },
        )

        offre_archivee = _archiver_si_offre_traitee(candidature.offre)

    action = 'acceptée' if code_cible == 'ACCEPTEE' else 'refusée'
    suffixe = " — Message envoyé au candidat." if message_envoye else ""
    if offre_archivee:
        suffixe += " L'offre a été archivée (toutes les candidatures traitées)."
    messages.success(
        request,
        f"Candidature {candidature.reference} de "
        f"{candidature.candidat.prenom} {candidature.candidat.nom} {action}.{suffixe}",
    )
    next_url = (request.POST.get('next_url') or '').strip()
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect('entreprise:candidatures')


@entreprise_required
@lecteur_bloque
@require_POST
def candidatures_offre_reinitialiser(request, offre_id):
    """Repasse en POSTULEE toutes les candidatures ACCEPTEE / REFUSEE d'une offre."""
    from django.db import transaction
    from candidat.models import Candidature, HistoriqueStatut, NotificationCandidat
    from referentiel.models import Statut

    offre = get_object_or_404(
        OffreEmploi, pk=offre_id, entreprise=request.entreprise,
    )
    rec = getattr(request, 'recruteur', None)
    if rec is not None and rec.roleMembre not in (RoleMembre.RH, RoleMembre.MANAGER, RoleMembre.ADMIN):
        messages.error(request, "Réservé aux RH et Managers.")
        return redirect('entreprise:candidatures_offre', offre_id=offre.id)

    statut_postulee = Statut.objects.filter(code='POSTULEE').first()
    if not statut_postulee:
        messages.error(request, "Statut 'POSTULEE' introuvable dans le référentiel.")
        return redirect('entreprise:candidatures_offre', offre_id=offre.id)

    cibles = list(
        Candidature.objects
        .filter(offre=offre, statut__code__in=['ACCEPTEE', 'REFUSEE'])
        .select_related('statut', 'candidat')
    )
    if not cibles:
        messages.info(request, "Aucune candidature à réinitialiser.")
        return redirect('entreprise:candidatures_offre', offre_id=offre.id)

    lien_filtre = f"{reverse('candidat:mes_candidatures')}?offre={offre.id}"
    nb_reset = 0
    with transaction.atomic():
        for cand in cibles:
            ancien_libelle = cand.statut.libelle
            HistoriqueStatut.creer(
                candidature = cand,
                nouveau     = statut_postulee,
                ancien      = cand.statut,
                commentaire = f'Réinitialisation globale (par {rec}).',
            )
            NotificationCandidat.objects.create(
                candidat = cand.candidat,
                type     = NotificationCandidat.Type.CANDIDATURE,
                titre    = f"🔄 Candidature réouverte — {offre.titre}",
                message  = f"Votre dossier est remis à l'étude (était : {ancien_libelle}).",
                lien     = lien_filtre,
                offre    = offre,
            )
            nb_reset += 1

        if offre.statutOffre == StatutOffre.POURVUE:
            aujourd_hui = timezone.now().date()
            if offre.dateExpiration and offre.dateExpiration < aujourd_hui:
                offre.statutOffre = StatutOffre.EXPIREE
            else:
                offre.statutOffre = StatutOffre.PUBLIEE
            offre.save(update_fields=['statutOffre'])

    messages.success(
        request,
        f"🔄 {nb_reset} candidature(s) réinitialisée(s) — toutes remises en attente.",
    )
    return redirect('entreprise:candidatures_offre', offre_id=offre.id)


@entreprise_required
@lecteur_bloque
@require_POST
def candidature_annuler_decision(request, candidature_id):
    """Reouvre une candidature ACCEPTEE / REFUSEE en la repassant en POSTULEE."""
    from candidat.models import Candidature, HistoriqueStatut, NotificationCandidat
    from referentiel.models import Statut

    candidature = get_object_or_404(
        Candidature.objects.select_related('offre__entreprise', 'statut', 'candidat'),
        pk=candidature_id,
        offre__in=_offres_visibles(request),
    )

    rec = getattr(request, 'recruteur', None)
    if rec is not None and rec.roleMembre not in (RoleMembre.RH, RoleMembre.MANAGER, RoleMembre.ADMIN):
        messages.error(request, "Réservé aux RH et Managers.")
        return redirect('entreprise:candidatures')

    if not candidature.statut or not candidature.statut.estFinal:
        messages.warning(request, "La candidature n'est pas dans un statut final, rien à annuler.")
        return redirect('entreprise:candidatures_offre', offre_id=candidature.offre_id)

    statut_postulee = Statut.objects.filter(code='POSTULEE').first()
    if not statut_postulee:
        messages.error(request, "Statut 'POSTULEE' introuvable dans le référentiel.")
        return redirect('entreprise:candidatures')

    ancien_libelle = candidature.statut.libelle
    offre = candidature.offre

    with transaction.atomic():
        HistoriqueStatut.creer(
            candidature = candidature,
            nouveau     = statut_postulee,
            ancien      = candidature.statut,
            commentaire = f'Décision annulée — retour en attente (par {rec}).',
        )

        if offre.statutOffre == StatutOffre.POURVUE:
            offre.statutOffre = StatutOffre.PUBLIEE
            offre.save(update_fields=['statutOffre'])

        NotificationCandidat.objects.create(
            candidat = candidature.candidat,
            type     = NotificationCandidat.Type.CANDIDATURE,
            titre    = f"🔄 Candidature réouverte — {offre.titre}",
            message  = f"Votre candidature a été remise à l'étude (était : {ancien_libelle}).",
            lien     = f"{reverse('candidat:mes_candidatures')}?offre={offre.id}",
            offre    = offre,
        )

    messages.success(
        request,
        f"Candidature {candidature.reference} réouverte (était {ancien_libelle}).",
    )
    return redirect('entreprise:candidatures_offre', offre_id=offre.id)


@entreprise_required
@lecteur_bloque
@require_POST
def candidatures_accepter_bulk(request, offre_id):
    """Accepte en lot plusieurs candidatures d'une offre."""
    from django.db import transaction
    from candidat.models import Candidature, HistoriqueStatut
    from referentiel.models import Statut
    from ..models import ModeleMessage, Message as MessageModel
    from ..messagerie import rendre_template

    offre = get_object_or_404(
        OffreEmploi, pk=offre_id, entreprise=request.entreprise,
    )

    rec = getattr(request, 'recruteur', None)
    if rec is not None and rec.roleMembre not in (RoleMembre.RH, RoleMembre.MANAGER, RoleMembre.ADMIN):
        return JsonResponse(
            {'erreur': "Réservé aux RH et Managers."},
            status=403,
        )

    raw_ids = request.POST.get('candidature_ids', '')
    ids: list[int] = []
    if raw_ids:
        try:
            parsed = json.loads(raw_ids)
            if isinstance(parsed, list):
                ids = [int(x) for x in parsed if str(x).isdigit()]
        except (ValueError, TypeError):
            pass
    if not ids:
        ids = [int(v) for v in request.POST.getlist('candidature_ids[]')
               if str(v).isdigit()]
    if not ids:
        return JsonResponse(
            {'erreur': "Aucun ID de candidature fourni."},
            status=400,
        )

    refuser_autres = (request.POST.get('refuser_autres') or '').lower() in (
        'true', '1', 'yes', 'on',
    )

    action = (request.POST.get('action') or 'ACCEPTER').upper()

    statut_accept = Statut.objects.filter(code='ACCEPTEE').first()
    statut_refus  = Statut.objects.filter(code='REFUSEE').first()
    if not statut_accept:
        return JsonResponse(
            {'erreur': "Statut 'ACCEPTEE' introuvable dans le référentiel."},
            status=500,
        )
    if refuser_autres and not statut_refus:
        return JsonResponse(
            {'erreur': "Statut 'REFUSEE' introuvable dans le référentiel."},
            status=500,
        )

    modele_accept = (
        ModeleMessage.objects
        .filter(entreprise=request.entreprise, est_actif=True,
                statut=statut_accept)
        .order_by('-date_modification')
        .first()
    )
    modele_refus = None
    if refuser_autres:
        modele_refus = (
            ModeleMessage.objects
            .filter(entreprise=request.entreprise, est_actif=True,
                    statut=statut_refus)
            .order_by('-date_modification')
            .first()
        )

    from candidat.models import NotificationCandidat
    lien_mes_cand_base = reverse('candidat:mes_candidatures')

    def _envoyer_notification(cand, modele, sujet_default, corps_default,
                              titre_notif, type_decision):
        contexte = {
            'candidat':    cand.candidat,
            'offre':       cand.offre,
            'entreprise':  request.entreprise,
            'recruteur':   rec,
            'candidature': cand,
        }
        if modele:
            sujet = rendre_template(modele.sujet_modele, **contexte)
            corps = rendre_template(modele.corps_message, **contexte)
            modele_label = modele.sujet_modele
        else:
            sujet = sujet_default.format(offre=cand.offre.titre)
            corps = corps_default.format(
                prenom=cand.candidat.prenom,
                offre=cand.offre.titre,
                entreprise=request.entreprise,
            )
            modele_label = '(générique automatique)'
        MessageModel.objects.create(
            candidat       = cand.candidat,
            recruteur      = rec,
            candidature    = cand,
            modele_message = modele,
            modele_utilise = modele_label,
            sujet          = sujet,
            contenu        = corps,
        )
        NotificationCandidat.objects.create(
            candidat = cand.candidat,
            type     = NotificationCandidat.Type.CANDIDATURE,
            titre    = titre_notif.format(offre=cand.offre.titre),
            message  = sujet,
            lien     = f"{lien_mes_cand_base}?offre={cand.offre_id}",
            offre    = cand.offre,
        )

    acceptees:      list[int] = []
    deja_accept:    list[int] = []
    refusees:       list[int] = []
    non_eligibles:  list[dict] = []
    erreurs:        list[dict] = []
    notif_envoyees = 0

    with transaction.atomic():
        statut_cible = statut_refus if action == 'REFUSER' else statut_accept
        modele_cible = modele_refus if action == 'REFUSER' else modele_accept

        candidatures = (
            Candidature.objects
            .filter(pk__in=ids, offre=offre)
            .select_related('statut', 'candidat')
        )
        trouvees_ids = set()
        for cand in candidatures:
            trouvees_ids.add(cand.id)
            try:
                if action == 'REFUSER' and cand.statut_id == statut_refus.id:
                    non_eligibles.append({'id': cand.id, 'raison': 'Déjà refusée'})
                    continue
                if action == 'ACCEPTER' and cand.statut_id == statut_accept.id:
                    deja_accept.append(cand.id)
                    continue
                if cand.statut and cand.statut.estFinal:
                    non_eligibles.append({
                        'id':     cand.id,
                        'raison': f"Déjà dans un statut final : {cand.statut.libelle}",
                    })
                    continue
                HistoriqueStatut.creer(
                    candidature = cand,
                    nouveau     = statut_cible,
                    ancien      = cand.statut,
                    commentaire = f'{"Refus" if action == "REFUSER" else "Acceptation"} en lot (par {rec}).',
                )
                if action == 'REFUSER':
                    refusees.append(cand.id)
                else:
                    acceptees.append(cand.id)
                if action == 'REFUSER':
                    _envoyer_notification(
                        cand, modele_cible,
                        sujet_default="Votre candidature pour « {offre} » n'a pas été retenue",
                        corps_default=(
                            "Bonjour {prenom},\n\n"
                            "Après examen de votre candidature pour le poste « {offre} », "
                            "nous n'avons pas retenu votre profil pour cette offre.\n\n"
                            "Nous vous remercions de l'intérêt porté à {entreprise} "
                            "et vous souhaitons bonne continuation.\n\n"
                            "Cordialement,\n{entreprise}"
                        ),
                        titre_notif="❌ Candidature non retenue — {offre}",
                        type_decision='REFUSEE',
                    )
                else:
                    _envoyer_notification(
                        cand, modele_cible,
                        sujet_default="Votre candidature pour « {offre} » a été acceptée",
                        corps_default=(
                            "Bonjour {prenom},\n\n"
                            "Nous avons le plaisir de vous informer que votre "
                            "candidature pour le poste « {offre} » a été acceptée "
                            "par {entreprise}.\n\n"
                            "Nous reviendrons rapidement vers vous concernant la suite "
                            "du processus de recrutement.\n\n"
                            "Cordialement,\n"
                            "{entreprise}"
                        ),
                        titre_notif="✅ Candidature acceptée — {offre}",
                        type_decision='ACCEPTEE',
                    )
                notif_envoyees += 1
            except Exception as exc:
                erreurs.append({'id': cand.id, 'raison': str(exc)})

        for missing in set(ids) - trouvees_ids:
            erreurs.append({'id': missing, 'raison': 'Candidature introuvable.'})

        if refuser_autres:
            autres = (
                Candidature.objects
                .filter(offre=offre)
                .exclude(pk__in=ids)
                .select_related('statut', 'candidat')
            )
            for cand in autres:
                try:
                    if cand.statut and cand.statut.estFinal:
                        continue
                    HistoriqueStatut.creer(
                        candidature = cand,
                        nouveau     = statut_refus,
                        ancien      = cand.statut,
                        commentaire = f'Refus automatique en lot (autres que Top IA) — par {rec}.',
                    )
                    refusees.append(cand.id)
                    _envoyer_notification(
                        cand, modele_refus,
                        sujet_default="Votre candidature pour « {offre} »",
                        corps_default=(
                            "Bonjour {prenom},\n\n"
                            "Nous vous remercions pour l'intérêt que vous avez "
                            "porté au poste « {offre} » chez {entreprise}.\n\n"
                            "Après analyse de votre dossier, nous ne pouvons pas "
                            "donner suite à votre candidature pour ce poste.\n\n"
                            "Nous vous souhaitons plein succès dans la poursuite "
                            "de vos démarches.\n\n"
                            "Cordialement,\n"
                            "{entreprise}"
                        ),
                        titre_notif="📋 Candidature non retenue — {offre}",
                        type_decision='REFUSEE',
                    )
                    notif_envoyees += 1
                except Exception as exc:
                    erreurs.append({'id': cand.id, 'raison': str(exc)})

    offre_archivee = _archiver_si_offre_traitee(offre)

    return JsonResponse({
        'acceptees':         acceptees,
        'deja_accept':       deja_accept,
        'refusees':          refusees,
        'non_eligibles':     non_eligibles,
        'erreurs':           erreurs,
        'total_traite':      len(acceptees) + len(deja_accept) + len(refusees),
        'notifications_envoyees': notif_envoyees,
        'offre_archivee':    offre_archivee,
    })
