"""Seed de données pour le demo : 5 entreprises, 3 recruteurs/entreprise, 3 offres/entreprise.

Idempotent : si une entreprise/recruteur/offre (clé email ou référence) existe
déjà, l'objet est mis à jour au lieu d'être recréé.

Usage :
    python manage.py seed_entreprises
    python manage.py seed_entreprises --reset   # supprime d'abord les données du demo
"""

import unicodedata
from datetime import date, timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from entreprise.models import (
    DROITS_DEFAUT,
    DroitAcces,
    Entreprise,
    ExperienceRequise,
    ModeTravail,
    OffreEmploi,
    OffreEmploiRecruteur,
    ParametreEntreprise,
    PlanAbonnement,
    Recruteur,
    RoleMembre,
    StatutCompte,
    StatutOffre,
    StatutVerification,
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

PASSWORD = "Abou0585"

# ── Données entreprises ───────────────────────────────────────────────────────

# Couleurs de marque pour les logos générés (fond + couleur du texte)
LOGO_COULEURS = {
    "Orange Côte d'Ivoire":            {"bg": "#F77F00", "fg": "#FFFFFF"},
    "Société Générale Côte d'Ivoire":  {"bg": "#E60028", "fg": "#FFFFFF"},
    "PETROCI Holding":                 {"bg": "#0033A0", "fg": "#FFD100"},
    "SIFCA":                           {"bg": "#009A44", "fg": "#FFFFFF"},
    "Bolloré Transport & Logistics CI":{"bg": "#1A1A2E", "fg": "#F77F00"},
}


def _logo_svg(raison_social, bg, fg):
    """Génère un SVG carré stylisé (initiales sur fond coloré) en bytes."""
    # Initiales : 2-3 premières lettres du nom (en majuscules, sans diacritiques)
    nettoye = "".join(c for c in unicodedata.normalize("NFKD", raison_social) if not unicodedata.combining(c))
    mots = [m for m in nettoye.replace("'", " ").split() if m and m[0].isalpha()]
    if len(mots) >= 3:
        initiales = "".join(m[0] for m in mots[:3]).upper()
    elif len(mots) == 2:
        initiales = (mots[0][:2] + mots[1][:1]).upper()
    else:
        initiales = mots[0][:3].upper() if mots else "ENT"

    svg = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">'
        f'<rect width="256" height="256" rx="32" fill="{bg}"/>'
        f'<circle cx="128" cy="128" r="100" fill="none" stroke="{fg}" stroke-width="3" opacity="0.25"/>'
        f'<text x="50%" y="50%" font-family="Arial, Helvetica, sans-serif" '
        f'font-size="84" font-weight="900" fill="{fg}" '
        f'text-anchor="middle" dominant-baseline="central">{initiales}</text>'
        f'</svg>'
    )
    return svg.encode("utf-8")


