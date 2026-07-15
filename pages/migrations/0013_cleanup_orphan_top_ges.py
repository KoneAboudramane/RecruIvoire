from django.db import migrations, transaction


def supprimer_orphelins_top(apps, schema_editor):
    """
    Supprime les GroupeElement top-level (parent=None) dont l'URL est déjà
    couverte par un GroupeElement enfant (parent!=None) dans le même groupe.
    Cas concret : Modèles CV et Lettre de motivation avaient deux objets Element
    en double en DB ; l'un est resté en top-level orphelin après la migration 0012.
    """
    GroupeElement = apps.get_model('pages', 'GroupeElement')

    with transaction.atomic():
        for ge_top in GroupeElement.objects.filter(parent__isnull=True).select_related('element'):
            url = ge_top.element.url
            if not url:
                continue
            # Y a-t-il un enfant dans le même groupe couvrant la même URL ?
            existe_enfant = GroupeElement.objects.filter(
                groupe=ge_top.groupe,
                parent__isnull=False,
                element__url=url,
            ).exclude(pk=ge_top.pk).exists()
            if existe_enfant:
                ge_top.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0012_parent_dropdown'),
    ]

    operations = [
        migrations.RunPython(supprimer_orphelins_top, migrations.RunPython.noop),
    ]
