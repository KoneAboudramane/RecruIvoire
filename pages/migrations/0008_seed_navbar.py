from django.db import migrations


def seed_navbar(apps, schema_editor):
    Groupe = apps.get_model('pages', 'Groupe')
    Element = apps.get_model('pages', 'Element')

    # Groupe navbar Candidat
    nav_cand = Groupe.objects.create(
        titre='Liens principaux', cible='CANDIDAT', placement='NAVBAR',
        ordre_candidat=1, actif=True,
    )
    Element.objects.bulk_create([
        Element(groupe=nav_cand, type='LIEN', label='Accueil',
                url='/candidat/', visibilite='TOUJOURS', correspondance_exacte=True, ordre=1, actif=True),
        Element(groupe=nav_cand, type='LIEN', label='Tableau de bord',
                url='/candidat/dashboard/', visibilite='CANDIDAT_CONNECTE', ordre=2, actif=True),
        Element(groupe=nav_cand, type='LIEN', label='Modèles CV',
                url='/candidat/modeles-cv/', visibilite='TOUJOURS', ordre=3, actif=True),
        Element(groupe=nav_cand, type='LIEN', label='Lettre de motivation',
                url='/candidat/modeles-lettre/', visibilite='TOUJOURS', ordre=4, actif=True),
        Element(groupe=nav_cand, type='LIEN', label="Offres d'emploi",
                url='/candidat/offres/', visibilite='TOUJOURS', ordre=5, actif=True),
        Element(groupe=nav_cand, type='LIEN', label='Mes candidatures',
                url='/candidat/mes-candidatures/', visibilite='CANDIDAT_CONNECTE', ordre=6, actif=True),
    ])

    # Groupe navbar Entreprise
    nav_ent = Groupe.objects.create(
        titre='Liens principaux', cible='ENTREPRISE', placement='NAVBAR',
        ordre_entreprise=1, actif=True,
    )
    Element.objects.bulk_create([
        Element(groupe=nav_ent, type='LIEN', label='Accueil',
                url='/entreprise/', visibilite='TOUJOURS', correspondance_exacte=True, ordre=1, actif=True),
        Element(groupe=nav_ent, type='LIEN', label='Tableau de bord',
                url='/entreprise/tableau-bord/', visibilite='ENTREPRISE', ordre=2, actif=True),
        Element(groupe=nav_ent, type='LIEN', label='Tableau de bord',
                url='/entreprise/recruteur/tableau-bord/', visibilite='RECRUTEUR', ordre=3, actif=True),
        Element(groupe=nav_ent, type='LIEN', label='Mes offres',
                url='/entreprise/offres/', visibilite='ENTREPRISE', ordre=4, actif=True),
        Element(groupe=nav_ent, type='LIEN', label='Offres',
                url='/entreprise/offres/', visibilite='RECRUTEUR', ordre=5, actif=True),
        Element(groupe=nav_ent, type='LIEN', label='Candidatures',
                url='/entreprise/candidatures/', visibilite='ENTREPRISE_OU_RECRUTEUR', ordre=6, actif=True),
        Element(groupe=nav_ent, type='LIEN', label='Profils candidats',
                url='/entreprise/candidats/', visibilite='ENTREPRISE_OU_RECRUTEUR', ordre=7, actif=True),
        Element(groupe=nav_ent, type='LIEN', label='Membres',
                url='/entreprise/membres/', visibilite='ENTREPRISE', ordre=8, actif=True),
        Element(groupe=nav_ent, type='LIEN', label='Membres',
                url='/entreprise/membres/', visibilite='RECRUTEUR_ADMIN', ordre=9, actif=True),
    ])


def unseed_navbar(apps, schema_editor):
    Groupe = apps.get_model('pages', 'Groupe')
    Groupe.objects.filter(titre='Liens principaux', placement='NAVBAR').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0007_rename_add_placement'),
    ]

    operations = [
        migrations.RunPython(seed_navbar, unseed_navbar),
    ]
