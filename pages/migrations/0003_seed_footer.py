from django.db import migrations


def seed_footer(apps, schema_editor):
    GroupeFooter = apps.get_model('pages', 'GroupeFooter')
    ElementFooter = apps.get_model('pages', 'ElementFooter')

    aide = GroupeFooter.objects.create(titre='Aide', cible='LES_DEUX', ordre=1, actif=True)
    ElementFooter.objects.bulk_create([
        ElementFooter(groupe=aide, type='LIEN', label='FAQ',               url='/faq/',               ordre=1, actif=True),
        ElementFooter(groupe=aide, type='LIEN', label='Contact',           url='/contact/',           ordre=2, actif=True),
        ElementFooter(groupe=aide, type='LIEN', label='Confidentialité',   url='/confidentialite/',   ordre=3, actif=True),
        ElementFooter(groupe=aide, type='LIEN', label='Mentions légales',  url='/mentions-legales/',  ordre=4, actif=True),
        ElementFooter(groupe=aide, type='LIEN', label='Tarifs',            url='/tarifs/',            ordre=5, actif=True),
        ElementFooter(groupe=aide, type='LIEN', label='CGU',               url='/cgu/',               ordre=6, actif=True),
        ElementFooter(groupe=aide, type='LIEN', label='À propos',          url='/a-propos/',          ordre=7, actif=True),
    ])

    recruteurs = GroupeFooter.objects.create(titre='Recruteurs', cible='CANDIDAT', ordre=2, actif=True)
    ElementFooter.objects.bulk_create([
        ElementFooter(groupe=recruteurs, type='LIEN',   label='Gérer ma newsletter',  url='/candidat/newsletter/gerer/', ordre=1, actif=True),
        ElementFooter(groupe=recruteurs, type='BOUTON', label='🏢 Espace Entreprise', url='/entreprise/',                ordre=2, actif=True),
    ])

    candidats = GroupeFooter.objects.create(titre='Candidats', cible='ENTREPRISE', ordre=2, actif=True)
    ElementFooter.objects.create(
        groupe=candidats, type='BOUTON', label='👤 Espace Candidat', url='/candidat/', ordre=1, actif=True
    )


def unseed_footer(apps, schema_editor):
    GroupeFooter = apps.get_model('pages', 'GroupeFooter')
    GroupeFooter.objects.filter(titre__in=['Aide', 'Recruteurs', 'Candidats']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0002_groupefooter_cible'),
    ]

    operations = [
        migrations.RunPython(seed_footer, unseed_footer),
    ]
