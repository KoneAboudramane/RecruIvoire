"""Synchronisation JSON ⇄ tables relationnelles pour les rubriques candidat.

L'éditeur Alpine.js manipule les rubriques sous forme de JSON nested et envoie
le tout à `api_sauvegarder_rubriques`. Ce module se charge de projeter ce JSON
dans les tables relationnelles (Competence, Formation, ExperienceProfessionnelle,
PosteOccupe, MissionClient, Projet, Benevolat, CandidatLangue, CentreInteret).

Stratégie : delete + recreate par section. Plus simple et sans risque d'état
intermédiaire incohérent que de faire un diff. Le coût (perte des IDs internes)
est sans impact car le frontend utilise ses propres IDs locaux côté JSON.

Les valeurs textuelles libres saisies par le candidat (entreprise, diplôme,
poste, langue…) sont upsertées dans le référentiel via `get_or_create`, et le
texte original est aussi conservé dans le champ `*Libre` correspondant pour
préserver la casse / orthographe d'origine.
"""

from datetime import date

from django.db import transaction

from referentiel.models import (
    Diplome, Domaine, Institution, Langue, Niveau, NiveauEtude,
    Pays, Poste, RaisonSociale, TypeCentreInteret, TypeCompetence,
)

from .models import (
    Benevolat, CandidatLangue, CentreInteret, Competence,
    ExperienceProfessionnelle, Formation, MissionClient,
    PosteOccupe, Projet,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_date(value):
    """Parse une date depuis le JSON éditeur.

    Le frontend envoie soit '' (vide), soit 'YYYY-MM' (mois), soit 'YYYY-MM-DD'.
    On normalise vers un objet date (1er du mois si format mois) ou None.
    """
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    parts = value.split('-')
    try:
        if len(parts) == 2:
            return date(int(parts[0]), int(parts[1]), 1)
        if len(parts) == 3:
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, TypeError):
        return None
    return None


def _bool(value):
    return bool(value)


def _int_or_none(value):
    if value in (None, '', False):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _txt(value):
    if value is None:
        return ''
    return str(value).strip()


# ─── Upsert référentiel (saisie libre → FK) ───────────────────────────────────

def _upsert_ref(model, lookup_field, value):
    """Récupère ou crée une entrée de référentiel à partir d'un libellé libre.

    À utiliser pour les référentiels extensibles (postes, diplômes, langues,
    domaines, compétences, institutions, raisons sociales…) où l'on accepte
    que l'entrée du candidat enrichisse le référentiel.

    Recherche insensible à la casse. Retourne None si la valeur est vide
    ou si la création échoue (contrainte unique, etc.) — dans ce cas le
    champ FK reste NULL et seul le `*Libre` conserve la valeur saisie.
    """
    val = _txt(value)
    if not val:
        return None
    qs = model.objects.filter(**{f'{lookup_field}__iexact': val})
    obj = qs.first()
    if obj is not None:
        return obj
    # Savepoint nécessaire : sur SQLite/PostgreSQL, une IntegrityError dans
    # un bloc atomic invalide la transaction entière. Le savepoint isole
    # l'échec de création (contrainte unique inattendue, ex. Pays.codeISO).
    try:
        with transaction.atomic():
            return model.objects.create(**{lookup_field: val})
    except Exception:
        return None


def _lookup_ref(model, lookup_field, value):
    """Recherche stricte (sans création) dans un référentiel fermé.

    À utiliser pour Pays, Sexe, etc. — masters data figés où l'on ne veut
    pas autoriser le candidat à créer de nouvelles entrées.
    """
    val = _txt(value)
    if not val:
        return None
    return model.objects.filter(**{f'{lookup_field}__iexact': val}).first()


# ─── Sync principal ───────────────────────────────────────────────────────────

