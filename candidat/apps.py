from django.apps import AppConfig


class CandidatConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'candidat'

    def ready(self):
        # Importe les signaux pour qu'ils soient enregistrés au boot.
        from . import signals  # noqa: F401
