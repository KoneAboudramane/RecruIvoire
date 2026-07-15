"""
Module de planification du ré-entraînement des modèles ML.

Architecture multi-OS via pattern Adapter :

    ┌──────────────────────────────────────────────────┐
    │  enregistrer(planif)  /  supprimer()  /  statut()│  ← API publique
    └────────────┬─────────────────────────────────────┘
                 │
                 ▼  selon planif.mode + OS détecté
       ┌─────────┴──────────┬──────────────────┐
       │                    │                  │
   WindowsAdapter      UnixAdapter      DatabaseAdapter
   (schtasks)          (crontab)        (déclencheur web)

  - mode = OS_NATIF   → adapter de l'OS courant (schtasks / crontab)
  - mode = WEB_TRAFIC → DatabaseAdapter (un middleware HTTP déclenche
                        l'exécution quand l'heure est passée)

Si l'adapter OS échoue (binaire absent, droits insuffisants…), on bascule
sur le DatabaseAdapter comme filet de sécurité, et le statut retourné
le mentionne explicitement.
"""

from __future__ import annotations

import logging
import platform
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, time as dt_time
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# Nom de la tâche système (schtasks / cron tag)
TASK_NAME = 'RecrutePro_ReentrainerML'
CRON_TAG  = '# RecrutePro_ReentrainerML'


# ──────────────────────────────────────────────────────────────────────────────
# Résultat d'opération
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class Resultat:
    ok:         bool
    methode:    str            # 'schtasks' | 'cron' | 'database' | 'manuel'
    message:    str = ''
    detail:     str = ''       # sortie console brute (debug)
    fallback:   bool = False   # True si on est passé sur DatabaseAdapter par défaut


# ──────────────────────────────────────────────────────────────────────────────
# Utilitaires partagés
# ──────────────────────────────────────────────────────────────────────────────

def _python_executable() -> str:
    """Chemin de l'interpréteur Python à utiliser dans le job planifié."""
    return sys.executable


def _manage_py() -> str:
    """Chemin absolu vers manage.py."""
    return str(Path(settings.BASE_DIR) / 'manage.py')


def _commande_complete() -> str:
    """Commande shell exécutée par le planificateur OS."""
    return f'"{_python_executable()}" "{_manage_py()}" reentrainer_tout'


def calculer_prochaine_execution(planif, depuis: Optional[datetime] = None) -> datetime:
    """Calcule la prochaine date/heure d'exécution selon la fréquence.

    Renvoie un datetime aware (timezone settings.TIME_ZONE).
    """
    from .models import FrequencePlanif

    now = depuis or timezone.localtime()
    h, m = planif.heure.hour, planif.heure.minute

    if planif.frequence == FrequencePlanif.QUOTIDIEN:
        candidat = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if candidat <= now:
            candidat += timedelta(days=1)
        return candidat

    if planif.frequence == FrequencePlanif.HEBDOMADAIRE:
        candidat = now.replace(hour=h, minute=m, second=0, microsecond=0)
        # weekday() : 0=lundi … 6=dimanche
        delta_jours = (planif.jour_semaine - now.weekday()) % 7
        candidat += timedelta(days=delta_jours)
        if candidat <= now:
            candidat += timedelta(days=7)
        return candidat

    if planif.frequence == FrequencePlanif.MENSUEL:
        jour = max(1, min(28, planif.jour_mois))
        candidat = now.replace(day=jour, hour=h, minute=m, second=0, microsecond=0)
        if candidat <= now:
            # Mois suivant
            year, month = candidat.year, candidat.month + 1
            if month > 12:
                month, year = 1, year + 1
            candidat = candidat.replace(year=year, month=month)
        return candidat

    # Défaut : dans 24h
    return now + timedelta(days=1)


# ──────────────────────────────────────────────────────────────────────────────
# Adapter : Windows (schtasks)
# ──────────────────────────────────────────────────────────────────────────────

