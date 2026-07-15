"""Dashboard, profile, identity, portfolio, rubriques, password change, testimonial."""
import json
import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .. import app_messages as messages
from ..cv_initial import build_rubriques_initial, extract_rubriques_snapshot
from ..decorators import candidat_required
from ..forms import (
    InformationPersonnelleForm, ProfilCandidatForm,
    ProfilIdentiteForm, ProfilPortfolioForm,
)
from ..models import (
    Candidat, InformationPersonnelle, LienCandidat,
    AbonneNewsletter, Candidature, NotificationCandidat,
    Portfolio, Temoignage, Entretien,
)
from referentiel.models import ReseauSocial

logger = logging.getLogger(__name__)


def _score_completion_profil(candidat):
    """Score de complétion du profil (0-100) + items `(label, ok, url_onglet)`.

    Utilisé par `dashboard`, `profil` et `api_profil_score` — les 9 critères
    pondérés doivent rester identiques dans les 3 vues.
    """
    info = getattr(candidat, 'informationPersonnelle', None)
    photo = getattr(candidat, 'photoProfil', None) or (info and getattr(info, 'photoProfil', None))
    items = [
        ('Photo de profil',      bool(photo),                                        '?onglet=identite'),
        ('Titre professionnel',  bool(candidat.titreProfessionnel),                   '?onglet=identite'),
        ('Biographie',           bool(candidat.biographie),                           '?onglet=identite'),
        ('Ville / localisation', bool(info and info.ville),                           '?onglet=identite'),
        ('Téléphone',            bool(info and info.telephone),                       '?onglet=identite'),
        ('Compétences',          bool(candidat.competences.exists()),                 '?onglet=rubriques'),
        ('Formations',           bool(candidat.formations.exists()),                  '?onglet=rubriques'),
        ('Expériences',          bool(candidat.experiencesProfessionnelles.exists()), '?onglet=rubriques'),
        ('Réseaux sociaux',      bool(candidat.liensSociaux.exists()),                '?onglet=identite'),
    ]
    score = round(sum(ok for _, ok, _ in items) / len(items) * 100)
    return score, items


# ─── Dashboard candidat ──────────────────────────────────────────────────────

