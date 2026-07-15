"""Public-facing pages (no auth required)."""
import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache as django_cache

from .. import app_messages as messages
from ..models import (
    Entreprise, Recruteur, OffreEmploi, StatutOffre, StatutCompte,
    TemoignageEntreprise, ConversationDirecte, InvitationEntretien,
    PartageProfilExterne, NotificationRecruteur,
)
from ..decorators import recruteur_ou_admin_required, bloque_roles
from candidat.models import Candidat, LogoSite
from candidat.visiteurs import enregistrer_visite
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


# ── Accueil ───────────────────────────────────────────────────────────────────

def accueil(request):
    from django.db.models import Count
    from django.db.models.functions import Lower

    # ── Donnees publiques (cachees 5 min) ────────────────────────────────
    stats_pub = django_cache.get('ent_accueil_stats')
    if stats_pub is None:
        stats_pub = {
            'nb_entreprises': Entreprise.objects.filter(statutCompte=StatutCompte.ACTIF).count(),
            'nb_offres':      OffreEmploi.objects.filter(statutOffre=StatutOffre.PUBLIEE).count(),
            'nb_recruteurs':  Recruteur.objects.filter(statutCompte=StatutCompte.ACTIF).count(),
        }
        django_cache.set('ent_accueil_stats', stats_pub, 300)

    stats_visiteurs = enregistrer_visite(request)

    # Stats propres a l'entreprise connectee (pour la carte flottante)
    nb_offres_ent = None
    nb_recruteurs_ent = None
    if getattr(request, 'entreprise', None):
        nb_offres_ent     = OffreEmploi.objects.filter(entreprise=request.entreprise, statutOffre=StatutOffre.PUBLIEE).count()
        nb_recruteurs_ent = Recruteur.objects.filter(entreprise=request.entreprise, statutCompte=StatutCompte.ACTIF).count()

    # ── Portfolios, villes, secteurs candidats (cache combiné 5 min) ────
    # Les 4 valeurs sont toujours invalidées ensemble (signal `Candidat`
    # post_save/post_delete, cf. candidat/signals.py::_invalider_cache_candidat)
    # — un seul aller-retour Redis au lieu de 4 pour les lire/écrire.
    donnees_candidats = django_cache.get('ent_accueil_candidats')
    if donnees_candidats is None:
        top_villes_candidats = list(
            _candidats_avec_portfolio()
            .exclude(informationPersonnelle__ville='')
            .exclude(informationPersonnelle__ville__isnull=True)
            .annotate(ville_lower=Lower('informationPersonnelle__ville'))
            .values('informationPersonnelle__ville', 'ville_lower')
            .annotate(nb=Count('id'))
            .order_by('-nb')[:8]
        )
        top_secteurs_candidats = list(
            _candidats_avec_portfolio()
            .exclude(secteurActivite='')
            .values('secteurActivite')
            .annotate(nb=Count('id'))
            .order_by('-nb')[:8]
        )
        donnees_candidats = {
            'portfolios_vedette': list(_candidats_avec_portfolio()[:6]),
            'nb_portfolios':      _candidats_avec_portfolio().count(),
            'top_villes':         top_villes_candidats,
            'top_secteurs':       top_secteurs_candidats,
        }
        django_cache.set('ent_accueil_candidats', donnees_candidats, 300)

    portfolios_vedette     = donnees_candidats['portfolios_vedette']
    nb_portfolios           = donnees_candidats['nb_portfolios']
    top_villes_candidats   = donnees_candidats['top_villes']
    top_secteurs_candidats = donnees_candidats['top_secteurs']

    temoignages = django_cache.get('ent_accueil_temoignages')
    if temoignages is None:
        temoignages = list(
            TemoignageEntreprise.objects
            .filter(statut=TemoignageEntreprise.STATUT_PUBLIE)
            .select_related('entreprise')
            .order_by('ordre', '-date_soumission')[:3]
        )
        django_cache.set('ent_accueil_temoignages', temoignages, 300)

    return render(request, 'entreprise/accueil.html', {
        'nb_entreprises':    stats_pub['nb_entreprises'],
        'nb_offres':         stats_pub['nb_offres'],
        'nb_recruteurs':     stats_pub['nb_recruteurs'],
        'nb_offres_ent':     nb_offres_ent,
        'nb_recruteurs_ent': nb_recruteurs_ent,
        'nb_visiteurs_jour': stats_visiteurs['nb_aujourd_hui'],
        'nb_visiteurs_30j':  stats_visiteurs['nb_30_jours'],
        'nb_visiteurs_365j': stats_visiteurs['nb_365_jours'],
        'portfolios_vedette': portfolios_vedette,
        'nb_portfolios':      nb_portfolios,
        'top_villes_candidats':    top_villes_candidats,
        'top_secteurs_candidats':  top_secteurs_candidats,
        'temoignages':             temoignages,
    })


