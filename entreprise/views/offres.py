"""Job offers CRUD views and helpers."""
import logging
import json

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.db.models import Q, Count
from django.views.decorators.http import require_POST

from .. import app_messages as messages
from ..models import (
    Entreprise, Recruteur, OffreEmploi, OffreEmploiRecruteur,
    StatutOffre, TypeContrat, ModeTravail, ExperienceRequise,
    RoleMembre, DEVISES,
)
from referentiel.models import (
    Contrat as ContratRef,
    ModeTravail as ModeTravailRef,
    AnneesExperience,
    Devise as DeviseRef,
    TypeCompetence,
)
from ..decorators import entreprise_required, lecteur_bloque, bloque_roles
from candidat.models import Candidature
from ._helpers import (
    _REV_CONTRAT_LIBELLE_TO_CODE,
    _REV_MODE_LIBELLE_TO_CODE,
    _REV_EXPERIENCE_LIBELLE_TO_CODE,
    resoudre_contrat_et_mode_travail,
)

logger = logging.getLogger(__name__)


def _offre_context(request=None):
    """Contexte commun pour les formulaires offre."""
    ctx = {
        'types_contrat':        ContratRef.objects.all(),
        'modes_travail':        ModeTravailRef.objects.all(),
        'experiences':          AnneesExperience.objects.all(),
        'devises_ref':          DeviseRef.objects.all(),
        'niveaux_etude':        [],
        'devises':              DEVISES,
        'managers_disponibles': [],
    }
    if request:
        entreprise = getattr(request, 'entreprise', None)
        if entreprise:
            ctx['managers_disponibles'] = list(
                Recruteur.objects.filter(
                    entreprise=entreprise,
                    roleMembre=RoleMembre.MANAGER,
                    estActif=True,
                ).values('id', 'prenom', 'nom')
            )
    return ctx


def _resolve_offre_referentiels(data):
    """Resout les FK referentiels a partir des IDs envoyes par le formulaire."""
    out = {
        'contrat': None, 'modeTravailRef': None, 'anneesExperience': None, 'deviseRef': None,
        'legacy_typeContrat': '', 'legacy_modeTravail': '', 'legacy_experienceRequise': '',
        'legacy_devise': '',
    }

    contrat_id = (data.get('contratId') or '').strip()
    if contrat_id.isdigit():
        c = ContratRef.objects.filter(pk=int(contrat_id)).first()
        if c:
            out['contrat'] = c
            out['legacy_typeContrat'] = _REV_CONTRAT_LIBELLE_TO_CODE.get(c.libelle, '')

    mode_id = (data.get('modeTravailId') or '').strip()
    if mode_id.isdigit():
        m = ModeTravailRef.objects.filter(pk=int(mode_id)).first()
        if m:
            out['modeTravailRef'] = m
            out['legacy_modeTravail'] = _REV_MODE_LIBELLE_TO_CODE.get(m.libelle, '')

    exp_id = (data.get('experienceId') or '').strip()
    if exp_id.isdigit():
        e = AnneesExperience.objects.filter(pk=int(exp_id)).first()
        if e:
            out['anneesExperience'] = e
            out['legacy_experienceRequise'] = _REV_EXPERIENCE_LIBELLE_TO_CODE.get(e.libelle, '')

    devise_id = (data.get('deviseId') or '').strip()
    if devise_id.isdigit():
        d = DeviseRef.objects.filter(pk=int(devise_id)).first()
        if d:
            out['deviseRef'] = d
            out['legacy_devise'] = d.libelle

    return out


def _sync_competences_m2m(offre, libelles_competences):
    """Synchronise la M2M typesCompetence depuis la liste de libelles."""
    offre.typesCompetence.clear()
    for libelle in libelles_competences:
        libelle = (libelle or '').strip()
        if not libelle:
            continue
        tc, _ = TypeCompetence.objects.get_or_create(
            nomCompetence=libelle, defaults={'domaine': ''},
        )
        offre.typesCompetence.add(tc)


def _sync_compteur_offres(entreprise):
    entreprise.nombreOffresActives = entreprise.offres.filter(statutOffre=StatutOffre.PUBLIEE).count()
    entreprise.save(update_fields=['nombreOffresActives'])


