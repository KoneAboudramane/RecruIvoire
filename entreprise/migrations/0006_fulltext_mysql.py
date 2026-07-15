from django.db import migrations


def crea_fulltext_entreprise(apps, schema_editor):
    # Index FULLTEXT MySQL utilisé par recrutement.search.fts_filter — sans
    # équivalent Django ORM portable, purement additif, no-op sous PostgreSQL
    # (qui utilise déjà son propre GinIndex, voir migration 0003).
    if schema_editor.connection.vendor != 'mysql':
        return
    schema_editor.execute(
        "ALTER TABLE entreprise_entreprise "
        "ADD FULLTEXT INDEX ft_entreprise_recherche (raisonSocial, description)"
    )


def suppr_fulltext_entreprise(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return
    schema_editor.execute("ALTER TABLE entreprise_entreprise DROP INDEX ft_entreprise_recherche")


def crea_fulltext_offreemploi(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return
    # Deux jeux de colonnes distincts : entreprise/views/offres.py cherche sur
    # (titre, missions, profilRecherche), entreprise/views/candidatures.py sur
    # (titre, missions) seulement — MySQL exige un index FULLTEXT correspondant
    # exactement à l'ensemble de colonnes interrogé (erreur 1191 sinon).
    schema_editor.execute(
        "ALTER TABLE entreprise_offreemploi "
        "ADD FULLTEXT INDEX ft_offre_recherche (titre, missions, profilRecherche)"
    )
    schema_editor.execute(
        "ALTER TABLE entreprise_offreemploi "
        "ADD FULLTEXT INDEX ft_offre_recherche_courte (titre, missions)"
    )


def suppr_fulltext_offreemploi(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return
    schema_editor.execute("ALTER TABLE entreprise_offreemploi DROP INDEX ft_offre_recherche_courte")
    schema_editor.execute("ALTER TABLE entreprise_offreemploi DROP INDEX ft_offre_recherche")


def crea_fulltext_recruteur(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return
    schema_editor.execute(
        "ALTER TABLE entreprise_recruteur ADD FULLTEXT INDEX ft_recruteur_recherche (nom, prenom)"
    )


def suppr_fulltext_recruteur(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return
    schema_editor.execute("ALTER TABLE entreprise_recruteur DROP INDEX ft_recruteur_recherche")


class Migration(migrations.Migration):

    # MySQL n'autorise pas de DDL brut (ALTER TABLE) dans une transaction.
    atomic = False

    dependencies = [
        ('entreprise', '0005_remove_offreemploi_idx_offre_embedding_hnsw_and_more'),
    ]

    operations = [
        migrations.RunPython(crea_fulltext_entreprise, suppr_fulltext_entreprise),
        migrations.RunPython(crea_fulltext_offreemploi, suppr_fulltext_offreemploi),
        migrations.RunPython(crea_fulltext_recruteur, suppr_fulltext_recruteur),
    ]
