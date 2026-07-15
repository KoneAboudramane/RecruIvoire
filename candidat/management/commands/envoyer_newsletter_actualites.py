"""
Commande Django : envoie les actualités planifiées dont la date est échue.

Usage :
    python manage.py envoyer_newsletter_actualites
    python manage.py envoyer_newsletter_actualites --dry-run
    python manage.py envoyer_newsletter_actualites --actualite 3
"""

from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone


class Command(BaseCommand):
    help = "Envoie les actualités newsletter planifiées aux abonnés."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Affiche les stats sans envoyer aucun email.')
        parser.add_argument('--actualite', type=int, default=None,
                            help="Forcer l'envoi d'une actualité précise (ID).")

    def handle(self, *args, **opts):
        from candidat.models import ActualiteNewsletter, AbonneNewsletter, LogoSite, _StatutNewsletter

        dry_run     = opts['dry_run']
        actualite_id = opts['actualite']

        self.stdout.write(self.style.MIGRATE_HEADING("\n> Envoi newsletter — Actualités"))
        self.stdout.write(f"  Mode : {'DRY-RUN' if dry_run else 'REEL'}")

        if actualite_id:
            actualites = ActualiteNewsletter.objects.filter(pk=actualite_id)
        else:
            actualites = ActualiteNewsletter.objects.filter(
                statut=_StatutNewsletter.PLANIFIE,
                date_envoi_prevu__lte=timezone.now(),
            )

        if not actualites.exists():
            self.stdout.write(self.style.WARNING("  Aucune actualité à envoyer."))
            return

        abonnes   = list(AbonneNewsletter.objects.filter(actif=True, actualites=True))
        logo_site = LogoSite.get_actif()

        self.stdout.write(f"  Actualités : {actualites.count()} | Abonnés : {len(abonnes)}")

        for actualite in actualites:
            self.stdout.write(f"\n  → {actualite.titre}")
            envoyes, erreurs = 0, 0
            for abonne in abonnes:
                if dry_run:
                    envoyes += 1
                    continue
                try:
                    _envoyer_email(abonne, actualite, logo_site)
                    envoyes += 1
                except Exception as e:
                    erreurs += 1
                    self.stdout.write(self.style.ERROR(f"    ✗ {abonne.email} : {e}"))

            self.stdout.write(f"    Envoyés : {envoyes} | Erreurs : {erreurs}")

            if not dry_run:
                actualite.statut           = _StatutNewsletter.ENVOYE
                actualite.date_envoi_reel  = timezone.now()
                actualite.nb_destinataires = envoyes
                actualite.save(update_fields=['statut', 'date_envoi_reel', 'nb_destinataires'])

        self.stdout.write(self.style.SUCCESS("\n✓ Terminé."))


def _envoyer_email(abonne, actualite, logo_site):
    from django.conf import settings

    site_url   = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
    desabo_url = f'{site_url}/candidat/newsletter/desabonnement/{abonne.token_desabonnement}/'
    image_url  = (site_url + actualite.image.url) if actualite.image else ''

    ctx = {
        'logo_site':  logo_site,
        'abonne':     abonne,
        'actualite':  actualite,
        'desabo_url': desabo_url,
        'image_url':  image_url,
        'site_url':   site_url,
    }

    sujet = f"📰 {actualite.titre} — {logo_site.nom_site}"
    txt   = render_to_string('candidat/newsletter/email_actualite.txt',  ctx)
    html  = render_to_string('candidat/newsletter/email_actualite.html', ctx)

    msg = EmailMultiAlternatives(subject=sujet, body=txt, to=[abonne.email])
    msg.attach_alternative(html, 'text/html')
    msg.send(fail_silently=False)
