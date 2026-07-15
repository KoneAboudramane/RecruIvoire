"""Staff admin views — verification dashboard, ML status & scheduling."""
import io
import json
import logging
from datetime import timedelta
from urllib.parse import urlparse

from django.contrib import admin as _django_admin
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Exists, OuterRef, Prefetch
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .. import app_messages as messages
from ..models import (
    Entreprise, Recruteur, OffreEmploi,
    StatutOffre, StatutCompte,
    StatutVerification, DemandeVerification, StatutDemande,
    NotificationRecruteur,
)
from candidat.models import Candidature, Entretien, LogoSite

logger = logging.getLogger(__name__)

__all__ = [
    '_admin_context',
    'admin_tableau_bord',
    'admin_verifier_email',
    'admin_verifications_liste',
    'admin_verification_detail',
    'admin_ml_status',
    'admin_ml_dashboard',
    'admin_ml_planification_enregistrer',
    'admin_ml_planification_supprimer',
    'admin_ml_reentrainer',
    'admin_kyc_document',
]


@staff_member_required
def admin_kyc_document(request, demande_pk, doc_type):
    demande = get_object_or_404(DemandeVerification, pk=demande_pk)
    field = demande.document_rccm if doc_type == 'rccm' else demande.document_identite
    if not field:
        raise Http404
    return redirect(field.url)


# ── Panneau admin — révision des vérifications (intégré dans /admin/) ──────────


def _admin_context(request):
    return _django_admin.site.each_context(request)


@staff_member_required
def admin_tableau_bord(request):
    from django.conf import settings

    filtre = request.GET.get('filtre', 'tous')
    q      = request.GET.get('q', '').strip()

    qs = Entreprise.objects.all()
    if filtre == 'email_non_verifie':
        qs = qs.filter(emailVerifie=False)
    elif filtre == 'compte_non_verifie':
        qs = qs.filter(statutVerification__in=[StatutVerification.EN_ATTENTE, StatutVerification.REJETE])
    elif filtre == 'non_verifies':
        qs = qs.exclude(emailVerifie=True, statutVerification=StatutVerification.VERIFIE)
    elif filtre == 'verifies':
        qs = qs.filter(emailVerifie=True, statutVerification=StatutVerification.VERIFIE)
    if q:
        from recrutement.search import fts_filter
        qs = fts_filter(qs, q,
                        vector_fields=['raisonSocial', 'description'],
                        fallback_lookups=['raisonSocial__icontains',
                                         'emailProfessionnel__icontains'])

    qs = qs.annotate(
        has_pending=Exists(
            DemandeVerification.objects.filter(entreprise=OuterRef('pk'), statut=StatutDemande.EN_ATTENTE)
        )
    ).prefetch_related(
        Prefetch(
            'demandes_verification',
            queryset=DemandeVerification.objects.filter(statut=StatutDemande.EN_ATTENTE).order_by('-date_soumission'),
            to_attr='pending_demandes',
        )
    ).order_by('-dateCreationCompte')

    demandes_urgentes = (
        DemandeVerification.objects
        .filter(statut=StatutDemande.EN_ATTENTE)
        .select_related('entreprise')
        .order_by('date_soumission')
    )
    pending_count = demandes_urgentes.count()
    total = Entreprise.objects.count()

    stats = {
        'total':            total,
        'emails_verifies':  Entreprise.objects.filter(emailVerifie=True).count(),
        'comptes_verifies': Entreprise.objects.filter(statutVerification=StatutVerification.VERIFIE).count(),
        'en_attente':       pending_count,
        'nouvelles_7j':     DemandeVerification.objects.filter(
            date_soumission__gte=timezone.now() - timedelta(days=7),
            statut=StatutDemande.EN_ATTENTE,
        ).count(),
    }
    return render(request, 'entreprise/admin/tableau_bord.html', {
        **_admin_context(request),
        'title':             'Vérifications — Tableau de bord',
        'entreprises':       qs,
        'demandes_urgentes': demandes_urgentes,
        'stats':             stats,
        'filtre':            filtre,
        'q':                 q,
        'pending_count':     pending_count,
        'now':               timezone.now(),
    })


