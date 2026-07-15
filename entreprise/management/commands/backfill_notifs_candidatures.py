"""Crée les NotificationCandidat manquantes pour les candidatures déjà
acceptées / refusées / embauchées.

Utile après l'ajout du système de notification cloche : permet aux candidats
de voir rétroactivement les décisions prises avant la mise en place du système.

Usage :
    python manage.py backfill_notifs_candidatures
    python manage.py backfill_notifs_candidatures --dry-run
"""

from django.core.management.base import BaseCommand
from django.urls import reverse


class Command(BaseCommand):
    help = "Crée les NotificationCandidat manquantes pour les candidatures finalisées."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Affiche ce qui serait créé sans rien écrire.",
        )

    def handle(self, *args, **options):
        from candidat.models import Candidature, NotificationCandidat

        dry_run = options['dry_run']
        lien_base = reverse('candidat:mes_candidatures')

        cibles = (
            Candidature.objects
            .filter(statut__code__in=['ACCEPTEE', 'REFUSEE', 'EMBAUCHEE'])
            .select_related('candidat', 'offre', 'statut')
        )

        cree, deja_ok = 0, 0
        for c in cibles:
            if NotificationCandidat.objects.filter(
                candidat=c.candidat,
                offre=c.offre,
                type=NotificationCandidat.Type.CANDIDATURE,
            ).exists():
                deja_ok += 1
                continue

            if c.statut.code == 'ACCEPTEE':
                titre = f"✅ Candidature acceptée — {c.offre.titre}"
                msg   = f"Votre candidature pour « {c.offre.titre} » a été acceptée."
            elif c.statut.code == 'EMBAUCHEE':
                titre = f"🎉 Félicitations, vous êtes embauché(e) ! — {c.offre.titre}"
                msg   = f"Vous avez été retenu(e) pour le poste « {c.offre.titre} »."
            else:  # REFUSEE
                titre = f"📋 Candidature non retenue — {c.offre.titre}"
                msg   = f"Votre candidature pour « {c.offre.titre} » n'a pas été retenue."

            if not dry_run:
                NotificationCandidat.objects.create(
                    candidat=c.candidat,
                    type=NotificationCandidat.Type.CANDIDATURE,
                    titre=titre,
                    message=msg,
                    lien=f"{lien_base}?offre={c.offre_id}",
                    offre=c.offre,
                )
            cree += 1
            self.stdout.write(
                f"  + {c.reference} [{c.statut.code}] → {c.candidat.email}"
            )

        prefix = '[DRY-RUN] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}{cree} notification(s) créée(s) · {deja_ok} déjà en place."
        ))