@candidat_required
def dashboard(request):
    from datetime import timedelta
    import json as _json
    from django.db.models import Count
    from django.db.models.functions import TruncMonth
    from entreprise.models import InvitationPostuler, MessageDirect
    from ..models import CV

    candidat = request.candidat
    now = timezone.now()

    # ── Candidatures ────────────────────────────────────────────────────────
    cands_qs = (
        Candidature.objects
        .filter(candidat=candidat)
        .select_related('offre', 'offre__entreprise', 'statut')
    )
    nb_total = cands_qs.count()

    candidatures_par_statut = list(
        cands_qs
        .exclude(statut=None)
        .values('statut__libelle', 'statut__couleur', 'statut__code')
        .annotate(nb=Count('id'))
        .order_by('-nb')
    )

    # 6 derniers mois (labels + données) — arithmétique calendaire exacte
    MOIS_FR = ['Jan','Fév','Mar','Avr','Mai','Juin','Juil','Août','Sep','Oct','Nov','Déc']

    def mois_relatif(dt, n_mois_arriere):
        """Retourne (year, month) du mois courant moins n_mois_arriere mois."""
        total_mois = dt.month - 1 - n_mois_arriere          # 0-indexed
        year  = dt.year + total_mois // 12
        month = total_mois % 12 + 1
        return year, month

    y0, m0 = mois_relatif(now, 5)
    import datetime as _dt
    debut_periode = now.replace(year=y0, month=m0, day=1, hour=0, minute=0, second=0, microsecond=0)

    par_mois_qs = (
        cands_qs
        .filter(dateCandidature__gte=debut_periode)
        .annotate(mois=TruncMonth('dateCandidature'))
        .values('mois')
        .annotate(nb=Count('id'))
        .order_by('mois')
    )
    data_by_month = {r['mois'].strftime('%Y-%m'): r['nb'] for r in par_mois_qs}

    chart_labels, chart_cand = [], []
    for i in range(5, -1, -1):
        year, month = mois_relatif(now, i)
        key = f"{year:04d}-{month:02d}"
        if i == 0:
            label = f"{now.day} {MOIS_FR[month - 1]}"
        else:
            label = f"1 {MOIS_FR[month - 1]}"
        chart_labels.append(label)
        chart_cand.append(data_by_month.get(key, 0))

    dernieres_candidatures = cands_qs.order_by('-dateCandidature')[:5]

    # ── Invitations ─────────────────────────────────────────────────────────
    inv_qs = (
        InvitationPostuler.objects
        .filter(candidat=candidat)
        .select_related('offre', 'offre__entreprise', 'recruteur')
    )
    nb_inv_attente  = inv_qs.filter(statut=InvitationPostuler.STATUT_EN_ATTENTE).count()
    nb_inv_acceptee = inv_qs.filter(statut=InvitationPostuler.STATUT_ACCEPTEE).count()
    nb_inv_ignoree  = inv_qs.filter(statut=InvitationPostuler.STATUT_IGNOREE).count()
    dernieres_invitations = inv_qs.order_by('-date_envoi')[:5]

    # ── Messages non lus ────────────────────────────────────────────────────
    nb_messages_non_lus = MessageDirect.objects.filter(
        conversation__candidat=candidat,
        expediteur=MessageDirect.EXPEDITEUR_RECRUTEUR,
        lu=False, supprime=False,
    ).count()

    # ── CVs ─────────────────────────────────────────────────────────────────
    nb_cvs = CV.objects.filter(candidat=candidat, archive=False).count()

    # ── Lettres de motivation ────────────────────────────────────────────────
    from ..models import LettreMotivation
    nb_lettres = LettreMotivation.objects.filter(candidat=candidat, archive=False).count()

    # ── Complétude du profil ─────────────────────────────────────────────────
    profil_score, profil_items = _score_completion_profil(candidat)
    profil_manquants = [(label, url) for label, ok, url in profil_items if not ok]

    # ── Entretiens à venir ───────────────────────────────────────────────────
    from ..models import Entretien
    prochains_entretiens = list(
        Entretien.objects
        .filter(candidature__candidat=candidat, statut='PLANIFIE', dateEntretien__gte=now)
        .select_related('candidature__offre', 'candidature__offre__entreprise')
        .order_by('dateEntretien')[:3]
    )

    # ── JSON pour Chart.js ───────────────────────────────────────────────────
    statut_labels   = [s['statut__libelle'] for s in candidatures_par_statut]
    statut_data     = [s['nb'] for s in candidatures_par_statut]
    statut_couleurs = [s['statut__couleur'] or '#6B7280' for s in candidatures_par_statut]

    return render(request, 'candidat/dashboard.html', {
        'candidat':               candidat,
        'nb_total':               nb_total,
        'candidatures_par_statut': candidatures_par_statut,
        'dernieres_candidatures': dernieres_candidatures,
        'nb_inv_attente':         nb_inv_attente,
        'nb_inv_acceptee':        nb_inv_acceptee,
        'nb_inv_ignoree':         nb_inv_ignoree,
        'dernieres_invitations':  dernieres_invitations,
        'nb_messages_non_lus':    nb_messages_non_lus,
        'nb_cvs':                 nb_cvs,
        'nb_lettres':             nb_lettres,
        'profil_score':           profil_score,
        'profil_manquants':       profil_manquants,
        'prochains_entretiens':   prochains_entretiens,
        'chart_mois_labels':      _json.dumps(chart_labels, ensure_ascii=False),
        'chart_mois_data':        _json.dumps(chart_cand),
        'chart_statut_labels':    _json.dumps(statut_labels, ensure_ascii=False),
        'chart_statut_data':      _json.dumps(statut_data),
        'chart_statut_couleurs':  _json.dumps(statut_couleurs),
    })


# ─── Profil ───────────────────────────────────────────────────────────────────