@staff_member_required
@require_POST
def admin_verifier_email(request, pk):
    ent = get_object_or_404(Entreprise, pk=pk)
    if not ent.emailVerifie:
        ent.emailVerifie = True
        ent.save(update_fields=['emailVerifie'])
        ent.calculerScorePertinence()
        messages.success(request, f'✅ Email de « {ent.raisonSocial} » validé manuellement.')
    else:
        messages.info(request, f'L\'email de {ent.raisonSocial} est déjà vérifié.')
    next_url = request.POST.get('next', '')
    if next_url and urlparse(next_url).netloc == '':
        return redirect(next_url)
    return redirect('admin:entreprise_demandeverification_dashboard')


@staff_member_required
def admin_verifications_liste(request):
    en_attente = (
        DemandeVerification.objects
        .filter(statut=StatutDemande.EN_ATTENTE)
        .select_related('entreprise')
        .order_by('date_soumission')
    )
    traitees = (
        DemandeVerification.objects
        .exclude(statut=StatutDemande.EN_ATTENTE)
        .select_related('entreprise', 'traite_par')
        .order_by('-date_traitement')[:30]
    )
    stats = {
        'en_attente':  DemandeVerification.objects.filter(statut=StatutDemande.EN_ATTENTE).count(),
        'approuvees':  DemandeVerification.objects.filter(statut=StatutDemande.APPROUVEE).count(),
        'rejetees':    DemandeVerification.objects.filter(statut=StatutDemande.REJETEE).count(),
    }
    return render(request, 'entreprise/admin/verifications_liste.html', {
        **_admin_context(request),
        'title':         'Demandes de vérification',
        'en_attente':    en_attente,
        'traitees':      traitees,
        'stats':         stats,
        'pending_count': stats['en_attente'],
    })


@staff_member_required
def admin_verification_detail(request, pk):
    demande = get_object_or_404(
        DemandeVerification.objects.select_related('entreprise', 'traite_par'),
        pk=pk,
    )

    if request.method == 'POST' and demande.statut == StatutDemande.EN_ATTENTE:
        action      = request.POST.get('action', '')
        notes_admin = request.POST.get('notes_admin', '').strip()

        if action == 'approuver':
            demande.statut          = StatutDemande.APPROUVEE
            demande.notes_admin     = notes_admin
            demande.date_traitement = timezone.now()
            demande.traite_par      = request.user
            demande.save()
            demande.entreprise.statutVerification = StatutVerification.VERIFIE
            demande.entreprise.save(update_fields=['statutVerification'])
            messages.success(request,
                f'✅ Compte de « {demande.entreprise.raisonSocial} » vérifié avec succès.')
            return redirect('admin:entreprise_demandeverification_liste_traitement')

        elif action == 'rejeter':
            if not notes_admin:
                messages.error(request, 'Le motif de rejet est obligatoire.')
            else:
                demande.statut          = StatutDemande.REJETEE
                demande.notes_admin     = notes_admin
                demande.date_traitement = timezone.now()
                demande.traite_par      = request.user
                demande.save()
                demande.entreprise.statutVerification = StatutVerification.REJETE
                demande.entreprise.save(update_fields=['statutVerification'])
                messages.warning(request,
                    f'❌ Demande de « {demande.entreprise.raisonSocial} » rejetée.')
                return redirect('admin:entreprise_demandeverification_liste_traitement')

    historique = (
        DemandeVerification.objects
        .filter(entreprise=demande.entreprise)
        .exclude(pk=demande.pk)
        .order_by('-date_soumission')
    )
    pending_count = DemandeVerification.objects.filter(statut=StatutDemande.EN_ATTENTE).count()
    return render(request, 'entreprise/admin/verification_detail.html', {
        **_admin_context(request),
        'title':         f'Révision — {demande.entreprise.raisonSocial}',
        'demande':       demande,
        'historique':    historique,
        'pending_count': pending_count,
    })


