from django.db import migrations, models


def reorganise_navbar_candidat(apps, schema_editor):
    Groupe = apps.get_model('pages', 'Groupe')
    Element = apps.get_model('pages', 'Element')
    GroupeElement = apps.get_model('pages', 'GroupeElement')

    try:
        liens = Groupe.objects.get(titre='Liens principaux', pour_candidat=True, en_navbar=True)
    except Groupe.DoesNotExist:
        return

    el_cv = Element.objects.filter(url='/candidat/modeles-cv/').first()
    el_lettre = Element.objects.filter(url='/candidat/modeles-lettre/').first()
    el_offres = Element.objects.filter(url='/candidat/offres/').first()
    el_cand = Element.objects.filter(url='/candidat/mes-candidatures/').first()

    # Groupe dropdown "Modèles" (ordre 2)
    modeles = Groupe.objects.create(
        titre='Modèles', pour_candidat=True, pour_entreprise=False,
        en_footer=False, en_navbar=True,
        ordre_candidat=2, actif=True,
        dropdown_label='Modèles',
    )
    for el, icone, ordre in [(el_cv, '📄', 1), (el_lettre, '✉️', 2)]:
        if el:
            if icone:
                el.icone = icone
                el.save(update_fields=['icone'])
            GroupeElement.objects.filter(groupe=liens, element=el).delete()
            GroupeElement.objects.create(groupe=modeles, element=el, ordre=ordre)

    # Groupe "Liens suite" (ordre 3)
    suite = Groupe.objects.create(
        titre='Liens', pour_candidat=True, pour_entreprise=False,
        en_footer=False, en_navbar=True,
        ordre_candidat=3, actif=True,
    )
    for el, ordre in [(el_offres, 1), (el_cand, 2)]:
        if el:
            GroupeElement.objects.filter(groupe=liens, element=el).delete()
            GroupeElement.objects.create(groupe=suite, element=el, ordre=ordre)

    # Réordonner Accueil et Tableau de bord dans le groupe initial
    el_acc = Element.objects.filter(url='/candidat/', correspondance_exacte=True).first()
    el_tdb = Element.objects.filter(url='/candidat/dashboard/').first()
    for el, ordre in [(el_acc, 1), (el_tdb, 2)]:
        if el:
            GroupeElement.objects.filter(groupe=liens, element=el).update(ordre=ordre)


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0010_m2m_through'),
    ]

    operations = [
        # Corriger le Meta.ordering de Element (ordre supprimé en 0010 mais ordering non mis à jour)
        migrations.AlterModelOptions(
            name='element',
            options={
                'ordering': ['label'],
                'verbose_name': 'Élément',
                'verbose_name_plural': 'Éléments',
            },
        ),
        migrations.AddField(
            model_name='groupe',
            name='dropdown_label',
            field=models.CharField(
                blank=True, default='', max_length=60, verbose_name='Label dropdown',
                help_text='Laisser vide → liens à plat. Remplir → menu déroulant avec ce texte comme bouton.',
            ),
        ),
        migrations.AddField(
            model_name='element',
            name='icone',
            field=models.CharField(
                blank=True, default='', max_length=10, verbose_name='Icône',
                help_text='Emoji optionnel affiché devant le label (ex: 📄 ✉️ 🏠).',
            ),
        ),
        migrations.RunPython(reorganise_navbar_candidat, migrations.RunPython.noop),
    ]
