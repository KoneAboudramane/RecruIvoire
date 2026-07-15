from django.core.management.base import BaseCommand
from candidat.models import ModeleLettre

MODELES = [
    {'nom': 'Classique',            'slug': 'classique',             'categorie': 'Classique',   'famille': 'classique', 'couleur': '#1a1a2e', 'ordre': 1},
    {'nom': 'Moderne',              'slug': 'moderne',                'categorie': 'Moderne',     'famille': 'classique', 'couleur': '#F77F00', 'ordre': 2},
    {'nom': 'Orange Pro',           'slug': 'orange-pro',             'categorie': 'Élégant',     'famille': 'classique', 'couleur': '#F77F00', 'ordre': 3},
    {'nom': 'Vert Ivoire',          'slug': 'vert-ivoire',            'categorie': 'Élégant',     'famille': 'classique', 'couleur': '#009A44', 'ordre': 4},
    {'nom': 'Executive',            'slug': 'executive',              'categorie': 'Élégant',     'famille': 'classique', 'couleur': '#1a1a2e', 'ordre': 5},
    {'nom': 'Minimaliste',          'slug': 'minimaliste',            'categorie': 'Minimaliste', 'famille': 'classique', 'couleur': '#1F2937', 'ordre': 6},
    {'nom': 'Corporate Bleu',       'slug': 'corporate-bleu',         'categorie': 'Élégant',     'famille': 'classique', 'couleur': '#2563EB', 'ordre': 7},
    {'nom': 'Startup Tech',         'slug': 'startup-tech',           'categorie': 'Créatif',     'famille': 'classique', 'couleur': '#1F2937', 'ordre': 8},
    {'nom': 'Académique',           'slug': 'academique',             'categorie': 'Classique',   'famille': 'classique', 'couleur': '#1a1a2e', 'ordre': 9},
    {'nom': 'Scandinave',           'slug': 'scandinave',             'categorie': 'Minimaliste', 'famille': 'sidebar',   'couleur': '#ffffff', 'ordre': 10},
    {'nom': 'Bold Typo',            'slug': 'bold-typo',              'categorie': 'Créatif',     'famille': 'accroche',  'couleur': '#1a1a2e', 'ordre': 11},
    {'nom': 'Sidebar Colonne',      'slug': 'sidebar-colonne',        'categorie': 'Moderne',     'famille': 'sidebar',   'couleur': '#1a1a2e', 'ordre': 12},
    {'nom': 'Vintage Papier',       'slug': 'vintage-papier',         'categorie': 'Classique',   'famille': 'carte',     'couleur': '#C9A227', 'ordre': 13},
    {'nom': 'Gradient Contemporain','slug': 'gradient-contemporain',  'categorie': 'Moderne',     'famille': 'accroche',  'couleur': '#2563EB', 'ordre': 14},
    {'nom': 'Ligne Rouge',          'slug': 'ligne-rouge',            'categorie': 'Minimaliste', 'famille': 'classique', 'couleur': '#ffffff', 'ordre': 15},
    {'nom': 'Grille Structurée',    'slug': 'grille-structuree',      'categorie': 'Moderne',     'famille': 'carte',     'couleur': '#1F2937', 'ordre': 16},
    {'nom': 'Signature Manuscrite', 'slug': 'signature-manuscrite',   'categorie': 'Créatif',     'famille': 'accroche',  'couleur': '#C9A227', 'ordre': 17},
    {'nom': 'Anglo-Saxon',          'slug': 'anglo-saxon',            'categorie': 'Classique',   'famille': 'carte',     'couleur': '#1a1a2e', 'ordre': 18},
    {'nom': 'Or & Noir Luxe',       'slug': 'or-noir-luxe',           'categorie': 'Élégant',     'famille': 'classique', 'couleur': '#C9A227', 'ordre': 19},
    {'nom': 'Bicolore Diagonal',    'slug': 'bicolore-diagonal',      'categorie': 'Créatif',     'famille': 'sidebar',   'couleur': '#009A44', 'ordre': 20},
]


class Command(BaseCommand):
    help = "Initialise les 20 modèles de lettre de motivation par défaut"

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO('\nInitialisation des modèles de lettre...\n'))
        created = 0
        updated = 0
        for data in MODELES:
            obj, is_new = ModeleLettre.objects.get_or_create(
                slug=data['slug'], defaults=data
            )
            if is_new:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'  ✓ Créé : {obj.nom}'))
            else:
                if obj.famille != data['famille']:
                    obj.famille = data['famille']
                    obj.save(update_fields=['famille'])
                    updated += 1
                self.stdout.write(f'  → Existe déjà : {obj.nom} (famille={obj.famille})')
        self.stdout.write(
            self.style.SUCCESS(f'\n{created} modèle(s) créé(s), {updated} famille(s) mise(s) à jour, sur {len(MODELES)}.\n')
        )