def _offres_visibles(request):
    """Retourne le queryset des offres visibles pour l'utilisateur connecte."""
    qs = request.entreprise.offres.all()
    rec = getattr(request, 'recruteur', None)
    if rec and rec.roleMembre not in (RoleMembre.ADMIN, RoleMembre.LECTEUR):
        qs = qs.filter(
            Q(creePar=rec) | Q(recruteurs_createurs__recruteur=rec)
        ).distinct()
    return qs


def _peut_modifier_offre(request, offre):
    """Determine si l'utilisateur connecte peut modifier/supprimer/changer le statut."""
    rec = getattr(request, 'recruteur', None)
    if rec is not None:
        if rec.roleMembre == 'LECTEUR':
            return False
        return offre.creePar_id == rec.pk
    return offre.creePar_id is None


def _parse_offre_post(data):
    """Parse et nettoie les donnees POST d'un formulaire offre."""
    competences = []
    try:
        competences = json.loads(data.get('competencesRequises', '[]'))
    except (ValueError, TypeError):
        pass

    criteres = {
        'cvObligatoire':                  data.get('cvObligatoire') == '1',
        'lettreMotivationnObligatoire':   data.get('lettreMotivationnObligatoire') == '1',
        'testRequis':                     data.get('testRequis') == '1',
    }
    try:
        criteres['scoreMinimum'] = int(data.get('scoreMinimum', 0))
    except (ValueError, TypeError):
        criteres['scoreMinimum'] = 0

    sal_min = sal_max = None
    try:
        v = data.get('salaireMin', '').strip()
        if v:
            sal_min = float(v.replace(' ', '').replace(',', '.'))
    except ValueError:
        pass
    try:
        v = data.get('salaireMax', '').strip()
        if v:
            sal_max = float(v.replace(' ', '').replace(',', '.'))
    except ValueError:
        pass

    return competences, criteres, sal_min, sal_max


# ── Liste ─────────────────────────────────────────────────────────────────────

@entreprise_required
def offres_liste(request):
    qs = _offres_visibles(request)

    statut        = request.GET.get('statut', 'PUBLIEE')
    type_contrat  = request.GET.get('typeContrat', '')
    mode_travail  = request.GET.get('modeTravail', '')
    q             = request.GET.get('q', '').strip()
    recruteur_id  = request.GET.get('recruteur', '').strip()

    rec_connecte = getattr(request, 'recruteur', None)
    est_admin    = rec_connecte is None or rec_connecte.roleMembre in (RoleMembre.ADMIN, RoleMembre.LECTEUR)

    if statut:       qs = qs.filter(statutOffre=statut)
    if type_contrat: qs = qs.filter(typeContrat=type_contrat)
    if mode_travail: qs = qs.filter(modeTravail=mode_travail)
    if q:
        from recrutement.search import fts_filter
        qs = fts_filter(qs, q,
                        vector_fields=['titre', 'missions', 'profilRecherche'],
                        fallback_lookups=['titre__icontains'])

    if est_admin and recruteur_id:
        if recruteur_id == 'aucun':
            qs = qs.filter(creePar__isnull=True)
        else:
            qs = qs.filter(creePar_id=recruteur_id)

    # Verifier expirations automatiquement — bulk (une seule requête UPDATE +
    # recruteurs_createurs préchargés) au lieu d'un `.verifierExpiration()`
    # par offre, qui fait un save() et une requête de notification séparés
    # à chaque offre venant d'expirer.
    a_expirer = list(
        qs.filter(statutOffre=StatutOffre.PUBLIEE, dateExpiration__lt=timezone.now().date())
        .prefetch_related('recruteurs_createurs')
    )
    if a_expirer:
        OffreEmploi.objects.filter(pk__in=[o.pk for o in a_expirer]).update(statutOffre=StatutOffre.EXPIREE)
        for offre in a_expirer:
            offre.statutOffre = StatutOffre.EXPIREE
            offre._notifier_expiration()

    offres_annotees = list(qs)
    for o in offres_annotees:
        o.peut_modifier = _peut_modifier_offre(request, o)

    all_offres = _offres_visibles(request)
    stats = {
        'total':      all_offres.count(),
        'publiees':   all_offres.filter(statutOffre=StatutOffre.PUBLIEE).count(),
        'brouillons': all_offres.filter(statutOffre=StatutOffre.BROUILLON).count(),
        'expirees':   all_offres.filter(statutOffre=StatutOffre.EXPIREE).count(),
        'pourvues':   all_offres.filter(statutOffre=StatutOffre.POURVUE).count(),
        'fermees':    all_offres.filter(statutOffre=StatutOffre.FERMEE).count(),
    }

    recruteurs_liste = []
    if est_admin:
        recruteurs_liste = (
            request.entreprise.recruteurs
            .filter(offres_creees__isnull=False)
            .distinct()
            .order_by('nomComplet')
        )

    return render(request, 'entreprise/offres/liste.html', {
        'offres':            offres_annotees,
        'stats':             stats,
        'filtres':           {
            'statut': statut, 'typeContrat': type_contrat,
            'modeTravail': mode_travail, 'q': q,
            'recruteur': recruteur_id,
        },
        'statuts':           StatutOffre.choices,
        'types_contrat':     TypeContrat.choices,
        'modes_travail':     ModeTravail.choices,
        'est_admin':         est_admin,
        'recruteurs_liste':  recruteurs_liste,
    })


