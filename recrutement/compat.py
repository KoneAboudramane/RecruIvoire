"""Correctifs de compatibilité pour des versions Python plus récentes que
celles ciblées par les dépendances (appliqués au démarrage, voir __init__.py).
"""


def patch_django_basecontext_copy():
    """Corrige `django.template.context.BaseContext.__copy__` (Django 5.1),
    cassé sous Python 3.14 : `copy(super())` n'y délègue plus correctement à
    l'instance concrète, et renvoie un objet `super` sans `__dict__` —
    `AttributeError: 'super' object has no attribute 'dicts' and no __dict__
    for setting new attributes`. Remplacé par une implémentation équivalente
    qui ne passe pas par `copy(super())`. Sans effet néfaste sous les
    versions de Python où le code d'origine fonctionnait déjà (même résultat).
    """
    from django.template.context import BaseContext

    def __copy__(self):
        duplicate = self.__class__.__new__(self.__class__)
        duplicate.__dict__.update(self.__dict__)
        duplicate.dicts = self.dicts[:]
        return duplicate

    BaseContext.__copy__ = __copy__