def avis(request):
    """Liste complète des témoignages entreprises publiés."""
    import json

    from django.core.paginator import Paginator

    temoignages_qs = (
        TemoignageEntreprise.objects
        .filter(statut=TemoignageEntreprise.STATUT_PUBLIE)
        .select_related('entreprise')
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
            'pk':         t.pk,
            'prenom_nom': t.prenom_nom,
            'poste':      t.poste,
            'texte':      t.texte,
            'note':       t.note,
            'logo_url':   t.entreprise.logoEntreprise.url if t.entreprise and t.entreprise.logoEntreprise else '',
            'initiales':  t.prenom_nom[:2].upper(),
        }
        for t in page
    ]
    return render(request, 'entreprise/avis.html', {
        'page_obj':         page,
        'temoignages_json': json.dumps(items, ensure_ascii=False),
    })


def candidats_liste(request):
    """Liste des candidats avec portfolio public -- filtres serveur + pagination."""
    from django.core.paginator import Paginator
    from django.db.models import Q
    from referentiel.models import SecteurActivite, TypeMobilite as TypeMobiliteRef

    base_qs = _candidats_avec_portfolio()

    q        = request.GET.get('q', '').strip()
    secteur  = request.GET.get('secteur', '').strip()
    ville    = request.GET.get('ville', '').strip()
    contrat  = request.GET.get('contrat', '').strip()
    mobilite = request.GET.get('mobilite', '').strip()
    dispo    = request.GET.get('dispo', '').strip()
    tri      = request.GET.get('tri', 'recent')

    from referentiel.models import Contrat as ContratRef

    qs = base_qs
    if q:
        from recrutement.search import fts_filter
        qs = fts_filter(qs, q,
                        vector_fields=['prenom', 'nom', 'titreProfessionnel',
                                       'biographie', 'secteurActivite'],
                        fallback_lookups=[
                            'prenom__icontains', 'nom__icontains',
                            'titreProfessionnel__icontains',
                            'secteurActivite__icontains',
                            'secteurActiviteRef__nomSecteur__icontains',
                            'biographie__icontains',
                            'informationPersonnelle__ville__icontains',
                        ])
    if secteur:
        qs = qs.filter(secteurActiviteRef__id=secteur)
    if ville:
        qs = qs.filter(informationPersonnelle__ville__icontains=ville)
    if contrat:
        qs = qs.filter(typeContratRecherche__id=contrat)
    if mobilite:
        qs = qs.filter(typeMobilite__id=mobilite)
    if dispo == '1':
        qs = qs.filter(typeContratRecherche__isnull=False)

    if tri == 'alpha':
        qs = qs.order_by('prenom', 'nom')
    else:
        qs = qs.order_by('-date_joined')

    total = qs.count()

    # Options pour les menus deroulants (basees sur les candidats visibles)
    secteurs_ids = base_qs.exclude(secteurActiviteRef__isnull=True).values_list('secteurActiviteRef_id', flat=True).distinct()
    secteurs     = SecteurActivite.objects.filter(id__in=secteurs_ids).order_by('nomSecteur')

    contrats_ids = base_qs.exclude(typeContratRecherche__isnull=True).values_list('typeContratRecherche_id', flat=True).distinct()
    contrats     = ContratRef.objects.filter(id__in=contrats_ids).order_by('libelle')

    mobilites_ids = base_qs.exclude(typeMobilite__isnull=True).values_list('typeMobilite_id', flat=True).distinct()
    mobilites     = TypeMobiliteRef.objects.filter(id__in=mobilites_ids).order_by('libelle')

    paginator = Paginator(qs.select_related(
        'portfolioModele', 'informationPersonnelle', 'typeMobilite',
        'typeContratRecherche', 'secteurActiviteRef',
    ), 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    filtres_actifs = bool(q or secteur or ville or contrat or mobilite or dispo)

    return render(request, 'entreprise/candidats_liste.html', {
        'candidats':       page_obj,
        'page_obj':        page_obj,
        'total':           total,
        'total_tous':      base_qs.count(),
        'q':               q,
        'secteur':         secteur,
        'ville':           ville,
        'contrat':         contrat,
        'mobilite':        mobilite,
        'dispo':           dispo,
        'tri':             tri,
        'secteurs':        secteurs,
        'contrats':        contrats,
        'mobilites':       mobilites,
        'filtres_actifs':  filtres_actifs,
        'q_initial':       q,
    })


def voir_portfolio_candidat(request, candidat_id):
    """Affiche le portfolio d'un candidat dans l'espace entreprise."""
    if request.entreprise is None and getattr(request, 'recruteur', None) is None:
        messages.info(
            request,
            "Connectez-vous en tant que recruteur pour consulter le portfolio des candidats.",
        )
        return redirect(f"{reverse('entreprise:recruteur_connexion')}?next={request.path}")

    from candidat.portfolio import _render_portfolio

    extra = {}
    recruteur = getattr(request, 'recruteur', None)
    depuis_suggestions = bool(request.GET.get('depuis_suggestions'))
    if recruteur or request.entreprise:
        from django.db.models import Q as _Q
        if recruteur:
            offres_filter = _Q(creePar=recruteur) | _Q(recruteurs_createurs__recruteur=recruteur)
        else:
            offres_filter = _Q(entreprise=request.entreprise)
        extra['offres_pour_invitation'] = list(
            OffreEmploi.objects.filter(offres_filter, statutOffre='PUBLIEE')
            .distinct().values('id', 'titre').order_by('titre')
        )
        if not depuis_suggestions:
            if recruteur:
                extra['conv_existante'] = ConversationDirecte.objects.filter(
                    recruteur=recruteur, candidat_id=candidat_id
                ).values_list('id', flat=True).first()
            else:
                extra['conv_existante'] = ConversationDirecte.objects.filter(
                    recruteur__entreprise=request.entreprise, candidat_id=candidat_id
                ).values_list('id', flat=True).first()
    if depuis_suggestions:
        extra['masquer_messagerie'] = True
        # Si l'offre est passee en parametre, on la valide et on l'injecte
        try:
            offre_auto = OffreEmploi.objects.get(
                pk=request.GET.get('offre'),
                entreprise=recruteur.entreprise if recruteur else request.entreprise,
                statutOffre='PUBLIEE',
            )
            extra['offre_auto_id'] = offre_auto.pk
        except (OffreEmploi.DoesNotExist, ValueError, TypeError):
            pass

    # Notifier le candidat si la preference est activee
    _notifier_profil_consulte(request, candidat_id)

    # Bouton de partage externe : ADMIN / RH / MANAGER uniquement
    peut_partager = False
    if recruteur and getattr(recruteur, 'roleMembre', None) not in ('LECTEUR',):
        peut_partager = True
    elif request.entreprise:
        peut_partager = True
    extra['peut_partager']      = peut_partager
    extra['candidat_partage_id'] = candidat_id

    return _render_portfolio(request, candidat_id, base_template='entreprise/base.html', **extra)


def _notifier_profil_consulte(request, candidat_id):
    """Cree une notification in-app + envoie un email au candidat quand un recruteur
    visite son portfolio.

    Anti-spam : 1 notification in-app + 1 email par entreprise par candidat par 24h.
    Ne fait rien si le candidat n'a pas active la preference `profil_consulte`.
    """
    try:
        import logging
        _log = logging.getLogger('candidat.profil_vu')
        from candidat.models import Candidat, NotificationCandidat, AbonneNewsletter
        from datetime import timedelta

        candidat = Candidat.objects.select_related('abonnement_newsletter').filter(pk=candidat_id).first()
        if not candidat:
            return

        # Verifier la preference newsletter
        abonnement = getattr(candidat, 'abonnement_newsletter', None)
        if not abonnement or not abonnement.actif or not abonnement.profil_consulte:
            return

        # Identifier la source
        recruteur  = getattr(request, 'recruteur', None)
        entreprise = getattr(request, 'entreprise', None)

        if recruteur and recruteur.entreprise:
            entreprise_obj = recruteur.entreprise
            entreprise_nom = entreprise_obj.raisonSocial
            entreprise_pk  = entreprise_obj.pk
        elif entreprise:
            entreprise_nom = entreprise.raisonSocial
            entreprise_pk  = entreprise.pk
        else:
            return

        # Anti-spam : 1 notif par entreprise par candidat par 24h
        # On stocke l'ID de l'entreprise dans `score` pour le filtrage
        depuis = timezone.now() - timedelta(hours=24)
        deja_notifie = NotificationCandidat.objects.filter(
            candidat=candidat,
            type=NotificationCandidat.Type.PROFIL_VU,
            score=entreprise_pk,
            dateCreation__gte=depuis,
        ).exists()

        if deja_notifie:
            return

        # ── Notification in-app ────────────────────────────────────────────
        notif = NotificationCandidat.objects.create(
            candidat=candidat,
            type=NotificationCandidat.Type.PROFIL_VU,
            titre='Votre profil a été consulté',
            message=f'{entreprise_nom} a consulté votre portfolio.',
            lien=f'/candidat/entreprises/{entreprise_pk}/',  # -> page profil de l'entreprise
            score=entreprise_pk,                              # Utilise pour l'anti-spam
        )

        # ── Email ──────────────────────────────────────────────────────────
        from candidat.models import LogoSite
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string

        logo_site  = LogoSite.get_actif()
        site_url   = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
        desabo_url = f'{site_url}/candidat/newsletter/desabonnement/{abonnement.token_desabonnement}/'

        ctx = {
            'logo_site':      logo_site,
            'candidat':       candidat,
            'entreprise_nom': entreprise_nom,
            'site_url':       site_url,
            'desabo_url':     desabo_url,
        }

        sujet = f'👀 Votre profil a été consulté — {logo_site.nom_site}'
        txt   = (
            f'Bonjour {candidat.prenom},\n\n'
            f'{entreprise_nom} a consulté votre portfolio.\n\n'
            f'Accédez à votre espace : {site_url}/candidat/dashboard/\n\n'
            f'Pour gérer vos préférences : {desabo_url}'
        )
        html = render_to_string('candidat/newsletter/email_profil_consulte.html', ctx)

        msg = EmailMultiAlternatives(subject=sujet, body=txt, to=[candidat.email])
        msg.attach_alternative(html, 'text/html')
        msg.send(fail_silently=True)

        notif.emailEnvoye   = True
        notif.emailEnvoyeAt = timezone.now()
        notif.save(update_fields=['emailEnvoye', 'emailEnvoyeAt'])

    except Exception as _e:
        # Ne jamais bloquer l'affichage du portfolio -- mais logger l'erreur
        import logging
        logging.getLogger('candidat.profil_vu').warning(
            'Erreur _notifier_profil_consulte (candidat_id=%s) : %s', candidat_id, _e
        )


def _candidats_avec_portfolio():
    """Candidats avec portfolio public ET un modele de portfolio choisi.

    Tries par date d'inscription decroissante. Permet a l'entreprise de
    parcourir les profils visibles publiquement.
    """
    return (
        Candidat.objects
        .filter(portfolioPublic=True, portfolioModele__isnull=False)
        .select_related('portfolioModele', 'informationPersonnelle', 'typeMobilite',
                        'typeContratRecherche')
        .order_by('-date_joined')
    )


# ── Partage de profil candidat vers entreprise externe ───────────────────────

@recruteur_ou_admin_required
@bloque_roles('LECTEUR')
def partage_creer(request, candidat_id):
    """Genere un lien de partage du profil candidat pour une entreprise tierce."""
    from candidat.models import Candidat
    from ..models import PartageProfilExterne

    candidat = get_object_or_404(Candidat, pk=candidat_id)
    rec = request.recruteur
    ent_admin = request.entreprise if not rec else None
    nom_entreprise = rec.entreprise.raisonSocial if rec else (request.entreprise.raisonSocial if request.entreprise else '')

    if request.method == 'POST':
        email = request.POST.get('email_destinataire', '').strip()
        message = request.POST.get('message', '').strip()

        partage = PartageProfilExterne.objects.create(
            recruteur=rec,
            entreprise_partageur=ent_admin,
            candidat=candidat,
            email_destinataire=email,
            message=message,
        )

        lien = partage.get_url_absolue(request)

        # Envoi email si destinataire renseigne
        if email:
            logo_site = LogoSite.get_actif()
            nom_site  = logo_site.nom_site
            sujet = f"{nom_entreprise} vous partage un profil candidat"
            corps_texte = (
                f"Bonjour,\n\n"
                f"{nom_entreprise} vous invite à consulter le profil d'un candidat "
                f"sélectionné pour vous.\n\n"
                f"{message}\n\n"
                f"Voir le profil : {lien}\n\n"
                f"Ce lien est valable 30 jours.\n\n"
                f"— L'équipe {nom_site}"
            )
            corps_html = render_to_string(
                'entreprise/emails/partage_profil.html',
                {'nom_entreprise': nom_entreprise, 'message_partage': message,
                 'lien': lien, 'logo_site': logo_site},
            )
            msg_email = EmailMultiAlternatives(
                subject=sujet,
                body=corps_texte,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email],
            )
            msg_email.attach_alternative(corps_html, 'text/html')
            msg_email.send(fail_silently=True)

        return JsonResponse({'ok': True, 'lien': lien, 'token': str(partage.token)})

    return JsonResponse({'error': 'Méthode non autorisée.'}, status=405)