# ── Creer ─────────────────────────────────────────────────────────────────────

@entreprise_required
@bloque_roles('LECTEUR', 'MANAGER')
def offre_creer(request):
    if request.method == 'POST':
        data   = request.POST
        errors = {}

        titre = data.get('titre', '').strip()
        ref   = _resolve_offre_referentiels(data)

        if not titre:
            errors['titre'] = 'Le titre du poste est obligatoire.'
        if not ref['contrat']:
            errors['typeContrat'] = 'Le type de contrat est obligatoire.'

        if errors:
            return render(request, 'entreprise/offres/creer.html', {
                'errors': errors, 'data': data, **_offre_context(request),
            })

        competences, criteres, sal_min, sal_max = _parse_offre_post(data)

        offre = OffreEmploi(
            entreprise          = request.entreprise,
            creePar             = getattr(request, 'recruteur', None),
            titre               = titre,
            contrat             = ref['contrat'],
            modeTravailRef      = ref['modeTravailRef'],
            anneesExperience    = ref['anneesExperience'],
            deviseRef           = ref['deviseRef'],
            typeContrat         = ref['legacy_typeContrat'],
            modeTravail         = ref['legacy_modeTravail'] or ModeTravail.PRESENTIEL,
            experienceRequise   = ref['legacy_experienceRequise'],
            devise              = (ref['legacy_devise'] or data.get('devise', 'FCFA').strip() or 'FCFA'),
            localisation        = data.get('localisation', '').strip(),
            ville               = data.get('ville', '').strip(),
            pays                = data.get('pays', "Côte d'Ivoire").strip() or "Côte d'Ivoire",
            missions            = data.get('missions', '').strip(),
            profilRecherche     = data.get('profilRecherche', '').strip(),
            competencesRequises = competences,
            niveauEtudeRequis   = data.get('niveauEtudeRequis', ''),
            salaireMin          = sal_min,
            salaireMax          = sal_max,
            criteresATS         = criteres,
        )

        date_exp = data.get('dateExpiration', '').strip()
        if date_exp:
            offre.dateExpiration = date_exp

        offre.save()
        from recrutement.background import lancer_en_arriere_plan
        from ..tasks import calculer_embedding_offre
        lancer_en_arriere_plan(calculer_embedding_offre, offre.id)

        _sync_competences_m2m(offre, competences)

        if offre.creePar_id:
            OffreEmploiRecruteur.objects.get_or_create(offre=offre, recruteur=offre.creePar)

        manager_ids = data.getlist('managers_assignes')
        if manager_ids:
            managers = Recruteur.objects.filter(
                pk__in=manager_ids,
                entreprise=request.entreprise,
                roleMembre=RoleMembre.MANAGER,
                estActif=True,
            )
            for manager in managers:
                OffreEmploiRecruteur.objects.get_or_create(offre=offre, recruteur=manager)

        if data.get('publierImmediatement') == '1':
            offre.publier()
            _sync_compteur_offres(request.entreprise)
            messages.success(request, f'L\'offre "{offre.titre}" a été publiée avec succès ! 🎉')
        else:
            messages.success(request, f'L\'offre "{offre.titre}" a été enregistrée en brouillon.')

        return redirect('entreprise:offre_detail', pk=offre.pk)

    return render(request, 'entreprise/offres/creer.html', _offre_context(request))