# ── Panneau admin — état des modèles ML (matching + ATS) ──────────────────────

@staff_member_required
def admin_ml_status(request):
    """Affiche les métadonnées des deux modèles ML + bouton de ré-entraînement."""
    from candidat import matching_ml
    from entreprise import ats_ml
    from candidat.models import Candidature
    from entreprise.models import PropositionProfil

    def _info(metadata: dict, nb_exemples_dispo: int) -> dict:
        entraine = bool(metadata)
        imps = metadata.get('importances', {}) if entraine else {}
        # Trie les features par importance décroissante (top 5)
        top_features = sorted(imps.items(), key=lambda kv: kv[1], reverse=True)[:5]
        # Normalisation pour la barre de progression (la plus grande = 100%)
        max_imp = max((v for _, v in top_features), default=1) or 1
        top_features = [
            {'nom': nom, 'imp': imp, 'pct': round(imp / max_imp * 100, 1)}
            for nom, imp in top_features
        ]
        return {
            'entraine':           entraine,
            'date_entrainement':  metadata.get('date_entrainement') if entraine else None,
            'nb_exemples':        metadata.get('nb_exemples', 0) if entraine else 0,
            'metriques':          metadata.get('metriques', {}) if entraine else {},
            'feature_names':      metadata.get('feature_names', []) if entraine else [],
            'top_features':       top_features,
            'version':            metadata.get('version', '—') if entraine else '—',
            'nb_exemples_dispo':  nb_exemples_dispo,
        }

    # Compte les exemples actuellement labellisables (sans relancer l'entraînement)
    try:
        from candidat.ml_features import label_pour_statut
        nb_candidatures_lab = sum(
            1 for c in Candidature.objects.select_related('statut').only('statut__code')
            if c.statut and label_pour_statut(c.statut.code) is not None
        )
    except Exception:
        nb_candidatures_lab = Candidature.objects.count()

    nb_propositions_lab = PropositionProfil.objects.exclude(action='').count()

    matching_info = _info(matching_ml.metadata(), nb_candidatures_lab)
    ats_info      = _info(ats_ml.metadata(),      nb_propositions_lab)

    # ── Planification ─────────────────────────────────────────────────────
    from ..models import PlanificationML, FrequencePlanif, ModePlanif
    from .. import ml_scheduler

    planif = PlanificationML.singleton()
    planif_statut    = ml_scheduler.statut(planif) if planif.active else {'present': False}
    adapters_dispo   = ml_scheduler.adapters_disponibles()

    jours_semaine = [
        (0, 'Lundi'), (1, 'Mardi'), (2, 'Mercredi'), (3, 'Jeudi'),
        (4, 'Vendredi'), (5, 'Samedi'), (6, 'Dimanche'),
    ]

    return render(request, 'entreprise/admin/ml_status.html', {
        **_admin_context(request),
        'title':         'Modèles ML — Matching & ATS',
        'matching':      matching_info,
        'ats':           ats_info,
        'planif':        planif,
        'planif_statut': planif_statut,
        'adapters':      adapters_dispo,
        'jours_semaine': jours_semaine,
        'frequences':    FrequencePlanif.choices,
        'modes':         ModePlanif.choices,
        'pending_count': DemandeVerification.objects.filter(statut=StatutDemande.EN_ATTENTE).count(),
    })


