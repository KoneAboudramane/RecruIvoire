import json

from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from .models import AbonneNewsletter, LogoSite

CHAMPS_PREFS_GENERALES    = ['offres_semaine', 'conseils', 'actualites']
CHAMPS_PREFS_INDIVIDUELLES = ['offres_perso', 'profil_consulte', 'resume_candidatures']
TOUS_CHAMPS_PREFS          = CHAMPS_PREFS_GENERALES + CHAMPS_PREFS_INDIVIDUELLES


def _email_valide(email):
    """Retourne True si l'adresse e-mail est syntaxiquement valide."""
    try:
        validate_email(email)
        return True
    except ValidationError:
        return False


# ─── API : toggle abonnement (pour le profil et la page publique) ─────────────

@require_POST
def api_newsletter_toggle(request):
    """Abonne ou désabonne selon l'état actuel. Retourne le nouvel état."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'message': 'Données invalides.'}, status=400)

    email = data.get('email', '').strip().lower()
    if not _email_valide(email):
        return JsonResponse({'ok': False, 'message': 'Adresse e-mail invalide.'})

    abonne = AbonneNewsletter.objects.filter(email=email).first()

    if abonne and abonne.actif:
        abonne.actif = False
        abonne.save(update_fields=['actif'])
        return JsonResponse({'ok': True, 'actif': False, 'message': 'Vous avez été désabonné(e) avec succès.'})
    elif abonne and not abonne.actif:
        abonne.actif = True
        abonne.save(update_fields=['actif'])
        logo_site = LogoSite.get_actif()
        _envoyer_email_confirmation(abonne, logo_site, request)
        return JsonResponse({'ok': True, 'actif': True, 'message': 'Vous êtes de nouveau abonné(e) !'})
    else:
        return JsonResponse({'ok': False, 'message': 'Aucune inscription trouvée pour cet e-mail.'})


# ─── API : consulter le statut sans modifier ──────────────────────────────────

@require_POST
def api_newsletter_statut(request):
    """Retourne le statut d'abonnement d'un email sans le modifier."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'message': 'Données invalides.'}, status=400)

    email = data.get('email', '').strip().lower()
    if not _email_valide(email):
        return JsonResponse({'ok': False, 'message': 'Adresse e-mail invalide.'})

    abonne = AbonneNewsletter.objects.filter(email=email).first()
    if not abonne:
        return JsonResponse({'ok': False, 'message': 'Aucune inscription trouvée pour cet e-mail.'})

    return JsonResponse({'ok': True, 'actif': abonne.actif})


# ─── Page publique : gérer son abonnement sans connexion ─────────────────────

def gerer_newsletter(request):
    logo_site = LogoSite.get_actif()
    return render(request, 'candidat/newsletter/gerer.html', {
        'logo_site': logo_site,
    })


# ─── Inscription ──────────────────────────────────────────────────────────────

@require_POST
def api_newsletter_inscription(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'message': 'Données invalides.'}, status=400)

    email = data.get('email', '').strip().lower()
    if not _email_valide(email):
        return JsonResponse({'ok': False, 'message': 'Adresse e-mail invalide.'})

    # Extraire les préférences générales uniquement (visiteur anonyme)
    prefs = {champ: bool(data.get(champ, False)) for champ in CHAMPS_PREFS_GENERALES}

    if not any(prefs.values()):
        return JsonResponse({'ok': False, 'message': 'Sélectionnez au moins un type d\'email à recevoir.'})

    abonne, created = AbonneNewsletter.objects.get_or_create(email=email)

    if not created and abonne.actif:
        # Mettre à jour les préférences même si déjà abonné
        for champ, val in prefs.items():
            setattr(abonne, champ, val)
        abonne.save(update_fields=list(prefs.keys()))
        return JsonResponse({'ok': True, 'message': 'Vos préférences ont été mises à jour.'})

    if not created and not abonne.actif:
        abonne.actif = True

    for champ, val in prefs.items():
        setattr(abonne, champ, val)
    abonne.save(update_fields=['actif'] + list(prefs.keys()))

    logo_site = LogoSite.get_actif()
    _envoyer_email_confirmation(abonne, logo_site, request)

    return JsonResponse({'ok': True, 'message': 'Inscription confirmée ! Vérifiez votre boîte mail.'})


@require_POST
def api_newsletter_preferences(request):
    """Met à jour les préférences d'un candidat connecté depuis la page profil."""
    from .models import Candidat
    candidat_id = request.session.get('candidat_id')
    if not candidat_id:
        return JsonResponse({'ok': False, 'message': 'Non connecté.'}, status=403)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'message': 'Données invalides.'}, status=400)

    try:
        candidat = Candidat.objects.get(pk=candidat_id)
    except Candidat.DoesNotExist:
        return JsonResponse({'ok': False, 'message': 'Candidat introuvable.'}, status=404)

    actif = bool(data.get('actif', False))
    prefs = {champ: bool(data.get(champ, False)) for champ in TOUS_CHAMPS_PREFS}

    if not actif or not any(prefs.values()):
        # Désabonnement complet
        AbonneNewsletter.objects.filter(email=candidat.email).update(actif=False)
        return JsonResponse({'ok': True, 'actif': False, 'message': 'Vous avez été désabonné(e).'})

    abonne, _ = AbonneNewsletter.objects.get_or_create(email=candidat.email)
    abonne.candidat = candidat
    abonne.actif    = True
    for champ, val in prefs.items():
        setattr(abonne, champ, val)
    abonne.save(update_fields=['candidat', 'actif'] + list(prefs.keys()))

    return JsonResponse({'ok': True, 'actif': True, 'message': 'Préférences enregistrées.'})


# ─── Désabonnement ────────────────────────────────────────────────────────────

def newsletter_desabonnement(request, token):
    abonne = AbonneNewsletter.objects.filter(token_desabonnement=token).first()
    logo_site = LogoSite.get_actif()

    if abonne and abonne.actif:
        abonne.actif = False
        abonne.save(update_fields=['actif'])
        desabonne = True
    elif abonne and not abonne.actif:
        desabonne = True  # déjà désabonné
    else:
        desabonne = False  # token invalide

    return render(request, 'candidat/newsletter/desabonnement.html', {
        'logo_site': logo_site,
        'desabonne': desabonne,
        'abonne': abonne,
    })


# ─── Envoi de l'email de confirmation ─────────────────────────────────────────

def _envoyer_email_confirmation(abonne, logo_site, request):
    desabo_url = request.build_absolute_uri(
        f'/candidat/newsletter/desabonnement/{abonne.token_desabonnement}/'
    )
    site_url = request.build_absolute_uri('/').rstrip('/')

    ctx = {
        'logo_site':   logo_site,
        'abonne':      abonne,
        'desabo_url':  desabo_url,
        'site_url':    site_url,
    }

    sujet   = f"Bienvenue dans la newsletter {logo_site.nom_site} !"
    txt     = render_to_string('candidat/newsletter/email_confirmation.txt', ctx)
    html    = render_to_string('candidat/newsletter/email_confirmation.html', ctx, request=request)

    msg = EmailMultiAlternatives(
        subject=sujet,
        body=txt,
        to=[abonne.email],
    )
    msg.attach_alternative(html, 'text/html')
    msg.send(fail_silently=True)
