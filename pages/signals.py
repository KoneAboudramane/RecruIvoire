from django.db.models.signals import post_save, post_delete
from django.core.cache import cache
from django.db import transaction
from .models import (
    Groupe, Element, GroupeElement, FooterGroupe,
    MenuDeroulant, MenuDeroulantElement, MenuDeroulantGroupe,
)

_CACHE_KEYS = ['footer_candidat', 'footer_entreprise', 'navbar_candidat', 'navbar_entreprise']


def _purger():
    cache.delete_many(_CACHE_KEYS)


def _invalider(sender, **kwargs):
    transaction.on_commit(_purger)


for _model in (
    Groupe, Element, GroupeElement, FooterGroupe,
    MenuDeroulant, MenuDeroulantElement, MenuDeroulantGroupe,
):
    post_save.connect(_invalider, sender=_model, weak=False)
    post_delete.connect(_invalider, sender=_model, weak=False)