@transaction.atomic
def sync_rubriques_to_db(candidat, data):
    """Reconstruit toutes les rubriques relationnelles du candidat depuis le JSON.

    Atomique : si une étape échoue, rien n'est persisté.

    Retour : dict `{section: [item_or_None, ...]}` mappant chaque entrée du JSON
    à son objet DB créé (ou None si l'entrée a été ignorée — vide / invalide).
    Permet à l'appelant (CV editor) d'aligner par index une carte de visibilité
    avec les IDs DB fraîchement attribués.
    """
    if not isinstance(data, dict):
        return {}

    # Purge : on supprime tout puis on recrée. ExperienceProfessionnelle cascade
    # vers PosteOccupe + MissionClient. Competence est supprimée après Benevolat
    # (M2M : Django nettoie la table de jointure automatiquement).
    candidat.benevolats.all().delete()
    candidat.projets.all().delete()
    candidat.experiencesProfessionnelles.all().delete()
    candidat.formations.all().delete()
    candidat.competences.all().delete()
    candidat.languesParlees.all().delete()
    candidat.centresInteret.all().delete()

    return {
        'experiences': _sync_experiences(candidat, data.get('experiences') or []),
        'formations':  _sync_formations(candidat, data.get('formations')  or []),
        'competences': _sync_competences(candidat, data.get('competences') or []),
        'langues':     _sync_langues(candidat, data.get('langues')      or []),
        'interets':    _sync_centres_interet(candidat, data.get('interets') or []),
        # Projets dépendent éventuellement d'ExperienceProfessionnelle créée plus
        # haut, mais le JSON ne stocke pas le lien — on crée projets sans FK.
        'projets':     _sync_projets(candidat, data.get('projets') or []),
        'benevs':      _sync_benevolats(candidat, data.get('benevs') or []),
    }


# ─── Sections ─────────────────────────────────────────────────────────────────

def _sync_experiences(candidat, experiences):
    created = []
    for exp in experiences:
        if not isinstance(exp, dict):
            created.append(None)
            continue
        entreprise_lib = _txt(exp.get('entreprise'))
        # Compat ascendante : ancien format avec un seul champ `lieu` →
        # on le bascule en `ville` si pays/ville ne sont pas fournis séparément.
        pays_lib = _txt(exp.get('pays'))
        ville    = _txt(exp.get('ville')) or _txt(exp.get('lieu'))
        e = ExperienceProfessionnelle.objects.create(
            candidat            = candidat,
            entreprise          = _upsert_ref(RaisonSociale, 'nomEntreprise', entreprise_lib),
            pays                = _lookup_ref(Pays, 'nomPays', pays_lib),
            entrepriseLibre     = entreprise_lib,
            paysLibre           = pays_lib,
            ville               = ville,
            dateDebut           = _parse_date(exp.get('debut')),
            dateFin             = _parse_date(exp.get('fin')),
            enCours             = _bool(exp.get('enCours')),
            estVisiblePortfolio = exp.get('visiblePortfolio', True) is not False,
        )

        # Postes nested
        for ordre, p in enumerate(exp.get('postes') or []):
            if not isinstance(p, dict):
                continue
            titre = _txt(p.get('titre'))
            if not titre and not p.get('debut') and not p.get('fin'):
                continue
            PosteOccupe.objects.create(
                experience = e,
                poste      = _upsert_ref(Poste, 'nomPoste', titre),
                titreLibre = titre,
                dateDebut  = _parse_date(p.get('debut')),
                dateFin    = _parse_date(p.get('fin')),
                enCours    = _bool(p.get('enCours')),
                ordre      = ordre,
            )

        # Missions clients nested (si toggle activé)
        if exp.get('hasMissionsClient'):
            for mc in exp.get('missionsClient') or []:
                if not isinstance(mc, dict):
                    continue
                client_lib = _txt(mc.get('client'))
                if not client_lib:
                    continue
                MissionClient.objects.create(
                    experience  = e,
                    client      = _upsert_ref(RaisonSociale, 'nomEntreprise', client_lib),
                    pays        = _lookup_ref(Pays, 'nomPays', _txt(mc.get('pays'))),
                    clientLibre = client_lib,
                    paysLibre   = _txt(mc.get('pays')),
                    ville       = _txt(mc.get('ville')),
                    dateDebut   = _parse_date(mc.get('debut')),
                    dateFin     = _parse_date(mc.get('fin')),
                    enCours     = _bool(mc.get('enCours')),
                    description = _txt(mc.get('desc')),
                )
        created.append(e)
    return created


