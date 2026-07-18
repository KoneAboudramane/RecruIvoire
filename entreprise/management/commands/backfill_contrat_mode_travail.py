"""Retro-remplit `OffreEmploi.contrat` / `modeTravailRef` (FK referentiel)
depuis les champs legacy `typeContrat` / `modeTravail` (CharField) pour les
offres creees avant l'ajout des FK.

Sans ce backfill, ces offres affichent correctement leur contrat/mode sur la
page de detail (qui lit encore le legacy en repli) mais le formulaire
d'edition — qui ne lit que le FK — les montre comme non selectionnes.
Idempotent : ne touche que les offres dont le FK est encore vide.

Usage :
    python manage.py backfill_contrat_mode_travail
    python manage.py backfill_contrat_mode_travail --dry-run
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Retro-remplit OffreEmploi.contrat / modeTravailRef depuis les champs legacy."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Affiche ce qui serait mis a jour sans rien ecrire.",
        )

    def handle(self, *args, **options):
        from entreprise.models import OffreEmploi
        from entreprise.views._helpers import resoudre_contrat_et_mode_travail

        dry_run = options['dry_run']
        maj_contrat = 0
        maj_mode = 0
        non_resolues = []

        offres = OffreEmploi.objects.filter(contrat__isnull=True) | OffreEmploi.objects.filter(modeTravailRef__isnull=True)
        for offre in offres.distinct():
            contrat, mode_travail = resoudre_contrat_et_mode_travail(offre)

            champs = []
            if offre.contrat_id is None and contrat is not None:
                offre.contrat = contrat
                champs.append('contrat')
                maj_contrat += 1
            if offre.modeTravailRef_id is None and mode_travail is not None:
                offre.modeTravailRef = mode_travail
                champs.append('modeTravailRef')
                maj_mode += 1

            if champs and not dry_run:
                offre.save(update_fields=champs)

            if offre.contrat_id is None and offre.typeContrat and contrat is None:
                non_resolues.append(f"offre #{offre.pk} : typeContrat={offre.typeContrat!r} sans correspondance referentiel")
            if offre.modeTravailRef_id is None and offre.modeTravail and mode_travail is None:
                non_resolues.append(f"offre #{offre.pk} : modeTravail={offre.modeTravail!r} sans correspondance referentiel")

        prefixe = "[dry-run] " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefixe}{maj_contrat} offre(s) mise(s) a jour (contrat), "
            f"{maj_mode} offre(s) mise(s) a jour (mode de travail)."
        ))
        for msg in non_resolues:
            self.stdout.write(self.style.WARNING(msg))
