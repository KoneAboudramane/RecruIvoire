from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

_site_url = getattr(settings, 'SITE_URL', 'https://www.recrutepro.ci').rstrip('/')
_protocol, _domain = (_site_url.split('://') + [''])[:2] if '://' in _site_url else ('https', _site_url)


class StaticViewSitemap(Sitemap):
    protocol = _protocol
    i18n = False

    @property
    def domain(self):
        return _domain

    _pages = [
        # (url_name, priority, changefreq)
        ('candidat:accueil',       1.0, 'daily'),
        ('candidat:offres',        0.9, 'daily'),
        ('contenu:tarifs',           0.7, 'monthly'),
        ('contenu:a_propos',         0.6, 'monthly'),
        ('contenu:faq',              0.6, 'monthly'),
        ('contenu:contact',          0.5, 'monthly'),
        ('contenu:cgu',              0.3, 'yearly'),
        ('contenu:confidentialite',  0.3, 'yearly'),
        ('contenu:mentions_legales', 0.3, 'yearly'),
    ]

    def items(self):
        return self._pages

    def location(self, item):
        return reverse(item[0])

    def priority(self, item):
        return item[1]

    def changefreq(self, item):
        return item[2]


class OffreSitemap(Sitemap):
    protocol = _protocol
    changefreq = 'weekly'
    priority = 0.8

    @property
    def domain(self):
        return _domain

    def items(self):
        from entreprise.models import OffreEmploi, StatutOffre
        return OffreEmploi.objects.filter(
            statutOffre=StatutOffre.PUBLIEE
        ).order_by('-datePublication')

    def location(self, offre):
        return reverse('candidat:offre_detail', args=[offre.pk])

    def lastmod(self, offre):
        return offre.datePublication
