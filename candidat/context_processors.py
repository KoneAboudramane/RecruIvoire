from django.core.cache import cache
from .models import LogoSite


def logo_site(request):
    """Injecte ``logo_site`` et ``favicon_url`` dans tous les templates (cache 1h).

    `favicon_url` porte un paramètre de version dérivé de
    `LogoSite.date_modification` : il change automatiquement à chaque
    nouveau logo, ce qui force le navigateur à recharger l'icône d'onglet.
    Sans ça, l'URL fixe `/favicon.png` reste en cache navigateur (24h via
    `Cache-Control` sur `pages.views.favicon_png`, souvent plus en pratique
    pour un favicon déjà chargé par l'onglet) même après un nouveau logo.
    """
    obj = cache.get('logo_site_actif')
    if obj is None:
        obj = LogoSite.get_actif()
        cache.set('logo_site_actif', obj, 3600)
    if obj and obj.date_modification:
        favicon_url = f'/favicon.png?v={int(obj.date_modification.timestamp())}'
    else:
        favicon_url = '/favicon.png'
    return {'logo_site': obj, 'favicon_url': favicon_url}
