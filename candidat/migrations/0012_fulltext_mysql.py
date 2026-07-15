from django.db import migrations


def crea_fulltext_candidat(apps, schema_editor):
    # Index FULLTEXT MySQL utilisé par recrutement.search.fts_filter — sans
    # équivalent Django ORM portable, purement additif, no-op sous PostgreSQL
    # (qui utilise déjà son propre GinIndex, voir migration 0008).
    if schema_editor.connection.vendor != 'mysql':
        return
    schema_editor.execute(
        "ALTER TABLE candidat_candidat "
        "ADD FULLTEXT INDEX ft_candidat_recherche "
        "(prenom, nom, titreProfessionnel, biographie, secteurActivite)"
    )


def suppr_fulltext_candidat(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return
    schema_editor.execute(
        "ALTER TABLE candidat_candidat DROP INDEX ft_candidat_recherche"
    )


class Migration(migrations.Migration):

    # MySQL n'autorise pas de DDL brut (ALTER TABLE) dans une transaction.
    atomic = False

    dependencies = [
        ('candidat', '0011_remove_candidat_idx_candidat_embedding_hnsw_and_more'),
    ]

    operations = [
        migrations.RunPython(crea_fulltext_candidat, suppr_fulltext_candidat),
    ]
