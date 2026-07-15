from django.db import migrations, models
import django.db.models.deletion


def migrer_contact_vers_categorie(apps, schema_editor):
    """Copie les lignes ContactCategorie existantes dans la table Categorie parente."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO contenu_categorie (id, label, ordre, actif) "
            "SELECT id, label, ordre, actif FROM contenu_contactcategorie"
        )
        if schema_editor.connection.vendor == 'postgresql':
            # MySQL resynchronise seul son AUTO_INCREMENT sur MAX(id)+1 après
            # un insert explicite — cette étape est spécifique à PostgreSQL.
            cursor.execute(
                "SELECT setval(pg_get_serial_sequence('contenu_categorie', 'id'), "
                "COALESCE(MAX(id), 1)) FROM contenu_categorie"
            )
        cursor.execute(
            "UPDATE contenu_contactcategorie SET categorie_ptr_id = id"
        )


def reverse_categorie_vers_contact(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        if schema_editor.connection.vendor == 'postgresql':
            cursor.execute(
                "UPDATE contenu_contactcategorie cc "
                "SET label = c.label, ordre = c.ordre, actif = c.actif "
                "FROM contenu_categorie c WHERE c.id = cc.categorie_ptr_id"
            )
        else:
            cursor.execute(
                "UPDATE contenu_contactcategorie cc "
                "JOIN contenu_categorie c ON c.id = cc.categorie_ptr_id "
                "SET cc.label = c.label, cc.ordre = c.ordre, cc.actif = c.actif"
            )


def restructurer_contactcategorie(apps, schema_editor):
    """Supprime l'ancien PK (id), rend categorie_ptr PK, supprime les champs
    migrés vers Categorie. Syntaxe DDL spécifique par moteur."""
    vendor = schema_editor.connection.vendor
    if vendor == 'postgresql':
        schema_editor.execute(
            "ALTER TABLE contenu_contactcategorie "
            "ALTER COLUMN categorie_ptr_id SET NOT NULL"
        )
        schema_editor.execute(
            "ALTER TABLE contenu_contactcategorie "
            "DROP CONSTRAINT contenu_contactcategorie_pkey"
        )
        schema_editor.execute(
            "ALTER TABLE contenu_contactcategorie "
            "DROP COLUMN id, DROP COLUMN label, DROP COLUMN ordre, DROP COLUMN actif"
        )
        schema_editor.execute(
            "ALTER TABLE contenu_contactcategorie ADD PRIMARY KEY (categorie_ptr_id)"
        )
    elif vendor == 'mysql':
        schema_editor.execute(
            "ALTER TABLE contenu_contactcategorie "
            "MODIFY COLUMN categorie_ptr_id BIGINT NOT NULL, "
            "DROP PRIMARY KEY, "
            "DROP COLUMN id, DROP COLUMN label, DROP COLUMN ordre, DROP COLUMN actif, "
            "ADD PRIMARY KEY (categorie_ptr_id)"
        )
    else:
        raise NotImplementedError(f"Backend {vendor} non supporté par cette migration.")


def reverse_restructurer_contactcategorie(apps, schema_editor):
    """Reconstruit les colonnes id/label/ordre/actif sur ContactCategorie
    (chemin de rollback, peu emprunté — best-effort)."""
    vendor = schema_editor.connection.vendor
    if vendor == 'postgresql':
        schema_editor.execute(
            "ALTER TABLE contenu_contactcategorie DROP CONSTRAINT contenu_contactcategorie_pkey"
        )
        schema_editor.execute(
            "ALTER TABLE contenu_contactcategorie "
            "ADD COLUMN id BIGSERIAL, "
            "ADD COLUMN label VARCHAR(80) NOT NULL DEFAULT '', "
            "ADD COLUMN ordre SMALLINT NOT NULL DEFAULT 0, "
            "ADD COLUMN actif BOOLEAN NOT NULL DEFAULT TRUE"
        )
        schema_editor.execute(
            "UPDATE contenu_contactcategorie cc "
            "SET id = c.id, label = c.label, ordre = c.ordre, actif = c.actif "
            "FROM contenu_categorie c WHERE c.id = cc.categorie_ptr_id"
        )
        schema_editor.execute(
            "ALTER TABLE contenu_contactcategorie ADD PRIMARY KEY (id)"
        )
        schema_editor.execute(
            "ALTER TABLE contenu_contactcategorie ALTER COLUMN categorie_ptr_id DROP NOT NULL"
        )
    elif vendor == 'mysql':
        schema_editor.execute(
            "ALTER TABLE contenu_contactcategorie "
            "DROP PRIMARY KEY, "
            "ADD COLUMN id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY, "
            "ADD COLUMN label VARCHAR(80) NOT NULL DEFAULT '', "
            "ADD COLUMN ordre SMALLINT UNSIGNED NOT NULL DEFAULT 0, "
            "ADD COLUMN actif BOOLEAN NOT NULL DEFAULT TRUE"
        )
        schema_editor.execute(
            "UPDATE contenu_contactcategorie cc "
            "JOIN contenu_categorie c ON c.id = cc.categorie_ptr_id "
            "SET cc.id = c.id, cc.label = c.label, cc.ordre = c.ordre, cc.actif = c.actif"
        )
        schema_editor.execute(
            "ALTER TABLE contenu_contactcategorie MODIFY COLUMN categorie_ptr_id BIGINT NULL"
        )
    else:
        raise NotImplementedError(f"Backend {vendor} non supporté par cette migration.")


class Migration(migrations.Migration):

    # MySQL n'autorise pas de DDL brut (ALTER TABLE) dans une transaction.
    atomic = False

    dependencies = [
        ('contenu', '0003_add_faq_texte'),
    ]

    operations = [

        # ── 1. Créer la table Categorie parente ──────────────────────────────
        migrations.CreateModel(
            name='Categorie',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=80, verbose_name='Libellé')),
                ('ordre', models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
            ],
            options={
                'verbose_name': 'Catégorie',
                'verbose_name_plural': 'Catégories',
                'ordering': ['ordre', 'label'],
            },
        ),

        # ── 2. Ajouter categorie_ptr nullable sur ContactCategorie ────────────
        migrations.AddField(
            model_name='contactcategorie',
            name='categorie_ptr',
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                parent_link=True,
                to='contenu.categorie',
            ),
        ),

        # ── 3. Copier les données + lier les lignes existantes ───────────────
        migrations.RunPython(
            migrer_contact_vers_categorie,
            reverse_categorie_vers_contact,
        ),

        # ── 4. Travail structurel (DDL par moteur) ────────────────────────────
        #       Supprimer l'ancien PK (id), rendre categorie_ptr PK,
        #       supprimer les champs migrés vers Categorie.
        migrations.RunPython(
            restructurer_contactcategorie,
            reverse_restructurer_contactcategorie,
        ),

        # ── 5. Synchroniser l'état Django (sans ré-exécuter de SQL) ──────────
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name='contactcategorie',
                    name='categorie_ptr',
                    field=models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to='contenu.categorie',
                    ),
                ),
                migrations.RemoveField(model_name='contactcategorie', name='id'),
                migrations.RemoveField(model_name='contactcategorie', name='label'),
                migrations.RemoveField(model_name='contactcategorie', name='ordre'),
                migrations.RemoveField(model_name='contactcategorie', name='actif'),
            ],
        ),

        # ── 6. Mettre à jour les options Meta ────────────────────────────────
        migrations.AlterModelOptions(
            name='contactcategorie',
            options={
                'verbose_name': 'Contact catégorie',
                'verbose_name_plural': 'Contact catégories',
            },
        ),
        migrations.AlterModelOptions(
            name='contactconfig',
            options={
                'verbose_name': 'Contact configuration',
                'verbose_name_plural': 'Contact configuration',
            },
        ),
        migrations.AlterModelOptions(
            name='messagecontact',
            options={
                'ordering': ['-cree_le'],
                'verbose_name': 'Contact message',
                'verbose_name_plural': 'Contact messages',
            },
        ),

        # ── 7. Créer FaqCategorie (enfant de Categorie) ──────────────────────
        migrations.CreateModel(
            name='FaqCategorie',
            fields=[
                ('categorie_ptr', models.OneToOneField(
                    auto_created=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    parent_link=True,
                    primary_key=True,
                    serialize=False,
                    to='contenu.categorie',
                )),
                ('slug', models.SlugField(unique=True, verbose_name='Slug')),
                ('icone', models.CharField(default='❓', max_length=10,
                                           verbose_name='Icône (emoji)')),
            ],
            options={
                'verbose_name': 'FAQ catégorie',
                'verbose_name_plural': 'FAQ catégories',
            },
            bases=('contenu.categorie',),
        ),

        # ── 8. Créer FaqQuestion ─────────────────────────────────────────────
        migrations.CreateModel(
            name='FaqQuestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('question', models.CharField(max_length=300, verbose_name='Question')),
                ('reponse', models.TextField(verbose_name='Réponse (HTML autorisé)')),
                ('ordre', models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('categorie', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='questions',
                    to='contenu.faqcategorie',
                    verbose_name='Catégorie',
                )),
            ],
            options={
                'verbose_name': 'FAQ question',
                'verbose_name_plural': 'FAQ questions',
                'ordering': ['ordre'],
            },
        ),
    ]