# ── Detail ────────────────────────────────────────────────────────────────────

@entreprise_required
def offre_detail(request, pk):
    offre = get_object_or_404(_offres_visibles(request), pk=pk)
    offre.verifierExpiration()
    return render(request, 'entreprise/offres/detail.html', {
        'offre': offre,
        'peut_modifier': _peut_modifier_offre(request, offre),
    })


# ── Modifier ──────────────────────────────────────────────────────────────────

@entreprise_required
@lecteur_bloque
def offre_modifier(request, pk):
    offre = get_object_or_404(_offres_visibles(request), pk=pk)

    if not _peut_modifier_offre(request, offre):
        messages.error(request,
            "Vous ne pouvez modifier que les offres que vous avez créées.")
        return redirect('entreprise:offre_detail', pk=offre.pk)

    if request.method == 'POST':
        data   = request.POST
        errors = {}

        titre = data.get('titre', '').strip()
        ref   = _resolve_offre_referentiels(data)

        if not titre:
            errors['titre'] = 'Le titre du poste est obligatoire.'
        if not ref['contrat']:
            errors['typeContrat'] = 'Le type de contrat est obligatoire.'

        if errors:
            return render(request, 'entreprise/offres/modifier.html', {
                'errors': errors, 'data': data, 'offre': offre, **_offre_context(request),
            })

        competences, criteres, sal_min, sal_max = _parse_offre_post(data)

        offre.titre               = titre
        offre.contrat             = ref['contrat']
        offre.modeTravailRef      = ref['modeTravailRef']
        offre.anneesExperience    = ref['anneesExperience']
        offre.deviseRef           = ref['deviseRef']
        offre.typeContrat         = ref['legacy_typeContrat']
        offre.modeTravail         = ref['legacy_modeTravail'] or offre.modeTravail
        offre.experienceRequise   = ref['legacy_experienceRequise']
        offre.devise              = ref['legacy_devise'] or (data.get('devise', 'FCFA').strip() or 'FCFA')
        offre.localisation        = data.get('localisation', '').strip()
        offre.ville               = data.get('ville', '').strip()
        offre.pays                = data.get('pays', "Côte d'Ivoire").strip() or "Côte d'Ivoire"
        offre.missions            = data.get('missions', '').strip()
        offre.profilRecherche     = data.get('profilRecherche', '').strip()
        offre.competencesRequises = competences
        offre.niveauEtudeRequis   = data.get('niveauEtudeRequis', '')
        offre.salaireMin          = sal_min
        offre.salaireMax          = sal_max
        offre.criteresATS         = criteres

        date_exp = data.get('dateExpiration', '').strip()
        offre.dateExpiration = date_exp or None

        offre.save()
        from recrutement.background import lancer_en_arriere_plan
        from ..tasks import calculer_embedding_offre
        lancer_en_arriere_plan(calculer_embedding_offre, offre.id)

        _sync_competences_m2m(offre, competences)
        if offre.creePar_id:
            OffreEmploiRecruteur.objects.get_or_create(offre=offre, recruteur=offre.creePar)

        manager_ids = data.getlist('managers_assignes')
        anciens_ids = set(
            OffreEmploiRecruteur.objects.filter(
                offre=offre, recruteur__roleMembre=RoleMembre.MANAGER
            ).values_list('recruteur_id', flat=True)
        )
        OffreEmploiRecruteur.objects.filter(
            offre=offre, recruteur__roleMembre=RoleMembre.MANAGER
        ).delete()
        nouveaux_managers = []
        if manager_ids:
            managers = Recruteur.objects.filter(
                pk__in=manager_ids,
                entreprise=request.entreprise,
                roleMembre=RoleMembre.MANAGER,
                estActif=True,
            )
            for manager in managers:
                OffreEmploiRecruteur.objects.get_or_create(offre=offre, recruteur=manager)
                if manager.pk not in anciens_ids:
                    nouveaux_managers.append(manager)

        if nouveaux_managers and offre.statutOffre == StatutOffre.PUBLIEE:
            from ..notifications_service import lancer_scan_offre_async
            lancer_scan_offre_async(offre)

        if data.get('publierImmediatement') == '1' and offre.statutOffre == StatutOffre.BROUILLON:
            offre.publier()
            _sync_compteur_offres(request.entreprise)
            messages.success(request, f'Offre mise à jour et publiée avec succès ! 🎉')
        else:
            messages.success(request, f'L\'offre "{offre.titre}" a été mise à jour.')

        return redirect('entreprise:offre_detail', pk=offre.pk)

    managers_assignes_ids = list(
        OffreEmploiRecruteur.objects.filter(
            offre=offre, recruteur__roleMembre=RoleMembre.MANAGER
        ).values_list('recruteur_id', flat=True)
    )
    # Offres creees avant l'ajout des FK referentiels (contrat/modeTravailRef) :
    # ces champs sont None mais le legacy CharField (typeContrat/modeTravail)
    # est renseigne. Sans ce fallback, le picker Alpine du formulaire
    # d'edition demarre vide alors que l'offre a bien un contrat/mode connu.
    contrat_edition, mode_travail_edition = resoudre_contrat_et_mode_travail(offre)

    return render(request, 'entreprise/offres/modifier.html', {
        'offre':                offre,
        'contrat_edition':      contrat_edition,
        'mode_travail_edition': mode_travail_edition,
        'managers_assignes_ids': managers_assignes_ids,
        **_offre_context(request),
    })


