"""Dashboard & profile management views."""
import logging
import json
from datetime import timedelta

from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from .. import app_messages as messages
from ..models import (
    Entreprise, Recruteur, OffreEmploi, StatutOffre,
    StatutCompte, RoleMembre, SECTEURS, TAILLES, DEVISES,
    StatutVerification, TokenVerificationEmail, DemandeVerification, StatutDemande,
    TemoignageEntreprise, NotificationRecruteur, InvitationEntretien,
    ParametreEntreprise,
)
from ..decorators import entreprise_required, recruteur_required, recruteur_ou_admin_required
from candidat.models import Candidat, Candidature, Entretien, LogoSite
from ._helpers import _valider_fichier_image

logger = logging.getLogger(__name__)


# ── Tableau de bord ───────────────────────────────────────────────────────────

@entreprise_required
def tableau_bord(request):
    ent = request.entreprise
    demande_en_cours = DemandeVerification.objects.filter(
        entreprise=ent, statut=StatutDemande.EN_ATTENTE
    ).first()
    derniere_demande = DemandeVerification.objects.filter(
        entreprise=ent
    ).order_by('-date_soumission').first()
    suggestions_non_lues = NotificationRecruteur.objects.filter(
        recruteur__entreprise=ent,
        type=NotificationRecruteur.Type.SUGGESTION_COLLEGUE,
        lue=False,
    ).count()

    # ── Statistiques calculees en temps reel ──────────────────────────────
    offres_actives     = OffreEmploi.objects.filter(
        entreprise=ent, statutOffre=StatutOffre.PUBLIEE
    ).count()

    total_candidatures = Candidature.objects.filter(
        offre__entreprise=ent
    ).count()

    candidatures_7j    = Candidature.objects.filter(
        offre__entreprise=ent,
        dateCandidature__gte=timezone.now() - timedelta(days=7),
    ).count()

    membres_actifs     = Recruteur.objects.filter(
        entreprise=ent, estActif=True
    ).count()

    offres_expirees    = OffreEmploi.objects.filter(
        entreprise=ent, statutOffre=StatutOffre.EXPIREE
    ).count()

    # ── Donnees graphiques ──────────────────────────────────────────────────
    today = timezone.localdate()
    date_debut_30j = today - timedelta(days=29)

    # Courbe candidatures -- 30 derniers jours
    cand_par_jour = (
        Candidature.objects
        .filter(offre__entreprise=ent, dateCandidature__date__gte=date_debut_30j)
        .annotate(jour=TruncDate('dateCandidature'))
        .values('jour')
        .annotate(nb=Count('id'))
        .order_by('jour')
    )
    cand_dict = {row['jour']: row['nb'] for row in cand_par_jour}
    jours_30 = [date_debut_30j + timedelta(days=i) for i in range(30)]
    chart_cand_labels = json.dumps([j.strftime('%d/%m') for j in jours_30])
    chart_cand_data   = json.dumps([cand_dict.get(j, 0) for j in jours_30])

    # Donut statuts candidatures
    statuts_qs = (
        Candidature.objects
        .filter(offre__entreprise=ent)
        .values('statut__libelle')
        .annotate(nb=Count('id'))
        .order_by('-nb')
    )
    chart_statuts_labels = json.dumps([s['statut__libelle'] or 'En attente' for s in statuts_qs])
    chart_statuts_data   = json.dumps([s['nb'] for s in statuts_qs])

    # Bar chart offres par statut
    offres_par_statut = (
        OffreEmploi.objects
        .filter(entreprise=ent)
        .values('statutOffre')
        .annotate(nb=Count('id'))
    )
    smap = {o['statutOffre']: o['nb'] for o in offres_par_statut}
    chart_offres_data = json.dumps([
        smap.get('PUBLIEE',   0),
        smap.get('BROUILLON', 0),
        smap.get('EXPIREE',   0),
        smap.get('POURVUE',   0),
        smap.get('FERMEE',    0),
    ])

    # Funnel de recrutement
    nb_recues      = total_candidatures
    nb_traitees    = Candidature.objects.filter(
        offre__entreprise=ent,
    ).exclude(statut__code='POSTULEE').exclude(statut__isnull=True).count()
    nb_planifies   = Candidature.objects.filter(
        offre__entreprise=ent,
        entretiens__isnull=False,
    ).distinct().count()
    nb_realises    = Entretien.objects.filter(
        candidature__offre__entreprise=ent,
        statut=Entretien.StatutEntretien.REALISE,
    ).values('candidature').distinct().count()
    chart_funnel_data = json.dumps([nb_recues, nb_traitees, nb_planifies, nb_realises])

    # Top 5 offres par candidatures
    top_offres_qs = (
        Candidature.objects
        .filter(offre__entreprise=ent)
        .values('offre__titre')
        .annotate(nb=Count('id'))
        .order_by('-nb')[:5]
    )
    chart_top_labels = json.dumps([o['offre__titre'] for o in top_offres_qs])
    chart_top_data   = json.dumps([o['nb'] for o in top_offres_qs])

    return render(request, 'entreprise/tableau_bord.html', {
        'demande_en_cours':     demande_en_cours,
        'derniere_demande':     derniere_demande,
        'suggestions_non_lues': suggestions_non_lues,
        'stat_offres_actives':  offres_actives,
        'stat_candidatures':    total_candidatures,
        'stat_candidatures_7j': candidatures_7j,
        'stat_membres':         membres_actifs,
        'stat_offres_expirees': offres_expirees,
        'stat_score':           ent.scorePertinence,
        'chart_cand_labels':    chart_cand_labels,
        'chart_cand_data':      chart_cand_data,
        'chart_statuts_labels': chart_statuts_labels,
        'chart_statuts_data':   chart_statuts_data,
        'chart_offres_data':    chart_offres_data,
        'chart_funnel_data':    chart_funnel_data,
        'chart_top_labels':     chart_top_labels,
        'chart_top_data':       chart_top_data,
    })


