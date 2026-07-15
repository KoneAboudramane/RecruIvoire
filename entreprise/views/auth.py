import logging
import json

from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from .. import app_messages as messages
from ..models import (
    Entreprise, Recruteur, ParametreEntreprise,
    StatutCompte, RoleMembre,
    TokenReinitialisationEntreprise,
    SECTEURS, TAILLES,
)
from candidat.models import LogoSite

logger = logging.getLogger(__name__)


# ── Inscription ───────────────────────────────────────────────────────────────

def inscription(request):
    if request.entreprise:
        return redirect('entreprise:tableau_bord')

    if request.method == 'POST':
        data   = request.POST
        errors = {}

        raison_social = data.get('raisonSocial', '').strip()
        email         = data.get('emailProfessionnel', '').strip().lower()
        mdp           = data.get('motPasse', '')
        mdp_confirm   = data.get('confirmerMotPasse', '')

        if not raison_social:
            errors['raisonSocial'] = 'La raison sociale est obligatoire.'
        if not email:
            errors['emailProfessionnel'] = "L'email professionnel est obligatoire."
        elif Entreprise.objects.filter(emailProfessionnel=email).exists():
            errors['emailProfessionnel'] = 'Cet email est déjà associé à un compte.'
        if not mdp:
            errors['motPasse'] = 'Le mot de passe est obligatoire.'
        elif len(mdp) < 8:
            errors['motPasse'] = 'Le mot de passe doit contenir au moins 8 caractères.'
        if mdp and mdp != mdp_confirm:
            errors['confirmerMotPasse'] = 'Les mots de passe ne correspondent pas.'

        if errors:
            return render(request, 'entreprise/inscription.html', {
                'errors': errors, 'data': data,
                'secteurs': SECTEURS, 'tailles': TAILLES,
            })

        ent = Entreprise(
            raisonSocial       = raison_social,
            emailProfessionnel = email,
            registreCommerce   = data.get('registreCommerce', '').strip(),
            idu                = data.get('idu', '').strip(),
            secteurActivite    = data.get('secteurActivite', ''),
            tailleEntreprise   = data.get('tailleEntreprise', ''),
            telephone          = data.get('telephone', '').strip(),
            emailContact       = data.get('emailContact', '').strip(),
            siteWeb            = data.get('siteWeb', '').strip(),
            adresse            = data.get('adresse', '').strip(),
            ville              = data.get('ville', '').strip(),
            pays               = data.get('pays', "Côte d'Ivoire").strip() or "Côte d'Ivoire",
            codePostal         = data.get('codePostal', '').strip(),
        )
        ent.set_password(mdp)
        with transaction.atomic():
            ent.save()
            ent.calculerScorePertinence()
            ParametreEntreprise.get_or_create_defaut(ent)

        request.session.cycle_key()
        request.session['entreprise_id'] = ent.pk
        request.session.set_expiry(28800)
        messages.success(request,
            f'Bienvenue {ent.raisonSocial} ! Votre espace entreprise a été créé avec succès.')
        return redirect('entreprise:tableau_bord')

    return render(request, 'entreprise/inscription.html', {
        'secteurs': SECTEURS, 'tailles': TAILLES,
    })


# ── Connexion ─────────────────────────────────────────────────────────────────

