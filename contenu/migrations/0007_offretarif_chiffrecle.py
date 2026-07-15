from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contenu', '0006_alter_contactcategorie_categorie_ptr'),
    ]

    operations = [

        migrations.CreateModel(
            name='OffreTarif',
            fields=[
                ('id',             models.BigAutoField(auto_created=True, primary_key=True,
                                                       serialize=False, verbose_name='ID')),
                ('page',           models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                     related_name='offres',
                                                     to='contenu.pagestatique',
                                                     verbose_name='Page')),
                ('groupe',         models.CharField(max_length=20,
                                                    choices=[('candidat', 'Espace Candidat'),
                                                             ('entreprise', 'Espace Entreprise')],
                                                    verbose_name='Groupe')),
                ('nom',            models.CharField(max_length=100, verbose_name="Nom de l'offre")),
                ('prix',           models.CharField(max_length=50, verbose_name='Prix affiché')),
                ('unite',          models.CharField(max_length=50, blank=True,
                                                    verbose_name='Unité (ex: FCFA / mois)')),
                ('fonctionnalites', models.TextField(verbose_name='Fonctionnalités (HTML <li>…</li>)')),
                ('badge',          models.CharField(max_length=50, blank=True,
                                                    verbose_name='Badge (ex: Bientôt, Populaire)')),
                ('cta_texte',      models.CharField(max_length=100, verbose_name='Texte du bouton')),
                ('cta_url',        models.CharField(max_length=200, blank=True,
                                                    verbose_name='URL du bouton (vide si désactivé)')),
                ('cta_desactive',  models.BooleanField(default=False, verbose_name='Bouton désactivé')),
                ('mise_en_avant',  models.BooleanField(default=False, verbose_name='Mise en avant')),
                ('ordre',          models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')),
                ('actif',          models.BooleanField(default=True, verbose_name='Actif')),
            ],
            options={
                'verbose_name': 'Offre tarifaire',
                'verbose_name_plural': 'Offres tarifaires',
                'ordering': ['groupe', 'ordre'],
            },
        ),

        migrations.CreateModel(
            name='ChiffreCle',
            fields=[
                ('id',      models.BigAutoField(auto_created=True, primary_key=True,
                                               serialize=False, verbose_name='ID')),
                ('page',    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name='chiffres',
                                              to='contenu.pagestatique',
                                              verbose_name='Page')),
                ('chiffre', models.CharField(max_length=20, verbose_name='Chiffre affiché')),
                ('label',   models.CharField(max_length=100, verbose_name='Label')),
                ('ordre',   models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')),
                ('actif',   models.BooleanField(default=True, verbose_name='Actif')),
            ],
            options={
                'verbose_name': 'Chiffre clé',
                'verbose_name_plural': 'Chiffres clés',
                'ordering': ['ordre'],
            },
        ),
    ]