# ── Changer le statut ─────────────────────────────────────────────────────────

@entreprise_required
@lecteur_bloque
@require_POST
def offre_changer_statut(request, pk):
    offre  = get_object_or_404(_offres_visibles(request), pk=pk)

    if not _peut_modifier_offre(request, offre):
        messages.error(request,
            "Seul le créateur de l'offre peut changer son statut.")
        return redirect('entreprise:offre_detail', pk=pk)

    action = request.POST.get('action', '')

    if action == 'publier' and offre.statutOffre == StatutOffre.BROUILLON:
        offre.publier()
        messages.success(request, f'L\'offre "{offre.titre}" est maintenant publiée ! 🎉')
    elif action == 'fermer' and offre.statutOffre == StatutOffre.PUBLIEE:
        offre.fermer()
        messages.info(request, f'L\'offre "{offre.titre}" a été fermée.')
    elif action == 'pourvue':
        offre.marquerPourvue()
        messages.success(request, f'L\'offre "{offre.titre}" est marquée comme pourvue. 🏆')
    elif action == 'brouillon':
        offre.remettreEnBrouillon()
        messages.info(request, f'L\'offre "{offre.titre}" repassée en brouillon.')

    _sync_compteur_offres(request.entreprise)
    return redirect('entreprise:offre_detail', pk=pk)


# ── Supprimer ─────────────────────────────────────────────────────────────────

@entreprise_required
@lecteur_bloque
@require_POST
def offre_supprimer(request, pk):
    offre = get_object_or_404(_offres_visibles(request), pk=pk)

    if not _peut_modifier_offre(request, offre):
        messages.error(request,
            "Seul le créateur de l'offre peut la supprimer.")
        return redirect('entreprise:offre_detail', pk=offre.pk)

    titre = offre.titre
    offre.delete()
    _sync_compteur_offres(request.entreprise)
    messages.success(request, f'L\'offre "{titre}" a été supprimée.')
    return redirect('entreprise:offres_liste')


# ─── Historique des offres (expirees / fermees / pourvues) ───────────────────

