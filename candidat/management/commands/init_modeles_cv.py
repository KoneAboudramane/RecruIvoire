"""
Commande de gestion : python manage.py init_modeles_cv

Peuple la table ModeleCV avec les 16 modèles livrés avec l'application.
Options :
  --force   Supprime les modèles existants avant de réinsérer.
"""

from django.core.management.base import BaseCommand
from candidat.models import ModeleCV


MODELES_INITIAUX = [
    # ── Gratuits ──────────────────────────────────────────────────────────────
    {
        'nom': 'Classique Orange', 'fichier': 'orange-plain',
        'categorie': 'Classique', 'secteur': 'Tous secteurs',
        'couleur': '#F77F00', 'premium': False, 'ordre': 1,
    },
    {
        'nom': 'Minimaliste Blanc', 'fichier': 'white-minimal',
        'categorie': 'Minimaliste', 'secteur': 'Tous secteurs',
        'couleur': '#2563EB', 'premium': False, 'ordre': 2,
    },
    {
        'nom': 'Moderne Dark', 'fichier': 'dark-side',
        'categorie': 'Moderne', 'secteur': 'Tech & IT',
        'couleur': '#1a1a2e', 'premium': False, 'ordre': 3,
    },
    {
        'nom': 'Élégant Vert', 'fichier': 'green-top',
        'categorie': 'Élégant', 'secteur': 'Cadres & Managers',
        'couleur': '#009A44', 'premium': False, 'ordre': 4,
    },
    {
        'nom': 'Bande Orange', 'fichier': 'orange-band',
        'categorie': 'Classique', 'secteur': 'Commerce',
        'couleur': '#F77F00', 'premium': False, 'ordre': 5,
    },
    {
        'nom': 'Académique', 'fichier': 'academic',
        'categorie': 'Classique', 'secteur': 'Éducation',
        'couleur': '#1e3a5f', 'premium': False, 'ordre': 6,
    },
    # ── Premium ───────────────────────────────────────────────────────────────
    {
        'nom': 'Créatif Bicolore', 'fichier': 'bicolor',
        'categorie': 'Créatif', 'secteur': 'Design & Art',
        'couleur': '#F77F00', 'premium': True, 'ordre': 7,
    },
    {
        'nom': 'Executive Pro', 'fichier': 'executive',
        'categorie': 'Élégant', 'secteur': 'Direction',
        'couleur': '#0D1F3C', 'premium': True, 'ordre': 8,
    },
    {
        'nom': 'Tech Sidebar', 'fichier': 'tech-side',
        'categorie': 'Moderne', 'secteur': 'Tech & IT',
        'couleur': '#0D1117', 'premium': True, 'ordre': 9,
    },
    {
        'nom': 'Artistique', 'fichier': 'artistic',
        'categorie': 'Créatif', 'secteur': 'Design & Art',
        'couleur': '#E85D4A', 'premium': True, 'ordre': 10,
    },
    {
        'nom': 'Corporate Vert', 'fichier': 'corporate-green',
        'categorie': 'Élégant', 'secteur': 'Finance & Banque',
        'couleur': '#009A44', 'premium': True, 'ordre': 11,
    },
    {
        'nom': 'Médical Propre', 'fichier': 'medical',
        'categorie': 'Minimaliste', 'secteur': 'Santé',
        'couleur': '#1565C0', 'premium': True, 'ordre': 12,
    },
    {
        'nom': 'Infographie', 'fichier': 'infographic',
        'categorie': 'Créatif', 'secteur': 'Marketing',
        'couleur': '#F77F00', 'premium': True, 'ordre': 13,
    },
    {
        'nom': 'Juridique Sobre', 'fichier': 'legal',
        'categorie': 'Classique', 'secteur': 'Droit',
        'couleur': '#1a237e', 'premium': True, 'ordre': 14,
    },
    {
        'nom': 'Ingénieur BTP', 'fichier': 'btp',
        'categorie': 'Moderne', 'secteur': 'BTP & Industrie',
        'couleur': '#1F2937', 'premium': True, 'ordre': 15,
    },
    {
        'nom': 'Comptable Bleu', 'fichier': 'accountant',
        'categorie': 'Classique', 'secteur': 'Finance & Banque',
        'couleur': '#003366', 'premium': True, 'ordre': 16,
    },
    {
        'nom': 'Magazine Tricolonne', 'fichier': 'magazine-triple',
        'categorie': 'Créatif', 'secteur': 'Tous secteurs',
        'couleur': '#881337', 'premium': True, 'ordre': 17,
    },
    {
        'nom': 'Cuivre Prestige', 'fichier': 'cuivre-prestige',
        'categorie': 'Élégant', 'secteur': 'Direction',
        'couleur': '#B45309', 'premium': False, 'ordre': 19,
    },
    {
        'nom': 'Cosmos Indigo', 'fichier': 'cosmos',
        'categorie': 'Moderne', 'secteur': 'Tous secteurs',
        'couleur': '#6366F1', 'premium': False, 'ordre': 20,
    },
    {
        'nom': 'Scarlett Rouge', 'fichier': 'scarlett',
        'categorie': 'Créatif', 'secteur': 'Tous secteurs',
        'couleur': '#DC2626', 'premium': False, 'ordre': 21,
    },
    {
        'nom': 'Cadre Bleu', 'fichier': 'cadre-bleu',
        'categorie': 'Classique', 'secteur': 'Tous secteurs',
        'couleur': '#1B56FF', 'premium': False, 'ordre': 22,
    },
    {
        'nom': 'Émeraude Sidebar', 'fichier': 'emeraude',
        'categorie': 'Élégant', 'secteur': 'Tous secteurs',
        'couleur': '#0D3B2E', 'premium': False, 'ordre': 23,
    },
    {
        'nom': 'Terre Cuite', 'fichier': 'terre-cuite',
        'categorie': 'Élégant', 'secteur': 'Tous secteurs',
        'couleur': '#8C3A2C', 'premium': False, 'ordre': 24,
    },
    {
        'nom': 'Minuit Or', 'fichier': 'minuit-or',
        'categorie': 'Moderne', 'secteur': 'Tous secteurs',
        'couleur': '#0F172A', 'premium': False, 'ordre': 25,
    },
    {
        'nom': 'Calligraphie', 'fichier': 'calligraphie',
        'categorie': 'Élégant', 'secteur': 'Tous secteurs',
        'couleur': '#3D1A24', 'premium': False, 'ordre': 26,
    },
    {
        'nom': 'Enluminure', 'fichier': 'enluminure',
        'categorie': 'Élégant', 'secteur': 'Tous secteurs',
        'couleur': '#2C1654', 'premium': False, 'ordre': 27,
    },
    {
        'nom': 'Nuit Étoilée', 'fichier': 'nuit-etoilee',
        'categorie': 'Élégant', 'secteur': 'Tous secteurs',
        'couleur': '#1A1040', 'premium': False, 'ordre': 28,
    },
    {
        'nom': 'Vague Indigo', 'fichier': 'indigo-wave',
        'categorie': 'Moderne', 'secteur': 'Tous secteurs',
        'couleur': '#1A237E', 'premium': False, 'ordre': 29,
    },
    {
        'nom': 'Petrol & Rose', 'fichier': 'petrol-rose',
        'categorie': 'Élégant', 'secteur': 'Tous secteurs',
        'couleur': '#1B3A4B', 'premium': False, 'ordre': 30,
    },
    {
        'nom': 'Lumina', 'fichier': 'lumina',
        'categorie': 'Moderne', 'secteur': 'Tous secteurs',
        'couleur': '#1E293B', 'premium': False, 'ordre': 31,
    },
    {
        'nom': 'Noir & Or', 'fichier': 'noir-or',
        'categorie': 'Élégant', 'secteur': 'Tous secteurs',
        'couleur': '#E8B434', 'premium': False, 'ordre': 32,
    },
    {
        'nom': 'Dark Gold', 'fichier': 'dark-gold',
        'categorie': 'Moderne', 'secteur': 'Tous secteurs',
        'couleur': '#F5C518', 'premium': False, 'ordre': 33,
    },
    {
        'nom': 'Noir & Rouge', 'fichier': 'noir-rouge',
        'categorie': 'Élégant', 'secteur': 'Tous secteurs',
        'couleur': '#CC2936', 'premium': False, 'ordre': 34,
    },
    {
        'nom': 'Gris & Photo', 'fichier': 'gris-photo',
        'categorie': 'Moderne', 'secteur': 'Tous secteurs',
        'couleur': '#3D3D3D', 'premium': False, 'ordre': 35,
    },
    {
        'nom': 'Rouge & Blanc', 'fichier': 'rouge-blanc',
        'categorie': 'Moderne', 'secteur': 'Tous secteurs',
        'couleur': '#E53935', 'premium': False, 'ordre': 36,
    },
    {
        'nom': 'Bicolore Sombre', 'fichier': 'bicolor-sombre',
        'categorie': 'Élégant', 'secteur': 'Tous secteurs',
        'couleur': '#A0734A', 'premium': False, 'ordre': 37,
    },
    {
        'nom': 'Onyx & Or', 'fichier': 'onyx-or',
        'categorie': 'Élégant', 'secteur': 'Tous secteurs',
        'couleur': '#D4AF37', 'premium': False, 'ordre': 38,
    },
    {
        'nom': 'Doré Olive', 'fichier': 'dore-olive',
        'categorie': 'Élégant', 'secteur': 'Tous secteurs',
        'couleur': '#7A6408', 'premium': False, 'ordre': 39,
    },
]


class Command(BaseCommand):
    help = 'Initialise les 16 modèles de CV dans la base de données'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Supprime tous les modèles existants avant de réinsérer',
        )

    def handle(self, *args, **options):
        existants = ModeleCV.objects.count()

        if existants and not options['force']:
            self.stdout.write(self.style.WARNING(
                f'{existants} modèle(s) déjà présent(s). '
                'Utilisez --force pour tout réinitialiser.'
            ))
            return

        if options['force'] and existants:
            ModeleCV.objects.all().delete()
            self.stdout.write(self.style.NOTICE(f'{existants} modèle(s) supprimé(s).'))

        crees = 0
        for data in MODELES_INITIAUX:
            ModeleCV.objects.get_or_create(fichier=data['fichier'], defaults=data)
            crees += 1

        self.stdout.write(self.style.SUCCESS(
            f'[OK] {crees} modele(s) de CV initialise(s) avec succes.'
        ))
