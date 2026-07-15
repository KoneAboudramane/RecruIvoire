"""Construction du dict d'état initial pour l'éditeur CV (Alpine.js).

L'éditeur CV manipule un objet `cv` au format JSON. Plutôt que de partir de
valeurs hardcodées (cas démo), on pré-remplit cet objet à partir des données
en base du candidat connecté :

  - Identité / contact / liens : champs directs sur `Candidat`
    (héritage `referentiel.Utilisateur`).
  - Collections (expériences, formations, compétences, langues, centres
    d'intérêt, projets, bénévolats) : on privilégie le snapshot
    `Candidat.rubriques` (JSON déjà au format éditeur, dernier état sauvegardé
    via la page Profil) et, à défaut, on reconstruit depuis les tables
    relationnelles (Competence, Formation, ExperienceProfessionnelle, …).

Tout est tolérant aux valeurs nulles : le candidat peut très bien n'avoir
aucune expérience ou aucune formation enregistrée, l'éditeur affiche alors
des sections vides prêtes à recevoir des saisies.
"""

from datetime import date


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _ymd(d):
    """Date → 'YYYY-MM-DD' attendu par les <input type='month'> / formatPeriode().
    Le frontend tolère 'YYYY-MM' ou 'YYYY-MM-DD' indistinctement.
    """
    if not d:
        return ''
    if isinstance(d, str):
        return d
    try:
        return d.strftime('%Y-%m-%d')
    except Exception:
        return ''


def _ym(d):
    """Date → 'YYYY-MM' (les inputs de type 'month' attendent ce format)."""
    if not d:
        return ''
    if isinstance(d, str):
        # Si déjà 'YYYY-MM-DD', on tronque ; sinon on retourne tel quel.
        return d[:7] if len(d) >= 7 and d[4] == '-' else d
    try:
        return d.strftime('%Y-%m')
    except Exception:
        return ''


def _calculer_age(date_naissance):
    if not date_naissance:
        return ''
    try:
        today = date.today()
        years = today.year - date_naissance.year - (
            (today.month, today.day) < (date_naissance.month, date_naissance.day)
        )
        return str(years) if years > 0 else ''
    except Exception:
        return ''


def _photo_url(candidat):
    photo = getattr(candidat, 'photoProfil', None)
    if photo and getattr(photo, 'name', ''):
        try:
            return photo.url
        except Exception:
            return ''
    return ''


def _lien_par_slug(candidat, slug):
    """Renvoie l'URL du lien social du candidat correspondant au slug donné,
    ou '' si non renseigné. Source : table `LienCandidat` (référentiel
    `ReseauSocial`)."""
    lien = candidat.liensSociaux.filter(reseau__slug=slug).first()
    return lien.url if lien else ''


def _ville_pays(candidat):
    """Récupère ville / pays depuis l'InformationPersonnelle legacy si présente,
    puis tente une heuristique sur `adresse` (ex : 'Abidjan, Côte d'Ivoire').
    """
    info = getattr(candidat, 'informationPersonnelle', None)
    ville = (getattr(info, 'ville', '') or '').strip() if info else ''
    pays  = (getattr(info, 'pays',  '') or '').strip() if info else ''
    if not (ville or pays) and getattr(candidat, 'adresse', ''):
        parts = [p.strip() for p in candidat.adresse.split(',') if p.strip()]
        if len(parts) >= 2:
            ville, pays = parts[0], parts[-1]
        elif len(parts) == 1:
            ville = parts[0]
    return ville, pays


def _permis(candidat):
    """Concatène les permis (M2M `typePermis`) ou retombe sur le legacy."""
    try:
        permis = list(candidat.typePermis.values_list('nomPermis', flat=True))
        if permis:
            return ', '.join(permis)
    except Exception:
        pass
    info = getattr(candidat, 'informationPersonnelle', None)
    return (getattr(info, 'permis', '') or '') if info else ''


# ─── Reconstruction des collections depuis les tables relationnelles ──────────

def _experiences_from_db(candidat):
    out = []
    qs = (
        candidat.experiencesProfessionnelles
        .all()
        .prefetch_related('postes', 'missionsClient')
    )
    for e in qs:
        ville = e.ville or ''
        pays  = e.paysLibre or (e.pays.nomPays if e.pays_id else '')
        out.append({
            'id'         : e.id,
            'entreprise' : e.entrepriseLibre or (e.entreprise.nomEntreprise if e.entreprise_id else ''),
            'ville'      : ville,
            'pays'       : pays,
            'lieu'       : ', '.join(p for p in (ville, pays) if p),
            'debut'      : _ym(e.dateDebut),
            'fin'        : _ym(e.dateFin),
            'enCours'    : bool(e.enCours),
            'visiblePortfolio': bool(e.estVisiblePortfolio),
            'postes'     : [{
                'id'     : p.id,
                'titre'  : p.titreLibre or (p.poste.nomPoste if p.poste_id else ''),
                'debut'  : _ym(p.dateDebut),
                'fin'    : _ym(p.dateFin),
                'enCours': bool(p.enCours),
            } for p in e.postes.all()],
            'hasMissionsClient': e.missionsClient.exists(),
            'missionsClient'   : [{
                'id'     : mc.id,
                'client' : mc.clientLibre or (mc.client.nomEntreprise if mc.client_id else ''),
                'pays'   : mc.paysLibre or (mc.pays.nomPays if mc.pays_id else ''),
                'ville'  : mc.ville or '',
                'debut'  : _ym(mc.dateDebut),
                'fin'    : _ym(mc.dateFin),
                'enCours': bool(mc.enCours),
                'desc'   : mc.description or '',
            } for mc in e.missionsClient.all()],
        })
    return out


