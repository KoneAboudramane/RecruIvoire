"""
Commande de seeding : pays + villes de référence.

Usage :
    python manage.py seeder_pays_villes
    python manage.py seeder_pays_villes --reset   # efface et recrée tout
"""

from django.core.management.base import BaseCommand
from referentiel.models import Pays, Ville


PAYS_VILLES = [

    # ── AFRIQUE DE L'OUEST ────────────────────────────────────────────────────
    {
        'nomPays': "Côte d'Ivoire", 'codeISO': 'CI',
        'indicatifTel': '+225', 'nationalite': 'Ivoirienne',
        'villes': [
            'Abidjan', 'Bouaké', 'Daloa', 'San-Pédro', 'Yamoussoukro',
            'Korhogo', 'Man', 'Gagnoa', 'Abengourou', 'Divo',
        ],
    },
    {
        'nomPays': 'Sénégal', 'codeISO': 'SN',
        'indicatifTel': '+221', 'nationalite': 'Sénégalaise',
        'villes': [
            'Dakar', 'Thiès', 'Kaolack', 'Ziguinchor', 'Saint-Louis',
            'Touba', 'Mbour', 'Diourbel', 'Tambacounda', 'Rufisque',
        ],
    },
    {
        'nomPays': 'Mali', 'codeISO': 'ML',
        'indicatifTel': '+223', 'nationalite': 'Malienne',
        'villes': [
            'Bamako', 'Sikasso', 'Mopti', 'Ségou', 'Koutiala',
            'Gao', 'Kayes', 'Tombouctou', 'Kidal', 'Bougouni',
        ],
    },
    {
        'nomPays': 'Burkina Faso', 'codeISO': 'BF',
        'indicatifTel': '+226', 'nationalite': 'Burkinabè',
        'villes': [
            'Ouagadougou', 'Bobo-Dioulasso', 'Koudougou', 'Banfora',
            'Ouahigouya', 'Kaya', 'Tenkodogo', 'Fada Ngourma',
        ],
    },
    {
        'nomPays': 'Guinée', 'codeISO': 'GN',
        'indicatifTel': '+224', 'nationalite': 'Guinéenne',
        'villes': [
            'Conakry', 'Kankan', 'Labé', 'Nzérékoré', 'Kindia',
            'Siguiri', 'Mamou', 'Faranah', 'Boké', 'Gueckedou',
        ],
    },
    {
        'nomPays': 'Togo', 'codeISO': 'TG',
        'indicatifTel': '+228', 'nationalite': 'Togolaise',
        'villes': [
            'Lomé', 'Sokodé', 'Kara', 'Kpalimé', 'Atakpamé',
            'Dapaong', 'Tsévié', 'Bassar', 'Aného', 'Notsé',
        ],
    },
    {
        'nomPays': 'Bénin', 'codeISO': 'BJ',
        'indicatifTel': '+229', 'nationalite': 'Béninoise',
        'villes': [
            'Cotonou', 'Porto-Novo', 'Parakou', 'Abomey-Calavi',
            'Bohicon', 'Kandi', 'Ouidah', 'Lokossa', 'Natitingou', 'Djougou',
        ],
    },
    {
        'nomPays': 'Ghana', 'codeISO': 'GH',
        'indicatifTel': '+233', 'nationalite': 'Ghanéenne',
        'villes': [
            'Accra', 'Kumasi', 'Tamale', 'Sekondi-Takoradi', 'Ashaiman',
            'Sunyani', 'Cape Coast', 'Obuasi', 'Ho', 'Koforidua',
        ],
    },
    {
        'nomPays': 'Nigeria', 'codeISO': 'NG',
        'indicatifTel': '+234', 'nationalite': 'Nigériane',
        'villes': [
            'Lagos', 'Kano', 'Ibadan', 'Abuja', 'Port Harcourt',
            'Benin City', 'Maiduguri', 'Zaria', 'Aba', 'Enugu',
        ],
    },

    # ── AFRIQUE CENTRALE ──────────────────────────────────────────────────────
    {
        'nomPays': 'Cameroun', 'codeISO': 'CM',
        'indicatifTel': '+237', 'nationalite': 'Camerounaise',
        'villes': [
            'Douala', 'Yaoundé', 'Garoua', 'Bamenda', 'Maroua',
            'Bafoussam', 'Ngaoundéré', 'Bertoua', 'Loum', 'Kumba',
        ],
    },
    {
        'nomPays': 'République Démocratique du Congo', 'codeISO': 'CD',
        'indicatifTel': '+243', 'nationalite': 'Congolaise',
        'villes': [
            'Kinshasa', 'Lubumbashi', 'Mbuji-Mayi', 'Kisangani', 'Goma',
            'Bukavu', 'Kananga', 'Tshikapa', 'Kolwezi', 'Bunia',
        ],
    },

    # ── AFRIQUE DU NORD ───────────────────────────────────────────────────────
    {
        'nomPays': 'Maroc', 'codeISO': 'MA',
        'indicatifTel': '+212', 'nationalite': 'Marocaine',
        'villes': [
            'Casablanca', 'Rabat', 'Fès', 'Marrakech', 'Tanger',
            'Agadir', 'Meknès', 'Oujda', 'Kénitra', 'Tétouan',
        ],
    },
    {
        'nomPays': 'Algérie', 'codeISO': 'DZ',
        'indicatifTel': '+213', 'nationalite': 'Algérienne',
        'villes': [
            'Alger', 'Oran', 'Constantine', 'Annaba', 'Blida',
            'Batna', 'Sétif', 'Sidi Bel Abbès', 'Biskra', 'Tlemcen',
        ],
    },
    {
        'nomPays': 'Tunisie', 'codeISO': 'TN',
        'indicatifTel': '+216', 'nationalite': 'Tunisienne',
        'villes': [
            'Tunis', 'Sfax', 'Sousse', 'Ettadhamen', 'Kairouan',
            'Bizerte', 'Gabès', 'Ariana', 'Gafsa', 'Monastir',
        ],
    },
    {
        'nomPays': 'Égypte', 'codeISO': 'EG',
        'indicatifTel': '+20', 'nationalite': 'Égyptienne',
        'villes': [
            'Le Caire', 'Alexandrie', 'Gizeh', 'Suez', 'Louxor',
            'Assouan', 'Port-Saïd', 'Ismaïlia', 'Tanta', 'Mansoura',
        ],
    },

    # ── AFRIQUE DE L'EST ──────────────────────────────────────────────────────
    {
        'nomPays': 'Kenya', 'codeISO': 'KE',
        'indicatifTel': '+254', 'nationalite': 'Kényane',
        'villes': [
            'Nairobi', 'Mombasa', 'Kisumu', 'Nakuru', 'Eldoret',
            'Thika', 'Malindi', 'Kitale', 'Garissa', 'Nyeri',
        ],
    },
    {
        'nomPays': 'Éthiopie', 'codeISO': 'ET',
        'indicatifTel': '+251', 'nationalite': 'Éthiopienne',
        'villes': [
            'Addis-Abeba', 'Dire Dawa', 'Mek\'ele', 'Gondar', 'Awasa',
            'Bahir Dar', 'Dessie', 'Jimma', 'Jijiga', 'Shashemene',
        ],
    },

    # ── AFRIQUE DU SUD ────────────────────────────────────────────────────────
    {
        'nomPays': 'Afrique du Sud', 'codeISO': 'ZA',
        'indicatifTel': '+27', 'nationalite': 'Sud-Africaine',
        'villes': [
            'Johannesburg', 'Le Cap', 'Durban', 'Pretoria', 'Soweto',
            'Port Elizabeth', 'Pietermaritzburg', 'Benoni', 'Bloemfontein', 'East London',
        ],
    },

    # ── EUROPE ────────────────────────────────────────────────────────────────
    {
        'nomPays': 'France', 'codeISO': 'FR',
        'indicatifTel': '+33', 'nationalite': 'Française',
        'villes': [
            'Paris', 'Marseille', 'Lyon', 'Toulouse', 'Nice',
            'Nantes', 'Strasbourg', 'Montpellier', 'Bordeaux', 'Lille',
        ],
    },
    {
        'nomPays': 'Belgique', 'codeISO': 'BE',
        'indicatifTel': '+32', 'nationalite': 'Belge',
        'villes': [
            'Bruxelles', 'Anvers', 'Gand', 'Charleroi', 'Liège',
            'Bruges', 'Namur', 'Louvain', 'Mons', 'Aalst',
        ],
    },
    {
        'nomPays': 'Suisse', 'codeISO': 'CH',
        'indicatifTel': '+41', 'nationalite': 'Suisse',
        'villes': [
            'Zurich', 'Genève', 'Bâle', 'Berne', 'Lausanne',
            'Winterthour', 'Lucerne', 'Saint-Gall', 'Lugano', 'Bienne',
        ],
    },
    {
        'nomPays': 'Portugal', 'codeISO': 'PT',
        'indicatifTel': '+351', 'nationalite': 'Portugaise',
        'villes': [
            'Lisbonne', 'Porto', 'Braga', 'Amadora', 'Funchal',
            'Coimbra', 'Setúbal', 'Almada', 'Queluz', 'Agualva-Cacém',
        ],
    },
    {
        'nomPays': 'Espagne', 'codeISO': 'ES',
        'indicatifTel': '+34', 'nationalite': 'Espagnole',
        'villes': [
            'Madrid', 'Barcelone', 'Valence', 'Séville', 'Saragosse',
            'Málaga', 'Murcie', 'Palma', 'Las Palmas', 'Bilbao',
        ],
    },
    {
        'nomPays': 'Royaume-Uni', 'codeISO': 'GB',
        'indicatifTel': '+44', 'nationalite': 'Britannique',
        'villes': [
            'Londres', 'Birmingham', 'Manchester', 'Glasgow', 'Liverpool',
            'Bristol', 'Sheffield', 'Leeds', 'Edinburgh', 'Leicester',
        ],
    },
    {
        'nomPays': 'Allemagne', 'codeISO': 'DE',
        'indicatifTel': '+49', 'nationalite': 'Allemande',
        'villes': [
            'Berlin', 'Hambourg', 'Munich', 'Cologne', 'Francfort',
            'Stuttgart', 'Düsseldorf', 'Dortmund', 'Essen', 'Leipzig',
        ],
    },

    # ── AMÉRIQUES ─────────────────────────────────────────────────────────────
    {
        'nomPays': 'États-Unis', 'codeISO': 'US',
        'indicatifTel': '+1', 'nationalite': 'Américaine',
        'villes': [
            'New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix',
            'Philadelphie', 'San Antonio', 'San Diego', 'Dallas', 'Miami',
        ],
    },
    {
        'nomPays': 'Canada', 'codeISO': 'CA',
        'indicatifTel': '+1', 'nationalite': 'Canadienne',
        'villes': [
            'Toronto', 'Montréal', 'Vancouver', 'Calgary', 'Edmonton',
            'Ottawa', 'Mississauga', 'Winnipeg', 'Québec', 'Hamilton',
        ],
    },
    {
        'nomPays': 'Brésil', 'codeISO': 'BR',
        'indicatifTel': '+55', 'nationalite': 'Brésilienne',
        'villes': [
            'São Paulo', 'Rio de Janeiro', 'Brasília', 'Salvador', 'Fortaleza',
            'Belo Horizonte', 'Manaus', 'Curitiba', 'Recife', 'Porto Alegre',
        ],
    },
    {
        'nomPays': 'Mexique', 'codeISO': 'MX',
        'indicatifTel': '+52', 'nationalite': 'Mexicaine',
        'villes': [
            'Mexico', 'Guadalajara', 'Monterrey', 'Puebla', 'Tijuana',
            'León', 'Ciudad Juárez', 'Zapopan', 'Mérida', 'Cancún',
        ],
    },
    {
        'nomPays': 'Haïti', 'codeISO': 'HT',
        'indicatifTel': '+509', 'nationalite': 'Haïtienne',
        'villes': [
            'Port-au-Prince', 'Cap-Haïtien', 'Gonaïves', 'Les Cayes',
            'Pétion-Ville', 'Delmas', 'Jacmel', 'Saint-Marc', 'Hinche', 'Jérémie',
        ],
    },

    # ── ASIE ──────────────────────────────────────────────────────────────────
    {
        'nomPays': 'Chine', 'codeISO': 'CN',
        'indicatifTel': '+86', 'nationalite': 'Chinoise',
        'villes': [
            'Shanghai', 'Pékin', 'Chongqing', 'Guangzhou', 'Shenzhen',
            'Tianjin', 'Chengdu', 'Wuhan', 'Xi\'an', 'Nanjing',
        ],
    },
    {
        'nomPays': 'Japon', 'codeISO': 'JP',
        'indicatifTel': '+81', 'nationalite': 'Japonaise',
        'villes': [
            'Tokyo', 'Yokohama', 'Osaka', 'Nagoya', 'Sapporo',
            'Kobe', 'Kyoto', 'Fukuoka', 'Kawasaki', 'Hiroshima',
        ],
    },
    {
        'nomPays': 'Inde', 'codeISO': 'IN',
        'indicatifTel': '+91', 'nationalite': 'Indienne',
        'villes': [
            'Mumbai', 'Delhi', 'Bangalore', 'Hyderabad', 'Ahmedabad',
            'Chennai', 'Kolkata', 'Surat', 'Pune', 'Jaipur',
        ],
    },
    {
        'nomPays': 'Arabie Saoudite', 'codeISO': 'SA',
        'indicatifTel': '+966', 'nationalite': 'Saoudienne',
        'villes': [
            'Riyad', 'Djeddah', 'La Mecque', 'Médine', 'Dammam',
            'Khobar', 'Taïf', 'Tabuk', 'Buraydah', 'Abha',
        ],
    },
    {
        'nomPays': 'Turquie', 'codeISO': 'TR',
        'indicatifTel': '+90', 'nationalite': 'Turque',
        'villes': [
            'Istanbul', 'Ankara', 'Izmir', 'Bursa', 'Adana',
            'Gaziantep', 'Konya', 'Şanlıurfa', 'Mersin', 'Diyarbakır',
        ],
    },

    # ── OCÉANIE ───────────────────────────────────────────────────────────────
    {
        'nomPays': 'Australie', 'codeISO': 'AU',
        'indicatifTel': '+61', 'nationalite': 'Australienne',
        'villes': [
            'Sydney', 'Melbourne', 'Brisbane', 'Perth', 'Adélaïde',
            'Gold Coast', 'Newcastle', 'Canberra', 'Wollongong', 'Geelong',
        ],
    },
    {
        'nomPays': 'Nouvelle-Zélande', 'codeISO': 'NZ',
        'indicatifTel': '+64', 'nationalite': 'Néo-Zélandaise',
        'villes': [
            'Auckland', 'Wellington', 'Christchurch', 'Hamilton', 'Tauranga',
            'Napier', 'Palmerston North', 'Dunedin', 'Nelson', 'Rotorua',
        ],
    },
]


