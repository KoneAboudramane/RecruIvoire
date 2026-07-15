"""Étend le jeu de données démo :
- ajoute 4 nouvelles entreprises (total 10),
- complète chaque entreprise existante à 5 recruteurs (rôles variés),
- garantit ≥ 2 offres publiées par recruteur.

Idempotent : relancer la commande ne crée pas de doublons.

Usage :
    python manage.py seed_etendre

Mot de passe (entreprises + recruteurs) : Abou0585
"""

import unicodedata
from datetime import date, timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from entreprise.models import (
    DROITS_DEFAUT, DroitAcces,
    Entreprise, ExperienceRequise, ModeTravail,
    OffreEmploi, OffreEmploiRecruteur, ParametreEntreprise,
    PlanAbonnement, Recruteur, RoleMembre,
    StatutCompte, StatutOffre, StatutVerification,
    TypeContrat,
)
from referentiel.models import (
    AnneesExperience as AnneesExperienceRef,
    Contrat as ContratRef,
    Devise as DeviseRef,
    ModeTravail as ModeTravailRef,
    NiveauEtude as NiveauEtudeRef,
    Pays as PaysRef,
    Role as RoleRef,
    SecteurActivite as SecteurActiviteRef,
    Sexe as SexeRef,
    StatutCompte as StatutCompteRef,
    TypeRaisonSociale as TypeRaisonSocialeRef,
    Ville as VilleRef,
)

PASSWORD = 'Abou0585'

# ── 4 nouvelles entreprises ───────────────────────────────────────────────────

ENTREPRISES_EXTRA = [
    {
        'raisonSocial':       'Nestlé Côte d\'Ivoire',
        'emailProfessionnel': 'contact@nestle-ci.demo',
        'emailContact':       'rh@nestle-ci.demo',
        'registreCommerce':   'CI-ABJ-1959-B-00120',
        'idu':                'IDU-1959-NESTLE',
        'identifiantFiscal':  '5900120F',
        'contact':            '+225 27 21 23 80 00',
        'telephone':          '+225 27 21 23 80 00',
        'siteWeb':            'https://www.nestle-cwa.com',
        'description': (
            "Filiale du groupe Nestlé, leader mondial de l'agroalimentaire. "
            "Présente en Côte d'Ivoire depuis 1959, produit MAGGI, NIDO, "
            "NESCAFÉ et CERELAC pour la sous-région."
        ),
        'secteurNom':       'Agriculture & Agro-alimentaire',
        'secteurLegacy':    'AGRI',
        'tailleEntreprise': '1001-5000',
        'adresse':          'Zone Industrielle de Yopougon',
        'ville':            'Abidjan',
        'codePostal':       '01 BP 1840',
        'formeJuridique':   'Société Anonyme (SA)',
        'plan':             PlanAbonnement.ENTERPRISE,
        'logoBg':           '#0033A0',
        'logoFg':           '#FFFFFF',
    },
    {
        'raisonSocial':       'CFAO Motors CI',
        'emailProfessionnel': 'contact@cfao-ci.demo',
        'emailContact':       'recrutement@cfao-ci.demo',
        'registreCommerce':   'CI-ABJ-1887-B-00045',
        'idu':                'IDU-1887-CFAO',
        'identifiantFiscal':  '8700045G',
        'contact':            '+225 27 21 75 30 00',
        'telephone':          '+225 27 21 75 30 00',
        'siteWeb':            'https://www.cfao.com',
        'description': (
            "Filiale du groupe CFAO (Toyota Tsusho), distributeur exclusif "
            "de marques automobiles premium (Toyota, Lexus, Suzuki) en Côte "
            "d'Ivoire. Plus de 130 ans d'expertise en Afrique."
        ),
        'secteurNom':       'Commerce & Distribution',
        'secteurLegacy':    'COMMERCE',
        'tailleEntreprise': '501-1000',
        'adresse':          'Boulevard Valéry Giscard d\'Estaing, Marcory',
        'ville':            'Abidjan',
        'codePostal':       '01 BP 2114',
        'formeJuridique':   'Société Anonyme (SA)',
        'plan':             PlanAbonnement.PRO,
        'logoBg':           '#E60028',
        'logoFg':           '#FFFFFF',
    },
    {
        'raisonSocial':       'NSIA Banque Côte d\'Ivoire',
        'emailProfessionnel': 'contact@nsia-banque-ci.demo',
        'emailContact':       'carrieres@nsia-banque-ci.demo',
        'registreCommerce':   'CI-ABJ-1995-B-00876',
        'idu':                'IDU-1995-NSIAB',
        'identifiantFiscal':  '9500876H',
        'contact':            '+225 27 20 20 10 10',
        'telephone':          '+225 27 20 20 10 10',
        'siteWeb':            'https://www.nsiabanque.ci',
        'description': (
            "Banque ivoirienne de référence, filiale du Groupe NSIA. "
            "Banque universelle de proximité avec un réseau de 70+ agences. "
            "Spécialisée en financement des PME et bancassurance."
        ),
        'secteurNom':       'Finance & Banque',
        'secteurLegacy':    'FINANCE',
        'tailleEntreprise': '501-1000',
        'adresse':          'Avenue Joseph Anoma, Plateau',
        'ville':            'Abidjan',
        'codePostal':       '01 BP 4092',
        'formeJuridique':   'Société Anonyme (SA)',
        'plan':             PlanAbonnement.PRO,
        'logoBg':           '#003DA5',
        'logoFg':           '#FFB81C',
    },
    {
        'raisonSocial':       'Eiffage Côte d\'Ivoire',
        'emailProfessionnel': 'contact@eiffage-ci.demo',
        'emailContact':       'talent@eiffage-ci.demo',
        'registreCommerce':   'CI-ABJ-1992-B-00554',
        'idu':                'IDU-1992-EIFFCI',
        'identifiantFiscal':  '9200554I',
        'contact':            '+225 27 21 27 15 00',
        'telephone':          '+225 27 21 27 15 00',
        'siteWeb':            'https://www.eiffage.ci',
        'description': (
            "Filiale ivoirienne du groupe Eiffage (BTP, énergies, "
            "infrastructures). Acteur majeur des grands chantiers publics "
            "et privés en Côte d'Ivoire (autoroutes, ponts, bâtiments)."
        ),
        'secteurNom':       'BTP & Immobilier',
        'secteurLegacy':    'BTP',
        'tailleEntreprise': '501-1000',
        'adresse':          'Rue du Commerce, Treichville',
        'ville':            'Abidjan',
        'codePostal':       '01 BP 1922',
        'formeJuridique':   'Société Anonyme (SA)',
        'plan':             PlanAbonnement.STARTER,
        'logoBg':           '#FFCD00',
        'logoFg':           '#1A1A2E',
    },
]


