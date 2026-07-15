from django.apps import AppConfig


class ContenuConfig(AppConfig):
    name = 'contenu'
    verbose_name = 'Contenu'

    def ready(self):
        import contenu.signals  # noqa: F401