ENTREPRISES = [
    {
        "raisonSocial": "Orange Côte d'Ivoire",
        "emailProfessionnel": "contact@orange-ci.demo",
        "emailContact": "rh@orange-ci.demo",
        "registreCommerce": "CI-ABJ-1996-B-12345",
        "idu": "IDU-1996-OCI",
        "identifiantFiscal": "9601234A",
        "contact": "+225 27 22 23 24 25",
        "telephone": "+225 27 22 23 24 25",
        "siteWeb": "https://www.orange.ci",
        "description": (
            "Filiale du groupe Orange, opérateur leader des télécommunications "
            "en Côte d'Ivoire (mobile, internet fixe, Orange Money). Présent "
            "depuis 1996, plus de 22 millions d'abonnés actifs."
        ),
        "secteurNom": "Télécommunications",
        "secteurLegacy": "TELECOM",
        "tailleEntreprise": "1001-5000",
        "adresse": "Immeuble Orange, Boulevard Valéry Giscard d'Estaing",
        "ville": "Abidjan",
        "codePostal": "01 BP 202",
        "formeJuridique": "Société Anonyme (SA)",
        "plan": PlanAbonnement.ENTERPRISE,
    },
    {
        "raisonSocial": "Société Générale Côte d'Ivoire",
        "emailProfessionnel": "contact@sgci.demo",
        "emailContact": "recrutement@sgci.demo",
        "registreCommerce": "CI-ABJ-1962-B-00001",
        "idu": "IDU-1962-SGCI",
        "identifiantFiscal": "6200001B",
        "contact": "+225 27 20 20 11 11",
        "telephone": "+225 27 20 20 11 11",
        "siteWeb": "https://www.societegenerale.ci",
        "description": (
            "Banque universelle, filiale du Groupe Société Générale, leader "
            "sur le marché ivoirien depuis 1962. Plus de 70 agences sur le "
            "territoire, banque de détail, entreprises et corporate."
        ),
        "secteurNom": "Finance & Banque",
        "secteurLegacy": "FINANCE",
        "tailleEntreprise": "1001-5000",
        "adresse": "Avenue Joseph Anoma, Plateau",
        "ville": "Abidjan",
        "codePostal": "01 BP 1355",
        "formeJuridique": "Société Anonyme (SA)",
        "plan": PlanAbonnement.ENTERPRISE,
    },
    {
        "raisonSocial": "PETROCI Holding",
        "emailProfessionnel": "contact@petroci.demo",
        "emailContact": "rh@petroci.demo",
        "registreCommerce": "CI-ABJ-1975-B-00789",
        "idu": "IDU-1975-PETROCI",
        "identifiantFiscal": "7500789C",
        "contact": "+225 27 21 75 50 00",
        "telephone": "+225 27 21 75 50 00",
        "siteWeb": "https://www.petroci.ci",
        "description": (
            "Société Nationale d'Opérations Pétrolières de Côte d'Ivoire. "
            "Acteur de référence dans l'exploration, la production et la "
            "distribution d'hydrocarbures depuis 1975."
        ),
        "secteurNom": "Énergie & Environnement",
        "secteurLegacy": "ENERGIE",
        "tailleEntreprise": "501-1000",
        "adresse": "Immeuble Les Hévéas, Plateau",
        "ville": "Abidjan",
        "codePostal": "01 BP 1908",
        "formeJuridique": "Société Anonyme (SA)",
        "plan": PlanAbonnement.PRO,
    },
    {
        "raisonSocial": "SIFCA",
        "emailProfessionnel": "contact@sifca.demo",
        "emailContact": "carrieres@sifca.demo",
        "registreCommerce": "CI-ABJ-1964-B-00432",
        "idu": "IDU-1964-SIFCA",
        "identifiantFiscal": "6400432D",
        "contact": "+225 27 22 40 71 00",
        "telephone": "+225 27 22 40 71 00",
        "siteWeb": "https://www.groupesifca.com",
        "description": (
            "Groupe agro-industriel leader en Afrique de l'Ouest spécialisé "
            "dans l'huile de palme, le sucre, l'hévéa. Présent en Côte "
            "d'Ivoire, au Nigeria, au Ghana, au Liberia et au Sénégal."
        ),
        "secteurNom": "Agriculture & Agro-alimentaire",
        "secteurLegacy": "AGRI",
        "tailleEntreprise": "5000+",
        "adresse": "Zone 4, Marcory",
        "ville": "Abidjan",
        "codePostal": "01 BP 1289",
        "formeJuridique": "Société Anonyme (SA)",
        "plan": PlanAbonnement.PRO,
    },
    {
        "raisonSocial": "Bolloré Transport & Logistics CI",
        "emailProfessionnel": "contact@bollore-ci.demo",
        "emailContact": "talent@bollore-ci.demo",
        "registreCommerce": "CI-ABJ-1990-B-04567",
        "idu": "IDU-1990-BTLCI",
        "identifiantFiscal": "9004567E",
        "contact": "+225 27 21 21 50 00",
        "telephone": "+225 27 21 21 50 00",
        "siteWeb": "https://www.bollore-logistics.com",
        "description": (
            "Filiale ivoirienne du leader mondial du transport, de la "
            "logistique portuaire et de la chaîne d'approvisionnement. "
            "Opérateur du Terminal à Conteneurs du Port d'Abidjan."
        ),
        "secteurNom": "Transport & Logistique",
        "secteurLegacy": "TRANSPORT",
        "tailleEntreprise": "501-1000",
        "adresse": "Port d'Abidjan, Boulevard du Port",
        "ville": "Abidjan",
        "codePostal": "01 BP 1727",
        "formeJuridique": "Société par Actions Simplifiée (SAS)",
        "plan": PlanAbonnement.STARTER,
    },
]

# ── Recruteurs par entreprise ─────────────────────────────────────────────────
# Chaque entreprise reçoit le même schéma : 1 ADMIN, 1 RH, 1 MANAGER.

RECRUTEURS_TEMPLATE = [
    {"role": RoleMembre.ADMIN,   "roleLibelle": "Administrateur",  "fonction": "Directeur des Ressources Humaines"},
    {"role": RoleMembre.RH,      "roleLibelle": "Responsable RH",  "fonction": "Responsable Recrutement"},
    {"role": RoleMembre.MANAGER, "roleLibelle": "Manager",         "fonction": "Manager Opérationnel"},
]

# (prenom, nom, sexe) par entreprise — 3 personnes chacune
RECRUTEURS_NOMS = [
    # Orange CI
    [("Kouadio", "ASSI",     "Homme"),  ("Aminata", "TRAORE",  "Femme"), ("Yves",     "KOFFI",     "Homme")],
    # SGCI
    [("Marie",   "DIALLO",   "Femme"),  ("Brice",   "OUATTARA", "Homme"), ("Fatou",    "BAMBA",     "Femme")],
    # PETROCI
    [("Hervé",   "GNAGNE",   "Homme"),  ("Nadia",   "KONE",    "Femme"), ("Sylvain",  "YAO",       "Homme")],
    # SIFCA
    [("Adjoua",  "TANO",     "Femme"),  ("Patrick", "BROU",    "Homme"), ("Aïcha",    "COULIBALY", "Femme")],
    # Bolloré
    [("Eric",    "N'GUESSAN","Homme"),  ("Sandra",  "ABLE",    "Femme"), ("Olivier",  "DJEDJE",    "Homme")],
]


# ── Offres d'emploi par entreprise ────────────────────────────────────────────

