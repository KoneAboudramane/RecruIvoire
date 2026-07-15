from django.core.cache import cache
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver

from .models import FaqCategorie, FaqQuestion, PageStatique, SectionPage, Fonctionnalite, OffreTarif, ChiffreCle

_FAQ_CACHE_KEY = 'faq_page_data'


def _purger_page(slug):
    """Purge les deux caches liés à une PageStatique : le dict complet
    (`contenu.views._get_page_data`/`tarifs`/`a_propos`) ET l'objet page nu
    (`contenu.views._get_page`, partagé entre ces vues) — les deux doivent
    être invalidés ensemble, sinon `_get_page()` continue de renvoyer une
    page obsolète même après purge du cache "vue" qui l'englobe."""
    cache.delete(f'page_statique_{slug}')
    cache.delete(f'page_statique_obj_{slug}')


@receiver([post_save, post_delete], sender=FaqCategorie)
@receiver([post_save, post_delete], sender=FaqQuestion)
def invalider_cache_faq(sender, **kwargs):
    cache.delete(_FAQ_CACHE_KEY)


@receiver([post_save, post_delete], sender=PageStatique)
def invalider_cache_page_statique(sender, instance, **kwargs):
    _purger_page(instance.slug)


@receiver([post_save, post_delete], sender=SectionPage)
def invalider_cache_section_page(sender, instance, **kwargs):
    _purger_page(instance.page.slug)


@receiver([post_save, post_delete], sender=OffreTarif)
def invalider_cache_offre_tarif(sender, instance, **kwargs):
    _purger_page(instance.page.slug)


@receiver(m2m_changed, sender=OffreTarif.fonctionnalites_choisies.through)
def invalider_cache_m2m_fonctionnalites(sender, instance, action, **kwargs):
    if action not in ('post_add', 'post_remove', 'post_clear'):
        return
    if isinstance(instance, OffreTarif):
        _purger_page(instance.page.slug)
    elif isinstance(instance, Fonctionnalite):
        for offre in instance.offres.select_related('page'):
            _purger_page(offre.page.slug)


@receiver([post_save, post_delete], sender=Fonctionnalite)
def invalider_cache_fonctionnalite_master(sender, instance, **kwargs):
    for offre in instance.offres.select_related('page'):
        _purger_page(offre.page.slug)


@receiver([post_save, post_delete], sender=ChiffreCle)
def invalider_cache_chiffre_cle(sender, instance, **kwargs):
    _purger_page(instance.page.slug)