class WindowsAdapter:
    """Crée/supprime une tâche planifiée via le Planificateur de tâches Windows."""

    @staticmethod
    def disponible() -> bool:
        if platform.system() != 'Windows':
            return False
        try:
            r = subprocess.run(
                ['schtasks', '/?'], capture_output=True, timeout=5,
            )
            return r.returncode == 0
        except (FileNotFoundError, subprocess.SubprocessError):
            return False

    @staticmethod
    def enregistrer(planif) -> Resultat:
        from .models import FrequencePlanif

        # Supprimer d'abord l'ancienne tâche si elle existe (idempotent)
        WindowsAdapter.supprimer()

        heure_str = planif.heure.strftime('%H:%M')

        args = [
            'schtasks', '/Create',
            '/TN', TASK_NAME,
            '/TR', _commande_complete(),
            '/ST', heure_str,
            '/F',  # Force (écrase si existe)
            '/RL', 'LIMITED',  # Pas de privilèges élevés
        ]

        if planif.frequence == FrequencePlanif.QUOTIDIEN:
            args += ['/SC', 'DAILY']
        elif planif.frequence == FrequencePlanif.HEBDOMADAIRE:
            jours = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
            args += ['/SC', 'WEEKLY', '/D', jours[planif.jour_semaine]]
        elif planif.frequence == FrequencePlanif.MENSUEL:
            args += ['/SC', 'MONTHLY', '/D', str(planif.jour_mois)]

        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=15)
            if r.returncode == 0:
                return Resultat(
                    ok=True, methode='schtasks',
                    message=f"Tâche Windows « {TASK_NAME} » planifiée.",
                    detail=r.stdout,
                )
            return Resultat(
                ok=False, methode='schtasks',
                message=f"Échec schtasks (code {r.returncode}).",
                detail=(r.stderr or r.stdout)[:500],
            )
        except subprocess.SubprocessError as e:
            return Resultat(
                ok=False, methode='schtasks',
                message=f"Erreur schtasks : {e}", detail=str(e),
            )

    @staticmethod
    def supprimer() -> Resultat:
        try:
            r = subprocess.run(
                ['schtasks', '/Delete', '/TN', TASK_NAME, '/F'],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0:
                return Resultat(ok=True, methode='schtasks',
                                message='Tâche Windows supprimée.')
            # Code 1 = pas trouvée → succès idempotent
            if 'ERROR:' in (r.stderr or '') and 'cannot find' in (r.stderr or '').lower():
                return Resultat(ok=True, methode='schtasks',
                                message='Aucune tâche à supprimer.')
            return Resultat(ok=True, methode='schtasks', message='Tâche supprimée.',
                            detail=r.stderr)
        except subprocess.SubprocessError as e:
            return Resultat(ok=False, methode='schtasks',
                            message=f"Erreur suppression : {e}")

    @staticmethod
    def statut() -> dict:
        try:
            r = subprocess.run(
                ['schtasks', '/Query', '/TN', TASK_NAME, '/FO', 'LIST', '/V'],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode != 0:
                return {'present': False}
            info = {'present': True, 'methode': 'schtasks'}
            for ligne in r.stdout.splitlines():
                ligne = ligne.strip()
                if ligne.startswith('Next Run Time:') or ligne.startswith('Prochaine exécution'):
                    info['prochaine'] = ligne.split(':', 1)[1].strip()
                elif ligne.startswith('Last Run Time:') or ligne.startswith('Dernière exécution'):
                    info['derniere'] = ligne.split(':', 1)[1].strip()
                elif ligne.startswith('Last Result:') or ligne.startswith('Dernier résultat'):
                    info['code'] = ligne.split(':', 1)[1].strip()
            return info
        except subprocess.SubprocessError:
            return {'present': False}


# ──────────────────────────────────────────────────────────────────────────────
# Adapter : Unix (crontab)
# ──────────────────────────────────────────────────────────────────────────────

class UnixAdapter:
    """Crée/supprime une entrée dans le crontab de l'utilisateur courant."""

    @staticmethod
    def disponible() -> bool:
        if platform.system() == 'Windows':
            return False
        try:
            r = subprocess.run(['crontab', '-l'], capture_output=True, timeout=5)
            # exit 0 (crontab existe) ou exit 1 + "no crontab" → crontab CLI OK
            return r.returncode in (0, 1)
        except (FileNotFoundError, subprocess.SubprocessError):
            return False

    @staticmethod
    def _lire_crontab() -> str:
        """Renvoie le crontab actuel (chaîne vide si vide)."""
        try:
            r = subprocess.run(['crontab', '-l'], capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                return r.stdout
            return ''  # 'no crontab for user'
        except subprocess.SubprocessError:
            return ''

    @staticmethod
    def _ecrire_crontab(contenu: str) -> bool:
        try:
            r = subprocess.run(['crontab', '-'], input=contenu, text=True,
                               capture_output=True, timeout=5)
            return r.returncode == 0
        except subprocess.SubprocessError:
            return False

    @staticmethod
    def _purger_lignes_rp(crontab: str) -> str:
        """Retire les anciennes lignes RecrutePro du crontab."""
        gardees = []
        skip_next = False
        for ligne in crontab.splitlines():
            if CRON_TAG in ligne:
                skip_next = True
                continue
            if skip_next:
                skip_next = False
                # On saute aussi la ligne immédiatement après le tag (la ligne cron)
                continue
            gardees.append(ligne)
        return '\n'.join(gardees).strip() + '\n' if gardees else ''

    @staticmethod
    def _expression_cron(planif) -> str:
        from .models import FrequencePlanif
        h, m = planif.heure.hour, planif.heure.minute

        if planif.frequence == FrequencePlanif.QUOTIDIEN:
            return f'{m} {h} * * *'
        if planif.frequence == FrequencePlanif.HEBDOMADAIRE:
            # cron: 0=dim, 1=lun, …, 6=sam ; Django: 0=lun, …, 6=dim
            cron_dow = (planif.jour_semaine + 1) % 7
            return f'{m} {h} * * {cron_dow}'
        if planif.frequence == FrequencePlanif.MENSUEL:
            return f'{m} {h} {planif.jour_mois} * *'
        return f'{m} {h} * * *'

    @staticmethod
    def enregistrer(planif) -> Resultat:
        actuel = UnixAdapter._lire_crontab()
        purge  = UnixAdapter._purger_lignes_rp(actuel)
        expr   = UnixAdapter._expression_cron(planif)
        commande = _commande_complete()

        nouveau = (purge + '\n' if purge and not purge.endswith('\n') else purge)
        nouveau += f'{CRON_TAG}\n{expr} {commande}\n'

        if UnixAdapter._ecrire_crontab(nouveau):
            return Resultat(ok=True, methode='cron',
                            message=f"Entrée crontab ajoutée ({expr}).")
        return Resultat(ok=False, methode='cron',
                        message="Échec écriture crontab.")

    @staticmethod
    def supprimer() -> Resultat:
        actuel = UnixAdapter._lire_crontab()
        purge  = UnixAdapter._purger_lignes_rp(actuel)
        if UnixAdapter._ecrire_crontab(purge):
            return Resultat(ok=True, methode='cron', message='Entrée crontab supprimée.')
        return Resultat(ok=False, methode='cron', message='Échec suppression crontab.')

    @staticmethod
    def statut() -> dict:
        actuel = UnixAdapter._lire_crontab()
        present = CRON_TAG in actuel
        return {'present': present, 'methode': 'cron'}


# ──────────────────────────────────────────────────────────────────────────────
# Adapter : Database / Web fallback
# ──────────────────────────────────────────────────────────────────────────────

class DatabaseAdapter:
    """Pas de système externe : la prochaine exécution est stockée en BD.

    Un middleware HTTP (cf. `entreprise.middleware_ml.MLSchedulerMiddleware`)
    vérifie à chaque requête si `now >= prochaine_execution` et lance
    le ré-entraînement dans un thread daemon.
    """

    @staticmethod
    def disponible() -> bool:
        return True  # toujours dispo

    @staticmethod
    def enregistrer(planif) -> Resultat:
        # La logique métier est faite côté vue (on sauvegarde planif.prochaine_execution)
        return Resultat(
            ok=True, methode='database',
            message=("Mode trafic web : l'entraînement se déclenchera lors "
                     "d'une visite HTTP après l'heure prévue."),
        )

    @staticmethod
    def supprimer() -> Resultat:
        return Resultat(ok=True, methode='database', message='Désactivée.')

    @staticmethod
    def statut() -> dict:
        return {'present': True, 'methode': 'database'}


# ──────────────────────────────────────────────────────────────────────────────
# API publique : sélection de l'adapter
# ──────────────────────────────────────────────────────────────────────────────

def _adapter_pour(planif):
    """Renvoie l'adapter à utiliser selon le mode et l'OS."""
    from .models import ModePlanif

    if planif.mode == ModePlanif.WEB_TRAFIC:
        return DatabaseAdapter, False

    # OS_NATIF : essaie l'adapter de l'OS courant
    if platform.system() == 'Windows':
        if WindowsAdapter.disponible():
            return WindowsAdapter, False
    else:
        if UnixAdapter.disponible():
            return UnixAdapter, False

    # Fallback : DatabaseAdapter
    return DatabaseAdapter, True


def enregistrer(planif) -> Resultat:
    """Enregistre/met à jour la planification dans le système approprié.

    `planif` est l'instance `PlanificationML` à appliquer (déjà sauvegardée).
    """
    adapter, fallback = _adapter_pour(planif)
    res = adapter.enregistrer(planif)
    res.fallback = fallback
    if fallback:
        res.message = (
            "Adapter OS indisponible — bascule sur le déclencheur web. "
        ) + res.message
    return res


def supprimer(planif=None) -> Resultat:
    """Supprime la planification de TOUS les adapters (idempotent)."""
    # On essaie de purger partout, peu importe le mode actuel
    resultats = []
    if WindowsAdapter.disponible():
        resultats.append(WindowsAdapter.supprimer())
    if UnixAdapter.disponible():
        resultats.append(UnixAdapter.supprimer())
    DatabaseAdapter.supprimer()
    # Renvoie le 1er OK ou le 1er échec
    for r in resultats:
        if r.ok:
            return r
    return Resultat(ok=True, methode='database', message='Planification désactivée.')


def statut(planif) -> dict:
    """Renvoie l'état de la planification (présence, prochaine, méthode)."""
    adapter, fallback = _adapter_pour(planif)
    info = adapter.statut()
    info['fallback'] = fallback
    info['adapter']  = adapter.__name__
    info['os']       = platform.system()
    return info


def os_courant() -> str:
    return platform.system()


def adapters_disponibles() -> dict:
    """Pour la UI : indique quels adapters sont opérationnels."""
    return {
        'windows':  WindowsAdapter.disponible(),
        'unix':     UnixAdapter.disponible(),
        'database': True,
        'os':       platform.system(),
    }
