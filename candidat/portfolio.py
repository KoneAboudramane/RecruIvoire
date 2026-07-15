"""
Portfolio — Vues et logique métier.

Ce fichier centralise tout ce qui concerne le portfolio candidat :
  - Affichage du builder (vue privée)
  - Vue publique d'un portfolio
  - API de sauvegarde / chargement (à implémenter)
  - Génération / export (à implémenter)

Modèle de données prévu (à créer via models.py + migration) :
  - Portfolio      : lié à un Candidat (OneToOne)
  - ProjetPortfolio: lié à un Portfolio (FK)
  - Competence     : lié à un Portfolio (FK)
"""

import json
from datetime import date

from django.conf import settings
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST

from .cv_initial import build_rubriques_initial
from .decorators import candidat_required
from .models import Candidat, Projet


_MOIS_FR = ('Jan.', 'Fév.', 'Mars', 'Avril', 'Mai', 'Juin',
            'Juil.', 'Août', 'Sept.', 'Oct.', 'Nov.', 'Déc.')


def _parse_ym(s):
    """'YYYY-MM' ou 'YYYY-MM-DD' → date(année, mois, 1). None si invalide."""
    if not s or not isinstance(s, str):
        return None
    parts = s.split('-')
    if len(parts) < 2:
        return None
    try:
        return date(int(parts[0]), int(parts[1]), 1)
    except (ValueError, TypeError):
        return None


def _format_periode(debut_str, fin_str, en_cours):
    """'Jan. 2022 — Avril 2024' (libellés FR)."""
    d = _parse_ym(debut_str)
    if not d:
        return ''
    debut_lbl = f"{_MOIS_FR[d.month - 1]} {d.year}"
    if en_cours:
        return f"{debut_lbl} — Présent"
    f = _parse_ym(fin_str)
    if not f:
        return debut_lbl
    return f"{debut_lbl} — {_MOIS_FR[f.month - 1]} {f.year}"


def _calc_duree(debut_str, fin_str, en_cours):
    """'4 ans · 2 mois' depuis strings 'YYYY-MM'. '' si calcul impossible."""
    debut_d = _parse_ym(debut_str)
    if not debut_d:
        return ''
    if en_cours:
        fin_d = date.today().replace(day=1)
    else:
        fin_d = _parse_ym(fin_str)
        if not fin_d:
            return ''
    months = (fin_d.year - debut_d.year) * 12 + (fin_d.month - debut_d.month)
    if months <= 0:
        return ''
    years, m = divmod(months, 12)
    parts = []
    if years:
        parts.append(f'{years} an{"s" if years > 1 else ""}')
    if m:
        parts.append(f'{m} mois')
    return ' · '.join(parts)


def _enrichir_experiences(experiences):
    """Ajoute `periodeFR` et `duree` à chaque expérience et chaque poste.
    Pas de modification du snapshot DB — pur enrichissement portfolio.
    """
    for exp in experiences or []:
        exp['periodeFR'] = _format_periode(exp.get('debut'), exp.get('fin'), exp.get('enCours'))
        exp['duree']     = _calc_duree(exp.get('debut'), exp.get('fin'), exp.get('enCours'))
        for poste in exp.get('postes') or []:
            poste['periodeFR'] = _format_periode(poste.get('debut'), poste.get('fin'), poste.get('enCours'))
            poste['duree']     = _calc_duree(poste.get('debut'), poste.get('fin'), poste.get('enCours'))
    return experiences


def _enrichir_benevolats(benevs):
    """Ajoute `periodeFR` et `duree` à chaque bénévolat. Idem expériences."""
    for b in benevs or []:
        b['periodeFR'] = _format_periode(b.get('debut'), b.get('fin'), b.get('enCours'))
        b['duree']     = _calc_duree(b.get('debut'), b.get('fin'), b.get('enCours'))
    return benevs


def _enrichir_projets(candidat, projets):
    """Enrichit chaque projet du snapshot :
      - `db_id` : ID du modèle Projet en DB (matching par titre normalisé) →
        nécessaire pour générer l'URL `portfolio_projet_detail`.
      - `lien` (override) : version trim du lien original, vide si pas une
        URL valide (ex: « http(s):// », « // », « www. »). Les valeurs non-URL
        comme un email sont neutralisées → le bouton « Voir la démo »
        n'apparaît que pour de vrais liens cliquables.
      - `has_demo` : bool dérivé pour simplifier la condition côté template.
    """
    import re
    url_re = re.compile(r'^(https?://|//|www\.)', re.IGNORECASE)

    db_map = {}
    for p in candidat.projets.all():
        if p.titre:
            db_map[p.titre.strip().lower()] = p.pk

    for p in projets or []:
        nom = (p.get('nom') or '').strip().lower()
        p['db_id'] = db_map.get(nom)

        lien_raw = (p.get('lien') or '').strip()
        if lien_raw and url_re.match(lien_raw):
            p['lien']     = lien_raw
            p['has_demo'] = True
        else:
            p['lien']     = ''
            p['has_demo'] = False

    return projets