@candidat_required
def profil(request):
    candidat = request.candidat
    form_info      = InformationPersonnelleForm(instance=candidat)
    form_identite  = ProfilIdentiteForm(instance=candidat)
    form_portfolio = ProfilPortfolioForm(instance=candidat)
    abonne_nl = AbonneNewsletter.objects.filter(email=candidat.email).first() if candidat.email else None

    # Rubriques : merge snapshot JSON (`candidat.rubriques`) + tables
    rubriques = build_rubriques_initial(candidat)

    # Liens sociaux : référentiel actif (pour le dropdown) + état initial du candidat.
    reseaux_actifs = list(
        ReseauSocial.objects.filter(actif=True)
        .values('id', 'libelle', 'slug', 'couleur')
    )
    liens_initiaux = [
        {'reseau_id': l.reseau_id, 'url': l.url}
        for l in candidat.liensSociaux.select_related('reseau').order_by('ordre', 'id')
    ]

    # Galerie de modèles de portfolio disponibles (catalogue admin).
    portfolios_actifs = Portfolio.objects.filter(actif=True).order_by('ordre', 'nom')

    temoignage_candidat = Temoignage.objects.filter(candidat=candidat).first()
    info = getattr(candidat, 'informationPersonnelle', None)
    ville_candidat = (info.ville if info else '') or getattr(candidat, 'ville', '') or ''
    titre_prefill = candidat.titreProfessionnel or ''
    if titre_prefill and ville_candidat:
        titre_prefill = f'{titre_prefill} · {ville_candidat}'
    temoignage_init = {
        'statut':      temoignage_candidat.statut if temoignage_candidat else '',
        'texte':       temoignage_candidat.texte if temoignage_candidat else '',
        'note':        temoignage_candidat.note if temoignage_candidat else 5,
        'titre_poste': temoignage_candidat.titre_poste if temoignage_candidat else titre_prefill,
    }

    from entreprise.models import InvitationPostuler
    invitations_qs = (
        InvitationPostuler.objects
        .filter(candidat=candidat)
        .select_related('offre', 'offre__entreprise', 'recruteur')
        .order_by('-date_envoi')
    )
    nb_invitations_en_attente = invitations_qs.filter(statut=InvitationPostuler.STATUT_EN_ATTENTE).count()

    # Complétion du profil
    profil_score_p, profil_items_p = _score_completion_profil(candidat)
    profil_manquants_p = [label for label, ok, _ in profil_items_p if not ok]

    from django.urls import reverse
    from django.utils import timezone
    if candidat.tokenPortfolioPartage:
        lien_partage_portfolio = request.build_absolute_uri(
            reverse('candidat:portfolio_partage', kwargs={'token': candidat.tokenPortfolioPartage})
        )
    else:
        lien_partage_portfolio = ''
    expiration_portfolio = (
        candidat.tokenPortfolioExpiration.strftime('%d/%m/%Y à %H:%M')
        if candidat.tokenPortfolioExpiration else ''
    )
    lien_expire = bool(
        candidat.tokenPortfolioExpiration and candidat.tokenPortfolioExpiration < timezone.now()
    )

    return render(request, 'candidat/profil.html', {
        'form_info':                  form_info,
        'form_identite':              form_identite,
        'form_portfolio':             form_portfolio,
        'candidat':                   candidat,
        'abonne_nl':                  abonne_nl,
        'rubriques_json':             json.dumps(rubriques, default=str),
        'reseaux_json':               json.dumps(reseaux_actifs),
        'liens_json':                 json.dumps(liens_initiaux),
        'portfolios_actifs':          portfolios_actifs,
        'temoignage_init':            json.dumps(temoignage_init),
        'invitations':                invitations_qs,
        'nb_invitations_en_attente':  nb_invitations_en_attente,
        'profil_score':               profil_score_p,
        'profil_manquants':           profil_manquants_p,
        'profil_manquants_json':      json.dumps(profil_manquants_p, ensure_ascii=False),
        'lien_partage_portfolio':     lien_partage_portfolio,
        'expiration_portfolio':       expiration_portfolio,
        'lien_expire':                lien_expire,
    })


