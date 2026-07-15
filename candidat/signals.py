"""
Signaux de l'app candidat.

Déclencheurs en place :
  • `OffreEmploi` (post_save) : à la TRANSITION vers PUBLIEE, on lance le scan
    des candidats pour créer/envoyer des notifications de matching.

Le travail est exécuté SYNCHRONEMENT dans le signal — acceptable pour quelques
centaines de candidats (~quelques secondes). Quand le volume grandira, il
faudra passer ce scan en arrière-plan (`recrutement.background.lancer_en_arriere_plan`,
même pattern que `entreprise/notifications_service.py`, ou un cron qui appelle
`python manage.py notifier_matchings --offre <id>`).
"""

from __future__ import annotations

import logging
import threading

from django.core.cache import cache
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Mémoire éphémère : statut précédent (pour détecter les transitions)
# ──────────────────────────────────────────────────────────────────────────────
# Comme pre_save n'a pas accès à `old_instance`, on stocke le statut courant
# (avant save) dans un thread-local indexé par PK.
_etats_avant_save = threading.local()


def _stash_for_pk(pk, statut):
    if not hasattr(_etats_avant_save, 'map'):
        _etats_avant_save.map = {}
    _etats_avant_save.map[pk] = statut


def _pop_for_pk(pk):
    m = getattr(_etats_avant_save, 'map', {})
    return m.pop(pk, None)


# ──────────────────────────────────────────────────────────────────────────────
# OffreEmploi : détection du passage à PUBLIEE
# ──────────────────────────────────────────────────────────────────────────────

def _registrer_signaux():
    """Enregistre les signaux. Fait en fonction pour éviter les imports au top."""
    try:
        from entreprise.models import OffreEmploi, StatutOffre
    except Exception as e:
        logger.warning("Impossible de brancher les signaux OffreEmploi : %s", e)
        return

    @receiver(pre_save, sender=OffreEmploi, weak=False)
    def offre_pre_save(sender, instance, **kwargs):
        """Mémorise l'ancien statut juste avant le save (None si création)."""
        if not instance.pk:
            _stash_for_pk(None, None)
            return
        try:
            ancien = sender.objects.only('statutOffre').get(pk=instance.pk).statutOffre
        except sender.DoesNotExist:
            ancien = None
        _stash_for_pk(instance.pk, ancien)

    @receiver(post_save, sender=OffreEmploi, weak=False)
    def offre_post_save(sender, instance, created, **kwargs):
        """Si transition (None|BROUILLON|...) -> PUBLIEE, scan les candidats."""
        ancien = _pop_for_pk(instance.pk)
        nouveau = instance.statutOffre
        if nouveau != StatutOffre.PUBLIEE:
            return
        # Création directe en PUBLIEE OU transition vers PUBLIEE
        if (created or ancien != StatutOffre.PUBLIEE):
            try:
                from . import notifications_service as svc
                stats = svc.scanner_matchings_pour_offre(instance)
                logger.info(
                    "Notifications matching pour offre #%s (%s) : %s",
                    instance.pk, instance.titre, stats,
                )
            except Exception as e:
                # Ne jamais casser le save de l'offre à cause d'un souci de notif.
                logger.exception("Echec scan notifications offre #%s : %s",
                                 instance.pk, e)


# ──────────────────────────────────────────────────────────────────────────────
# NotificationCandidat : envoi email automatique à la création
# ──────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='candidat.NotificationCandidat', weak=False)
def notif_post_save(sender, instance, created, **kwargs):
    """À chaque nouvelle notification, envoie un email si le candidat a opt-in."""
    if not created:
        return
    if instance.emailEnvoye:
        return

    from . import notifications_service as svc
    from .models import NotificationCandidat

    try:
        if instance.type == NotificationCandidat.Type.OFFRE_MATCH:
            svc.envoyer_email_match(instance)
        else:
            svc.envoyer_email_notification(instance)
    except Exception:
        logger.exception("Echec envoi email pour notification #%s", instance.pk)




# ──────────────────────────────────────────────────────────────────────────────
# Invalidation du cache à la modification des données
# ──────────────────────────────────────────────────────────────────────────────

_CACHE_ACCUEIL_CANDIDAT = [
    'accueil_offres_vedette', 'accueil_top_secteurs', 'accueil_villes_top',
    'accueil_top_entreprises', 'accueil_stats_globales', 'accueil_temoignages',
]

_CACHE_ACCUEIL_ENTREPRISE = [
    'ent_accueil_stats', 'ent_accueil_candidats', 'ent_accueil_temoignages',
]


def _purger_cles(*cles):
    for cle in cles:
        cache.delete(cle)


@receiver(post_save, sender='candidat.ModeleCV', weak=False)
@receiver(post_delete, sender='candidat.ModeleCV', weak=False)
def _invalider_cache_modeles_cv(sender, **kwargs):
    _purger_cles('accueil_modeles', 'accueil_carousel', 'modeles_cv_data')


@receiver(post_save, sender='candidat.ModeleLettre', weak=False)
@receiver(post_delete, sender='candidat.ModeleLettre', weak=False)
def _invalider_cache_modeles_lettre(sender, **kwargs):
    _purger_cles('modeles_lettre_data')


@receiver(post_save, sender='candidat.LogoSite', weak=False)
@receiver(post_delete, sender='candidat.LogoSite', weak=False)
def _invalider_cache_logo(sender, **kwargs):
    cache.clear()


@receiver(post_save, sender='candidat.Temoignage', weak=False)
@receiver(post_delete, sender='candidat.Temoignage', weak=False)
def _invalider_cache_temoignages(sender, **kwargs):
    _purger_cles('accueil_temoignages')


# Champs de `Candidat` sans effet sur les caches accueil (stats globales,
# portfolios/villes/secteurs vedette) : des écritures très fréquentes comme
# `derniereConnexion` à chaque login ne doivent pas invalider ces caches 5 min.
_CHAMPS_SANS_IMPACT_ACCUEIL = {
    'derniereConnexion', 'password', 'notificationsOffresEmail',
    'notificationsInApp', 'alertesActives', 'recommandationsActives',
    'emailVerifie', 'rubriques',
}


@receiver(post_save, sender='candidat.Candidat', weak=False)
@receiver(post_delete, sender='candidat.Candidat', weak=False)
def _invalider_cache_candidat(sender, **kwargs):
    update_fields = kwargs.get('update_fields')
    if update_fields is not None and set(update_fields) <= _CHAMPS_SANS_IMPACT_ACCUEIL:
        return
    _purger_cles('accueil_stats_globales', 'ent_accueil_candidats')


# Lance l'enregistrement à l'import (déclenché par CandidatConfig.ready())
_registrer_signaux()
