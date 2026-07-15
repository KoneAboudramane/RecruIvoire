from django.db import migrations, models


def copier_ordre(apps, schema_editor):
    GroupeFooter = apps.get_model('pages', 'GroupeFooter')
    for g in GroupeFooter.objects.all():
        if g.cible in ('CANDIDAT', 'LES_DEUX'):
            g.ordre_candidat = g.ordre
        if g.cible in ('ENTREPRISE', 'LES_DEUX'):
            g.ordre_entreprise = g.ordre
        g.save()


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0003_seed_footer'),
    ]

    operations = [
        migrations.AddField(
            model_name='groupefooter',
            name='ordre_candidat',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Ordre (Candidat)'),
        ),
        migrations.AddField(
            model_name='groupefooter',
            name='ordre_entreprise',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Ordre (Entreprise)'),
        ),
        migrations.RunPython(copier_ordre, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='groupefooter',
            name='ordre',
        ),
        migrations.AlterModelOptions(
            name='groupefooter',
            options={'ordering': ['ordre_candidat', 'ordre_entreprise'], 'verbose_name': 'Groupe footer', 'verbose_name_plural': 'Groupes footer'},
        ),
    ]
