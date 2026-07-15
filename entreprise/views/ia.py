"""AI/ML scoring and suggestions views."""
import logging
import json

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .. import app_messages as messages
from ..models import OffreEmploi, StatutOffre, NotificationRecruteur, PropositionProfil
from ..decorators import entreprise_required, lecteur_bloque
from candidat.models import Candidat, Candidature
from .offres import _offres_visibles
from .notifications import _filtre_destinataire

logger = logging.getLogger(__name__)


# ─── Analyse IA : scoring sémantique CV ↔ Offre ──────────────────────────────

@entreprise_required
def candidature_analyser_ia(request, candidature_id):
    """Score IA (sémantique) d'une candidature via sentence-transformer.

    Retourne du JSON :
        {score, niveau, cosinus, modele, candidat, offre}
    Le recruteur doit appartenir à l'entreprise propriétaire de l'offre.
    """
    from candidat.models import Candidature
    from ..ats_predict import score_candidature

    candidature = get_object_or_404(
        Candidature.objects.select_related('candidat', 'offre'),
        pk=candidature_id,
        offre__in=_offres_visibles(request),
    )

    try:
        resultat = score_candidature(candidature)
    except Exception as exc:
        return JsonResponse(
            {'erreur': f"Échec du scoring IA : {exc}"},
            status=500,
        )
    return JsonResponse(resultat)


@entreprise_required
@lecteur_bloque
def candidatures_offre_scoring_ia(request, offre_id):
    """Score IA en lot de toutes les candidatures d'une offre, triées.

    Enrichit chaque résultat avec cv_url, lettre_url, portfolio_url
    pour permettre l'affichage direct des liens dans le panneau Top N.
    """
    from candidat.models import Candidature
    from ..ats_predict import scorer_toutes_candidatures

    offre = get_object_or_404(
        OffreEmploi, pk=offre_id, entreprise=request.entreprise,
    )
    candidatures = list(
        Candidature.objects
        .filter(offre=offre)
        .select_related('candidat', 'cvSauvegarde')
    )

    try:
        resultats = scorer_toutes_candidatures(offre, candidatures)
    except Exception as exc:
        return JsonResponse(
            {'erreur': f"Échec du scoring IA en lot : {exc}"},
            status=500,
        )

    # Index des candidatures par id pour enrichir les résultats
    par_id = {c.id: c for c in candidatures}
    for r in resultats:
        cand = par_id.get(r['candidature_id'])
        if not cand:
            continue
        r['cv_url']        = cand.cv_url or ''
        r['lettre_url']    = cand.lettreMotivation.url if cand.lettreMotivation else ''
        r['portfolio_url'] = reverse('entreprise:voir_portfolio',
                                      args=[cand.candidat_id])

    return JsonResponse({
        'offre_id':  offre.id,
        'total':     len(resultats),
        'resultats': resultats,
    })


# ─── ATS : Page dédiée Suggestions de profils par offre ──────────────────────

@entreprise_required
def suggestions_offre(request, offre_id):
    """Page dédiée affichant les profils suggérés par l'ATS pour une offre.

    Si aucune `PropositionProfil` n'existe encore, on déclenche un scan en
    avant d'afficher (sync — le recruteur attend le 1er chargement, ensuite
    c'est instantané grâce au cache de Propositions persistées).

    En navigant sur cette page, on marque comme lues les notifications
    de type PROFIL_MATCH liées à cette offre (le recruteur a vu le résultat).
    """
    from candidat.models import Candidat
    from django.core.cache import cache as django_cache
    from ..models import PropositionProfil, NotificationRecruteur
    from .. import notifications_service

    offre = get_object_or_404(
        OffreEmploi, pk=offre_id, entreprise=request.entreprise,
    )

    propositions = list(
        PropositionProfil.objects
        .filter(offre=offre)
        .exclude(action=PropositionProfil.Action.IGNORE)
        .select_related('candidat', 'candidat__informationPersonnelle')
        .order_by('-scoreATS')
    )

    # Si aucune proposition encore, on déclenche un scan synchrone une seule
    # fois — verrou anti-doublon : si un autre recruteur a ouvert la page en
    # même temps et scanne déjà cette offre, on ne relance pas un second scan
    # (coût élevé : encodage sentence-transformer de tous les candidats).
    scan_lance = False
    if not propositions:
        lock_key = f'scan_ats_offre_{offre.id}'
        if django_cache.add(lock_key, True, 120):
            try:
                notifications_service.scanner_profils_pour_offre(offre)
                scan_lance = True
                propositions = list(
                    PropositionProfil.objects
                    .filter(offre=offre)
                    .exclude(action=PropositionProfil.Action.IGNORE)
                    .select_related('candidat', 'candidat__informationPersonnelle')
                    .order_by('-scoreATS')
                )
            except Exception as exc:
                logger.exception("Échec du scan sync pour offre #%s : %s", offre.id, exc)
            finally:
                django_cache.delete(lock_key)

    # Statistiques par niveau (basé sur scoreATS)
    def niveau(score):
        if score >= 80: return 'EXCELLENT'
        if score >= 60: return 'BON'
        if score >= 40: return 'MOYEN'
        return 'FAIBLE'

    stats = {'EXCELLENT': 0, 'BON': 0, 'MOYEN': 0, 'FAIBLE': 0}
    for p in propositions:
        p.niveau = niveau(p.scoreATS)
        stats[p.niveau] += 1

    # Marquer les notifs PROFIL_MATCH liées à cette offre comme lues
    notif_qs = _filtre_destinataire(
        NotificationRecruteur.objects.filter(
            offre=offre,
            type=NotificationRecruteur.Type.PROFIL_MATCH,
            lue=False,
        ),
        request,
    )
    notif_qs.update(lue=True, dateLecture=timezone.now())

    seuil = int((offre.criteresATS or {}).get('scoreMinimum', 0))

    return render(request, 'entreprise/offres/suggestions.html', {
        'offre':         offre,
        'propositions':  propositions,
        'stats':         stats,
        'total':         len(propositions),
        'seuil':         seuil,
        'scan_lance':    scan_lance,
    })


