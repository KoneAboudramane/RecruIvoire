"""Exécution de tâches courtes en arrière-plan, sans worker persistant.

O2switch mutualisé (Passenger/WSGI) ne permet aucun process daemon — un
worker Celery ne peut donc jamais y tourner. Cette fonction généralise le
pattern déjà utilisé dans `entreprise/notifications_service.py` (thread
démon + `close_old_connections()`), qui fonctionne aussi bien en local
(runserver) qu'en prod (Passenger, chaque requête peut spawner ses threads).

Pour les tâches périodiques (pas liées à une requête HTTP précise), voir les
management commands dédiées, déclenchées par cron (cPanel > Tâches Cron).
"""
from __future__ import annotations

import logging
import threading

from django.db import close_old_connections

logger = logging.getLogger(__name__)


def lancer_en_arriere_plan(func, *args, **kwargs):
    """Exécute `func(*args, **kwargs)` dans un thread démon, sans bloquer la requête.

    Les exceptions sont capturées et loggées (jamais propagées à la requête
    HTTP appelante). Ferme la connexion DB du thread à la fin dans tous les cas.
    """
    def _run():
        try:
            func(*args, **kwargs)
        except Exception:
            logger.exception("Tâche arrière-plan %s a échoué", func.__name__)
        finally:
            close_old_connections()

    thread = threading.Thread(target=_run, daemon=True, name=func.__name__)
    thread.start()
    return thread