@ratelimit(key='ip', rate='5/m', method='POST', block=False)
def connexion(request):
    """Connexion administrateur :
       - proprietaire de l'entreprise (modele Entreprise) ;
       - recruteur avec roleMembre == ADMIN.
    Les autres roles (RH, MANAGER, LECTEUR) doivent passer par
    ``entreprise:recruteur_connexion``.
    """
    if request.entreprise and not request.recruteur:
        return redirect('entreprise:tableau_bord')
    if request.recruteur and request.recruteur.roleMembre == RoleMembre.ADMIN:
        return redirect('entreprise:recruteur_tableau_bord')

    if request.method == 'POST':
        if getattr(request, 'limited', False):
            return render(request, 'entreprise/connexion.html', {
                'error': 'Trop de tentatives. Veuillez réessayer dans une minute.',
            })
        email = request.POST.get('email', '').strip().lower()
        mdp   = request.POST.get('motPasse', '')

        ent = Entreprise.objects.filter(emailProfessionnel=email).first()

        if ent:
            if not ent.check_password(mdp):
                return render(request, 'entreprise/connexion.html', {
                    'error': 'Email ou mot de passe incorrect.', 'email': email,
                })
            if ent.statutCompte != StatutCompte.ACTIF:
                return render(request, 'entreprise/connexion.html', {
                    'error': 'Votre compte est suspendu ou désactivé. Contactez le support.',
                    'email': email,
                })

            ent.derniereConnexion = timezone.now()
            ent.save(update_fields=['derniereConnexion'])
            request.session.cycle_key()
            request.session['entreprise_id'] = ent.pk
            request.session.pop('recruteur_id', None)
            request.session.set_expiry(28800)
            messages.success(request, f'Bienvenue, {ent.raisonSocial} !')

            next_url = request.GET.get('next', '')
            return redirect(next_url or 'entreprise:tableau_bord')

        # Pas une entreprise : on tente le recruteur ADMIN
        rec = (Recruteur.objects
               .select_related('entreprise')
               .filter(emailProfessionnel=email)
               .first())

        if rec and rec.roleMembre != RoleMembre.ADMIN:
            return render(request, 'entreprise/connexion.html', {
                'error': "Cet espace est réservé aux administrateurs. "
                         "Connectez-vous via l'espace recruteur.",
                'email': email,
                'redirect_recruteur': True,
            })

        if not rec or not rec.check_password(mdp):
            return render(request, 'entreprise/connexion.html', {
                'error': 'Email ou mot de passe incorrect.', 'email': email,
            })

        if not rec.estActif or rec.statutCompte != StatutCompte.ACTIF:
            return render(request, 'entreprise/connexion.html', {
                'error': 'Votre compte est suspendu ou désactivé. '
                         'Contactez votre administrateur.',
                'email': email,
            })

        if rec.entreprise.statutCompte == StatutCompte.DESACTIVE:
            return render(request, 'entreprise/connexion.html', {
                'error': "Le compte de votre entreprise est désactivé.",
                'email': email,
            })

        rec.derniereConnexion = timezone.now()
        rec.save(update_fields=['derniereConnexion'])
        auth_login(request, rec, backend='referentiel.backends.EmailBackend')
        request.session.pop('entreprise_id', None)
        messages.success(request, f'Bienvenue, {rec.nomComplet} !')

        next_url = request.GET.get('next', '')
        return redirect(next_url or 'entreprise:recruteur_tableau_bord')

    return render(request, 'entreprise/connexion.html')


# ── Deconnexion ───────────────────────────────────────────────────────────────

@require_POST
def deconnexion(request):
    request.session.pop('entreprise_id', None)
    messages.info(request, 'Vous avez été déconnecté.')
    return redirect('entreprise:connexion')


# ════════════════════════════════════════════════════════════════════════════════
# ESPACE RECRUTEUR (auth autonome)
# ════════════════════════════════════════════════════════════════════════════════

