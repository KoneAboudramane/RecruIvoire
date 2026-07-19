"""Public-facing pages (no auth required)."""
import json
import logging

from django.core.cache import cache as django_cache
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_POST

from .. import app_messages as messages
from ..decorators import candidat_required
from ..forms import CandidatureForm
from ..models import (
    Candidat, ModeleCV, AbonneNewsletter,
    Candidature, Entretien, NotificationCandidat,
    Temoignage, LogoSite,
)
from ..visiteurs import enregistrer_visite

logger = logging.getLogger(__name__)


def _ids_favoris(candidat):
    """IDs des offres favorites du candidat (set vide si non connecté)."""
    if not candidat:
        return set()
    from ..models import OffreFavori
    return set(
        OffreFavori.objects.filter(candidat=candidat).values_list('offre_id', flat=True)
    )


def accueil(request):
    from datetime import timedelta
    from django.db.models import Count, Q
    from entreprise.models import OffreEmploi, StatutOffre, Entreprise
    from referentiel.models import Ville

    modeles_accueil  = django_cache.get('accueil_modeles')
    modeles_carousel = django_cache.get('accueil_carousel')
    if modeles_accueil is None:
        modeles_accueil  = list(ModeleCV.objects.filter(actif=True).order_by('ordre')[:4])
        modeles_carousel = list(ModeleCV.objects.filter(actif=True).order_by('ordre'))
        django_cache.set('accueil_modeles',  modeles_accueil,  1800)
        django_cache.set('accueil_carousel', modeles_carousel, 1800)

    stats_visiteurs   = enregistrer_visite(request)

    # Expire automatiquement les offres dont la date est dépassée (même
    # logique lazy que côté entreprise, voir entreprise/views/offres.py et
    # candidat/views/public.py::offres()) — sinon une offre publiée reste
    # visible ici tant qu'aucun recruteur n'a rouvert sa liste d'offres.
    a_expirer = list(
        OffreEmploi.objects
        .filter(statutOffre=StatutOffre.PUBLIEE, dateExpiration__lt=timezone.now().date())
        .prefetch_related('recruteurs_createurs')
    )
    if a_expirer:
        OffreEmploi.objects.filter(pk__in=[o.pk for o in a_expirer]).update(statutOffre=StatutOffre.EXPIREE)
        for offre in a_expirer:
            offre.statutOffre = StatutOffre.EXPIREE
            offre._notifier_expiration()

    offres_publiees_qs = OffreEmploi.objects.filter(statutOffre=StatutOffre.PUBLIEE)

    def _offres_vedette_generiques():
        """6 dernières offres publiées, sans personnalisation (cache global 5 min)."""
        offres = django_cache.get('accueil_offres_vedette')
        if offres is None:
            offres = list(
                offres_publiees_qs
                .select_related('entreprise', 'contrat', 'modeTravailRef', 'anneesExperience')
                .prefetch_related('typesCompetence', 'langues')
                .order_by('-datePublication', '-dateCreation', '-pk')[:6]
            )
            django_cache.set('accueil_offres_vedette', offres, 300)
        return offres

    from ..matching import couleur_score, libelle_score, matching_actif as _matching_actif
    candidat = getattr(request, 'candidat', None)
    offres_vedette_avec_score = []

    ids_offres_traitees = set()
    if candidat:
        # Une offre déjà acceptée ou refusée n'a plus rien à faire dans les
        # recommandations, expirée ou pas (voir aussi offres()).
        ids_offres_traitees = set(Candidature.objects.filter(
            candidat=candidat, statut__code__in=['ACCEPTEE', 'REFUSEE'],
        ).values_list('offre_id', flat=True))

    # Ensemble d'IDs réellement publiés MAINTENANT (source de vérité DB) —
    # purge les caches (jusqu'à 7 j en repli stale) qui peuvent contenir une
    # offre entre-temps fermée/pourvue par l'entreprise, voir offres().
    ids_offres_valides = set(
        offres_publiees_qs.exclude(pk__in=ids_offres_traitees).values_list('pk', flat=True)
    )

    if candidat:
        # Offres personnalisées : le calcul sémantique + ML est trop lent pour
        # tourner dans le cycle requête/réponse HTTP (voir candidat/tasks.py).
        # La vue ne fait donc QUE lire le cache — jamais de calcul synchrone ici.
        cache_key = f'accueil_reco_{candidat.pk}'
        stale_key = f'accueil_reco_stale_{candidat.pk}'
        lock_key  = f'accueil_reco_computing_{candidat.pk}'

        offres_reco = django_cache.get(cache_key)  # list[(offre, score)]
        if offres_reco is None:
            # Cache froid : on déclenche le recalcul en arrière-plan (verrou
            # court pour éviter les tâches en double si plusieurs requêtes
            # arrivent pendant le calcul), et on retombe sur le dernier
            # résultat personnalisé connu plutôt que de bloquer la réponse.
            if django_cache.add(lock_key, True, 60):
                from recrutement.background import lancer_en_arriere_plan
                from ..tasks import calculer_recommandations_accueil
                lancer_en_arriere_plan(calculer_recommandations_accueil, candidat.pk)
            offres_reco = django_cache.get(stale_key)

        if offres_reco is not None:
            offres_reco = [
                (offre, score) for offre, score in offres_reco
                if offre.pk in ids_offres_valides
            ]
            offres_vedette = [offre for offre, _ in offres_reco]
            if _matching_actif(request):
                offres_vedette_avec_score = [
                    {
                        'offre':   offre,
                        'score':   score,
                        'couleur': couleur_score(score),
                        'libelle': libelle_score(score),
                    }
                    for offre, score in offres_reco
                ]
        else:
            # Tout premier calcul pour ce candidat (jamais encore fait) :
            # générique en attendant, comme pour un visiteur anonyme.
            offres_vedette = [
                o for o in _offres_vedette_generiques()
                if o.pk in ids_offres_valides
            ]
    else:
        # Visiteur anonyme : 6 dernières offres publiées (cache global 5 min,
        # purgé lui aussi des offres entre-temps fermées/pourvues).
        offres_vedette = [
            o for o in _offres_vedette_generiques()
            if o.pk in ids_offres_valides
        ]

    # ── Top secteurs (par nombre d'offres publiées) ──────────────────────────
    top_secteurs = django_cache.get('accueil_top_secteurs')
    if top_secteurs is None:
        top_secteurs = list(
            offres_publiees_qs
            .filter(entreprise__secteurActiviteRef__isnull=False)
            .values(
                'entreprise__secteurActiviteRef__id',
                'entreprise__secteurActiviteRef__nomSecteur',
            )
            .annotate(nb=Count('id'))
            .order_by('-nb')[:8]
        )
        django_cache.set('accueil_top_secteurs', top_secteurs, 300)

    # ── Villes proches du candidat (par référentiel) ────────────────────────
    from django.db.models.functions import Lower
    from referentiel.models import Pays

    candidat_ville = ''
    candidat_region = ''
    candidat_pays = ''
    villes_proches = []
    inviter_completer_profil = False

    def _agg_villes_par_noms(noms, limite=12):
        """Agrège les offres par ville (case-insensible) pour une liste de noms."""
        if not noms:
            return []
        noms_lower = {n.lower() for n in noms if n}
        rows = (
            offres_publiees_qs
            .annotate(ville_lower=Lower('ville'))
            .filter(ville_lower__in=noms_lower)
            .exclude(ville='')
            .values('ville', 'ville_lower')
            .annotate(nb=Count('id'))
        )
        groupes = {}
        for r in rows:
            k = r['ville_lower']
            if k not in groupes:
                groupes[k] = {'ville': r['ville'], 'nb': 0}
            groupes[k]['nb'] += r['nb']
        return sorted(groupes.values(), key=lambda x: -x['nb'])[:limite]

    # Top global
    villes_top = django_cache.get('accueil_villes_top')
    if villes_top is None:
        villes_top = list(
            offres_publiees_qs
            .exclude(ville='')
            .values('ville')
            .annotate(nb=Count('id'))
            .order_by('-nb')[:8]
        )
        django_cache.set('accueil_villes_top', villes_top, 300)

    info = candidat.informationPersonnelle if candidat else None
    if info and (info.ville or '').strip():
        candidat_ville = info.ville.strip()
        candidat_pays  = (info.pays or '').strip()

        ville_ref = (
            Ville.objects
            .annotate(nomVille_lower=Lower('nomVille'))
            .filter(nomVille_lower=candidat_ville.lower())
            .select_related('pays')
            .first()
        )
        if ville_ref:
            if ville_ref.region:
                candidat_region = ville_ref.region
            if not candidat_pays and ville_ref.pays:
                candidat_pays = ville_ref.pays.nomPays

        noms_proches = {candidat_ville}
        if candidat_pays:
            pays_ref = Pays.objects.filter(nomPays__iexact=candidat_pays).first()
            if pays_ref:
                noms_proches |= set(
                    Ville.objects.filter(pays=pays_ref).values_list('nomVille', flat=True)
                )
        villes_proches = _agg_villes_par_noms(noms_proches)
    else:
        inviter_completer_profil = True

    # ── Top entreprises qui recrutent (par nb d'offres publiées) ─────────────
    top_entreprises = django_cache.get('accueil_top_entreprises')
    if top_entreprises is None:
        top_entreprises = list(
            Entreprise.objects
            .annotate(nb_offres=Count('offres', filter=Q(offres__statutOffre=StatutOffre.PUBLIEE)))
            .filter(nb_offres__gt=0)
            .order_by('-nb_offres')[:8]
        )
        django_cache.set('accueil_top_entreprises', top_entreprises, 300)

    # ── Stats globales ───────────────────────────────────────────────────────
    stats_globales = django_cache.get('accueil_stats_globales')
    if stats_globales is None:
        stats_globales = {
            'nb_offres':      offres_publiees_qs.count(),
            'nb_entreprises': Entreprise.objects.count(),
            'nb_candidats':   Candidat.objects.count(),
        }
        django_cache.set('accueil_stats_globales', stats_globales, 300)
    nb_offres_publiees   = stats_globales['nb_offres']
    nb_entreprises_total = stats_globales['nb_entreprises']
    nb_candidats_total   = stats_globales['nb_candidats']

    temoignages = django_cache.get('accueil_temoignages')
    if temoignages is None:
        temoignages = list(
            Temoignage.objects
            .filter(statut=Temoignage.STATUT_PUBLIE)
            .select_related('candidat')
            .order_by('ordre', '-date_soumission')[:3]
        )
        django_cache.set('accueil_temoignages', temoignages, 300)

    ids_favoris = _ids_favoris(candidat)

    # ── Tableau de bord rapide (candidat connecté) ──────────────────────────
    tableau_bord = {}
    if candidat:
        try:
            from entreprise.models import MessageDirect
            nb_cand_en_cours = (
                Candidature.objects.filter(candidat=candidat)
                .exclude(statut__code='RETIREE').count()
            )
            nb_msg_non_lus = MessageDirect.objects.filter(
                conversation__candidat=candidat,
                conversation__archivee_candidat=False,
                conversation__supprimee_candidat=False,
                expediteur='recruteur',
                lu=False,
            ).count()
            prochain_entretien = (
                Entretien.objects
                .filter(
                    candidature__candidat=candidat,
                    statut__in=['PLANIFIE', 'REPORTE'],
                    dateEntretien__gt=timezone.now(),
                )
                .select_related('candidature__offre__entreprise')
                .order_by('dateEntretien')
                .first()
            )
            # Tags profil : 2 premières compétences, sinon secteur
            comps = list(
                candidat.competences
                .select_related('typeCompetence')
                .order_by('pk')[:2]
            )
            tags_profil = []
            for c in comps:
                nom = (c.typeCompetence.nomCompetence if c.typeCompetence else None) or c.nomLibre
                if nom:
                    tags_profil.append(nom)
            if not tags_profil and candidat.secteurActiviteRef:
                tags_profil.append(candidat.secteurActiviteRef.nomSecteur)

            # Complétion du profil (8 critères pondérés → 100 %)
            nb_comps = candidat.competences.count()
            _criteres = [
                (bool(candidat.photoProfil),                         15),
                (bool(candidat.titreProfessionnel),                  15),
                (bool(candidat.biographie),                          10),
                (bool(info and (info.ville or '').strip()),           10),
                (nb_comps >= 2,                                       15),
                (candidat.experiencesProfessionnelles.exists(),       15),
                (candidat.formations.exists(),                        10),
                (candidat.languesParlees.exists(),                    10),
            ]
            score_completion = sum(pts for ok, pts in _criteres if ok)

            tableau_bord = {
                'nb_candidatures':    nb_cand_en_cours,
                'nb_messages':        nb_msg_non_lus,
                'prochain_entretien': prochain_entretien,
                'tags_profil':        tags_profil,
                'score_completion':   score_completion,
            }
        except Exception as e:
            logger.warning("Tableau de bord rapide : erreur — %s", e)

    return render(request, 'candidat/accueil.html', {
        'modeles_accueil':       modeles_accueil,
        'modeles_carousel':      modeles_carousel,
        'nb_visiteurs_jour':     stats_visiteurs['nb_aujourd_hui'],
        'nb_visiteurs_30j':      stats_visiteurs['nb_30_jours'],
        'nb_visiteurs_365j':     stats_visiteurs['nb_365_jours'],
        'offres_vedette':            offres_vedette,
        'offres_vedette_avec_score': offres_vedette_avec_score,
        'top_secteurs':          top_secteurs,
        'villes_proches':            villes_proches,
        'villes_top':                villes_top,
        'candidat_ville':            candidat_ville,
        'candidat_region':           candidat_region,
        'candidat_pays':             candidat_pays,
        'inviter_completer_profil':  inviter_completer_profil,
        'top_entreprises':       top_entreprises,
        'nb_offres_publiees':    nb_offres_publiees,
        'nb_entreprises_total':  nb_entreprises_total,
        'nb_candidats_total':    nb_candidats_total,
        'seuil_recente':         timezone.now() - timedelta(days=7),
        'temoignages':           temoignages,
        'ids_favoris':           ids_favoris,
        'tableau_bord':          tableau_bord,
    })


