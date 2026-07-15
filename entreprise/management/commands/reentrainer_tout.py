"""
Commande Django : ré-entraîne les deux modèles ML (matching candidat + ATS).

Usage :
    python manage.py reentrainer_tout                # entraîne les deux modèles
    python manage.py reentrainer_tout --min 30       # seuil min d'exemples
    python manage.py reentrainer_tout --dry-run      # rapport sans sauvegarde
    python manage.py reentrainer_tout --skip-matching
    python manage.py reentrainer_tout --skip-ats

Conçue pour être appelée par le Planificateur de tâches Windows (ou un cron)
de façon hebdomadaire. Délègue à `entrainer_matching` et `entrainer_ats`,
capture les erreurs individuellement (un modèle peut échouer sans bloquer l'autre)
et affiche un rapport synthétique à la fin.
"""

from __future__ import annotations

import io
import time
from contextlib import redirect_stdout, redirect_stderr

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Ré-entraîne les deux modèles ML (matching + ATS) en une seule commande."

    def add_arguments(self, parser):
        parser.add_argument(
            '--min', type=int, default=30,
            help="Seuil minimum d'exemples requis (transmis aux deux commandes).",
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Affiche le rapport sans sauvegarder les modèles.",
        )
        parser.add_argument(
            '--skip-matching', action='store_true',
            help="Ne pas ré-entraîner le modèle de matching candidat -> offre.",
        )
        parser.add_argument(
            '--skip-ats', action='store_true',
            help="Ne pas ré-entraîner le modèle ATS recruteur.",
        )
        parser.add_argument(
            '--verbose-sub', action='store_true',
            help="Affiche la sortie complète des sous-commandes (sinon résumé).",
        )

    # ──────────────────────────────────────────────────────────────────────

    def handle(self, *args, **opts):
        seuil      = opts['min']
        dry_run    = opts['dry_run']
        skip_match = opts['skip_matching']
        skip_ats   = opts['skip_ats']
        verbose    = opts['verbose_sub']

        self.stdout.write(self.style.MIGRATE_HEADING(
            "=" * 60
        ))
        self.stdout.write(self.style.MIGRATE_HEADING(
            "  Ré-entraînement global des modèles ML RecrutePro"
        ))
        self.stdout.write(self.style.MIGRATE_HEADING(
            "=" * 60
        ))

        rapport = []

        if not skip_match:
            rapport.append(self._lancer(
                'entrainer_matching', 'Matching candidat -> offre',
                seuil, dry_run, verbose,
            ))
        else:
            self.stdout.write(self.style.WARNING("\n[--skip-matching] Matching ignoré."))

        if not skip_ats:
            rapport.append(self._lancer(
                'entrainer_ats', 'ATS recruteur (re-ranking profils)',
                seuil, dry_run, verbose,
            ))
        else:
            self.stdout.write(self.style.WARNING("\n[--skip-ats] ATS ignoré."))

        # ── Rapport final ──────────────────────────────────────────────────
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.MIGRATE_HEADING("  Rapport final"))
        self.stdout.write("=" * 60)

        for nom, statut, duree, message in rapport:
            badge = self.style.SUCCESS("OK  ") if statut == 'ok' else self.style.ERROR("ECHEC")
            self.stdout.write(f"  {badge}  {nom:40s}  ({duree:.1f}s)")
            if message and statut != 'ok':
                # Indente le message d'erreur
                for ligne in message.splitlines()[:3]:
                    self.stdout.write(f"         -> {ligne}")

        nb_ok = sum(1 for r in rapport if r[1] == 'ok')
        if nb_ok == len(rapport) and rapport:
            self.stdout.write(self.style.SUCCESS(
                f"\nTermine : {nb_ok}/{len(rapport)} modeles ré-entraînés avec succès."
            ))
        elif rapport:
            self.stdout.write(self.style.WARNING(
                f"\nTermine : {nb_ok}/{len(rapport)} modeles OK, "
                f"{len(rapport) - nb_ok} en échec."
            ))

    # ──────────────────────────────────────────────────────────────────────

    def _lancer(self, commande: str, label: str,
                seuil: int, dry_run: bool, verbose: bool) -> tuple:
        """Lance une sous-commande et capture son résultat.

        Returns (label, 'ok'|'error', durée_sec, message_ou_vide).
        """
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n>>> {label}"
        ))
        start = time.monotonic()

        kwargs = {'min': seuil, 'dry_run': dry_run}
        buffer_out = io.StringIO()
        buffer_err = io.StringIO()

        try:
            if verbose:
                call_command(commande, **kwargs, stdout=self.stdout, stderr=self.stderr)
            else:
                # Capture la sortie pour ne montrer que les lignes pertinentes
                with redirect_stdout(buffer_out), redirect_stderr(buffer_err):
                    call_command(commande, **kwargs)
                self._afficher_resume(buffer_out.getvalue())
            duree = time.monotonic() - start
            return (label, 'ok', duree, '')
        except Exception as e:
            duree = time.monotonic() - start
            self.stdout.write(self.style.ERROR(f"   X Echec : {e}"))
            return (label, 'error', duree, str(e))

    def _afficher_resume(self, sortie: str) -> None:
        """Extrait quelques lignes clés du log d'une sous-commande."""
        cles = ('candidatures', 'propositions', 'X shape', 'MAE', 'RMSE',
                'R²', 'R2', 'OK Modèle', 'OK Modele', 'Modèle persisté',
                '->', 'Pas assez', 'NON enregistré', 'NON sauvegardé')
        for ligne in sortie.splitlines():
            if any(k in ligne for k in cles):
                self.stdout.write(f"   {ligne.strip()}")
