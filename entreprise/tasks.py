"""Tâches Celery pour le calcul des embeddings ATS.

Le modèle ML est chargé une seule fois dans le worker Celery (singleton).
Les workers web (Daphne) n'ont jamais besoin de charger le modèle.
"""
from celery import shared_task


@shared_task
def calculer_embedding_candidat(candidat_id):
    """Calcule et stocke l'embedding d'un candidat."""
    from candidat.models import Candidat
    from .ats_predict import extraire_texte_candidat, get_model
    from django.utils import timezone

    try:
        candidat = Candidat.objects.get(pk=candidat_id)
    except Candidat.DoesNotExist:
        return

    texte = extraire_texte_candidat(candidat)
    if not texte.strip():
        candidat.embedding = None
        candidat.embedding_updated = None
        candidat.save(update_fields=['embedding', 'embedding_updated'])
        return

    emb = get_model().encode(texte).tolist()
    candidat.embedding = emb
    candidat.embedding_updated = timezone.now()
    candidat.save(update_fields=['embedding', 'embedding_updated'])


@shared_task
def calculer_embedding_offre(offre_id):
    """Calcule et stocke l'embedding d'une offre."""
    from .models import OffreEmploi
    from .ats_predict import extraire_texte_offre, get_model
    from django.utils import timezone

    try:
        offre = OffreEmploi.objects.get(pk=offre_id)
    except OffreEmploi.DoesNotExist:
        return

    texte = extraire_texte_offre(offre)
    if not texte.strip():
        offre.embedding = None
        offre.embedding_updated = None
        offre.save(update_fields=['embedding', 'embedding_updated'])
        return

    emb = get_model().encode(texte).tolist()
    offre.embedding = emb
    offre.embedding_updated = timezone.now()
    offre.save(update_fields=['embedding', 'embedding_updated'])


@shared_task
def calculer_tous_embeddings_manquants():
    """Calcule les embeddings pour tous les candidats et offres qui n'en ont pas."""
    from candidat.models import Candidat
    from .models import OffreEmploi

    candidats = Candidat.objects.filter(embedding__isnull=True).values_list('id', flat=True)
    for cid in candidats:
        calculer_embedding_candidat.delay(cid)

    offres = OffreEmploi.objects.filter(embedding__isnull=True).values_list('id', flat=True)
    for oid in offres:
        calculer_embedding_offre.delay(oid)
