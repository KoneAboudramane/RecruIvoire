"""Authentication, registration, password reset."""
import json
import logging
import secrets
import urllib.error
import urllib.parse
import urllib.request
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from .. import app_messages as messages
from ..forms import ConnexionForm, InscriptionForm
from ..models import (
    Candidat, TokenConfirmationInscription, TokenReinitialisationMDP,
    AbonneNewsletter, LogoSite,
)
from referentiel.models import TypeCompte

logger = logging.getLogger(__name__)


def inscription(request):
    if request.candidat:
        return redirect('candidat:accueil')

    if request.method == 'POST':
        form = InscriptionForm(request.POST)
        if form.is_valid():
            email  = form.cleaned_data['email']
            prenom = form.cleaned_data['prenom']
            nom    = form.cleaned_data['nom']

            from referentiel.models import Utilisateur
            if Utilisateur.objects.filter(email=email).exists():
                messages.error(request, 'Un compte existe déjà avec cette adresse email.')
                return render(request, 'candidat/inscription.html', {'form': form})

            candidat = Candidat(
                email=email,
                type_compte=TypeCompte.CANDIDAT,
                prenom=prenom, nom=nom,
                emailVerifie=False,
            )
            candidat.set_password(form.cleaned_data['password1'])

            # Génération du code à 4 chiffres
            code = TokenConfirmationInscription.generer_code()
            with transaction.atomic():
                candidat.save()
                token_obj = TokenConfirmationInscription.objects.create(candidat=candidat, code=code)

            # Envoi de l'email de confirmation
            logo_site = LogoSite.get_actif()
            nom_site  = logo_site.nom_site
            try:
                sujet       = f"Votre code de confirmation — {nom_site}"
                corps_texte = (
                    f"Bonjour {prenom},\n\n"
                    f"Votre code de confirmation est : {code}\n\n"
                    f"Saisissez-le sur la page d'inscription pour activer votre compte.\n"
                    f"Ce code est valable 10 minutes.\n\n"
                    f"Si vous n'avez pas créé de compte, ignorez cet email.\n\n"
                    f"L'équipe {nom_site}"
                )
                corps_html = render_to_string(
                    'candidat/emails/confirmation_inscription.html',
                    {'prenom': prenom, 'code': code, 'logo_site': logo_site},
                )
                msg = EmailMultiAlternatives(
                    subject=sujet,
                    body=corps_texte,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email],
                )
                msg.attach_alternative(corps_html, 'text/html')
                msg.send()
            except Exception:
                candidat.delete()
                messages.error(
                    request,
                    "Impossible d'envoyer l'email de confirmation. "
                    "Vérifiez votre adresse email et réessayez.",
                )
                return render(request, 'candidat/inscription.html', {'form': form})

            # Sauvegarde du token en session pour la page de vérification
            request.session['inscription_token'] = str(token_obj.token)
            request.session['inscription_email'] = email

            # Préférences newsletter choisies à l'inscription
            request.session['nl_offres_semaine']      = form.cleaned_data.get('nl_offres_semaine', False)
            request.session['nl_conseils']            = form.cleaned_data.get('nl_conseils', False)
            request.session['nl_actualites']          = form.cleaned_data.get('nl_actualites', False)
            request.session['nl_offres_perso']        = form.cleaned_data.get('nl_offres_perso', False)
            request.session['nl_profil_consulte']     = form.cleaned_data.get('nl_profil_consulte', False)
            request.session['nl_resume_candidatures'] = form.cleaned_data.get('nl_resume_candidatures', False)

            return redirect('candidat:inscription_en_attente')
    else:
        form = InscriptionForm()

    return render(request, 'candidat/inscription.html', {'form': form})


def inscription_en_attente(request):
    """Page de saisie du code à 4 chiffres envoyé par email."""
    if request.candidat:
        return redirect('candidat:accueil')
    if not request.session.get('inscription_token'):
        return redirect('candidat:inscription')
    email = request.session.get('inscription_email', '')
    return render(request, 'candidat/inscription_en_attente.html', {'email': email})


