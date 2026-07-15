"""
Commande Django : envoie les conseils planifiés dont la date est échue.

Usage :
    python manage.py envoyer_newsletter_conseils
    python manage.py envoyer_newsletter_conseils --dry-run
    python manage.py envoyer_newsletter_conseils --conseil 5   # forcer un conseil précis
"""

from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone


class Command(BaseCommand):
    help = "Envoie les conseils newsletter planifiés aux abonnés."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Affiche les stats sans envoyer aucun email.')
        parser.add_argument('--conseil', type=int, default=None,
                            help='Forcer l\'envoi d\'un conseil précis (ID).')

    def handle(self, *args, **opts):
        from candidat.models import ConseilNewsletter, AbonneNewsletter, LogoSite

        dry_run    = opts['dry_run']
        conseil_id = opts['conseil']

        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n> Envoi newsletter — Conseils & astuces"
        ))
        self.stdout.write(f"  Mode : {'DRY-RUN' if dry_run else 'REEL'}")

        # Sélection des conseils à envoyer
        if conseil_id:
            conseils = ConseilNewsletter.objects.filter(pk=conseil_id)
        else:
            conseils = ConseilNewsletter.objects.filter(
                statut=ConseilNewsletter.Statut.PLANIFIE,
                date_envoi_prevu__lte=timezone.now(),
            )

        if not conseils.exists():
            self.stdout.write(self.style.WARNING("  Aucun conseil à envoyer."))
            return

        logo_site = LogoSite.get_actif()

        self.stdout.write(f"  Contenus à traiter : {conseils.count()}")

        for conseil in conseils:
            # Destinataires selon la catégorie
            filtre = {'conseils': True, 'actif': True}
            abonnes = list(AbonneNewsletter.objects.filter(**filtre))

            self.stdout.write(
                f"\n  → [{conseil.get_categorie_display()}] {conseil.titre}"
                f" ({len(abonnes)} destinataire(s))"
            )

            envoyes, erreurs = 0, 0
            for abonne in abonnes:
                if dry_run:
                    envoyes += 1
                    continue
                try:
                    _envoyer_email(abonne, conseil, logo_site)
                    envoyes += 1
                except Exception as e:
                    erreurs += 1
                    self.stdout.write(self.style.ERROR(f"    ✗ {abonne.email} : {e}"))

            self.stdout.write(f"    Envoyés : {envoyes} | Erreurs : {erreurs}")

            if not dry_run:
                conseil.statut           = ConseilNewsletter.Statut.ENVOYE
                conseil.date_envoi_reel  = timezone.now()
                conseil.nb_destinataires = envoyes
                conseil.save(update_fields=['statut', 'date_envoi_reel', 'nb_destinataires'])

        self.stdout.write(self.style.SUCCESS("\n✓ Terminé."))


def _envoyer_email(abonne, conseil, logo_site):
    from django.conf import settings

    site_url   = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
    desabo_url = f'{site_url}/candidat/newsletter/desabonnement/{abonne.token_desabonnement}/'

    # URL absolue de l'image pour les clients email
    image_url = ''
    if conseil.image:
        image_url = site_url + conseil.image.url

    ctx = {
        'logo_site':  logo_site,
        'abonne':     abonne,
        'conseil':    conseil,
        'desabo_url': desabo_url,
        'image_url':  image_url,
        'site_url':   site_url,
    }

    sujet = f"{conseil.icone_categorie} {conseil.titre} — {logo_site.nom_site}"
    txt   = render_to_string('candidat/newsletter/email_conseil.txt',  ctx)
    html  = render_to_string('candidat/newsletter/email_conseil.html', ctx)

    msg = EmailMultiAlternatives(subject=sujet, body=txt, to=[abonne.email])
    msg.attach_alternative(html, 'text/html')
    msg.send(fail_silently=False)