# ─── API témoignage candidat ──────────────────────────────────────────────────

@candidat_required
@require_POST
def api_soumettre_temoignage(request):
    """Crée ou met à jour le témoignage du candidat connecté (statut -> en_attente)."""
    candidat = request.candidat
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'message': 'Données invalides.'}, status=400)

    texte = (data.get('texte') or '').strip()
    titre_poste = (data.get('titre_poste') or '').strip()
    try:
        note = max(1, min(5, int(data.get('note', 5))))
    except (TypeError, ValueError):
        note = 5

    if not texte:
        return JsonResponse({'ok': False, 'message': 'Le témoignage ne peut pas être vide.'})

    prenom_nom = f'{candidat.prenom} {candidat.nom}'.strip()

    Temoignage.objects.update_or_create(
        candidat=candidat,
        defaults={
            'prenom_nom':  prenom_nom,
            'titre_poste': titre_poste,
            'texte':       texte,
            'note':        note,
            'source':      Temoignage.SOURCE_CANDIDAT,
            'statut':      Temoignage.STATUT_EN_ATTENTE,
        },
    )

    return JsonResponse({
        'ok':      True,
        'message': "Votre témoignage a été soumis et sera visible après validation par l'administration.",
        'statut':  Temoignage.STATUT_EN_ATTENTE,
    })


# ─── API sauvegarde profil (AJAX par onglet) ──────────────────────────────────

@candidat_required
def api_profil_score(request):
    """Retourne le score de complétion du profil en JSON."""
    candidat = request.candidat
    score, items = _score_completion_profil(candidat)
    manquants = [label for label, ok, _ in items if not ok]
    return JsonResponse({'score': score, 'manquants': manquants})


@candidat_required
@require_POST
def api_supprimer_photo(request):
    """Supprime la photo de profil du candidat."""
    candidat = request.candidat
    if candidat.photoProfil:
        candidat.photoProfil.delete(save=False)
        candidat.photoProfil = None
        candidat.save(update_fields=['photoProfil'])
    return JsonResponse({'ok': True})


@candidat_required
@require_POST
def api_sauvegarder_identite(request):
    """Sauvegarde l'onglet Identité (infos personnelles + titre/secteur/année)."""
    candidat  = request.candidat
    form_info = InformationPersonnelleForm(
        request.POST, request.FILES, instance=candidat,
    )
    form_identite = ProfilIdentiteForm(request.POST, instance=candidat)

    if form_info.is_valid() and form_identite.is_valid():
        obj = form_info.save(commit=False)
        if request.FILES.get('photoProfil'):
            obj.photoProfil = request.FILES['photoProfil']
        # Sauvegarde des champs référentiels (nationalite, pays, ville, codePostal)
        nat        = (request.POST.get('nationalite') or '').strip()
        pays       = (request.POST.get('pays')        or '').strip()
        ville      = (request.POST.get('ville')       or '').strip()
        codePostal = (request.POST.get('codePostal')  or '').strip()
        try:
            with transaction.atomic():
                obj.save()
                if obj.informationPersonnelle:
                    info = obj.informationPersonnelle
                    changed = False
                    if nat        != info.nationalite:  info.nationalite = nat;        changed = True
                    if pays       != info.pays:         info.pays       = pays;        changed = True
                    if ville      != info.ville:        info.ville      = ville;       changed = True
                    if codePostal != info.codePostal:   info.codePostal = codePostal;  changed = True
                    if changed:
                        info.save(update_fields=['nationalite', 'pays', 'ville', 'codePostal'])
                else:
                    # Crée un objet InformationPersonnelle minimal et lie au candidat
                    info = InformationPersonnelle.objects.create(
                        nom=obj.nom or '',
                        prenom=obj.prenom or '',
                        dateNaissance=obj.dateNaissance,
                        nationalite=nat,
                        email=obj.email or '',
                        telephone=obj.telephone or '',
                        adresse=obj.adresse or '',
                        codePostal=codePostal,
                        pays=pays,
                        ville=ville,
                    )
                    obj.informationPersonnelle = info
                    obj.save(update_fields=['informationPersonnelle'])
                form_identite.save()
        except Exception:
            logger.exception('Erreur lors de la sauvegarde des infos référentielles (pays/ville/nationalite/codePostal)')
        from recrutement.background import lancer_en_arriere_plan
        from entreprise.tasks import calculer_embedding_candidat
        lancer_en_arriere_plan(calculer_embedding_candidat, obj.id)
        info_obj = obj.informationPersonnelle
        return JsonResponse({
            'ok':        True,
            'message':   'Identité mise à jour avec succès !',
            'identite': {
                'prenom':           obj.prenom or '',
                'nom':              obj.nom or '',
                'email':            obj.email or '',
                'telephone':        obj.telephone or '',
                'adresse':          obj.adresse or '',
                'dateNaissance':    obj.dateNaissance.strftime('%Y-%m-%d') if obj.dateNaissance else '',
                'titreProfessionnel': obj.titreProfessionnel or '',
                'secteurActivite':    obj.secteurActiviteRef.nomSecteur if obj.secteurActiviteRef else '',
                'secteurActiviteId':  obj.secteurActiviteRef_id or '',
                'datePremierEmploi':  obj.datePremierEmploi or '',
                'permis':           (info_obj.permis      if info_obj else '') or '',
                'codePostal':       (info_obj.codePostal  if info_obj else '') or '',
                'pays':             pays,
                'ville':            ville,
                'nationalite':      nat,
                'photoUrl':         obj.photoProfil.url if obj.photoProfil else '',
            },
            'prenom':    obj.prenom,
            'nom':       obj.nom,
            'photo_url': obj.photoProfil.url if obj.photoProfil else '',
        })
    else:
        errors = {}
        for f, errs in form_info.errors.items():
            errors[f] = errs[0]
        for f, errs in form_identite.errors.items():
            errors[f] = errs[0]
        return JsonResponse(
            {'ok': False, 'message': 'Veuillez corriger les erreurs.', 'errors': errors},
            status=400,
        )