def _sync_formations(candidat, formations):
    created = []
    for f in formations:
        if not isinstance(f, dict):
            created.append(None)
            continue
        diplome_lib = _txt(f.get('diplome'))
        ecole_lib   = _txt(f.get('ecole'))
        # On ignore les lignes complètement vides
        if not (diplome_lib or ecole_lib or f.get('debut') or f.get('fin')):
            created.append(None)
            continue
        type_sortie = f.get('typeSortie') or Formation.TYPE_DIPLOME
        if type_sortie not in dict(Formation.TYPE_CHOICES):
            type_sortie = Formation.TYPE_DIPLOME

        obj = Formation.objects.create(
            candidat            = candidat,
            diplomeRef          = _upsert_ref(Diplome,     'nomDiplome',     diplome_lib),
            domaine             = _upsert_ref(Domaine,     'nomDomaine',     _txt(f.get('domaine'))),
            niveauEtude         = _upsert_ref(NiveauEtude, 'nomNiveau',      _txt(f.get('niveauEtude'))),
            institution         = _upsert_ref(Institution, 'nomInstitution', ecole_lib),
            pays                = _lookup_ref(Pays,        'nomPays',        _txt(f.get('pays'))),
            typeSortie          = type_sortie,
            diplomeLibre        = diplome_lib,
            domaineLibre        = _txt(f.get('domaine')),
            ecoleLibre          = ecole_lib,
            paysLibre           = _txt(f.get('pays')),
            ville               = _txt(f.get('lieu')),
            dateDebut           = _parse_date(f.get('debut')),
            dateFin             = _parse_date(f.get('fin')),
            enCours             = _bool(f.get('enCours')),
            description         = _txt(f.get('desc')),
            numero              = _txt(f.get('numero')),
            expiration          = _parse_date(f.get('expiration')),
            estVisiblePortfolio = f.get('visiblePortfolio', True) is not False,
        )
        created.append(obj)
    return created


def _resolve_niveau(val, type_):
    """Payload `niveau` → `Niveau` (FK) ou None.

    Format nouveau : `val` = id Niveau (int).
    Rétrocompat : int 1-5 (legacy compétence) ou code CEFR str (legacy langue).
    """
    if val in (None, ''):
        return None
    try:
        ival = int(val)
        n = Niveau.objects.filter(pk=ival).first()
        if n:
            return n
        # Legacy compétence : entier 1-5 = nbEtoiles
        if type_ == 'competence' and 1 <= ival <= 5:
            return Niveau.objects.filter(type='competence', nbEtoiles=ival).first()
    except (TypeError, ValueError):
        pass
    # Legacy langue : code CEFR
    if type_ == 'langue' and isinstance(val, str):
        return Niveau.objects.filter(type='langue', nomNiveau=val).first()
    return None


def _sync_competences(candidat, competences):
    created = []
    for c in competences:
        if not isinstance(c, dict):
            created.append(None)
            continue
        nom = _txt(c.get('nom'))
        if not nom:
            created.append(None)
            continue
        niveau = _resolve_niveau(c.get('niveau'), 'competence')
        obj = Competence.objects.create(
            candidat            = candidat,
            typeCompetence      = _upsert_ref(TypeCompetence, 'nomCompetence', nom),
            nomLibre            = nom,
            niveau              = niveau,
            valeurEtoiles       = niveau.nbEtoiles if niveau else 0,
            estVisiblePortfolio = c.get('visiblePortfolio', True) is not False,
        )
        created.append(obj)
    return created