def _formations_from_db(candidat):
    out = []
    for f in candidat.formations.all():
        out.append({
            'id'         : f.id,
            'typeSortie' : f.typeSortie or 'diplome',
            'diplome'    : f.diplomeLibre or (f.diplomeRef.nomDiplome if f.diplomeRef_id else ''),
            'domaine'    : f.domaineLibre or (f.domaine.nomDomaine if f.domaine_id else ''),
            'niveauEtude': f.niveauEtude.nomNiveau if f.niveauEtude_id else '',
            'ecole'      : f.ecoleLibre or (f.institution.nomInstitution if f.institution_id else ''),
            'lieu'       : f.ville or '',
            'debut'      : _ym(f.dateDebut),
            'fin'        : _ym(f.dateFin),
            'enCours'    : bool(f.enCours),
            'desc'       : f.description or '',
            'numero'     : f.numero or '',
            'expiration' : _ym(f.expiration),
            'visiblePortfolio': bool(f.estVisiblePortfolio),
        })
    return out


def _competences_from_db(candidat):
    from .cv import _build_niveau_index
    from .niveau_resolver import resolve_competence_niveau_id
    niveaux_idx = _build_niveau_index()
    return [{
        'id'    : c.id,
        'nom'   : c.nomLibre or (c.typeCompetence.nomCompetence if c.typeCompetence_id else ''),
        'niveau': resolve_competence_niveau_id(c, niveaux_idx),
        'visiblePortfolio': bool(c.estVisiblePortfolio),
    } for c in candidat.competences.all()]


def _langues_from_db(candidat):
    from .cv import _build_niveau_index
    from .niveau_resolver import resolve_langue_niveau_id
    niveaux_idx = _build_niveau_index()
    return [{
        'id'    : l.id,
        'nom'   : l.nomLibre or (l.langue.nomLangue if l.langue_id else ''),
        'niveau': resolve_langue_niveau_id(l, niveaux_idx),
        'visiblePortfolio': bool(l.estVisiblePortfolio),
    } for l in candidat.languesParlees.all()]


def _interets_from_db(candidat):
    """Centres d'intérêt comme tableau d'objets `{id, libelle, visiblePortfolio}`.

    Format objet (vs. ancien array de strings) pour aligner sur les autres
    rubriques et permettre un toggle de visibilité portfolio par item.
    `build_cv_initial` aplatit ce tableau pour le CV (qui reste sur des strings).
    """
    out = []
    for ci in candidat.centresInteret.all():
        libelle = ci.libelleLibre or (ci.typeCentreInteret.nomCentreInteret if ci.typeCentreInteret_id else '')
        if not libelle:
            continue
        out.append({
            'id': ci.id,
            'libelle': libelle,
            'visiblePortfolio': bool(ci.estVisiblePortfolio),
        })
    return out


def _projets_from_db(candidat):
    # `desc` (format CV simplifié) ← `realisation` (= « Vos contributions »).
    # Le modèle `Projet` n'a plus de champ `description` (orphelin supprimé).
    return [{
        'id'   : p.id,
        'nom'  : p.titre or '',
        'desc' : p.realisation or '',
        'lien' : p.urlDemo or '',
        'annee': p.dateDebut.year if p.dateDebut else '',
        'visiblePortfolio': bool(p.estVisiblePortfolio),
    } for p in candidat.projets.all()]


def _benevs_from_db(candidat):
    return [{
        'id'     : b.id,
        'role'   : b.titre or '',
        'orga'   : b.organisation or '',
        'debut'  : _ym(b.dateDebut),
        'fin'    : _ym(b.dateFin),
        'enCours': bool(b.enCours),
        'visiblePortfolio': bool(b.estVisiblePortfolio),
    } for b in candidat.benevolats.all()]


# ─── API publique ─────────────────────────────────────────────────────────────

# Clés du snapshot `Candidat.rubriques`. Source unique pour :
#  - l'éditeur CV (lecture initiale + sauvegarde du snapshot)
#  - la page Profil → onglet Rubriques (lecture + sauvegarde du snapshot)
RUBRIQUES_KEYS = (
    'experiences', 'formations', 'competences', 'langues',
    'interets', 'projets', 'benevs',
    'showProjets', 'showBenev', 'showRef',
)


def extract_rubriques_snapshot(data):
    """Extrait les clés rubriques d'un dict (cv_data ou payload Profil).

    Retourne un dict ne contenant que les clés présentes dans `data`.
    Utilisé pour persister `Candidat.rubriques` à partir de payloads
    qui peuvent contenir des champs supplémentaires (identité, etc.).
    """
    return {k: data[k] for k in RUBRIQUES_KEYS if k in data}


