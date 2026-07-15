"""Tâches de calcul des embeddings ATS, lancées en arrière-plan.

Ces fonctions sont appelées via `recrutement.background.lancer_en_arriere_plan()`
(thread démon, cf. `candidat/views/profil.py`, `entreprise/views/offres.py`)
plutôt qu'en synchrone dans la vue, pour ne jamais bloquer une réponse HTTP
sur le chargement du modèle + l'encodage.

`calculer_tous_embeddings_manquants()` est le rattrapage périodique — voir la
management command `entreprise calculer_embeddings_manquants`, déclenchée par
cron (pas de worker persistant possible sous Passenger/O2switch).
"""


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


def calculer_tous_embeddings_manquants():
    """Calcule les embeddings pour tous les candidats et offres qui n'en ont pas.

    Appelée en synchrone par la management command `calculer_embeddings_manquants`
    (exécution cron périodique) — pas de mise en file d'attente ici, le cron
    fournit déjà l'exécution différée.

    Renvoie (nb_candidats, nb_offres) traités.
    """
    from candidat.models import Candidat
    from .models import OffreEmploi

    candidats = list(
        Candidat.objects.filter(embedding__isnull=True).values_list('id', flat=True)
    )
    for cid in candidats:
        calculer_embedding_candidat(cid)

    offres = list(
        OffreEmploi.objects.filter(embedding__isnull=True).values_list('id', flat=True)
    )
    for oid in offres:
        calculer_embedding_offre(oid)

    return len(candidats), len(offres)
