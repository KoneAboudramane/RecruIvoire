from django.core.management.base import BaseCommand
from django.utils import timezone
from candidat.models import Entretien


class Command(BaseCommand):
    help = "Passe en REALISE les entretiens PLANIFIE dont la date est dépassée."

    def handle(self, *args, **options):
        maintenant = timezone.now()
        mis_a_jour = Entretien.objects.filter(
            statut=Entretien.StatutEntretien.PLANIFIE,
            dateEntretien__lt=maintenant,
        ).update(
            statut=Entretien.StatutEntretien.REALISE,
            dateModification=maintenant,
        )
        self.stdout.write(self.style.SUCCESS(
            f"{mis_a_jour} entretien(s) passé(s) en REALISE."
        ))