# ── Profil ────────────────────────────────────────────────────────────────────

@entreprise_required
def profil(request):
    ent = request.entreprise
    demande_en_cours = DemandeVerification.objects.filter(
        entreprise=ent, statut=StatutDemande.EN_ATTENTE
    ).first()
    derniere_demande = DemandeVerification.objects.filter(
        entreprise=ent
    ).order_by('-date_soumission').first()
    code_email_actif = (
        not ent.emailVerifie
        and TokenVerificationEmail.objects.filter(
            entreprise=ent, utilise=False,
            date_expiration__gt=timezone.now(),
        ).exists()
    )
    temoignage_ent = TemoignageEntreprise.objects.filter(entreprise=ent).first()
    temoignage_init = {
        'statut': temoignage_ent.statut if temoignage_ent else '',
        'texte':  temoignage_ent.texte  if temoignage_ent else '',
        'note':   temoignage_ent.note   if temoignage_ent else 5,
        'poste':  temoignage_ent.poste  if temoignage_ent else '',
    }

    return render(request, 'entreprise/profil.html', {
        'secteurs':         SECTEURS,
        'tailles':          TAILLES,
        'demande_en_cours': demande_en_cours,
        'derniere_demande': derniere_demande,
        'code_email_actif': code_email_actif,
        'temoignage_init':  temoignage_init,
    })


@entreprise_required
@require_POST
def api_soumettre_temoignage_entreprise(request):
    """Cree ou met a jour le temoignage de l'entreprise connectee (statut -> en_attente)."""
    ent = request.entreprise
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'message': 'Données invalides.'}, status=400)

    texte = (data.get('texte') or '').strip()
    poste = (data.get('poste') or '').strip()
    try:
        note = max(1, min(5, int(data.get('note', 5))))
    except (TypeError, ValueError):
        note = 5

    if not texte:
        return JsonResponse({'ok': False, 'message': 'Le témoignage ne peut pas être vide.'})

    prenom_nom = ent.raisonSocial or str(ent)

    TemoignageEntreprise.objects.update_or_create(
        entreprise=ent,
        defaults={
            'prenom_nom': prenom_nom,
            'poste':      poste,
            'texte':      texte,
            'note':       note,
            'source':     TemoignageEntreprise.SOURCE_ENTREPRISE,
            'statut':     TemoignageEntreprise.STATUT_EN_ATTENTE,
        },
    )

    return JsonResponse({
        'ok':      True,
        'message': 'Votre témoignage a été soumis et sera visible après validation par l\'administration.',
        'statut':  TemoignageEntreprise.STATUT_EN_ATTENTE,
    })