def avis(request):
    """Liste complète des témoignages candidats publiés."""
    from django.core.paginator import Paginator

    temoignages_qs = (
        Temoignage.objects
        .filter(statut=Temoignage.STATUT_PUBLIE)
        .select_related('candidat')
        .order_by('ordre', '-date_soumission')
    )

    page_number = request.GET.get('page')
    cible_pk = request.GET.get('t')
    if cible_pk and not page_number:
        ids_ordonnes = list(temoignages_qs.values_list('pk', flat=True))
        try:
            page_number = ids_ordonnes.index(int(cible_pk)) // 12 + 1
        except (ValueError, TypeError):
            page_number = None

    page = Paginator(temoignages_qs, 12).get_page(page_number)
    items = [
        {
            'pk':          t.pk,
            'prenom_nom':  t.prenom_nom,
            'titre_poste': t.titre_poste,
            'texte':       t.texte,
            'note':        t.note,
            'photo_url':   t.candidat.photoProfil.url if t.candidat and t.candidat.photoProfil else '',
            'initiales':   t.prenom_nom[:2].upper(),
        }
        for t in page
    ]
    return render(request, 'candidat/avis.html', {
        'page_obj':         page,
        'temoignages_json': json.dumps(items, ensure_ascii=False),
    })


def offres(request):
    """Liste publique de toutes les offres d'emploi publiées."""
    from datetime import timedelta
    from entreprise.models import OffreEmploi, StatutOffre
    from ..matching import couleur_score, libelle_score

    # Expire automatiquement les offres dont la date est dépassée (même
    # logique lazy que côté entreprise, voir entreprise/views/offres.py) —
    # sinon une offre publiée reste visible ici tant qu'aucun recruteur n'a
    # rouvert sa liste d'offres pour déclencher la transition.
    a_expirer = list(
        OffreEmploi.objects
        .filter(statutOffre=StatutOffre.PUBLIEE, dateExpiration__lt=timezone.now().date())
        .prefetch_related('recruteurs_createurs')
    )
    if a_expirer:
        OffreEmploi.objects.filter(pk__in=[o.pk for o in a_expirer]).update(statutOffre=StatutOffre.EXPIREE)
        for offre in a_expirer:
            offre.statutOffre = StatutOffre.EXPIREE
            offre._notifier_expiration()

    candidat = getattr(request, 'candidat', None)

    offres_publiees = (
        OffreEmploi.objects
        .filter(statutOffre=StatutOffre.PUBLIEE)
        .select_related(
            'entreprise', 'entreprise__secteurActiviteRef',
            'contrat', 'modeTravailRef', 'anneesExperience',
        )
        .prefetch_related('typesCompetence', 'langues')
        .order_by('-datePublication', '-dateCreation')
    )

    ids_offres_traitees = set()
    if candidat:
        # Une fois la candidature acceptée ou refusée, l'offre n'a plus rien
        # à faire dans la liste à parcourir/postuler (y compris en mode
        # matching, voir plus bas où scored_pairs est filtré pareil).
        ids_offres_traitees = set(Candidature.objects.filter(
            candidat=candidat, statut__code__in=['ACCEPTEE', 'REFUSEE'],
        ).values_list('offre_id', flat=True))
        offres_publiees = offres_publiees.exclude(pk__in=ids_offres_traitees)

    # Ensemble d'IDs réellement affichables MAINTENANT (source de vérité DB) —
    # sert à purger les résultats scorés issus du cache (jusqu'à 30 min, voire
    # 7 j en repli stale) qui peuvent contenir une offre entre-temps fermée/
    # pourvue par l'entreprise : sinon elle reste listée ici alors que sa page
    # détail refuse déjà la candidature.
    ids_offres_valides = set(offres_publiees.values_list('pk', flat=True))

    villes = sorted({o.ville for o in offres_publiees if o.ville})
    pays   = sorted({o.pays  for o in offres_publiees if o.pays})
    secteurs = sorted({
        o.entreprise.secteurActiviteRef.nomSecteur
        for o in offres_publiees
        if o.entreprise.secteurActiviteRef
    })

    from entreprise.models import Entreprise
    ville_initiale     = (request.GET.get('ville') or '').strip()
    secteur_initial    = (request.GET.get('secteur') or '').strip()
    entreprise_id      = (request.GET.get('entreprise') or '').strip()
    entreprise_nom     = ''
    if entreprise_id.isdigit():
        ent = Entreprise.objects.filter(pk=int(entreprise_id)).only('raisonSocial').first()
        if ent:
            entreprise_nom = ent.raisonSocial
    q_initiale = (
        request.GET.get('q')
        or entreprise_nom
        or ville_initiale
        or secteur_initial
        or ''
    ).strip()

    contrats_valides = {'CDI', 'CDD', 'FREELANCE', 'STAGE', 'ALTERNANCE'}
    contrat_initial = request.GET.get('contrat', '').upper().strip()
    if contrat_initial not in contrats_valides:
        contrat_initial = 'TOUS'

    from ..matching import matching_actif as _matching_actif, peut_utiliser_matching, est_opt_in
    from django.core.paginator import Paginator
    matching_eligible = peut_utiliser_matching(candidat)
    matching_actif    = _matching_actif(request)
    total_offres      = offres_publiees.count()

    page_number = request.GET.get('page', 1)
    PER_PAGE = 54

    offres_avec_score = []
    matching_en_calcul = False
    if matching_actif:
        # Le calcul sémantique + ML sur l'ensemble des offres est trop lent
        # pour tourner dans le cycle requête/réponse HTTP (comme pour les
        # recommandations de l'accueil, voir candidat/tasks.py). La vue ne
        # fait donc QUE lire le cache — jamais de calcul synchrone ici.
        cache_key = f'matching_offres_{candidat.pk}'
        stale_key = f'matching_offres_stale_{candidat.pk}'
        lock_key  = f'matching_offres_computing_{candidat.pk}'

        scored_pairs = django_cache.get(cache_key)
        if scored_pairs is None:
            if django_cache.add(lock_key, True, 60):
                from recrutement.background import lancer_en_arriere_plan
                from ..tasks import calculer_matching_offres
                lancer_en_arriere_plan(calculer_matching_offres, candidat.pk)
            scored_pairs = django_cache.get(stale_key)
            matching_en_calcul = True

        if scored_pairs is not None:
            scored_pairs = [
                (offre, score) for offre, score in scored_pairs
                if offre.pk in ids_offres_valides
            ]
            all_scored = [
                {
                    'offre':   offre,
                    'score':   score,
                    'couleur': couleur_score(score),
                    'libelle': libelle_score(score),
                }
                for offre, score in scored_pairs
            ]
            paginator = Paginator(all_scored, PER_PAGE)
            page_obj  = paginator.get_page(page_number)
            offres_avec_score = list(page_obj.object_list)
            offres_page = []
        else:
            # Tout premier calcul pour ce candidat (jamais encore fait) : on
            # retombe sur le tri par date le temps que le calcul se termine
            # (le bouton reste "activé" — voir matching_actif vs affichage
            # scoré ci-dessous — et le JS reprendra automatiquement le résultat
            # scoré une fois `matching_en_calcul` retombé à False).
            paginator = Paginator(offres_publiees, PER_PAGE)
            page_obj  = paginator.get_page(page_number)
            offres_page = page_obj
    else:
        paginator = Paginator(offres_publiees, PER_PAGE)
        page_obj  = paginator.get_page(page_number)
        offres_page = page_obj

    cur   = page_obj.number
    total_pages = paginator.num_pages
    start = max(1, cur - 2)
    end   = min(total_pages, cur + 2)
    if end - start < 4:
        if start == 1:
            end = min(total_pages, start + 4)
        else:
            start = max(1, end - 4)
    page_range = range(start, end + 1)

    params = request.GET.copy()
    params.pop('page', None)
    qs = params.urlencode()

    ids_favoris = _ids_favoris(candidat)

    offres_affichees = [item['offre'] for item in offres_avec_score] if offres_avec_score else list(offres_page)
    offres_filtre_json = json.dumps([
        {
            'contrat': o.typeContrat,
            'mode':    o.modeTravail,
            'search':  ' '.join(filter(None, [
                o.titre, o.entreprise.raisonSocial, o.ville, o.pays,
                o.entreprise.secteurActiviteRef.nomSecteur if o.entreprise.secteurActiviteRef else '',
            ])).lower(),
        }
        for o in offres_affichees
    ], ensure_ascii=False)

    contexte = {
        'offres':              offres_page,
        'offres_avec_score':   offres_avec_score,
        'offres_filtre_json':  offres_filtre_json,
        'matching_actif':      matching_actif,
        'matching_eligible':   matching_eligible,
        'matching_en_calcul':  matching_en_calcul,
        'total_offres':        total_offres,
        'seuil_recente':       timezone.now() - timedelta(days=7),
        'villes':              villes,
        'pays_liste':          pays,
        'secteurs':            secteurs,
        'q_initiale':          q_initiale,
        'contrat_initial':     contrat_initial,
        'page_obj':            page_obj,
        'page_range':          page_range,
        'qs':                  qs,
        'ids_favoris':         ids_favoris,
    }

    # Requête AJAX (toggle du matching) : on ne renvoie que la liste, pas la page entière.
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'candidat/partials/_offres_liste.html', contexte)

    return render(request, 'candidat/offres.html', contexte)