# Modèle de portfolio par défaut si le candidat n'en a sélectionné aucun.
DEFAULT_PORTFOLIO_FICHIER = 'orange-vibrant'


# ── Vue builder (espace privé) ────────────────────────────────────────────────

@candidat_required
def portfolio(request):
    """
    Page de gestion du portfolio — accessible uniquement au candidat connecté.
    Affiche le builder Alpine.js qui permet de gérer projets, compétences et paramètres.
    """
    return render(request, 'candidat/portfolio/portfolio.html', {
        'page': 'portfolio',
    })


# ── Vue publique ──────────────────────────────────────────────────────────────

def _render_portfolio(request, candidat_id, base_template='candidat/base.html', ignorer_visibilite=False, **extra_ctx):
    """Rendu factorisé du portfolio public d'un candidat.

    Visibilité :
      - `portfolioPublic=True`  → visible par tous.
      - `portfolioPublic=False` → 404 sauf pour le propriétaire (preview).

    Choix du template enfant :
      - Le candidat sélectionne un modèle via `Candidat.portfolioModele`
        (FK vers `Portfolio`). À défaut, on utilise `orange-vibrant`.

    Couleur accent :
      - `Candidat.couleurPortfolio` si défini (override personnel),
      - sinon `Portfolio.couleurPrincipale` du modèle choisi,
      - sinon orange par défaut.

    `base_template` : template parent utilisé par les modèles portfolio via
    `{% extends base_template %}`. Permet d'afficher le portfolio dans
    l'espace candidat (`candidat/base.html`, défaut) ou dans l'espace
    entreprise (`entreprise/base.html`) avec la bonne navbar / footer.
    """
    candidat = get_object_or_404(
        Candidat.objects.select_related('sexe', 'typeMobilite', 'portfolioModele'),
        pk=candidat_id,
    )

    if not ignorer_visibilite and not candidat.portfolioPublic:
        if not request.candidat or request.candidat.id != candidat.id:
            from django.http import Http404
            raise Http404

    modele = candidat.portfolioModele if (candidat.portfolioModele and candidat.portfolioModele.actif) else None
    fichier = modele.fichier if modele else DEFAULT_PORTFOLIO_FICHIER
    couleur = candidat.couleurPortfolio or (modele.couleurPrincipale if modele else '#F77F00')

    liens = list(
        candidat.liensSociaux
        .select_related('reseau')
        .order_by('ordre', 'id')
    )

    # Années d'expérience : calcul direct depuis l'année du premier emploi.
    # `None` si non renseigné → le template ne pousse pas l'item méta.
    annees_xp = None
    if candidat.datePremierEmploi:
        annees_xp = max(0, date.today().year - candidat.datePremierEmploi)

    rubriques = build_rubriques_initial(candidat)
    # Filtre `visiblePortfolio` : le candidat peut masquer individuellement chaque
    # item via les toggles de l'onglet Rubriques du Profil (champ `estVisiblePortfolio`
    # sur les modèles relationnels, exposé sous la clé `visiblePortfolio` dans le JSON).
    # Un item avec `visiblePortfolio=False` ne s'affiche pas sur le portfolio public.
    for _section in ('experiences', 'formations', 'competences', 'langues', 'projets', 'benevs', 'interets'):
        items = rubriques.get(_section)
        if isinstance(items, list):
            rubriques[_section] = [i for i in items if not isinstance(i, dict) or i.get('visiblePortfolio', True) is not False]

    # Enrichit expériences, bénévolats et projets (impact 0 sur le CV : copie
    # locale enrichie). Projets reçoivent `db_id` pour le lien détail.
    _enrichir_experiences(rubriques.get('experiences'))
    _enrichir_benevolats(rubriques.get('benevs'))
    _enrichir_projets(candidat, rubriques.get('projets'))

    # Partitionne les formations en 3 groupes : diplomes, certifications,
    # attestations. Le template les affiche en sous-sections successives.
    formations_groupees = {'diplome': [], 'certification': [], 'attestation': []}
    for f in rubriques.get('formations') or []:
        t = f.get('typeSortie') or 'diplome'
        if t not in formations_groupees:
            t = 'diplome'
        formations_groupees[t].append(f)

    ctx = {
        'base_template':  base_template,
        'candidat':       candidat,
        'est_proprio':    request.candidat and request.candidat.id == candidat.id,
        'liens_sociaux':  liens,
        'rubriques':      rubriques,
        'formations_groupees': formations_groupees,
        'couleur_accent': couleur,
        'modele':         modele,
        'params':         candidat.get_portfolio_params(),
        'annees_xp':      annees_xp,
        'portfolio': {
            'couleurAccent': couleur,
            'slogan':        candidat.sloganPortfolio or '',
        },
    }
    ctx.update(extra_ctx)
    if ctx.get('masquer_contact'):
        params = dict(ctx['params'])
        params['showContact'] = False
        ctx['params'] = params
    return render(request, f'candidat/portfolio/modeles/{fichier}.html', ctx)