@entreprise_required
def modifier_profil(request):
    if request.method != 'POST':
        return redirect('entreprise:profil')

    ent  = request.entreprise
    data = request.POST

    if not data.get('raisonSocial', '').strip():
        messages.error(request, 'La raison sociale est obligatoire.')
        return redirect('entreprise:profil')

    if 'logoEntreprise' in request.FILES:
        logo = request.FILES['logoEntreprise']
        try:
            _valider_fichier_image(logo, max_mo=2)
        except ValidationError as e:
            messages.error(request, f'Logo invalide : {e.message}')
            return redirect('entreprise:profil')
        ent.logoEntreprise = logo

    champs = [
        'raisonSocial', 'registreCommerce', 'idu', 'description',
        'secteurActivite', 'tailleEntreprise', 'siteWeb',
        'telephone', 'emailContact', 'adresse', 'ville', 'pays', 'codePostal',
    ]
    for champ in champs:
        if champ in data:
            setattr(ent, champ, data[champ].strip() if isinstance(data[champ], str) else data[champ])

    ent.save()
    ent.calculerScorePertinence()
    messages.success(request, 'Profil mis à jour avec succès.')
    return redirect('entreprise:profil')


@entreprise_required
def changer_mot_de_passe(request):
    if request.method != 'POST':
        return redirect('entreprise:profil')

    ancien    = request.POST.get('ancienMotPasse', '')
    nouveau   = request.POST.get('nouveauMotPasse', '')
    confirmer = request.POST.get('confirmerMotPasse', '')

    if not request.entreprise.check_password(ancien):
        messages.error(request, 'Ancien mot de passe incorrect.')
        return redirect('entreprise:profil')
    if len(nouveau) < 8:
        messages.error(request, 'Le nouveau mot de passe doit contenir au moins 8 caractères.')
        return redirect('entreprise:profil')
    if nouveau != confirmer:
        messages.error(request, 'Les nouveaux mots de passe ne correspondent pas.')
        return redirect('entreprise:profil')

    request.entreprise.changerMotDePasse(ancien, nouveau)
    messages.success(request, 'Mot de passe changé avec succès.')
    return redirect('entreprise:profil')


# ── Verification email ────────────────────────────────────────────────────────

def _profil_verification_url():
    return f"{reverse('entreprise:profil')}?tab=verification"


