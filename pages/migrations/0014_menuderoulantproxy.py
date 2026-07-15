from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0013_cleanup_orphan_top_ges'),
    ]

    operations = [
        migrations.CreateModel(
            name='MenuDeroulantProxy',
            fields=[],
            options={
                'verbose_name': 'Menu déroulant',
                'verbose_name_plural': 'Menus déroulants',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('pages.groupeelement',),
        ),
    ]
