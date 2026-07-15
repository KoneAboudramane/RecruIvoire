from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contenu', '0004_categorie_multitable_faq'),
    ]

    operations = [

        migrations.CreateModel(
            name='PageStatique',
            fields=[
                ('id',          models.BigAutoField(auto_created=True, primary_key=True,
                                                    serialize=False, verbose_name='ID')),
                ('slug',        models.SlugField(max_length=50, unique=True, verbose_name='Slug')),
                ('titre',       models.CharField(max_length=200, verbose_name='Titre')),
                ('description', models.CharField(max_length=500, blank=True,
                                                 verbose_name='Description / chapeau')),
                ('mise_a_jour', models.DateField(null=True, blank=True,
                                                 verbose_name='Date de mise à jour')),
                ('actif',       models.BooleanField(default=True, verbose_name='Actif')),
            ],
            options={
                'verbose_name': 'Page statique',
                'verbose_name_plural': 'Pages statiques',
                'ordering': ['slug'],
            },
        ),

        migrations.CreateModel(
            name='SectionPage',
            fields=[
                ('id',      models.BigAutoField(auto_created=True, primary_key=True,
                                               serialize=False, verbose_name='ID')),
                ('page',    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name='sections',
                                              to='contenu.pagestatique',
                                              verbose_name='Page')),
                ('ancre',   models.SlugField(max_length=80, verbose_name='Ancre HTML')),
                ('icone',   models.CharField(max_length=10, default='📄',
                                             verbose_name='Icône (emoji)')),
                ('titre',   models.CharField(max_length=300, verbose_name='Titre')),
                ('contenu', models.TextField(verbose_name='Contenu (HTML)')),
                ('ordre',   models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')),
                ('actif',   models.BooleanField(default=True, verbose_name='Actif')),
            ],
            options={
                'verbose_name': 'Section',
                'verbose_name_plural': 'Sections',
                'ordering': ['ordre'],
            },
        ),
    ]