@candidat_required
@require_POST
def api_sauvegarder_portfolio(request):
    """Sauvegarde l'onglet Portfolio (bio, contrat, visibilité, liens sociaux)."""
    candidat       = request.candidat
    form_portfolio = ProfilPortfolioForm(request.POST, instance=candidat)

    liens_payload = _parse_liens_sociaux(request.POST.get('liensSociaux_json', '[]'))
    if liens_payload is None:
        return JsonResponse(
            {'ok': False, 'message': 'Format des liens sociaux invalide.'},
            status=400,
        )

    if not form_portfolio.is_valid():
        errors = {f: errs[0] for f, errs in form_portfolio.errors.items()}
        return JsonResponse(
            {'ok': False, 'message': 'Veuillez corriger les erreurs.', 'errors': errors},
            status=400,
        )

    raw_params = request.POST.get('paramsPortfolio_json', '')
    new_params = None
    if raw_params:
        try:
            parsed = json.loads(raw_params)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse(
                {'ok': False, 'message': 'Format des paramètres portfolio invalide.'},
                status=400,
            )
        if isinstance(parsed, dict):
            allowed = set(Candidat.PORTFOLIO_DEFAULTS.keys())
            new_params = {k: bool(v) for k, v in parsed.items() if k in allowed}

    try:
        with transaction.atomic():
            form_portfolio.save()
            _sync_liens_sociaux(candidat, liens_payload)
            if new_params is not None:
                candidat.paramsPortfolio = new_params
                candidat.save(update_fields=['paramsPortfolio'])
            from recrutement.background import lancer_en_arriere_plan
            from entreprise.tasks import calculer_embedding_candidat
            lancer_en_arriere_plan(calculer_embedding_candidat, candidat.id)
    except ValidationError as exc:
        return JsonResponse({'ok': False, 'message': str(exc)}, status=400)

    candidat.refresh_from_db()
    liens_serialises = [
        {'reseau_id': l.reseau_id, 'url': l.url}
        for l in candidat.liensSociaux.select_related('reseau').order_by('ordre', 'id')
    ]
    return JsonResponse({
        'ok': True,
        'message': 'Portfolio mis à jour avec succès !',
        'portfolio': {
            'biographie':          candidat.biographie or '',
            'sloganPortfolio':     candidat.sloganPortfolio or '',
            'couleurPortfolio':    candidat.couleurPortfolio or '',
            'portfolioPublic':     bool(candidat.portfolioPublic),
            'typeMobilite_id':     candidat.typeMobilite_id,
            'typeMobilite_label':  candidat.typeMobilite.libelle if candidat.typeMobilite else '',
            'typeContrat_id':      candidat.typeContratRecherche_id,
            'typeContrat_label':   candidat.typeContratRecherche.libelle if candidat.typeContratRecherche else '',
            'portfolioModele_id':  candidat.portfolioModele_id,
            'portfolioModele_nom': candidat.portfolioModele.nom if candidat.portfolioModele else '',
            'liensSociaux':        liens_serialises,
            'paramsPortfolio':     candidat.get_portfolio_params(),
        },
    })


