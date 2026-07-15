from django.apps import AppConfig


class EntrepriseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'entreprise'

    def ready(self):
        # Branche les signaux (auto-scan ATS à la publication d'une offre)
        from . import signals  # noqa: F401