@staff_member_required
def admin_ml_dashboard(request):
    """Dashboard ML global : historique d'évolution des modèles + charts."""
    from pathlib import Path
    from collections import Counter
    from django.conf import settings
    from candidat.models import Candidature
    from candidat.ml_features import LABELS_PAR_STATUT
    from ..models import PropositionProfil

    try:
        import joblib
    except ImportError:
        joblib = None

    ml_dir = Path(settings.MEDIA_ROOT) / 'ml_models'

    def _charger_snapshots(prefix: str) -> list:
        """Charge les metadata de tous les snapshots datés (pas le 'current').
        Renvoie une liste triée par date d'entraînement croissante."""
        if not joblib or not ml_dir.exists():
            return []
        snapshots = []
        for f in ml_dir.glob(f'{prefix}_*.joblib'):
            if f.name.endswith('current.joblib'):
                continue
            try:
                payload = joblib.load(f)
                md = payload.get('metadata', {})
                snapshots.append({
                    'fichier':  f.name,
                    'date':     md.get('date_entrainement', ''),
                    'nb':       md.get('nb_exemples', 0),
                    'mae':      md.get('metriques', {}).get('mae', 0),
                    'rmse':     md.get('metriques', {}).get('rmse', 0),
                    'r2':       md.get('metriques', {}).get('r2', 0),
                })
            except Exception:
                continue
        snapshots.sort(key=lambda s: s['date'])
        return snapshots

    matching_snaps = _charger_snapshots('matching')
    ats_snaps      = _charger_snapshots('ats')

    # ── Distribution des labels (datasets actuels) ────────────────────────
    # Matching : par statut Candidature
    dist_matching = Counter()
    for cand in Candidature.objects.select_related('statut').only('statut__code'):
        if cand.statut and cand.statut.code in LABELS_PAR_STATUT:
            dist_matching[cand.statut.code] += 1
    # ordre fixe pour affichage cohérent
    ordre_matching = ['EMBAUCHEE', 'ACCEPTEE', 'ENTRETIEN', 'TEST',
                      'PRESELECTIONNEE', 'VUE', 'REFUSEE']
    dist_matching_data = [(code, dist_matching.get(code, 0)) for code in ordre_matching
                          if dist_matching.get(code, 0) > 0]

    # ATS : par action
    dist_ats = Counter(
        PropositionProfil.objects.exclude(action='').values_list('action', flat=True)
    )
    ordre_ats = ['invite', 'contacte', 'vu', 'propose', 'ignore']
    dist_ats_data = [(a, dist_ats.get(a, 0)) for a in ordre_ats if dist_ats.get(a, 0) > 0]

    # ── Top features actuels ──────────────────────────────────────────────
    def _top_features(prefix: str, n: int = 8) -> list:
        path = ml_dir / f'{prefix}_current.joblib'
        if not joblib or not path.exists():
            return []
        try:
            payload = joblib.load(path)
            imps = payload.get('metadata', {}).get('importances', {})
            return sorted(imps.items(), key=lambda kv: -kv[1])[:n]
        except Exception:
            return []

    top_matching = _top_features('matching')
    top_ats      = _top_features('ats')

    # ── Métadonnées actuelles ─────────────────────────────────────────────
    from candidat import matching_ml
    from entreprise import ats_ml

    matching_meta = matching_ml.metadata()
    ats_meta      = ats_ml.metadata()

    return render(request, 'entreprise/admin/ml_dashboard.html', {
        **_admin_context(request),
        'title':         'Dashboard ML — Évolution des modèles',
        'matching_meta': matching_meta,
        'ats_meta':      ats_meta,
        'matching_snaps_json': json.dumps(matching_snaps, default=str),
        'ats_snaps_json':      json.dumps(ats_snaps, default=str),
        'dist_matching_json':  json.dumps(dist_matching_data),
        'dist_ats_json':       json.dumps(dist_ats_data),
        'top_matching_json':   json.dumps(top_matching),
        'top_ats_json':        json.dumps(top_ats),
        'nb_snaps_matching':   len(matching_snaps),
        'nb_snaps_ats':        len(ats_snaps),
        'pending_count':       DemandeVerification.objects.filter(statut=StatutDemande.EN_ATTENTE).count(),
    })


