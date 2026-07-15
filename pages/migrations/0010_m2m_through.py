from django.db import migrations, models
import django.db.models.deletion


def fk_vers_m2m(apps, schema_editor):
    Element = apps.get_model('pages', 'Element')
    GroupeElement = apps.get_model('pages', 'GroupeElement')
    for el in Element.objects.exclude(groupe__isnull=True):
        GroupeElement.objects.get_or_create(
            groupe_id=el.groupe_id,
            element=el,
            defaults={'ordre': el.ordre},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0009_booleans_proxies'),
    ]

    operations = [
        # 1. Créer le modèle intermédiaire
        migrations.CreateModel(
            name='GroupeElement',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('ordre', models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')),
                ('groupe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='pages.groupe')),
                ('element', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='pages.element')),
            ],
            options={
                'verbose_name': 'Élément du groupe',
                'verbose_name_plural': 'Éléments du groupe',
                'ordering': ['ordre'],
                'unique_together': {('groupe', 'element')},
            },
        ),
        # 2. Déclarer le champ M2M sur Groupe (pas de nouvelle table : utilise GroupeElement)
        migrations.AddField(
            model_name='groupe',
            name='elements',
            field=models.ManyToManyField(
                blank=True,
                through='pages.GroupeElement',
                to='pages.element',
                related_name='groupes',
                verbose_name='Éléments',
            ),
        ),
        # 3. Migrer les données : FK → M2M
        migrations.RunPython(fk_vers_m2m, migrations.RunPython.noop),
        # 4. Supprimer l'ancien FK groupe sur Element
        migrations.RemoveField(model_name='element', name='groupe'),
        # 5. Supprimer l'ancien champ ordre sur Element
        migrations.RemoveField(model_name='element', name='ordre'),
    ]
