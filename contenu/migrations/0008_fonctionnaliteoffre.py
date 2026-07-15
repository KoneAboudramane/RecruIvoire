from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contenu', '0007_offretarif_chiffrecle'),
    ]

    operations = [

        migrations.AlterField(
            model_name='offretarif',
            name='fonctionnalites',
            field=models.TextField(blank=True, verbose_name='Fonctionnalités (legacy HTML)'),
        ),

        migrations.CreateModel(
            name='FonctionnaliteOffre',
            fields=[
                ('id',    models.BigAutoField(auto_created=True, primary_key=True,
                                             serialize=False, verbose_name='ID')),
                ('offre', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                            related_name='fonctionnalites_list',
                                            to='contenu.offretarif',
                                            verbose_name='Offre')),
                ('texte', models.CharField(max_length=200, verbose_name='Fonctionnalité')),
                ('ordre', models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')),
            ],
            options={
                'verbose_name': 'Fonctionnalité',
                'verbose_name_plural': 'Fonctionnalités',
                'ordering': ['ordre'],
            },
        ),
    ]