@candidat_required
@require_POST
def api_changer_modele_portfolio(request):
    """Bascule rapide du modèle de portfolio."""
    candidat = request.candidat
    raw_id   = (request.POST.get('modele_id') or '').strip()

    if not raw_id or raw_id.lower() == 'null':
        candidat.portfolioModele = None
        candidat.save(update_fields=['portfolioModele'])
        return JsonResponse({'ok': True, 'message': 'Modèle retiré.', 'modele_id': None})

    try:
        modele = Portfolio.objects.get(pk=int(raw_id), actif=True)
    except (Portfolio.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'ok': False, 'message': 'Modèle introuvable ou inactif.'}, status=400)

    candidat.portfolioModele = modele
    candidat.save(update_fields=['portfolioModele'])
    return JsonResponse({
        'ok': True,
        'message': f"Modèle « {modele.nom} » appliqué.",
        'modele_id':   modele.id,
        'modele_nom':  modele.nom,
        'couleur':     modele.couleurPrincipale,
    })


def _parse_liens_sociaux(raw_json):
    """Parse le JSON envoyé par le front et normalise.

    Retourne une liste de tuples `(reseau_id, url)` dans l'ordre reçu, ou
    None si le JSON est invalide.
    """
    try:
        data = json.loads(raw_json or '[]')
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, list):
        return None

    liens = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            reseau_id = int(item.get('reseau_id'))
        except (TypeError, ValueError):
            continue
        url = (item.get('url') or '').strip()
        if not url:
            continue
        liens.append((reseau_id, url))
    return liens


def _sync_liens_sociaux(candidat, liens):
    """Remplace les liens sociaux du candidat par la liste fournie."""
    reseaux_valides = set(
        ReseauSocial.objects.filter(actif=True).values_list('id', flat=True)
    )

    par_reseau = {}
    for ordre, (reseau_id, url) in enumerate(liens, start=1):
        if reseau_id in reseaux_valides:
            par_reseau[reseau_id] = (ordre * 10, url)

    candidat.liensSociaux.all().delete()
    LienCandidat.objects.bulk_create([
        LienCandidat(candidat=candidat, reseau_id=rid, url=url, ordre=ordre)
        for rid, (ordre, url) in par_reseau.items()
    ])


# ─── API sauvegarde rubriques ─────────────────────────────────────────────────

@candidat_required
@require_POST
def api_sauvegarder_rubriques(request):
    """Sauvegarde les rubriques CV du candidat."""
    from ..rubriques_sync import sync_rubriques_to_db

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'message': 'Données invalides.'}, status=400)

    try:
        with transaction.atomic():
            request.candidat.rubriques = extract_rubriques_snapshot(data)
            request.candidat.save(update_fields=['rubriques'])
            sync_rubriques_to_db(request.candidat, data)
    except Exception as exc:
        logger.exception('Échec sync rubriques candidat=%s', request.candidat.pk)
        return JsonResponse(
            {'ok': False, 'message': f"Erreur lors de l'enregistrement : {exc}"},
            status=500,
        )

    return JsonResponse({'ok': True, 'message': 'Rubriques enregistrées avec succès !'})


