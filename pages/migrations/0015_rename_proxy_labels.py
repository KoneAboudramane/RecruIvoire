from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0014_menuderoulantproxy'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='groupefooterproxy',
            options={'verbose_name': 'Footer', 'verbose_name_plural': 'Footer', 'proxy': True},
        ),
        migrations.AlterModelOptions(
            name='groupenavbarproxy',
            options={'verbose_name': 'Navbar', 'verbose_name_plural': 'Navbar', 'proxy': True},
        ),
    ]