def _sync_langues(candidat, langues):
    """Filet de sécurité serveur : dédoublonne sur le nom (case-insensitive)
    avant insertion. Le frontend dédoublonne déjà à la save, mais on ne peut
    pas s'y fier seul (un payload manuel ou un état déjà corrompu pourrait
    contenir des doublons). On garde la première occurrence et jette les
    suivantes — l'éditeur affichera 1 entrée au prochain chargement."""
    created = []
    seen = set()
    for l in langues:
        if not isinstance(l, dict):
            created.append(None)
            continue
        nom = _txt(l.get('nom'))
        if not nom:
            created.append(None)
            continue
        key = nom.strip().lower()
        if key in seen:
            created.append(None)
            continue
        seen.add(key)
        niveau = _resolve_niveau(l.get('niveau'), 'langue')
        obj = CandidatLangue.objects.create(
            candidat            = candidat,
            langue              = _upsert_ref(Langue, 'nomLangue', nom),
            nomLibre            = nom,
            niveau              = niveau,
            niveauCode          = niveau.nomNiveau if niveau else '',
            estVisiblePortfolio = l.get('visiblePortfolio', True) is not False,
        )
        created.append(obj)
    return created


def _sync_centres_interet(candidat, interets):
    created = []
    for ci in interets:
        # Format moderne : objet `{libelle, visiblePortfolio}` (rubrique Profil).
        # Format legacy : string brute (ancien snapshot ou éditeur CV).
        if isinstance(ci, dict):
            libelle  = _txt(ci.get('libelle') or ci.get('nom'))
            visible  = ci.get('visiblePortfolio', True) is not False
        else:
            libelle = _txt(ci)
            visible = True
        if not libelle:
            created.append(None)
            continue
        obj = CentreInteret.objects.create(
            candidat            = candidat,
            typeCentreInteret   = _upsert_ref(TypeCentreInteret, 'nomCentreInteret', libelle),
            libelleLibre        = libelle,
            estVisiblePortfolio = visible,
        )
        created.append(obj)
    return created


def _sync_projets(candidat, projets):
    created = []
    for p in projets:
        if not isinstance(p, dict):
            created.append(None)
            continue
        titre = _txt(p.get('nom'))
        if not titre:
            created.append(None)
            continue
        # Les fichiers ont été uploadés au préalable via api_upload_projet_media :
        # chaque item a la forme {id, url, name}. On filtre les items en cours
        # d'upload (sans url) et on ne garde que les clés persistables.
        def _clean_media(items):
            out = []
            for it in items or []:
                if isinstance(it, dict):
                    url = it.get('url')
                    if not url:
                        continue
                    out.append({
                        'id'  : it.get('id') or '',
                        'url' : url,
                        'name': it.get('name') or '',
                    })
            return out

        obj = Projet.objects.create(
            candidat            = candidat,
            titre               = titre,
            dateDebut           = _parse_date(p.get('dateDebut')),
            dateFin             = _parse_date(p.get('dateFin')),
            tailleEquipe        = _int_or_none(p.get('tailleEquipe')),
            contexte            = _txt(p.get('contexte')),
            realisation         = _txt(p.get('realisation')),
            urlDemo             = _txt(p.get('lien'))[:500],
            images              = _clean_media(p.get('images')),
            videos              = _clean_media(p.get('videos')),
            estVisiblePortfolio = p.get('visiblePortfolio', True) is not False,
        )
        created.append(obj)
    return created


def _sync_benevolats(candidat, benevs):
    created = []
    for b in benevs:
        if not isinstance(b, dict):
            created.append(None)
            continue
        titre = _txt(b.get('role'))
        orga  = _txt(b.get('orga'))
        if not (titre or orga):
            created.append(None)
            continue
        obj = Benevolat.objects.create(
            candidat            = candidat,
            titre               = titre,
            organisation        = orga,
            dateDebut           = _parse_date(b.get('debut')),
            dateFin             = _parse_date(b.get('fin')),
            enCours             = _bool(b.get('enCours')),
            estVisiblePortfolio = b.get('visiblePortfolio', True) is not False,
        )
        created.append(obj)
    return created
