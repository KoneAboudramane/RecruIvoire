"""
Middleware : déclencheur web du ré-entraînement ML.

Quand la planification est en mode WEB_TRAFIC, ce middleware vérifie à chaque
requête HTTP si l'heure de la prochaine exécution est passée. Si oui, il lance
le ré-entraînement dans un thread daemon (non bloquant pour la requête).

Sécurités :
  - Lock en mémoire pour éviter deux exécutions simultanées.
  - Marquage immédiat en BD (status='running') pour empêcher d'autres workers
    de relancer entre temps.
  - Échecs capturés et loggés, jamais propagés à la requête HTTP.
"""

from __future__ import annotations

import logging
import threading
import time

from django.utils import timezone

logger = logging.getLogger(__name__)


# Lock global (process-level). Pour multi-process, le marquage BD suffit.
_LOCK = threading.Lock()
_EN_COURS = False


class MLSchedulerMiddleware:
    """Déclenche le ré-entraînement ML quand le mode WEB_TRAFIC est actif."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Best-effort : si la vérification échoue, on ne bloque jamais la requête
        try:
            self._verifier_et_declencher()
        except Exception as e:
            logger.warning("MLSchedulerMiddleware : vérification échouée : %s", e)
        return self.get_response(request)

    @staticmethod
    def _verifier_et_declencher() -> None:
        global _EN_COURS

        # Import local pour éviter les soucis d'init Django
        from .models import PlanificationML, ModePlanif

        if _EN_COURS:
            return

        try:
            planif = PlanificationML.objects.filter(pk=1).first()
        except Exception:
            # Migrations pas encore appliquées, etc.
            return

        if not planif or not planif.active:
            return
        if planif.mode != ModePlanif.WEB_TRAFIC:
            return
        if not planif.prochaine_execution:
            return

        now = timezone.now()
        if now < planif.prochaine_execution:
            return

        # Acquérir le lock sans bloquer la requête
        if not _LOCK.acquire(blocking=False):
            return

        try:
            # Recharger pour relire le statut à jour
            planif.refresh_from_db()
            if planif.derniere_status == 'running':
                return

            planif.derniere_status = 'running'
            planif.save(update_fields=['derniere_status'])

            _EN_COURS = True
            thread = threading.Thread(
                target=_executer_reentrainement_async,
                args=(planif.pk,),
                daemon=True,
                name='MLReentrainement',
            )
            thread.start()
        finally:
            _LOCK.release()


def _executer_reentrainement_async(planif_id: int) -> None:
    """Cible du thread daemon : lance reentrainer_tout puis met à jour la BD."""
    global _EN_COURS
    from django.core.management import call_command
    from django.db import close_old_connections
    import io

    from .models import PlanificationML
    from .ml_scheduler import calculer_prochaine_execution

    start = time.monotonic()
    buffer = io.StringIO()
    status, message = 'ok', ''

    try:
        call_command('reentrainer_tout', stdout=buffer)
    except Exception as e:
        status = 'error'
        message = f"{type(e).__name__}: {e}"
        logger.exception("Ré-entraînement ML déclenché par middleware a échoué")

    duree = time.monotonic() - start

    # Mise à jour BD (avec nouvelle connexion thread)
    close_old_connections()
    try:
        planif = PlanificationML.objects.get(pk=planif_id)
        planif.derniere_execution  = timezone.now()
        planif.derniere_status     = status
        planif.derniere_duree_sec  = duree
        planif.derniere_message    = (message or buffer.getvalue()[-500:])
        planif.prochaine_execution = calculer_prochaine_execution(planif)
        planif.save(update_fields=[
            'derniere_execution', 'derniere_status', 'derniere_duree_sec',
            'derniere_message', 'prochaine_execution',
        ])
    except Exception:
        logger.exception("Impossible de mettre à jour PlanificationML après run")
    finally:
        close_old_connections()
        _EN_COURS = False