def offre_detail(request, offre_id):
    """Deteil public d'une offre d'emploi publiee."""
    from datetime import timedelta
    from entreprise.models import OffreEmploi, StatutOffre
    from ..matching import Matcher, couleur_score, libelle_score

    # Expire automatiquement les offres dont la date est dépassée (même
    # logique lazy qu'ailleurs côté candidat, voir offres()/accueil() dans ce
    # module) — couvre à la fois l'offre demandée (bannière "expirée" à jour)
    # et les offres similaires/suggestions listées plus bas.
    a_expirer = list(
        OffreEmploi.objects
        .filter(statutOffre=StatutOffre.PUBLIEE, dateExpiration__lt=timezone.now().date())
        .prefetch_related('recruteurs_createurs')
    )
    if a_expirer:
        OffreEmploi.objects.filter(pk__in=[o.pk for o in a_expirer]).update(statutOffre=StatutOffre.EXPIREE)
        for o in a_expirer:
            o.statutOffre = StatutOffre.EXPIREE
            o._notifier_expiration()

    offre = get_object_or_404(
        OffreEmploi.objects
            .select_related('entreprise', 'contrat', 'modeTravailRef',
                            'anneesExperience', 'niveauEtudeRef', 'paysRef', 'diplome')
            .prefetch_related('typesCompetence', 'langues'),
        pk=offre_id,
        statutOffre__in=[
            StatutOffre.PUBLIEE, StatutOffre.EXPIREE,
            StatutOffre.POURVUE, StatutOffre.FERMEE,
        ],
    )
    est_publiee = offre.statutOffre == StatutOffre.PUBLIEE
    if est_publiee:
        from django.db.models import F
        OffreEmploi.objects.filter(pk=offre.pk).update(nbVues=F('nbVues') + 1)

    candidat_courant = getattr(request, 'candidat', None)
    ids_offres_traitees = set()
    if candidat_courant:
        # Une offre déjà acceptée ou refusée ne doit plus être re-suggérée
        # au candidat, expirée ou pas (voir aussi offres()/accueil()).
        ids_offres_traitees = set(Candidature.objects.filter(
            candidat=candidat_courant, statut__code__in=['ACCEPTEE', 'REFUSEE'],
        ).values_list('offre_id', flat=True))

    offres_similaires = (
        OffreEmploi.objects
            .filter(statutOffre=StatutOffre.PUBLIEE, entreprise=offre.entreprise)
            .exclude(pk=offre.pk)
            .exclude(pk__in=ids_offres_traitees)
            .select_related('entreprise')
            .order_by('-datePublication')[:3]
    )

    from django.db.models import Q, Case, When, IntegerField, Value
    ids_meme_ent = [offre.pk] + list(offres_similaires.values_list('pk', flat=True))
    q_similaire = Q(statutOffre=StatutOffre.PUBLIEE) & ~Q(pk__in=ids_meme_ent) & ~Q(pk__in=ids_offres_traitees)
    q_criteres = Q()
    if offre.typeContrat:
        q_criteres |= Q(typeContrat=offre.typeContrat)
    if offre.ville:
        q_criteres |= Q(ville__iexact=offre.ville)
    if offre.entreprise.secteurActiviteRef_id:
        q_criteres |= Q(entreprise__secteurActiviteRef_id=offre.entreprise.secteurActiviteRef_id)
    offres_suggestions = (
        OffreEmploi.objects
            .filter(q_similaire & q_criteres)
            .select_related('entreprise')
            .order_by('-datePublication')[:4]
    ) if q_criteres else OffreEmploi.objects.none()

    # ── Matching (opt-in) ───────────────────────────────────────────────────
    from ..matching import matching_actif as _matching_actif
    matching = None
    if _matching_actif(request):
        r = Matcher(request.candidat).scorer(offre)
        matching = {
            'score':    r['score'],
            'methode':  r['methode'],
            'criteres': r['criteres'],
            'couleur':  couleur_score(r['score']),
            'libelle':  libelle_score(r['score']),
        }

    # ── Candidature : a-t-il deja postule ? Formulaire ? ────────────────────
    candidature_existante = None
    candidature_form      = None
    est_favori            = False
    a_un_cv                = False
    ouvrir_formulaire      = False
    candidat = getattr(request, 'candidat', None)
    if candidat:
        from ..models import OffreFavori
        candidature_existante = (
            Candidature.objects
            .filter(candidat=candidat, offre=offre)
            .exclude(statut__code='RETIREE')
            .select_related('statut')
            .first()
        )
        if not candidature_existante:
            initial = {}
            # Arrivee depuis "Postuler avec ce CV" / "Postuler avec cette lettre"
            # (boutons CV/lettre adaptes par IA, cv/_form_panel.html et
            # lettreMo/creer_lettre.html) : preselectionne le CV et/ou la
            # lettre et ouvre directement le formulaire de candidature.
            if request.GET.get('postuler') == '1':
                if request.GET.get('cv', '').isdigit():
                    cv_preselectionne = candidat.cvs.filter(
                        pk=request.GET['cv'], archive=False,
                    ).first()
                    if cv_preselectionne:
                        initial['cvSauvegarde'] = cv_preselectionne
                        ouvrir_formulaire = True
                if request.GET.get('lettre', '').isdigit():
                    lettre_preselectionnee = candidat.lettres.filter(
                        pk=request.GET['lettre'], archive=False,
                    ).first()
                    if lettre_preselectionnee:
                        initial['lettreSauvegardee'] = lettre_preselectionnee
                        ouvrir_formulaire = True
            candidature_form = CandidatureForm(candidat=candidat, offre=offre, initial=initial)
        est_favori = OffreFavori.objects.filter(candidat=candidat, offre=offre).exists()
        a_un_cv = candidat.cvs.filter(archive=False).exists()

    # Lettre de motivation exigee par l'offre (orthographe d'origine, cf. forms.py) —
    # sert a n'afficher la carte "Adapter ma lettre avec l'IA" que si pertinent.
    ats = offre.criteresATS or {}
    lettre_requise = bool(ats.get('lettreMotivationnObligatoire') or ats.get('lettreMotivationObligatoire'))
    # Calcule ici (plutot que dans le template) pour eviter tout piege de
    # precedence "and"/"or" cote Django template.
    afficher_bloc_adaptation_ia = bool(candidat) and (a_un_cv or lettre_requise)

    # ── JSON-LD JobPosting (Google rich results) ────────────────────────────
    _contrat_map = {
        'CDI': 'FULL_TIME', 'CDD': 'TEMPORARY',
        'STAGE': 'INTERN', 'ALTERNANCE': 'OTHER', 'FREELANCE': 'CONTRACTOR',
    }
    _ld = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": offre.titre,
        "description": (offre.missions or '')[:500],
        "datePosted": offre.datePublication.strftime('%Y-%m-%d') if offre.datePublication else '',
        "hiringOrganization": {
            "@type": "Organization",
            "name": offre.entreprise.raisonSocial,
        },
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": offre.ville or '',
                "addressCountry": "CI",
            },
        },
        "employmentType": _contrat_map.get(offre.typeContrat, 'OTHER'),
    }
    if offre.entreprise.siteWeb:
        _ld["hiringOrganization"]["sameAs"] = offre.entreprise.siteWeb
    if offre.salaireMin or offre.salaireMax:
        _sal = {"@type": "MonetaryAmount", "currency": "XOF",
                "value": {"@type": "QuantitativeValue", "unitText": "MONTH"}}
        if offre.salaireMin:
            _sal["value"]["minValue"] = float(offre.salaireMin)
        if offre.salaireMax:
            _sal["value"]["maxValue"] = float(offre.salaireMax)
        _ld["baseSalary"] = _sal
    json_ld = json.dumps(_ld, ensure_ascii=False).replace('</', '<\\/')

    return render(request, 'candidat/offre_detail.html', {
        'offre':                  offre,
        'est_publiee':            est_publiee,
        'offres_similaires':      offres_similaires,
        'offres_suggestions':     offres_suggestions,
        'seuil_recente':          timezone.now() - timedelta(days=7),
        'matching':               matching,
        'candidature_existante':  candidature_existante,
        'candidature_form':       candidature_form,
        'est_favori':             est_favori,
        'a_un_cv':                a_un_cv,
        'lettre_requise':         lettre_requise,
        'afficher_bloc_adaptation_ia': afficher_bloc_adaptation_ia,
        'ouvrir_formulaire':      ouvrir_formulaire,
        'json_ld':                json_ld,
    })


def entreprise_profil(request, entreprise_id):
    """Profil public d'une entreprise (informations consultables par un candidat)."""
    from entreprise.models import Entreprise

    entreprise = get_object_or_404(
        Entreprise.objects.select_related('secteurActiviteRef', 'typeRaisonSocialeRef'),
        pk=entreprise_id,
    )
    return render(request, 'candidat/entreprise_profil.html', {
        'entreprise': entreprise,
    })



