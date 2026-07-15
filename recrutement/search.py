from django.db import connections
from django.db.models import Q
from django.db.models.expressions import RawSQL


def fts_filter(queryset, query, vector_fields, fallback_lookups, config='french'):
    """Recherche plein texte MySQL (FULLTEXT) avec fallback icontains.

    Args:
        queryset: QuerySet de base (déjà filtré par autres critères).
        query: Texte saisi par l'utilisateur.
        vector_fields: Liste de noms de champs pour la recherche plein texte.
            Cet ensemble exact de colonnes doit correspondre à un index
            FULLTEXT existant sur le modèle (voir migrations dédiées).
        fallback_lookups: Liste de lookups icontains (ex: ['titre__icontains']).
        config: non utilisé (conservé pour compatibilité des appels existants).

    Returns:
        QuerySet filtré et trié par pertinence.
    """
    if not query:
        return queryset

    vendor = connections[queryset.db].vendor
    qs_fts = _fts_mysql(queryset, query, vector_fields) if vendor == 'mysql' else queryset.none()

    if qs_fts.exists():
        return qs_fts

    q_filter = Q()
    for lookup in fallback_lookups:
        q_filter |= Q(**{lookup: query})
    return queryset.filter(q_filter)


def _fts_mysql(queryset, query, vector_fields):
    """Recherche via un index FULLTEXT MySQL (MATCH ... AGAINST).

    L'ensemble des colonnes doit correspondre exactement à un index FULLTEXT
    défini sur le modèle, sinon MySQL lève une erreur 1191 (« Can't find
    FULLTEXT index matching the column list »).
    """
    columns = [queryset.model._meta.get_field(name).column for name in vector_fields]
    table = queryset.model._meta.db_table
    columns_sql = ', '.join(f'{table}.{col}' for col in columns)
    match_sql = f"MATCH({columns_sql}) AGAINST (%s IN NATURAL LANGUAGE MODE)"

    return (
        queryset
        .annotate(rank=RawSQL(match_sql, (query,)))
        .filter(rank__gt=0)
        .order_by('-rank')
    )