def portfolio_public(request, candidat_id):
    """Vue publique du portfolio (espace candidat — navbar candidat)."""
    return _render_portfolio(request, candidat_id, base_template='candidat/base.html')


def portfolio_partage(request, token):
    """Portfolio accessible via lien de partage (sans compte requis)."""
    from django.utils import timezone
    candidat = get_object_or_404(Candidat, tokenPortfolioPartage=token)
    if candidat.tokenPortfolioExpiration and candidat.tokenPortfolioExpiration < timezone.now():
        return render(request, 'candidat/portfolio/lien_expire.html', {
            'base_template': 'candidat/base.html',
        }, status=410)
    return _render_portfolio(request, candidat.id, base_template='candidat/base.html', ignorer_visibilite=True)


@candidat_required
@require_POST
def api_regenerer_token_portfolio(request):
    """Régénère le token de partage avec une durée optionnelle."""
    import uuid as uuid_module
    from django.utils import timezone
    from datetime import timedelta

    c = request.candidat
    duree = request.POST.get('duree', '0')  # jours ; 0 = permanent

    c.tokenPortfolioPartage = uuid_module.uuid4()
    try:
        jours = int(duree)
        c.tokenPortfolioExpiration = timezone.now() + timedelta(days=jours) if jours > 0 else None
    except (ValueError, TypeError):
        c.tokenPortfolioExpiration = None

    c.save(update_fields=['tokenPortfolioPartage', 'tokenPortfolioExpiration'])

    from django.urls import reverse
    lien = request.build_absolute_uri(
        reverse('candidat:portfolio_partage', kwargs={'token': c.tokenPortfolioPartage})
    )
    expiration_str = (
        c.tokenPortfolioExpiration.strftime('%d/%m/%Y à %H:%M')
        if c.tokenPortfolioExpiration else ''
    )
    return JsonResponse({'ok': True, 'lien': lien, 'expiration': expiration_str})


# ─── Détail d'un projet (page dédiée) ────────────────────────────────────────

def portfolio_projet_detail(request, candidat_id, projet_id):
    """Page de détail d'un projet du portfolio public d'un candidat.

    Contexte : titre, période, équipe, contexte, réalisation, médias (images +
    vidéos), lien démo. Accessible publiquement si le portfolio est public ;
    sinon 404 sauf pour le propriétaire (preview privée).
    """
    candidat = get_object_or_404(
        Candidat.objects.select_related('sexe', 'typeMobilite', 'portfolioModele'),
        pk=candidat_id,
    )
    if not candidat.portfolioPublic:
        if not request.candidat or request.candidat.id != candidat.id:
            from django.http import Http404
            raise Http404

    # Le projet doit appartenir au candidat (sinon 404).
    projet_db = get_object_or_404(Projet, pk=projet_id, candidat=candidat)

    # On reconstruit un dict identique à `rubriques.projets` pour cohérence
    # avec le template (mêmes champs nom, contexte, réalisation, etc.).
    # Le snapshot JSON `candidat.rubriques.projets` est plus riche (médias) ;
    # on cherche d'abord par titre (signature), sinon on fabrique depuis l'ORM.
    projet = None
    rub = candidat.rubriques if isinstance(candidat.rubriques, dict) else {}
    for p in rub.get('projets') or []:
        if isinstance(p, dict) and (p.get('nom') or '').strip().lower() == (projet_db.titre or '').strip().lower():
            projet = dict(p)
            break
    if projet is None:
        projet = {
            'id'         : projet_db.pk,
            'nom'        : projet_db.titre,
            'dateDebut'  : projet_db.dateDebut.strftime('%Y-%m-%d') if projet_db.dateDebut else '',
            'dateFin'    : projet_db.dateFin.strftime('%Y-%m-%d')   if projet_db.dateFin   else '',
            'tailleEquipe': projet_db.tailleEquipe,
            'contexte'   : projet_db.contexte,
            'realisation': projet_db.realisation,
            'lien'       : projet_db.urlDemo,
            'images'     : projet_db.images or [],
            'videos'     : projet_db.videos or [],
        }

    # Validation lien : `has_demo` True uniquement si vraie URL (http/https///,
    # ou www.). Email ou autre format non-cliquable → has_demo=False et lien=''.
    import re
    url_re = re.compile(r'^(https?://|//|www\.)', re.IGNORECASE)
    lien_raw = (projet.get('lien') or '').strip()
    if lien_raw and url_re.match(lien_raw):
        projet['lien']     = lien_raw
        projet['has_demo'] = True
    else:
        projet['lien']     = ''
        projet['has_demo'] = False

    # Couleur accent (mêmes règles que portfolio_public).
    modele  = candidat.portfolioModele if (candidat.portfolioModele and candidat.portfolioModele.actif) else None
    couleur = candidat.couleurPortfolio or (modele.couleurPrincipale if modele else '#F77F00')

    # Choix du template détail : `details/<fichier>.html` si présent (pour
    # rester graphiquement aligné avec le modèle de portfolio choisi),
    # sinon fallback sur `projet_detail.html` (template historique).
    fichier = modele.fichier if modele else DEFAULT_PORTFOLIO_FICHIER
    from django.template.loader import select_template
    template = select_template([
        f'candidat/portfolio/details/{fichier}.html',
        'candidat/portfolio/projet_detail.html',
    ])

    return render(request, template.template.name, {
        'candidat':       candidat,
        'projet':         projet,
        'projet_db_id':   projet_db.pk,
        'est_proprio':    request.candidat and request.candidat.id == candidat.id,
        'couleur_accent': couleur,
    })