@recruteur_ou_admin_required
def partages_liste(request):
    """Liste des liens de partage crees par le recruteur connecte."""
    from ..models import PartageProfilExterne
    if request.recruteur:
        partages = PartageProfilExterne.objects.filter(
            recruteur=request.recruteur
        )
    else:
        partages = PartageProfilExterne.objects.filter(
            entreprise_partageur=request.entreprise
        )
    partages = partages.select_related('candidat').order_by('-date_creation')
    return render(request, 'entreprise/partages/liste.html', {'partages': partages})


@recruteur_ou_admin_required
@require_POST
def partage_desactiver(request, token):
    """Desactive un lien de partage (revocation immediate)."""
    from ..models import PartageProfilExterne
    if request.recruteur:
        partage = get_object_or_404(PartageProfilExterne, token=token, recruteur=request.recruteur)
    else:
        partage = get_object_or_404(PartageProfilExterne, token=token, entreprise_partageur=request.entreprise)
    partage.actif = False
    partage.save(update_fields=['actif'])
    return JsonResponse({'ok': True})


def profil_partage_public(request, token):
    """Vue publique du profil candidat partage -- accessible sans authentification."""
    from ..models import PartageProfilExterne
    from candidat.portfolio import _render_portfolio

    partage = get_object_or_404(PartageProfilExterne, token=token)

    if not partage.est_valide:
        return render(request, 'entreprise/partages/profil_expire.html', {
            'expire': partage.est_expire,
            'desactive': not partage.actif,
        })

    partage.enregistrer_vue()

    entreprise_partageuse = partage.recruteur.entreprise if partage.recruteur else partage.entreprise_partageur

    return _render_portfolio(
        request,
        partage.candidat_id,
        base_template='entreprise/partages/base_partage_public.html',
        ignorer_visibilite=True,
        masquer_contact=True,
        partage=partage,
        entreprise_partageuse=entreprise_partageuse,
    )
