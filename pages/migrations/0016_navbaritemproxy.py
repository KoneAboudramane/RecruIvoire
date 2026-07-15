from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0015_rename_proxy_labels'),
    ]

    operations = [
        migrations.CreateModel(
            name='NavbarItemProxy',
            fields=[],
            options={
                'verbose_name': 'Navbar',
                'verbose_name_plural': 'Navbar',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('pages.groupeelement',),
        ),
    ]
