import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_POST


# ── API Contact ───────────────────────────────────────────────────────────────

@require_POST
def api_contact(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'message': 'Donnees invalides.'}, status=400)

    if data.get('website'):
        return JsonResponse({'ok': True, 'message': 'Message envoye !'})

    nom       = data.get('nom', '').strip()
    email     = data.get('email', '').strip()
    sujet     = data.get('sujet', '').strip()
    categorie = data.get('categorie', 'Général').strip()
    message   = data.get('message', '').strip()

    if not all([nom, email, sujet, message]):
        return JsonResponse({'ok': False, 'message': 'Tous les champs obligatoires doivent etre remplis.'})
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({'ok': False, 'message': 'Adresse e-mail invalide.'})
    if len(message) < 20:
        return JsonResponse({'ok': False, 'message': 'Votre message est trop court (20 caracteres minimum).'})

    from candidat.models import LogoSite
    from contenu.models import ContactConfig, MessageContact

    logo_site = LogoSite.get_actif()
    config    = ContactConfig.get()

    # Sauvegarde en base
    MessageContact.objects.create(
        nom=nom, email=email, categorie=categorie, sujet=sujet, message=message,
    )

    corps_texte = (
        f"Nouveau message de contact — {logo_site.nom_site}\n"
        f"{'─' * 50}\n"
        f"Nom      : {nom}\n"
        f"E-mail   : {email}\n"
        f"Catégorie: {categorie}\n"
        f"Sujet    : {sujet}\n"
        f"{'─' * 50}\n\n"
        f"{message}\n"
    )
    corps_html = render_to_string(
        'candidat/emails/contact.html',
        {'nom': nom, 'email': email, 'sujet': sujet,
         'categorie': categorie, 'message': message, 'logo_site': logo_site},
    )

    try:
        msg = EmailMultiAlternatives(
            subject=f"[Contact] {categorie} — {sujet}",
            body=corps_texte,
            from_email=f"{nom} <noreply@recrutepro.ci>",
            to=[config.email],
        )
        msg.attach_alternative(corps_html, 'text/html')
        msg.send(fail_silently=False)
    except Exception:
        return JsonResponse({'ok': False, 'message': "Erreur lors de l'envoi. Réessayez ou contactez-nous par e-mail."})

    return JsonResponse({'ok': True, 'message': 'Votre message a bien été envoyé ! Nous vous répondrons sous 24–48h ouvrées.'})


# ── manifest.json (PWA) ──────────────────────────────────────────────────────

@cache_page(86400)
def manifest_json(request):
    from candidat.models import LogoSite
    logo = LogoSite.get_actif()
    nom  = logo.nom_site if logo else 'RecrutePro'
    data = {
        "name": nom,
        "short_name": nom,
        "description": "Plateforme de recrutement en Côte d'Ivoire — offres d'emploi, CV, candidatures.",
        "start_url": "/candidat/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#2e7d52",
        "lang": "fr-CI",
        "categories": ["business", "productivity"],
        "icons": [],
    }
    import json as _json
    return HttpResponse(
        _json.dumps(data, ensure_ascii=False),
        content_type='application/manifest+json',
    )


# ── Favicon PNG (converti depuis logo) ──────────────────────────────────────

@cache_page(86400)
def favicon_png(request):
    from candidat.models import LogoSite
    import io
    try:
        from PIL import Image
        logo = LogoSite.get_actif()
        if logo and logo.logo_image:
            logo_img = Image.open(logo.logo_image.path).convert('RGBA')
            # Fond blanc 64×64 pour que les logos foncés soient visibles
            canvas = Image.new('RGBA', (64, 64), (255, 255, 255, 255))
            logo_img.thumbnail((60, 60), Image.LANCZOS)
            offset_x = (64 - logo_img.width) // 2
            offset_y = (64 - logo_img.height) // 2
            canvas.paste(logo_img, (offset_x, offset_y), logo_img)
            buf = io.BytesIO()
            canvas.convert('RGB').save(buf, format='PNG')
            return HttpResponse(buf.getvalue(), content_type='image/png')
    except Exception:
        pass
    # Fallback : initiale sur fond vert
    try:
        from PIL import Image, ImageDraw
        from candidat.models import LogoSite
        logo = LogoSite.get_actif()
        lettre = (logo.nom_site[0].upper() if logo else 'R')
        img = Image.new('RGB', (64, 64), (46, 125, 82))
        d = ImageDraw.Draw(img)
        d.text((20, 16), lettre, fill=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return HttpResponse(buf.getvalue(), content_type='image/png')
    except Exception:
        return HttpResponse(status=404)


# ── robots.txt ────────────────────────────────────────────────────────────────

def robots_txt(request):
    site_url = getattr(settings, 'SITE_URL', 'https://www.recrutepro.ci')
    lines = [
        'User-agent: *',
        'Allow: /',
        '',
        '# Pages privées — candidats',
        'Disallow: /candidat/dashboard/',
        'Disallow: /candidat/profil/',
        'Disallow: /candidat/mes-candidatures/',
        'Disallow: /candidat/notifications/',
        'Disallow: /candidat/messagerie/',
        'Disallow: /candidat/connexion/',
        'Disallow: /candidat/inscription/',
        'Disallow: /candidat/api/',
        '',
        '# Pages privées — entreprises',
        'Disallow: /entreprise/dashboard/',
        'Disallow: /entreprise/offres/',
        'Disallow: /entreprise/candidatures/',
        'Disallow: /entreprise/membres/',
        'Disallow: /entreprise/connexion/',
        'Disallow: /entreprise/inscription/',
        '',
        '# Technique',
        'Disallow: /admin/',
        'Disallow: /referentiel/',
        'Disallow: /api/',
        '',
        f'Sitemap: {site_url}/sitemap.xml',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain; charset=utf-8')


# ── Pages d'erreur ────────────────────────────────────────────────────────────

def error_404(request, exception):
    return render(request, '404.html', status=404)


def error_500(request):
    return render(request, '500.html', status=500)


def error_403(request, exception):
    return render(request, '403.html', status=403)