class Command(BaseCommand):
    help = 'Alimente la table Pays et Ville avec les données de référence'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Supprime tous les pays et villes avant de reseeder',
        )

    def handle(self, *args, **options):
        if options['reset']:
            Ville.objects.all().delete()
            Pays.objects.all().delete()
            self.stdout.write(self.style.WARNING('Données supprimées.'))

        nb_pays_crees   = 0
        nb_villes_crees = 0

        for data in PAYS_VILLES:
            pays, pays_cree = Pays.objects.update_or_create(
                codeISO=data['codeISO'],
                defaults={
                    'nomPays':      data['nomPays'],
                    'indicatifTel': data['indicatifTel'],
                    'nationalite':  data['nationalite'],
                    'estActif':     True,
                },
            )
            if pays_cree:
                nb_pays_crees += 1

            for nom_ville in data['villes']:
                _, ville_creee = Ville.objects.get_or_create(
                    nomVille=nom_ville,
                    pays=pays,
                    defaults={'estActif': True},
                )
                if ville_creee:
                    nb_villes_crees += 1

        self.stdout.write(self.style.SUCCESS(
            f'✅ {nb_pays_crees} pays créés / mis à jour, '
            f'{nb_villes_crees} villes créées. '
            f'Total : {Pays.objects.count()} pays, {Ville.objects.count()} villes.'
        ))
