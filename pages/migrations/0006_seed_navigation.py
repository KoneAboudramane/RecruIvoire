from django.db import migrations


def seed_navigation(apps, schema_editor):
    GroupeFooter = apps.get_model('pages', 'GroupeFooter')
    ElementFooter = apps.get_model('pages', 'ElementFooter')

    # Décaler les ordres existants pour laisser la place à Navigation en position 1
    for g in GroupeFooter.objects.filter(cible__in=['CANDIDAT', 'LES_DEUX']):
        if g.ordre_candidat is not None:
            g.ordre_candidat += 1
            g.save(update_fields=['ordre_candidat'])

    for g in GroupeFooter.objects.filter(cible__in=['ENTREPRISE', 'LES_DEUX']):
        if g.ordre_entreprise is not None:
            g.ordre_entreprise += 1
            g.save(update_fields=['ordre_entreprise'])

    # Groupe Navigation Candidat
    nav_cand = GroupeFooter.objects.create(
        titre='Navigation', cible='CANDIDAT', ordre_candidat=1, actif=True
    )
    ElementFooter.objects.bulk_create([
        ElementFooter(groupe=nav_cand, type='LIEN', label='Accueil',              url='/candidat/',                visibilite='TOUJOURS',          ordre=1, actif=True),
        ElementFooter(groupe=nav_cand, type='LIEN', label='Modèles CV',           url='/candidat/modeles-cv/',     visibilite='TOUJOURS',          ordre=2, actif=True),
        ElementFooter(groupe=nav_cand, type='LIEN', label='Lettre de motivation', url='/candidat/modeles-lettre/', visibilite='TOUJOURS',          ordre=3, actif=True),
        ElementFooter(groupe=nav_cand, type='LIEN', label='Mon portfolio',        url='/candidat/mon-portfolio/',  visibilite='CANDIDAT_CONNECTE', ordre=4, actif=True),
    ])

    # Groupe Navigation Entreprise
    nav_ent = GroupeFooter.objects.create(
        titre='Navigation', cible='ENTREPRISE', ordre_entreprise=1, actif=True
    )
    ElementFooter.objects.bulk_create([
        ElementFooter(groupe=nav_ent, type='LIEN', label='Accueil',         url='/entreprise/',                        visibilite='TOUJOURS',              ordre=1, actif=True),
        ElementFooter(groupe=nav_ent, type='LIEN', label='Tableau de bord', url='/entreprise/tableau-bord/',           visibilite='ENTREPRISE',            ordre=2, actif=True),
        ElementFooter(groupe=nav_ent, type='LIEN', label='Tableau de bord', url='/entreprise/recruteur/tableau-bord/', visibilite='RECRUTEUR',             ordre=3, actif=True),
        ElementFooter(groupe=nav_ent, type='LIEN', label='Mes offres',      url='/entreprise/offres/',                 visibilite='ENTREPRISE',            ordre=4, actif=True),
        ElementFooter(groupe=nav_ent, type='LIEN', label='Offres',          url='/entreprise/offres/',                 visibilite='RECRUTEUR',             ordre=5, actif=True),
        ElementFooter(groupe=nav_ent, type='LIEN', label='Membres',         url='/entreprise/membres/',                visibilite='ENTREPRISE',            ordre=6, actif=True),
    ])


def unseed_navigation(apps, schema_editor):
    GroupeFooter = apps.get_model('pages', 'GroupeFooter')
    GroupeFooter.objects.filter(titre='Navigation').delete()

    for g in GroupeFooter.objects.filter(cible__in=['CANDIDAT', 'LES_DEUX']):
        if g.ordre_candidat is not None:
            g.ordre_candidat = max(1, g.ordre_candidat - 1)
            g.save(update_fields=['ordre_candidat'])

    for g in GroupeFooter.objects.filter(cible__in=['ENTREPRISE', 'LES_DEUX']):
        if g.ordre_entreprise is not None:
            g.ordre_entreprise = max(1, g.ordre_entreprise - 1)
            g.save(update_fields=['ordre_entreprise'])


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0005_add_visibilite'),
    ]

    operations = [
        migrations.RunPython(seed_navigation, unseed_navigation),
    ]