@entreprise_required
@require_POST
def envoyer_verification_email(request):
    ent = request.entreprise
    if ent.emailVerifie:
        messages.info(request, 'Votre email est déjà vérifié.')
        return redirect(_profil_verification_url())

    TokenVerificationEmail.objects.filter(entreprise=ent, utilise=False).update(utilise=True)

    code = TokenVerificationEmail.generer_code()
    TokenVerificationEmail.objects.create(entreprise=ent, code=code)

    logo_site = LogoSite.get_actif()
    nom_site  = logo_site.nom_site
    try:
        html = render_to_string('entreprise/emails/verification_email.html', {
            'entreprise': ent,
            'code':       code,
            'logo_site':  logo_site,
        })
        send_mail(
            subject=f'Code de vérification de votre email — {nom_site}',
            message=(
                f"Bonjour {ent.raisonSocial},\n\n"
                f"Votre code de vérification est : {code}\n\n"
                f"Saisissez-le sur votre profil pour valider votre email.\n"
                f"Ce code est valide 15 minutes.\n\n"
                f"L'équipe {nom_site}"
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@recrute-pro.ci'),
            recipient_list=[ent.emailProfessionnel],
            html_message=html,
            fail_silently=False,
        )
        messages.success(request,
            f'Code envoyé à {ent.emailProfessionnel}. Saisissez-le ci-dessous (valide 15 min).')
    except Exception:
        messages.info(request,
            f'Mode développement — code de vérification : {code}')

    return redirect(_profil_verification_url())


@entreprise_required
@require_POST
@ratelimit(key='ip', rate='7/m', method='POST', block=False)
def verifier_code_email(request):
    if getattr(request, 'limited', False):
        messages.error(request, 'Trop de tentatives. Réessayez dans une minute.')
        return redirect('entreprise:profil')
    ent = request.entreprise

    if ent.emailVerifie:
        messages.info(request, 'Votre email est déjà vérifié.')
        return redirect(_profil_verification_url())

    code_saisi = request.POST.get('code', '').strip()
    if not code_saisi or not code_saisi.isdigit() or len(code_saisi) != 6:
        messages.error(request, 'Veuillez saisir le code à 6 chiffres reçu par email.')
        return redirect(_profil_verification_url())

    token_obj = (
        TokenVerificationEmail.objects
        .filter(entreprise=ent, utilise=False)
        .order_by('-date_creation')
        .first()
    )

    if not token_obj or not token_obj.est_valide():
        messages.error(request,
            'Aucun code valide. Demandez un nouveau code de vérification.')
        return redirect(_profil_verification_url())

    if token_obj.code != code_saisi:
        messages.error(request, 'Code incorrect. Vérifiez votre email et réessayez.')
        return redirect(_profil_verification_url())

    with transaction.atomic():
        token_obj.utilise = True
        token_obj.save(update_fields=['utilise'])

        ent.emailVerifie = True
        ent.save(update_fields=['emailVerifie'])
    ent.calculerScorePertinence()

    messages.success(request,
        'Email vérifié avec succès ! Votre score de profil a augmenté de 20 points.')
    return redirect(_profil_verification_url())


@entreprise_required
@require_POST
def soumettre_demande_verification(request):
    from ._helpers import _valider_fichier_document
    ent = request.entreprise

    if ent.statutVerification == StatutVerification.VERIFIE:
        messages.info(request, 'Votre compte est déjà vérifié.')
        return redirect('entreprise:profil')

    if DemandeVerification.objects.filter(
            entreprise=ent, statut=StatutDemande.EN_ATTENTE).exists():
        messages.warning(request, "Une demande de vérification est déjà en cours d'examen.")
        return redirect('entreprise:profil')

    demande = DemandeVerification(
        entreprise=ent,
        notes_entreprise=request.POST.get('message', '').strip(),
    )

    for champ, label in [('document_rccm', 'RCCM'), ('document_identite', "pièce d'identité")]:
        if champ in request.FILES:
            f = request.FILES[champ]
            try:
                _valider_fichier_document(f, max_mo=5)
            except ValidationError as e:
                messages.error(request, f'Document {label} invalide : {e.message}')
                return redirect('entreprise:profil')
            setattr(demande, champ, f)

    demande.save()

    # Si precedemment rejete, remettre EN_ATTENTE pour permettre une nouvelle demande
    if ent.statutVerification == StatutVerification.REJETE:
        ent.statutVerification = StatutVerification.EN_ATTENTE
        ent.save(update_fields=['statutVerification'])

    # ── Notification admin ───────────────────────────────────────────────────
    from django.core.mail import mail_admins
    try:
        admin_url = request.build_absolute_uri(
            reverse('admin:entreprise_demandeverification_reviser', args=[demande.pk])
        )
        mail_admins(
            subject=f'[{LogoSite.get_actif().nom_site}] Nouvelle demande de vérification — {ent.raisonSocial}',
            message=(
                f'Une nouvelle demande de vérification a été soumise.\n\n'
                f'Entreprise : {ent.raisonSocial}\n'
                f'Email      : {ent.emailProfessionnel}\n'
                f'RCCM       : {"Oui" if demande.document_rccm else "Non"}\n'
                f'Identité   : {"Oui" if demande.document_identite else "Non"}\n\n'
                f'Réviser : {admin_url}'
            ),
            fail_silently=True,
        )
    except Exception:
        pass  # Ne jamais bloquer l'utilisateur sur l'envoi de notification

    messages.success(request,
        'Votre demande de vérification a été soumise. '
        "Notre équipe l'examinera dans les 2 à 5 jours ouvrables.")
    return redirect('entreprise:profil')


# ── Recruteur dashboard & profil ──────────────────────────────────────────────

@recruteur_required
def recruteur_tableau_bord(request):
    from candidat.models import Candidature, Entretien
    from .offres import _offres_visibles
    rec = request.recruteur
    now = timezone.now()
    today = timezone.localdate()

    offres_qs = _offres_visibles(request)

    candidatures_qs = Candidature.objects.filter(offre__in=offres_qs)

    # ── Stats cards ───────────────────────────────────────────────────────
    nb_offres_actives  = offres_qs.filter(statutOffre=StatutOffre.PUBLIEE).count()
    nb_en_attente      = candidatures_qs.filter(statut__code='POSTULEE').count()

    # Pour l'ADMIN : compteur perso (ses offres) + total entreprise
    nb_en_attente_perso = None
    nb_en_attente_total = None
    if rec.roleMembre == RoleMembre.ADMIN:
        from django.db.models import Q as _Q2
        offres_perso = OffreEmploi.objects.filter(
            _Q2(creePar=rec) | _Q2(recruteurs_createurs__recruteur=rec),
            entreprise=rec.entreprise,
        ).distinct()
        nb_en_attente_perso = Candidature.objects.filter(
            offre__in=offres_perso, statut__code='POSTULEE',
        ).count()
        nb_en_attente_total = Candidature.objects.filter(
            offre__entreprise=rec.entreprise, statut__code='POSTULEE',
        ).count()
    nb_entretiens_jour = Entretien.objects.filter(
        candidature__offre__in=offres_qs,
        statut='PLANIFIE',
        dateEntretien__date=today,
    ).count()
    nb_entretiens_semaine = Entretien.objects.filter(
        candidature__offre__in=offres_qs,
        statut='PLANIFIE',
        dateEntretien__date__gte=today,
        dateEntretien__date__lte=today + timedelta(days=7),
    ).count()

    stats = {
        'mes_offres':           nb_offres_actives,
        'candidatures':         nb_en_attente,
        'candidatures_perso':   nb_en_attente_perso,
        'candidatures_total':   nb_en_attente_total,
        'entretiens_jour':      nb_entretiens_jour,
        'entretiens_semaine':   nb_entretiens_semaine,
    }

    LIMIT = 4  # nombre d'items affiches par section

    # ── Entretiens du jour (liste) ────────────────────────────────────────
    _ej_qs = Entretien.objects.filter(
        candidature__offre__in=offres_qs,
        statut='PLANIFIE',
        dateEntretien__date=today,
    ).select_related('candidature__candidat', 'candidature__offre').order_by('dateEntretien')
    entretiens_aujourd_hui      = _ej_qs[:LIMIT]
    entretiens_aujourd_hui_plus = max(0, _ej_qs.count() - LIMIT)

    # ── Candidatures nouvelles (dernieres 48h) ────────────────────────────
    _rec_qs = candidatures_qs.filter(
        dateCandidature__gte=now - timedelta(hours=48),
    ).select_related('candidat', 'offre').order_by('-dateCandidature')
    candidatures_recentes      = _rec_qs[:LIMIT]
    candidatures_recentes_plus = max(0, _rec_qs.count() - LIMIT)

    # ── Candidatures urgentes (en attente > 5 jours) ──────────────────────
    _urg_qs = candidatures_qs.filter(
        statut__code='POSTULEE',
        dateCandidature__lte=now - timedelta(days=5),
    ).select_related('candidat', 'offre').order_by('dateCandidature')
    candidatures_urgentes      = _urg_qs[:LIMIT]
    candidatures_urgentes_plus = max(0, _urg_qs.count() - LIMIT)

    # ── Prochains entretiens (7 jours) ────────────────────────────────────
    _pe_qs = Entretien.objects.filter(
        candidature__offre__in=offres_qs,
        statut='PLANIFIE',
        dateEntretien__date__gt=today,
        dateEntretien__date__lte=today + timedelta(days=7),
    ).select_related('candidature__candidat', 'candidature__offre').order_by('dateEntretien')
    prochains_entretiens      = _pe_qs[:LIMIT]
    prochains_entretiens_plus = max(0, _pe_qs.count() - LIMIT)

    from ..models import NotificationRecruteur
    suggestions_non_lues = NotificationRecruteur.objects.filter(
        recruteur=rec,
        type=NotificationRecruteur.Type.SUGGESTION_COLLEGUE,
        lue=False,
    ).count()

    return render(request, 'entreprise/recruteur/tableau_bord.html', {
        'stats':                   stats,
        'suggestions_non_lues':    suggestions_non_lues,
        'entretiens_aujourd_hui':       entretiens_aujourd_hui,
        'entretiens_aujourd_hui_plus':  entretiens_aujourd_hui_plus,
        'candidatures_recentes':        candidatures_recentes,
        'candidatures_recentes_plus':   candidatures_recentes_plus,
        'candidatures_urgentes':        candidatures_urgentes,
        'candidatures_urgentes_plus':   candidatures_urgentes_plus,
        'prochains_entretiens':         prochains_entretiens,
        'prochains_entretiens_plus':    prochains_entretiens_plus,
        'today':                        today,
    })


@recruteur_required
def recruteur_profil(request):
    return render(request, 'entreprise/recruteur/profil.html')


@recruteur_required
def recruteur_modifier_profil(request):
    if request.method != 'POST':
        return redirect('entreprise:recruteur_profil')

    rec  = request.recruteur
    data = request.POST

    if not data.get('nomComplet', '').strip():
        messages.error(request, 'Le nom complet est obligatoire.')
        return redirect('entreprise:recruteur_profil')

    if 'photoProfil' in request.FILES:
        photo = request.FILES['photoProfil']
        try:
            _valider_fichier_image(photo, max_mo=2)
        except ValidationError as e:
            messages.error(request, f'Photo invalide : {e.message}')
            return redirect('entreprise:recruteur_profil')
        rec.photoProfil = photo

    for champ in ['nomComplet', 'telephone']:
        if champ in data:
            setattr(rec, champ, data[champ].strip())

    date_emb = data.get('dateEmbauche', '').strip()
    if date_emb:
        rec.dateEmbauche = date_emb

    rec.save()
    messages.success(request, 'Profil mis à jour avec succès.')
    return redirect('entreprise:recruteur_profil')


@entreprise_required
@require_POST
def entreprise_preferences(request):
    """Mise a jour des preferences de confidentialite de l'admin entreprise."""
    ent = request.entreprise

    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'erreur': 'JSON invalide.'}, status=400)
    else:
        data = request.POST

    def _bool(val):
        if isinstance(val, bool):
            return val
        if val is None:
            return False
        return str(val).lower() in ('1', 'true', 'on', 'yes', 'oui')

    ent.recevoirNotifsATS      = _bool(data.get('recevoirNotifsATS'))
    ent.recevoirNotifsATSEmail = _bool(data.get('recevoirNotifsATSEmail'))
    ent.save(update_fields=['recevoirNotifsATS', 'recevoirNotifsATSEmail'])

    return JsonResponse({
        'ok':                       True,
        'recevoirNotifsATS':        ent.recevoirNotifsATS,
        'recevoirNotifsATSEmail':   ent.recevoirNotifsATSEmail,
    })