@staff_member_required
@require_POST
def admin_ml_planification_enregistrer(request):
    """Enregistre la configuration de planification + l'applique au système."""
    from ..models import PlanificationML, FrequencePlanif, ModePlanif
    from .. import ml_scheduler

    planif = PlanificationML.singleton()

    # Lecture du formulaire (validation minimale, l'UI restreint déjà les choix)
    mode      = request.POST.get('mode', ModePlanif.OS_NATIF)
    frequence = request.POST.get('frequence', FrequencePlanif.HEBDOMADAIRE)
    try:
        jour_semaine = int(request.POST.get('jour_semaine', 6))
        jour_mois    = int(request.POST.get('jour_mois', 1))
    except (TypeError, ValueError):
        jour_semaine, jour_mois = 6, 1

    heure_str = request.POST.get('heure', '03:00')
    try:
        h, m = heure_str.split(':')
        heure = timezone.datetime.strptime(f'{int(h):02d}:{int(m):02d}', '%H:%M').time()
    except (ValueError, AttributeError):
        heure = timezone.datetime.strptime('03:00', '%H:%M').time()

    planif.mode          = mode if mode in ModePlanif.values else ModePlanif.OS_NATIF
    planif.frequence     = frequence if frequence in FrequencePlanif.values else FrequencePlanif.HEBDOMADAIRE
    planif.jour_semaine  = max(0, min(6, jour_semaine))
    planif.jour_mois     = max(1, min(28, jour_mois))
    planif.heure         = heure
    planif.active        = True
    planif.prochaine_execution = ml_scheduler.calculer_prochaine_execution(planif)
    planif.modifie_par   = request.user if request.user.is_authenticated else None
    planif.save()

    # Applique au système
    resultat = ml_scheduler.enregistrer(planif)
    if resultat.ok:
        if resultat.fallback:
            messages.warning(request, f'⚠ {resultat.message}')
        else:
            messages.success(request, f'✅ Planification enregistrée — {resultat.message}')
    else:
        messages.error(request, f'❌ {resultat.message}')

    return redirect('admin:entreprise_demandeverification_ml_status')


@staff_member_required
@require_POST
def admin_ml_planification_supprimer(request):
    """Désactive et supprime la planification de tous les adapters."""
    from ..models import PlanificationML
    from .. import ml_scheduler

    planif = PlanificationML.singleton()
    planif.active = False
    planif.prochaine_execution = None
    planif.modifie_par = request.user if request.user.is_authenticated else None
    planif.save(update_fields=['active', 'prochaine_execution', 'modifie_par'])

    resultat = ml_scheduler.supprimer(planif)
    if resultat.ok:
        messages.success(request, '✅ Planification désactivée.')
    else:
        messages.warning(request, f'⚠ {resultat.message}')

    return redirect('admin:entreprise_demandeverification_ml_status')


@staff_member_required
@require_POST
def admin_ml_reentrainer(request):
    """Lance le ré-entraînement des modèles via la commande `reentrainer_tout`."""
    from django.core.management import call_command
    from candidat import matching_ml
    from entreprise import ats_ml
    from ..middleware_ml import _LOCK

    # Réutilise le verrou process-level du scheduler ML : évite qu'un
    # double-clic (ou une exécution planifiée concurrente) ne lance deux
    # ré-entraînements en parallèle.
    if not _LOCK.acquire(blocking=False):
        messages.warning(request, '⚠ Un ré-entraînement est déjà en cours, réessayez dans quelques instants.')
        return redirect('admin:entreprise_demandeverification_ml_status')

    cible = request.POST.get('cible', 'tous')  # 'tous' | 'matching' | 'ats'

    kwargs = {'min': 30, 'dry_run': False}
    if cible == 'matching':
        kwargs['skip_ats'] = True
    elif cible == 'ats':
        kwargs['skip_matching'] = True

    buffer = io.StringIO()
    try:
        call_command('reentrainer_tout', **kwargs, stdout=buffer)
        # Invalide les singletons pour que la page suivante recharge les nouveaux modèles
        matching_ml.vider_cache()
        ats_ml.vider_cache()
        messages.success(request, f'✅ Ré-entraînement terminé ({cible}).')
    except Exception as e:
        logger.exception('Échec ré-entraînement ML')
        messages.error(request, f'❌ Échec du ré-entraînement : {e}')
    finally:
        _LOCK.release()

    return redirect('admin:entreprise_demandeverification_ml_status')
