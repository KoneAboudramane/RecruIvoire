from django.core.cache import cache
from django.db.models import Prefetch


def _serialize_element(el):
    return {
        'type': el.type,
        'label': el.label,
        'url': el.url,
        'visibilite': el.visibilite,
        'icone': el.icone,
        'nouvel_onglet': el.nouvel_onglet,
        'correspondance_exacte': el.correspondance_exacte,
    }


def _sous_liens_menu(ge):
    """Construit les sous-liens d'un menu déroulant depuis menu_deroulant.elements + groupes."""
    menu = ge.menu_deroulant
    if not menu:
        return []
    sous_liens = []
    # Éléments directs du menu
    for me in getattr(menu, 'prefetched_elements', []):
        sous_liens.append(_serialize_element(me.element))
    # Éléments de chaque groupe du menu
    for mg in getattr(menu, 'prefetched_groupes', []):
        for ge_item in getattr(mg.groupe, 'items', []):
            sous_liens.append(_serialize_element(ge_item.element))
    return sous_liens


def _serialize_ge(ge):
    data = _serialize_element(ge.element)
    if ge.menu_deroulant_id:
        # Nouveau système : MenuDeroulant dédié
        data['type'] = 'MENU'
        data['label'] = ge.menu_deroulant.titre
        data['icone'] = ge.menu_deroulant.icone
        data['visibilite'] = ge.menu_deroulant.visibilite
        data['url'] = ''
        data['enfants'] = _sous_liens_menu(ge)
    elif ge.element.type == 'MENU':
        # Fallback legacy : sous-liens via parent FK
        data['enfants'] = [_serialize_element(c.element) for c in getattr(ge, 'sous_items', [])]
    else:
        data['enfants'] = []
    return data


def _navbar_ge_queryset():
    from pages.models import GroupeElement, MenuDeroulantElement, MenuDeroulantGroupe
    return (
        GroupeElement.objects
        .filter(element__actif=True, parent__isnull=True)
        .select_related('element', 'menu_deroulant')
        .prefetch_related(
            # Fallback legacy : sous-liens via parent FK
            Prefetch(
                'enfants',
                queryset=GroupeElement.objects.filter(element__actif=True).select_related('element').order_by('ordre'),
                to_attr='sous_items',
            ),
            Prefetch(
                'menu_deroulant__menu_elements',
                queryset=MenuDeroulantElement.objects.select_related('element').order_by('ordre'),
                to_attr='prefetched_elements',
            ),
            Prefetch(
                'menu_deroulant__menu_groupes',
                queryset=(
                    MenuDeroulantGroupe.objects
                    .select_related('groupe')
                    .prefetch_related(
                        Prefetch(
                            'groupe__groupeelement_set',
                            queryset=(
                                GroupeElement.objects
                                .filter(element__actif=True, parent__isnull=True)
                                .select_related('element')
                                .order_by('ordre')
                            ),
                            to_attr='items',
                        )
                    )
                    .order_by('ordre')
                ),
                to_attr='prefetched_groupes',
            ),
        )
        .order_by('ordre')
    )


def _build_footer(cible_field, ordre_field):
    from pages.models import FooterGroupe, GroupeElement
    configs = (
        FooterGroupe.objects
        .filter(actif=True, **{cible_field: True})
        .order_by(ordre_field)
        .select_related('groupe')
        .prefetch_related(
            Prefetch(
                'groupe__groupeelement_set',
                queryset=(
                    GroupeElement.objects
                    .filter(element__actif=True, parent__isnull=True)
                    .select_related('element')
                    .order_by('ordre')
                ),
                to_attr='items',
            )
        )
    )
    return [
        {
            'titre': fg.groupe.titre,
            'elements': [_serialize_element(ge.element) for ge in fg.groupe.items],
        }
        for fg in configs
    ]


def _build_navbar(cible_field, ordre_field):
    from pages.models import Groupe
    groups = (
        Groupe.objects
        .filter(actif=True, en_navbar=True, **{cible_field: True})
        .order_by(ordre_field)
        .prefetch_related(
            Prefetch(
                'groupeelement_set',
                queryset=_navbar_ge_queryset(),
                to_attr='items',
            )
        )
    )
    return [
        {'titre': g.titre, 'elements': [_serialize_ge(ge) for ge in g.items]}
        for g in groups
    ]


def navigation_groupes(request):
    """Contexte global (candidat/base.html, entreprise/base.html,
    templates/base_public.html — ce dernier affiche les deux espaces).

    `candidat/base.html` n'utilise que `*_candidat`, `entreprise/base.html`
    que `*_entreprise` : sur ces gabarits, on ne construit que la paire
    utile plutôt que les 4 structures à chaque requête. `base_public.html`
    (pages contenu : FAQ, CGU, contact...) a besoin des deux — hors de ces
    deux namespaces, on construit tout par défaut (comportement inchangé).
    """
    app_name = getattr(getattr(request, 'resolver_match', None), 'app_name', None)
    besoin_candidat   = app_name != 'entreprise'
    besoin_entreprise = app_name != 'candidat'

    footer_cand = navbar_cand = footer_ent = navbar_ent = []

    if besoin_candidat:
        footer_cand = cache.get('footer_candidat')
        if footer_cand is None:
            footer_cand = _build_footer('pour_candidat', 'ordre_candidat')
            cache.set('footer_candidat', footer_cand, 1800)

        navbar_cand = cache.get('navbar_candidat')
        if navbar_cand is None:
            navbar_cand = _build_navbar('pour_candidat', 'ordre_candidat')
            cache.set('navbar_candidat', navbar_cand, 1800)

    if besoin_entreprise:
        footer_ent = cache.get('footer_entreprise')
        if footer_ent is None:
            footer_ent = _build_footer('pour_entreprise', 'ordre_entreprise')
            cache.set('footer_entreprise', footer_ent, 1800)

        navbar_ent = cache.get('navbar_entreprise')
        if navbar_ent is None:
            navbar_ent = _build_navbar('pour_entreprise', 'ordre_entreprise')
            cache.set('navbar_entreprise', navbar_ent, 1800)

    return {
        'footer_candidat': footer_cand,
        'footer_entreprise': footer_ent,
        'navbar_candidat': navbar_cand,
        'navbar_entreprise': navbar_ent,
    }
