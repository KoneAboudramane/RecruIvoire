from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('candidat', '0006_alerte_multi_select'),
    ]

    operations = [
        migrations.AddField(
            model_name='candidat',
            name='alertesActives',
            field=models.BooleanField(
                default=True,
                help_text="Si activé, vous êtes notifié dès qu'une offre correspond à vos alertes personnalisées.",
                verbose_name='Alertes emploi actives',
            ),
        ),
    ]