@recruteur_required
@require_POST
def recruteur_preferences(request):
    """Mise a jour des preferences de confidentialite / notifications du recruteur."""
    rec = request.recruteur

    # Lecture compatible form-encoded ou JSON
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'erreur': 'JSON invalide.'}, status=400)
    else:
        data = request.POST

    def _bool(val):
        if isinstance(val, bool):
            return val
        if val is None:
            return False
        return str(val).lower() in ('1', 'true', 'on', 'yes', 'oui')

    rec.recevoirNotifsATS      = _bool(data.get('recevoirNotifsATS'))
    rec.recevoirNotifsATSEmail = _bool(data.get('recevoirNotifsATSEmail'))
    rec.save(update_fields=['recevoirNotifsATS', 'recevoirNotifsATSEmail'])

    return JsonResponse({
        'ok':                       True,
        'recevoirNotifsATS':        rec.recevoirNotifsATS,
        'recevoirNotifsATSEmail':   rec.recevoirNotifsATSEmail,
    })


@recruteur_required
def recruteur_changer_mdp(request):
    if request.method != 'POST':
        return redirect('entreprise:recruteur_profil')

    ancien    = request.POST.get('ancienMotPasse', '')
    nouveau   = request.POST.get('nouveauMotPasse', '')
    confirmer = request.POST.get('confirmerMotPasse', '')

    if not request.recruteur.check_password(ancien):
        messages.error(request, 'Ancien mot de passe incorrect.')
    elif len(nouveau) < 8:
        messages.error(request, 'Le nouveau mot de passe doit contenir au moins 8 caractères.')
    elif nouveau != confirmer:
        messages.error(request, 'Les nouveaux mots de passe ne correspondent pas.')
    else:
        request.recruteur.changerMotDePasse(ancien, nouveau)
        messages.success(request, 'Mot de passe changé avec succès.')

    return redirect('entreprise:recruteur_profil')
