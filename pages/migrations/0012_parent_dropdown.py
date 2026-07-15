from django.db import migrations, models, transaction
import django.db.models.deletion


def reorganise_vers_parent(apps, schema_editor):
    """
    Fusionne les 3 groupes navbar candidat (créés en 0011) en un seul.
    Crée un Element de type MENU pour le dropdown "Modèles",
    puis lie Modèles CV et Lettre de motivation comme sous-éléments via parent FK.
    """
    Groupe = apps.get_model('pages', 'Groupe')
    Element = apps.get_model('pages', 'Element')
    GroupeElement = apps.get_model('pages', 'GroupeElement')

    with transaction.atomic():
        try:
            g_debut = Groupe.objects.get(titre='Liens principaux', pour_candidat=True, en_navbar=True, ordre_candidat=1)
            g_modeles = Groupe.objects.get(titre='Modèles', pour_candidat=True, en_navbar=True)
            g_fin = Groupe.objects.get(titre='Liens', pour_candidat=True, en_navbar=True, ordre_candidat=3)
        except Groupe.DoesNotExist:
            return

        # Créer l'élément MENU "Modèles" (pas de lien, toggle dropdown)
        menu_el = Element.objects.create(
            type='MENU',
            label='Modèles',
            url='',
            visibilite='TOUJOURS',
            icone='',
            actif=True,
            nouvel_onglet=False,
            correspondance_exacte=False,
        )

        # Ajouter le MENU dans le groupe principal à l'ordre 3
        menu_ge = GroupeElement.objects.create(
            groupe=g_debut,
            element=menu_el,
            ordre=3,
            parent=None,
        )

        # Transférer Modèles CV et Lettre de motivation comme enfants du MENU
        for ge in GroupeElement.objects.filter(groupe=g_modeles).select_related('element').order_by('ordre'):
            GroupeElement.objects.create(
                groupe=g_debut,
                element=ge.element,
                ordre=ge.ordre,
                parent=menu_ge,
            )

        # Transférer les éléments de g_fin (Offres, Mes candidatures) à l'ordre 4+
        for ge in GroupeElement.objects.filter(groupe=g_fin).select_related('element').order_by('ordre'):
            GroupeElement.objects.create(
                groupe=g_debut,
                element=ge.element,
                ordre=ge.ordre + 3,
                parent=None,
            )

        # Supprimer les groupes devenus obsolètes (cascade supprime leurs GroupeElement)
        g_modeles.delete()
        g_fin.delete()


class Migration(migrations.Migration):
    # atomic=False car on ne peut pas ALTER TABLE pages_groupe (supprimer dropdown_label)
    # dans la même transaction PostgreSQL que les INSERT du RunPython (triggers différés).
    atomic = False

    dependencies = [
        ('pages', '0011_dropdown_icone'),
    ]

    operations = [
        # 1. Ajouter le type MENU à Element
        migrations.AlterField(
            model_name='element',
            name='type',
            field=models.CharField(
                choices=[('LIEN', 'Lien'), ('BOUTON', 'Bouton'), ('MENU', 'Menu déroulant')],
                default='LIEN',
                max_length=6,
                verbose_name='Type',
            ),
        ),
        # 2. Autoriser url vide (MENU n'a pas de lien)
        migrations.AlterField(
            model_name='element',
            name='url',
            field=models.CharField(
                blank=True,
                default='',
                max_length=255,
                verbose_name='URL',
            ),
        ),
        # 3. Ajouter le champ parent sur GroupeElement
        migrations.AddField(
            model_name='groupeelement',
            name='parent',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='enfants',
                to='pages.groupeelement',
                verbose_name='Élément parent',
            ),
        ),
        # 4. Réorganiser les données (fusionner les 3 groupes navbar candidat)
        migrations.RunPython(reorganise_vers_parent, migrations.RunPython.noop),
        # 5. Supprimer dropdown_label devenu inutile
        migrations.RemoveField(
            model_name='groupe',
            name='dropdown_label',
        ),
    ]
