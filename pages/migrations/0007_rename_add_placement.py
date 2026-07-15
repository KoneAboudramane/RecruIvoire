from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0006_seed_navigation'),
    ]

    operations = [
        migrations.RenameModel('GroupeFooter', 'Groupe'),
        migrations.RenameModel('ElementFooter', 'Element'),
        migrations.AlterModelOptions(
            name='groupe',
            options={
                'ordering': ['ordre_candidat', 'ordre_entreprise'],
                'verbose_name': 'Groupe',
                'verbose_name_plural': 'Groupes',
            },
        ),
        migrations.AlterModelOptions(
            name='element',
            options={
                'ordering': ['ordre'],
                'verbose_name': 'Élément',
                'verbose_name_plural': 'Éléments',
            },
        ),
        migrations.AddField(
            model_name='groupe',
            name='placement',
            field=models.CharField(
                choices=[('FOOTER', 'Footer seulement'), ('NAVBAR', 'Navbar seulement'), ('PARTOUT', 'Footer + Navbar')],
                default='FOOTER',
                max_length=7,
                verbose_name='Placement',
            ),
        ),
        migrations.AddField(
            model_name='element',
            name='correspondance_exacte',
            field=models.BooleanField(
                default=False,
                verbose_name='URL exacte',
                help_text="Cocher pour les URLs racines (ex: /candidat/) afin d'éviter qu'elles soient toujours actives.",
            ),
        ),
    ]