# ─── ATS : Profils recommandés pour une offre (sourcing proactif) ────────────

@entreprise_required
def profils_recommandes_offre(request, offre_id):
    """Propose au recruteur une liste de profils candidats triés par score ATS.

    Filtre :
      - candidats avec `portfolioPublic=True` (opt-in candidat)
      - score ATS >= `offre.criteresATS['scoreMinimum']`

    Tri : score décroissant. Top 20 retournés.

    Effets de bord :
      - crée/met à jour les `PropositionProfil` (action=propose) pour servir
        de signal d'apprentissage à `entreprise/ats_ml.py`.
    """
    from candidat.models import Candidat
    from ..ats_predict import scorer_candidats
    from ..models import PropositionProfil

    offre = get_object_or_404(
        OffreEmploi, pk=offre_id, entreprise=request.entreprise,
    )

    seuil = int((offre.criteresATS or {}).get('scoreMinimum', 0))

    candidats = list(
        Candidat.objects
        .filter(portfolioPublic=True)
        .select_related('informationPersonnelle')
    )
    if not candidats:
        return JsonResponse({
            'offre_id': offre.id,
            'seuil':    seuil,
            'total':    0,
            'resultats': [],
            'message':  "Aucun candidat avec portfolio public dans la base.",
        })

    try:
        scores = scorer_candidats(offre, candidats)
    except Exception as exc:
        return JsonResponse(
            {'erreur': f"Échec du scoring ATS : {exc}"},
            status=500,
        )

    # Re-ranking ML si un modèle ATS entraîné est disponible
    try:
        from .. import ats_ml
        if ats_ml.est_disponible():
            scores = ats_ml.reranker(offre, candidats, scores)
    except Exception as exc:
        logger.warning("Re-ranking ML échoué (fallback ATS brut) : %s", exc)

    # Filtre seuil + top 20
    filtres = [r for r in scores if r['score'] >= seuil][:20]

    # Enrichissement : photo profil + URL portfolio
    par_id = {c.id: c for c in candidats}
    for r in filtres:
        cand = par_id.get(r['candidat_id'])
        if not cand:
            continue
        r['photo_url'] = cand.photoProfil.url if cand.photoProfil else ''
        r['portfolio_url'] = reverse('entreprise:voir_portfolio', args=[cand.id])
        r['initiales'] = (
            (cand.prenom[:1] + cand.nom[:1]).upper() if cand.prenom and cand.nom
            else (cand.prenom[:2] if cand.prenom else cand.nom[:2]).upper()
        )

    # Persistance des propositions (signal d'apprentissage)
    recruteur = getattr(request, 'recruteur', None)
    for r in filtres:
        PropositionProfil.objects.update_or_create(
            offre=offre,
            candidat_id=r['candidat_id'],
            defaults={
                'recruteur':  recruteur,
                'scoreATS':   r['score'],
                # On NE remplace PAS une action existante (vu/contacté/invité)
                # par 'propose' — seules les nouvelles propositions ont action=propose
            },
        )

    return JsonResponse({
        'offre_id':  offre.id,
        'seuil':     seuil,
        'total':     len(filtres),
        'total_scores': len(scores),
        'resultats': filtres,
        'ml_actif':  _ats_ml_actif(),
    })


def _ats_ml_actif() -> bool:
    """Indique si un modèle ATS entraîné est chargé (informatif pour l'UI)."""
    try:
        from .. import ats_ml
        return ats_ml.est_disponible()
    except Exception:
        return False


# ─── Tracking : actions du recruteur sur les profils proposés ────────────────

@entreprise_required
@lecteur_bloque
@require_POST
def proposition_profil_marquer(request, proposition_id, action):
    """Met à jour l'action d'une PropositionProfil (signal d'apprentissage).

    Actions valides : 'vu', 'contacte', 'invite', 'ignore'.
    Le recruteur doit appartenir à l'entreprise propriétaire de l'offre.
    """
    from ..models import PropositionProfil

    valides = {'vu', 'contacte', 'invite', 'ignore'}
    if action not in valides:
        return JsonResponse({'erreur': f"Action invalide : {action}"}, status=400)

    proposition = get_object_or_404(
        PropositionProfil.objects.select_related('offre'),
        pk=proposition_id,
        offre__in=_offres_visibles(request),
    )

    try:
        proposition.marquer_action(action)
    except ValueError as e:
        return JsonResponse({'erreur': str(e)}, status=400)

    return JsonResponse({
        'ok':        True,
        'action':    proposition.action,
        'date':      proposition.dateAction.isoformat() if proposition.dateAction else None,
    })
