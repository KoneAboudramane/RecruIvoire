"""
Gestion du compteur de visiteurs journaliers uniques.

Règle : une adresse IP n'est comptée qu'une seule fois par jour.
Si le visiteur revient dans la même journée (même IP), il n'est pas recompté.
"""

from datetime import timedelta

from django.conf import settings
from django.core.cache import cache as django_cache
from django.db.models import F, Sum
from django.utils import timezone

from .models import VisiteurJournalier, VisiteIP


def _get_ip(request):
    """
    Récupère l'adresse IP du visiteur.

    Sécurité : X-Forwarded-For peut être forgé par n'importe quel client.
    On ne l'utilise que si le serveur est explicitement configuré derrière
    un proxy de confiance (BEHIND_PROXY=True dans settings).

    En production derrière nginx/Cloudflare, définir BEHIND_PROXY=True
    et s'assurer que nginx filtre et réécrit l'en-tête X-Forwarded-For.
    """
    behind_proxy = getattr(settings, 'BEHIND_PROXY', False)

    if behind_proxy:
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if forwarded:
            # En-tête peut contenir plusieurs IPs : « client, proxy1, proxy2 »
            # La première est l'IP du client réel (si nginx la préserve).
            return forwarded.split(',')[0].strip()

    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def enregistrer_visite(request):
    """
    Enregistre la visite si cette adresse IP n'a pas encore visité aujourd'hui.
    Retourne un dict avec :
      - nb_aujourd_hui : visiteurs uniques du jour
      - nb_30_jours    : total des 30 derniers jours
    """
    today = timezone.localdate()
    ip    = _get_ip(request)

    # get_or_create renvoie (objet, created) — created=True si c'est la première visite
    _, nouvelle_visite = VisiteIP.objects.get_or_create(date=today, adresse_ip=ip)

    if nouvelle_visite:
        # Première visite de cette IP aujourd'hui → incrémenter le compteur
        VisiteurJournalier.objects.get_or_create(date=today)
        VisiteurJournalier.objects.filter(date=today).update(
            nb_visiteurs=F('nb_visiteurs') + 1
        )

    try:
        nb_aujourd_hui = VisiteurJournalier.objects.get(date=today).nb_visiteurs
    except VisiteurJournalier.DoesNotExist:
        nb_aujourd_hui = 0

    # Agrégats 30j / 365j : ne varient qu'une fois par jour au mieux (ils ne
    # bougent que lors de la première visite d'une nouvelle IP) — mis en
    # cache 5 min pour éviter 2 agrégations SUM à chaque chargement de
    # l'accueil, la page la plus fréquentée du site.
    nb_30_jours = django_cache.get('visiteurs_nb_30j')
    if nb_30_jours is None:
        depuis_30j = today - timedelta(days=30)
        nb_30_jours = (
            VisiteurJournalier.objects
            .filter(date__gte=depuis_30j)
            .aggregate(total=Sum('nb_visiteurs'))['total'] or 0
        )
        django_cache.set('visiteurs_nb_30j', nb_30_jours, 300)

    nb_365_jours = django_cache.get('visiteurs_nb_365j')
    if nb_365_jours is None:
        depuis_365j = today - timedelta(days=365)
        nb_365_jours = (
            VisiteurJournalier.objects
            .filter(date__gte=depuis_365j)
            .aggregate(total=Sum('nb_visiteurs'))['total'] or 0
        )
        django_cache.set('visiteurs_nb_365j', nb_365_jours, 300)

    return {
        'nb_aujourd_hui': nb_aujourd_hui,
        'nb_30_jours':    nb_30_jours,
        'nb_365_jours':   nb_365_jours,
    }