@require_POST
@ratelimit(key='ip', rate='7/m', method='POST', block=False)
def api_verifier_code_inscription(request):
    """Vérifie le code à 4 chiffres, active le compte et connecte le candidat."""
    if getattr(request, 'limited', False):
        return JsonResponse({'valide': False, 'message': 'Trop de tentatives. Réessayez dans une minute.'}, status=429)
    try:
        data       = json.loads(request.body)
        code_saisi = data.get('code', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'valide': False, 'message': 'Données invalides.'}, status=400)

    token_uuid = request.session.get('inscription_token')
    if not token_uuid:
        return JsonResponse({'valide': False, 'message': "Session expirée. Recommencez l'inscription."})

    try:
        token_obj = (
            TokenConfirmationInscription.objects
            .select_related('candidat')
            .get(token=token_uuid)
        )
    except (TokenConfirmationInscription.DoesNotExist, ValueError):
        return JsonResponse({'valide': False, 'message': 'Token invalide.'})

    if not token_obj.est_valide():
        token_obj.candidat.delete()
        request.session.pop('inscription_token', None)
        request.session.pop('inscription_email', None)
        return JsonResponse({
            'valide': False,
            'expire': True,
            'message': 'Ce code a expiré (10 minutes). Votre inscription a été annulée.',
        })

    if token_obj.code != code_saisi:
        return JsonResponse({'valide': False, 'message': 'Code incorrect. Vérifiez votre email.'})

    # ── Code correct ────────────────────────────────────────────────────────────
    candidat = token_obj.candidat
    prenom   = candidat.prenom

    # Étape critique : activer le compte en base
    try:
        with transaction.atomic():
            candidat.emailVerifie = True
            candidat.save(update_fields=['emailVerifie'])
            token_obj.delete()
    except Exception:
        return JsonResponse({
            'valide':  False,
            'message': "Erreur lors de l'activation du compte. Réessayez.",
        }, status=500)

    request.session.pop('inscription_token', None)
    request.session.pop('inscription_email', None)
    auth_login(request, candidat, backend='referentiel.backends.EmailBackend')

    # Créer AbonneNewsletter uniquement si au moins une préférence cochée
    prefs_nl = {
        'offres_semaine':      request.session.pop('nl_offres_semaine', False),
        'conseils':            request.session.pop('nl_conseils', False),
        'actualites':          request.session.pop('nl_actualites', False),
        'offres_perso':        request.session.pop('nl_offres_perso', False),
        'profil_consulte':     request.session.pop('nl_profil_consulte', False),
        'resume_candidatures': request.session.pop('nl_resume_candidatures', False),
    }
    try:
        with transaction.atomic():
            if any(prefs_nl.values()):
                AbonneNewsletter.objects.update_or_create(
                    email=candidat.email,
                    defaults={'candidat': candidat, 'actif': True, **prefs_nl},
                )
            candidat.derniereConnexion = timezone.now()
            candidat.save(update_fields=['derniereConnexion'])
    except Exception:
        pass

    return JsonResponse({
        'valide':   True,
        'prenom':   prenom,
        'redirect': reverse('candidat:accueil'),
    })


