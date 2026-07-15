"""
Signaux Django de l'app entreprise.

Pour l'instant : auto-scan ATS quand une offre passe au statut PUBLIEE.
Le scan tourne dans un thread démon pour ne pas bloquer la requête HTTP.
"""

from __future__ import annotations

import logging

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

from .models import OffreEmploi, StatutOffre

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Auto-scan ATS à la publication d'une offre
# ──────────────────────────────────────────────────────────────────────────────

@receiver(pre_save, sender=OffreEmploi)
def _capture_ancien_statut(sender, instance, **kwargs):
    """Mémorise le statut avant save() pour détecter une transition.

    Stocké sur l'instance (in-memory) — utilisé par le post_save associé.
    """
    if instance.pk:
        try:
            old = OffreEmploi.objects.only('statutOffre').get(pk=instance.pk)
            instance._ancien_statut = old.statutOffre
        except OffreEmploi.DoesNotExist:
            instance._ancien_statut = None
    else:
        instance._ancien_statut = None


@receiver(post_save, sender=OffreEmploi)
def _on_offre_publiee(sender, instance, created, **kwargs):
    """Quand une offre passe au statut PUBLIEE, déclenche un scan ATS async.

    Cas couverts :
      • Offre créée directement en PUBLIEE
      • Offre BROUILLON → PUBLIEE (modification)
      • Offre ARCHIVEE/PAUSE → PUBLIEE (republication)

    PAS déclenché si l'offre est juste mise à jour en gardant PUBLIEE
    (évite les re-scans inutiles à chaque sauvegarde).
    """
    nouveau = instance.statutOffre
    ancien  = getattr(instance, '_ancien_statut', None)

    transition_publication = (
        nouveau == StatutOffre.PUBLIEE
        and ancien != StatutOffre.PUBLIEE
    )
    if not transition_publication:
        return

    # On attend que la transaction soit committée avant de spawner le thread
    # (sinon le thread peut lire des données pas encore persistées).
    def _go():
        try:
            from . import notifications_service
            notifications_service.lancer_scan_offre_async(instance)
            logger.info("Auto-scan ATS lancé pour offre #%s (publication).", instance.id)
        except Exception:
            logger.exception("Échec du lancement du scan async pour offre #%s", instance.id)

    transaction.on_commit(_go)


# ──────────────────────────────────────────────────────────────────────────────
# Invalidation du cache à la modification des données
# ──────────────────────────────────────────────────────────────────────────────

_CACHE_OFFRE = [
    'accueil_offres_vedette', 'accueil_top_secteurs', 'accueil_villes_top',
    'accueil_top_entreprises', 'accueil_stats_globales', 'ent_accueil_stats',
]

_CACHE_ENTREPRISE = [
    'accueil_top_entreprises', 'accueil_stats_globales', 'ent_accueil_stats',
]


def _purger_cles(*cles):
    for cle in cles:
        cache.delete(cle)


@receiver(post_save, sender=OffreEmploi)
@receiver(post_delete, sender=OffreEmploi)
def _invalider_cache_offre(sender, **kwargs):
    _purger_cles(*_CACHE_OFFRE)


@receiver(post_save, sender='entreprise.Entreprise')
@receiver(post_delete, sender='entreprise.Entreprise')
def _invalider_cache_entreprise(sender, **kwargs):
    _purger_cles(*_CACHE_ENTREPRISE)


@receiver(post_save, sender='entreprise.TemoignageEntreprise')
@receiver(post_delete, sender='entreprise.TemoignageEntreprise')
def _invalider_cache_temoignage_ent(sender, **kwargs):
    _purger_cles('ent_accueil_temoignages')
