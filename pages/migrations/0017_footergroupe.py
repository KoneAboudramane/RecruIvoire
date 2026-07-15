from django.db import migrations, models, transaction
import django.db.models.deletion


def migrer_footer_existant(apps, schema_editor):
    Groupe = apps.get_model('pages', 'Groupe')
    FooterGroupe = apps.get_model('pages', 'FooterGroupe')
    with transaction.atomic():
        for g in Groupe.objects.filter(en_footer=True):
            FooterGroupe.objects.create(
                groupe=g,
                pour_candidat=g.pour_candidat,
                pour_entreprise=g.pour_entreprise,
                ordre_candidat=g.ordre_candidat,
                ordre_entreprise=g.ordre_entreprise,
                actif=g.actif,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0016_navbaritemproxy'),
    ]

    operations = [
        migrations.CreateModel(
            name='FooterGroupe',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pour_candidat', models.BooleanField(default=True, verbose_name='Candidat')),
                ('pour_entreprise', models.BooleanField(default=False, verbose_name='Entreprise')),
                ('ordre_candidat', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Ordre (Candidat)')),
                ('ordre_entreprise', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Ordre (Entreprise)')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('groupe', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='footer_configs',
                    to='pages.groupe',
                    verbose_name='Groupe',
                )),
            ],
            options={
                'verbose_name': 'Footer',
                'verbose_name_plural': 'Footer',
                'ordering': ['ordre_candidat', 'ordre_entreprise'],
            },
        ),
        migrations.RunPython(migrer_footer_existant, migrations.RunPython.noop),
    ]