@require_POST
def api_renvoyer_code_inscription(request):
    """Génère un nouveau code et le renvoie par email."""
    token_uuid = request.session.get('inscription_token')
    if not token_uuid:
        return JsonResponse({'succes': False, 'message': "Session expirée. Recommencez l'inscription."})

    try:
        token_obj = (
            TokenConfirmationInscription.objects
            .select_related('candidat')
            .get(token=token_uuid)
        )
    except (TokenConfirmationInscription.DoesNotExist, ValueError):
        return JsonResponse({'succes': False, 'message': 'Token invalide.'})

    candidat = token_obj.candidat

    # Supprimer l'ancien token et créer un nouveau
    nouveau_code = TokenConfirmationInscription.generer_code()
    with transaction.atomic():
        token_obj.delete()
        nouveau_token_obj = TokenConfirmationInscription.objects.create(candidat=candidat, code=nouveau_code)
    request.session['inscription_token'] = str(nouveau_token_obj.token)

    logo_site = LogoSite.get_actif()
    nom_site  = logo_site.nom_site
    try:
        corps_html = render_to_string(
            'candidat/emails/confirmation_inscription.html',
            {'prenom': candidat.prenom, 'code': nouveau_code, 'logo_site': logo_site},
        )
        msg = EmailMultiAlternatives(
            subject=f'Votre nouveau code de confirmation — {nom_site}',
            body=(
                f"Bonjour {candidat.prenom},\n\n"
                f"Votre nouveau code de confirmation est : {nouveau_code}\n\n"
                f"Ce code est valable 10 minutes.\n\n"
                f"L'équipe {nom_site}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[candidat.email],
        )
        msg.attach_alternative(corps_html, 'text/html')
        msg.send()
    except Exception:
        return JsonResponse({'succes': False, 'message': "Impossible d'envoyer l'email. Réessayez."})

    return JsonResponse({'succes': True})


@ratelimit(key='ip', rate='5/m', method='POST', block=False)
def connexion(request):
    if request.candidat:
        return redirect('candidat:accueil')

    if request.method == 'POST':
        if getattr(request, 'limited', False):
            return render(request, 'candidat/connexion.html', {
                'form': ConnexionForm(),
                'error': 'Trop de tentatives. Veuillez réessayer dans une minute.',
            })
        form = ConnexionForm(request.POST)
        if form.is_valid():
            email    = form.cleaned_data['email']
            password = form.cleaned_data['motdepasse']
            try:
                candidat = Candidat.objects.get(email=email)
                if candidat.verifier_mot_de_passe(password):
                    if not candidat.emailVerifie:
                        messages.warning(
                            request,
                            "Votre adresse email n'a pas encore été confirmée. "
                            "Vérifiez votre boîte mail et saisissez le code de confirmation reçu.",
                        )
                    else:
                        auth_login(request, candidat, backend='referentiel.backends.EmailBackend')
                        candidat.derniereConnexion = timezone.now()
                        candidat.save(update_fields=['derniereConnexion'])
                        next_url = request.GET.get('next', '')
                        if next_url and urlparse(next_url).netloc == '':
                            return redirect(next_url)
                        return redirect('candidat:accueil')
                else:
                    messages.error(request, 'Email ou mot de passe incorrect.')
            except Candidat.DoesNotExist:
                messages.error(request, 'Email ou mot de passe incorrect.')
    else:
        form = ConnexionForm()

    return render(request, 'candidat/connexion.html', {'form': form})


def deconnexion(request):
    if request.method == 'POST':
        auth_logout(request)
        messages.success(request, 'Vous avez été déconnecté.')
    return redirect('candidat:accueil')


def mot_de_passe_oublie(request):
    if request.candidat:
        return redirect('candidat:accueil')
    return render(request, 'candidat/mot_de_passe_oublie.html')


def reinitialiser_mot_de_passe(request, token):
    if request.candidat:
        return redirect('candidat:accueil')

    token_obj = get_object_or_404(TokenReinitialisationMDP, token=token)

    if not token_obj.est_valide():
        messages.error(request, 'Ce lien a expiré ou a déjà été utilisé.')
        return redirect('candidat:mot_de_passe_oublie')

    if token_obj.methode == 'code' and not token_obj.verifie:
        messages.error(request, 'Accès non autorisé. Veuillez saisir votre code.')
        return redirect('candidat:mot_de_passe_oublie')

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
            token_obj.candidat.set_password(password1)
            token_obj.candidat.save(update_fields=['password'])
            token_obj.utilise = True
            token_obj.save(update_fields=['utilise'])
            messages.success(request, 'Mot de passe réinitialisé avec succès. Vous pouvez maintenant vous connecter.')
            return redirect('candidat:connexion')

    return render(request, 'candidat/reinitialiser_mot_de_passe.html', {'token': token})


# ─── API réinitialisation MDP ─────────────────────────────────────────────────

@require_POST
def api_verifier_email(request):
    """Vérifie si un email correspond à un compte candidat existant."""
    try:
        data  = json.loads(request.body)
        email = data.get('email', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'existe': False}, status=400)

    existe = Candidat.objects.filter(email=email).exists()
    return JsonResponse({'existe': existe})