@entreprise_required
def offres_historique(request):
    """Historique des offres : offres expirees, pourvues ou fermees."""
    import json as _json

    aujourd_hui = timezone.now().date()

    ids_a_expirer = list(
        request.entreprise.offres
        .filter(statutOffre=StatutOffre.PUBLIEE, dateExpiration__lt=aujourd_hui)
        .values_list('pk', flat=True)
    )
    if ids_a_expirer:
        OffreEmploi.objects.filter(pk__in=ids_a_expirer).update(statutOffre=StatutOffre.EXPIREE)
        for offre_exp in OffreEmploi.objects.filter(pk__in=ids_a_expirer).select_related('creePar').prefetch_related('recruteurs_createurs__recruteur'):
            offre_exp._notifier_expiration()

    from django.db.models import Prefetch
    qs = (
        _offres_visibles(request)
        .filter(
            Q(statutOffre__in=[StatutOffre.EXPIREE, StatutOffre.POURVUE, StatutOffre.FERMEE])
            | Q(dateExpiration__lt=aujourd_hui)
        )
        .annotate(nb_cand=Count('candidatures'))
        .order_by('-dateExpiration', '-dateCreation')
    )

    total           = qs.count()
    nb_expirees     = qs.filter(statutOffre=StatutOffre.EXPIREE).count()
    nb_pourvues     = qs.filter(statutOffre=StatutOffre.POURVUE).count()
    nb_fermees      = qs.filter(statutOffre=StatutOffre.FERMEE).count()

    offres_data = [
        {
            'id':                o.pk,
            'titre':             o.titre,
            'reference':         o.reference or '',
            'ville':             o.ville or '',
            'type_contrat_code': o.typeContrat,
            'type_contrat':      o.get_typeContrat_display(),
            'statut_code':       o.statutOffre,
            'statut_libelle':    o.get_statutOffre_display(),
            'nb_candidatures':   o.nb_cand,
            'date_creation':     o.dateCreation.isoformat(),
            'date_expiration':   o.dateExpiration.isoformat() if o.dateExpiration else '',
            'url':               reverse('entreprise:offre_detail', kwargs={'pk': o.pk}),
            'url_candidatures':  reverse('entreprise:candidatures_offre', kwargs={'offre_id': o.pk}),
        }
        for o in qs
    ]
    offres_json = _json.dumps(offres_data)

    seen = set()
    types_contrat = []
    for o in offres_data:
        code = o['type_contrat_code']
        if code and code not in seen:
            seen.add(code)
            types_contrat.append({'code': code, 'libelle': o['type_contrat']})
    types_contrat.sort(key=lambda x: x['libelle'])
    types_contrat_json = _json.dumps(types_contrat)

    return render(request, 'entreprise/offres/historique.html', {
        'offres_json':        offres_json,
        'types_contrat_json': types_contrat_json,
        'total':              total,
        'nb_expirees':        nb_expirees,
        'nb_pourvues':        nb_pourvues,
        'nb_fermees':         nb_fermees,
    })


# ─── Helpers used by candidatures ─────────────────────────────────────────────

def _archiver_si_offre_traitee(offre) -> bool:
    """Si toutes les candidatures de l'offre sont en statut final, archive l'offre."""
    from candidat.models import Candidature
    if offre.statutOffre in (StatutOffre.POURVUE, StatutOffre.FERMEE):
        return False
    restantes = (
        Candidature.objects
        .filter(offre=offre)
        .exclude(statut__estFinal=True)
        .exists()
    )
    if restantes:
        return False
    if offre.statutOffre == StatutOffre.PUBLIEE:
        offre.statutOffre = StatutOffre.POURVUE
        offre.save(update_fields=['statutOffre'])
    return True


def _rattraper_offres_expirees(entreprise):
    """Passe en EXPIREE toutes les offres PUBLIEE dont la date est depassee."""
    from candidat.models import Candidature
    aujourd_hui = timezone.now().date()

    a_expirer = list(
        entreprise.offres
        .filter(statutOffre=StatutOffre.PUBLIEE, dateExpiration__lt=aujourd_hui)
    )
    if not a_expirer:
        return []

    OffreEmploi.objects.filter(pk__in=[o.pk for o in a_expirer]) \
        .update(statutOffre=StatutOffre.EXPIREE)

    a_traiter = []
    for o in a_expirer:
        nb_pending = Candidature.objects.filter(
            offre=o,
        ).exclude(statut__estFinal=True).count()
        if nb_pending > 0:
            o.statutOffre = StatutOffre.EXPIREE
            o._nb_pending = nb_pending
            a_traiter.append(o)
    return a_traiter