def build_rubriques_initial(candidat):
    """Construit le dict des rubriques (collections + toggles d'affichage).

    Source : `candidat.rubriques` (snapshot JSON éditeur) en priorité ;
    fallback sur les tables relationnelles si le snapshot est vide pour
    une rubrique donnée.

    Utilisé par :
      - l'éditeur CV (via `build_cv_initial`),
      - la page Profil → onglet Rubriques.
    Garantit que les deux affichent exactement les mêmes données.
    """
    rub = candidat.rubriques if isinstance(candidat.rubriques, dict) else {}

    experiences = rub.get('experiences') or _experiences_from_db(candidat)
    formations  = rub.get('formations')  or _formations_from_db(candidat)
    competences = rub.get('competences') or _competences_from_db(candidat)
    langues     = rub.get('langues')     or _langues_from_db(candidat)
    interets    = rub.get('interets')    or _interets_from_db(candidat)
    projets     = rub.get('projets')     or _projets_from_db(candidat)
    benevs      = rub.get('benevs')      or _benevs_from_db(candidat)

    # Toggles d'affichage : on respecte le dernier choix de l'éditeur ;
    # à défaut, on active une rubrique uniquement si elle a du contenu.
    return {
        'experiences': experiences,
        'formations' : formations,
        'competences': competences,
        'langues'    : langues,
        'interets'   : interets,
        'projets'    : projets,
        'benevs'     : benevs,
        'showProjets': rub.get('showProjets', bool(projets)),
        'showBenev'  : rub.get('showBenev',   bool(benevs)),
        'showRef'    : rub.get('showRef',     True),
    }


def build_cv_initial(candidat):
    """Construit le dict d'état initial à injecter dans l'éditeur Alpine.

    Sémantique **création de CV** : on charge l'intégralité du profil candidat
    (identité + toutes les rubriques) avec **tous les items visibles**. Le
    candidat décidera ensuite ce qu'il fait figurer ou non sur ce CV-ci en
    masquant manuellement (les masquages sont propres au CV, pas au profil).

    Identité : toujours depuis `Candidat` (source de vérité, mise à jour
    via l'onglet Profil).

    Collections / toggles : délégué à `build_rubriques_initial` pour
    garantir une logique unique partagée avec la page Profil. Les flags
    `visible:false` qui auraient pu transiter via `candidat.rubriques`
    (après un masquage dans un précédent CV) sont neutralisés ici — la
    visibilité par CV est portée par le snapshot, pas par le profil.
    """
    ville, pays = _ville_pays(candidat)
    # Adresse, ville, pays sont trois champs indépendants côté éditeur :
    # adresse = saisie libre (ex: « Cocody Riviera 3 »), distincte de ville/pays.
    adresse = candidat.adresse or ''

    rubriques = build_rubriques_initial(candidat)
    # Normalisation : tout est visible à la création. Centres d'intérêt :
    # on repart sans masques (les masques étaient propres à un autre CV).
    for section in ('experiences', 'formations', 'competences', 'langues', 'projets', 'benevs'):
        for item in rubriques.get(section) or []:
            if isinstance(item, dict):
                item['visible'] = True

    # Centres d'intérêt : l'éditeur CV consomme un tableau plat de strings.
    # Côté Profil rubriques on stocke des objets `{id, libelle, visiblePortfolio}` ;
    # on aplatit en `libelle` ici pour préserver l'API du CV.
    interets_raw = rubriques.get('interets') or []
    rubriques['interets'] = [
        (i.get('libelle') if isinstance(i, dict) else i) or ''
        for i in interets_raw
    ]
    rubriques['interets'] = [s for s in rubriques['interets'] if s]

    return {
        # ── Identité / contact ──
        'photo'    : _photo_url(candidat),
        'prenom'   : candidat.prenom or '',
        'nom'      : candidat.nom or '',
        'titre'    : candidat.titreProfessionnel or '',
        'email'    : candidat.email or '',
        'telephone': candidat.telephone or '',
        'ville'    : ville,
        'pays'     : pays,
        'adresse'  : adresse,
        'age'      : _calculer_age(candidat.dateNaissance),
        'linkedin' : _lien_par_slug(candidat, 'linkedin'),
        'portfolio': _lien_par_slug(candidat, 'googlechrome'),
        'permis'   : _permis(candidat),
        'profil'   : candidat.profilCV or '',

        # ── Collections + toggles ──
        **rubriques,

        # ── Centres d'intérêt : pas de masques en création. ──
        'interetsMasques': [],

        # ── Suggestions : vide en création (le CV neuf part de toutes les
        # rubriques candidat → rien à suggérer). Renseigné en modification
        # via `_compute_suggestions` côté `cv.py::_from_snapshot`.
        'suggestions': {
            'experiences': [], 'formations': [], 'competences': [],
            'langues':     [], 'interets':   [], 'projets':     [], 'benevs': [],
        },
    }