# L'API de sauvegarde du portfolio est implémentée dans `views.py::api_sauvegarder_portfolio`
# (utilise ProfilPortfolioForm + sync des liens sociaux).


# ─── API Contact (envoi de message depuis le portfolio public) ───────────────

@require_POST
def api_portfolio_contact(request, candidat_id):
    """Reçoit un message depuis le formulaire de contact du portfolio public
    et l'envoie par email au candidat propriétaire.

    Body JSON :
        { "nom": "...", "email": "...", "sujet": "...", "message": "..." }

    Réponse JSON : { ok: bool, message: str }

    Garde-fous :
      - Le candidat doit exister et avoir un email.
      - Le portfolio doit être public (sinon 404 — cohérent avec la vue publique).
      - Validation minimale des champs (taille, format email).
    """
    candidat = get_object_or_404(Candidat, pk=candidat_id)

    # Pas d'email destinataire renseigné → pas de contact possible.
    if not candidat.email:
        return JsonResponse(
            {'ok': False, 'message': "Ce profil n'expose pas d'adresse email."},
            status=400,
        )

    # Portfolio privé → 404 (sauf propriétaire qui peut tester depuis sa propre preview).
    if not candidat.portfolioPublic:
        if not request.candidat or request.candidat.id != candidat.id:
            return JsonResponse({'ok': False, 'message': 'Portfolio non accessible.'}, status=404)

    # Parsing du body JSON
    try:
        payload = json.loads(request.body or '{}')
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'message': 'Données invalides.'}, status=400)

    nom     = (payload.get('nom') or '').strip()[:100]
    email   = (payload.get('email') or '').strip()[:150]
    sujet   = (payload.get('sujet') or '').strip()[:200]
    message = (payload.get('message') or '').strip()[:5000]

    # Validation minimale
    if not nom or len(nom) < 2:
        return JsonResponse({'ok': False, 'message': 'Veuillez renseigner votre nom.'}, status=400)
    if not email or '@' not in email or '.' not in email.rsplit('@', 1)[-1]:
        return JsonResponse({'ok': False, 'message': 'Adresse email invalide.'}, status=400)
    if not message or len(message) < 10:
        return JsonResponse({'ok': False, 'message': 'Le message doit faire au moins 10 caractères.'}, status=400)

    sujet_final = sujet or f"Message depuis votre portfolio — {nom}"
    body = (
        f"Bonjour {candidat.prenom},\n\n"
        f"Vous avez reçu un message depuis votre portfolio public :\n\n"
        f"De      : {nom} <{email}>\n"
        f"Sujet   : {sujet or '(sans sujet)'}\n"
        f"\n----- Message -----\n\n"
        f"{message}\n\n"
        f"-------------------\n"
        f"Pour répondre, écrivez directement à {email}.\n"
    )

    try:
        send_mail(
            subject       = sujet_final,
            message       = body,
            from_email    = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or email,
            recipient_list= [candidat.email],
            reply_to      = [email] if hasattr(send_mail, 'reply_to') else None,
            fail_silently = False,
        )
    except TypeError:
        # `send_mail` ne supporte pas reply_to → fallback EmailMessage
        from django.core.mail import EmailMessage
        EmailMessage(
            subject  = sujet_final,
            body     = body,
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or email,
            to       = [candidat.email],
            reply_to = [email],
        ).send(fail_silently=False)
    except Exception as exc:
        return JsonResponse(
            {'ok': False, 'message': f"Échec de l'envoi : {exc}"},
            status=500,
        )

    return JsonResponse({
        'ok': True,
        'message': f"Message envoyé à {candidat.prenom}. Une réponse arrivera à {email}.",
    })