# ── Recruteurs supplémentaires (compléter à 5 par entreprise) ─────────────────
# Templates de rôles attendus pour chaque entreprise (5 rôles variés).
ROLES_CIBLE = [
    RoleMembre.ADMIN,
    RoleMembre.RH,
    RoleMembre.RH,
    RoleMembre.MANAGER,
    RoleMembre.LECTEUR,
]

# Pool de noms à piocher pour les recruteurs (5 prénoms / 5 noms / sexe)
POOL_NOMS = [
    [('Adama',   'BAKAYOKO',  'Homme'),  ('Mariam',  'CISSE',     'Femme'),
     ('Stéphane','KIPRE',     'Homme'),  ('Awa',     'SANGARE',   'Femme'),
     ('Mohamed', 'TOURE',     'Homme')],
    [('Estelle', 'KOUASSI',   'Femme'),  ('Désiré',  'GBA',       'Homme'),
     ('Akissi',  'AKA',       'Femme'),  ('Roland',  'YOBOUE',    'Homme'),
     ('Sylvie',  'EBO',       'Femme')],
    [('Issouf',  'DOUMBIA',   'Homme'),  ('Naomi',   'BANDAMA',   'Femme'),
     ('Cédric',  'KONAN',     'Homme'),  ('Linda',   'TIA',       'Femme'),
     ('Junior',  'OBE',       'Homme')],
    [('Aboubacar','SYLLA',    'Homme'),  ('Rachel',  'LAGO',      'Femme'),
     ('Salif',   'KEITA',     'Homme'),  ('Béatrice','KAKOU',     'Femme'),
     ('Bernard', 'AMOIKON',   'Homme')],
    [('Drissa',  'OUATTARA',  'Homme'),  ('Léa',     'KOUAME',    'Femme'),
     ('Frédéric','ZADI',      'Homme'),  ('Jasmine', 'AGRE',      'Femme'),
     ('Thierry', 'LATTE',     'Homme')],
    [('Cheick',  'BERTE',     'Homme'),  ('Carole',  'GNAHORE',   'Femme'),
     ('Romaric', 'KOUAKOU',   'Homme'),  ('Murielle','DAGO',      'Femme'),
     ('Jean',    'KOUASSI',   'Homme')],
    [('Boubacar','DIABATE',   'Homme'),  ('Mireille','GUEU',      'Femme'),
     ('Aristide','BOHUI',     'Homme'),  ('Sonia',   'KIPRE',     'Femme'),
     ('Yannick', 'TOTO',      'Homme')],
    [('Lassina', 'KOUYATE',   'Homme'),  ('Régina',  'NAHOUNOU',  'Femme'),
     ('Souleymane','TRAORE',  'Homme'),  ('Maïmouna','BAMBA',     'Femme'),
     ('Hubert',  'GAHE',      'Homme')],
    [('Karim',   'COULIBALY', 'Homme'),  ('Pélagie', 'YEO',       'Femme'),
     ('Anicet',  'KASSI',     'Homme'),  ('Rosine',  'GBAGBO',    'Femme'),
     ('Maxime',  'DOSSO',     'Homme')],
    [('Hamed',   'CAMARA',    'Homme'),  ('Christine','EHOUMAN',  'Femme'),
     ('Boris',   'YEKE',      'Homme'),  ('Sabine',  'KOFFI',     'Femme'),
     ('Lamine',  'FOFANA',    'Homme')],
]


