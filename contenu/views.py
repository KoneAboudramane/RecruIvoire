import json

from django.core.cache import cache
from django.shortcuts import render

from .models import ContactConfig, ContactCategorie, FaqCategorie, FaqQuestion, PageStatique

_FAQ_CACHE_KEY = 'faq_page_data'


def _get_page(slug):
    """Retourne le `PageStatique` (slug, actif=True) depuis le cache Redis ou
    la base — `None` si aucune page active pour ce slug.

    Partagé par toutes les vues ci-dessous pour éviter de dupliquer la
    requête + le `try/except DoesNotExist` (et la durée de cache 3600s)
    à chaque vue qui a besoin, en plus des sections, d'autres relations
    de la page (offres pour `tarifs`, chiffres pour `a_propos`...).
    """
    key = f'page_statique_obj_{slug}'
    page = cache.get(key)
    if page is None:
        try:
            page = PageStatique.objects.get(slug=slug, actif=True)
        except PageStatique.DoesNotExist:
            page = False  # sentinel distinct de « pas encore en cache »
        cache.set(key, page, 3600)
    return page or None


def _get_page_data(slug):
    """Retourne {'page', 'sections'} depuis le cache Redis ou la base."""
    key = f'page_statique_{slug}'
    data = cache.get(key)
    if data is None:
        page = _get_page(slug)
        sections = list(page.sections.filter(actif=True).order_by('ordre')) if page else []
        data = {'page': page, 'sections': sections}
        cache.set(key, data, 3600)
    return data


def mentions_legales(request):
    ctx = _get_page_data('mentions-legales')
    return render(request, 'contenu/mentions_legales.html', ctx)


def tarifs(request):
    key = 'page_statique_tarifs'
    data = cache.get(key)
    if data is None:
        page = _get_page('tarifs')
        offres = list(
            page.offres.filter(actif=True)
            .order_by('groupe', 'ordre')
            .prefetch_related('fonctionnalites_choisies')
        ) if page else []
        data = {
            'page':               page,
            'offres_candidat':    [o for o in offres if o.groupe == 'candidat'],
            'offres_entreprise':  [o for o in offres if o.groupe == 'entreprise'],
        }
        cache.set(key, data, 3600)
    return render(request, 'contenu/tarifs.html', data)


def faq(request):
    page_data = _get_page_data('faq')
    data = cache.get(_FAQ_CACHE_KEY)
    if data is None:
        categories = list(
            FaqCategorie.objects.filter(actif=True)
            .order_by('ordre', 'label')
            .values('id', 'slug', 'label', 'icone')
        )
        cats_json = [{'id': 'tous', 'slug': 'tous', 'label': 'Toutes les questions', 'icone': '🗂️'}] + [
            {'id': c['slug'], 'slug': c['slug'], 'label': c['label'], 'icone': c['icone']}
            for c in categories
        ]
        faqs_json = [
            {
                'id':  f'{q["categorie__slug"]}_{q["id"]}',
                'cat': q['categorie__slug'],
                'q':   q['question'],
                'a':   q['reponse'],
            }
            for q in FaqQuestion.objects.filter(actif=True, categorie__actif=True)
            .order_by('categorie__ordre', 'ordre')
            .values('id', 'question', 'reponse', 'categorie__slug')
        ]
        data = {
            'categories_json': json.dumps(cats_json, ensure_ascii=False),
            'faqs_json':       json.dumps(faqs_json, ensure_ascii=False),
        }
        cache.set(_FAQ_CACHE_KEY, data, 3600)
    return render(request, 'contenu/faq.html', {**data, 'page': page_data['page']})


def contact(request):
    page_data  = _get_page_data('contact')
    config     = ContactConfig.get()
    categories = list(ContactCategorie.objects.filter(actif=True).values_list('label', flat=True))
    if not categories:
        categories = ['Question générale', 'Problème technique', 'Abonnement Premium',
                      'Signaler un bug', 'Partenariat', 'Autre']
    return render(request, 'contenu/contact.html', {
        'page':            page_data['page'],
        'config':          config,
        'categories_json': json.dumps(categories, ensure_ascii=False),
    })


def confidentialite(request):
    ctx = _get_page_data('confidentialite')
    return render(request, 'contenu/confidentialite.html', ctx)


def cgu(request):
    ctx = _get_page_data('cgu')
    return render(request, 'contenu/cgu.html', ctx)


def a_propos(request):
    key = 'page_statique_a-propos'
    data = cache.get(key)
    if data is None:
        page = _get_page('a-propos')
        sections = list(page.sections.filter(actif=True).order_by('ordre')) if page else []
        chiffres = list(page.chiffres.filter(actif=True).order_by('ordre')) if page else []
        data = {
            'page':               page,
            'section_mission':    next((s for s in sections if s.ancre == 'mission'), None),
            'section_vision':     next((s for s in sections if s.ancre == 'vision'), None),
            'valeurs':            [s for s in sections if s.ancre.startswith('valeur')],
            'etapes_candidat':    [s for s in sections if s.ancre.startswith('etape-candidat')],
            'etapes_entreprise':  [s for s in sections if s.ancre.startswith('etape-entreprise')],
            'chiffres':           chiffres,
        }
        cache.set(key, data, 3600)
    return render(request, 'contenu/a_propos.html', data)