@require_POST
@ratelimit(key='ip', rate='3/m', method='POST', block=False)
def api_envoyer_reinitialisation(request):
    """Envoie un code ou un lien de réinitialisation selon la méthode choisie."""
    if getattr(request, 'limited', False):
        return JsonResponse({'succes': False, 'message': 'Trop de tentatives. Réessayez dans une minute.'}, status=429)
    try:
        data    = json.loads(request.body)
        email   = data.get('email', '').strip()
        methode = data.get('methode', 'lien')
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'succes': False, 'message': 'Données invalides.'}, status=400)

    try:
        candidat = Candidat.objects.get(email=email)
    except Candidat.DoesNotExist:
        return JsonResponse({'succes': False, 'message': 'Email introuvable.'}, status=404)

    prenom = candidat.prenom

    # Invalider les anciens tokens non utilisés et créer le nouveau
    logo_site = LogoSite.get_actif()
    nom_site  = logo_site.nom_site
    if methode == 'code':
        code = TokenReinitialisationMDP.generer_code()
        with transaction.atomic():
            TokenReinitialisationMDP.objects.filter(candidat=candidat, utilise=False).update(utilise=True)
            token_obj = TokenReinitialisationMDP.objects.create(candidat=candidat, methode='code', code=code)
        corps_texte = (
            f'Bonjour {prenom},\n\n'
            f'Votre code de réinitialisation est : {code}\n\n'
            f'Ce code est valable 10 minutes.\n\n'
            f"Si vous n'avez pas demandé cette réinitialisation, ignorez cet email.\n\n"
            f"L'équipe {nom_site}"
        )
        corps_html = render_to_string(
            'candidat/emails/reinitialisation_code.html',
            {'prenom': prenom, 'code': code, 'logo_site': logo_site},
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
        with transaction.atomic():
            TokenReinitialisationMDP.objects.filter(candidat=candidat, utilise=False).update(utilise=True)
            token_obj = TokenReinitialisationMDP.objects.create(candidat=candidat, methode='lien')
        reset_url = request.build_absolute_uri(f'/candidat/reinitialisation/{token_obj.token}/')
        corps_texte = (
            f'Bonjour {prenom},\n\n'
            f'Cliquez sur ce lien pour réinitialiser votre mot de passe (valable 10 minutes) :\n\n'
            f'{reset_url}\n\n'
            f"Si vous n'avez pas demandé cette réinitialisation, ignorez cet email.\n\n"
            f"L'équipe {nom_site}"
        )
        corps_html = render_to_string(
            'candidat/emails/reinitialisation_lien.html',
            {'prenom': prenom, 'reset_url': reset_url, 'logo_site': logo_site},
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
def api_verifier_code(request):
    """Vérifie le code 5 chiffres et renvoie l'URL de réinitialisation si correct."""
    if getattr(request, 'limited', False):
        return JsonResponse({'valide': False, 'message': 'Trop de tentatives. Réessayez dans une minute.'}, status=429)
    try:
        data       = json.loads(request.body)
        token_uuid = data.get('token', '')
        code_saisi = data.get('code', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'valide': False, 'message': 'Données invalides.'}, status=400)

    try:
        token_obj = TokenReinitialisationMDP.objects.get(token=token_uuid, methode='code')
    except (TokenReinitialisationMDP.DoesNotExist, ValueError):
        return JsonResponse({'valide': False, 'message': 'Token invalide.'})

    if not token_obj.est_valide():
        return JsonResponse({'valide': False, 'message': 'Ce code a expiré. Veuillez recommencer.'})

    if token_obj.code != code_saisi:
        return JsonResponse({'valide': False, 'message': 'Code incorrect. Vérifiez votre email.'})

    token_obj.verifie = True
    token_obj.save(update_fields=['verifie'])
    return JsonResponse({'valide': True, 'redirect': f'/candidat/reinitialisation/{token_obj.token}/'})