@ratelimit(key='ip', rate='5/m', method='POST', block=False)
def recruteur_connexion(request):
    """Connexion des recruteurs non-administrateurs (RH, MANAGER, LECTEUR)."""
    if getattr(request, 'recruteur', None):
        return redirect('entreprise:recruteur_tableau_bord')
    if request.entreprise:
        return redirect('entreprise:tableau_bord')

    if request.method == 'POST':
        if getattr(request, 'limited', False):
            return render(request, 'entreprise/connexion.html', {
                'error': 'Trop de tentatives. Veuillez réessayer dans une minute.',
            })
        email = request.POST.get('email', '').strip().lower()
        mdp   = request.POST.get('motPasse', '')

        # Bloquer les comptes proprietaires d'entreprise -> page entreprise
        if Entreprise.objects.filter(emailProfessionnel=email).exists():
            return render(request, 'entreprise/recruteur/connexion.html', {
                'error': "Cet email correspond à un compte administrateur. "
                         "Connectez-vous via l'espace entreprise.",
                'email': email,
                'redirect_admin': True,
            })

        try:
            rec = Recruteur.objects.select_related('entreprise').get(emailProfessionnel=email)
        except Recruteur.DoesNotExist:
            return render(request, 'entreprise/recruteur/connexion.html', {
                'error': 'Email ou mot de passe incorrect.', 'email': email,
            })

        if not rec.check_password(mdp):
            return render(request, 'entreprise/recruteur/connexion.html', {
                'error': 'Email ou mot de passe incorrect.', 'email': email,
            })

        # Recruteur ADMIN -> renvoyer vers la connexion entreprise
        if rec.roleMembre == RoleMembre.ADMIN:
            return render(request, 'entreprise/recruteur/connexion.html', {
                'error': "Votre rôle est administrateur. "
                         "Connectez-vous via l'espace entreprise.",
                'email': email,
                'redirect_admin': True,
            })

        if not rec.estActif or rec.statutCompte != StatutCompte.ACTIF:
            return render(request, 'entreprise/recruteur/connexion.html', {
                'error': 'Votre compte est suspendu ou désactivé. Contactez votre administrateur.',
                'email': email,
            })

        if rec.entreprise.statutCompte == StatutCompte.DESACTIVE:
            return render(request, 'entreprise/recruteur/connexion.html', {
                'error': "Le compte de votre entreprise est désactivé.", 'email': email,
            })

        rec.derniereConnexion = timezone.now()
        rec.save(update_fields=['derniereConnexion'])
        auth_login(request, rec, backend='referentiel.backends.EmailBackend')
        messages.success(request, f'Bienvenue, {rec.nomComplet} !')

        next_url = request.GET.get('next', '')
        return redirect(next_url or 'entreprise:recruteur_tableau_bord')

    return render(request, 'entreprise/recruteur/connexion.html')


@require_POST
def recruteur_deconnexion(request):
    auth_logout(request)
    messages.info(request, 'Vous avez été déconnecté.')
    return redirect('entreprise:recruteur_connexion')


# ════════════════════════════════════════════════════════════════════════════════
# REINITIALISATION MDP ENTREPRISE
# ════════════════════════════════════════════════════════════════════════════════

def mot_de_passe_oublie(request):
    if request.entreprise and not request.recruteur:
        return redirect('entreprise:tableau_bord')
    return render(request, 'entreprise/mot_de_passe_oublie.html')


def reinitialiser_mot_de_passe(request, token):
    if request.entreprise and not request.recruteur:
        return redirect('entreprise:tableau_bord')

    token_obj = get_object_or_404(TokenReinitialisationEntreprise, token=token)

    if not token_obj.est_valide():
        messages.error(request, 'Ce lien a expiré ou a déjà été utilisé.')
        return redirect('entreprise:mot_de_passe_oublie')

    if token_obj.methode == 'code' and not token_obj.verifie:
        messages.error(request, 'Accès non autorisé. Veuillez saisir votre code.')
        return redirect('entreprise:mot_de_passe_oublie')

    if token_obj.methode == 'lien' and not token_obj.verifie:
        token_obj.verifie = True
        token_obj.save(update_fields=['verifie'])

    if request.method == 'POST':
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        erreur = None

        if len(password1) < 8:
            erreur = 'Le mot de passe doit contenir au moins 8 caractères.'
        elif password1 != password2:
            erreur = 'Les deux mots de passe ne correspondent pas.'

        if erreur:
            messages.error(request, erreur)
        else:
            token_obj.entreprise.set_password(password1)
            token_obj.entreprise.save(update_fields=['motPasse'])
            token_obj.utilise = True
            token_obj.save(update_fields=['utilise'])
            messages.success(request, 'Mot de passe réinitialisé avec succès. Vous pouvez maintenant vous connecter.')
            return redirect('entreprise:connexion')

    return render(request, 'entreprise/reinitialiser_mot_de_passe.html', {'token': token})


@require_POST
def api_verifier_email_entreprise(request):
    try:
        data  = json.loads(request.body)
        email = data.get('email', '').strip().lower()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'existe': False}, status=400)

    existe = Entreprise.objects.filter(emailProfessionnel=email).exists()
    return JsonResponse({'existe': existe})


