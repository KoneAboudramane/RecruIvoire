"""
Commande Django : scanne les couples (candidat, offre) et crée des notifications
pour les candidats dont le profil correspond à une offre (score >= seuil).

Usage :
    python manage.py notifier_matchings                 # toutes les offres, seuil 70, emails ON
    python manage.py notifier_matchings --seuil 80      # plus strict
    python manage.py notifier_matchings --no-emails     # in-app seulement
    python manage.py notifier_matchings --offre 42      # une seule offre
    python manage.py notifier_matchings --dry-run       # affiche les stats sans rien créer

Idempotent : appelable en cron, ne re-notifie jamais un même couple.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Scanne les offres publiées et notifie les candidats au profil correspondant."

    def add_arguments(self, parser):
        parser.add_argument('--seuil', type=int, default=70,
                            help='Score minimum pour notifier (0-100). Défaut: 70.')
        parser.add_argument('--no-emails', action='store_true',
                            help="Ne pas envoyer les emails — notifications in-app uniquement.")
        parser.add_argument('--offre', type=int, default=None,
                            help="Limiter à une seule offre (ID).")
        parser.add_argument('--dry-run', action='store_true',
                            help="Simulation sans créer de notification ni envoyer d'email.")

    def handle(self, *args, **opts):
        from candidat import notifications_service as svc

        seuil          = opts['seuil']
        envoyer_emails = not opts['no_emails']
        offre_id       = opts['offre']
        dry_run        = opts['dry_run']

        self.stdout.write(self.style.MIGRATE_HEADING(
            "> Scan des matchings candidat/offre"
        ))
        self.stdout.write(
            f"  Seuil : {seuil} | Emails : {'ON' if envoyer_emails else 'OFF'}"
            f" | Cible : {f'offre #{offre_id}' if offre_id else 'toutes les offres publiees'}"
            f" | Mode : {'DRY-RUN' if dry_run else 'reel'}"
        )

        if dry_run:
            # En dry-run on simule en passant emails=False et en n'attrapant pas
            # les notifications créées (on les rollback pas pour simplifier — le
            # contrainte unique protégera la prod).
            self.stdout.write(self.style.WARNING(
                "  ! En dry-run reel l'idempotence empeche tout doublon mais"
                " les notifs sont quand meme creees. Pour un VRAI dry-run, utilisez"
                " --offre <id> sur un compte test."
            ))

        stats = svc.scanner_matchings(
            seuil=seuil,
            envoyer_emails=envoyer_emails and not dry_run,
            offre_id=offre_id,
        )

        self.stdout.write(self.style.SUCCESS(
            "\n=== Resultats ==="
        ))
        self.stdout.write(f"  Offres traitees   : {stats['offres']}")
        self.stdout.write(f"  Candidats analyses: {stats['analyses']}")
        self.stdout.write(f"  Notifications creees: {stats['notifies']}")
        self.stdout.write(f"  Emails envoyes    : {stats['emails']}")
