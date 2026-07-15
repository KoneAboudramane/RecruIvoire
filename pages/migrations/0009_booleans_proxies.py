from django.db import migrations, models


def cible_placement_vers_booleans(apps, schema_editor):
    Groupe = apps.get_model('pages', 'Groupe')
    for g in Groupe.objects.all():
        cible = g.cible or 'LES_DEUX'
        placement = g.placement or 'FOOTER'
        g.pour_candidat = cible in ('CANDIDAT', 'LES_DEUX')
        g.pour_entreprise = cible in ('ENTREPRISE', 'LES_DEUX')
        g.en_footer = placement in ('FOOTER', 'PARTOUT')
        g.en_navbar = placement in ('NAVBAR', 'PARTOUT')
        g.save(update_fields=['pour_candidat', 'pour_entreprise', 'en_footer', 'en_navbar'])


def booleans_vers_cible_placement(apps, schema_editor):
    Groupe = apps.get_model('pages', 'Groupe')
    for g in Groupe.objects.all():
        if g.pour_candidat and g.pour_entreprise:
            g.cible = 'LES_DEUX'
        elif g.pour_candidat:
            g.cible = 'CANDIDAT'
        else:
            g.cible = 'ENTREPRISE'
        if g.en_footer and g.en_navbar:
            g.placement = 'PARTOUT'
        elif g.en_navbar:
            g.placement = 'NAVBAR'
        else:
            g.placement = 'FOOTER'
        g.save(update_fields=['cible', 'placement'])


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0008_seed_navbar'),
    ]

    operations = [
        # 1. Ajouter les 4 booléens avec des valeurs temporaires
        migrations.AddField(
            model_name='groupe',
            name='pour_candidat',
            field=models.BooleanField(default=True, verbose_name='Candidat'),
        ),
        migrations.AddField(
            model_name='groupe',
            name='pour_entreprise',
            field=models.BooleanField(default=False, verbose_name='Entreprise'),
        ),
        migrations.AddField(
            model_name='groupe',
            name='en_footer',
            field=models.BooleanField(default=True, verbose_name='Footer'),
        ),
        migrations.AddField(
            model_name='groupe',
            name='en_navbar',
            field=models.BooleanField(default=False, verbose_name='Navbar'),
        ),
        # 2. Convertir les données existantes
        migrations.RunPython(cible_placement_vers_booleans, booleans_vers_cible_placement),
        # 3. Supprimer les anciens champs
        migrations.RemoveField(model_name='groupe', name='cible'),
        migrations.RemoveField(model_name='groupe', name='placement'),
        # 4. Créer les proxy models pour l'admin
        migrations.CreateModel(
            name='GroupeFooterProxy',
            fields=[],
            options={
                'proxy': True,
                'verbose_name': 'Groupe footer',
                'verbose_name_plural': 'Groupes footer',
                'indexes': [],
                'constraints': [],
            },
            bases=('pages.groupe',),
        ),
        migrations.CreateModel(
            name='GroupeNavbarProxy',
            fields=[],
            options={
                'proxy': True,
                'verbose_name': 'Groupe navbar',
                'verbose_name_plural': 'Groupes navbar',
                'indexes': [],
                'constraints': [],
            },
            bases=('pages.groupe',),
        ),
    ]
