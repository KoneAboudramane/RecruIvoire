from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import Q


def fts_filter(queryset, query, vector_fields, fallback_lookups, config='french'):
    """Recherche plein texte PostgreSQL avec fallback icontains.

    Args:
        queryset: QuerySet de base (déjà filtré par autres critères).
        query: Texte saisi par l'utilisateur.
        vector_fields: Liste de noms de champs pour le SearchVector.
        fallback_lookups: Liste de lookups icontains (ex: ['titre__icontains']).
        config: Configuration linguistique PostgreSQL.

    Returns:
        QuerySet filtré et trié par pertinence.
    """
    if not query:
        return queryset

    vector = SearchVector(*vector_fields, config=config)
    search_query = SearchQuery(query, config=config)

    qs_fts = (
        queryset
        .annotate(search=vector, rank=SearchRank(vector, search_query))
        .filter(search=search_query)
        .order_by('-rank')
    )

    if qs_fts.exists():
        return qs_fts

    q_filter = Q()
    for lookup in fallback_lookups:
        q_filter |= Q(**{lookup: query})
    return queryset.filter(q_filter)