OFFRES = {
    "Orange Côte d'Ivoire": [
        {
            "titre": "Ingénieur Réseau & Télécoms (5G)",
            "typeContrat": TypeContrat.CDI,
            "modeTravail": ModeTravail.HYBRIDE,
            "experience": ExperienceRequise.CONFIRME,
            "anneesExpLib": "Confirmé (2 – 5 ans)",
            "niveauEtudeLib": "Bac+5",
            "salaireMin": Decimal("900000"),
            "salaireMax": Decimal("1500000"),
            "ville": "Abidjan",
            "missions": (
                "• Concevoir et déployer l'architecture réseau 5G sur le périmètre Abidjan\n"
                "• Superviser l'exploitation des sites BTS/RNC en collaboration avec les sous-traitants\n"
                "• Analyser les KPI radio et proposer les actions d'optimisation\n"
                "• Participer aux études techniques avant-projet (chiffrage, faisabilité)\n"
                "• Assurer le reporting hebdomadaire auprès du Direction Technique"
            ),
            "profil": (
                "• Diplôme d'ingénieur Télécom (INPHB, ESATIC, INSA, équivalent)\n"
                "• 3 à 5 ans d'expérience en environnement opérateur mobile\n"
                "• Maîtrise des technos 4G/5G NR, NetAct, Huawei U2000\n"
                "• Bonne capacité d'analyse, esprit d'équipe, anglais technique"
            ),
            "competences": ["5G NR", "LTE", "Radio Planning", "NetAct", "Huawei U2000", "Anglais technique"],
            "avantages": "Mutuelle famille, prime de performance, 13e mois, formation continue, télétravail 2j/semaine",
            "nbPostes": 2,
        },
        {
            "titre": "Chargé(e) de Clientèle Orange Money",
            "typeContrat": TypeContrat.CDD,
            "modeTravail": ModeTravail.PRESENTIEL,
            "experience": ExperienceRequise.JUNIOR,
            "anneesExpLib": "Junior (0 – 2 ans)",
            "niveauEtudeLib": "Bac+2",
            "salaireMin": Decimal("250000"),
            "salaireMax": Decimal("400000"),
            "ville": "Abidjan",
            "missions": (
                "• Accueillir, conseiller et orienter la clientèle en agence\n"
                "• Promouvoir les services Orange Money (transfert, paiement marchand, micro-crédit)\n"
                "• Gérer les ouvertures de comptes et les réclamations niveau 1\n"
                "• Atteindre les objectifs commerciaux mensuels fixés"
            ),
            "profil": (
                "• BTS / DUT en commerce, marketing ou banque\n"
                "• Premier expérience (stage / alternance) en relation client appréciée\n"
                "• Excellent relationnel, présentation soignée\n"
                "• Maîtrise du français, le dioula/baoulé est un plus"
            ),
            "competences": ["Relation client", "Sens commercial", "Mobile Money", "Pack Office"],
            "avantages": "Prime de challenge, ticket repas, formation produit",
            "nbPostes": 5,
            "dureeContratMois": 12,
        },
        {
            "titre": "Data Analyst — Business Intelligence",
            "typeContrat": TypeContrat.CDI,
            "modeTravail": ModeTravail.HYBRIDE,
            "experience": ExperienceRequise.CONFIRME,
            "anneesExpLib": "Confirmé (2 – 5 ans)",
            "niveauEtudeLib": "Bac+5",
            "salaireMin": Decimal("800000"),
            "salaireMax": Decimal("1300000"),
            "ville": "Abidjan",
            "missions": (
                "• Concevoir et maintenir les dashboards stratégiques (Power BI, Tableau)\n"
                "• Modéliser les KPI commerciaux et techniques pour le COMEX\n"
                "• Croiser les données clients (CRM, facturation, usages) pour identifier des opportunités\n"
                "• Garantir la qualité et la cohérence des données sources"
            ),
            "profil": (
                "• Bac+5 en statistiques, data science ou équivalent\n"
                "• 3 ans d'expérience minimum sur poste similaire\n"
                "• SQL avancé, Python ou R, Power BI / Tableau\n"
                "• Capacité à vulgariser, esprit de synthèse, rigueur"
            ),
            "competences": ["SQL", "Python", "Power BI", "Tableau", "Statistiques", "Storytelling"],
            "avantages": "Prime annuelle, mutuelle, formation certifiante prise en charge",
            "nbPostes": 1,
        },
    ],

    "Société Générale Côte d'Ivoire": [
        {
            "titre": "Chargé(e) d'Affaires Entreprises",
            "typeContrat": TypeContrat.CDI,
            "modeTravail": ModeTravail.PRESENTIEL,
            "experience": ExperienceRequise.SENIOR,
            "anneesExpLib": "Senior (5 – 10 ans)",
            "niveauEtudeLib": "Bac+5",
            "salaireMin": Decimal("1200000"),
            "salaireMax": Decimal("2000000"),
            "ville": "Abidjan",
            "missions": (
                "• Développer et fidéliser un portefeuille d'entreprises (PME et grandes entreprises)\n"
                "• Analyser les demandes de financement et monter les dossiers de crédit\n"
                "• Négocier les conditions tarifaires en lien avec la direction des engagements\n"
                "• Assurer un suivi proactif des engagements et anticiper les risques"
            ),
            "profil": (
                "• Bac+5 en finance, gestion ou école de commerce\n"
                "• 5 à 8 ans d'expérience en banque corporate ou de financement\n"
                "• Excellente maîtrise de l'analyse financière (bilan, compte de résultat, ratios)\n"
                "• Sens commercial développé, autonomie, anglais professionnel"
            ),
            "competences": ["Analyse financière", "Crédit Corporate", "Risk Management", "Négociation", "Anglais"],
            "avantages": "Bonus sur objectifs, 13e mois, retraite complémentaire, mutuelle premium",
            "nbPostes": 2,
        },
        {
            "titre": "Auditeur(rice) Interne",
            "typeContrat": TypeContrat.CDI,
            "modeTravail": ModeTravail.PRESENTIEL,
            "experience": ExperienceRequise.CONFIRME,
            "anneesExpLib": "Confirmé (2 – 5 ans)",
            "niveauEtudeLib": "Bac+5",
            "salaireMin": Decimal("900000"),
            "salaireMax": Decimal("1400000"),
            "ville": "Abidjan",
            "missions": (
                "• Réaliser les missions d'audit interne selon le plan annuel\n"
                "• Évaluer les risques opérationnels et l'efficacité du contrôle interne\n"
                "• Rédiger les rapports d'audit et formuler des recommandations\n"
                "• Assurer le suivi de la mise en œuvre des plans d'action"
            ),
            "profil": (
                "• Bac+5 audit / contrôle / finance (DESCF, CCA, école de commerce)\n"
                "• 3 à 5 ans d'expérience en audit (Big 4 ou audit interne bancaire)\n"
                "• Certification CIA / CISA appréciée\n"
                "• Capacité d'analyse, esprit critique, intégrité, anglais courant"
            ),
            "competences": ["Audit Interne", "Contrôle Interne", "COSO", "Risk Assessment", "Anglais"],
            "avantages": "Prime annuelle, parcours mobilité internationale Groupe Société Générale",
            "nbPostes": 1,
        },
        {
            "titre": "Stagiaire Conformité / KYC",
            "typeContrat": TypeContrat.STAGE,
            "modeTravail": ModeTravail.PRESENTIEL,
            "experience": ExperienceRequise.JUNIOR,
            "anneesExpLib": "Junior (0 – 2 ans)",
            "niveauEtudeLib": "Bac+4",
            "salaireMin": Decimal("150000"),
            "salaireMax": Decimal("200000"),
            "ville": "Abidjan",
            "missions": (
                "• Contribuer aux revues KYC (Know Your Customer) du portefeuille existant\n"
                "• Collecter et vérifier les pièces justificatives clients\n"
                "• Préparer les fiches de synthèse pour le Comité de conformité\n"
                "• Participer à la veille réglementaire (LCB-FT, GAFI)"
            ),
            "profil": (
                "• Étudiant(e) en Master 1 ou Master 2 droit bancaire, conformité, finance\n"
                "• Rigueur, sens du détail, discrétion professionnelle\n"
                "• Bonne maîtrise du pack Office, anglais lu/écrit"
            ),
            "competences": ["KYC", "AML", "Réglementation bancaire", "Pack Office"],
            "avantages": "Gratification, ticket restaurant, formation continue, possibilité d'embauche",
            "nbPostes": 3,
            "dureeContratMois": 6,
        },
    ],

    "PETROCI Holding": [
        {
            "titre": "Ingénieur Production Pétrolière",
            "typeContrat": TypeContrat.CDI,
            "modeTravail": ModeTravail.PRESENTIEL,
            "experience": ExperienceRequise.SENIOR,
            "anneesExpLib": "Senior (5 – 10 ans)",
            "niveauEtudeLib": "Bac+5",
            "salaireMin": Decimal("1500000"),
            "salaireMax": Decimal("2500000"),
            "ville": "Abidjan",
            "missions": (
                "• Superviser les opérations de production sur les champs offshore\n"
                "• Optimiser les puits en production (analyse de productivité, well testing)\n"
                "• Coordonner les interventions avec les sous-traitants (work-over, slickline)\n"
                "• Garantir le respect des normes HSE sur l'ensemble des installations"
            ),
            "profil": (
                "• Diplôme d'ingénieur pétrolier (IFP, INPHB, équivalent)\n"
                "• 6 à 10 ans d'expérience en production E&P (offshore exigé)\n"
                "• Maîtrise des outils de simulation (Prosper, GAP)\n"
                "• Anglais courant indispensable, rotation 28/28 acceptée"
            ),
            "competences": ["Reservoir Engineering", "Well Testing", "Prosper", "HSE", "Anglais courant"],
            "avantages": "Prime offshore, logement, transport, mutuelle famille, plan de retraite",
            "nbPostes": 2,
        },
        {
            "titre": "Géologue d'Exploration",
            "typeContrat": TypeContrat.CDI,
            "modeTravail": ModeTravail.HYBRIDE,
            "experience": ExperienceRequise.CONFIRME,
            "anneesExpLib": "Confirmé (2 – 5 ans)",
            "niveauEtudeLib": "Bac+5",
            "salaireMin": Decimal("1100000"),
            "salaireMax": Decimal("1800000"),
            "ville": "Abidjan",
            "missions": (
                "• Interpréter les données sismiques 2D/3D du bassin sédimentaire ivoirien\n"
                "• Construire les modèles géologiques et identifier les prospects\n"
                "• Participer au chiffrage des ressources et à la rédaction des rapports techniques\n"
                "• Présenter les conclusions aux partenaires (Majors, ministère)"
            ),
            "profil": (
                "• Bac+5 en géologie / géosciences pétrolières\n"
                "• 3 à 5 ans d'expérience en exploration (offshore West Africa apprécié)\n"
                "• Maîtrise de Petrel, Kingdom, ArcGIS\n"
                "• Anglais technique courant"
            ),
            "competences": ["Sismique", "Petrel", "Kingdom", "ArcGIS", "Pétrographie", "Anglais"],
            "avantages": "Bonus exploration, mutuelle, plan de carrière international",
            "nbPostes": 1,
        },
        {
            "titre": "Technicien(ne) Maintenance Mécanique",
            "typeContrat": TypeContrat.CDD,
            "modeTravail": ModeTravail.PRESENTIEL,
            "experience": ExperienceRequise.CONFIRME,
            "anneesExpLib": "Confirmé (2 – 5 ans)",
            "niveauEtudeLib": "Bac+2",
            "salaireMin": Decimal("400000"),
            "salaireMax": Decimal("650000"),
            "ville": "Abidjan",
            "missions": (
                "• Réaliser la maintenance préventive et curative des équipements rotatifs (pompes, compresseurs, turbines)\n"
                "• Diagnostiquer les pannes et coordonner les réparations\n"
                "• Renseigner la GMAO (CMMS) et les rapports d'intervention\n"
                "• Veiller au strict respect des procédures HSE"
            ),
            "profil": (
                "• BTS / DUT Maintenance Industrielle ou équivalent\n"
                "• 3 à 5 ans d'expérience en industrie lourde / pétrolière\n"
                "• Habilitations électriques B0/H0, ATEX appréciées\n"
                "• Disponibilité pour rotations offshore"
            ),
            "competences": ["Maintenance industrielle", "GMAO", "Mécanique", "Hydraulique", "HSE"],
            "avantages": "Prime offshore, transport, équipements fournis",
            "nbPostes": 4,
            "dureeContratMois": 18,
        },
    ],

    "SIFCA": [
        {
            "titre": "Responsable de Plantation Hévéa",
            "typeContrat": TypeContrat.CDI,
            "modeTravail": ModeTravail.PRESENTIEL,
            "experience": ExperienceRequise.SENIOR,
            "anneesExpLib": "Senior (5 – 10 ans)",
            "niveauEtudeLib": "Bac+5",
            "salaireMin": Decimal("800000"),
            "salaireMax": Decimal("1300000"),
            "ville": "Bouaké",
            "missions": (
                "• Piloter l'exploitation d'un bloc de plantation hévéa (~1 500 ha)\n"
                "• Encadrer les chefs d'équipes saigneurs et les ouvriers agricoles\n"
                "• Suivre les indicateurs de productivité (rendement kg/ha, qualité du latex)\n"
                "• Mettre en œuvre les bonnes pratiques agricoles (taille, fertilisation, ITK)\n"
                "• Garantir la traçabilité et la conformité RSPO / FSC"
            ),
            "profil": (
                "• Ingénieur agronome (INPHB, IAVFF, équivalent)\n"
                "• 5 à 8 ans d'expérience en exploitation agricole tropicale (hévéa idéalement)\n"
                "• Leadership terrain, capacité à manager des équipes pluriculturelles\n"
                "• Mobilité géographique (basé en zone rurale)"
            ),
            "competences": ["Agronomie", "Hévéaculture", "Management terrain", "RSPO", "Excel"],
            "avantages": "Logement fourni, véhicule de fonction, prime de zone, école pour enfants",
            "nbPostes": 2,
        },
        {
            "titre": "Contrôleur(se) de Gestion Industriel",
            "typeContrat": TypeContrat.CDI,
            "modeTravail": ModeTravail.PRESENTIEL,
            "experience": ExperienceRequise.CONFIRME,
            "anneesExpLib": "Confirmé (2 – 5 ans)",
            "niveauEtudeLib": "Bac+5",
            "salaireMin": Decimal("700000"),
            "salaireMax": Decimal("1100000"),
            "ville": "Abidjan",
            "missions": (
                "• Élaborer le budget annuel et les forecasts trimestriels de la filiale\n"
                "• Analyser les écarts entre réel et budget, expliquer les performances\n"
                "• Calculer les coûts de revient par usine et par produit (huile, sucre)\n"
                "• Préparer le reporting mensuel pour la Direction Financière Groupe"
            ),
            "profil": (
                "• Bac+5 contrôle de gestion / finance (DSCG, école de commerce)\n"
                "• 3 à 5 ans d'expérience en contrôle de gestion industriel\n"
                "• Maîtrise SAP CO, Excel avancé, Power BI\n"
                "• Esprit d'analyse, rigueur, capacité de communication"
            ),
            "competences": ["Contrôle de gestion", "SAP", "Excel avancé", "Power BI", "Budget"],
            "avantages": "Prime annuelle, mutuelle, restaurant d'entreprise, plan d'épargne",
            "nbPostes": 1,
        },
        {
            "titre": "Alternant(e) QHSE",
            "typeContrat": TypeContrat.ALTERNANCE,
            "modeTravail": ModeTravail.PRESENTIEL,
            "experience": ExperienceRequise.JUNIOR,
            "anneesExpLib": "Junior (0 – 2 ans)",
            "niveauEtudeLib": "Bac+3",
            "salaireMin": Decimal("200000"),
            "salaireMax": Decimal("300000"),
            "ville": "Abidjan",
            "missions": (
                "• Participer au déploiement du SMQ ISO 9001 sur le site de raffinage\n"
                "• Contribuer aux audits internes QHSE et au suivi des plans d'action\n"
                "• Animer les causeries sécurité avec les opérateurs\n"
                "• Tenir à jour les indicateurs HSE (TF, TG, presque-accidents)"
            ),
            "profil": (
                "• En cursus Bac+3 / Bac+5 QHSE, ingénierie agroalimentaire\n"
                "• Première expérience industrielle (stage, projet) souhaitée\n"
                "• Connaissance des référentiels ISO 9001, 14001, 45001\n"
                "• Rigueur, curiosité, esprit terrain"
            ),
            "competences": ["ISO 9001", "ISO 14001", "ISO 45001", "Audit", "Pack Office"],
            "avantages": "Indemnité d'alternance attractive, tutorat, accès cantine",
            "nbPostes": 2,
            "dureeContratMois": 24,
        },
    ],

    "Bolloré Transport & Logistics CI": [
        {
            "titre": "Chef d'Exploitation Portuaire",
            "typeContrat": TypeContrat.CDI,
            "modeTravail": ModeTravail.PRESENTIEL,
            "experience": ExperienceRequise.SENIOR,
            "anneesExpLib": "Senior (5 – 10 ans)",
            "niveauEtudeLib": "Bac+5",
            "salaireMin": Decimal("1300000"),
            "salaireMax": Decimal("2100000"),
            "ville": "Abidjan",
            "missions": (
                "• Piloter les opérations du terminal à conteneurs (chargement / déchargement navires)\n"
                "• Coordonner les équipes opérationnelles 24/7 (~150 personnes)\n"
                "• Optimiser la productivité quai (mouvements/heure) et la rotation des conteneurs\n"
                "• Garantir la sécurité, la sûreté ISPS et le respect des KPI clients"
            ),
            "profil": (
                "• Bac+5 logistique, supply chain ou ingénieur généraliste\n"
                "• 6 à 10 ans d'expérience en terminal portuaire ou logistique de gros volume\n"
                "• Leadership confirmé sur équipes pluridisciplinaires en horaires postés\n"
                "• Anglais professionnel exigé, maîtrise TOS (Navis N4 apprécié)"
            ),
            "competences": ["Exploitation portuaire", "Navis N4", "Management d'équipe", "ISPS", "Anglais"],
            "avantages": "Bonus performance, voiture de fonction, mutuelle famille, mobilité Groupe",
            "nbPostes": 1,
        },
        {
            "titre": "Commercial(e) Freight Forwarding",
            "typeContrat": TypeContrat.CDI,
            "modeTravail": ModeTravail.HYBRIDE,
            "experience": ExperienceRequise.CONFIRME,
            "anneesExpLib": "Confirmé (2 – 5 ans)",
            "niveauEtudeLib": "Bac+3",
            "salaireMin": Decimal("600000"),
            "salaireMax": Decimal("1000000"),
            "ville": "Abidjan",
            "missions": (
                "• Développer un portefeuille clients import/export (aérien, maritime, routier)\n"
                "• Élaborer les cotations et négocier les contrats commerciaux\n"
                "• Assurer le suivi opérationnel des expéditions en lien avec les services exploitation\n"
                "• Atteindre les objectifs de volumes et de marge mensuels"
            ),
            "profil": (
                "• Bac+3 / Bac+5 commerce international ou transport-logistique\n"
                "• 3 à 5 ans d'expérience en vente B2B dans le transit / freight forwarding\n"
                "• Bonne connaissance des Incoterms, des règles douanières CEDEAO\n"
                "• Anglais professionnel, permis B, mobilité Abidjan / intérieur"
            ),
            "competences": ["Transit international", "Incoterms", "Négociation B2B", "Anglais", "CRM"],
            "avantages": "Commissions déplafonnées, véhicule, smartphone, formation Groupe",
            "nbPostes": 3,
        },
        {
            "titre": "Stagiaire Supply Chain — Analyse Flux",
            "typeContrat": TypeContrat.STAGE,
            "modeTravail": ModeTravail.HYBRIDE,
            "experience": ExperienceRequise.JUNIOR,
            "anneesExpLib": "Junior (0 – 2 ans)",
            "niveauEtudeLib": "Bac+5",
            "salaireMin": Decimal("180000"),
            "salaireMax": Decimal("250000"),
            "ville": "Abidjan",
            "missions": (
                "• Cartographier les flux logistiques d'un client grand compte\n"
                "• Identifier les gisements d'optimisation (coûts, délais, empreinte carbone)\n"
                "• Proposer un plan d'amélioration chiffré et le présenter au client\n"
                "• Participer à la mise en œuvre des premières recommandations"
            ),
            "profil": (
                "• Étudiant(e) Bac+5 école d'ingénieur ou de commerce, spécialité supply chain\n"
                "• Maîtrise Excel avancé, Power BI ou Tableau\n"
                "• Capacité d'analyse, autonomie, sens du client\n"
                "• Anglais professionnel"
            ),
            "competences": ["Supply Chain", "Analyse de données", "Excel avancé", "Power BI", "Anglais"],
            "avantages": "Gratification, ticket restaurant, possibilité d'embauche en CDI",
            "nbPostes": 2,
            "dureeContratMois": 6,
        },
    ],
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ascii(s):
    """Retire les accents (NFKD) pour générer des emails propres."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _get_or_none(model, **kwargs):
    return model.objects.filter(**kwargs).first()


def _ref_lookups():
    """Récupère tous les référentiels nécessaires en une fois."""
    return {
        "sexe_homme":   _get_or_none(SexeRef, sexe="Homme"),
        "sexe_femme":   _get_or_none(SexeRef, sexe="Femme"),
        "statut_actif": _get_or_none(StatutCompteRef, libelle="Actif"),
        "pays_ci":      _get_or_none(PaysRef, nomPays__iexact="COTE D'IVOIRE"),
        "role_admin":   _get_or_none(RoleRef, libelle="Administrateur"),
        "role_rh":      _get_or_none(RoleRef, libelle="Responsable RH"),
        "role_manager": _get_or_none(RoleRef, libelle="Manager"),
        "devise_fcfa":  _get_or_none(DeviseRef, libelle="FCFA"),
    }


def _ville_lookup(nom):
    return VilleRef.objects.filter(nomVille__iexact=nom).first()


def _contrat_ref(libelle):
    return ContratRef.objects.filter(libelle=libelle).first()


def _mode_travail_ref(libelle):
    return ModeTravailRef.objects.filter(libelle=libelle).first()


def _annees_exp_ref(libelle):
    return AnneesExperienceRef.objects.filter(libelle__iexact=libelle).first()


def _niveau_etude_ref(libelle):
    # libelle reçu peut être "Bac+5", on tolère "BAC +5" aussi
    qs = NiveauEtudeRef.objects.filter(nomNiveau__iexact=libelle)
    if qs.exists():
        return qs.first()
    norm = libelle.replace("Bac", "BAC ").replace("BAC  ", "BAC ").strip()
    return NiveauEtudeRef.objects.filter(nomNiveau__iexact=norm).first()


def _secteur_ref(nom):
    return SecteurActiviteRef.objects.filter(nomSecteur__iexact=nom).first()


def _type_raison_sociale_ref(nom):
    return TypeRaisonSocialeRef.objects.filter(nomRaisonSocial=nom).first()


# ── Command ───────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "Seed de démo : 5 entreprises, 3 recruteurs/entreprise, 3 offres/entreprise"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Supprime d'abord les entreprises du demo avant de les recréer",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        refs = _ref_lookups()
        emails_demo = [e["emailProfessionnel"] for e in ENTREPRISES]

        if options["reset"]:
            qs = Entreprise.objects.filter(emailProfessionnel__in=emails_demo)
            self.stdout.write(self.style.WARNING(
                f"--reset : suppression de {qs.count()} entreprise(s) du demo (cascade)"
            ))
            qs.delete()

        for idx, data in enumerate(ENTREPRISES):
            ent = self._upsert_entreprise(data, refs)
            self.stdout.write(self.style.SUCCESS(
                f"[Entreprise] {ent.raisonSocial}  ->  {ent.emailProfessionnel}"
            ))

            recruteurs = self._upsert_recruteurs(ent, RECRUTEURS_NOMS[idx], refs)
            for r in recruteurs:
                self.stdout.write(f"    - Recruteur : {r.email}  ({r.roleMembre})")

            ent.nombreMembre = ent.recruteurs.filter(estActif=True).count()
            ent.save(update_fields=["nombreMembre"])

            offres = self._upsert_offres(ent, OFFRES[ent.raisonSocial], recruteurs, refs)
            for o in offres:
                self.stdout.write(f"    - Offre : {o.reference} -- {o.titre} [{o.statutOffre}]")

            ent.nombreOffresActives = ent.offres.filter(statutOffre=StatutOffre.PUBLIEE).count()
            ent.save(update_fields=["nombreOffresActives"])
            ent.calculerScorePertinence()

        total_ent = Entreprise.objects.filter(emailProfessionnel__in=emails_demo).count()
        total_rec = Recruteur.objects.filter(entreprise__emailProfessionnel__in=emails_demo).count()
        total_off = OffreEmploi.objects.filter(entreprise__emailProfessionnel__in=emails_demo).count()
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Terminé : {total_ent} entreprise(s), {total_rec} recruteur(s), {total_off} offre(s)."
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Mot de passe (entreprises et recruteurs) : {PASSWORD}"
        ))

    # ── Étapes ────────────────────────────────────────────────────────────────

    def _upsert_entreprise(self, data, refs):
        ent, _created = Entreprise.objects.get_or_create(
            emailProfessionnel=data["emailProfessionnel"],
            defaults={"raisonSocial": data["raisonSocial"]},
        )
        ent.raisonSocial       = data["raisonSocial"]
        ent.registreCommerce   = data["registreCommerce"]
        ent.idu                = data["idu"]
        ent.identifiantFiscal  = data["identifiantFiscal"]
        ent.contact            = data["contact"]
        ent.telephone          = data["telephone"]
        ent.siteWeb            = data["siteWeb"]
        ent.emailContact       = data["emailContact"]
        ent.description        = data["description"]
        ent.secteurActivite    = data["secteurLegacy"]
        ent.tailleEntreprise   = data["tailleEntreprise"]
        ent.adresse            = data["adresse"]
        ent.ville              = data["ville"]
        ent.pays               = "Côte d'Ivoire"
        ent.codePostal         = data["codePostal"]
        ent.planAbonnement     = data["plan"]
        ent.droiteAcces        = DroitAcces.ADMIN
        ent.statutVerification = StatutVerification.VERIFIE
        ent.statutCompte       = StatutCompte.ACTIF
        ent.emailVerifie       = True

        ent.secteurActiviteRef    = _secteur_ref(data["secteurNom"])
        ent.typeRaisonSocialeRef  = _type_raison_sociale_ref(data["formeJuridique"])
        ent.statutCompteRef       = refs["statut_actif"]

        ent.set_password(PASSWORD)
        ent.save()

        # Génère et enregistre un logo SVG si l'entreprise n'a pas déjà un logo uploadé
        if not ent.logoEntreprise:
            couleurs = LOGO_COULEURS.get(data["raisonSocial"], {"bg": "#009A44", "fg": "#FFFFFF"})
            svg_bytes = _logo_svg(data["raisonSocial"], couleurs["bg"], couleurs["fg"])
            slug = data["emailProfessionnel"].split("@")[-1].replace(".", "_")
            ent.logoEntreprise.save(f"{slug}.svg", ContentFile(svg_bytes), save=True)

        ParametreEntreprise.get_or_create_defaut(ent)
        return ent

    def _upsert_recruteurs(self, entreprise, noms, refs):
        recruteurs = []
        slug = entreprise.emailProfessionnel.split("@")[-1]  # ex. "orange-ci.demo"

        for i, (prenom, nom, sexe_lib) in enumerate(noms):
            template = RECRUTEURS_TEMPLATE[i]
            role_enum = template["role"]
            local = _ascii(f"{prenom.lower()}.{nom.lower().replace(' ', '').replace(chr(39), '')}")
            email = f"{local}@{slug}"

            rec, _ = Recruteur.objects.get_or_create(
                email=email,
                defaults={"entreprise": entreprise},
            )
            rec.entreprise         = entreprise
            rec.prenom             = prenom
            rec.nom                = nom
            rec.nomComplet         = f"{prenom} {nom}"
            rec.emailProfessionnel = email
            rec.telephone          = f"+225 07 0{i+1} 0{i+1} 0{i+1} 0{i+1}"
            rec.adresse            = entreprise.adresse
            rec.sexe               = refs["sexe_femme"] if sexe_lib == "Femme" else refs["sexe_homme"]
            rec.dateEmbauche       = date.today() - timedelta(days=365 * (i + 1))

            rec.roleMembre = role_enum
            rec.role = {
                RoleMembre.ADMIN:   refs["role_admin"],
                RoleMembre.RH:      refs["role_rh"],
                RoleMembre.MANAGER: refs["role_manager"],
            }.get(role_enum)
            rec.droitsAcces  = DROITS_DEFAUT.get(role_enum, {})
            rec.estActif     = True
            rec.statutCompte = StatutCompte.ACTIF
            rec.emailVerifie = True

            rec.set_password(PASSWORD)
            rec.save()
            recruteurs.append(rec)
        return recruteurs

    def _upsert_offres(self, entreprise, offres_data, recruteurs, refs):
        creates = []
        # Reference déterministe : OFF-<slug-domaine>-<index>
        # (le domaine est unique par entreprise, ex: "orange-ci", "sgci"…)
        domaine = entreprise.emailProfessionnel.split("@")[-1]
        slug_ent = domaine.replace(".demo", "").replace(".", "").replace("-", "").upper()[:10]
        recruteur_rh = next((r for r in recruteurs if r.roleMembre == RoleMembre.RH), recruteurs[0])

        for idx, od in enumerate(offres_data, start=1):
            ref_code = f"OFF-{slug_ent}-{idx:02d}"
            offre, _ = OffreEmploi.objects.get_or_create(
                reference=ref_code,
                defaults={"entreprise": entreprise, "titre": od["titre"], "typeContrat": od["typeContrat"]},
            )
            offre.entreprise           = entreprise
            offre.creePar              = recruteur_rh
            offre.titre                = od["titre"]
            offre.typeContrat          = od["typeContrat"]
            offre.modeTravail          = od["modeTravail"]
            offre.localisation         = entreprise.adresse
            offre.ville                = od["ville"]
            offre.pays                 = "Côte d'Ivoire"
            offre.missions             = od["missions"]
            offre.profilRecherche      = od["profil"]
            offre.competencesRequises  = od["competences"]
            offre.experienceRequise    = od["experience"]
            offre.niveauEtudeRequis    = od["niveauEtudeLib"]
            offre.salaireMin           = od["salaireMin"]
            offre.salaireMax           = od["salaireMax"]
            offre.devise               = "FCFA"
            offre.avantages            = od["avantages"]
            offre.nombrePostes         = od["nbPostes"]
            offre.dureeContratMois     = od.get("dureeContratMois")

            offre.contrat          = _contrat_ref({
                TypeContrat.CDI:        "CDI",
                TypeContrat.CDD:        "CDD",
                TypeContrat.FREELANCE:  "Freelance / Mission",
                TypeContrat.STAGE:      "Stage",
                TypeContrat.ALTERNANCE: "Alternance",
            }[od["typeContrat"]])
            offre.modeTravailRef   = _mode_travail_ref({
                ModeTravail.PRESENTIEL: "Présentiel",
                ModeTravail.REMOTE:     "Télétravail",
                ModeTravail.HYBRIDE:    "Hybride",
            }[od["modeTravail"]])
            offre.anneesExperience = _annees_exp_ref(od["anneesExpLib"])
            offre.niveauEtudeRef   = _niveau_etude_ref(od["niveauEtudeLib"])
            offre.deviseRef        = refs["devise_fcfa"]
            offre.paysRef          = refs["pays_ci"]

            offre.statutOffre      = StatutOffre.PUBLIEE
            offre.datePublication  = timezone.now() - timedelta(days=idx * 2)
            offre.dateExpiration   = date.today() + timedelta(days=45)
            # Critères ATS — défauts cohérents par type de contrat
            if od["typeContrat"] in (TypeContrat.STAGE, TypeContrat.ALTERNANCE):
                offre.criteresATS = {
                    "cvObligatoire":                 True,
                    "lettreMotivationnObligatoire":  True,
                    "testRequis":                    False,
                    "scoreMinimum":                  50,
                }
            elif od["typeContrat"] == TypeContrat.CDI and "ngénieur" in od["titre"]:
                offre.criteresATS = {
                    "cvObligatoire":                 True,
                    "lettreMotivationnObligatoire":  False,
                    "testRequis":                    True,
                    "scoreMinimum":                  75,
                }
            else:
                offre.criteresATS = {
                    "cvObligatoire":                 True,
                    "lettreMotivationnObligatoire":  False,
                    "testRequis":                    False,
                    "scoreMinimum":                  60,
                }
            offre.save()

            ville_ref = _ville_lookup(od["ville"])
            if ville_ref:
                offre.villesRef.add(ville_ref)

            OffreEmploiRecruteur.objects.get_or_create(offre=offre, recruteur=recruteur_rh)
            creates.append(offre)
        return creates
