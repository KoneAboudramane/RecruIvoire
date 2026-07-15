"""Résolution des `Niveau` (référentiel) pour le payload CV.

Le payload JSON de l'éditeur CV stocke désormais un `niveau_id` (FK vers
`referentiel.Niveau`) plutôt qu'un code CEFR ou un entier d'étoiles. Ces
helpers résolvent l'ID à partir d'une compétence ou d'une langue de
candidat, avec fallback rétro-compat sur les anciens champs
`valeurEtoiles` / `niveauCode`.
"""

from referentiel.models import Niveau


def resolve_competence_niveau_id(competence, niveaux_idx=None):
    """`Competence` (modèle) → id Niveau (type=competence) ou None.

    Si `niveaux_idx` (dict {id: Niveau}, cf. `cv._build_niveau_index()`) est
    fourni, la résolution legacy se fait en mémoire plutôt que par requête —
    à utiliser quand la fonction est appelée en boucle sur plusieurs items.
    """
    if competence.niveau_id:
        return competence.niveau_id
    val = competence.valeurEtoiles or 0
    if val:
        if niveaux_idx is not None:
            for n in niveaux_idx.values():
                if n.type == Niveau.TYPE_COMPETENCE and n.nbEtoiles == val:
                    return n.id
            return None
        n = Niveau.objects.filter(type=Niveau.TYPE_COMPETENCE, nbEtoiles=val).first()
        if n:
            return n.id
    return None


def resolve_langue_niveau_id(langue, niveaux_idx=None):
    """`CandidatLangue` (modèle) → id Niveau (type=langue) ou None.

    Si `niveaux_idx` (dict {id: Niveau}, cf. `cv._build_niveau_index()`) est
    fourni, la résolution legacy se fait en mémoire plutôt que par requête —
    à utiliser quand la fonction est appelée en boucle sur plusieurs items.
    """
    if langue.niveau_id:
        return langue.niveau_id
    code = (langue.niveauCode or '').strip()
    if code:
        if niveaux_idx is not None:
            for n in niveaux_idx.values():
                if n.type == Niveau.TYPE_LANGUE and n.nomNiveau == code:
                    return n.id
            return None
        n = Niveau.objects.filter(type=Niveau.TYPE_LANGUE, nomNiveau=code).first()
        if n:
            return n.id
    return None


def niveaux_for_editor():
    """Liste sérialisée pour injection dans l'éditeur Alpine.js.
    Retourne `{langue: [...], competence: [...]}` chaque entrée étant un
    dict `{id, nomNiveau, libelle, nbEtoiles, ordre}`."""
    out = {Niveau.TYPE_LANGUE: [], Niveau.TYPE_COMPETENCE: []}
    for n in Niveau.objects.all().order_by('type', 'ordre'):
        out[n.type].append({
            'id'        : n.id,
            'nomNiveau' : n.nomNiveau,
            'libelle'   : n.libelle,
            'nbEtoiles' : n.nbEtoiles,
            'ordre'     : n.ordre,
        })
    return out
