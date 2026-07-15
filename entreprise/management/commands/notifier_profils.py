"""
Commande Django : scan périodique des offres publiées pour notifier les
recruteurs des profils candidats correspondants.

Usage :
    python manage.py notifier_profils                  # toutes les offres PUBLIEE
    python manage.py notifier_profils --offre 42       # une seule offre
    python manage.py notifier_profils --seuil 70       # override le seuil
    python manage.py notifier_profils --dry-run        # simulation sans création

Idempotent : la contrainte unique sur NotificationRecruteur empêche tout
doublon — on peut donc l'appeler en cron à intervalle régulier sans risque
de spam.

Exemple cron (Linux, toutes les heures) :
    0 * * * * cd /app && python manage.py notifier_profils >> /var/log/ats.log 2>&1

Sous Windows (Planificateur de tâches) :
    schtasks /create /tn "ATS Notify" /tr "python manage.py notifier_profils" /sc HOURLY
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Scanne les offres publiées et notifie les recruteurs des profils correspondants."

    def add_arguments(self, parser):
        parser.add_argument(
            '--offre', type=int, default=None,
            help="Limiter à une seule offre (ID).",
        )
        parser.add_argument(
            '--seuil', type=int, default=None,
            help="Score minimum (override criteresATS.scoreMinimum de l'offre).",
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Simulation : affiche les stats mais ne crée aucune notification.",
        )

    def handle(self, *args, **opts):
        from entreprise.models import OffreEmploi, StatutOffre
        from entreprise import notifications_service as svc

        offre_id = opts['offre']
        seuil    = opts['seuil']
        dry_run  = opts['dry_run']

        # Sélection des offres à scanner
        offres = OffreEmploi.objects.filter(statutOffre=StatutOffre.PUBLIEE)
        if offre_id:
            offres = offres.filter(pk=offre_id)

        offres = list(offres.select_related('entreprise'))

        self.stdout.write(self.style.MIGRATE_HEADING(
            "> Scan des profils candidats pour les offres publiées"
        ))
        self.stdout.write(
            f"  Cible : {'offre #'+str(offre_id) if offre_id else f'{len(offres)} offre(s) publiees'}"
            f" | Seuil : {seuil if seuil else 'criteresATS.scoreMinimum par offre'}"
            f" | Mode : {'DRY-RUN' if dry_run else 'reel'}"
        )

        if not offres:
            self.stdout.write(self.style.WARNING("  Aucune offre publiée à scanner."))
            return

        # Stats globales
        total_analyses = 0
        total_matches  = 0
        total_notifs   = 0

        for offre in offres:
            self.stdout.write(f"\n  --- Offre #{offre.id} : {offre.titre} ---")
            if dry_run:
                # En dry-run on simule : on scanne mais ne crée pas
                from entreprise import ats_predict
                from candidat.models import Candidat
                candidats = list(Candidat.objects.filter(portfolioPublic=True))
                seuil_eff = seuil or int((offre.criteresATS or {}).get('scoreMinimum', 60))
                try:
                    scores = ats_predict.scorer_candidats(offre, candidats)
                    matches = [s for s in scores if s['score'] >= seuil_eff]
                    self.stdout.write(
                        f"  -> {len(scores)} analyses, {len(matches)} matches >= {seuil_eff}%."
                    )
                    total_analyses += len(scores)
                    total_matches  += len(matches)
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  ! Erreur : {e}"))
            else:
                try:
                    stats = svc.scanner_profils_pour_offre(offre, seuil=seuil)
                    self.stdout.write(
                        f"  -> {stats['analyses']} analyses, "
                        f"{stats['matches']} matches >= {stats['seuil']}%, "
                        f"{stats['notifs_creees']} notifs creees, "
                        f"{stats['recruteurs_notifies']} recruteurs."
                    )
                    total_analyses += stats['analyses']
                    total_matches  += stats['matches']
                    total_notifs   += stats['notifs_creees']
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  ! Erreur : {e}"))

        self.stdout.write(self.style.SUCCESS(
            f"\nOK Scan termine : {len(offres)} offre(s), "
            f"{total_analyses} analyse(s), {total_matches} match(es), "
            f"{total_notifs} notif(s) creee(s)."
        ))