@require_POST
@ratelimit(key='ip', rate='3/m', method='POST', block=False)
def api_envoyer_reinitialisation_entreprise(request):
    if getattr(request, 'limited', False):
        return JsonResponse({'succes': False, 'message': 'Trop de tentatives. Réessayez dans une minute.'}, status=429)
    try:
        data    = json.loads(request.body)
        email   = data.get('email', '').strip().lower()
        methode = data.get('methode', 'lien')
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'succes': False, 'message': 'Données invalides.'}, status=400)

    try:
        ent = Entreprise.objects.get(emailProfessionnel=email)
    except Entreprise.DoesNotExist:
        return JsonResponse({'succes': False, 'message': 'Email introuvable.'}, status=404)

    # Invalider les anciens tokens non utilises
    TokenReinitialisationEntreprise.objects.filter(entreprise=ent, utilise=False).update(utilise=True)

    nom = ent.raisonSocial
    logo_site = LogoSite.get_actif()
    nom_site  = logo_site.nom_site

    if methode == 'code':
        code      = TokenReinitialisationEntreprise.generer_code()
        token_obj = TokenReinitialisationEntreprise.objects.create(entreprise=ent, methode='code', code=code)
        corps_texte = (
            f'Bonjour {nom},\n\n'
            f'Votre code de réinitialisation est : {code}\n\n'
            f'Ce code est valable 10 minutes.\n\n'
            f"Si vous n'avez pas demandé cette réinitialisation, ignorez cet email.\n\n"
            f"L'équipe {nom_site}"
        )
        corps_html = render_to_string(
            'entreprise/emails/reinitialisation_code.html',
            {'nom': nom, 'code': code, 'logo_site': logo_site},
        )
        msg = EmailMultiAlternatives(
            subject=f'Votre code de réinitialisation — {nom_site}',
            body=corps_texte,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach_alternative(corps_html, 'text/html')
        msg.send(fail_silently=True)
        return JsonResponse({'succes': True, 'token': str(token_obj.token)})

    else:  # 'lien'
        token_obj = TokenReinitialisationEntreprise.objects.create(entreprise=ent, methode='lien')
        reset_url = request.build_absolute_uri(
            reverse('entreprise:reinitialiser_mot_de_passe', args=[str(token_obj.token)])
        )
        corps_texte = (
            f'Bonjour {nom},\n\n'
            f'Cliquez sur ce lien pour réinitialiser votre mot de passe (valable 10 minutes) :\n\n'
            f'{reset_url}\n\n'
            f"Si vous n'avez pas demandé cette réinitialisation, ignorez cet email.\n\n"
            f"L'équipe {nom_site}"
        )
        corps_html = render_to_string(
            'entreprise/emails/reinitialisation_lien.html',
            {'nom': nom, 'reset_url': reset_url, 'logo_site': logo_site},
        )
        msg = EmailMultiAlternatives(
            subject=f'Réinitialisation de votre mot de passe — {nom_site}',
            body=corps_texte,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach_alternative(corps_html, 'text/html')
        msg.send(fail_silently=True)
        return JsonResponse({'succes': True})


@require_POST
@ratelimit(key='ip', rate='7/m', method='POST', block=False)
def api_verifier_code_entreprise(request):
    if getattr(request, 'limited', False):
        return JsonResponse({'valide': False, 'message': 'Trop de tentatives. Réessayez dans une minute.'}, status=429)
    try:
        data       = json.loads(request.body)
        token_uuid = data.get('token', '')
        code_saisi = data.get('code', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'valide': False, 'message': 'Données invalides.'}, status=400)

    try:
        token_obj = TokenReinitialisationEntreprise.objects.get(token=token_uuid, methode='code')
    except (TokenReinitialisationEntreprise.DoesNotExist, ValueError):
        return JsonResponse({'valide': False, 'message': 'Token invalide.'})

    if not token_obj.est_valide():
        return JsonResponse({'valide': False, 'message': 'Ce code a expiré. Veuillez recommencer.'})

    if token_obj.code != code_saisi:
        return JsonResponse({'valide': False, 'message': 'Code incorrect. Vérifiez votre email.'})

    token_obj.verifie = True
    token_obj.save(update_fields=['verifie'])
    return JsonResponse({'valide': True, 'redirect': f'/entreprise/reinitialisation/{token_obj.token}/'})
