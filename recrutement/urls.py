from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.sitemaps.views import sitemap as sitemap_view
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.conf.urls.i18n import i18n_patterns

from pages.views import robots_txt, manifest_json, favicon_png
from pages.sitemaps import StaticViewSitemap, OffreSitemap

admin.site.site_header = "RecrutePro — Administration"
admin.site.site_title  = "RecrutePro Admin"
admin.site.index_title = "Tableau de bord"

# Déplacer Utilisateur et Administrateur dans "Authentification et autorisation"
_original_get_app_list = admin.AdminSite.get_app_list

def _custom_get_app_list(self, request, app_label=None):
    app_list = _original_get_app_list(self, request, app_label)
    auth_app = None
    ref_app = None
    models_a_deplacer = {'Utilisateur', 'Administrateur'}

    for app in app_list:
        if app['app_label'] == 'auth':
            auth_app = app
        elif app['app_label'] == 'referentiel':
            ref_app = app

    if auth_app and ref_app:
        a_garder = []
        for model in ref_app['models']:
            if model.get('object_name') in models_a_deplacer:
                auth_app['models'].append(model)
            else:
                a_garder.append(model)
        ref_app['models'] = a_garder

    return app_list

admin.AdminSite.get_app_list = _custom_get_app_list

# ── Gestionnaires d'erreurs custom ───────────────────────────────────────────
handler404 = 'pages.views.error_404'
handler500 = 'pages.views.error_500'
handler403 = 'pages.views.error_403'

# ── Sitemaps ──────────────────────────────────────────────────────────────────
_sitemaps = {
    'static': StaticViewSitemap,
    'offres': OffreSitemap,
}

# ── URLs techniques (hors i18n — toujours à la racine) ───────────────────────
urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
    path('robots.txt',    robots_txt,    name='robots_txt'),
    path('manifest.json', manifest_json, name='manifest_json'),
    path('favicon.png',   favicon_png,   name='favicon_png'),
    # /favicon.ico est demandé automatiquement par les navigateurs (avant même
    # de lire le <link rel="icon"> de la page) — on le redirige vers la route
    # dynamique plutôt que de servir un fichier statique figé, sinon toute
    # requête directe sur /favicon.ico reste connectée à l'ancien logo pour
    # toujours, indépendamment de LogoSite.
    path('favicon.ico', RedirectView.as_view(url='/favicon.png', permanent=False)),
    path('sitemap.xml', sitemap_view, {'sitemaps': _sitemaps},
         name='django.contrib.sitemaps.views.sitemap'),
]

# ── Routes avec préfixe de langue (/en/, /es/, etc.) — /fr/ reste sans préfixe
urlpatterns += i18n_patterns(
    # Déconnexion admin → redirige vers la page de connexion admin
    path('admin/logout/', auth_views.LogoutView.as_view(next_page='/admin/login/')),
    path('admin/', admin.site.urls),
    path('candidat/', include('candidat.urls')),
    path('entreprise/', include('entreprise.urls')),
    path('referentiel/', include('referentiel.urls')),
    path('', include('pages.urls')),
    path('', include('contenu.urls')),
    path('candidat/oauth/', include('allauth.socialaccount.urls')),
    path('accounts/', include('allauth.urls')),
    path('', RedirectView.as_view(url='candidat/', permanent=False)),
    prefix_default_language=False,
)

if settings.DEBUG and not getattr(settings, 'USE_MINIO', False):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