# ── Templates d'offres par secteur (génériques, riches) ───────────────────────

OFFRES_PAR_SECTEUR = {
    'TELECOM': [
        ('Ingénieur Cybersécurité Réseaux',  TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+5', 800000, 1300000),
        ('Technicien Fibre Optique',         TypeContrat.CDD, 'Junior (0 – 2 ans)',   'Bac+2', 250000,  400000),
        ('Chef de Projet Data Center',       TypeContrat.CDI, 'Senior (5 – 10 ans)',  'Bac+5', 1200000,1800000),
        ('Analyste Performance Mobile',      TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+4', 700000, 1100000),
        ('Stagiaire DevOps Telecom',         TypeContrat.STAGE,'Junior (0 – 2 ans)',  'Bac+5', 180000,  250000),
        ('Responsable Vente B2B Fibre',      TypeContrat.CDI, 'Senior (5 – 10 ans)',  'Bac+5', 900000, 1400000),
        ('Chargé(e) Service Client',         TypeContrat.CDD, 'Junior (0 – 2 ans)',   'Bac+2', 220000,  350000),
        ('Architecte Solutions Cloud',       TypeContrat.CDI, 'Senior (5 – 10 ans)',  'Bac+5', 1500000,2200000),
        ('Développeur Mobile Android',       TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+4', 650000, 1000000),
        ('Alternant — Marketing Digital',    TypeContrat.ALTERNANCE,'Junior (0 – 2 ans)','Bac+3', 200000, 350000),
    ],
    'FINANCE': [
        ('Chargé(e) de Clientèle Particuliers',TypeContrat.CDI, 'Junior (0 – 2 ans)','Bac+3', 400000, 700000),
        ('Analyste Crédit Entreprises',      TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+5', 800000, 1300000),
        ('Conseiller Patrimoine',            TypeContrat.CDI, 'Senior (5 – 10 ans)',  'Bac+5', 1000000,1600000),
        ('Auditeur Interne',                 TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+5', 900000, 1400000),
        ('Stagiaire Contrôle de Gestion',    TypeContrat.STAGE,'Junior (0 – 2 ans)',  'Bac+5', 200000,  280000),
        ('Responsable Conformité (RCSI)',    TypeContrat.CDI, 'Senior (5 – 10 ans)',  'Bac+5', 1400000,2000000),
        ('Chargé(e) Risque Opérationnel',    TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+5', 850000, 1300000),
        ('Caissier(e) Principal(e)',         TypeContrat.CDD, 'Junior (0 – 2 ans)',   'Bac+2', 280000,  420000),
        ('Trésorier Junior',                 TypeContrat.CDI, 'Junior (0 – 2 ans)',   'Bac+4', 600000,  900000),
        ('Alternant — Banque Digitale',      TypeContrat.ALTERNANCE,'Junior (0 – 2 ans)','Bac+4', 220000, 380000),
    ],
    'ENERGIE': [
        ('Ingénieur HSE (QHSE)',             TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+5', 800000, 1200000),
        ('Technicien Maintenance Industrielle',TypeContrat.CDI,'Junior (0 – 2 ans)',  'Bac+2', 350000,  550000),
        ('Géologue Exploration',             TypeContrat.CDI, 'Senior (5 – 10 ans)',  'Bac+5', 1500000,2200000),
        ('Ingénieur Procédés',               TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+5', 1100000,1600000),
        ('Stagiaire R&D Énergies Renouvelables',TypeContrat.STAGE,'Junior (0 – 2 ans)','Bac+5',180000, 250000),
        ('Responsable Logistique Hydrocarbures',TypeContrat.CDI,'Senior (5 – 10 ans)','Bac+5', 1200000,1800000),
        ('Chargé(e) Études Réglementaires',  TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+5', 800000, 1200000),
        ('Opérateur Salle de Contrôle',      TypeContrat.CDI, 'Junior (0 – 2 ans)',   'Bac+2', 400000,  600000),
        ('Acheteur Industriel',              TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+4', 700000, 1050000),
        ('Alternant — Audit Énergie',        TypeContrat.ALTERNANCE,'Junior (0 – 2 ans)','Bac+5',200000,300000),
    ],
    'AGRI': [
        ('Chef de Plantation',               TypeContrat.CDI, 'Senior (5 – 10 ans)',  'Bac+5', 900000, 1400000),
        ('Ingénieur Agronome',               TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+5', 800000, 1200000),
        ('Responsable Qualité Production',   TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+5', 850000, 1300000),
        ('Technicien Laboratoire Agroalim.', TypeContrat.CDD, 'Junior (0 – 2 ans)',   'Bac+3', 350000,  550000),
        ('Stagiaire Innovation Produits',    TypeContrat.STAGE,'Junior (0 – 2 ans)',  'Bac+5', 200000,  280000),
        ('Chef d\'Équipe Conditionnement',   TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+3', 450000,  700000),
        ('Acheteur Matières Premières',      TypeContrat.CDI, 'Senior (5 – 10 ans)',  'Bac+5', 1000000,1500000),
        ('Commercial Terrain (Brousse)',     TypeContrat.CDI, 'Junior (0 – 2 ans)',   'Bac+3', 350000,  550000),
        ('Responsable Chaîne du Froid',      TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+5', 800000, 1200000),
        ('Alternant — RSE Agro',             TypeContrat.ALTERNANCE,'Junior (0 – 2 ans)','Bac+5',200000,300000),
    ],
    'TRANSPORT': [
        ('Coordinateur Exploitation Portuaire',TypeContrat.CDI,'Confirmé (2 – 5 ans)','Bac+5', 800000, 1200000),
        ('Agent Transit Douane',             TypeContrat.CDI, 'Junior (0 – 2 ans)',   'Bac+3', 400000,  600000),
        ('Chef de Quai',                     TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+3', 600000,  900000),
        ('Ingénieur Logistique',             TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+5', 800000, 1200000),
        ('Stagiaire Supply Chain',           TypeContrat.STAGE,'Junior (0 – 2 ans)',  'Bac+5', 180000,  250000),
        ('Commercial Fret Maritime',         TypeContrat.CDI, 'Senior (5 – 10 ans)',  'Bac+5', 900000, 1400000),
        ('Chauffeur Poids Lourds',           TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'CAP',   300000,  450000),
        ('Responsable Entrepôt',             TypeContrat.CDI, 'Senior (5 – 10 ans)',  'Bac+5', 1000000,1500000),
        ('Planneur Transport Routier',       TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+3', 550000,  850000),
        ('Alternant — Digitalisation Supply',TypeContrat.ALTERNANCE,'Junior (0 – 2 ans)','Bac+5',200000,300000),
    ],
    'TECH': [
        ('Développeur Full Stack',           TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+5', 800000, 1300000),
        ('Designer UX/UI',                   TypeContrat.CDI, 'Junior (0 – 2 ans)',   'Bac+3', 500000,  800000),
        ('Architecte Logiciel',              TypeContrat.CDI, 'Senior (5 – 10 ans)',  'Bac+5', 1500000,2200000),
        ('Data Engineer',                    TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+5', 900000, 1400000),
        ('Stagiaire Développement Backend',  TypeContrat.STAGE,'Junior (0 – 2 ans)',  'Bac+5', 180000,  250000),
        ('Product Manager',                  TypeContrat.CDI, 'Senior (5 – 10 ans)',  'Bac+5', 1200000,1800000),
        ('DevOps Engineer',                  TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+5', 1000000,1500000),
        ('QA Engineer',                      TypeContrat.CDI, 'Junior (0 – 2 ans)',   'Bac+4', 500000,  800000),
        ('Tech Lead Frontend',               TypeContrat.CDI, 'Senior (5 – 10 ans)',  'Bac+5', 1300000,2000000),
        ('Alternant — Cybersécurité',        TypeContrat.ALTERNANCE,'Junior (0 – 2 ans)','Bac+5',200000,300000),
    ],
    'COMMERCE': [
        ('Vendeur Showroom Automobile',      TypeContrat.CDI, 'Junior (0 – 2 ans)',   'Bac+2', 400000,  650000),
        ('Chef des Ventes',                  TypeContrat.CDI, 'Senior (5 – 10 ans)',  'Bac+5', 1000000,1600000),
        ('Responsable Atelier Mécanique',    TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+3', 700000, 1100000),
        ('Magasinier Pièces Détachées',      TypeContrat.CDD, 'Junior (0 – 2 ans)',   'Bac+2', 280000,  400000),
        ('Stagiaire Marketing Automobile',   TypeContrat.STAGE,'Junior (0 – 2 ans)',  'Bac+5', 180000,  250000),
        ('Conseiller Service Client SAV',    TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+3', 450000,  700000),
        ('Comptable Concessionnaire',        TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+5', 600000,  950000),
        ('Carrossier Peintre',               TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'CAP',   350000,  550000),
        ('Responsable Marketing Digital',    TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+5', 800000, 1200000),
        ('Alternant — Achats Pièces',        TypeContrat.ALTERNANCE,'Junior (0 – 2 ans)','Bac+5',200000,300000),
    ],
    'BTP': [
        ('Conducteur de Travaux',            TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+5', 900000, 1400000),
        ('Ingénieur Génie Civil',            TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+5', 1000000,1500000),
        ('Chef de Chantier Routes',          TypeContrat.CDI, 'Senior (5 – 10 ans)',  'Bac+3', 800000, 1200000),
        ('Topographe',                       TypeContrat.CDI, 'Junior (0 – 2 ans)',   'Bac+3', 450000,  700000),
        ('Stagiaire Bureau d\'Études',       TypeContrat.STAGE,'Junior (0 – 2 ans)',  'Bac+5', 200000,  280000),
        ('Responsable Qualité Sécurité',     TypeContrat.CDI, 'Senior (5 – 10 ans)',  'Bac+5', 1100000,1700000),
        ('Métreur Bâtiment',                 TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+3', 600000,  900000),
        ('Coffreur Bancheur',                TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'CAP',   400000,  600000),
        ('Chargé d\'Affaires BTP',           TypeContrat.CDI, 'Senior (5 – 10 ans)',  'Bac+5', 1200000,1800000),
        ('Alternant — Conduite de Travaux',  TypeContrat.ALTERNANCE,'Junior (0 – 2 ans)','Bac+5',200000,300000),
    ],
}

# Fallback générique si secteur inconnu
OFFRES_DEFAUT = [
    ('Assistant(e) Administratif(ve)',  TypeContrat.CDI, 'Junior (0 – 2 ans)',   'Bac+2', 300000, 500000),
    ('Chargé(e) Communication',         TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+4', 500000, 800000),
    ('Comptable',                       TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+3', 450000, 700000),
    ('Responsable Achats',              TypeContrat.CDI, 'Senior (5 – 10 ans)',  'Bac+5', 800000,1300000),
    ('Stagiaire Polyvalent',            TypeContrat.STAGE,'Junior (0 – 2 ans)',  'Bac+5', 180000, 250000),
    ('Chargé(e) RH',                    TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+5', 550000, 900000),
    ('Contrôleur de Gestion',           TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+5', 700000,1100000),
    ('Chargé(e) Marketing',             TypeContrat.CDI, 'Confirmé (2 – 5 ans)', 'Bac+4', 500000, 800000),
    ('Juriste d\'Entreprise',           TypeContrat.CDI, 'Senior (5 – 10 ans)',  'Bac+5', 800000,1300000),
    ('Alternant — RH',                  TypeContrat.ALTERNANCE,'Junior (0 – 2 ans)','Bac+5',200000,300000),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ascii(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))


def _logo_svg(raison_social, bg, fg):
    nettoye = _ascii(raison_social)
    mots = [m for m in nettoye.replace("'", ' ').split() if m and m[0].isalpha()]
    if len(mots) >= 3:
        initiales = ''.join(m[0] for m in mots[:3]).upper()
    elif len(mots) == 2:
        initiales = (mots[0][:2] + mots[1][:1]).upper()
    else:
        initiales = mots[0][:3].upper() if mots else 'ENT'
    svg = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">'
        f'<rect width="256" height="256" rx="32" fill="{bg}"/>'
        f'<text x="50%" y="50%" font-family="Arial" font-size="84" font-weight="900" '
        f'fill="{fg}" text-anchor="middle" dominant-baseline="central">{initiales}</text>'
        f'</svg>'
    )
    return svg.encode('utf-8')


def _get(model, **kwargs):
    return model.objects.filter(**kwargs).first()


def _refs():
    return {
        'sexe_h':       _get(SexeRef, sexe='Homme'),
        'sexe_f':       _get(SexeRef, sexe='Femme'),
        'statut_actif': _get(StatutCompteRef, libelle='Actif'),
        'pays_ci':      _get(PaysRef, nomPays__iexact="COTE D'IVOIRE"),
        'role_admin':   _get(RoleRef, libelle='Administrateur'),
        'role_rh':      _get(RoleRef, libelle='Responsable RH'),
        'role_manager': _get(RoleRef, libelle='Manager'),
        'role_lecteur': _get(RoleRef, libelle='Lecteur'),
        'devise_fcfa':  _get(DeviseRef, libelle='FCFA'),
    }


def _contrat_ref(tc):
    return _get(ContratRef, libelle={
        TypeContrat.CDI: 'CDI', TypeContrat.CDD: 'CDD',
        TypeContrat.FREELANCE: 'Freelance / Mission',
        TypeContrat.STAGE: 'Stage', TypeContrat.ALTERNANCE: 'Alternance',
    }[tc])


def _mode_ref(mt):
    return _get(ModeTravailRef, libelle={
        ModeTravail.PRESENTIEL: 'Présentiel',
        ModeTravail.REMOTE:     'Télétravail',
        ModeTravail.HYBRIDE:    'Hybride',
    }[mt])


def _annees_ref(lib):
    return _get(AnneesExperienceRef, libelle__iexact=lib)


def _niveau_ref(lib):
    n = _get(NiveauEtudeRef, nomNiveau__iexact=lib)
    if n:
        return n
    norm = lib.replace('Bac', 'BAC ').replace('BAC  ', 'BAC ').strip()
    return _get(NiveauEtudeRef, nomNiveau__iexact=norm)


# ── Command ───────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Étend le seed démo à 10 entreprises × 5 recruteurs × ≥ 2 offres'

    @transaction.atomic
    def handle(self, *args, **options):
        refs = _refs()

        # 1) Crée / met à jour les 4 nouvelles entreprises
        for data in ENTREPRISES_EXTRA:
            ent = self._upsert_entreprise(data, refs)
            self.stdout.write(self.style.SUCCESS(
                f"[Entreprise] {ent.raisonSocial} -> {ent.emailProfessionnel}"
            ))

        # 2) Pour chaque entreprise existante, compléter à 5 recruteurs + 2 offres
        entreprises = list(Entreprise.objects.all().order_by('id'))
        for idx, ent in enumerate(entreprises):
            self.stdout.write('')
            self.stdout.write(f"=== {ent.raisonSocial} ===")
            noms_pool = POOL_NOMS[idx % len(POOL_NOMS)]
            recs = self._completer_recruteurs(ent, noms_pool, refs)
            ent.nombreMembre = ent.recruteurs.filter(estActif=True).count()
            ent.save(update_fields=['nombreMembre'])

            # 3) Pour chaque recruteur, garantir au moins 2 offres
            for rec in recs:
                self._completer_offres(ent, rec, refs, min_offres=2)
            ent.nombreOffresActives = ent.offres.filter(statutOffre=StatutOffre.PUBLIEE).count()
            ent.save(update_fields=['nombreOffresActives'])
            ent.calculerScorePertinence()

        # 4) Récap
        total_e = Entreprise.objects.count()
        total_r = Recruteur.objects.count()
        total_o = OffreEmploi.objects.count()
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Terminé : {total_e} entreprises, {total_r} recruteurs, {total_o} offres.'
        ))
        self.stdout.write(self.style.SUCCESS(f'Mot de passe (entreprises + recruteurs) : {PASSWORD}'))

    # ── Étapes ────────────────────────────────────────────────────────────────

    def _upsert_entreprise(self, data, refs):
        ent, _ = Entreprise.objects.get_or_create(
            emailProfessionnel=data['emailProfessionnel'],
            defaults={'raisonSocial': data['raisonSocial']},
        )
        ent.raisonSocial       = data['raisonSocial']
        ent.registreCommerce   = data['registreCommerce']
        ent.idu                = data['idu']
        ent.identifiantFiscal  = data['identifiantFiscal']
        ent.contact            = data['contact']
        ent.telephone          = data['telephone']
        ent.siteWeb            = data['siteWeb']
        ent.emailContact       = data['emailContact']
        ent.description        = data['description']
        ent.secteurActivite    = data['secteurLegacy']
        ent.tailleEntreprise   = data['tailleEntreprise']
        ent.adresse            = data['adresse']
        ent.ville              = data['ville']
        ent.pays               = "Côte d'Ivoire"
        ent.codePostal         = data['codePostal']
        ent.planAbonnement     = data['plan']
        ent.droiteAcces        = DroitAcces.ADMIN
        ent.statutVerification = StatutVerification.VERIFIE
        ent.statutCompte       = StatutCompte.ACTIF
        ent.emailVerifie       = True
        ent.secteurActiviteRef = _get(SecteurActiviteRef, nomSecteur__iexact=data['secteurNom'])
        ent.typeRaisonSocialeRef = _get(TypeRaisonSocialeRef, nomRaisonSocial=data['formeJuridique'])
        ent.statutCompteRef    = refs['statut_actif']
        ent.set_password(PASSWORD)
        ent.save()
        if not ent.logoEntreprise:
            svg = _logo_svg(data['raisonSocial'], data['logoBg'], data['logoFg'])
            slug = data['emailProfessionnel'].split('@')[-1].replace('.', '_')
            ent.logoEntreprise.save(f'{slug}.svg', ContentFile(svg), save=True)
        ParametreEntreprise.get_or_create_defaut(ent)
        return ent

    def _completer_recruteurs(self, entreprise, noms_pool, refs):
        """Garantit 5 recruteurs sur l'entreprise. Conserve les existants,
        ajoute les manquants pour combler les rôles ROLES_CIBLE."""
        existants = list(entreprise.recruteurs.all().order_by('id'))
        slug = entreprise.emailProfessionnel.split('@')[-1]

        # Quels rôles manquent encore parmi les 5 cibles ?
        roles_presents = [r.roleMembre for r in existants]
        roles_cible_iter = list(ROLES_CIBLE)
        # Retire les rôles déjà couverts (1 par 1) pour ne combler que ce qui manque
        for r in roles_presents:
            if r in roles_cible_iter:
                roles_cible_iter.remove(r)
        # Si on a déjà 5 recruteurs ou plus, rien à ajouter
        nb_a_ajouter = max(0, 5 - len(existants))
        roles_a_ajouter = roles_cible_iter[:nb_a_ajouter]
        # Si la liste cible est plus courte (déjà tous les rôles), on complète en RH
        while len(roles_a_ajouter) < nb_a_ajouter:
            roles_a_ajouter.append(RoleMembre.LECTEUR)

        # Indice prénoms — saute ceux déjà utilisés (heuristique simple)
        used_emails = {r.email for r in existants}
        ajoutes = []
        i = 0
        for role_enum in roles_a_ajouter:
            # Trouve un prénom/nom dans le pool dont l'email n'existe pas
            while i < len(noms_pool):
                prenom, nom, sexe_lib = noms_pool[i]
                local = _ascii(f"{prenom.lower()}.{nom.lower().replace(' ', '').replace(chr(39), '')}")
                email = f"{local}@{slug}"
                i += 1
                if email in used_emails:
                    continue
                used_emails.add(email)
                rec = Recruteur(email=email, entreprise=entreprise)
                rec.prenom             = prenom
                rec.nom                = nom
                rec.nomComplet         = f"{prenom} {nom}"
                rec.emailProfessionnel = email
                rec.telephone          = f"+225 07 0{(i % 9) + 1} 0{(i % 9) + 1} 0{(i % 9) + 1} 0{(i % 9) + 1}"
                rec.adresse            = entreprise.adresse
                rec.sexe               = refs['sexe_f'] if sexe_lib == 'Femme' else refs['sexe_h']
                rec.dateEmbauche       = date.today() - timedelta(days=180 + i * 60)
                rec.roleMembre         = role_enum
                rec.role               = {
                    RoleMembre.ADMIN:   refs['role_admin'],
                    RoleMembre.RH:      refs['role_rh'],
                    RoleMembre.MANAGER: refs['role_manager'],
                    RoleMembre.LECTEUR: refs['role_lecteur'],
                }.get(role_enum)
                rec.droitsAcces  = DROITS_DEFAUT.get(role_enum, {})
                rec.estActif     = True
                rec.statutCompte = StatutCompte.ACTIF
                rec.emailVerifie = True
                rec.set_password(PASSWORD)
                rec.save()
                ajoutes.append(rec)
                self.stdout.write(f"   + Recruteur ajouté : {email} ({role_enum})")
                break

        return list(entreprise.recruteurs.all().order_by('id'))

    def _completer_offres(self, entreprise, recruteur, refs, min_offres=2):
        """Crée des offres pour ce recruteur jusqu'à ce qu'il en ait min_offres
        en tant que `creePar`. Idempotent (ne touche pas aux offres existantes)."""
        deja_creees = recruteur.offres_creees.count()
        a_creer = max(0, min_offres - deja_creees)
        if a_creer == 0:
            return

        secteur = entreprise.secteurActivite or 'AUTRE'
        pool = OFFRES_PAR_SECTEUR.get(secteur, OFFRES_DEFAUT)

        # Index de l'offre dans le pool pour éviter les doublons par titre
        deja_titres = set(entreprise.offres.values_list('titre', flat=True))
        # Slug entreprise pour la référence
        domaine = entreprise.emailProfessionnel.split('@')[-1]
        slug_ent = domaine.replace('.demo', '').replace('.', '').replace('-', '').upper()[:10]

        cree = 0
        for titre, type_c, exp_lib, niv_etude, sal_min, sal_max in pool:
            if cree >= a_creer:
                break
            if titre in deja_titres:
                continue
            deja_titres.add(titre)

            # Référence déterministe pour éviter les doublons
            n = entreprise.offres.count() + 1
            ref = f"OFF-{slug_ent}-{n:03d}"
            while OffreEmploi.objects.filter(reference=ref).exists():
                n += 1
                ref = f"OFF-{slug_ent}-{n:03d}"

            offre = OffreEmploi(
                entreprise=entreprise,
                reference=ref,
                titre=titre,
                creePar=recruteur,
            )
            offre.typeContrat        = type_c
            offre.modeTravail        = ModeTravail.HYBRIDE if type_c == TypeContrat.CDI else ModeTravail.PRESENTIEL
            offre.ville              = entreprise.ville
            offre.pays               = "Côte d'Ivoire"
            offre.localisation       = entreprise.adresse
            offre.missions           = (
                f"• Mission principale : {titre} chez {entreprise.raisonSocial}.\n"
                f"• Collaborer avec les équipes opérationnelles.\n"
                f"• Reporter au manager de référence sur les indicateurs clés.\n"
                f"• Participer aux projets transverses du département."
            )
            offre.profilRecherche    = (
                f"• Diplôme {niv_etude} dans un domaine pertinent.\n"
                f"• Expérience : {exp_lib}.\n"
                f"• Autonomie, esprit d'équipe, rigueur."
            )
            offre.competencesRequises = []
            offre.experienceRequise   = ExperienceRequise.CONFIRME
            offre.niveauEtudeRequis   = niv_etude
            offre.salaireMin          = Decimal(sal_min)
            offre.salaireMax          = Decimal(sal_max)
            offre.devise              = 'FCFA'

            offre.contrat             = _contrat_ref(type_c)
            offre.modeTravailRef      = _mode_ref(offre.modeTravail)
            offre.anneesExperience    = _annees_ref(exp_lib)
            offre.niveauEtudeRef      = _niveau_ref(niv_etude)
            offre.deviseRef           = refs['devise_fcfa']
            offre.paysRef             = refs['pays_ci']

            offre.statutOffre         = StatutOffre.PUBLIEE
            offre.datePublication     = timezone.now() - timedelta(days=cree + 1)
            offre.dateExpiration      = date.today() + timedelta(days=60)
            offre.criteresATS = {
                'cvObligatoire': True, 'lettreMotivationnObligatoire': False,
                'testRequis': False, 'scoreMinimum': 60,
            }
            offre.save()
            OffreEmploiRecruteur.objects.get_or_create(offre=offre, recruteur=recruteur)
            cree += 1
            self.stdout.write(f"   + Offre créée : {ref} -- {titre} (par {recruteur.email})")