# ─── API upload média (images / vidéos) pour les réalisations ────────────────

_MAX_IMAGE_SIZE_MO = 5
_MAX_VIDEO_SIZE_MO = 50
_ALLOWED_IMAGE_MIMES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
_ALLOWED_VIDEO_MIMES = {'video/mp4', 'video/webm', 'video/quicktime', 'video/x-matroska'}


@candidat_required
@require_POST
def api_upload_projet_media(request):
    """Upload d'une image ou vidéo de réalisation pour le candidat connecté."""
    import os
    import uuid
    from django.core.files.storage import default_storage
    from django.utils.text import get_valid_filename
    from recrutement.storages import get_public_storage

    type_media = (request.POST.get('type') or '').strip().lower()
    fichier    = request.FILES.get('file')

    if type_media not in ('image', 'video'):
        return JsonResponse({'ok': False, 'message': "Type invalide (attendu 'image' ou 'video')."}, status=400)
    if not fichier:
        return JsonResponse({'ok': False, 'message': 'Aucun fichier reçu.'}, status=400)

    # Validation MIME + taille
    mime = (fichier.content_type or '').lower()
    if type_media == 'image':
        max_size = _MAX_IMAGE_SIZE_MO * 1024 * 1024
        if mime not in _ALLOWED_IMAGE_MIMES:
            return JsonResponse({'ok': False, 'message': f'Format image non supporté ({mime}).'}, status=400)
    else:
        max_size = _MAX_VIDEO_SIZE_MO * 1024 * 1024
        if mime not in _ALLOWED_VIDEO_MIMES:
            return JsonResponse({'ok': False, 'message': f'Format vidéo non supporté ({mime}).'}, status=400)

    if fichier.size > max_size:
        limite_mo = max_size // (1024 * 1024)
        return JsonResponse(
            {'ok': False, 'message': f'Fichier trop volumineux (max {limite_mo} Mo).'},
            status=400,
        )

    safe_name = get_valid_filename(fichier.name) or 'fichier'
    file_id   = uuid.uuid4().hex[:12]
    nom_final = f'{file_id}_{safe_name}'
    sous_dir  = 'images' if type_media == 'image' else 'videos'
    chemin    = f'candidat/{request.candidat.pk}/projets/{sous_dir}/{nom_final}'

    storage    = get_public_storage() or default_storage
    saved_path = storage.save(chemin, fichier)
    url        = storage.url(saved_path)

    return JsonResponse({
        'ok'  : True,
        'id'  : file_id,
        'url' : url,
        'name': fichier.name,
        'size': fichier.size,
    })


# ─── API changement de mot de passe ──────────────────────────────────────────

@candidat_required
@require_POST
def api_changer_mot_de_passe(request):
    """Permet au candidat connecté de changer (ou définir) son mot de passe."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'message': 'Données invalides.'}, status=400)

    candidat  = request.candidat
    actuel    = data.get('actuel', '').strip()
    nouveau   = data.get('nouveau', '').strip()

    # Vérification du mot de passe actuel (si le candidat en a un)
    if candidat.has_usable_password():
        if not actuel:
            return JsonResponse({'ok': False, 'message': 'Saisissez votre mot de passe actuel.'})
        if not candidat.verifier_mot_de_passe(actuel):
            return JsonResponse({'ok': False, 'message': 'Mot de passe actuel incorrect.'})

    # Validation du nouveau
    if not nouveau:
        return JsonResponse({'ok': False, 'message': 'Le nouveau mot de passe est vide.'})
    if len(nouveau) < 8:
        return JsonResponse({'ok': False, 'message': 'Le mot de passe doit contenir au moins 8 caractères.'})

    candidat.set_password(nouveau)
    candidat.save(update_fields=['password'])
    return JsonResponse({'ok': True, 'message': 'Mot de passe mis à jour avec succès !'})


@candidat_required
def mon_portfolio(request):
    return redirect('candidat:portfolio_public', candidat_id=request.candidat.id)
