"""Seed de démo : 15 candidats avec profil complet (identité, rubriques,
liens sociaux, 2 CVs, portfolio public).

Idempotent : les candidats sont identifiés par leur email. Re-lancer la
commande met à jour les profils existants au lieu de recréer.

Usage :
    python manage.py seed_candidats
    python manage.py seed_candidats --reset   # supprime d'abord puis recrée
"""

import random
import unicodedata
from datetime import date, timedelta
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from candidat.models import (
    Benevolat,
    Candidat,
    CandidatLangue,
    Competence,
    CV,
    CVContenu,
    CentreInteret,
    ExperienceProfessionnelle,
    Formation,
    InformationPersonnelle,
    LienCandidat,
    MissionClient,
    ModeleCV,
    Portfolio,
    PosteOccupe,
    Projet,
)
from referentiel.models import (
    Contrat,
    Diplome,
    Domaine,
    Institution,
    Langue,
    Niveau,
    NiveauEtude,
    Pays,
    RaisonSociale,
    ReseauSocial,
    Sexe,
    TypeCentreInteret,
    TypeCompetence,
    TypeMobilite,
    TypePermis,
)

PASSWORD = "Abou0585"


# ═════════════════════════════════════════════════════════════════════════════
# PROFILS CANDIDATS
# ═════════════════════════════════════════════════════════════════════════════

CANDIDATS = [
    {
        "prenom": "Kouadio", "nom": "ASSOMOI", "sexe": "Homme",
        "email": "kouadio.assomoi@demo.test", "telephone": "+225 07 01 02 03 04",
        "naissance": date(1991, 4, 15), "nationalite": "Ivoirienne",
        "adresse": "II Plateaux, Cocody", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Développeur Full-Stack Senior",
        "secteur": "Numérique (Tech)",
        "biographie": "Développeur passionné par le web et les architectures distribuées. 8 ans d'expérience dans des startups et grands groupes ivoiriens. Spécialiste Python/Django et React, je conçois des plateformes scalables et maintenables.",
        "profilCV": "Développeur Full-Stack Senior · 8 ans d'expérience · Python, Django, React, PostgreSQL, AWS. Capable de mener des projets de bout en bout, du cadrage à la mise en production.",
        "anneePremEmploi": 2016, "mobilite": "International", "contrat": "CDI",
        "slogan": "Code with purpose, build with passion.",
        "couleur": "#F77F00", "portfolioFichier": "orange-vibrant",
        "experiences": [
            {"entreprise": "Orange Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 3, 1), "fin": None, "enCours": True, "description": "Lead développement plateforme Orange Money B2B (microservices Django + React). Encadrement de 4 développeurs. Migration monolithe → architecture event-driven.", "poste": "Senior Full-Stack Developer", "missionClient": {"client": "Société Générale CI", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2022, 1, 1), "fin": date(2022, 6, 30), "desc": "Intégration de l'API Orange Money dans l'application bancaire mobile SGCI."}},
            {"entreprise": "PETROCI Holding", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2016, 9, 1), "fin": date(2020, 2, 28), "enCours": False, "description": "Développement d'applications internes de suivi de production (Django REST + Angular). Refonte du système de reporting BI.", "poste": "Développeur Backend", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master en Informatique", "ecole": "INPHB Yamoussoukro", "ville": "Yamoussoukro", "pays": "COTE D'IVOIRE", "debut": date(2014, 9, 1), "fin": date(2016, 6, 30), "niveau": "Bac+5", "desc": "Spécialité Systèmes d'Information et Génie Logiciel. Major de promotion."},
            {"diplome": "Licence Informatique", "ecole": "Université Félix Houphouët-Boigny", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2011, 9, 1), "fin": date(2014, 6, 30), "niveau": "BAC +3", "desc": "Mention Bien. Projet de fin d'études : plateforme de e-learning."},
        ],
        "competences": [("Python", 5), ("Django", 5), ("React", 4), ("PostgreSQL", 4), ("Docker", 4), ("AWS", 3)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Baoulé", "C1")],
        "interets":    ["Football", "Open Source", "Photographie", "Lecture"],
        "projets": [
            {"titre": "Plateforme e-commerce TchopTchop", "contexte": "Marketplace ivoirienne dédiée aux produits locaux. 12 000 utilisateurs.", "realisation": "Conception architecture, dev backend Django, paiement Orange Money/MTN MoMo. Mise en prod sur AWS.", "url": "https://github.com/demo/tchoptchop", "debut": date(2022, 1, 1), "fin": date(2022, 12, 31)},
            {"titre": "Migration ERP PETROCI", "contexte": "Refonte d'un système de gestion legacy (Oracle Forms → web).", "realisation": "Lead technique d'une équipe de 5. Migration de 80 modules métier. Livré dans les délais.", "url": "", "debut": date(2018, 6, 1), "fin": date(2020, 1, 31)},
        ],
        "benevolats": [{"titre": "Mentor", "organisation": "Code Côte d'Ivoire", "debut": date(2019, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/kouadio-assomoi"), ("github", "https://github.com/kouadio-assomoi"), ("x", "https://x.com/kouadiocode")],
    },
    {
        "prenom": "Aminata", "nom": "TRAORE", "sexe": "Femme",
        "email": "aminata.traore@demo.test", "telephone": "+225 07 11 22 33 44",
        "naissance": date(1994, 11, 22), "nationalite": "Ivoirienne",
        "adresse": "Riviera Palmeraie", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Designer UI/UX Senior",
        "secteur": "Numérique (Tech)",
        "biographie": "Designer UI/UX avec 6 ans d'expérience, je conçois des interfaces utilisables et belles qui placent l'humain au centre. Spécialisée en design system et accessibilité.",
        "profilCV": "Designer produit avec une forte sensibilité utilisateur. Maîtrise Figma, Sketch, Adobe XD. Expérience en design system et tests utilisateurs.",
        "anneePremEmploi": 2018, "mobilite": "National", "contrat": "CDI",
        "slogan": "Design is how it works.",
        "couleur": "#E85D4A", "portfolioFichier": "snapfolio",
        "experiences": [
            {"entreprise": "MTN Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2021, 6, 1), "fin": None, "enCours": True, "description": "Lead designer de l'app MoMo Pro (200k+ utilisateurs actifs). Mise en place du design system interne.", "poste": "Lead UI/UX Designer", "missionClient": None},
            {"entreprise": "WAVE Mobile Money", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2018, 9, 1), "fin": date(2021, 5, 31), "enCours": False, "description": "Conception des écrans onboarding et transactions de l'app. A/B testing.", "poste": "Designer Produit", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master Design d'Interaction", "ecole": "Strate École de Design (Paris)", "ville": "Paris", "pays": "FRANCE", "debut": date(2016, 9, 1), "fin": date(2018, 6, 30), "niveau": "Bac+5", "desc": "Spécialité UX Research et design system. Mémoire sur l'inclusion bancaire mobile en Afrique de l'Ouest."},
            {"diplome": "Licence Arts Plastiques", "ecole": "Université Félix Houphouët-Boigny", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2013, 9, 1), "fin": date(2016, 6, 30), "niveau": "BAC +3", "desc": "Spécialité design graphique. Mention Très Bien."},
        ],
        "competences": [("Figma", 5), ("Sketch", 4), ("Adobe XD", 4), ("Design System", 5), ("Prototypage", 5)],
        "langues":     [("Français", "C2"), ("Anglais", "C1"), ("Dioula", "B2")],
        "interets":    ["Calligraphie", "Voyages", "Méditation"],
        "projets": [
            {"titre": "Design System MoMo Pro", "contexte": "Unification des composants UI de 4 produits MTN.", "realisation": "Création d'une bibliothèque Figma de 120 composants documentés. Adoption par toutes les équipes produit.", "url": "https://www.figma.com/community/momopro", "debut": date(2022, 3, 1), "fin": date(2022, 9, 30)},
            {"titre": "Refonte WAVE Onboarding", "contexte": "Améliorer le taux d'activation des nouveaux comptes (de 62% à 85%).", "realisation": "Tests utilisateurs, A/B testing sur 3 variantes, refonte du parcours. Résultat : +23 pts.", "url": "", "debut": date(2020, 1, 1), "fin": date(2020, 7, 31)},
        ],
        "benevolats": [{"titre": "Animatrice ateliers design", "organisation": "Femmes & Tech CI", "debut": date(2020, 5, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/aminata-traore"), ("behance", "https://www.behance.net/aminatatraore"), ("instagram", "https://instagram.com/aminata.designs")],
    },
    {
        "prenom": "Yves", "nom": "KOFFI", "sexe": "Homme",
        "email": "yves.koffi@demo.test", "telephone": "+225 05 02 02 02 02",
        "naissance": date(1988, 7, 8), "nationalite": "Ivoirienne",
        "adresse": "Plateau, Avenue Chardy", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Comptable Général",
        "secteur": "Finance & Banque",
        "biographie": "Comptable rigoureux avec 10 ans d'expérience en cabinet et entreprise. Expert SAGE et SYSCOHADA, j'accompagne les PME ivoiriennes dans leur gestion financière et fiscale.",
        "profilCV": "Comptable confirmé · 10 ans d'expérience SYSCOHADA · Maîtrise SAGE 100, fiscalité ivoirienne, élaboration des états financiers.",
        "anneePremEmploi": 2014, "mobilite": "Local", "contrat": "CDI",
        "slogan": "La rigueur au service de votre performance.",
        "couleur": "#009A44", "portfolioFichier": "style",
        "experiences": [
            {"entreprise": "SIFCA", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 1, 15), "fin": None, "enCours": True, "description": "Tenue de la comptabilité générale de 3 filiales. Élaboration des liasses fiscales. Animation de la clôture mensuelle.", "poste": "Comptable Général Senior", "missionClient": None},
            {"entreprise": "Cabinet Mazars CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2014, 9, 1), "fin": date(2018, 12, 31), "enCours": False, "description": "Missions d'audit et de revue comptable pour des clients du secteur agro-industriel et BTP.", "poste": "Auditeur Confirmé", "missionClient": {"client": "Cargill Côte d'Ivoire", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2016, 1, 1), "fin": date(2016, 4, 30), "desc": "Audit légal des comptes 2015. Revue des stocks cacao et procédures internes."}},
        ],
        "formations": [
            {"diplome": "DESCOGEF", "ecole": "CESAG Dakar", "ville": "Paris", "pays": "FRANCE", "debut": date(2012, 9, 1), "fin": date(2014, 6, 30), "niveau": "Bac+5", "desc": "Diplôme d'Études Supérieures en Comptabilité et Gestion Financière."},
            {"diplome": "DUT Gestion", "ecole": "INPHB Yamoussoukro", "ville": "Yamoussoukro", "pays": "COTE D'IVOIRE", "debut": date(2010, 9, 1), "fin": date(2012, 6, 30), "niveau": "BAC +2", "desc": "Spécialité Finance Comptabilité."},
        ],
        "competences": [("SAGE 100", 5), ("SYSCOHADA", 5), ("Fiscalité CI", 4), ("Excel avancé", 5), ("Power BI", 3)],
        "langues":     [("Français", "C2"), ("Anglais", "B1")],
        "interets":    ["Lecture", "Échecs", "Football", "Cuisine"],
        "projets": [
            {"titre": "Mise en place SAGE 100 SIFCA", "contexte": "Migration depuis ERP legacy vers SAGE 100 pour 3 filiales.", "realisation": "Paramétrage des comptes, formation de 12 utilisateurs, audit post-migration.", "url": "", "debut": date(2020, 6, 1), "fin": date(2021, 3, 31)},
            {"titre": "Audit Cargill 2015-2016", "contexte": "Mission d'audit légal annuel.", "realisation": "Revue complète des comptes, identification de 4 points d'amélioration sur les procédures internes.", "url": "", "debut": date(2016, 1, 1), "fin": date(2016, 4, 30)},
        ],
        "benevolats": [{"titre": "Formateur bénévole", "organisation": "Junior Achievement CI", "debut": date(2017, 9, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/yves-koffi"), ("googlechrome", "https://yveskoffi.ci")],
    },
    {
        "prenom": "Marie", "nom": "DIALLO", "sexe": "Femme",
        "email": "marie.diallo@demo.test", "telephone": "+225 07 22 33 44 55",
        "naissance": date(1992, 3, 12), "nationalite": "Ivoirienne",
        "adresse": "Marcory Résidentiel", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Auditrice Financière",
        "secteur": "Finance & Banque",
        "biographie": "Auditrice financière chez SGCI avec 7 ans d'expérience Big 4 et banque. Spécialisée en audit interne et conformité réglementaire (Bâle III, IFRS).",
        "profilCV": "Auditrice financière senior · 7 ans d'expérience · CFA Niveau 2 · Maîtrise IFRS, COSO, ACL Analytics.",
        "anneePremEmploi": 2017, "mobilite": "International", "contrat": "CDI",
        "slogan": "Audit. Insight. Trust.",
        "couleur": "#1565C0", "portfolioFichier": "orange-vibrant",
        "experiences": [
            {"entreprise": "Société Générale CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2021, 4, 1), "fin": None, "enCours": True, "description": "Pilotage du plan d'audit interne (15 missions/an). Reporting au Comité d'Audit Groupe. Conformité Bâle III.", "poste": "Auditrice Senior", "missionClient": None},
            {"entreprise": "Deloitte CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2017, 9, 1), "fin": date(2021, 3, 31), "enCours": False, "description": "Audit légal de banques et établissements financiers. Missions IFRS, FATCA, LCB-FT.", "poste": "Audit Senior", "missionClient": {"client": "Banque Atlantique CI", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2019, 1, 1), "fin": date(2019, 5, 31), "desc": "Audit légal des comptes 2018 + revue des contrôles internes IT."}},
        ],
        "formations": [
            {"diplome": "Master Finance d'Entreprise", "ecole": "ESSEC Business School", "ville": "Paris", "pays": "FRANCE", "debut": date(2015, 9, 1), "fin": date(2017, 6, 30), "niveau": "Bac+5", "desc": "Spécialité Audit & Conseil. Stage de fin d'études chez KPMG Paris."},
            {"diplome": "Licence Économie-Gestion", "ecole": "Université Paris-Dauphine", "ville": "Paris", "pays": "FRANCE", "debut": date(2012, 9, 1), "fin": date(2015, 6, 30), "niveau": "BAC +3", "desc": "Mention Bien. Bourse d'excellence du Ministère ivoirien."},
        ],
        "competences": [("Audit", 5), ("IFRS", 5), ("Bâle III", 4), ("ACL Analytics", 4), ("Risk Management", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "C1"), ("Espagnol", "B1")],
        "interets":    ["Yoga", "Randonnée", "Cinéma africain"],
        "projets": [
            {"titre": "Refonte du dispositif LCB-FT SGCI", "contexte": "Mise en conformité avec les nouvelles exigences GAFI.", "realisation": "Cartographie des risques, refonte des procédures KYC, formation de 80 collaborateurs.", "url": "", "debut": date(2022, 1, 1), "fin": date(2022, 9, 30)},
            {"titre": "Audit Banque Atlantique 2018", "contexte": "Mission d'audit légal annuel.", "realisation": "Conduite de la mission, rédaction du rapport, recommandations adoptées par le Comex.", "url": "", "debut": date(2019, 1, 1), "fin": date(2019, 5, 31)},
        ],
        "benevolats": [{"titre": "Marraine du programme", "organisation": "Elles Bougent CI", "debut": date(2021, 10, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/marie-diallo"), ("googlechrome", "https://mariediallo.com")],
    },
    {
        "prenom": "Hervé", "nom": "GNAGNE", "sexe": "Homme",
        "email": "herve.gnagne@demo.test", "telephone": "+225 07 33 44 55 66",
        "naissance": date(1985, 12, 5), "nationalite": "Ivoirienne",
        "adresse": "Cocody Angré 8e tranche", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Chef de Projet IT",
        "secteur": "Numérique (Tech)",
        "biographie": "Chef de projet IT certifié PMP/Scrum Master avec 12 ans d'expérience. Pilotage de programmes de transformation digitale pour des grands comptes en Côte d'Ivoire et Afrique de l'Ouest.",
        "profilCV": "PMP, Scrum Master · Pilotage projets IT (>2M€) · Lean management, Agile à l'échelle (SAFe).",
        "anneePremEmploi": 2012, "mobilite": "Régional", "contrat": "CDI",
        "slogan": "Bringing projects from vision to value.",
        "couleur": "#1F2937", "portfolioFichier": "style",
        "experiences": [
            {"entreprise": "Bolloré Transport & Logistics CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 5, 1), "fin": None, "enCours": True, "description": "Pilotage du programme de digitalisation des opérations portuaires (budget 1.8M€, 18 mois). Coordination de 25 personnes.", "poste": "Senior Project Manager", "missionClient": None},
            {"entreprise": "Orange Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2012, 9, 1), "fin": date(2019, 4, 30), "enCours": False, "description": "Pilotage de 15 projets IT cumulés (~5M€ total). Lead de la transition Agile pour la direction IT.", "poste": "Project Manager", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master Management de Projet", "ecole": "EMLyon Business School", "ville": "Paris", "pays": "FRANCE", "debut": date(2010, 9, 1), "fin": date(2012, 6, 30), "niveau": "Bac+5", "desc": "Spécialité Direction de projets de transformation."},
            {"diplome": "Ingénieur Génie Informatique", "ecole": "INPHB Yamoussoukro", "ville": "Yamoussoukro", "pays": "COTE D'IVOIRE", "debut": date(2005, 9, 1), "fin": date(2010, 6, 30), "niveau": "BAC +5", "desc": "Filière Génie Logiciel. Promotion 2010."},
        ],
        "competences": [("PMP", 5), ("Scrum / SAFe", 5), ("Jira", 5), ("MS Project", 4), ("Gestion budget", 5)],
        "langues":     [("Français", "C2"), ("Anglais", "C1")],
        "interets":    ["Tennis", "Voyages", "Mentoring"],
        "projets": [
            {"titre": "Digitalisation Terminal Conteneurs Bolloré", "contexte": "Modernisation du SI portuaire.", "realisation": "Lead d'un programme de 18 mois, déploiement Navis N4, formation de 150 opérateurs.", "url": "", "debut": date(2020, 1, 1), "fin": date(2021, 6, 30)},
            {"titre": "Transformation Agile Orange CI IT", "contexte": "Migration de l'organisation IT vers SAFe.", "realisation": "Définition du framework, formation de 6 RTE et 30 Scrum Masters, suivi des KPIs.", "url": "", "debut": date(2017, 9, 1), "fin": date(2018, 12, 31)},
        ],
        "benevolats": [{"titre": "Coach Junior Achievement", "organisation": "JA Côte d'Ivoire", "debut": date(2016, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/herve-gnagne"), ("github", "https://github.com/hgnagne")],
    },
    {
        "prenom": "Nadia", "nom": "KONE", "sexe": "Femme",
        "email": "nadia.kone@demo.test", "telephone": "+225 07 44 55 66 77",
        "naissance": date(1990, 8, 19), "nationalite": "Ivoirienne",
        "adresse": "Yopougon Selmer", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Ingénieure Réseau & Télécoms",
        "secteur": "Télécommunications et Digital",
        "biographie": "Ingénieure réseau passionnée par les technologies mobiles. 8 ans d'expérience en planification radio 4G/5G et optimisation chez les opérateurs ivoiriens.",
        "profilCV": "Ingénieure Telecom · LTE/5G Radio Planning · NetAct, Atoll, MapInfo · Multi-vendeur Huawei/Nokia/Ericsson.",
        "anneePremEmploi": 2016, "mobilite": "International", "contrat": "CDI",
        "slogan": "Connect the unconnected.",
        "couleur": "#F77F00", "portfolioFichier": "snapfolio",
        "experiences": [
            {"entreprise": "MTN Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 2, 1), "fin": None, "enCours": True, "description": "Planification du réseau radio 5G sur Abidjan. Coordination avec les vendeurs. Optimisation KPIs (taux de coupures < 0.5%).", "poste": "Radio Planning Engineer", "missionClient": None},
            {"entreprise": "Orange Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Bouaké", "debut": date(2016, 8, 1), "fin": date(2020, 1, 31), "enCours": False, "description": "Optimisation du réseau LTE sur la zone Centre. Audit drive-test, intégration de nouveaux sites.", "poste": "Optimization Engineer", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Ingénieur Télécommunications", "ecole": "ESATIC", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2011, 9, 1), "fin": date(2016, 6, 30), "niveau": "Bac+5", "desc": "Spécialité Réseaux Mobiles. Mémoire sur l'optimisation des cellules 4G en zone dense urbaine."},
            {"diplome": "Bac Scientifique", "ecole": "Lycée Sainte-Marie de Cocody", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2008, 9, 1), "fin": date(2011, 6, 30), "niveau": "BAC +1", "desc": "Mention Très Bien. Lauréate du concours d'entrée à l'ESATIC."},
        ],
        "competences": [("LTE/5G NR", 5), ("Atoll", 5), ("NetAct", 4), ("MapInfo", 4), ("Drive Test", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Mooré", "B1")],
        "interets":    ["Basketball", "Cuisine africaine", "Documentaires"],
        "projets": [
            {"titre": "Déploiement 5G MTN Abidjan", "contexte": "Premier déploiement commercial 5G en Côte d'Ivoire.", "realisation": "Planification de 120 sites radio, coordination Huawei/ZTE, mise en service phase 1.", "url": "", "debut": date(2022, 6, 1), "fin": date(2023, 3, 31)},
            {"titre": "Optimisation Réseau Bouaké Orange", "contexte": "Réduire le taux de coupures de 1.8% à <0.8% sur la ville.", "realisation": "Audit complet, réglages cellulaires, ajout de 8 sites. Objectif atteint en 6 mois.", "url": "", "debut": date(2018, 1, 1), "fin": date(2018, 6, 30)},
        ],
        "benevolats": [{"titre": "Animatrice ateliers STEM", "organisation": "Tech4Girls CI", "debut": date(2019, 3, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/nadia-kone"), ("github", "https://github.com/nadiakone")],
    },
    {
        "prenom": "Patrick", "nom": "BROU", "sexe": "Homme",
        "email": "patrick.brou@demo.test", "telephone": "+225 05 33 44 55 66",
        "naissance": date(1987, 2, 28), "nationalite": "Ivoirienne",
        "adresse": "Cocody Riviera Bonoumin", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Responsable Marketing Digital",
        "secteur": "Médias & Communication",
        "biographie": "Marketeur digital avec 11 ans d'expérience. Spécialiste growth & content marketing pour la consumer goods et les fintech ouest-africaines.",
        "profilCV": "Growth marketer · 11 ans · Google Ads, Meta, SEO, CRM, Marketing automation. ROI moyen +35% sur les campagnes pilotées.",
        "anneePremEmploi": 2013, "mobilite": "Régional", "contrat": "CDI",
        "slogan": "Data + Storytelling = Growth.",
        "couleur": "#E85D4A", "portfolioFichier": "orange-vibrant",
        "experiences": [
            {"entreprise": "WAVE Mobile Money", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2021, 3, 1), "fin": None, "enCours": True, "description": "Pilotage de la stratégie d'acquisition et de rétention. Budget annuel 600k€. Croissance utilisateurs +180% en 2 ans.", "poste": "Head of Marketing", "missionClient": None},
            {"entreprise": "Unilever Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2013, 9, 1), "fin": date(2021, 2, 28), "enCours": False, "description": "Brand manager sur Maggi, Knorr puis Omo. Lancement de 6 produits réussis.", "poste": "Brand Manager Senior", "missionClient": None},
        ],
        "formations": [
            {"diplome": "MBA Marketing", "ecole": "HEC Paris", "ville": "Paris", "pays": "FRANCE", "debut": date(2011, 9, 1), "fin": date(2013, 6, 30), "niveau": "Bac+5", "desc": "Spécialité Marketing & Digital Strategy. Échange Stern (NYU)."},
            {"diplome": "Licence Marketing", "ecole": "ESCA Casablanca", "ville": "Paris", "pays": "FRANCE", "debut": date(2008, 9, 1), "fin": date(2011, 6, 30), "niveau": "BAC +3", "desc": "Top 5 de la promotion. Stage HSBC Maroc."},
        ],
        "competences": [("Google Ads", 5), ("Meta Ads", 5), ("SEO", 4), ("HubSpot", 4), ("Analytics", 5)],
        "langues":     [("Français", "C2"), ("Anglais", "C1"), ("Arabe", "A2")],
        "interets":    ["Course à pied", "Photographie", "Bandes dessinées"],
        "projets": [
            {"titre": "Campagne Acquisition WAVE Sénégal", "contexte": "Pénétrer le marché sénégalais en 6 mois.", "realisation": "Stratégie multicanale, partenariats influenceurs, 300k installations en 4 mois.", "url": "", "debut": date(2022, 4, 1), "fin": date(2022, 9, 30)},
            {"titre": "Lancement Maggi Étoile", "contexte": "Nouveau bouillon premium ciblant les ménages urbains.", "realisation": "Campagne TV+digital, partenariat avec 8 chefs cuisiniers. Atteinte des objectifs à 115%.", "url": "", "debut": date(2018, 6, 1), "fin": date(2019, 3, 31)},
        ],
        "benevolats": [{"titre": "Conseil pro bono", "organisation": "Impact Hub Abidjan", "debut": date(2020, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/patrick-brou"), ("x", "https://x.com/patrickbrou")],
    },
    {
        "prenom": "Aïcha", "nom": "COULIBALY", "sexe": "Femme",
        "email": "aicha.coulibaly@demo.test", "telephone": "+225 07 55 66 77 88",
        "naissance": date(1993, 6, 14), "nationalite": "Ivoirienne",
        "adresse": "Cocody Deux Plateaux", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Data Analyst",
        "secteur": "Numérique (Tech)",
        "biographie": "Data analyst avec 5 ans d'expérience dans la banque et l'e-commerce. Passionnée par la visualisation et le data storytelling.",
        "profilCV": "Data analyst · SQL, Python, Power BI, Tableau · Statistiques inférentielles · Capable de transformer des données en insights actionnables.",
        "anneePremEmploi": 2019, "mobilite": "Télétravail uniquement", "contrat": "CDI",
        "slogan": "Numbers tell stories.",
        "couleur": "#2A9D8F", "portfolioFichier": "style",
        "experiences": [
            {"entreprise": "Société Générale CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2022, 2, 1), "fin": None, "enCours": True, "description": "Analyse comportementale clientèle, scoring de risque crédit, dashboards stratégiques pour le COMEX.", "poste": "Data Analyst Senior", "missionClient": None},
            {"entreprise": "Jumia Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 9, 1), "fin": date(2022, 1, 31), "enCours": False, "description": "Analyse des KPI commerciaux, cohort analysis, recommandations sur l'assortiment produit.", "poste": "Data Analyst", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master Statistiques", "ecole": "ENSEA Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2017, 9, 1), "fin": date(2019, 6, 30), "niveau": "Bac+5", "desc": "Spécialité Data Science. Stage de fin d'études BCEAO."},
            {"diplome": "Licence Mathématiques", "ecole": "Université Félix Houphouët-Boigny", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2014, 9, 1), "fin": date(2017, 6, 30), "niveau": "BAC +3", "desc": "Mention Bien. 2e prix concours d'analyse de données BCEAO."},
        ],
        "competences": [("SQL", 5), ("Python (Pandas)", 5), ("Power BI", 4), ("Tableau", 4), ("Statistiques", 5)],
        "langues":     [("Français", "C2"), ("Anglais", "B2")],
        "interets":    ["Sudoku", "Cinéma", "Voyages", "Café"],
        "projets": [
            {"titre": "Scoring crédit SGCI", "contexte": "Améliorer la décision d'octroi des crédits aux PME.", "realisation": "Modèle logistique sur 10 ans d'historique, intégration dans le SI. Gain : -18% sur le taux de défaut.", "url": "", "debut": date(2022, 6, 1), "fin": date(2023, 2, 28)},
            {"titre": "Cohort analysis Jumia CI", "contexte": "Comprendre la rétention des nouveaux clients.", "realisation": "Pipeline Python, dashboard Tableau, identification de 3 leviers d'amélioration adoptés.", "url": "", "debut": date(2020, 6, 1), "fin": date(2020, 12, 31)},
        ],
        "benevolats": [{"titre": "Mentore Data", "organisation": "WomenInData CI", "debut": date(2021, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/aicha-coulibaly"), ("github", "https://github.com/aichakoulibaly")],
    },
    {
        "prenom": "Sylvain", "nom": "YAO", "sexe": "Homme",
        "email": "sylvain.yao@demo.test", "telephone": "+225 05 66 77 88 99",
        "naissance": date(1986, 9, 23), "nationalite": "Ivoirienne",
        "adresse": "Treichville Boulevard de Marseille", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "ABCDE", "titre": "Ingénieur QHSE",
        "secteur": "Industrie manufacturière",
        "biographie": "Ingénieur QHSE certifié ISO 9001/14001/45001 avec 10 ans en industrie agroalimentaire et pétrolière. Passionné par la culture sécurité au travail.",
        "profilCV": "Ingénieur QHSE · ISO 9001/14001/45001 Lead Auditor · 0 accident grave sur les 24 derniers mois pilotés.",
        "anneePremEmploi": 2014, "mobilite": "National", "contrat": "CDI",
        "slogan": "Safety first, always.",
        "couleur": "#C9A227", "portfolioFichier": "snapfolio",
        "experiences": [
            {"entreprise": "PETROCI Holding", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 1, 15), "fin": None, "enCours": True, "description": "Animation du SMQ multi-sites (2 raffineries, 6 dépôts). Plans de prévention, audits internes mensuels, formation HSE.", "poste": "Ingénieur QHSE Senior", "missionClient": None},
            {"entreprise": "SIFCA", "pays": "COTE D'IVOIRE", "ville": "Bouaké", "debut": date(2014, 10, 1), "fin": date(2019, 12, 31), "enCours": False, "description": "Mise en place et certification ISO 9001 puis 14001 d'une raffinerie d'huile de palme.", "poste": "Responsable QHSE", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Ingénieur Génie Industriel", "ecole": "Polytech Lille", "ville": "Lille", "pays": "FRANCE", "debut": date(2009, 9, 1), "fin": date(2014, 6, 30), "niveau": "Bac+5", "desc": "Spécialité Sécurité Industrielle. Lauréat du concours ATOUT 2014."},
            {"diplome": "DEUG Sciences Industrielles", "ecole": "Université Félix Houphouët-Boigny", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2007, 9, 1), "fin": date(2009, 6, 30), "niveau": "BAC +2", "desc": "Mention Très Bien. Major de promotion."},
        ],
        "competences": [("ISO 9001/14001/45001", 5), ("Audit interne", 5), ("HAZOP", 4), ("Risk Assessment", 5), ("Excel", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Baoulé", "C1")],
        "interets":    ["Pêche", "Jardinage", "Karaté"],
        "projets": [
            {"titre": "Certification ISO 14001 SIFCA Bouaké", "contexte": "Première certification environnement du site.", "realisation": "Diagnostic, plan d'actions, formation des équipes, audit Bureau Veritas validé du 1er coup.", "url": "", "debut": date(2017, 1, 1), "fin": date(2018, 6, 30)},
            {"titre": "Refonte plan d'urgence PETROCI", "contexte": "Mise à jour suite à incident 2020.", "realisation": "Revue complète, exercice grandeur nature avec pompiers GSPM, validation DGPC.", "url": "", "debut": date(2021, 1, 1), "fin": date(2021, 8, 31)},
        ],
        "benevolats": [{"titre": "Formateur secourisme", "organisation": "Croix-Rouge Côte d'Ivoire", "debut": date(2015, 5, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/sylvain-yao"), ("googlechrome", "https://sylvainyao.ci")],
    },
    {
        "prenom": "Brice", "nom": "OUATTARA", "sexe": "Homme",
        "email": "brice.ouattara@demo.test", "telephone": "+225 07 77 88 99 00",
        "naissance": date(1989, 1, 30), "nationalite": "Ivoirienne",
        "adresse": "Marcory Zone 4", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Commercial B2B Senior",
        "secteur": "Commerce et Distribution",
        "biographie": "Commercial confirmé dans les biens d'équipement et services aux entreprises. Track record de 9 ans avec +12M€ de chiffre d'affaires généré.",
        "profilCV": "Commercial B2B · 9 ans · Cycle long, comptes stratégiques, négociation grands comptes. Hunter & Farmer.",
        "anneePremEmploi": 2015, "mobilite": "Régional", "contrat": "CDI",
        "slogan": "Customer is king, partnership is queen.",
        "couleur": "#003366", "portfolioFichier": "orange-vibrant",
        "experiences": [
            {"entreprise": "Schneider Electric CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 6, 1), "fin": None, "enCours": True, "description": "Gestion d'un portefeuille de 25 grands comptes (BTP, Mines, Industrie). Atteinte des quotas à 124% en moyenne.", "poste": "Key Account Manager", "missionClient": None},
            {"entreprise": "Xerox Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2015, 9, 1), "fin": date(2020, 5, 31), "enCours": False, "description": "Vente de solutions d'impression et de gestion documentaire. Croissance du portefeuille +180% sur 5 ans.", "poste": "Account Executive", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master Commerce International", "ecole": "INSEEC Paris", "ville": "Paris", "pays": "FRANCE", "debut": date(2013, 9, 1), "fin": date(2015, 6, 30), "niveau": "Bac+5", "desc": "Spécialité Négociation B2B. Mémoire sur les pratiques commerciales en Afrique de l'Ouest."},
            {"diplome": "BTS Commerce", "ecole": "ESCA Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2011, 9, 1), "fin": date(2013, 6, 30), "niveau": "BAC +2", "desc": "Major de promotion. Stage Air France-KLM Abidjan."},
        ],
        "competences": [("Négociation", 5), ("Salesforce", 4), ("Pipeline management", 5), ("Lead generation", 4), ("Excel", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Italien", "A2")],
        "interets":    ["Golf", "Vin", "Voyages d'affaires"],
        "projets": [
            {"titre": "Contrat Schneider × SODECI", "contexte": "Renouvellement contrat-cadre 5 ans, 3.5M€.", "realisation": "Pilotage de la consultation, négociation, signature en septembre 2022.", "url": "", "debut": date(2022, 4, 1), "fin": date(2022, 9, 30)},
            {"titre": "Pénétration secteur Mines", "contexte": "Ouverture d'un nouveau segment client.", "realisation": "Cartographie des 30 mines actives, prise de RDV, signature de 4 contrats la 1ère année.", "url": "", "debut": date(2021, 1, 1), "fin": date(2021, 12, 31)},
        ],
        "benevolats": [{"titre": "Coach commercial", "organisation": "Jeune Chambre Économique CI", "debut": date(2018, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/brice-ouattara")],
    },
    {
        "prenom": "Fatou", "nom": "BAMBA", "sexe": "Femme",
        "email": "fatou.bamba@demo.test", "telephone": "+225 07 88 99 00 11",
        "naissance": date(1991, 5, 7), "nationalite": "Ivoirienne",
        "adresse": "Cocody Angré 7e tranche", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Chargée de Mission RH",
        "secteur": "ONG & Secteur public",
        "biographie": "Chargée de mission RH avec 7 ans d'expérience en recrutement, formation et accompagnement du changement. Convaincue que le capital humain est le 1er actif des organisations.",
        "profilCV": "Chargée RH · Recrutement, formation, accompagnement managérial · 200+ recrutements pilotés.",
        "anneePremEmploi": 2017, "mobilite": "Local", "contrat": "CDI",
        "slogan": "Putting people first.",
        "couleur": "#E9C46A", "portfolioFichier": "snapfolio",
        "experiences": [
            {"entreprise": "Orange Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2021, 8, 1), "fin": None, "enCours": True, "description": "Pilotage du plan de recrutement (80 recrutements/an). Gestion des partenariats écoles. Accompagnement de la transformation digitale RH.", "poste": "Talent Acquisition Manager", "missionClient": None},
            {"entreprise": "PwC Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2017, 10, 1), "fin": date(2021, 7, 31), "enCours": False, "description": "Conseil RH pour des clients banque/télécom/industrie. Missions de diagnostic, refonte des processus, change management.", "poste": "Consultante RH Senior", "missionClient": {"client": "Bolloré Transport & Logistics CI", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2019, 6, 1), "fin": date(2019, 11, 30), "desc": "Refonte du processus d'entretien annuel pour 800 collaborateurs."}},
        ],
        "formations": [
            {"diplome": "Master GRH", "ecole": "Université Paris-Dauphine", "ville": "Paris", "pays": "FRANCE", "debut": date(2015, 9, 1), "fin": date(2017, 6, 30), "niveau": "Bac+5", "desc": "Spécialité Talent Management. Stage Total HQ Paris."},
            {"diplome": "Licence Psychologie", "ecole": "Université Félix Houphouët-Boigny", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2012, 9, 1), "fin": date(2015, 6, 30), "niveau": "BAC +3", "desc": "Mention Bien."},
        ],
        "competences": [("Recrutement", 5), ("SIRH (Oracle HCM)", 4), ("LinkedIn Recruiter", 5), ("Conduite du changement", 4), ("Coaching", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Wolof", "A2")],
        "interets":    ["Danse afro", "Lecture", "Cuisine", "Voyages"],
        "projets": [
            {"titre": "Programme Talent Pool Orange", "contexte": "Construire un vivier de 200 candidats qualifiés.", "realisation": "Stratégie sourcing, partenariats 6 écoles, événements campus, plateforme dédiée.", "url": "", "debut": date(2022, 1, 1), "fin": date(2022, 12, 31)},
            {"titre": "Refonte entretiens Bolloré", "contexte": "Mission de conseil de 6 mois.", "realisation": "Nouveau référentiel compétences, formation de 80 managers, déploiement en 4 vagues.", "url": "", "debut": date(2019, 6, 1), "fin": date(2019, 11, 30)},
        ],
        "benevolats": [{"titre": "Coach carrière", "organisation": "Femmes Leaders CI", "debut": date(2018, 9, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/fatou-bamba")],
    },
    {
        "prenom": "Adjoua", "nom": "TANO", "sexe": "Femme",
        "email": "adjoua.tano@demo.test", "telephone": "+225 07 99 00 11 22",
        "naissance": date(1984, 10, 11), "nationalite": "Ivoirienne",
        "adresse": "Treichville Avenue 16", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Architecte Logiciel",
        "secteur": "Numérique (Tech)",
        "biographie": "Architecte logiciel passionnée par les systèmes distribués et le cloud. 13 ans dans la tech, dont 4 en Europe.",
        "profilCV": "Architecte logiciel · Java/Spring Boot, Go, Kafka, Kubernetes · Architecture event-driven, DDD, microservices.",
        "anneePremEmploi": 2011, "mobilite": "International", "contrat": "Freelance / Mission",
        "slogan": "Architect for tomorrow, build for today.",
        "couleur": "#0D1117", "portfolioFichier": "style",
        "experiences": [
            {"entreprise": "Wave Mobile Money", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2022, 4, 1), "fin": None, "enCours": True, "description": "Architecture cible du backend (Go, gRPC, Kafka). Migration des monolithes legacy. Mentoring de 12 ingénieurs.", "poste": "Principal Software Architect", "missionClient": None},
            {"entreprise": "BNP Paribas (Paris)", "pays": "FRANCE", "ville": "Paris", "debut": date(2017, 1, 1), "fin": date(2022, 3, 31), "enCours": False, "description": "Architecte du programme paiement instantané SEPA. Conception architecture event-driven, conformité PSD2.", "poste": "Senior Software Architect", "missionClient": None},
            {"entreprise": "Capgemini", "pays": "FRANCE", "ville": "Paris", "debut": date(2011, 9, 1), "fin": date(2016, 12, 31), "enCours": False, "description": "Missions chez clients (Total, EDF, BNP). De développeur à tech lead.", "poste": "Tech Lead", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Ingénieur Génie Logiciel", "ecole": "Télécom ParisTech", "ville": "Paris", "pays": "FRANCE", "debut": date(2008, 9, 1), "fin": date(2011, 6, 30), "niveau": "Bac+5", "desc": "Spécialité Systèmes Distribués. Bourse Eiffel."},
            {"diplome": "Classes prépa MPSI/MP*", "ecole": "Lycée Henri-IV (Paris)", "ville": "Paris", "pays": "FRANCE", "debut": date(2005, 9, 1), "fin": date(2008, 6, 30), "niveau": "BAC +2", "desc": "Admise à Télécom ParisTech."},
        ],
        "competences": [("Java/Spring Boot", 5), ("Go", 4), ("Kafka", 5), ("Kubernetes", 5), ("AWS", 4), ("DDD", 5)],
        "langues":     [("Français", "C2"), ("Anglais", "C2"), ("Mandarin", "A2")],
        "interets":    ["Jeux de société", "Trekking", "Tech podcasts"],
        "projets": [
            {"titre": "SEPA Instant BNP", "contexte": "Mise en conformité PSD2 avec virements instantanés.", "realisation": "Architecture event-driven, déploiement zero-downtime, traitement de 8M tx/jour.", "url": "", "debut": date(2018, 9, 1), "fin": date(2020, 6, 30)},
            {"titre": "Refonte backend WAVE", "contexte": "Réduction de la latence p99 sous 100ms.", "realisation": "Migration vers Go + Kafka, sharding multi-régions. Objectif atteint en 9 mois.", "url": "", "debut": date(2022, 6, 1), "fin": date(2023, 3, 31)},
        ],
        "benevolats": [{"titre": "Mentor", "organisation": "Africa Code Week", "debut": date(2018, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/adjoua-tano"), ("github", "https://github.com/adjouatano"), ("googlechrome", "https://adjouatano.dev")],
    },
    {
        "prenom": "Eric", "nom": "N'GUESSAN", "sexe": "Homme",
        "email": "eric.nguessan@demo.test", "telephone": "+225 05 00 11 22 33",
        "naissance": date(1982, 6, 18), "nationalite": "Ivoirienne",
        "adresse": "Cocody Mermoz", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Médecin Généraliste",
        "secteur": "Santé & Pharmaceutique",
        "biographie": "Médecin généraliste depuis 12 ans, je consulte en cabinet privé et collabore avec l'hôpital de Cocody. Spécialiste de la médecine de famille et de la prévention.",
        "profilCV": "Médecin généraliste · 12 ans · CHU Cocody + cabinet privé · DU Diabétologie tropicale.",
        "anneePremEmploi": 2012, "mobilite": "Local", "contrat": "CDI",
        "slogan": "Soigner, écouter, accompagner.",
        "couleur": "#2563EB", "portfolioFichier": "orange-vibrant",
        "experiences": [
            {"entreprise": "Cabinet médical Mermoz", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2018, 1, 1), "fin": None, "enCours": True, "description": "Cabinet de médecine générale, ~25 patients/jour. Suivi pathologies chroniques, médecine préventive.", "poste": "Médecin généraliste libéral", "missionClient": None},
            {"entreprise": "CHU de Cocody", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2012, 11, 1), "fin": date(2017, 12, 31), "enCours": False, "description": "Médecin assistant au service de médecine générale. Encadrement d'internes.", "poste": "Médecin assistant", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Doctorat de Médecine", "ecole": "Faculté de Médecine d'Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2005, 9, 1), "fin": date(2012, 6, 30), "niveau": "BAC +7", "desc": "Thèse sur la prise en charge du diabète de type 2 en milieu rural. Mention Très Honorable."},
            {"diplome": "DU Diabétologie Tropicale", "ecole": "Université Paris-Saclay", "ville": "Paris", "pays": "FRANCE", "debut": date(2015, 9, 1), "fin": date(2016, 6, 30), "niveau": "BAC +6", "desc": "Diplôme universitaire complémentaire."},
        ],
        "competences": [("Médecine générale", 5), ("Diabétologie", 4), ("Urgences", 4), ("Pédagogie", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B1"), ("Baoulé", "C2")],
        "interets":    ["Course à pied", "Lecture", "Chorale"],
        "projets": [
            {"titre": "Campagne dépistage diabète", "contexte": "Sensibilisation dans 4 quartiers populaires d'Abidjan.", "realisation": "Coordination de 8 médecins, dépistage gratuit de 1200 personnes, suivi des cas positifs.", "url": "", "debut": date(2020, 11, 1), "fin": date(2021, 2, 28)},
            {"titre": "Thèse Diabète rural", "contexte": "Recherche-action en milieu rural Korhogo.", "realisation": "Étude sur 350 patients, publication dans Cahiers de Santé Tropicale 2013.", "url": "", "debut": date(2010, 9, 1), "fin": date(2012, 5, 31)},
        ],
        "benevolats": [{"titre": "Médecin bénévole", "organisation": "Médecins Sans Frontières CI", "debut": date(2013, 6, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/eric-nguessan"), ("googlechrome", "https://docteurnguessan.ci")],
    },
    {
        "prenom": "Sandra", "nom": "ABLE", "sexe": "Femme",
        "email": "sandra.able@demo.test", "telephone": "+225 07 12 13 14 15",
        "naissance": date(1989, 11, 3), "nationalite": "Ivoirienne",
        "adresse": "Plateau, Rue du Commerce", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Avocate d'Affaires",
        "secteur": "Services financiers",
        "biographie": "Avocate au Barreau d'Abidjan, spécialiste en droit des affaires et fusions-acquisitions. 8 ans en cabinet français et ivoirien.",
        "profilCV": "Avocate au Barreau d'Abidjan · Droit des affaires, M&A, droit OHADA · 8 ans en cabinet international.",
        "anneePremEmploi": 2016, "mobilite": "Régional", "contrat": "CDI",
        "slogan": "Stratégie. Rigueur. Discrétion.",
        "couleur": "#1a237e", "portfolioFichier": "snapfolio",
        "experiences": [
            {"entreprise": "Cabinet SCPA Avocats Plateau", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 1, 1), "fin": None, "enCours": True, "description": "Avocate associée. Dossiers M&A, restructuration, contentieux commercial. Portefeuille 25 clients.", "poste": "Avocate Associée", "missionClient": None},
            {"entreprise": "Gide Loyrette Nouel (Paris)", "pays": "FRANCE", "ville": "Paris", "debut": date(2016, 9, 1), "fin": date(2019, 12, 31), "enCours": False, "description": "Avocate collaboratrice — département M&A Africa. Missions en Côte d'Ivoire, Sénégal, Cameroun.", "poste": "Avocate Collaboratrice", "missionClient": None},
        ],
        "formations": [
            {"diplome": "CAPA (Avocat)", "ecole": "EFB - École de Formation du Barreau (Paris)", "ville": "Paris", "pays": "FRANCE", "debut": date(2014, 9, 1), "fin": date(2016, 6, 30), "niveau": "Bac+5", "desc": "Major 2016. Stage final Gide."},
            {"diplome": "Master 2 Droit des Affaires", "ecole": "Université Paris-Panthéon-Assas", "ville": "Paris", "pays": "FRANCE", "debut": date(2013, 9, 1), "fin": date(2014, 6, 30), "niveau": "BAC +5", "desc": "Mention Bien. Spécialité M&A."},
        ],
        "competences": [("Droit OHADA", 5), ("M&A", 5), ("Rédaction contrats", 5), ("Négociation", 5), ("Anglais juridique", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "C1"), ("Allemand", "B1")],
        "interets":    ["Opéra", "Tennis", "Cuisine française"],
        "projets": [
            {"titre": "M&A Acquisition COSMIVOIRE", "contexte": "Cession à un groupe européen, 80M€.", "realisation": "Conseil vendeur, négociation, closing en 6 mois. Pas de litige post-closing.", "url": "", "debut": date(2021, 6, 1), "fin": date(2021, 12, 31)},
            {"titre": "Restructuration groupe BTP", "contexte": "Restructuration fiscale et juridique d'un groupe de 7 sociétés.", "realisation": "Réorganisation menée en 12 mois. Économie annuelle 1.2M€.", "url": "", "debut": date(2020, 1, 1), "fin": date(2021, 1, 31)},
        ],
        "benevolats": [{"titre": "Permanences juridiques", "organisation": "Maison de la Justice Abobo", "debut": date(2020, 9, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/sandra-able"), ("googlechrome", "https://sandra-able.law")],
    },
    {
        "prenom": "Olivier", "nom": "DJEDJE", "sexe": "Homme",
        "email": "olivier.djedje@demo.test", "telephone": "+225 05 16 17 18 19",
        "naissance": date(1983, 4, 24), "nationalite": "Ivoirienne",
        "adresse": "San-Pédro, Quartier Cité", "ville": "Daloa", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Géologue Senior",
        "secteur": "Ressources minières et hydrocarbures",
        "biographie": "Géologue avec 11 ans dans l'exploration pétrolière et minière. Expertise sur les bassins sédimentaires d'Afrique de l'Ouest. Doctorat en géologie pétrolière.",
        "profilCV": "Géologue senior · Exploration offshore West Africa · Petrel, Kingdom, ArcGIS · Doctorat.",
        "anneePremEmploi": 2013, "mobilite": "International", "contrat": "CDI",
        "slogan": "Reading the language of the Earth.",
        "couleur": "#0D1F3C", "portfolioFichier": "style",
        "experiences": [
            {"entreprise": "PETROCI Holding", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 3, 1), "fin": None, "enCours": True, "description": "Géologue senior exploration. Interprétation sismique 3D bassin ivoirien. Coordination avec partenaires Tullow, Foxtrot.", "poste": "Géologue Senior", "missionClient": None},
            {"entreprise": "Schlumberger (Aberdeen)", "pays": "FRANCE", "ville": "Paris", "debut": date(2013, 9, 1), "fin": date(2019, 2, 28), "enCours": False, "description": "Consultant exploration pour clients West Africa, North Sea. Missions terrain 3 mois/an.", "poste": "Senior Geologist Consultant", "missionClient": {"client": "Tullow Oil", "ville": "Paris", "pays": "FRANCE", "debut": date(2017, 6, 1), "fin": date(2018, 5, 31), "desc": "Réinterprétation sismique du bloc CI-103 ivoirien."}},
        ],
        "formations": [
            {"diplome": "Doctorat de Géologie Pétrolière", "ecole": "Université de Strasbourg", "ville": "Paris", "pays": "FRANCE", "debut": date(2010, 9, 1), "fin": date(2013, 6, 30), "niveau": "BAC +7", "desc": "Thèse sur les systèmes pétroliers du bassin sédimentaire ivoirien. Mention Très Honorable avec félicitations."},
            {"diplome": "Master Géologie", "ecole": "INPHB Yamoussoukro", "ville": "Yamoussoukro", "pays": "COTE D'IVOIRE", "debut": date(2008, 9, 1), "fin": date(2010, 6, 30), "niveau": "Bac+5", "desc": "Spécialité Géologie Pétrolière."},
        ],
        "competences": [("Petrel", 5), ("Kingdom", 5), ("Sismique", 5), ("ArcGIS", 4), ("Anglais technique", 5)],
        "langues":     [("Français", "C2"), ("Anglais", "C1"), ("Bété", "C2")],
        "interets":    ["Spéléologie", "Photographie nature", "Course"],
        "projets": [
            {"titre": "Découverte gisement CI-103", "contexte": "Première découverte commerciale du bassin offshore profond ivoirien depuis 10 ans.", "realisation": "Interprétation 3D, identification du prospect, supervision du forage. Test positif en 2022.", "url": "", "debut": date(2020, 1, 1), "fin": date(2022, 9, 30)},
            {"titre": "Thèse Doctorale", "contexte": "Modélisation des systèmes pétroliers bassin ivoirien.", "realisation": "3 ans de recherche, 4 publications scientifiques, prix de la meilleure thèse 2013 (SGAFI).", "url": "", "debut": date(2010, 9, 1), "fin": date(2013, 5, 31)},
        ],
        "benevolats": [{"titre": "Conférencier", "organisation": "Société Géologique Afrique de l'Ouest", "debut": date(2015, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/olivier-djedje"), ("googlechrome", "https://oliverdjedje.science")],
    },

    # ── 16 ── PROMAN ──────────────────────────────────────────────────────────
    {
        "prenom": "Ibrahim", "nom": "COULIBALY", "sexe": "Homme",
        "email": "ibrahim.coulibaly@demo.test", "telephone": "+225 07 55 66 77 88",
        "naissance": date(1989, 6, 14), "nationalite": "Ivoirienne",
        "adresse": "Yopougon Selmer", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Ingénieur Génie Civil BTP",
        "secteur": "BTP & Génie Civil",
        "biographie": "Ingénieur génie civil avec 10 ans d'expérience dans la construction d'infrastructures routières et de bâtiments industriels en Afrique de l'Ouest. Expert en supervision de chantier et gestion de projets multimillionnaires.",
        "profilCV": "Ingénieur GC · 10 ans BTP · AutoCAD Civil 3D, ROBOT Structural, MS Project · Chantiers routiers et industriels.",
        "anneePremEmploi": 2014, "mobilite": "International", "contrat": "CDI",
        "slogan": "Bâtir l'Afrique, une structure à la fois.",
        "couleur": "#c96010", "portfolioFichier": "proman",
        "experiences": [
            {"entreprise": "Bouygues Travaux Publics CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 2, 1), "fin": None, "enCours": True, "description": "Supervision de la construction de 45 km d'autoroute Abidjan–Grand-Bassam. Coordination de 120 ouvriers et sous-traitants. Respect du planning et du budget de 28 M€.", "poste": "Ingénieur Travaux Senior", "missionClient": None},
            {"entreprise": "SOGEA-SATOM", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2014, 8, 1), "fin": date(2019, 1, 31), "enCours": False, "description": "Suivi de travaux de réhabilitation de routes en terre dans le nord du pays. Rapports d'avancement, contrôle qualité et sécurité chantier.", "poste": "Ingénieur Travaux", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master Génie Civil", "ecole": "INPHB Yamoussoukro", "ville": "Yamoussoukro", "pays": "COTE D'IVOIRE", "debut": date(2012, 9, 1), "fin": date(2014, 6, 30), "niveau": "Bac+5", "desc": "Spécialité Structures et Infrastructures. Projet de fin d'études : dimensionnement d'un pont mixte."},
            {"diplome": "Licence Génie Civil", "ecole": "Université FHB", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2009, 9, 1), "fin": date(2012, 6, 30), "niveau": "BAC +3", "desc": "Mention Bien."},
        ],
        "competences": [("AutoCAD Civil 3D", 5), ("ROBOT Structural", 4), ("MS Project", 5), ("Topographie", 4), ("Béton armé", 5)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Dioula", "C1")],
        "interets":    ["Maquettes architecture", "Football", "Montagne"],
        "projets": [
            {"titre": "Autoroute Abidjan–Grand-Bassam", "contexte": "Infrastructure clé du projet de développement du corridor sud ivoirien.", "realisation": "45 km livrés en 30 mois. 0 accident grave. Économie de 1.2M€ sur les coûts de matériaux.", "url": "", "debut": date(2019, 2, 1), "fin": date(2021, 8, 31)},
            {"titre": "Réhabilitation RN5 (Côte d'Ivoire)", "contexte": "340 km de route en terre nord-ivoirien, financement Banque Mondiale.", "realisation": "Travaux livrés avec 2 mois d'avance. Rapport de conformité validé sans réserve.", "url": "", "debut": date(2015, 3, 1), "fin": date(2018, 9, 30)},
        ],
        "benevolats": [{"titre": "Encadrant technique", "organisation": "Habitat pour l'Humanité CI", "debut": date(2016, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/ibrahim-coulibaly-gc"), ("github", "https://github.com/ibrahimcoul")],
    },

    # ── 17 ── PROMAN-PRO ──────────────────────────────────────────────────────
    {
        "prenom": "Grace", "nom": "ASSOUMOU", "sexe": "Femme",
        "email": "grace.assoumou@demo.test", "telephone": "+225 07 44 55 66 77",
        "naissance": date(1993, 9, 3), "nationalite": "Ivoirienne",
        "adresse": "Cocody Riviera 2", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Responsable Marketing Digital",
        "secteur": "Communication & Marketing",
        "biographie": "Spécialiste marketing digital avec 7 ans d'expérience en Afrique francophone. Experte en stratégie de contenu, campagnes social media et growth hacking. Passionnée par les marques locales qui rayonnent sur le continent.",
        "profilCV": "Marketing Digital · 7 ans · Meta Ads, Google Ads, SEO, CRM HubSpot · Stratégie de croissance Afrique.",
        "anneePremEmploi": 2017, "mobilite": "National", "contrat": "CDI",
        "slogan": "Your brand, amplified.",
        "couleur": "#6244C5", "portfolioFichier": "proman-pro",
        "experiences": [
            {"entreprise": "Jumia Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2021, 1, 1), "fin": None, "enCours": True, "description": "Direction de la stratégie marketing digital. Gestion d'un budget pub de 400K€/an. +35% de trafic organique en 18 mois. Animation d'une équipe de 6 personnes.", "poste": "Head of Digital Marketing", "missionClient": None},
            {"entreprise": "Ivoire Buzz (Agence)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2017, 6, 1), "fin": date(2020, 12, 31), "enCours": False, "description": "Gestion des comptes réseaux sociaux de 15 marques ivoiriennes. Production de contenu, influenceurs, reporting mensuel.", "poste": "Chargée de Communication Digitale", "missionClient": None},
        ],
        "formations": [
            {"diplome": "MBA Marketing Digital", "ecole": "ESCA Casablanca", "ville": "Casablanca", "pays": "MAROC", "debut": date(2015, 9, 1), "fin": date(2017, 6, 30), "niveau": "Bac+5", "desc": "Spécialité Brand Management & Growth Hacking. Exchange semester HEC Paris."},
            {"diplome": "Licence Communication", "ecole": "ISTC Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2012, 9, 1), "fin": date(2015, 6, 30), "niveau": "BAC +3", "desc": "Mention Très Bien."},
        ],
        "competences": [("Meta Ads", 5), ("Google Ads", 5), ("SEO", 4), ("HubSpot CRM", 4), ("Canva/Adobe", 4), ("Data Analytics", 3)],
        "langues":     [("Français", "C2"), ("Anglais", "C1"), ("Bété", "B2")],
        "interets":    ["Mode africaine", "Podcasting", "Voyages"],
        "projets": [
            {"titre": "Campagne Jumia Black Friday 2023", "contexte": "Objectif : doubler les ventes en 72h vs 2022.", "realisation": "Stratégie cross-canal (email, SMS, social, influenceurs). +128% de CA, meilleure performance Jumia CI.", "url": "", "debut": date(2023, 10, 1), "fin": date(2023, 11, 30)},
            {"titre": "Lancement marque Zaka Foods", "contexte": "Startup food locale cherchant visibilité nationale.", "realisation": "Identité digitale, 50k abonnés en 4 mois, couverture médias nationaux.", "url": "", "debut": date(2019, 6, 1), "fin": date(2019, 12, 31)},
        ],
        "benevolats": [{"titre": "Mentor startup", "organisation": "Orange Fab CI", "debut": date(2021, 3, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/grace-assoumou"), ("instagram", "https://instagram.com/gracemarketing.ci"), ("x", "https://x.com/GraceAssoumou")],
    },

    # ── 18 ── PROMAN-GLASS ────────────────────────────────────────────────────
    {
        "prenom": "Kwame", "nom": "MENSAH", "sexe": "Homme",
        "email": "kwame.mensah@demo.test", "telephone": "+225 05 77 88 99 00",
        "naissance": date(1991, 12, 7), "nationalite": "Ghanéenne",
        "adresse": "Treichville, Avenue 14", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Data Scientist / IA",
        "secteur": "Numérique (Tech)",
        "biographie": "Data Scientist avec 8 ans d'expérience dans la modélisation prédictive et le machine learning appliqués à la finance, la santé et l'agriculture. Profil bilingue anglais/français, habitué aux environnements multiculturels.",
        "profilCV": "Data Scientist · Python, TensorFlow, Spark · MLOps · 8 ans Afrique & Europe · Publications NeurIPS 2022.",
        "anneePremEmploi": 2016, "mobilite": "International", "contrat": "CDI",
        "slogan": "Turning data into decisions.",
        "couleur": "#a78bfa", "portfolioFichier": "proman-glass",
        "experiences": [
            {"entreprise": "Ecobank Transnational", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 7, 1), "fin": None, "enCours": True, "description": "Lead Data Scientist pour les 33 pays du groupe. Modèles de scoring crédit, détection de fraude temps réel (+40% précision), recommandations produits.", "poste": "Lead Data Scientist", "missionClient": None},
            {"entreprise": "iHub Nairobi / BRCK", "pays": "KENYA", "ville": "Nairobi", "debut": date(2016, 5, 1), "fin": date(2020, 6, 30), "enCours": False, "description": "Modèles prédictifs agricoles (rendements, météo) pour 8 000 agriculteurs kényans. Déploiement mobile sur réseau bas débit.", "poste": "Machine Learning Engineer", "missionClient": None},
        ],
        "formations": [
            {"diplome": "MSc Artificial Intelligence", "ecole": "University of Edinburgh", "ville": "Edinburgh", "pays": "ROYAUME-UNI", "debut": date(2014, 9, 1), "fin": date(2016, 6, 30), "niveau": "Bac+5", "desc": "Distinction. Thèse sur les réseaux de neurones pour la prédiction de rendements agricoles en Afrique sub-saharienne."},
            {"diplome": "BSc Computer Science", "ecole": "University of Ghana (Legon)", "ville": "Accra", "pays": "GHANA", "debut": date(2010, 9, 1), "fin": date(2014, 6, 30), "niveau": "BAC +3", "desc": "First Class Honours."},
        ],
        "competences": [("Python", 5), ("TensorFlow", 5), ("Spark", 4), ("SQL", 5), ("MLOps", 4), ("R", 3)],
        "langues":     [("Anglais", "C2"), ("Français", "C1"), ("Twi", "C2")],
        "interets":    ["Basketball", "Open Data Africa", "Jazz"],
        "projets": [
            {"titre": "Système détection fraude Ecobank", "contexte": "Fraude carte coûtait 12M$/an au groupe.", "realisation": "Modèle XGBoost + règles métier. Réduction fraude de 43%. ROI : 8M$ économisés dès la 1re année.", "url": "", "debut": date(2021, 1, 1), "fin": date(2021, 9, 30)},
            {"titre": "Publication NeurIPS 2022", "contexte": "Recherche sur les modèles de prédiction météo pour l'agriculture africaine.", "realisation": "Accepted paper NeurIPS 2022 — ML for Developing World workshop. 180 citations.", "url": "https://arxiv.org/abs/2210.demo", "debut": date(2022, 1, 1), "fin": date(2022, 11, 30)},
        ],
        "benevolats": [{"titre": "Mentor Data Science", "organisation": "Data Science Africa", "debut": date(2018, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/kwame-mensah-ds"), ("github", "https://github.com/kwamemensah"), ("x", "https://x.com/kwame_data")],
    },

    # ── 19 ── CLINIC-PRO ──────────────────────────────────────────────────────
    {
        "prenom": "Fatimata", "nom": "OUÉDRAOGO", "sexe": "Femme",
        "email": "fatimata.ouedraogo@demo.test", "telephone": "+225 07 33 44 55 66",
        "naissance": date(1987, 3, 22), "nationalite": "Burkinabé",
        "adresse": "Adjamé Liberté", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Médecin Généraliste / Santé Publique",
        "secteur": "Santé",
        "biographie": "Médecin généraliste avec 12 ans d'expérience clinique et en santé communautaire en Afrique de l'Ouest. Spécialisée en maladies tropicales et nutrition. Coordinatrice de programmes de santé maternelle et infantile.",
        "profilCV": "Médecin Généraliste · Santé Publique · 12 ans · Maladies tropicales, nutrition, SMI · OMS, MSF.",
        "anneePremEmploi": 2012, "mobilite": "International", "contrat": "CDI",
        "slogan": "Soigner, prévenir, éduquer.",
        "couleur": "#0d6efd", "portfolioFichier": "clinic-pro",
        "experiences": [
            {"entreprise": "MSF (Médecins Sans Frontières)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2018, 6, 1), "fin": None, "enCours": True, "description": "Coordinatrice médicale pour le programme paludisme et malnutrition dans l'ouest de la Côte d'Ivoire. Gestion d'équipe de 25 agents de santé.", "poste": "Coordinatrice Médicale", "missionClient": None},
            {"entreprise": "CHU de Treichville", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2012, 11, 1), "fin": date(2018, 5, 31), "enCours": False, "description": "Médecin généraliste en consultation externe et urgences. Participation aux campagnes de vaccination nationale.", "poste": "Médecin Généraliste", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Doctorat en Médecine (MD)", "ecole": "Université de Ouagadougou", "ville": "Ouagadougou", "pays": "BURKINA FASO", "debut": date(2006, 9, 1), "fin": date(2012, 6, 30), "niveau": "BAC +7", "desc": "Thèse sur la prise en charge de la malnutrition aiguë sévère en contexte sahélien."},
            {"diplome": "DU Santé Tropicale", "ecole": "Institut Pasteur Paris", "ville": "Paris", "pays": "FRANCE", "debut": date(2015, 9, 1), "fin": date(2016, 6, 30), "niveau": "Bac+5", "desc": "Maladies vectorielles et parasitoses tropicales."},
        ],
        "competences": [("Médecine générale", 5), ("Maladies tropicales", 5), ("Santé publique", 5), ("Nutrition", 4), ("Gestion de projet humanitaire", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "C1"), ("Mooré", "C2"), ("Dioula", "B2")],
        "interets":    ["Jardinage", "Littérature africaine", "Randonnée"],
        "projets": [
            {"titre": "Programme SMART nutrition Ouest-CI", "contexte": "Malnutrition aiguë sévère chez enfants <5 ans dans 3 districts.", "realisation": "3 200 enfants pris en charge. Taux guérison 89% vs standard OMS 75%. Programme étendu à 2 districts supplémentaires.", "url": "", "debut": date(2020, 1, 1), "fin": date(2022, 12, 31)},
            {"titre": "Campagne vaccination COVID-19 CI", "contexte": "Coordination logistique vaccination dans les camps de réfugiés.", "realisation": "12 500 doses administrées en 4 semaines. 0 incident grave.", "url": "", "debut": date(2021, 6, 1), "fin": date(2021, 10, 31)},
        ],
        "benevolats": [{"titre": "Consultante médicale bénévole", "organisation": "Plan International CI", "debut": date(2016, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/fatimata-ouedraogo-md"), ("googlechrome", "https://fatimatamed.org")],
    },

    # ── 20 ── CYBER-NEON ──────────────────────────────────────────────────────
    {
        "prenom": "Jean-Marc", "nom": "AHUI", "sexe": "Homme",
        "email": "jeanmarc.ahui@demo.test", "telephone": "+225 05 12 34 56 78",
        "naissance": date(1994, 5, 19), "nationalite": "Ivoirienne",
        "adresse": "Cocody 2 Plateaux", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Expert Cybersécurité",
        "secteur": "Numérique (Tech)",
        "biographie": "Expert cybersécurité certifié (CEH, OSCP) avec 7 ans d'expérience en pentest, SOC et réponse à incidents. Spécialiste de la sécurité des systèmes bancaires africains. Bug bounty hunter passionné.",
        "profilCV": "Cybersécurité · Pentest · SOC · OSCP, CEH, CISSP · 7 ans · Banques & Télécoms CI.",
        "anneePremEmploi": 2017, "mobilite": "International", "contrat": "CDI",
        "slogan": "Attack to defend. Defend to protect.",
        "couleur": "#00ff88", "portfolioFichier": "cyber-neon",
        "experiences": [
            {"entreprise": "Bridge Bank Group CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2021, 3, 1), "fin": None, "enCours": True, "description": "Responsable SOC (Security Operations Center). Supervision des alertes SIEM, réponse aux incidents, tests d'intrusion bi-annuels. Réduction des incidents critiques de 70%.", "poste": "Cybersecurity Lead / SOC Manager", "missionClient": None},
            {"entreprise": "ANSSI Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2017, 9, 1), "fin": date(2021, 2, 28), "enCours": False, "description": "Analyste cybersécurité gouvernemental. Audits de sécurité des SI ministériels, formation des agents publics.", "poste": "Analyste Cybersécurité", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master Sécurité Informatique", "ecole": "INPHB Yamoussoukro", "ville": "Yamoussoukro", "pays": "COTE D'IVOIRE", "debut": date(2015, 9, 1), "fin": date(2017, 6, 30), "niveau": "Bac+5", "desc": "Spécialité Cryptographie et Sécurité des Réseaux."},
            {"diplome": "Licence Réseaux & Télécoms", "ecole": "Université FHB", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2012, 9, 1), "fin": date(2015, 6, 30), "niveau": "BAC +3", "desc": "Major de promotion."},
        ],
        "competences": [("Pentest", 5), ("SIEM/SOC", 5), ("Kali Linux", 5), ("Python sécurité", 4), ("Forensics", 4), ("Cloud Security", 3)],
        "langues":     [("Français", "C2"), ("Anglais", "C1"), ("Abouré", "C2")],
        "interets":    ["CTF (Capture The Flag)", "Électronique", "Jeux vidéo"],
        "projets": [
            {"titre": "Pentest infrastructure Bridge Bank", "contexte": "Audit annuel de sécurité réglementaire (CREPMF).", "realisation": "32 vulnérabilités identifiées, 28 corrigées en 3 mois. 0 incident depuis l'audit.", "url": "", "debut": date(2023, 1, 1), "fin": date(2023, 3, 31)},
            {"titre": "CTF HackTheBox Africa Top 10", "contexte": "Compétition CTF internationale, classement Afrique.", "realisation": "Top 8 Afrique 2022. Résolution de 45 challenges en catégories Web, Reverse, Crypto.", "url": "https://hackthebox.com/profile/jm-ahui", "debut": date(2022, 1, 1), "fin": date(2022, 12, 31)},
        ],
        "benevolats": [{"titre": "Formateur cybersécurité", "organisation": "CIV-CERT (CERT National CI)", "debut": date(2019, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/jeanmarc-ahui"), ("github", "https://github.com/jmahui-sec"), ("x", "https://x.com/jmahui_sec")],
    },

    # ── 21 ── RETRO-MAG ───────────────────────────────────────────────────────
    {
        "prenom": "Chantal", "nom": "BOGUI", "sexe": "Femme",
        "email": "chantal.bogui@demo.test", "telephone": "+225 07 98 76 54 32",
        "naissance": date(1986, 11, 30), "nationalite": "Ivoirienne",
        "adresse": "Cocody Danga", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Journaliste / Rédactrice en Chef",
        "secteur": "Médias & Journalisme",
        "biographie": "Journaliste avec 15 ans d'expérience dans la presse écrite et numérique en Afrique de l'Ouest. Spécialiste des sujets économiques et politiques ivoiriens. Ancienne correspondante pour RFI et Le Monde Afrique.",
        "profilCV": "Journaliste senior · Presse écrite & digitale · 15 ans · Économie Afrique · RFI, Le Monde Afrique, Jeune Afrique.",
        "anneePremEmploi": 2009, "mobilite": "International", "contrat": "Freelance",
        "slogan": "L'information au service de l'Afrique.",
        "couleur": "#c0392b", "portfolioFichier": "retro-mag",
        "experiences": [
            {"entreprise": "Jeune Afrique Médias", "pays": "FRANCE", "ville": "Paris", "debut": date(2018, 4, 1), "fin": None, "enCours": True, "description": "Rédactrice en chef adjointe pour l'édition Afrique de l'Ouest. Coordination d'une équipe de 8 journalistes. Dossiers spéciaux sur l'économie ivoirienne et la Côte d'Ivoire numérique.", "poste": "Rédactrice en Chef Adjointe", "missionClient": None},
            {"entreprise": "RFI (Radio France Internationale)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2009, 6, 1), "fin": date(2018, 3, 31), "enCours": False, "description": "Correspondante permanente depuis Abidjan. Couverture de l'élection présidentielle 2010, crise post-électorale 2011, CAN 2012 et 2023.", "poste": "Correspondante Permanente", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master Journalisme", "ecole": "CFPJ Paris", "ville": "Paris", "pays": "FRANCE", "debut": date(2007, 9, 1), "fin": date(2009, 6, 30), "niveau": "Bac+5", "desc": "Spécialité Journalisme international et presse économique."},
            {"diplome": "Licence Lettres Modernes", "ecole": "Université Cocody", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2004, 9, 1), "fin": date(2007, 6, 30), "niveau": "BAC +3", "desc": "Mention Bien. Prix du meilleur mémoire de Licence."},
        ],
        "competences": [("Rédaction", 5), ("Investigation", 5), ("SEO éditorial", 4), ("Montage vidéo", 3), ("Réseaux sociaux", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "C1"), ("Baoulé", "B2")],
        "interets":    ["Littérature africaine", "Cinéma", "Voyages culturels"],
        "projets": [
            {"titre": "Série enquête 'L'or vert ivoirien'", "contexte": "Investigation sur la filière cacao, corruption et prix plancher.", "realisation": "Série de 8 articles — 2M de vues, prix Grand Prix Journalisme Économique Afrique 2022.", "url": "https://jeuneafrique.com/or-vert-ci", "debut": date(2022, 3, 1), "fin": date(2022, 6, 30)},
            {"titre": "Couverture crise post-électorale CI 2010-11", "contexte": "Terrain pendant 4 mois en zone de conflit.", "realisation": "400 articles, 12 reportages radio, 3 documentaires. Référence journalistique internationale sur la période.", "url": "", "debut": date(2010, 11, 1), "fin": date(2011, 4, 30)},
        ],
        "benevolats": [{"titre": "Formatrice presse", "organisation": "Reporters Sans Frontières CI", "debut": date(2015, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/chantal-bogui"), ("x", "https://x.com/chantalinfo"), ("googlechrome", "https://chantalbogui.press")],
    },

    # ── 22 ── TECH-DASHBOARD ──────────────────────────────────────────────────
    {
        "prenom": "Sékou", "nom": "CAMARA", "sexe": "Homme",
        "email": "sekou.camara@demo.test", "telephone": "+225 05 24 68 13 57",
        "naissance": date(1990, 8, 11), "nationalite": "Guinéenne",
        "adresse": "Marcory Zone 4", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Chef de Projet IT / Scrum Master",
        "secteur": "Numérique (Tech)",
        "biographie": "Chef de projet IT certifié PMP et Scrum Master avec 10 ans d'expérience dans la livraison de projets de transformation numérique pour des institutions financières et gouvernementales africaines. Maîtrise des méthodologies agile et cycle en V.",
        "profilCV": "Chef de Projet IT · PMP · Scrum Master · 10 ans · JIRA, Confluence, SAFe · Transformation digitale Afrique.",
        "anneePremEmploi": 2014, "mobilite": "International", "contrat": "CDI",
        "slogan": "Deliver. Iterate. Succeed.",
        "couleur": "#6366f1", "portfolioFichier": "tech-dashboard",
        "experiences": [
            {"entreprise": "NSIA Banque CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 10, 1), "fin": None, "enCours": True, "description": "Pilotage du programme de transformation digitale (15 projets simultanés, budget 6M€). Migration core banking TEMENOS. Delivery en mode SAFe agile.", "poste": "Programme Manager Digital", "missionClient": None},
            {"entreprise": "Capgemini Afrique (Sénégal)", "pays": "SENEGAL", "ville": "Dakar", "debut": date(2014, 9, 1), "fin": date(2020, 9, 30), "enCours": False, "description": "Chef de projet pour clients telcos et banques (Orange, SGBS, BICIS). Méthodologie cycle en V et agile. 12 projets livrés, 0 dérapage budget.", "poste": "Chef de Projet Senior", "missionClient": {"client": "Orange Sénégal", "ville": "Dakar", "pays": "SENEGAL", "debut": date(2018, 1, 1), "fin": date(2019, 12, 31), "desc": "Refonte SI facturation — 3M abortissants, livré en 11 mois."}},
        ],
        "formations": [
            {"diplome": "Master Systèmes d'Information", "ecole": "École Supérieure Polytechnique (Dakar)", "ville": "Dakar", "pays": "SENEGAL", "debut": date(2012, 9, 1), "fin": date(2014, 6, 30), "niveau": "Bac+5", "desc": "Spécialité Gestion de Projets IT. Major."},
            {"diplome": "Licence Informatique", "ecole": "Université Gamal Abdel Nasser", "ville": "Conakry", "pays": "GUINEE", "debut": date(2009, 9, 1), "fin": date(2012, 6, 30), "niveau": "BAC +3", "desc": "Mention Très Bien."},
        ],
        "competences": [("JIRA/Confluence", 5), ("SAFe Agile", 5), ("MS Project", 4), ("Risk Management", 4), ("TEMENOS", 3), ("SQL", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "C1"), ("Soussou", "C2"), ("Malinké", "B2")],
        "interets":    ["Échecs", "Running", "Fintech africaine"],
        "projets": [
            {"titre": "Programme Digital NSIA Banque", "contexte": "Transformation digitale de la 2e banque ivoirienne.", "realisation": "15 projets livrés sur 3 ans. Migration TEMENOS T24 sans interruption de service. ROI évalué à 4.5x.", "url": "", "debut": date(2020, 10, 1), "fin": date(2023, 9, 30)},
            {"titre": "Refonte SI facturation Orange SN", "contexte": "Modernisation du système de facturation pour 3M clients.", "realisation": "Livré en 11 mois (prévu 14). Budget respecté. 99.97% de disponibilité post-go live.", "url": "", "debut": date(2018, 1, 1), "fin": date(2019, 12, 31)},
        ],
        "benevolats": [{"titre": "Mentor projets digitaux", "organisation": "CTIC Dakar / Incubateur", "debut": date(2017, 6, 1), "fin": date(2020, 9, 30), "enCours": False}],
        "liens": [("linkedin", "https://www.linkedin.com/in/sekou-camara-pmp"), ("github", "https://github.com/sekoucamara"), ("x", "https://x.com/sekou_pm")],
    },

    # ── 23 ── SNAPFOLIO ───────────────────────────────────────────────────────
    {
        "prenom": "Koffi", "nom": "ASSOUMAN", "sexe": "Homme",
        "email": "koffi.assouman@demo.test", "telephone": "+225 07 11 22 33 44",
        "naissance": date(1996, 4, 15), "nationalite": "Ivoirienne",
        "adresse": "Cocody Angré 7e Tranche", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Développeur Full Stack",
        "secteur": "Numérique (Tech)",
        "biographie": "Développeur full stack de 28 ans spécialisé React, Django et Flutter. 4 ans d'expérience sur des projets SaaS africains. Passionné par les solutions tech qui résolvent les problèmes locaux.",
        "profilCV": "Full Stack Dev · React · Django · Flutter · 4 ans · SaaS Afrique.",
        "anneePremEmploi": 2020, "mobilite": "National", "contrat": "CDI",
        "slogan": "Build fast. Ship smart.",
        "couleur": "#f59e0b", "portfolioFichier": "snapfolio",
        "experiences": [
            {"entreprise": "Bizao (Fintech CI)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2022, 3, 1), "fin": None, "enCours": True, "description": "Développement et maintenance de l'API d'agrégation de paiements mobiles (Orange Money, MTN, Wave). Stack : Django REST + React + PostgreSQL.", "poste": "Développeur Backend Senior", "missionClient": None},
            {"entreprise": "Freelance", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 6, 1), "fin": date(2022, 2, 28), "enCours": False, "description": "Développement d'applications mobiles Flutter pour PME ivoiriennes (gestion stocks, caisse, livraison).", "poste": "Développeur Flutter Freelance", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Licence Informatique", "ecole": "INPHB Yamoussoukro", "ville": "Yamoussoukro", "pays": "COTE D'IVOIRE", "debut": date(2016, 9, 1), "fin": date(2020, 6, 30), "niveau": "BAC +3", "desc": "Spécialité Génie Logiciel. Major de promotion."},
        ],
        "competences": [("React", 5), ("Django", 5), ("Flutter", 4), ("PostgreSQL", 4), ("Docker", 3), ("Git", 5)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Agni", "C1")],
        "interets":    ["Open source", "Gaming", "IA générative"],
        "projets": [
            {"titre": "API Paiement Mobile Bizao v3", "contexte": "Refonte de l'API pour supporter 8 pays UEMOA.", "realisation": "Latence réduite de 340ms à 80ms. 99.9% uptime sur 6 mois.", "url": "", "debut": date(2023, 1, 1), "fin": date(2023, 6, 30)},
        ],
        "benevolats": [{"titre": "Formateur code", "organisation": "Coding for Africa CI", "debut": date(2021, 9, 1), "fin": None, "enCours": True}],
        "liens": [("github", "https://github.com/koffi-assouman"), ("linkedin", "https://linkedin.com/in/koffi-assouman")],
    },

    # ── 24 ── PROMAN ──────────────────────────────────────────────────────────
    {
        "prenom": "Mariam", "nom": "KOUYATÉ", "sexe": "Femme",
        "email": "mariam.kouyate@demo.test", "telephone": "+225 05 88 77 66 55",
        "naissance": date(1988, 7, 22), "nationalite": "Guinéenne",
        "adresse": "Plateau Centre", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Directrice des Ressources Humaines",
        "secteur": "Ressources Humaines",
        "biographie": "DRH avec 12 ans d'expérience dans les secteurs bancaire et industriel en Afrique de l'Ouest. Spécialisée en gestion des talents, transformation organisationnelle et droit social ivoirien.",
        "profilCV": "DRH · 12 ans · GPEC, droit social, talent management · Banque & Industrie CI.",
        "anneePremEmploi": 2012, "mobilite": "National", "contrat": "CDI",
        "slogan": "Les hommes sont le moteur de toute organisation.",
        "couleur": "#0f766e", "portfolioFichier": "proman",
        "experiences": [
            {"entreprise": "CFAO Motors CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 5, 1), "fin": None, "enCours": True, "description": "Directrice RH d'un effectif de 380 employés. Mise en place du SIRH, refonte de la politique de rémunération, gestion des IRP.", "poste": "Directrice des Ressources Humaines", "missionClient": None},
            {"entreprise": "Banque Atlantique CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2012, 9, 1), "fin": date(2019, 4, 30), "enCours": False, "description": "Gestion du recrutement, formation et développement des compétences pour 220 collaborateurs.", "poste": "Responsable RH", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master Management RH", "ecole": "CESAG Dakar", "ville": "Dakar", "pays": "SENEGAL", "debut": date(2010, 9, 1), "fin": date(2012, 6, 30), "niveau": "Bac+5", "desc": "Spécialité Gestion des Talents et Relations Sociales."},
            {"diplome": "Licence Droit du Travail", "ecole": "Université de Conakry", "ville": "Conakry", "pays": "GUINEE", "debut": date(2007, 9, 1), "fin": date(2010, 6, 30), "niveau": "BAC +3", "desc": "Mention Bien."},
        ],
        "competences": [("GPEC", 5), ("Recrutement", 5), ("Droit social CI", 5), ("SAP HR", 4), ("Paie", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Soussou", "C2"), ("Malinké", "C1")],
        "interets":    ["Coaching professionnel", "Lecture", "Yoga"],
        "projets": [
            {"titre": "Déploiement SIRH CFAO", "contexte": "Modernisation de la gestion RH d'un groupe multi-filiales.", "realisation": "SIRH SAP déployé en 8 mois. Réduction de 60% du temps de traitement paie.", "url": "", "debut": date(2020, 1, 1), "fin": date(2020, 8, 31)},
        ],
        "benevolats": [{"titre": "Mentor RH", "organisation": "Women in Tech CI", "debut": date(2020, 3, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://linkedin.com/in/mariam-kouyate-drh")],
    },

    # ── 25 ── STYLE ───────────────────────────────────────────────────────────
    {
        "prenom": "Abdou", "nom": "THIAW", "sexe": "Homme",
        "email": "abdou.thiaw@demo.test", "telephone": "+225 07 44 33 22 11",
        "naissance": date(1985, 11, 8), "nationalite": "Sénégalaise",
        "adresse": "Plateau Avenue Botreau-Roussel", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Expert Comptable / DAF",
        "secteur": "Finance & Comptabilité",
        "biographie": "Expert-comptable inscrit à l'ONECCA avec 15 ans d'expérience. Directeur Administratif et Financier dans les secteurs BTP et distribution. Maîtrise des normes SYSCOHADA et IFRS.",
        "profilCV": "Expert-Comptable · DAF · 15 ans · SYSCOHADA, IFRS · BTP & Distribution CI.",
        "anneePremEmploi": 2010, "mobilite": "National", "contrat": "CDI",
        "slogan": "La rigueur financière au service de la croissance.",
        "couleur": "#1e3a5f", "portfolioFichier": "style",
        "experiences": [
            {"entreprise": "Groupe Sifca CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2017, 6, 1), "fin": None, "enCours": True, "description": "DAF d'une filiale agro-industrielle (CA 45M€). Supervision d'une équipe finance de 12 personnes. Reporting IFRS trimestriel au groupe.", "poste": "Directeur Administratif et Financier", "missionClient": None},
            {"entreprise": "PricewaterhouseCoopers CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2010, 9, 1), "fin": date(2017, 5, 31), "enCours": False, "description": "Audit légal et commissariat aux comptes de grandes entreprises ivoiriennes. Chef de mission sur des audits multi-sites.", "poste": "Auditeur Senior", "missionClient": None},
        ],
        "formations": [
            {"diplome": "DESCF (Expert-Comptable)", "ecole": "ISCAE Dakar", "ville": "Dakar", "pays": "SENEGAL", "debut": date(2007, 9, 1), "fin": date(2010, 6, 30), "niveau": "Bac+5", "desc": "Diplôme d'Expertise Comptable et Financière — Major de promotion."},
            {"diplome": "Licence Comptabilité", "ecole": "UGB Saint-Louis", "ville": "Saint-Louis", "pays": "SENEGAL", "debut": date(2004, 9, 1), "fin": date(2007, 6, 30), "niveau": "BAC +3", "desc": "Mention Très Bien."},
        ],
        "competences": [("SYSCOHADA", 5), ("IFRS", 5), ("Cegid", 4), ("Excel avancé", 5), ("Audit", 5), ("Trésorerie", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "C1"), ("Wolof", "C2")],
        "interets":    ["Golf", "Économie africaine", "Mentoring"],
        "projets": [
            {"titre": "Restructuration financière filiale Sifca", "contexte": "Filiale en perte depuis 3 ans suite à la chute des cours du caoutchouc.", "realisation": "Plan de redressement en 18 mois. Retour à l'équilibre en année 2. Économies de 2.8M€.", "url": "", "debut": date(2019, 1, 1), "fin": date(2020, 6, 30)},
        ],
        "benevolats": [{"titre": "Formateur comptabilité", "organisation": "Junior Entreprise ISCAE CI", "debut": date(2015, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://linkedin.com/in/abdou-thiaw-daf"), ("x", "https://x.com/abdouthiaw_fi")],
    },

    # ── 26 ── PROMAN-GLASS ────────────────────────────────────────────────────
    {
        "prenom": "Christelle", "nom": "ASSOGBA", "sexe": "Femme",
        "email": "christelle.assogba@demo.test", "telephone": "+225 07 22 11 00 99",
        "naissance": date(1993, 2, 14), "nationalite": "Béninoise",
        "adresse": "Cocody les Deux Plateaux", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Architecte DPLG / Urbaniste",
        "secteur": "BTP & Génie Civil",
        "biographie": "Architecte diplômée de l'EAMAU avec 8 ans d'expérience en architecture résidentielle et tertiaire en Afrique de l'Ouest. Passionnée par l'architecture bioclimatique adaptée au contexte tropical africain.",
        "profilCV": "Architecte DPLG · 8 ans · Architecture tropicale, SketchUp, AutoCAD, Revit · CI & Bénin.",
        "anneePremEmploi": 2018, "mobilite": "International", "contrat": "CDI",
        "slogan": "Concevoir des espaces qui racontent l'Afrique.",
        "couleur": "#7c3aed", "portfolioFichier": "proman-glass",
        "experiences": [
            {"entreprise": "Cabinet AUA (Architecture Urbaine Africaine)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2021, 4, 1), "fin": None, "enCours": True, "description": "Conception de 12 villas de luxe à Cocody et Riviera. Coordination MOE, suivi de chantier, relation clients haut de gamme.", "poste": "Architecte Cheffe de Projet", "missionClient": None},
            {"entreprise": "SORED (Société de Réalisation et Développement)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2018, 7, 1), "fin": date(2021, 3, 31), "enCours": False, "description": "Conception et suivi de programmes immobiliers sociaux. 240 logements livrés en 2 ans.", "poste": "Architecte d'Exécution", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Diplôme d'Architecte DPLG", "ecole": "EAMAU (École Africaine et Mauricienne d'Architecture)", "ville": "Lomé", "pays": "TOGO", "debut": date(2012, 9, 1), "fin": date(2018, 6, 30), "niveau": "Bac+5", "desc": "Mémoire de fin d'études : Architecture bioclimatique en zone tropicale humide."},
        ],
        "competences": [("AutoCAD", 5), ("Revit", 4), ("SketchUp", 5), ("Architecture bioclimatique", 4), ("Gestion de chantier", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Fon", "C2")],
        "interets":    ["Art contemporain africain", "Photographie", "Jardinage"],
        "projets": [
            {"titre": "Villa Akwaba — Cocody", "contexte": "Villa de prestige 600m² à Cocody pour client privé.", "realisation": "Livrée en 14 mois, budget respecté. Récompensée au Prix Architecture CI 2023.", "url": "", "debut": date(2021, 6, 1), "fin": date(2022, 7, 31)},
        ],
        "benevolats": [{"titre": "Jury concours jeunes architectes", "organisation": "Ordre des Architectes CI", "debut": date(2022, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://linkedin.com/in/christelle-assogba-archi"), ("instagram", "https://instagram.com/christelle_archi")],
    },

    # ── 27 ── ORANGE-VIBRANT ──────────────────────────────────────────────────
    {
        "prenom": "Moussa", "nom": "DIABATÉ", "sexe": "Homme",
        "email": "moussa.diabate@demo.test", "telephone": "+225 05 33 44 55 66",
        "naissance": date(1990, 9, 30), "nationalite": "Ivoirienne",
        "adresse": "Yopougon Kouté", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Directeur Commercial",
        "secteur": "Commerce & Vente",
        "biographie": "Directeur commercial avec 10 ans d'expérience dans la grande distribution et les FMCG en Afrique de l'Ouest. Expert en développement réseau de distribution, négociation grands comptes et management d'équipes commerciales terrain.",
        "profilCV": "Directeur Commercial · FMCG · 10 ans · Distribution Afrique de l'Ouest · Gestion grands comptes.",
        "anneePremEmploi": 2014, "mobilite": "International", "contrat": "CDI",
        "slogan": "Vendre, c'est servir.",
        "couleur": "#ea580c", "portfolioFichier": "orange-vibrant",
        "experiences": [
            {"entreprise": "Nestlé Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 1, 1), "fin": None, "enCours": True, "description": "Gestion d'un portefeuille de 45 distributeurs et 12 000 points de vente. CA sous responsabilité : 18M€. Management d'une équipe de 35 commerciaux terrain.", "poste": "Directeur Commercial Zone Ouest", "missionClient": None},
            {"entreprise": "DAFCI (Distribution Alimentaire)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2014, 3, 1), "fin": date(2019, 12, 31), "enCours": False, "description": "Développement du réseau de distribution national. +120% de croissance CA en 5 ans.", "poste": "Responsable Développement Commercial", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master Commerce International", "ecole": "ESC Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2012, 9, 1), "fin": date(2014, 6, 30), "niveau": "Bac+5", "desc": "Spécialité Marketing et Distribution."},
            {"diplome": "BTS Négociation Relation Client", "ecole": "Lycée Technique d'Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2010, 9, 1), "fin": date(2012, 6, 30), "niveau": "BAC +2", "desc": "Major de promotion."},
        ],
        "competences": [("Négociation grands comptes", 5), ("Management équipe terrain", 5), ("CRM Salesforce", 4), ("Trade marketing", 4), ("P&L management", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Dioula", "C2"), ("Baoulé", "B1")],
        "interets":    ["Football", "Leadership", "Podcasts business"],
        "projets": [
            {"titre": "Expansion réseau rural Nestlé CI", "contexte": "Pénétration des zones rurales sous-équipées en distribution.", "realisation": "320 nouveaux points de vente ruraux ouverts en 18 mois. +8M€ de CA additionnel.", "url": "", "debut": date(2022, 3, 1), "fin": date(2023, 9, 30)},
        ],
        "benevolats": [{"titre": "Coach business", "organisation": "Réseau Entreprendre CI", "debut": date(2019, 6, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://linkedin.com/in/moussa-diabate-commercial"), ("x", "https://x.com/moussadiabate_ci")],
    },

    # ── 28 ── CLINIC-PRO ──────────────────────────────────────────────────────
    {
        "prenom": "Aya", "nom": "SANOGO", "sexe": "Femme",
        "email": "aya.sanogo@demo.test", "telephone": "+225 07 55 44 33 22",
        "naissance": date(1998, 3, 19), "nationalite": "Ivoirienne",
        "adresse": "Abobo Baoulé", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Infirmière Diplômée d'État",
        "secteur": "Santé",
        "biographie": "Infirmière diplômée avec 4 ans d'expérience en soins intensifs et médecine interne. Passionnée par les soins de qualité et l'éducation thérapeutique du patient. Cherche à intégrer une structure de santé innovante.",
        "profilCV": "Infirmière IDE · 4 ans · Soins intensifs, médecine interne, pédiatrie · CHU Abidjan.",
        "anneePremEmploi": 2021, "mobilite": "National", "contrat": "CDI",
        "slogan": "Soigner avec le cœur, traiter avec la tête.",
        "couleur": "#0891b2", "portfolioFichier": "clinic-pro",
        "experiences": [
            {"entreprise": "CHU de Yopougon", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2021, 9, 1), "fin": None, "enCours": True, "description": "Infirmière en service de médecine interne et soins intensifs. Prise en charge des patients chroniques (diabète, HTA, IRC). Encadrement des stagiaires.", "poste": "Infirmière IDE", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Diplôme d'État Infirmier", "ecole": "Institut National de Formation des Agents de Santé (INFAS)", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2018, 9, 1), "fin": date(2021, 6, 30), "niveau": "BAC +3", "desc": "Major de promotion. Stage de fin d'études au CHU de Treichville."},
        ],
        "competences": [("Soins intensifs", 5), ("Prise en charge chroniques", 5), ("Pédiatrie", 4), ("Urgences", 4), ("Éducation thérapeutique", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B1"), ("Dioula", "C2"), ("Sénoufo", "B2")],
        "interets":    ["Yoga", "Jardinage", "Livres de santé"],
        "projets": [
            {"titre": "Programme éducation patients diabétiques CHU Yopougon", "contexte": "Fort taux de réhospitalisation des patients diabétiques.", "realisation": "Programme d'éducation en groupe (8 séances). Réduction des réhospitalisations de 30% en 1 an.", "url": "", "debut": date(2023, 1, 1), "fin": date(2023, 12, 31)},
        ],
        "benevolats": [{"titre": "Infirmière bénévole", "organisation": "Croix-Rouge Côte d'Ivoire", "debut": date(2022, 6, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://linkedin.com/in/aya-sanogo-ide")],
    },

    # ── 29 ── TECH-DASHBOARD ──────────────────────────────────────────────────
    {
        "prenom": "Cheick", "nom": "COULIBALY", "sexe": "Homme",
        "email": "cheick.coulibaly@demo.test", "telephone": "+225 05 66 77 88 99",
        "naissance": date(1983, 6, 5), "nationalite": "Malienne",
        "adresse": "Treichville Avenue 18", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Responsable Logistique & Supply Chain",
        "secteur": "Logistique & Transport",
        "biographie": "Responsable logistique avec 16 ans d'expérience dans la gestion de chaînes d'approvisionnement complexes en Afrique. Expert en import/export, gestion d'entrepôt et optimisation des flux sous contrainte.",
        "profilCV": "Supply Chain Manager · 16 ans · Import/export, WMS, S&OP · Agro-industrie & FMCG.",
        "anneePremEmploi": 2008, "mobilite": "International", "contrat": "CDI",
        "slogan": "Le bon produit, au bon endroit, au bon moment.",
        "couleur": "#4338ca", "portfolioFichier": "tech-dashboard",
        "experiences": [
            {"entreprise": "SUCRIVOIRE (Sucre CI)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2016, 4, 1), "fin": None, "enCours": True, "description": "Responsable de la supply chain du plus grand sucrier ivoirien. Gestion d'un stock de 45 000 tonnes. 18 transporteurs, 6 entrepôts régionaux.", "poste": "Directeur Logistique & Supply Chain", "missionClient": None},
            {"entreprise": "SDV Bolloré CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2008, 2, 1), "fin": date(2016, 3, 31), "enCours": False, "description": "Transit, dédouanement et gestion entrepôt pour clients industriels et agro-alimentaires.", "poste": "Responsable Transit Senior", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master Logistique & Transport", "ecole": "ISTA Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2006, 9, 1), "fin": date(2008, 6, 30), "niveau": "Bac+5", "desc": "Spécialité Supply Chain Management."},
            {"diplome": "BTS Transport & Logistique", "ecole": "Lycée Professionnel de Bamako", "ville": "Bamako", "pays": "MALI", "debut": date(2003, 9, 1), "fin": date(2006, 6, 30), "niveau": "BAC +2", "desc": "Major de promotion."},
        ],
        "competences": [("WMS (Warehouse Mgmt)", 5), ("SAP MM", 4), ("S&OP", 5), ("Import/Export", 5), ("Gestion de flotte", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Bambara", "C2"), ("Dioula", "C1")],
        "interets":    ["Lecture stratégie", "Football", "Jardinage"],
        "projets": [
            {"titre": "Optimisation flux sucre SUCRIVOIRE", "contexte": "Ruptures fréquentes en saison sèche, coûts de stockage élevés.", "realisation": "Modèle prédictif de réapprovisionnement. Ruptures -72%. Économie stock : 1.4M€/an.", "url": "", "debut": date(2020, 6, 1), "fin": date(2021, 3, 31)},
        ],
        "benevolats": [{"titre": "Formateur logistique", "organisation": "CGECI (Patronat CI)", "debut": date(2018, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://linkedin.com/in/cheick-coulibaly-scm")],
    },

    # ── 30 ── RETRO-MAG ───────────────────────────────────────────────────────
    {
        "prenom": "Natacha", "nom": "GBAGBO", "sexe": "Femme",
        "email": "natacha.gbagbo@demo.test", "telephone": "+225 07 12 23 34 45",
        "naissance": date(1991, 12, 8), "nationalite": "Ivoirienne",
        "adresse": "Marcory Anoumabo", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Chef Cuisinière / Restauratrice",
        "secteur": "Hôtellerie & Restauration",
        "biographie": "Chef cuisinière formée à Paris et Abidjan avec 10 ans d'expérience. Spécialisée dans la cuisine africaine contemporaine et fusion franco-ivoirienne. Propriétaire du restaurant 'Sauce Graine' à Marcory.",
        "profilCV": "Chef Cuisinière · 10 ans · Cuisine africaine contemporaine · Gestion restaurant · Formation.",
        "anneePremEmploi": 2014, "mobilite": "National", "contrat": "Freelance",
        "slogan": "La cuisine africaine au rang des grandes tables.",
        "couleur": "#b91c1c", "portfolioFichier": "retro-mag",
        "experiences": [
            {"entreprise": "Restaurant Sauce Graine (propre)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 6, 1), "fin": None, "enCours": True, "description": "Fondatrice et chef du restaurant gastronomique africain 'Sauce Graine'. 45 couverts/soir. 4,7/5 sur TripAdvisor. Carte réinventée chaque saison.", "poste": "Chef Propriétaire", "missionClient": None},
            {"entreprise": "Hôtel Ivoire Abidjan", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2014, 7, 1), "fin": date(2019, 5, 31), "enCours": False, "description": "Chef de partie puis sous-chef pour le restaurant gastronomique 5 étoiles. Formation de 8 commis. Création menus événementiels.", "poste": "Sous-Chef", "missionClient": None},
        ],
        "formations": [
            {"diplome": "CAP Cuisine + Brevet Professionnel", "ecole": "École Ferrandi Paris", "ville": "Paris", "pays": "FRANCE", "debut": date(2012, 9, 1), "fin": date(2014, 6, 30), "niveau": "BAC +2", "desc": "Formation cuisine gastronomique française. Stage au restaurant 3 étoiles Le Meurice."},
        ],
        "competences": [("Cuisine africaine contemporaine", 5), ("Gestion restaurant", 5), ("Pâtisserie", 4), ("Management cuisine", 4), ("Food costing", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B1"), ("Guéré", "C2")],
        "interets":    ["Voyages gastronomiques", "Photographie culinaire", "Agriculture bio"],
        "projets": [
            {"titre": "Lancement restaurant 'Sauce Graine'", "contexte": "Créer un restaurant de cuisine africaine haut de gamme à Abidjan.", "realisation": "Ouvert en 2019. Complet 5 soirs/7. 4,7/5 sur Google Maps. Article dans Jeune Afrique Économie.", "url": "", "debut": date(2018, 9, 1), "fin": date(2019, 6, 1)},
        ],
        "benevolats": [{"titre": "Formatrice cuisine", "organisation": "Maison d'arrêt d'Abidjan (réinsertion)", "debut": date(2021, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://linkedin.com/in/natacha-gbagbo-chef"), ("instagram", "https://instagram.com/saucegraine_abidjan")],
    },

    # ── 31 ── CYBER-NEON ──────────────────────────────────────────────────────
    {
        "prenom": "Moïse", "nom": "KOUAKOU", "sexe": "Homme",
        "email": "moise.kouakou@demo.test", "telephone": "+225 05 99 00 11 22",
        "naissance": date(1995, 8, 27), "nationalite": "Ivoirienne",
        "adresse": "Cocody Riviera 3", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Juriste d'Entreprise / Droit des Affaires",
        "secteur": "Juridique & Compliance",
        "biographie": "Juriste d'entreprise spécialisé en droit des affaires OHADA, droit des contrats et droit de la propriété intellectuelle. 5 ans d'expérience auprès de PME et grands groupes internationaux en Côte d'Ivoire.",
        "profilCV": "Juriste d'Entreprise · Droit OHADA · 5 ans · Contrats, PI, Compliance · CI.",
        "anneePremEmploi": 2019, "mobilite": "National", "contrat": "CDI",
        "slogan": "Sécuriser les affaires, libérer la croissance.",
        "couleur": "#059669", "portfolioFichier": "cyber-neon",
        "experiences": [
            {"entreprise": "Cabinet Lath & Associés", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2021, 9, 1), "fin": None, "enCours": True, "description": "Juriste en droit des affaires et OHADA. Rédaction et négociation de contrats commerciaux, due diligence, accompagnement d'investisseurs étrangers.", "poste": "Juriste Senior", "missionClient": None},
            {"entreprise": "Total Énergies CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 7, 1), "fin": date(2021, 8, 31), "enCours": False, "description": "Juriste interne. Gestion des contrats fournisseurs, suivi litiges, veille juridique.", "poste": "Juriste d'Entreprise Junior", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master Droit des Affaires", "ecole": "Université FHB Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2017, 9, 1), "fin": date(2019, 6, 30), "niveau": "Bac+5", "desc": "Spécialité Droit OHADA et des affaires internationales. Major."},
            {"diplome": "Licence Droit Privé", "ecole": "Université FHB Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2014, 9, 1), "fin": date(2017, 6, 30), "niveau": "BAC +3", "desc": "Mention Très Bien."},
        ],
        "competences": [("Droit OHADA", 5), ("Rédaction contrats", 5), ("Propriété intellectuelle", 4), ("Due diligence", 4), ("Droit social", 3)],
        "langues":     [("Français", "C2"), ("Anglais", "C1"), ("Agni", "C2")],
        "interets":    ["Droit comparé Afrique", "Basketball", "Philosophie"],
        "projets": [
            {"titre": "Restructuration juridique groupe PME familiale", "contexte": "Groupe familial de 5 sociétés sans holding structurée.", "realisation": "Création holding OHADA, pacte d'actionnaires, consolidation IP. Sécurisation du patrimoine familial.", "url": "", "debut": date(2022, 3, 1), "fin": date(2022, 9, 30)},
        ],
        "benevolats": [{"titre": "Consultant juridique bénévole", "organisation": "ANADER (Agric. CI)", "debut": date(2020, 6, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://linkedin.com/in/moise-kouakou-juriste"), ("x", "https://x.com/moise_law")],
    },

    # ── 32 ── PROMAN-PRO ──────────────────────────────────────────────────────
    {
        "prenom": "Rokia", "nom": "OUATTARA", "sexe": "Femme",
        "email": "rokia.ouattara@demo.test", "telephone": "+225 07 88 99 00 11",
        "naissance": date(1987, 4, 3), "nationalite": "Ivoirienne",
        "adresse": "Adjamé Biafrà", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Enseignante / Formatrice en Éducation",
        "secteur": "Éducation & Formation",
        "biographie": "Professeure agrégée de Français avec 14 ans d'expérience dans le secondaire et la formation professionnelle. Spécialisée en ingénierie pédagogique et e-learning. Conceptrice de curricula pour institutions internationales.",
        "profilCV": "Enseignante agrégée · Formatrice · 14 ans · Ingénierie pédagogique, e-learning, Moodle · CI.",
        "anneePremEmploi": 2010, "mobilite": "National", "contrat": "CDI",
        "slogan": "Éduquer, c'est construire l'avenir.",
        "couleur": "#9333ea", "portfolioFichier": "proman-pro",
        "experiences": [
            {"entreprise": "Lycée Scientifique de Yamoussoukro", "pays": "COTE D'IVOIRE", "ville": "Yamoussoukro", "pays": "COTE D'IVOIRE", "debut": date(2010, 9, 1), "fin": date(2020, 7, 31), "enCours": False, "description": "Professeure de Français, Littérature et Expression en classes de terminale et BTS. Responsable du club théâtre.", "poste": "Professeure Agrégée Lettres", "missionClient": None},
            {"entreprise": "Université Virtuelle de Côte d'Ivoire (UVCI)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 8, 1), "fin": None, "enCours": True, "description": "Conception de cours en ligne pour 12 000 étudiants. Coordination pédagogique de 8 modules Lettres et SHS. Tuteur Moodle.", "poste": "Chargée de Cours et Conceptrice E-learning", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Agrégation de Lettres Modernes", "ecole": "Université FHB Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2008, 9, 1), "fin": date(2010, 6, 30), "niveau": "Bac+5", "desc": "Reçue au concours national d'agrégation CI — rang 3."},
            {"diplome": "Licence Lettres Modernes", "ecole": "Université de Bouaké", "ville": "Bouaké", "pays": "COTE D'IVOIRE", "debut": date(2005, 9, 1), "fin": date(2008, 6, 30), "niveau": "BAC +3", "desc": "Mention Très Bien."},
        ],
        "competences": [("Ingénierie pédagogique", 5), ("Moodle LMS", 5), ("Conception curricula", 5), ("Expression orale/écrite", 5), ("E-learning", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Malinké", "C1"), ("Dioula", "B2")],
        "interets":    ["Littérature africaine", "Théâtre", "Randonnée"],
        "projets": [
            {"titre": "Conception module 'Écriture académique UVCI'", "contexte": "Étudiants en difficulté rédactionnelle (26% d'échec en licence).", "realisation": "Module e-learning 8 semaines, 3 200 étudiants formés. Taux réussite licence +18 points.", "url": "", "debut": date(2021, 1, 1), "fin": date(2021, 9, 30)},
        ],
        "benevolats": [{"titre": "Alphabétisation adultes", "organisation": "ONG Lumière CI", "debut": date(2013, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://linkedin.com/in/rokia-ouattara-formatrice"), ("googlechrome", "https://rokia-education.ci")],
    },

    # ── 33 ── ORANGE-VIBRANT ─────────────────────────────────────────────────
    {
        "prenom": "Bakary", "nom": "SILUE", "sexe": "Homme",
        "email": "bakary.silue@demo.test", "telephone": "+225 07 15 25 35 45",
        "naissance": date(1990, 2, 19), "nationalite": "Ivoirienne",
        "adresse": "Angré 8e Tranche", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Ingénieur Réseaux & Télécoms",
        "secteur": "Télécommunications et Digital",
        "biographie": "Ingénieur réseaux avec 9 ans d'expérience dans le déploiement et la supervision d'infrastructures télécoms. Certifié Cisco CCNP, je conçois des architectures fiables et sécurisées pour opérateurs et entreprises.",
        "profilCV": "Ingénieur réseaux · 9 ans · CCNP, infrastructures télécoms, sécurité périmétrique, supervision NOC.",
        "anneePremEmploi": 2015, "mobilite": "International", "contrat": "CDI",
        "slogan": "Connecter, sécuriser, performer.",
        "couleur": "#F77F00", "portfolioFichier": "orange-vibrant",
        "experiences": [
            {"entreprise": "MOOV Africa Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 2, 1), "fin": None, "enCours": True, "description": "Supervision du réseau cœur (MPLS/IP). Pilotage des déploiements 4G/5G en régions. Astreinte NOC niveau 3.", "poste": "Ingénieur Réseaux Senior", "missionClient": None},
            {"entreprise": "Huawei Technologies CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2015, 3, 1), "fin": date(2019, 1, 31), "enCours": False, "description": "Installation et configuration d'équipements radio pour opérateurs locaux. Support technique niveau 2.", "poste": "Ingénieur Support Technique", "missionClient": {"client": "Orange Côte d'Ivoire", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2017, 3, 1), "fin": date(2017, 9, 30), "desc": "Déploiement de 40 sites 4G dans la région des Lagunes."}},
        ],
        "formations": [
            {"diplome": "Ingénieur en Télécommunications", "ecole": "INPHB Yamoussoukro", "ville": "Yamoussoukro", "pays": "COTE D'IVOIRE", "debut": date(2012, 9, 1), "fin": date(2015, 6, 30), "niveau": "Bac+5", "desc": "Spécialité Réseaux et Systèmes de Télécommunications."},
            {"diplome": "Certification CCNP Enterprise", "ecole": "Cisco Networking Academy", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2018, 1, 1), "fin": date(2018, 6, 30), "niveau": "BAC +5", "desc": "Certification professionnelle réseaux avancés."},
        ],
        "competences": [("Cisco CCNP", 5), ("MPLS", 4), ("Sécurité réseaux", 4), ("4G/5G", 4), ("Supervision NOC", 5)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Senoufo", "C1")],
        "interets":    ["Football", "Robotique amateur", "Voyages"],
        "projets": [
            {"titre": "Déploiement 4G Région des Lagunes", "contexte": "Extension de couverture pour 40 nouveaux sites.", "realisation": "Coordination technique du chantier, tests de charge, mise en service dans les délais.", "url": "", "debut": date(2017, 3, 1), "fin": date(2017, 9, 30)},
            {"titre": "Refonte supervision NOC MOOV", "contexte": "Réduire le MTTR des incidents réseau critiques.", "realisation": "Mise en place de dashboards temps réel, alerting automatisé. MTTR réduit de 40%.", "url": "", "debut": date(2021, 1, 1), "fin": date(2021, 6, 30)},
        ],
        "benevolats": [{"titre": "Formateur réseaux bénévole", "organisation": "Simplon Côte d'Ivoire", "debut": date(2020, 3, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/bakary-silue"), ("github", "https://github.com/bakarysilue")],
    },

    # ── 34 ── SNAPFOLIO ──────────────────────────────────────────────────────
    {
        "prenom": "Estelle", "nom": "KACOU", "sexe": "Femme",
        "email": "estelle.kacou@demo.test", "telephone": "+225 05 12 24 36 48",
        "naissance": date(1993, 8, 27), "nationalite": "Ivoirienne",
        "adresse": "Cocody Danga", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Responsable Communication & Marketing Digital",
        "secteur": "Communication & Marketing",
        "biographie": "Spécialiste en communication digitale avec 7 ans d'expérience en agence et annonceur. Je pilote des stratégies de contenu et campagnes social media à fort impact pour des marques grand public.",
        "profilCV": "Responsable communication digitale · 7 ans · Stratégie de contenu, social ads, growth marketing, brand content.",
        "anneePremEmploi": 2017, "mobilite": "National", "contrat": "CDI",
        "slogan": "Raconter des histoires qui vendent.",
        "couleur": "#E85D4A", "portfolioFichier": "snapfolio",
        "experiences": [
            {"entreprise": "Nestlé Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 5, 1), "fin": None, "enCours": True, "description": "Pilotage de la stratégie social media pour 5 marques (2M+ abonnés cumulés). Gestion d'un budget média de 400M FCFA/an.", "poste": "Responsable Communication Digitale", "missionClient": None},
            {"entreprise": "Agence Kaïna Communication", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2017, 6, 1), "fin": date(2020, 4, 30), "enCours": False, "description": "Gestion de comptes clients (télécoms, agroalimentaire). Conception de campagnes 360°.", "poste": "Chargée de Communication", "missionClient": {"client": "MTN Côte d'Ivoire", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2018, 1, 1), "fin": date(2018, 12, 31), "desc": "Campagne de lancement MoMo Pay — +35% d'activations en 6 mois."}},
        ],
        "formations": [
            {"diplome": "Master Communication & Marketing", "ecole": "ISTC Polytechnique Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2015, 9, 1), "fin": date(2017, 6, 30), "niveau": "Bac+5", "desc": "Spécialité Communication digitale et publicité."},
            {"diplome": "Licence Sciences de l'Information et Communication", "ecole": "Université FHB Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2012, 9, 1), "fin": date(2015, 6, 30), "niveau": "BAC +3", "desc": "Mention Assez Bien."},
        ],
        "competences": [("Social Media Strategy", 5), ("Meta Ads", 5), ("Content Marketing", 5), ("Google Analytics", 4), ("Canva/Adobe Suite", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Baoulé", "B1")],
        "interets":    ["Photographie", "Podcasts", "Mode"],
        "projets": [
            {"titre": "Lancement MoMo Pay MTN", "contexte": "Faire connaître le nouveau service de paiement marchand.", "realisation": "Campagne 360° (social, influenceurs, terrain). +35% d'activations en 6 mois.", "url": "", "debut": date(2018, 1, 1), "fin": date(2018, 12, 31)},
            {"titre": "Refonte identité social media Nestlé CI", "contexte": "Harmoniser la voix de marque sur 5 comptes.", "realisation": "Charte éditoriale unifiée, calendrier de contenu, +60% d'engagement moyen.", "url": "", "debut": date(2021, 3, 1), "fin": date(2021, 10, 31)},
        ],
        "benevolats": [{"titre": "Bénévole communication", "organisation": "Croix-Rouge Côte d'Ivoire", "debut": date(2019, 4, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/estelle-kacou"), ("instagram", "https://instagram.com/estelle.kacou")],
    },

    # ── 35 ── STYLE ───────────────────────────────────────────────────────────
    {
        "prenom": "Modeste", "nom": "YEO", "sexe": "Homme",
        "email": "modeste.yeo@demo.test", "telephone": "+225 07 63 52 41 30",
        "naissance": date(1986, 6, 11), "nationalite": "Ivoirienne",
        "adresse": "Yopougon Niangon", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "ABCDE", "titre": "Chef de Chantier BTP",
        "secteur": "BTP & Génie Civil",
        "biographie": "Chef de chantier avec 13 ans d'expérience dans la construction de bâtiments et infrastructures routières. Rigoureux sur la sécurité et le respect des délais, j'ai piloté plus de 20 chantiers en Côte d'Ivoire.",
        "profilCV": "Chef de chantier BTP · 13 ans · Gestion d'équipes de 30+ ouvriers, planification, sécurité HSE, suivi budgétaire.",
        "anneePremEmploi": 2011, "mobilite": "National", "contrat": "CDI",
        "slogan": "Bâtir solide, livrer à l'heure.",
        "couleur": "#009A44", "portfolioFichier": "style",
        "experiences": [
            {"entreprise": "Eiffage Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2016, 4, 1), "fin": None, "enCours": True, "description": "Pilotage de chantiers de voirie et bâtiments tertiaires. Management d'équipes de 30 à 50 ouvriers. Suivi budgétaire et reporting hebdomadaire.", "poste": "Chef de Chantier Senior", "missionClient": None},
            {"entreprise": "SOGEA-SATOM", "pays": "COTE D'IVOIRE", "ville": "Yamoussoukro", "debut": date(2011, 3, 1), "fin": date(2016, 3, 31), "enCours": False, "description": "Suivi de travaux d'infrastructures routières. Contrôle qualité des matériaux et coordination des sous-traitants.", "poste": "Chef d'Équipe Travaux Publics", "missionClient": None},
        ],
        "formations": [
            {"diplome": "BTS Bâtiment et Travaux Publics", "ecole": "Lycée Technique d'Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2009, 9, 1), "fin": date(2011, 6, 30), "niveau": "BAC +2", "desc": "Spécialité gros œuvre et conduite de travaux."},
            {"diplome": "Certification HSE Chantier", "ecole": "Institut de Sécurité au Travail CI", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2015, 1, 1), "fin": date(2015, 3, 31), "niveau": "BAC +2", "desc": "Formation sécurité et prévention des risques sur chantier."},
        ],
        "competences": [("Gestion de chantier", 5), ("Lecture de plans", 5), ("Sécurité HSE", 5), ("Management d'équipe", 4), ("MS Project", 3)],
        "langues":     [("Français", "C1"), ("Sénoufo", "C2"), ("Anglais", "A2")],
        "interets":    ["Football", "Menuiserie", "Agriculture"],
        "projets": [
            {"titre": "Voirie Boulevard de Yopougon", "contexte": "Réfection de 4,5 km de voirie urbaine.", "realisation": "Livraison avec 2 semaines d'avance sur planning, zéro accident chantier.", "url": "", "debut": date(2019, 1, 1), "fin": date(2019, 8, 31)},
            {"titre": "Construction siège social Eiffage CI", "contexte": "Bâtiment tertiaire R+4 de 3 200 m².", "realisation": "Coordination de 6 corps de métier, respect du budget à 98%.", "url": "", "debut": date(2020, 2, 1), "fin": date(2021, 5, 31)},
        ],
        "benevolats": [{"titre": "Formateur jeunes maçons", "organisation": "Chambre des Métiers CI", "debut": date(2018, 6, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/modeste-yeo")],
    },

    # ── 36 ── TECH-DASHBOARD ─────────────────────────────────────────────────
    {
        "prenom": "Diarra", "nom": "FOFANA", "sexe": "Femme",
        "email": "diarra.fofana@demo.test", "telephone": "+225 07 74 63 52 41",
        "naissance": date(1995, 1, 30), "nationalite": "Ivoirienne",
        "adresse": "Riviera 3", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Data Analyst",
        "secteur": "Numérique (Tech)",
        "biographie": "Data analyst passionnée par la donnée au service de la décision. 5 ans d'expérience en banque et télécoms, je transforme des données brutes en tableaux de bord actionnables.",
        "profilCV": "Data Analyst · 5 ans · SQL, Python, Power BI, dashboards de pilotage, modélisation de données.",
        "anneePremEmploi": 2019, "mobilite": "National", "contrat": "CDI",
        "slogan": "La donnée qui éclaire la décision.",
        "couleur": "#003366", "portfolioFichier": "tech-dashboard",
        "experiences": [
            {"entreprise": "NSIA Banque Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2021, 9, 1), "fin": None, "enCours": True, "description": "Conception de dashboards Power BI pour le comité de direction. Automatisation de rapports mensuels (gain de 15h/mois). Analyse du risque crédit.", "poste": "Data Analyst Senior", "missionClient": None},
            {"entreprise": "Orange Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 3, 1), "fin": date(2021, 8, 31), "enCours": False, "description": "Analyse des données d'usage réseau et churn client. Reporting pour la direction marketing.", "poste": "Analyste Data Junior", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master Data Science", "ecole": "ENSEA Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2017, 9, 1), "fin": date(2019, 6, 30), "niveau": "Bac+5", "desc": "Spécialité statistique appliquée et data mining."},
            {"diplome": "Licence Mathématiques Appliquées", "ecole": "Université FHB Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2014, 9, 1), "fin": date(2017, 6, 30), "niveau": "BAC +3", "desc": "Mention Bien."},
        ],
        "competences": [("SQL", 5), ("Python", 4), ("Power BI", 5), ("Excel avancé", 5), ("Statistiques", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Dioula", "B1")],
        "interets":    ["Jeux de données ouvertes", "Course à pied", "Cinéma"],
        "projets": [
            {"titre": "Dashboard risque crédit NSIA", "contexte": "Suivi mensuel manuel et chronophage du portefeuille crédit.", "realisation": "Automatisation complète sous Power BI, alertes de dépassement de seuils en temps réel.", "url": "", "debut": date(2022, 2, 1), "fin": date(2022, 7, 31)},
            {"titre": "Modèle de prédiction du churn Orange", "contexte": "Anticiper la résiliation des abonnés post-payés.", "realisation": "Modèle de scoring en Python, précision de 78%. Adopté par l'équipe rétention.", "url": "https://github.com/demo/churn-model", "debut": date(2020, 4, 1), "fin": date(2020, 9, 30)},
        ],
        "benevolats": [{"titre": "Mentor data", "organisation": "Women in Data CI", "debut": date(2021, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/diarra-fofana"), ("github", "https://github.com/diarrafofana")],
    },

    # ── 37 ── CLINIC-PRO ──────────────────────────────────────────────────────
    {
        "prenom": "Prisca", "nom": "EHOUMAN", "sexe": "Femme",
        "email": "prisca.ehouman@demo.test", "telephone": "+225 05 85 74 63 52",
        "naissance": date(1991, 9, 14), "nationalite": "Ivoirienne",
        "adresse": "Treichville", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Infirmière Diplômée d'État",
        "secteur": "Santé",
        "biographie": "Infirmière diplômée d'État avec 8 ans d'expérience en milieu hospitalier, spécialisée en soins d'urgence. Engagée pour un accompagnement humain et rigoureux des patients.",
        "profilCV": "Infirmière DE · 8 ans · Soins d'urgence, réanimation, gestion de la douleur, encadrement stagiaires.",
        "anneePremEmploi": 2016, "mobilite": "Local", "contrat": "CDI",
        "slogan": "Soigner avec compétence et humanité.",
        "couleur": "#2A9D8F", "portfolioFichier": "clinic-pro",
        "experiences": [
            {"entreprise": "CHU de Treichville", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 6, 1), "fin": None, "enCours": True, "description": "Infirmière au service des urgences. Prise en charge de 25 à 40 patients/jour. Encadrement de 4 stagiaires infirmiers.", "poste": "Infirmière Urgentiste", "missionClient": None},
            {"entreprise": "Polyclinique Internationale Sainte Anne-Marie", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2016, 2, 1), "fin": date(2019, 5, 31), "enCours": False, "description": "Soins infirmiers en médecine générale et pédiatrie. Participation aux campagnes de vaccination.", "poste": "Infirmière Polyvalente", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Diplôme d'État Infirmier", "ecole": "INFAS Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2013, 9, 1), "fin": date(2016, 6, 30), "niveau": "BAC +3", "desc": "Formation en soins infirmiers généraux."},
            {"diplome": "Certification Soins d'Urgence et Réanimation", "ecole": "CHU de Treichville", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2020, 1, 1), "fin": date(2020, 4, 30), "niveau": "BAC +3", "desc": "Formation continue en gestes d'urgence et réanimation cardio-pulmonaire."},
        ],
        "competences": [("Soins d'urgence", 5), ("Réanimation", 4), ("Gestion de la douleur", 5), ("Encadrement stagiaires", 4), ("Dossier patient informatisé", 3)],
        "langues":     [("Français", "C2"), ("Anglais", "B1"), ("Bété", "C1")],
        "interets":    ["Bénévolat médical", "Chant choral", "Lecture"],
        "projets": [
            {"titre": "Campagne de vaccination COVID-19", "contexte": "Mobilisation communautaire à Treichville.", "realisation": "Coordination de 3 équipes mobiles, plus de 4 000 personnes vaccinées.", "url": "", "debut": date(2021, 3, 1), "fin": date(2021, 8, 31)},
            {"titre": "Amélioration du tri aux urgences", "contexte": "Temps d'attente élevé et priorisation peu claire.", "realisation": "Mise en place d'une grille de tri standardisée, temps d'attente moyen réduit de 25%.", "url": "", "debut": date(2022, 1, 1), "fin": date(2022, 5, 31)},
        ],
        "benevolats": [{"titre": "Infirmière bénévole", "organisation": "Médecins du Monde CI", "debut": date(2018, 5, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/prisca-ehouman")],
    },

    # ── 38 ── CYBER-NEON ──────────────────────────────────────────────────────
    {
        "prenom": "Landry", "nom": "KOUASSI", "sexe": "Homme",
        "email": "landry.kouassi@demo.test", "telephone": "+225 07 96 85 74 63",
        "naissance": date(1996, 5, 5), "nationalite": "Ivoirienne",
        "adresse": "Cocody Mermoz", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Développeur Mobile (iOS/Android)",
        "secteur": "Numérique (Tech)",
        "biographie": "Développeur mobile spécialisé Flutter et React Native, 5 ans d'expérience dans des fintechs et startups. Je conçois des applications performantes et intuitives pour des millions d'utilisateurs.",
        "profilCV": "Développeur mobile · 5 ans · Flutter, React Native, Kotlin, intégration API, publication App Store/Play Store.",
        "anneePremEmploi": 2019, "mobilite": "International", "contrat": "Freelance / Mission",
        "slogan": "Une app, mille possibilités.",
        "couleur": "#1a1a2e", "portfolioFichier": "cyber-neon",
        "experiences": [
            {"entreprise": "WAVE Mobile Money", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2021, 1, 1), "fin": None, "enCours": True, "description": "Développement de nouvelles fonctionnalités de l'app Wave (Flutter). Optimisation des performances pour appareils bas de gamme.", "poste": "Développeur Mobile Senior", "missionClient": None},
            {"entreprise": "Baguera Digital", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 4, 1), "fin": date(2020, 12, 31), "enCours": False, "description": "Développement d'applications mobiles pour clients variés (santé, e-commerce). React Native et Kotlin natif.", "poste": "Développeur Mobile", "missionClient": {"client": "Jumia Côte d'Ivoire", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2020, 3, 1), "fin": date(2020, 9, 30), "desc": "Refonte du module panier et paiement de l'app Jumia CI."}},
        ],
        "formations": [
            {"diplome": "Licence Génie Logiciel", "ecole": "ESATIC Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2016, 9, 1), "fin": date(2019, 6, 30), "niveau": "BAC +3", "desc": "Spécialité développement mobile et applications distribuées."},
        ],
        "competences": [("Flutter", 5), ("React Native", 4), ("Kotlin", 4), ("REST/GraphQL", 4), ("CI/CD mobile", 3)],
        "langues":     [("Français", "C2"), ("Anglais", "B2")],
        "interets":    ["Jeux vidéo", "Open Source", "Basketball"],
        "projets": [
            {"titre": "Refonte panier Jumia CI", "contexte": "Taux d'abandon panier élevé sur mobile (68%).", "realisation": "Refonte UX du tunnel de paiement, taux d'abandon réduit à 47%.", "url": "", "debut": date(2020, 3, 1), "fin": date(2020, 9, 30)},
            {"titre": "App communautaire QuartierLink", "contexte": "Projet personnel de mise en relation de voisinage.", "realisation": "App Flutter complète, 3 000 téléchargements organiques, 4.6★ sur Play Store.", "url": "https://github.com/demo/quartierlink", "debut": date(2022, 1, 1), "fin": date(2022, 11, 30)},
        ],
        "benevolats": [{"titre": "Formateur coding club", "organisation": "Djelia Tech CI", "debut": date(2020, 9, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/landry-kouassi"), ("github", "https://github.com/landrykouassi"), ("x", "https://x.com/landrydev")],
    },

    # ── 39 ── RETRO-MAG ───────────────────────────────────────────────────────
    {
        "prenom": "Awa", "nom": "TOURE", "sexe": "Femme",
        "email": "awa.toure@demo.test", "telephone": "+225 05 41 52 63 74",
        "naissance": date(1989, 12, 2), "nationalite": "Ivoirienne",
        "adresse": "Plateau, Rue du Commerce", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Juriste d'Affaires",
        "secteur": "Juridique & Compliance",
        "biographie": "Juriste d'affaires avec 10 ans d'expérience en cabinet et direction juridique d'entreprise. Spécialisée en droit OHADA, contrats commerciaux et conformité réglementaire.",
        "profilCV": "Juriste d'affaires · 10 ans · Droit OHADA, contrats commerciaux, conformité, contentieux, fusions-acquisitions.",
        "anneePremEmploi": 2013, "mobilite": "International", "contrat": "CDI",
        "slogan": "Le droit au service de la performance.",
        "couleur": "#C9A227", "portfolioFichier": "retro-mag",
        "experiences": [
            {"entreprise": "CFAO Motors CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2018, 3, 1), "fin": None, "enCours": True, "description": "Direction juridique du pôle Afrique de l'Ouest. Négociation de contrats commerciaux majeurs. Gestion du contentieux et de la conformité anti-corruption.", "poste": "Juriste d'Affaires Senior", "missionClient": None},
            {"entreprise": "Cabinet FIDAFRICA (PwC Legal)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2013, 9, 1), "fin": date(2018, 2, 28), "enCours": False, "description": "Conseil en droit des affaires OHADA pour multinationales et PME. Rédaction de contrats et due diligence.", "poste": "Avocate Collaboratrice", "missionClient": {"client": "TotalEnergies Côte d'Ivoire", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2016, 1, 1), "fin": date(2016, 12, 31), "desc": "Due diligence juridique dans le cadre d'une opération d'acquisition de stations-service."}},
        ],
        "formations": [
            {"diplome": "Master en Droit des Affaires OHADA", "ecole": "Université Catholique de l'Afrique de l'Ouest", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2011, 9, 1), "fin": date(2013, 6, 30), "niveau": "Bac+5", "desc": "Spécialité droit commercial et arbitrage international."},
            {"diplome": "Maîtrise en Droit Privé", "ecole": "Université FHB Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2007, 9, 1), "fin": date(2011, 6, 30), "niveau": "Bac+5", "desc": "Mention Bien."},
        ],
        "competences": [("Droit OHADA", 5), ("Contrats commerciaux", 5), ("Conformité / Compliance", 4), ("Négociation", 5), ("Contentieux", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "C1"), ("Malinké", "B1")],
        "interets":    ["Arbitrage international", "Tennis", "Voyages"],
        "projets": [
            {"titre": "Programme de conformité anti-corruption CFAO", "contexte": "Renforcer le dispositif de conformité groupe en Afrique de l'Ouest.", "realisation": "Élaboration de la charte, formation de 200 collaborateurs, cartographie des risques.", "url": "", "debut": date(2019, 4, 1), "fin": date(2020, 3, 31)},
            {"titre": "Due diligence acquisition TotalEnergies", "contexte": "Opération d'acquisition de 15 stations-service.", "realisation": "Revue juridique complète, identification de risques majeurs, renégociation du prix.", "url": "", "debut": date(2016, 1, 1), "fin": date(2016, 12, 31)},
        ],
        "benevolats": [{"titre": "Consultations juridiques gratuites", "organisation": "Barreau de Côte d'Ivoire", "debut": date(2015, 6, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/awa-toure-juriste")],
    },

    # ── 40 ── PROMAN ──────────────────────────────────────────────────────────
    {
        "prenom": "Bertin", "nom": "ZADI", "sexe": "Homme",
        "email": "bertin.zadi@demo.test", "telephone": "+225 07 25 36 47 58",
        "naissance": date(1984, 10, 21), "nationalite": "Ivoirienne",
        "adresse": "Vridi Zone Industrielle", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "ABCDE", "titre": "Technicien Maintenance Industrielle",
        "secteur": "Industrie manufacturière",
        "biographie": "Technicien de maintenance industrielle avec 15 ans d'expérience en agroalimentaire. Expert en maintenance préventive et curative de lignes de production automatisées.",
        "profilCV": "Technicien maintenance industrielle · 15 ans · Automates, pneumatique, GMAO, maintenance préventive.",
        "anneePremEmploi": 2008, "mobilite": "Local", "contrat": "CDI",
        "slogan": "Zéro panne, zéro arrêt.",
        "couleur": "#003366", "portfolioFichier": "proman",
        "experiences": [
            {"entreprise": "SOLIBRA (Heineken Côte d'Ivoire)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2014, 5, 1), "fin": None, "enCours": True, "description": "Maintenance préventive et curative des lignes d'embouteillage. Diagnostic de pannes automates Siemens. Réduction des arrêts non planifiés de 30%.", "poste": "Technicien Maintenance Senior", "missionClient": None},
            {"entreprise": "SIFCA (usine de transformation)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2008, 6, 1), "fin": date(2014, 4, 30), "enCours": False, "description": "Maintenance électromécanique des équipements de production. Gestion du stock de pièces détachées.", "poste": "Technicien Électromécanicien", "missionClient": None},
        ],
        "formations": [
            {"diplome": "BTS Maintenance Industrielle", "ecole": "Lycée Technique d'Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2006, 9, 1), "fin": date(2008, 6, 30), "niveau": "BAC +2", "desc": "Spécialité électromécanique et automatismes industriels."},
        ],
        "competences": [("Automates Siemens", 5), ("Pneumatique/Hydraulique", 5), ("GMAO", 4), ("Électrotechnique", 5), ("Diagnostic de pannes", 5)],
        "langues":     [("Français", "C1"), ("Bété", "C2"), ("Anglais", "A2")],
        "interets":    ["Mécanique automobile", "Football", "Bricolage"],
        "projets": [
            {"titre": "Réduction des arrêts machine SOLIBRA", "contexte": "Taux de pannes non planifiées élevé sur ligne d'embouteillage.", "realisation": "Mise en place d'un plan de maintenance préventive renforcé. Arrêts réduits de 30%.", "url": "", "debut": date(2019, 1, 1), "fin": date(2019, 12, 31)},
            {"titre": "Déploiement GMAO SOLIBRA", "contexte": "Suivi papier des interventions, peu de traçabilité.", "realisation": "Participation au déploiement du logiciel GMAO, formation de 12 techniciens.", "url": "", "debut": date(2021, 1, 1), "fin": date(2021, 6, 30)},
        ],
        "benevolats": [{"titre": "Formateur technique bénévole", "organisation": "Centre de Formation Professionnelle de Vridi", "debut": date(2017, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/bertin-zadi")],
    },

    # ── 41 ── PROMAN-GLASS ────────────────────────────────────────────────────
    {
        "prenom": "Solange", "nom": "AMANI", "sexe": "Femme",
        "email": "solange.amani@demo.test", "telephone": "+225 05 36 47 58 69",
        "naissance": date(1992, 7, 16), "nationalite": "Ivoirienne",
        "adresse": "Cocody Angré", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Chargée de Recrutement RH",
        "secteur": "Ressources Humaines",
        "biographie": "Professionnelle RH spécialisée en recrutement avec 6 ans d'expérience en cabinet et entreprise. Je combine sourcing digital et évaluation rigoureuse pour identifier les meilleurs talents.",
        "profilCV": "Chargée de recrutement · 6 ans · Sourcing digital, entretiens structurés, marque employeur, ATS.",
        "anneePremEmploi": 2018, "mobilite": "National", "contrat": "CDI",
        "slogan": "Le bon talent, au bon endroit.",
        "couleur": "#E85D4A", "portfolioFichier": "proman-glass",
        "experiences": [
            {"entreprise": "Société Générale Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2021, 2, 1), "fin": None, "enCours": True, "description": "Recrutement de profils cadres et techniques (60 postes/an). Pilotage de la marque employeur sur les réseaux sociaux.", "poste": "Chargée de Recrutement Senior", "missionClient": None},
            {"entreprise": "Cabinet Adexen Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2018, 6, 1), "fin": date(2021, 1, 31), "enCours": False, "description": "Recrutement pour clients multisectoriels (mines, télécoms, FMCG). Sourcing LinkedIn et évaluation de compétences.", "poste": "Consultante en Recrutement", "missionClient": {"client": "Barrick Gold CI", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2019, 3, 1), "fin": date(2019, 10, 31), "desc": "Campagne de recrutement de 25 ingénieurs miniers en 6 mois."}},
        ],
        "formations": [
            {"diplome": "Master Ressources Humaines", "ecole": "ISTC Polytechnique Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2016, 9, 1), "fin": date(2018, 6, 30), "niveau": "Bac+5", "desc": "Spécialité gestion des talents et recrutement."},
            {"diplome": "Licence Psychologie du Travail", "ecole": "Université FHB Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2013, 9, 1), "fin": date(2016, 6, 30), "niveau": "BAC +3", "desc": "Mention Bien."},
        ],
        "competences": [("Sourcing LinkedIn", 5), ("Entretiens structurés", 5), ("ATS / SIRH", 4), ("Marque employeur", 4), ("Évaluation de compétences", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2")],
        "interets":    ["Développement personnel", "Danse", "Voyages"],
        "projets": [
            {"titre": "Campagne recrutement Barrick Gold", "contexte": "Besoin urgent de 25 ingénieurs miniers.", "realisation": "Sourcing ciblé, 25 postes pourvus en 6 mois, taux de rétention à 1 an de 92%.", "url": "", "debut": date(2019, 3, 1), "fin": date(2019, 10, 31)},
            {"titre": "Refonte marque employeur SGCI", "contexte": "Faible visibilité RH de la banque auprès des jeunes diplômés.", "realisation": "Stratégie de contenu LinkedIn, partenariats écoles, +150% de candidatures spontanées.", "url": "", "debut": date(2022, 1, 1), "fin": date(2022, 8, 31)},
        ],
        "benevolats": [{"titre": "Coach CV bénévole", "organisation": "Association des Jeunes Diplômés CI", "debut": date(2020, 2, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/solange-amani-rh")],
    },

    # ── 42 ── ORANGE-VIBRANT ──────────────────────────────────────────────────
    {
        "prenom": "Yacouba", "nom": "SANGARE", "sexe": "Homme",
        "email": "yacouba.sangare@demo.test", "telephone": "+225 07 47 58 69 70",
        "naissance": date(1988, 3, 9), "nationalite": "Ivoirienne",
        "adresse": "Bingerville Centre", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Ingénieur Agronome",
        "secteur": "Agriculture & Agro-alimentaire",
        "biographie": "Ingénieur agronome avec 11 ans d'expérience dans les filières cacao et hévéa. J'accompagne les coopératives agricoles dans l'amélioration de leurs rendements et la certification durable.",
        "profilCV": "Ingénieur agronome · 11 ans · Filière cacao, certification durable, agronomie tropicale, appui aux coopératives.",
        "anneePremEmploi": 2012, "mobilite": "National", "contrat": "CDI",
        "slogan": "Cultiver la performance durable.",
        "couleur": "#2A9D8F", "portfolioFichier": "orange-vibrant",
        "experiences": [
            {"entreprise": "SIFCA", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2017, 6, 1), "fin": None, "enCours": True, "description": "Appui technique à 40 coopératives cacaoyères. Programme de certification Rainforest Alliance. Formation de 500 producteurs par an.", "poste": "Ingénieur Agronome Senior", "missionClient": None},
            {"entreprise": "Conseil du Café-Cacao", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2012, 9, 1), "fin": date(2017, 5, 31), "enCours": False, "description": "Suivi agronomique de parcelles pilotes. Vulgarisation des bonnes pratiques agricoles auprès des planteurs.", "poste": "Agent Technique Agricole", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Ingénieur Agronome", "ecole": "INPHB Yamoussoukro", "ville": "Yamoussoukro", "pays": "COTE D'IVOIRE", "debut": date(2009, 9, 1), "fin": date(2012, 6, 30), "niveau": "Bac+5", "desc": "Spécialité productions végétales tropicales."},
        ],
        "competences": [("Agronomie tropicale", 5), ("Certification durable", 4), ("Formation de producteurs", 5), ("Filière cacao", 5), ("Gestion de projet agricole", 4)],
        "langues":     [("Français", "C2"), ("Dioula", "C2"), ("Anglais", "B1")],
        "interets":    ["Agriculture biologique", "Football", "Randonnée"],
        "projets": [
            {"titre": "Certification Rainforest Alliance", "contexte": "40 coopératives à certifier en 2 ans.", "realisation": "Accompagnement complet, 38 coopératives certifiées, +18% de prix de vente moyen pour les producteurs.", "url": "", "debut": date(2019, 1, 1), "fin": date(2020, 12, 31)},
            {"titre": "Programme d'agroforesterie cacao", "contexte": "Lutte contre la déforestation liée à la culture du cacao.", "realisation": "Plantation de 50 000 arbres d'ombrage sur 2 000 hectares avec 800 producteurs.", "url": "", "debut": date(2021, 1, 1), "fin": date(2022, 12, 31)},
        ],
        "benevolats": [{"titre": "Formateur agriculture durable", "organisation": "ONG Agri+ CI", "debut": date(2016, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/yacouba-sangare")],
    },

    # ── 43 ── SNAPFOLIO ───────────────────────────────────────────────────────
    {
        "prenom": "Carine", "nom": "LOBA", "sexe": "Femme",
        "email": "carine.loba@demo.test", "telephone": "+225 05 58 69 70 81",
        "naissance": date(1990, 11, 4), "nationalite": "Ivoirienne",
        "adresse": "Cocody Riviera Golf", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Architecte",
        "secteur": "BTP & Génie Civil",
        "biographie": "Architecte diplômée avec 9 ans d'expérience en conception de bâtiments résidentiels et tertiaires. Passionnée par l'architecture bioclimatique adaptée au climat ivoirien.",
        "profilCV": "Architecte · 9 ans · Conception résidentielle et tertiaire, architecture bioclimatique, AutoCAD, Revit.",
        "anneePremEmploi": 2015, "mobilite": "National", "contrat": "CDI",
        "slogan": "Concevoir des espaces qui respirent.",
        "couleur": "#9333ea", "portfolioFichier": "snapfolio",
        "experiences": [
            {"entreprise": "Atelier d'Architecture Koffi & Associés", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 3, 1), "fin": None, "enCours": True, "description": "Conception de programmes résidentiels haut de gamme et bureaux. Suivi de chantier et coordination des bureaux d'études.", "poste": "Architecte Associée", "missionClient": None},
            {"entreprise": "Cabinet ARKIA Design", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2015, 9, 1), "fin": date(2019, 2, 28), "enCours": False, "description": "Conception de logements sociaux et petits équipements publics. Modélisation 3D et permis de construire.", "poste": "Architecte Junior", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Diplôme d'État d'Architecte", "ecole": "École Africaine des Métiers de l'Architecture et de l'Urbanisme (EAMAU)", "ville": "Lomé", "pays": "TOGO", "debut": date(2010, 9, 1), "fin": date(2015, 6, 30), "niveau": "Bac+5", "desc": "Diplôme reconnu par l'Ordre des Architectes de Côte d'Ivoire."},
        ],
        "competences": [("AutoCAD", 5), ("Revit BIM", 4), ("Architecture bioclimatique", 5), ("SketchUp", 4), ("Suivi de chantier", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Ewé", "B1")],
        "interets":    ["Urbanisme", "Photographie d'architecture", "Voyages"],
        "projets": [
            {"titre": "Résidence Les Palmiers Riviera", "contexte": "Programme résidentiel de 24 villas bioclimatiques.", "realisation": "Conception complète, réduction de 30% des besoins en climatisation par l'orientation et la ventilation naturelle.", "url": "", "debut": date(2020, 1, 1), "fin": date(2021, 6, 30)},
            {"titre": "Extension École Primaire Bingerville", "contexte": "Équipement public pour une commune en croissance.", "realisation": "Conception de 8 salles de classe bioclimatiques, livré dans le budget alloué par l'État.", "url": "", "debut": date(2017, 3, 1), "fin": date(2018, 1, 31)},
        ],
        "benevolats": [{"titre": "Conception bénévole", "organisation": "Architectes Sans Frontières CI", "debut": date(2018, 9, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/carine-loba"), ("instagram", "https://instagram.com/carine.archi")],
    },

    # ── 44 ── STYLE ───────────────────────────────────────────────────────────
    {
        "prenom": "Franck", "nom": "DJE", "sexe": "Homme",
        "email": "franck.dje@demo.test", "telephone": "+225 07 69 70 81 92",
        "naissance": date(1993, 4, 25), "nationalite": "Ivoirienne",
        "adresse": "Plateau, Immeuble CRRAE-UMOA", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Analyste Financier",
        "secteur": "Services financiers",
        "biographie": "Analyste financier avec 6 ans d'expérience en banque d'investissement et gestion d'actifs. Titulaire CFA Niveau 3, je réalise des analyses de valorisation et de risque pour des décisions d'investissement éclairées.",
        "profilCV": "Analyste financier · 6 ans · Valorisation d'entreprises, modélisation financière, marchés obligataires UEMOA.",
        "anneePremEmploi": 2017, "mobilite": "International", "contrat": "CDI",
        "slogan": "Analyser pour mieux investir.",
        "couleur": "#1565C0", "portfolioFichier": "style",
        "experiences": [
            {"entreprise": "BOA Côte d'Ivoire (Bank of Africa)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 6, 1), "fin": None, "enCours": True, "description": "Analyse de portefeuille obligataire UEMOA. Modélisation financière pour comité de crédit entreprises. Veille macroéconomique régionale.", "poste": "Analyste Financier Senior", "missionClient": None},
            {"entreprise": "Hudson & Cie Gestion d'Actifs", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2017, 9, 1), "fin": date(2020, 5, 31), "enCours": False, "description": "Analyse et valorisation d'entreprises cotées à la BRVM. Rédaction de notes de recherche sectorielles.", "poste": "Analyste Junior", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master Finance de Marché", "ecole": "CESAG Dakar", "ville": "Dakar", "pays": "SENEGAL", "debut": date(2015, 9, 1), "fin": date(2017, 6, 30), "niveau": "Bac+5", "desc": "Spécialité marchés financiers et gestion de portefeuille."},
            {"diplome": "Licence Économie", "ecole": "Université FHB Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2012, 9, 1), "fin": date(2015, 6, 30), "niveau": "BAC +3", "desc": "Mention Bien."},
        ],
        "competences": [("Modélisation financière", 5), ("Valorisation d'entreprise", 5), ("Bloomberg Terminal", 4), ("Excel VBA", 4), ("Analyse macroéconomique", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "C1")],
        "interets":    ["Marchés financiers", "Course à pied", "Échecs"],
        "projets": [
            {"titre": "Note sectorielle télécoms BRVM", "contexte": "Manque d'analyses locales sur le secteur télécoms coté.", "realisation": "Publication d'une note de recherche de référence, reprise par 3 médias économiques.", "url": "", "debut": date(2019, 1, 1), "fin": date(2019, 3, 31)},
            {"titre": "Modèle de scoring crédit entreprises BOA", "contexte": "Homogénéiser l'analyse de risque des dossiers de crédit.", "realisation": "Développement d'un modèle Excel/VBA adopté par le comité de crédit régional.", "url": "", "debut": date(2021, 6, 1), "fin": date(2021, 12, 31)},
        ],
        "benevolats": [{"titre": "Formateur éducation financière", "organisation": "Association CFA Society CI", "debut": date(2019, 9, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/franck-dje")],
    },

    # ── 45 ── CLINIC-PRO ──────────────────────────────────────────────────────
    {
        "prenom": "Rachel", "nom": "AKE", "sexe": "Femme",
        "email": "rachel.ake@demo.test", "telephone": "+225 05 70 81 92 03",
        "naissance": date(1987, 6, 18), "nationalite": "Ivoirienne",
        "adresse": "Marcory Zone 4", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Pharmacienne",
        "secteur": "Santé & Pharmaceutique",
        "biographie": "Pharmacienne diplômée avec 12 ans d'expérience en officine et industrie pharmaceutique. Experte en pharmacovigilance et conseil patient, j'allie rigueur scientifique et sens du service.",
        "profilCV": "Pharmacienne · 12 ans · Officine, pharmacovigilance, gestion des stocks, conseil patient, réglementation pharmaceutique.",
        "anneePremEmploi": 2011, "mobilite": "Local", "contrat": "CDI",
        "slogan": "La santé, un engagement quotidien.",
        "couleur": "#2A9D8F", "portfolioFichier": "clinic-pro",
        "experiences": [
            {"entreprise": "Laboratoire Pharmacie de la Riviera", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2016, 1, 1), "fin": None, "enCours": True, "description": "Titulaire adjointe d'une officine de 8 collaborateurs. Gestion des approvisionnements et de la pharmacovigilance. Conseil patient quotidien.", "poste": "Pharmacienne Titulaire Adjointe", "missionClient": None},
            {"entreprise": "DENK Pharma Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2011, 9, 1), "fin": date(2015, 12, 31), "enCours": False, "description": "Chargée des affaires réglementaires pour l'enregistrement de médicaments génériques. Relations avec la DPML.", "poste": "Pharmacienne Affaires Réglementaires", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Doctorat en Pharmacie", "ecole": "Université FHB Abidjan (UFR Sciences Pharmaceutiques)", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2005, 9, 1), "fin": date(2011, 6, 30), "niveau": "BAC +6", "desc": "Spécialité pharmacie d'officine et industrielle."},
        ],
        "competences": [("Pharmacovigilance", 5), ("Conseil patient", 5), ("Gestion des stocks", 4), ("Réglementation pharmaceutique", 4), ("Management d'équipe", 3)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Baoulé", "C1")],
        "interets":    ["Nutrition", "Natation", "Bénévolat médical"],
        "projets": [
            {"titre": "Programme de pharmacovigilance renforcée", "contexte": "Sous-déclaration des effets indésirables observée.", "realisation": "Mise en place d'un protocole de déclaration systématique, formation de l'équipe. +40% de déclarations transmises à la DPML.", "url": "", "debut": date(2020, 1, 1), "fin": date(2020, 6, 30)},
            {"titre": "Journée dépistage diabète et hypertension", "contexte": "Sensibilisation de la clientèle du quartier.", "realisation": "Organisation annuelle, plus de 300 personnes dépistées chaque édition depuis 2018.", "url": "", "debut": date(2018, 1, 1), "fin": None},
        ],
        "benevolats": [{"titre": "Consultations pharmaceutiques gratuites", "organisation": "Ordre des Pharmaciens de Côte d'Ivoire", "debut": date(2017, 3, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/rachel-ake-pharmacienne")],
    },

    # ── 46 ── PROMAN-PRO ──────────────────────────────────────────────────────
    {
        "prenom": "Boubacar", "nom": "KONE", "sexe": "Homme",
        "email": "boubacar.kone@demo.test", "telephone": "+225 07 81 92 03 14",
        "naissance": date(1983, 8, 30), "nationalite": "Ivoirienne",
        "adresse": "Port-Bouët", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "ABCDE", "titre": "Responsable Transport & Logistique",
        "secteur": "Logistique & Transport",
        "biographie": "Responsable logistique avec 16 ans d'expérience dans le transport routier et la gestion de flotte. Spécialiste de l'optimisation des coûts et des délais de livraison en Afrique de l'Ouest.",
        "profilCV": "Responsable transport & logistique · 16 ans · Gestion de flotte, optimisation de tournées, douane, supply chain régionale.",
        "anneePremEmploi": 2008, "mobilite": "International", "contrat": "CDI",
        "slogan": "Livrer juste, livrer à temps.",
        "couleur": "#F77F00", "portfolioFichier": "proman-pro",
        "experiences": [
            {"entreprise": "Bolloré Transport & Logistics CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2015, 4, 1), "fin": None, "enCours": True, "description": "Gestion d'une flotte de 120 véhicules pour le transport de marchandises vers le Mali et le Burkina Faso. Optimisation des coûts carburant (-18%).", "poste": "Responsable Transport Régional", "missionClient": None},
            {"entreprise": "SDV Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2008, 3, 1), "fin": date(2015, 3, 31), "enCours": False, "description": "Coordination des opérations de dédouanement et de transit au Port d'Abidjan. Suivi des expéditions internationales.", "poste": "Agent Logistique Senior", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Licence Transport et Logistique", "ecole": "INPHB Yamoussoukro", "ville": "Yamoussoukro", "pays": "COTE D'IVOIRE", "debut": date(2005, 9, 1), "fin": date(2008, 6, 30), "niveau": "BAC +3", "desc": "Spécialité logistique internationale et transit douanier."},
        ],
        "competences": [("Gestion de flotte", 5), ("Optimisation logistique", 5), ("Douane et transit", 4), ("Supply chain", 4), ("Négociation fournisseurs", 4)],
        "langues":     [("Français", "C2"), ("Dioula", "C2"), ("Anglais", "B1")],
        "interets":    ["Football", "Mécanique", "Voyages en Afrique de l'Ouest"],
        "projets": [
            {"titre": "Optimisation des tournées régionales", "contexte": "Coûts carburant en hausse constante sur les corridors Mali/Burkina.", "realisation": "Mise en place d'un logiciel de planification de tournées. Réduction des coûts carburant de 18%.", "url": "", "debut": date(2019, 1, 1), "fin": date(2019, 9, 30)},
            {"titre": "Digitalisation du suivi de flotte", "contexte": "Absence de géolocalisation en temps réel des 120 véhicules.", "realisation": "Déploiement d'un système GPS et de tableaux de bord de suivi. Amélioration de la ponctualité de 22%.", "url": "", "debut": date(2020, 5, 1), "fin": date(2021, 2, 28)},
        ],
        "benevolats": [{"titre": "Formateur conduite sécuritaire", "organisation": "Sécurité Routière Côte d'Ivoire", "debut": date(2016, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/boubacar-kone-logistique")],
    },

    # ── 47 ── PROMAN-GLASS ────────────────────────────────────────────────────
    {
        "prenom": "Vanessa", "nom": "KRAGBE", "sexe": "Femme",
        "email": "vanessa.kragbe@demo.test", "telephone": "+225 05 92 03 14 25",
        "naissance": date(1997, 2, 14), "nationalite": "Ivoirienne",
        "adresse": "Cocody Saint-Jean", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Community Manager",
        "secteur": "Communication & Marketing",
        "biographie": "Community manager créative avec 4 ans d'expérience, spécialisée dans l'animation de communautés pour des marques lifestyle et food. Toujours à l'affût des dernières tendances social media.",
        "profilCV": "Community manager · 4 ans · TikTok, Instagram, création de contenu, veille tendances, gestion de communauté.",
        "anneePremEmploi": 2020, "mobilite": "National", "contrat": "CDI",
        "slogan": "Créer du lien, un post à la fois.",
        "couleur": "#E85D4A", "portfolioFichier": "proman-glass",
        "experiences": [
            {"entreprise": "Groupe NSIA", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2022, 3, 1), "fin": None, "enCours": True, "description": "Animation quotidienne des communautés Instagram et TikTok (150k+ abonnés). Création de contenus courts et modération.", "poste": "Community Manager", "missionClient": None},
            {"entreprise": "Agence Yolo Digital", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 9, 1), "fin": date(2022, 2, 28), "enCours": False, "description": "Gestion de comptes clients food et lifestyle. Création de contenus photo/vidéo pour réseaux sociaux.", "poste": "Assistante Community Manager", "missionClient": None},
        ],
        "formations": [
            {"diplome": "BTS Communication", "ecole": "ISTC Polytechnique Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2018, 9, 1), "fin": date(2020, 6, 30), "niveau": "BAC +2", "desc": "Spécialité communication digitale."},
        ],
        "competences": [("TikTok Ads", 4), ("Création de contenu vidéo", 5), ("Instagram/Meta", 5), ("CapCut/Premiere Rush", 4), ("Veille tendances", 5)],
        "langues":     [("Français", "C2"), ("Anglais", "B1"), ("Nouchi", "C2")],
        "interets":    ["TikTok", "Danse", "Cuisine créative"],
        "projets": [
            {"titre": "Lancement compte TikTok NSIA", "contexte": "Marque absente de TikTok, cible jeune non touchée.", "realisation": "Création du compte, stratégie éditoriale, 45 000 abonnés en 8 mois.", "url": "", "debut": date(2022, 5, 1), "fin": date(2023, 1, 31)},
            {"titre": "Campagne UGC restaurant partenaire", "contexte": "Faible notoriété locale d'un client food.", "realisation": "Campagne d'influence micro-créateurs, +80% de couverture géolocalisée en 1 mois.", "url": "", "debut": date(2021, 6, 1), "fin": date(2021, 7, 31)},
        ],
        "benevolats": [{"titre": "Bénévole réseaux sociaux", "organisation": "Festival Abidjan Design Week", "debut": date(2021, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/vanessa-kragbe"), ("instagram", "https://instagram.com/vanessa.kragbe"), ("x", "https://x.com/vanessakcm")],
    },

    # ── 48 ── RETRO-MAG ───────────────────────────────────────────────────────
    {
        "prenom": "Armand", "nom": "TIA", "sexe": "Homme",
        "email": "armand.tia@demo.test", "telephone": "+225 07 03 14 25 36",
        "naissance": date(1985, 1, 8), "nationalite": "Ivoirienne",
        "adresse": "Abobo Baoulé", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Électricien Industriel",
        "secteur": "Industrie manufacturière",
        "biographie": "Électricien industriel avec 14 ans d'expérience en câblage, automatismes et maintenance électrique de sites industriels. Habilité haute et basse tension.",
        "profilCV": "Électricien industriel · 14 ans · Habilitation HT/BT, automatismes, câblage industriel, dépannage électrique.",
        "anneePremEmploi": 2009, "mobilite": "National", "contrat": "CDI",
        "slogan": "L'électricité maîtrisée, la production assurée.",
        "couleur": "#C9A227", "portfolioFichier": "retro-mag",
        "experiences": [
            {"entreprise": "CIE (Compagnie Ivoirienne d'Électricité)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2013, 5, 1), "fin": None, "enCours": True, "description": "Maintenance des postes de distribution HT/BT. Intervention sur incidents réseau. Habilitation électrique niveau B2V/BR.", "poste": "Électricien Industriel Senior", "missionClient": None},
            {"entreprise": "Nestlé Côte d'Ivoire (usine)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2009, 6, 1), "fin": date(2013, 4, 30), "enCours": False, "description": "Câblage et maintenance des équipements électriques de production. Installation d'automates.", "poste": "Électricien de Production", "missionClient": None},
        ],
        "formations": [
            {"diplome": "BTS Électrotechnique", "ecole": "Lycée Technique d'Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2007, 9, 1), "fin": date(2009, 6, 30), "niveau": "BAC +2", "desc": "Spécialité électrotechnique industrielle."},
        ],
        "competences": [("Habilitation HT/BT", 5), ("Automatismes industriels", 4), ("Câblage industriel", 5), ("Dépannage électrique", 5), ("Lecture de schémas électriques", 5)],
        "langues":     [("Français", "C1"), ("Baoulé", "C2"), ("Anglais", "A2")],
        "interets":    ["Électronique amateur", "Football", "Football amateur"],
        "projets": [
            {"titre": "Modernisation poste HT Abobo", "contexte": "Équipements vieillissants, risque de coupures fréquentes.", "realisation": "Remplacement de disjoncteurs et cellules HT, réduction des incidents de 45%.", "url": "", "debut": date(2020, 1, 1), "fin": date(2020, 10, 31)},
            {"titre": "Installation automates ligne conditionnement Nestlé", "contexte": "Automatisation d'une ligne manuelle.", "realisation": "Câblage complet et mise en service, gain de productivité de 25%.", "url": "", "debut": date(2011, 3, 1), "fin": date(2011, 9, 30)},
        ],
        "benevolats": [{"titre": "Formateur électricité de base", "organisation": "Centre de Formation Professionnelle d'Abobo", "debut": date(2018, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/armand-tia")],
    },

    # ── 49 ── CYBER-NEON ──────────────────────────────────────────────────────
    {
        "prenom": "Hortense", "nom": "GONO", "sexe": "Femme",
        "email": "hortense.gono@demo.test", "telephone": "+225 05 14 25 36 47",
        "naissance": date(1991, 10, 3), "nationalite": "Ivoirienne",
        "adresse": "Yopougon Selmer", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Sage-Femme",
        "secteur": "Santé",
        "biographie": "Sage-femme diplômée avec 9 ans d'expérience en maternité hospitalière. Engagée pour la santé maternelle et néonatale, je forme aussi les futures sages-femmes.",
        "profilCV": "Sage-femme · 9 ans · Accouchement, suivi de grossesse, planification familiale, encadrement d'étudiantes.",
        "anneePremEmploi": 2015, "mobilite": "Local", "contrat": "CDI",
        "slogan": "Accompagner la vie dès son premier souffle.",
        "couleur": "#2A9D8F", "portfolioFichier": "cyber-neon",
        "experiences": [
            {"entreprise": "CHU de Yopougon", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2018, 3, 1), "fin": None, "enCours": True, "description": "Suivi de grossesses à risque et accouchements (150+ par an). Encadrement de 6 étudiantes sages-femmes par semestre.", "poste": "Sage-Femme Senior", "missionClient": None},
            {"entreprise": "Centre de Santé Urbain de Yopougon", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2015, 4, 1), "fin": date(2018, 2, 28), "enCours": False, "description": "Consultations prénatales, planification familiale, sensibilisation communautaire.", "poste": "Sage-Femme", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Diplôme d'État de Sage-Femme", "ecole": "INFAS Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2012, 9, 1), "fin": date(2015, 6, 30), "niveau": "BAC +3", "desc": "Formation en maïeutique et santé maternelle."},
        ],
        "competences": [("Accouchement", 5), ("Suivi de grossesse", 5), ("Planification familiale", 4), ("Urgences obstétricales", 4), ("Encadrement d'étudiantes", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B1"), ("Guéré", "C1")],
        "interets":    ["Santé communautaire", "Chant", "Couture"],
        "projets": [
            {"titre": "Programme de réduction de la mortalité maternelle", "contexte": "Taux de complications élevé dans le district de Yopougon.", "realisation": "Formation de 30 agents de santé communautaire au dépistage précoce des risques.", "url": "", "debut": date(2020, 1, 1), "fin": date(2020, 12, 31)},
            {"titre": "Sensibilisation planification familiale", "contexte": "Faible taux de recours à la contraception dans le quartier.", "realisation": "Campagnes de sensibilisation mensuelles, +35% de nouvelles utilisatrices en 1 an.", "url": "", "debut": date(2019, 1, 1), "fin": date(2019, 12, 31)},
        ],
        "benevolats": [{"titre": "Sensibilisation santé maternelle", "organisation": "UNFPA Côte d'Ivoire (bénévolat local)", "debut": date(2017, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/hortense-gono")],
    },

    # ── 50 ── TECH-DASHBOARD ──────────────────────────────────────────────────
    {
        "prenom": "Ismael", "nom": "BAMBA", "sexe": "Homme",
        "email": "ismael.bamba@demo.test", "telephone": "+225 07 25 36 47 58",
        "naissance": date(1994, 12, 29), "nationalite": "Ivoirienne",
        "adresse": "Cocody Deux Plateaux Vallon", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Data Scientist",
        "secteur": "Numérique (Tech)",
        "biographie": "Data scientist avec 5 ans d'expérience en machine learning appliqué à la finance et aux télécoms. Je conçois des modèles prédictifs qui créent une réelle valeur métier.",
        "profilCV": "Data scientist · 5 ans · Machine learning, Python, scoring, NLP, MLOps, déploiement de modèles.",
        "anneePremEmploi": 2019, "mobilite": "International", "contrat": "CDI",
        "slogan": "Des modèles qui décident juste.",
        "couleur": "#1a1a2e", "portfolioFichier": "tech-dashboard",
        "experiences": [
            {"entreprise": "Ecobank Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2021, 9, 1), "fin": None, "enCours": True, "description": "Conception de modèles de scoring crédit pour la clientèle particuliers. Détection de fraude en temps réel par machine learning.", "poste": "Data Scientist Senior", "missionClient": None},
            {"entreprise": "Orange Digital Center CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 5, 1), "fin": date(2021, 8, 31), "enCours": False, "description": "Développement de modèles NLP pour l'analyse de la satisfaction client (chatbot et centres d'appels).", "poste": "Data Scientist Junior", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Ingénieur Statistique et Data Science", "ecole": "ENSEA Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2016, 9, 1), "fin": date(2019, 6, 30), "niveau": "Bac+5", "desc": "Spécialité intelligence artificielle et statistiques appliquées."},
        ],
        "competences": [("Python / scikit-learn", 5), ("Machine Learning", 5), ("NLP", 4), ("SQL", 4), ("MLOps / Docker", 3)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Dioula", "B1")],
        "interets":    ["Compétitions Kaggle", "Échecs", "Course à pied"],
        "projets": [
            {"titre": "Modèle de détection de fraude Ecobank", "contexte": "Augmentation des tentatives de fraude sur les transactions mobiles.", "realisation": "Modèle de détection en temps réel, réduction des pertes fraude de 40%.", "url": "", "debut": date(2022, 3, 1), "fin": date(2022, 10, 31)},
            {"titre": "Chatbot NLP Orange Digital Center", "contexte": "Volume élevé de demandes clients répétitives au centre d'appels.", "realisation": "Chatbot en français traitant 65% des requêtes sans intervention humaine.", "url": "https://github.com/demo/orange-chatbot", "debut": date(2020, 1, 1), "fin": date(2020, 9, 30)},
        ],
        "benevolats": [{"titre": "Mentor data science", "organisation": "Orange Digital Center CI", "debut": date(2021, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/ismael-bamba"), ("github", "https://github.com/ismaelbamba")],
    },

    # ── 51 ── ORANGE-VIBRANT ──────────────────────────────────────────────────
    {
        "prenom": "Clarisse", "nom": "N'DRI", "sexe": "Femme",
        "email": "clarisse.ndri@demo.test", "telephone": "+225 05 36 47 58 69",
        "naissance": date(1996, 7, 21), "nationalite": "Ivoirienne",
        "adresse": "Cocody Danga Nord", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Assistante de Direction",
        "secteur": "Ressources Humaines",
        "biographie": "Assistante de direction bilingue avec 5 ans d'expérience auprès de dirigeants d'entreprise. Organisée et discrète, je gère agendas complexes, déplacements et communication interne.",
        "profilCV": "Assistante de direction · 5 ans · Gestion d'agenda, organisation d'événements, communication interne, bilingue français-anglais.",
        "anneePremEmploi": 2019, "mobilite": "National", "contrat": "CDI",
        "slogan": "L'organisation au service de la performance.",
        "couleur": "#F77F00", "portfolioFichier": "orange-vibrant",
        "experiences": [
            {"entreprise": "CANAL+ Afrique", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2021, 6, 1), "fin": None, "enCours": True, "description": "Assistante de la Direction Générale Afrique de l'Ouest. Gestion d'agenda, organisation de comités de direction et déplacements internationaux.", "poste": "Assistante de Direction Générale", "missionClient": None},
            {"entreprise": "PETROCI Holding", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 2, 1), "fin": date(2021, 5, 31), "enCours": False, "description": "Assistante d'un directeur de département. Gestion administrative, rédaction de comptes rendus, accueil de délégations.", "poste": "Assistante de Direction", "missionClient": None},
        ],
        "formations": [
            {"diplome": "BTS Assistanat de Direction", "ecole": "ISTC Polytechnique Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2017, 9, 1), "fin": date(2019, 6, 30), "niveau": "BAC +2", "desc": "Spécialité assistanat trilingue."},
        ],
        "competences": [("Gestion d'agenda", 5), ("Pack Office", 5), ("Organisation d'événements", 4), ("Rédaction professionnelle", 4), ("Communication interne", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "C1"), ("Espagnol", "A2")],
        "interets":    ["Protocole et étiquette", "Voyages", "Lecture"],
        "projets": [
            {"titre": "Organisation du séminaire annuel CANAL+ Afrique", "contexte": "Rassemblement de 120 cadres de 8 pays africains.", "realisation": "Coordination logistique complète (voyages, hébergement, programme), satisfaction participants 4.8/5.", "url": "", "debut": date(2022, 9, 1), "fin": date(2022, 11, 30)},
            {"titre": "Digitalisation de la gestion des agendas", "contexte": "Suivi papier générant des conflits de planning fréquents.", "realisation": "Migration vers Outlook/Teams partagé pour toute la direction, zéro conflit depuis.", "url": "", "debut": date(2021, 9, 1), "fin": date(2021, 12, 31)},
        ],
        "benevolats": [{"titre": "Bénévole organisation événementielle", "organisation": "Fondation CANAL+ Afrique", "debut": date(2022, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/clarisse-ndri")],
    },

    # ── 52 ── SNAPFOLIO ───────────────────────────────────────────────────────
    {
        "prenom": "Yao", "nom": "KOUASSI JUNIOR", "sexe": "Homme",
        "email": "yao.kouassi.junior@demo.test", "telephone": "+225 07 47 58 69 70",
        "naissance": date(1992, 5, 17), "nationalite": "Ivoirienne",
        "adresse": "Koumassi Grand Campement", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Commercial Terrain B2C",
        "secteur": "Commerce & Vente",
        "biographie": "Commercial terrain avec 8 ans d'expérience dans la grande distribution et les télécoms. Dépassement d'objectifs constant, j'excelle dans la prospection et la fidélisation client.",
        "profilCV": "Commercial terrain · 8 ans · Prospection B2C, animation de réseau de distribution, négociation, atteinte d'objectifs.",
        "anneePremEmploi": 2015, "mobilite": "National", "contrat": "CDI",
        "slogan": "Chaque client compte, chaque objectif se dépasse.",
        "couleur": "#009A44", "portfolioFichier": "snapfolio",
        "experiences": [
            {"entreprise": "MOOV Africa Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 1, 1), "fin": None, "enCours": True, "description": "Animation d'un réseau de 60 points de vente. Formation des revendeurs. Dépassement des objectifs de vente de 20% en moyenne.", "poste": "Commercial Terrain Senior", "missionClient": None},
            {"entreprise": "Prosuma (Groupe distribution)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2015, 6, 1), "fin": date(2018, 12, 31), "enCours": False, "description": "Vente directe et merchandising en grande surface. Meilleur commercial de l'année 2017.", "poste": "Commercial Grande Distribution", "missionClient": None},
        ],
        "formations": [
            {"diplome": "BTS Action Commerciale", "ecole": "Institut Supérieur de Commerce d'Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2013, 9, 1), "fin": date(2015, 6, 30), "niveau": "BAC +2", "desc": "Spécialité vente et négociation commerciale."},
        ],
        "competences": [("Prospection commerciale", 5), ("Négociation", 5), ("Animation de réseau", 4), ("CRM", 3), ("Merchandising", 4)],
        "langues":     [("Français", "C1"), ("Baoulé", "C2"), ("Anglais", "A2")],
        "interets":    ["Football", "Moto", "Musique"],
        "projets": [
            {"titre": "Extension réseau de distribution MOOV", "contexte": "Faible couverture dans les communes périphériques d'Abidjan.", "realisation": "Recrutement et formation de 15 nouveaux points de vente en 6 mois.", "url": "", "debut": date(2021, 1, 1), "fin": date(2021, 6, 30)},
            {"titre": "Programme de fidélisation revendeurs", "contexte": "Turnover élevé des revendeurs partenaires.", "realisation": "Mise en place d'un système de primes de performance, rétention des revendeurs +30%.", "url": "", "debut": date(2020, 3, 1), "fin": date(2020, 12, 31)},
        ],
        "benevolats": [{"titre": "Coach vente bénévole", "organisation": "Association des Jeunes Entrepreneurs de Koumassi", "debut": date(2019, 6, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/yao-kouassi-junior")],
    },

    # ── 53 ── CLINIC-PRO ──────────────────────────────────────────────────────
    {
        "prenom": "Marc", "nom": "ADOU", "sexe": "Homme",
        "email": "marc.adou@demo.test", "telephone": "+225 07 36 47 58 69",
        "naissance": date(1986, 3, 12), "nationalite": "Ivoirienne",
        "adresse": "Aéroport Félix Houphouët-Boigny", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Pilote de Ligne",
        "secteur": "Transport Aérien",
        "biographie": "Pilote de ligne avec 12 ans d'expérience, qualifié sur Airbus A320 et Boeing 737. Rigueur et sang-froid sont mes maîtres-mots pour assurer la sécurité de chaque vol.",
        "profilCV": "Pilote de ligne · 12 ans · Airbus A320, Boeing 737, 8 500 heures de vol, sécurité aérienne.",
        "anneePremEmploi": 2013, "mobilite": "International", "contrat": "CDI",
        "slogan": "Chaque vol commence par la rigueur.",
        "couleur": "#1565C0", "portfolioFichier": "clinic-pro",
        "experiences": [
            {"entreprise": "Air Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2016, 6, 1), "fin": None, "enCours": True, "description": "Commandant de bord sur Airbus A320, lignes régionales Afrique de l'Ouest. Plus de 5 000 heures de vol sans incident.", "poste": "Commandant de Bord", "missionClient": None},
            {"entreprise": "Air Ivoire (ex)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2013, 3, 1), "fin": date(2016, 5, 31), "enCours": False, "description": "Copilote sur vols domestiques et régionaux.", "poste": "Copilote", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Brevet de Pilote de Ligne (ATPL)", "ecole": "Académie Régionale de l'Aviation Civile", "ville": "Niamey", "pays": "NIGER", "debut": date(2010, 9, 1), "fin": date(2013, 2, 28), "niveau": "Bac+5", "desc": "Formation complète pilote de ligne, qualification multi-moteurs."},
        ],
        "competences": [("Pilotage Airbus A320", 5), ("Gestion de crise", 5), ("Anglais aéronautique", 5), ("Navigation", 5), ("Leadership d'équipage", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "C2"), ("Baoulé", "B1")],
        "interets":    ["Aéromodélisme", "Course à pied", "Voyages"],
        "projets": [
            {"titre": "Formation jeunes pilotes locaux", "contexte": "Manque de pilotes qualifiés en Afrique de l'Ouest.", "realisation": "Mentorat de 6 copilotes juniors, 3 promus commandants de bord depuis.", "url": "", "debut": date(2019, 1, 1), "fin": None},
        ],
        "benevolats": [{"titre": "Sensibilisation sécurité aérienne", "organisation": "ANAC Côte d'Ivoire", "debut": date(2018, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/marc-adou-pilote")],
    },

    # ── 54 ── SNAPFOLIO ───────────────────────────────────────────────────────
    {
        "prenom": "Josiane", "nom": "KOFFI", "sexe": "Femme",
        "email": "josiane.koffi@demo.test", "telephone": "+225 05 47 58 69 70",
        "naissance": date(1993, 9, 25), "nationalite": "Ivoirienne",
        "adresse": "Cocody Angré 9e Tranche", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Kinésithérapeute",
        "secteur": "Santé",
        "biographie": "Kinésithérapeute diplômée avec 7 ans d'expérience en rééducation fonctionnelle et sportive. J'accompagne mes patients vers une récupération complète avec une approche personnalisée.",
        "profilCV": "Kinésithérapeute · 7 ans · Rééducation fonctionnelle, kinésithérapie du sport, thérapie manuelle.",
        "anneePremEmploi": 2017, "mobilite": "Local", "contrat": "CDI",
        "slogan": "Remettre le mouvement au cœur de la vie.",
        "couleur": "#2A9D8F", "portfolioFichier": "snapfolio",
        "experiences": [
            {"entreprise": "Clinique Farah", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 3, 1), "fin": None, "enCours": True, "description": "Prise en charge de patients post-opératoires et sportifs de haut niveau. Élaboration de programmes de rééducation personnalisés.", "poste": "Kinésithérapeute Senior", "missionClient": None},
            {"entreprise": "CHU de Cocody", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2017, 4, 1), "fin": date(2020, 2, 29), "enCours": False, "description": "Rééducation en service de traumatologie. Encadrement d'étudiants kinésithérapeutes.", "poste": "Kinésithérapeute", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Diplôme d'État de Masso-Kinésithérapie", "ecole": "INFAS Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2014, 9, 1), "fin": date(2017, 6, 30), "niveau": "BAC +3", "desc": "Spécialité rééducation fonctionnelle."},
        ],
        "competences": [("Thérapie manuelle", 5), ("Rééducation fonctionnelle", 5), ("Kinésithérapie du sport", 4), ("Électrothérapie", 4), ("Relation patient", 5)],
        "langues":     [("Français", "C2"), ("Anglais", "B1"), ("Baoulé", "C1")],
        "interets":    ["Natation", "Danse", "Nutrition sportive"],
        "projets": [
            {"titre": "Programme de rééducation athlètes CIV", "contexte": "Préparation de sportifs pour les compétitions régionales.", "realisation": "Suivi de 12 athlètes, réduction du taux de rechute de blessure de 40%.", "url": "", "debut": date(2021, 1, 1), "fin": date(2021, 12, 31)},
        ],
        "benevolats": [{"titre": "Séances gratuites personnes âgées", "organisation": "Maison de Retraite de Cocody", "debut": date(2019, 5, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/josiane-koffi-kine")],
    },

    # ── 55 ── RETRO-MAG ───────────────────────────────────────────────────────
    {
        "prenom": "Parfait", "nom": "GUEI", "sexe": "Homme",
        "email": "parfait.guei@demo.test", "telephone": "+225 07 58 69 70 81",
        "naissance": date(1990, 6, 8), "nationalite": "Ivoirienne",
        "adresse": "Cocody Danga", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Régisseur Audiovisuel",
        "secteur": "Médias & Communication",
        "biographie": "Régisseur audiovisuel avec 9 ans d'expérience en télévision et événementiel. Je gère la production technique de plateaux TV et grands événements en direct.",
        "profilCV": "Régisseur audiovisuel · 9 ans · Régie plateau, montage vidéo, direct TV, gestion technique événementielle.",
        "anneePremEmploi": 2014, "mobilite": "National", "contrat": "CDI",
        "slogan": "L'image parfaite, à chaque prise.",
        "couleur": "#C9A227", "portfolioFichier": "retro-mag",
        "experiences": [
            {"entreprise": "RTI (Radiodiffusion Télévision Ivoirienne)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2018, 2, 1), "fin": None, "enCours": True, "description": "Régie technique des journaux télévisés et émissions en direct. Coordination d'une équipe de 8 techniciens.", "poste": "Régisseur Plateau Senior", "missionClient": None},
            {"entreprise": "CANAL+ Afrique", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2014, 5, 1), "fin": date(2018, 1, 31), "enCours": False, "description": "Montage et post-production d'émissions. Régie de tournages terrain.", "poste": "Technicien Audiovisuel", "missionClient": None},
        ],
        "formations": [
            {"diplome": "BTS Audiovisuel", "ecole": "ISTC Polytechnique Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2012, 9, 1), "fin": date(2014, 6, 30), "niveau": "BAC +2", "desc": "Spécialité production et réalisation audiovisuelle."},
        ],
        "competences": [("Régie plateau", 5), ("Montage vidéo", 4), ("Direct TV", 5), ("Éclairage studio", 4), ("Gestion d'équipe technique", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B1"), ("Guéré", "C1")],
        "interets":    ["Cinéma", "Photographie", "Musique"],
        "projets": [
            {"titre": "Régie technique Election présidentielle", "contexte": "Couverture en direct 24h/24 sur plusieurs jours.", "realisation": "Coordination technique sans incident majeur, audience record pour la chaîne.", "url": "", "debut": date(2020, 10, 1), "fin": date(2020, 11, 15)},
        ],
        "benevolats": [{"titre": "Formateur audiovisuel bénévole", "organisation": "Institut de la Communication d'Abidjan", "debut": date(2019, 9, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/parfait-guei")],
    },

    # ── 56 ── PROMAN-GLASS ────────────────────────────────────────────────────
    {
        "prenom": "Nina", "nom": "ABOA", "sexe": "Femme",
        "email": "nina.aboa@demo.test", "telephone": "+225 05 69 70 81 92",
        "naissance": date(1989, 1, 17), "nationalite": "Ivoirienne",
        "adresse": "Plateau, Rue des Jardins", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Chef Cuisinière",
        "secteur": "Hôtellerie & Restauration",
        "biographie": "Cheffe cuisinière passionnée par la gastronomie ivoirienne revisitée. 10 ans d'expérience en restauration haut de gamme, je dirige une brigade de 8 personnes.",
        "profilCV": "Chef cuisinière · 10 ans · Gastronomie ivoirienne, gestion de brigade, création de cartes, HACCP.",
        "anneePremEmploi": 2013, "mobilite": "National", "contrat": "CDI",
        "slogan": "La cuisine ivoirienne, réinventée.",
        "couleur": "#F77F00", "portfolioFichier": "proman-glass",
        "experiences": [
            {"entreprise": "Hôtel Ivoire (Sofitel Abidjan)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 4, 1), "fin": None, "enCours": True, "description": "Cheffe de cuisine du restaurant gastronomique. Création de la carte saisonnière. Gestion d'une brigade de 8 personnes.", "poste": "Cheffe de Cuisine", "missionClient": None},
            {"entreprise": "Restaurant La Villa Abidjanaise", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2013, 6, 1), "fin": date(2019, 3, 31), "enCours": False, "description": "Sous-cheffe puis cheffe de partie. Spécialisation cuisine fusion ivoiro-française.", "poste": "Sous-Cheffe", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Diplôme de Cuisine Professionnelle", "ecole": "École Hôtelière d'Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2011, 9, 1), "fin": date(2013, 6, 30), "niveau": "BAC +2", "desc": "Spécialité cuisine gastronomique et gestion de brigade."},
        ],
        "competences": [("Cuisine gastronomique", 5), ("Gestion de brigade", 5), ("Création de cartes", 5), ("HACCP", 4), ("Gestion des coûts matières", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Baoulé", "C1")],
        "interets":    ["Gastronomie du monde", "Jardinage", "Œnologie"],
        "projets": [
            {"titre": "Carte gastronomique 'Racines'", "contexte": "Valoriser les produits locaux ivoiriens en haute cuisine.", "realisation": "Nouvelle carte 100% produits locaux, +25% de fréquentation du restaurant.", "url": "", "debut": date(2021, 1, 1), "fin": date(2021, 6, 30)},
        ],
        "benevolats": [{"titre": "Ateliers cuisine pour jeunes défavorisés", "organisation": "Fondation Children of Africa", "debut": date(2020, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/nina-aboa-chef"), ("instagram", "https://instagram.com/nina.aboa.chef")],
    },

    # ── 57 ── TECH-DASHBOARD ──────────────────────────────────────────────────
    {
        "prenom": "Serge", "nom": "N'GORAN", "sexe": "Homme",
        "email": "serge.ngoran@demo.test", "telephone": "+225 07 70 81 92 03",
        "naissance": date(1984, 11, 30), "nationalite": "Ivoirienne",
        "adresse": "Vridi Canal", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Ingénieur Pétrolier",
        "secteur": "Ressources minières et hydrocarbures",
        "biographie": "Ingénieur pétrolier avec 15 ans d'expérience en exploration et production offshore. J'ai contribué au développement de plusieurs champs pétroliers ivoiriens.",
        "profilCV": "Ingénieur pétrolier · 15 ans · Exploration offshore, forage, réservoir, sécurité HSE industrie pétrolière.",
        "anneePremEmploi": 2009, "mobilite": "International", "contrat": "CDI",
        "slogan": "L'énergie qui fait avancer la Côte d'Ivoire.",
        "couleur": "#1a1a2e", "portfolioFichier": "tech-dashboard",
        "experiences": [
            {"entreprise": "PETROCI Holding", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2015, 3, 1), "fin": None, "enCours": True, "description": "Ingénieur réservoir sur les champs offshore CI-27 et CI-40. Coordination avec partenaires internationaux (ENI, TotalEnergies).", "poste": "Ingénieur Réservoir Senior", "missionClient": None},
            {"entreprise": "CNR International (offshore CI)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2009, 6, 1), "fin": date(2015, 2, 28), "enCours": False, "description": "Ingénieur de forage sur plateformes offshore. Suivi des opérations de production.", "poste": "Ingénieur de Forage", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Ingénieur en Génie Pétrolier", "ecole": "Institut Algérien du Pétrole", "ville": "Boumerdès", "pays": "ALGERIE", "debut": date(2005, 9, 1), "fin": date(2009, 6, 30), "niveau": "Bac+5", "desc": "Spécialité exploration-production."},
        ],
        "competences": [("Ingénierie réservoir", 5), ("Forage offshore", 5), ("Sécurité HSE", 5), ("Négociation partenaires", 4), ("Logiciels de simulation (Eclipse)", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "C1"), ("Arabe", "B1")],
        "interets":    ["Plongée sous-marine", "Géologie", "Voile"],
        "projets": [
            {"titre": "Développement champ offshore CI-40", "contexte": "Nouveau gisement à mettre en production.", "realisation": "Coordination des études de réservoir, production démarrée dans les délais.", "url": "", "debut": date(2020, 1, 1), "fin": date(2022, 6, 30)},
        ],
        "benevolats": [{"titre": "Formateur sécurité industrielle", "organisation": "Ordre des Ingénieurs de Côte d'Ivoire", "debut": date(2018, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/serge-ngoran")],
    },

    # ── 58 ── STYLE ───────────────────────────────────────────────────────────
    {
        "prenom": "Aïcha", "nom": "DOSSO", "sexe": "Femme",
        "email": "aicha.dosso@demo.test", "telephone": "+225 05 81 92 03 14",
        "naissance": date(1991, 4, 6), "nationalite": "Ivoirienne",
        "adresse": "Abobo Anonkoua-Kouté", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Institutrice Primaire",
        "secteur": "Éducation & Formation",
        "biographie": "Institutrice avec 8 ans d'expérience dans l'enseignement primaire public. Je crois en une pédagogie active adaptée à chaque enfant pour favoriser la réussite scolaire.",
        "profilCV": "Institutrice · 8 ans · Pédagogie active, gestion de classe, méthodes d'apprentissage de la lecture.",
        "anneePremEmploi": 2016, "mobilite": "Local", "contrat": "CDI",
        "slogan": "Chaque enfant mérite de réussir.",
        "couleur": "#009A44", "portfolioFichier": "style",
        "experiences": [
            {"entreprise": "École Primaire Publique d'Anonkoua-Kouté", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2016, 9, 1), "fin": None, "enCours": True, "description": "Enseignante en classe de CE2, 45 élèves. Mise en place d'ateliers de lecture personnalisés. Coordinatrice du projet cantine scolaire.", "poste": "Institutrice", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Brevet de Technicien Supérieur en Enseignement", "ecole": "École Normale d'Instituteurs d'Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2014, 9, 1), "fin": date(2016, 6, 30), "niveau": "BAC +2", "desc": "Formation pédagogique enseignement primaire."},
        ],
        "competences": [("Pédagogie active", 5), ("Gestion de classe", 5), ("Apprentissage de la lecture", 5), ("Animation d'ateliers", 4), ("Suivi individualisé", 4)],
        "langues":     [("Français", "C2"), ("Dioula", "C2"), ("Anglais", "A2")],
        "interets":    ["Lecture jeunesse", "Théâtre pédagogique", "Couture"],
        "projets": [
            {"titre": "Projet cantine scolaire équilibrée", "contexte": "Taux d'absentéisme lié à la malnutrition.", "realisation": "Mise en place d'un menu équilibré avec des parents bénévoles, absentéisme réduit de 20%.", "url": "", "debut": date(2020, 1, 1), "fin": date(2020, 12, 31)},
        ],
        "benevolats": [{"titre": "Cours de soutien gratuits", "organisation": "Association des Enseignants Bénévoles d'Abobo", "debut": date(2017, 9, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/aicha-dosso")],
    },

    # ── 59 ── ORANGE-VIBRANT ──────────────────────────────────────────────────
    {
        "prenom": "Guillaume", "nom": "KOUAME", "sexe": "Homme",
        "email": "guillaume.kouame@demo.test", "telephone": "+225 07 92 03 14 25",
        "naissance": date(1995, 8, 14), "nationalite": "Ivoirienne",
        "adresse": "Cocody Riviera 2", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Développeur Backend Java",
        "secteur": "Numérique (Tech)",
        "biographie": "Développeur backend spécialisé Java/Spring avec 5 ans d'expérience dans le secteur bancaire. Je conçois des systèmes robustes et sécurisés à forte volumétrie.",
        "profilCV": "Développeur backend · 5 ans · Java, Spring Boot, microservices, architecture bancaire sécurisée.",
        "anneePremEmploi": 2019, "mobilite": "National", "contrat": "CDI",
        "slogan": "Du code solide pour des systèmes fiables.",
        "couleur": "#F77F00", "portfolioFichier": "orange-vibrant",
        "experiences": [
            {"entreprise": "Ecobank Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2021, 4, 1), "fin": None, "enCours": True, "description": "Développement de microservices Java/Spring pour la plateforme bancaire mobile. Migration progressive du legacy COBOL vers Java.", "poste": "Développeur Backend Senior", "missionClient": None},
            {"entreprise": "NSIA Banque Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 6, 1), "fin": date(2021, 3, 31), "enCours": False, "description": "Développement d'API REST pour les services de virement et de consultation de compte.", "poste": "Développeur Backend Junior", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Licence Génie Logiciel", "ecole": "ESATIC Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2016, 9, 1), "fin": date(2019, 6, 30), "niveau": "BAC +3", "desc": "Spécialité développement backend et architecture logicielle."},
        ],
        "competences": [("Java / Spring Boot", 5), ("Microservices", 4), ("SQL / PostgreSQL", 4), ("Sécurité bancaire", 4), ("Kafka", 3)],
        "langues":     [("Français", "C2"), ("Anglais", "B2")],
        "interets":    ["Compétitions de code", "Basketball", "Jeux vidéo"],
        "projets": [
            {"titre": "Migration microservices Ecobank", "contexte": "Système legacy COBOL difficile à maintenir.", "realisation": "Migration de 6 modules vers Spring Boot, temps de réponse divisé par 3.", "url": "https://github.com/demo/ecobank-migration", "debut": date(2022, 1, 1), "fin": date(2022, 10, 31)},
        ],
        "benevolats": [{"titre": "Mentor développement backend", "organisation": "Djelia Tech CI", "debut": date(2021, 6, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/guillaume-kouame"), ("github", "https://github.com/guillaumekouame")],
    },

    # ── 60 ── PROMAN-PRO ──────────────────────────────────────────────────────
    {
        "prenom": "Joséphine", "nom": "BLE", "sexe": "Femme",
        "email": "josephine.ble@demo.test", "telephone": "+225 05 03 14 25 36",
        "naissance": date(1988, 12, 20), "nationalite": "Ivoirienne",
        "adresse": "Plateau, Immeuble EECI", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Contrôleuse de Gestion",
        "secteur": "Finance & Comptabilité",
        "biographie": "Contrôleuse de gestion avec 9 ans d'expérience dans l'industrie et la distribution. Je pilote la performance financière et accompagne les décisions stratégiques par l'analyse de données.",
        "profilCV": "Contrôleuse de gestion · 9 ans · Reporting financier, budgets, analyse de rentabilité, Power BI.",
        "anneePremEmploi": 2014, "mobilite": "National", "contrat": "CDI",
        "slogan": "Chiffrer pour mieux décider.",
        "couleur": "#1565C0", "portfolioFichier": "proman-pro",
        "experiences": [
            {"entreprise": "CFAO Motors CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2018, 9, 1), "fin": None, "enCours": True, "description": "Pilotage du budget annuel de 3 filiales. Reporting mensuel à la direction générale. Analyse de rentabilité par ligne de produits.", "poste": "Contrôleuse de Gestion Senior", "missionClient": None},
            {"entreprise": "SIFCA", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2014, 6, 1), "fin": date(2018, 8, 31), "enCours": False, "description": "Contrôle budgétaire de sites de production. Élaboration de tableaux de bord mensuels.", "poste": "Contrôleuse de Gestion", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master Contrôle de Gestion et Audit", "ecole": "ISTC Polytechnique Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2012, 9, 1), "fin": date(2014, 6, 30), "niveau": "Bac+5", "desc": "Spécialité pilotage de la performance financière."},
        ],
        "competences": [("Contrôle budgétaire", 5), ("Power BI", 4), ("Analyse de rentabilité", 5), ("SAP", 4), ("Reporting financier", 5)],
        "langues":     [("Français", "C2"), ("Anglais", "B2")],
        "interets":    ["Course à pied", "Lecture", "Voyages"],
        "projets": [
            {"titre": "Refonte du reporting mensuel CFAO", "contexte": "Process manuel Excel générant des erreurs et retards.", "realisation": "Automatisation via Power BI, délai de production du reporting réduit de 5 à 1 jour.", "url": "", "debut": date(2021, 1, 1), "fin": date(2021, 5, 31)},
        ],
        "benevolats": [{"titre": "Formatrice gestion financière PME", "organisation": "CGECI Académie", "debut": date(2019, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/josephine-ble")],
    },

    # ── 61 ── SNAPFOLIO ───────────────────────────────────────────────────────
    {
        "prenom": "Idriss", "nom": "FOFANA", "sexe": "Homme",
        "email": "idriss.fofana@demo.test", "telephone": "+225 07 14 25 36 47",
        "naissance": date(1994, 5, 2), "nationalite": "Ivoirienne",
        "adresse": "Koumassi Remblais", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Responsable Livraison Urbaine",
        "secteur": "Logistique & Transport",
        "biographie": "Responsable logistique du dernier kilomètre avec 6 ans d'expérience dans la livraison urbaine. J'optimise les tournées pour des délais toujours plus courts.",
        "profilCV": "Responsable livraison urbaine · 6 ans · Optimisation de tournées, gestion d'équipe de livreurs, logistique e-commerce.",
        "anneePremEmploi": 2018, "mobilite": "Local", "contrat": "CDI",
        "slogan": "Livrer vite, livrer bien.",
        "couleur": "#E85D4A", "portfolioFichier": "snapfolio",
        "experiences": [
            {"entreprise": "Jumia Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 6, 1), "fin": None, "enCours": True, "description": "Gestion de 35 livreurs sur la zone Abidjan Sud. Optimisation des tournées, réduction du délai moyen de livraison de 40%.", "poste": "Responsable Livraison Urbaine", "missionClient": None},
            {"entreprise": "Glovo Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2018, 3, 1), "fin": date(2020, 5, 31), "enCours": False, "description": "Livreur puis superviseur d'une équipe de 10 coursiers.", "poste": "Superviseur Livraison", "missionClient": None},
        ],
        "formations": [
            {"diplome": "BTS Logistique et Transport", "ecole": "Institut Supérieur de Commerce d'Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2016, 9, 1), "fin": date(2018, 6, 30), "niveau": "BAC +2", "desc": "Spécialité logistique urbaine et e-commerce."},
        ],
        "competences": [("Optimisation de tournées", 5), ("Management d'équipe", 4), ("Logistique e-commerce", 5), ("Résolution de problèmes", 4), ("Outils de tracking GPS", 4)],
        "langues":     [("Français", "C1"), ("Dioula", "C2"), ("Anglais", "A2")],
        "interets":    ["Football", "Moto", "Jeux vidéo"],
        "projets": [
            {"titre": "Optimisation zone Abidjan Sud", "contexte": "Délais de livraison jugés trop longs par les clients.", "realisation": "Réorganisation des zones de livraison, délai moyen passé de 90 à 55 minutes.", "url": "", "debut": date(2021, 3, 1), "fin": date(2021, 9, 30)},
        ],
        "benevolats": [{"titre": "Formateur code de la route", "organisation": "Auto-École Solidaire de Koumassi", "debut": date(2020, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/idriss-fofana")],
    },

    # ── 62 ── CYBER-NEON ──────────────────────────────────────────────────────
    {
        "prenom": "Adèle", "nom": "YAPI", "sexe": "Femme",
        "email": "adele.yapi@demo.test", "telephone": "+225 05 25 36 47 58",
        "naissance": date(1996, 10, 9), "nationalite": "Ivoirienne",
        "adresse": "Marcory Anoumabo", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Esthéticienne",
        "secteur": "Beauté & Bien-être",
        "biographie": "Esthéticienne avec 6 ans d'expérience, spécialisée en soins du visage et bien-être. Passionnée par les cosmétiques naturels africains, je conseille chaque cliente avec attention.",
        "profilCV": "Esthéticienne · 6 ans · Soins du visage, épilation, cosmétique naturelle, conseil beauté personnalisé.",
        "anneePremEmploi": 2018, "mobilite": "Local", "contrat": "Freelance",
        "slogan": "La beauté commence par le bien-être.",
        "couleur": "#E85D4A", "portfolioFichier": "cyber-neon",
        "experiences": [
            {"entreprise": "Institut Beauté Éclat d'Ébène", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2021, 1, 1), "fin": None, "enCours": True, "description": "Gérante indépendante d'un institut de beauté. Développement d'une gamme de soins à base de produits locaux (karité, huile de coco).", "poste": "Esthéticienne Gérante", "missionClient": None},
            {"entreprise": "Spa Le Wafou", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2018, 4, 1), "fin": date(2020, 12, 31), "enCours": False, "description": "Soins du visage et du corps pour une clientèle haut de gamme.", "poste": "Esthéticienne", "missionClient": None},
        ],
        "formations": [
            {"diplome": "CAP Esthétique Cosmétique", "ecole": "École d'Esthétique d'Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2016, 9, 1), "fin": date(2018, 6, 30), "niveau": "BAC +2", "desc": "Spécialité soins du visage et cosmétique naturelle."},
        ],
        "competences": [("Soins du visage", 5), ("Cosmétique naturelle", 5), ("Conseil beauté", 5), ("Épilation", 4), ("Gestion de salon", 3)],
        "langues":     [("Français", "C2"), ("Baoulé", "C2"), ("Anglais", "A2")],
        "interets":    ["Cosmétiques naturels", "Mode", "Danse"],
        "projets": [
            {"titre": "Gamme de soins au karité local", "contexte": "Forte demande pour des cosmétiques naturels et locaux.", "realisation": "Développement de 5 soins signature à base de karité et huile de coco ivoiriens, best-seller de l'institut.", "url": "", "debut": date(2022, 1, 1), "fin": date(2022, 8, 31)},
        ],
        "benevolats": [{"titre": "Ateliers beauté et confiance en soi", "organisation": "Association Femmes Debout CI", "debut": date(2021, 3, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/adele-yapi"), ("instagram", "https://instagram.com/adele.beaute.ci")],
    },

    # ── 63 ── PROMAN ──────────────────────────────────────────────────────────
    {
        "prenom": "Willy", "nom": "DJAMA", "sexe": "Homme",
        "email": "willy.djama@demo.test", "telephone": "+225 07 36 47 58 69",
        "naissance": date(1987, 2, 23), "nationalite": "Ivoirienne",
        "adresse": "Cocody II Plateaux", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Ingénieur Génie Civil",
        "secteur": "BTP & Génie Civil",
        "biographie": "Ingénieur génie civil avec 12 ans d'expérience en conception et suivi de projets de construction. Spécialiste des structures en béton armé et des études de sol.",
        "profilCV": "Ingénieur génie civil · 12 ans · Calcul de structures, études de sol, suivi de chantier, béton armé.",
        "anneePremEmploi": 2011, "mobilite": "National", "contrat": "CDI",
        "slogan": "Concevoir des structures qui durent.",
        "couleur": "#003366", "portfolioFichier": "proman",
        "experiences": [
            {"entreprise": "SOGEA-SATOM", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2017, 1, 1), "fin": None, "enCours": True, "description": "Ingénieur études pour des projets de ponts et échangeurs. Calcul de structures en béton armé et précontraint.", "poste": "Ingénieur Structures Senior", "missionClient": None},
            {"entreprise": "Eiffage Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2011, 9, 1), "fin": date(2016, 12, 31), "enCours": False, "description": "Ingénieur études de sol et fondations pour bâtiments tertiaires.", "poste": "Ingénieur Géotechnique", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Ingénieur en Génie Civil", "ecole": "INPHB Yamoussoukro", "ville": "Yamoussoukro", "pays": "COTE D'IVOIRE", "debut": date(2008, 9, 1), "fin": date(2011, 6, 30), "niveau": "Bac+5", "desc": "Spécialité structures et géotechnique."},
        ],
        "competences": [("Calcul de structures", 5), ("Béton armé", 5), ("Études de sol", 4), ("AutoCAD/Robot", 4), ("Suivi de chantier", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Baoulé", "B1")],
        "interets":    ["Architecture", "Football", "Randonnée"],
        "projets": [
            {"titre": "Échangeur de la Riviera 2", "contexte": "Désengorgement d'un axe routier majeur d'Abidjan.", "realisation": "Calcul et suivi des structures de l'échangeur, livré conforme au planning.", "url": "", "debut": date(2019, 1, 1), "fin": date(2021, 3, 31)},
        ],
        "benevolats": [{"titre": "Consultant technique bénévole", "organisation": "Ordre des Ingénieurs de Côte d'Ivoire", "debut": date(2018, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/willy-djama")],
    },

    # ── 64 ── CLINIC-PRO ──────────────────────────────────────────────────────
    {
        "prenom": "Odette", "nom": "KRA", "sexe": "Femme",
        "email": "odette.kra@demo.test", "telephone": "+225 05 47 58 69 70",
        "naissance": date(1990, 7, 19), "nationalite": "Ivoirienne",
        "adresse": "Yopougon Wassakara", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Assistante Sociale",
        "secteur": "ONG & Secteur public",
        "biographie": "Assistante sociale avec 8 ans d'expérience auprès des familles vulnérables et des enfants en difficulté. J'accompagne vers l'autonomie avec écoute et détermination.",
        "profilCV": "Assistante sociale · 8 ans · Accompagnement familial, protection de l'enfance, médiation sociale.",
        "anneePremEmploi": 2016, "mobilite": "Local", "contrat": "CDI",
        "slogan": "Accompagner, sans jamais juger.",
        "couleur": "#2A9D8F", "portfolioFichier": "clinic-pro",
        "experiences": [
            {"entreprise": "Ministère de la Femme, de la Famille et de l'Enfant", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 3, 1), "fin": None, "enCours": True, "description": "Accompagnement de familles en difficulté dans la commune de Yopougon. Coordination de la protection de 60 enfants suivis par an.", "poste": "Assistante Sociale Référente", "missionClient": None},
            {"entreprise": "ONG SOS Villages d'Enfants CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2016, 6, 1), "fin": date(2019, 2, 28), "enCours": False, "description": "Suivi psychosocial d'enfants placés. Médiation familiale.", "poste": "Assistante Sociale", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Diplôme d'État d'Assistante Sociale", "ecole": "INFAS Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2013, 9, 1), "fin": date(2016, 6, 30), "niveau": "BAC +3", "desc": "Spécialité protection de l'enfance et médiation familiale."},
        ],
        "competences": [("Accompagnement familial", 5), ("Protection de l'enfance", 5), ("Médiation sociale", 4), ("Écoute active", 5), ("Rédaction de rapports sociaux", 4)],
        "langues":     [("Français", "C2"), ("Baoulé", "C2"), ("Anglais", "A2")],
        "interets":    ["Bénévolat", "Lecture", "Chant"],
        "projets": [
            {"titre": "Programme de réinsertion familiale", "contexte": "Nombre croissant d'enfants placés à Yopougon.", "realisation": "Suivi de 25 familles, 18 réunifications familiales réussies en 2 ans.", "url": "", "debut": date(2020, 1, 1), "fin": date(2021, 12, 31)},
        ],
        "benevolats": [{"titre": "Écoute téléphonique enfance en danger", "organisation": "Ligne Verte Côte d'Ivoire", "debut": date(2017, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/odette-kra")],
    },

    # ── 65 ── RETRO-MAG ───────────────────────────────────────────────────────
    {
        "prenom": "Fabrice", "nom": "AKESSE", "sexe": "Homme",
        "email": "fabrice.akesse@demo.test", "telephone": "+225 07 58 69 70 81",
        "naissance": date(1992, 3, 27), "nationalite": "Ivoirienne",
        "adresse": "Treichville Biafra", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Technicien de Laboratoire Médical",
        "secteur": "Santé",
        "biographie": "Technicien de laboratoire médical avec 7 ans d'expérience en analyses biologiques. Rigueur et précision guident chacune de mes manipulations pour un diagnostic fiable.",
        "profilCV": "Technicien de laboratoire · 7 ans · Analyses biologiques, hématologie, biochimie, contrôle qualité.",
        "anneePremEmploi": 2017, "mobilite": "Local", "contrat": "CDI",
        "slogan": "La précision au service du diagnostic.",
        "couleur": "#C9A227", "portfolioFichier": "retro-mag",
        "experiences": [
            {"entreprise": "CHU de Treichville", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 1, 1), "fin": None, "enCours": True, "description": "Réalisation d'analyses de biochimie et hématologie. Participation au contrôle qualité du laboratoire. Traitement de 150 échantillons par jour.", "poste": "Technicien de Laboratoire Senior", "missionClient": None},
            {"entreprise": "Laboratoire Bio 24", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2017, 3, 1), "fin": date(2019, 12, 31), "enCours": False, "description": "Analyses de routine et sérologie. Accueil et prélèvement patients.", "poste": "Technicien de Laboratoire", "missionClient": None},
        ],
        "formations": [
            {"diplome": "BTS Analyses Biologiques", "ecole": "INFAS Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2015, 9, 1), "fin": date(2017, 6, 30), "niveau": "BAC +2", "desc": "Spécialité biochimie et hématologie."},
        ],
        "competences": [("Analyses biochimiques", 5), ("Hématologie", 4), ("Contrôle qualité", 4), ("Sérologie", 4), ("Gestion des prélèvements", 5)],
        "langues":     [("Français", "C2"), ("Anglais", "B1"), ("Ebrié", "C1")],
        "interets":    ["Sciences", "Football", "Jeux de société"],
        "projets": [
            {"titre": "Mise à niveau contrôle qualité laboratoire", "contexte": "Préparation à une accréditation qualité.", "realisation": "Participation à la mise en conformité des procédures, accréditation obtenue.", "url": "", "debut": date(2021, 6, 1), "fin": date(2022, 3, 31)},
        ],
        "benevolats": [{"titre": "Dépistage gratuit communautaire", "organisation": "Croix-Rouge Côte d'Ivoire", "debut": date(2018, 6, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/fabrice-akesse")],
    },

    # ── 66 ── ORANGE-VIBRANT ──────────────────────────────────────────────────
    {
        "prenom": "Pauline", "nom": "N'GUESSAN", "sexe": "Femme",
        "email": "pauline.nguessan@demo.test", "telephone": "+225 05 69 70 81 92",
        "naissance": date(1989, 9, 5), "nationalite": "Ivoirienne",
        "adresse": "Cocody Ambassades", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Traductrice-Interprète",
        "secteur": "Communication & Marketing",
        "biographie": "Traductrice-interprète français-anglais avec 9 ans d'expérience auprès d'institutions internationales et d'entreprises. Précision et confidentialité sont mes priorités.",
        "profilCV": "Traductrice-interprète · 9 ans · Traduction juridique et technique, interprétation de conférence, français-anglais.",
        "anneePremEmploi": 2014, "mobilite": "International", "contrat": "Freelance / Mission",
        "slogan": "Faire passer le sens, pas seulement les mots.",
        "couleur": "#F77F00", "portfolioFichier": "orange-vibrant",
        "experiences": [
            {"entreprise": "Banque Africaine de Développement (BAD)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2018, 1, 1), "fin": None, "enCours": True, "description": "Traduction de documents financiers et interprétation lors de conférences internationales. Missions ponctuelles pour la direction communication.", "poste": "Traductrice-Interprète Freelance", "missionClient": {"client": "TotalEnergies Côte d'Ivoire", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2021, 2, 1), "fin": date(2021, 3, 31), "desc": "Interprétation lors d'un séminaire international sur les énergies renouvelables."}},
            {"entreprise": "Cabinet de Traduction Verbatim CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2014, 9, 1), "fin": date(2017, 12, 31), "enCours": False, "description": "Traduction de contrats commerciaux et documents juridiques.", "poste": "Traductrice Junior", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master Traduction et Interprétation", "ecole": "Université de Genève", "ville": "Genève", "pays": "SUISSE", "debut": date(2012, 9, 1), "fin": date(2014, 6, 30), "niveau": "Bac+5", "desc": "Spécialité traduction juridique et interprétation de conférence."},
        ],
        "competences": [("Traduction juridique", 5), ("Interprétation simultanée", 5), ("Traduction technique", 4), ("Relecture/révision", 5), ("Terminologie spécialisée", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "C2"), ("Espagnol", "B2")],
        "interets":    ["Littérature", "Voyages", "Linguistique"],
        "projets": [
            {"titre": "Interprétation séminaire TotalEnergies", "contexte": "Conférence internationale sur les énergies renouvelables.", "realisation": "Interprétation simultanée pour 200 participants sur 3 jours, satisfaction unanime des organisateurs.", "url": "", "debut": date(2021, 2, 1), "fin": date(2021, 3, 31)},
        ],
        "benevolats": [{"titre": "Traduction bénévole documents ONG", "organisation": "Médecins Sans Frontières CI", "debut": date(2019, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/pauline-nguessan")],
    },

    # ── 67 ── SNAPFOLIO ───────────────────────────────────────────────────────
    {
        "prenom": "Emmanuel", "nom": "BROU", "sexe": "Homme",
        "email": "emmanuel.brou@demo.test", "telephone": "+225 07 70 81 92 03",
        "naissance": date(1985, 6, 30), "nationalite": "Ivoirienne",
        "adresse": "Cocody Attoban", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Agent Immobilier",
        "secteur": "BTP & Immobilier",
        "biographie": "Agent immobilier avec 11 ans d'expérience dans la transaction et la location de biens résidentiels et commerciaux à Abidjan. Réseau solide et connaissance fine du marché local.",
        "profilCV": "Agent immobilier · 11 ans · Transaction, location, négociation, estimation de biens, connaissance du marché abidjanais.",
        "anneePremEmploi": 2012, "mobilite": "Local", "contrat": "Freelance",
        "slogan": "Trouver la clé de votre prochain chez-vous.",
        "couleur": "#009A44", "portfolioFichier": "snapfolio",
        "experiences": [
            {"entreprise": "Agence Immobilière Diamant CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2016, 1, 1), "fin": None, "enCours": True, "description": "Gestion d'un portefeuille de 80 biens résidentiels et commerciaux. Négociation de plus de 150 transactions.", "poste": "Agent Immobilier Senior", "missionClient": None},
            {"entreprise": "Cabinet Foncier Ivoire Immo", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2012, 4, 1), "fin": date(2015, 12, 31), "enCours": False, "description": "Prospection et vente de terrains et logements en périphérie d'Abidjan.", "poste": "Agent Commercial Immobilier", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Licence en Gestion Immobilière", "ecole": "Institut Supérieur de Commerce d'Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2009, 9, 1), "fin": date(2012, 6, 30), "niveau": "BAC +3", "desc": "Spécialité transaction et gestion de patrimoine immobilier."},
        ],
        "competences": [("Négociation immobilière", 5), ("Estimation de biens", 5), ("Droit immobilier de base", 4), ("Prospection", 4), ("Relation client", 5)],
        "langues":     [("Français", "C2"), ("Anglais", "B1"), ("Baoulé", "C2")],
        "interets":    ["Architecture", "Golf", "Immobilier d'investissement"],
        "projets": [
            {"titre": "Commercialisation résidence Attoban", "contexte": "Programme de 40 appartements neufs à commercialiser.", "realisation": "Vente de 35 appartements en 8 mois, dépassement de l'objectif de 20%.", "url": "", "debut": date(2021, 1, 1), "fin": date(2021, 9, 30)},
        ],
        "benevolats": [{"titre": "Conseil logement pour familles modestes", "organisation": "Fondation Abidjan Solidaire", "debut": date(2018, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/emmanuel-brou-immo")],
    },

    # ── 68 ── TECH-DASHBOARD ──────────────────────────────────────────────────
    {
        "prenom": "Sarah", "nom": "ADJOUA", "sexe": "Femme",
        "email": "sarah.adjoua@demo.test", "telephone": "+225 05 92 03 14 25",
        "naissance": date(1994, 4, 11), "nationalite": "Ivoirienne",
        "adresse": "Cocody Riviera Palmeraie", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "UX Researcher",
        "secteur": "Numérique (Tech)",
        "biographie": "UX researcher avec 5 ans d'expérience, spécialisée dans l'étude des comportements utilisateurs pour des produits fintech. Je transforme les insights terrain en décisions produit.",
        "profilCV": "UX Researcher · 5 ans · Tests utilisateurs, entretiens qualitatifs, analyse de données comportementales, fintech.",
        "anneePremEmploi": 2019, "mobilite": "National", "contrat": "CDI",
        "slogan": "Comprendre avant de concevoir.",
        "couleur": "#1a1a2e", "portfolioFichier": "tech-dashboard",
        "experiences": [
            {"entreprise": "WAVE Mobile Money", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2021, 5, 1), "fin": None, "enCours": True, "description": "Conduite d'études utilisateurs sur l'app Wave (entretiens, tests d'usabilité). Recommandations ayant conduit à une refonte du parcours de paiement.", "poste": "UX Researcher Senior", "missionClient": None},
            {"entreprise": "Orange Digital Center CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 2, 1), "fin": date(2021, 4, 30), "enCours": False, "description": "Recherche utilisateur pour des startups incubées. Ateliers de co-conception avec les usagers.", "poste": "UX Researcher Junior", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master UX Design et Recherche Utilisateur", "ecole": "ESATIC Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2017, 9, 1), "fin": date(2019, 6, 30), "niveau": "Bac+5", "desc": "Spécialité recherche utilisateur et design centré humain."},
        ],
        "competences": [("Tests utilisateurs", 5), ("Entretiens qualitatifs", 5), ("Analyse de données", 4), ("Figma", 3), ("Synthèse et restitution", 5)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Dioula", "B1")],
        "interets":    ["Sciences comportementales", "Yoga", "Podcasts"],
        "projets": [
            {"titre": "Refonte du parcours de paiement Wave", "contexte": "Taux d'abandon élevé lors du premier envoi d'argent.", "realisation": "Étude de 40 utilisateurs, refonte du parcours, taux d'abandon réduit de 30%.", "url": "", "debut": date(2022, 1, 1), "fin": date(2022, 6, 30)},
        ],
        "benevolats": [{"titre": "Ateliers UX pour étudiants", "organisation": "Orange Digital Center CI", "debut": date(2020, 9, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/sarah-adjoua"), ("behance", "https://www.behance.net/sarahadjoua")],
    },

    # ── 69 ── PROMAN-GLASS ────────────────────────────────────────────────────
    {
        "prenom": "Cyrille", "nom": "OUATTARA", "sexe": "Homme",
        "email": "cyrille.ouattara@demo.test", "telephone": "+225 07 03 14 25 36",
        "naissance": date(1983, 1, 15), "nationalite": "Ivoirienne",
        "adresse": "Yopougon Sicogi", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "ABCDE", "titre": "Mécanicien Automobile",
        "secteur": "Industrie manufacturière",
        "biographie": "Mécanicien automobile avec 17 ans d'expérience, spécialisé en diagnostic électronique et moteurs diesel. Je forme aussi la nouvelle génération de mécaniciens.",
        "profilCV": "Mécanicien automobile · 17 ans · Diagnostic électronique, moteurs diesel, boîtes automatiques, formation.",
        "anneePremEmploi": 2007, "mobilite": "Local", "contrat": "CDI",
        "slogan": "Chaque moteur a une histoire à réparer.",
        "couleur": "#003366", "portfolioFichier": "proman-glass",
        "experiences": [
            {"entreprise": "CFAO Motors CI (Toyota)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2012, 3, 1), "fin": None, "enCours": True, "description": "Diagnostic et réparation de véhicules Toyota. Responsable de la formation des apprentis mécaniciens de l'atelier.", "poste": "Mécanicien Diagnostiqueur Senior", "missionClient": None},
            {"entreprise": "Garage Indépendant Yopougon", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2007, 6, 1), "fin": date(2012, 2, 28), "enCours": False, "description": "Réparation mécanique générale toutes marques.", "poste": "Mécanicien Automobile", "missionClient": None},
        ],
        "formations": [
            {"diplome": "CAP Mécanique Automobile", "ecole": "Lycée Technique d'Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2005, 9, 1), "fin": date(2007, 6, 30), "niveau": "BAC +2", "desc": "Spécialité mécanique et diagnostic électronique."},
        ],
        "competences": [("Diagnostic électronique", 5), ("Moteurs diesel", 5), ("Boîtes automatiques", 4), ("Formation technique", 4), ("Climatisation automobile", 3)],
        "langues":     [("Français", "C1"), ("Dioula", "C2"), ("Anglais", "A1")],
        "interets":    ["Course automobile", "Football", "Bricolage"],
        "projets": [
            {"titre": "Formation de 20 apprentis mécaniciens", "contexte": "Pénurie de mécaniciens qualifiés sur le marché.", "realisation": "Programme de formation de 18 mois, 15 apprentis certifiés et embauchés.", "url": "", "debut": date(2019, 1, 1), "fin": date(2020, 6, 30)},
        ],
        "benevolats": [{"titre": "Réparations gratuites taxis solidaires", "organisation": "Coopérative des Chauffeurs de Yopougon", "debut": date(2016, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/cyrille-ouattara")],
    },

    # ── 70 ── STYLE ───────────────────────────────────────────────────────────
    {
        "prenom": "Linda", "nom": "KOUAKOU", "sexe": "Femme",
        "email": "linda.kouakou@demo.test", "telephone": "+225 05 14 25 36 47",
        "naissance": date(1990, 8, 3), "nationalite": "Ivoirienne",
        "adresse": "Yopougon Toit Rouge", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Responsable Qualité Industrielle",
        "secteur": "Industrie manufacturière",
        "biographie": "Responsable qualité avec 8 ans d'expérience dans l'agroalimentaire. Je veille au respect des normes ISO et à l'amélioration continue des processus de production.",
        "profilCV": "Responsable qualité · 8 ans · Normes ISO 9001/22000, audits qualité, amélioration continue, agroalimentaire.",
        "anneePremEmploi": 2016, "mobilite": "National", "contrat": "CDI",
        "slogan": "La qualité, une exigence de chaque instant.",
        "couleur": "#2A9D8F", "portfolioFichier": "style",
        "experiences": [
            {"entreprise": "Nestlé Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 6, 1), "fin": None, "enCours": True, "description": "Pilotage du système qualité ISO 22000 de l'usine. Conduite d'audits internes mensuels. Formation des équipes de production aux bonnes pratiques.", "poste": "Responsable Qualité", "missionClient": None},
            {"entreprise": "SOLIBRA (Heineken Côte d'Ivoire)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2016, 4, 1), "fin": date(2019, 5, 31), "enCours": False, "description": "Contrôle qualité des lignes d'embouteillage. Gestion des non-conformités.", "poste": "Technicienne Qualité", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master Qualité, Hygiène, Sécurité, Environnement", "ecole": "INPHB Yamoussoukro", "ville": "Yamoussoukro", "pays": "COTE D'IVOIRE", "debut": date(2014, 9, 1), "fin": date(2016, 6, 30), "niveau": "Bac+5", "desc": "Spécialité gestion de la qualité en agroalimentaire."},
        ],
        "competences": [("ISO 9001/22000", 5), ("Audit qualité", 5), ("Amélioration continue", 4), ("HACCP", 5), ("Formation d'équipes", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Baoulé", "C1")],
        "interets":    ["Amélioration continue (Lean)", "Course à pied", "Cuisine"],
        "projets": [
            {"titre": "Certification ISO 22000 usine Nestlé", "contexte": "Renouvellement de la certification qualité de l'usine.", "realisation": "Pilotage du projet de mise en conformité, certification obtenue sans non-conformité majeure.", "url": "", "debut": date(2021, 1, 1), "fin": date(2021, 11, 30)},
        ],
        "benevolats": [{"titre": "Sensibilisation hygiène alimentaire", "organisation": "Association des Femmes Transformatrices CI", "debut": date(2020, 3, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/linda-kouakou-qualite")],
    },

    # ── 71 ── PROMAN-PRO ──────────────────────────────────────────────────────
    {
        "prenom": "Aristide", "nom": "KOFFI", "sexe": "Homme",
        "email": "aristide.koffi@demo.test", "telephone": "+225 07 25 36 47 58",
        "naissance": date(1986, 5, 28), "nationalite": "Ivoirienne",
        "adresse": "Port-Bouët Vridi", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Agent des Douanes",
        "secteur": "Logistique & Transport",
        "biographie": "Agent des douanes avec 13 ans d'expérience au Port Autonome d'Abidjan. Je facilite le commerce international tout en assurant le respect de la réglementation.",
        "profilCV": "Agent des douanes · 13 ans · Dédouanement, réglementation douanière, contrôle des marchandises, facilitation commerciale.",
        "anneePremEmploi": 2010, "mobilite": "National", "contrat": "CDI",
        "slogan": "Faciliter le commerce, protéger l'économie.",
        "couleur": "#1565C0", "portfolioFichier": "proman-pro",
        "experiences": [
            {"entreprise": "Direction Générale des Douanes de Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2015, 1, 1), "fin": None, "enCours": True, "description": "Contrôle et dédouanement des marchandises au Port Autonome d'Abidjan. Lutte contre la fraude douanière.", "poste": "Agent des Douanes Senior", "missionClient": None},
            {"entreprise": "Bolloré Transport & Logistics CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2010, 6, 1), "fin": date(2014, 12, 31), "enCours": False, "description": "Déclarant en douane pour le compte d'importateurs et exportateurs.", "poste": "Déclarant en Douane", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Licence en Droit Douanier", "ecole": "Université FHB Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2007, 9, 1), "fin": date(2010, 6, 30), "niveau": "BAC +3", "desc": "Spécialité réglementation douanière et commerce international."},
        ],
        "competences": [("Réglementation douanière", 5), ("Dédouanement", 5), ("Contrôle des marchandises", 4), ("Nomenclature tarifaire", 4), ("Lutte anti-fraude", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Baoulé", "B1")],
        "interets":    ["Droit international", "Football", "Voyages"],
        "projets": [
            {"titre": "Digitalisation des procédures douanières", "contexte": "Délais de dédouanement jugés trop longs par les opérateurs économiques.", "realisation": "Participation au déploiement du guichet unique électronique, délai moyen réduit de 30%.", "url": "", "debut": date(2020, 1, 1), "fin": date(2020, 12, 31)},
        ],
        "benevolats": [{"titre": "Formation réglementation douanière PME", "organisation": "CGECI Académie", "debut": date(2019, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/aristide-koffi")],
    },

    # ── 72 ── CYBER-NEON ──────────────────────────────────────────────────────
    {
        "prenom": "Sandrine", "nom": "ABLE", "sexe": "Femme",
        "email": "sandrine.able@demo.test", "telephone": "+225 05 36 47 58 69",
        "naissance": date(1993, 12, 14), "nationalite": "Ivoirienne",
        "adresse": "Plateau, Rue du Textile", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Styliste Modéliste",
        "secteur": "Mode & Artisanat",
        "biographie": "Styliste modéliste avec 6 ans d'expérience, je conçois des collections inspirées des tissus wax et du pagne tissé. Ma marque met en valeur l'artisanat textile ivoirien.",
        "profilCV": "Styliste modéliste · 6 ans · Conception de collections, patronage, tissus africains, direction artistique.",
        "anneePremEmploi": 2018, "mobilite": "National", "contrat": "Freelance",
        "slogan": "L'élégance africaine, réinventée.",
        "couleur": "#F77F00", "portfolioFichier": "cyber-neon",
        "experiences": [
            {"entreprise": "Maison de Couture Sandrine Able (marque propre)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 1, 1), "fin": None, "enCours": True, "description": "Création de 4 collections par an. Défilés lors de la Fashion Week d'Abidjan. Vente en boutique et en ligne.", "poste": "Styliste Créatrice", "missionClient": None},
            {"entreprise": "Atelier Pathé'O", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2018, 3, 1), "fin": date(2019, 12, 31), "enCours": False, "description": "Assistante styliste, patronage et suivi de fabrication.", "poste": "Assistante Styliste", "missionClient": None},
        ],
        "formations": [
            {"diplome": "BTS Stylisme et Modélisme", "ecole": "École Supérieure de Mode d'Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2016, 9, 1), "fin": date(2018, 6, 30), "niveau": "BAC +2", "desc": "Spécialité création de mode et patronage."},
        ],
        "competences": [("Conception de collections", 5), ("Patronage", 5), ("Textiles africains", 5), ("Direction artistique", 4), ("Gestion d'atelier", 3)],
        "langues":     [("Français", "C2"), ("Anglais", "B1"), ("Baoulé", "B2")],
        "interets":    ["Mode africaine", "Photographie", "Danse traditionnelle"],
        "projets": [
            {"titre": "Collection 'Racines' — Fashion Week Abidjan", "contexte": "Participation à l'un des plus grands événements mode d'Afrique de l'Ouest.", "realisation": "Défilé de 20 tenues, forte couverture médiatique, +150 commandes en ligne suite à l'événement.", "url": "https://instagram.com/sandrine.able.mode", "debut": date(2022, 3, 1), "fin": date(2022, 6, 30)},
        ],
        "benevolats": [{"titre": "Formatrice couture pour jeunes femmes", "organisation": "Association des Artisans de Mode CI", "debut": date(2020, 6, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/sandrine-able-mode"), ("instagram", "https://instagram.com/sandrine.able.mode")],
    },

    # ── 73 ── RETRO-MAG ───────────────────────────────────────────────────────
    {
        "prenom": "Junior", "nom": "KRAGBE", "sexe": "Homme",
        "email": "junior.kragbe@demo.test", "telephone": "+225 07 47 58 69 70",
        "naissance": date(1991, 2, 8), "nationalite": "Ivoirienne",
        "adresse": "Cocody Sainte Thérèse", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Coach Sportif / Préparateur Physique",
        "secteur": "Sport & Loisirs",
        "biographie": "Coach sportif certifié avec 7 ans d'expérience en préparation physique de sportifs amateurs et professionnels. Je conçois des programmes sur-mesure pour chaque objectif.",
        "profilCV": "Coach sportif · 7 ans · Préparation physique, coaching individuel, nutrition sportive, remise en forme.",
        "anneePremEmploi": 2017, "mobilite": "Local", "contrat": "Freelance",
        "slogan": "Dépasser ses limites, une séance à la fois.",
        "couleur": "#C9A227", "portfolioFichier": "retro-mag",
        "experiences": [
            {"entreprise": "ASEC Mimosas (Centre de formation)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 7, 1), "fin": None, "enCours": True, "description": "Préparation physique des jeunes joueurs du centre de formation. Suivi individualisé de 25 athlètes.", "poste": "Préparateur Physique", "missionClient": None},
            {"entreprise": "Fitness Park Abidjan", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2017, 2, 1), "fin": date(2020, 6, 30), "enCours": False, "description": "Coaching individuel et collectif en salle de sport. Conception de programmes personnalisés.", "poste": "Coach Sportif", "missionClient": None},
        ],
        "formations": [
            {"diplome": "BPJEPS Activités Physiques pour Tous", "ecole": "Institut National de la Jeunesse et des Sports (INJS)", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2015, 9, 1), "fin": date(2017, 6, 30), "niveau": "BAC +2", "desc": "Formation d'éducateur sportif et préparateur physique."},
        ],
        "competences": [("Préparation physique", 5), ("Coaching individuel", 5), ("Nutrition sportive", 4), ("Prévention des blessures", 4), ("Suivi de performance", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B1"), ("Baoulé", "C1")],
        "interets":    ["Football", "Musculation", "Course à pied"],
        "projets": [
            {"titre": "Programme préparation physique jeunes espoirs", "contexte": "Préparer une génération de jeunes footballeurs pour le haut niveau.", "realisation": "Suivi de 25 jeunes sur 2 saisons, 4 joueurs recrutés en club professionnel européen.", "url": "", "debut": date(2020, 7, 1), "fin": date(2022, 6, 30)},
        ],
        "benevolats": [{"titre": "Coach bénévole quartier", "organisation": "Association Sport pour Tous Cocody", "debut": date(2018, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/junior-kragbe-coach"), ("instagram", "https://instagram.com/junior.coach.ci")],
    },

    # ── 74 ── SNAPFOLIO ───────────────────────────────────────────────────────
    {
        "prenom": "Béatrice", "nom": "GOLI", "sexe": "Femme",
        "email": "beatrice.goli@demo.test", "telephone": "+225 05 58 69 70 81",
        "naissance": date(1992, 10, 22), "nationalite": "Ivoirienne",
        "adresse": "Cocody Riviera Faya", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Ingénieure Environnement",
        "secteur": "Énergie & Environnement",
        "biographie": "Ingénieure environnement avec 7 ans d'expérience en études d'impact et gestion des déchets industriels. J'accompagne les entreprises vers des pratiques plus durables.",
        "profilCV": "Ingénieure environnement · 7 ans · Études d'impact environnemental, gestion des déchets, conformité réglementaire, RSE.",
        "anneePremEmploi": 2017, "mobilite": "National", "contrat": "CDI",
        "slogan": "Un développement qui respecte son environnement.",
        "couleur": "#2A9D8F", "portfolioFichier": "snapfolio",
        "experiences": [
            {"entreprise": "PETROCI Holding", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 3, 1), "fin": None, "enCours": True, "description": "Réalisation d'études d'impact environnemental pour les projets pétroliers. Suivi de la conformité réglementaire environnementale.", "poste": "Ingénieure Environnement Senior", "missionClient": None},
            {"entreprise": "Cabinet d'Études Environnementales EnviroConseil CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2017, 6, 1), "fin": date(2020, 2, 29), "enCours": False, "description": "Études d'impact pour des projets industriels et miniers. Rédaction de rapports environnementaux.", "poste": "Ingénieure Environnement Junior", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master en Sciences de l'Environnement", "ecole": "Université Nangui Abrogoua", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2015, 9, 1), "fin": date(2017, 6, 30), "niveau": "Bac+5", "desc": "Spécialité gestion environnementale et développement durable."},
        ],
        "competences": [("Études d'impact environnemental", 5), ("Gestion des déchets", 4), ("Réglementation environnementale", 5), ("RSE", 4), ("Audit environnemental", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Attié", "C1")],
        "interets":    ["Écologie", "Randonnée", "Jardinage"],
        "projets": [
            {"titre": "Plan de gestion des déchets industriels PETROCI", "contexte": "Absence de traçabilité complète des déchets dangereux.", "realisation": "Mise en place d'un plan de gestion conforme aux normes internationales, audité positivement.", "url": "", "debut": date(2021, 1, 1), "fin": date(2021, 10, 31)},
        ],
        "benevolats": [{"titre": "Sensibilisation au tri des déchets", "organisation": "ONG Renaissance Verte CI", "debut": date(2019, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/beatrice-goli")],
    },

    # ── 75 ── PROMAN ──────────────────────────────────────────────────────────
    {
        "prenom": "Théodore", "nom": "ANOMA", "sexe": "Homme",
        "email": "theodore.anoma@demo.test", "telephone": "+225 07 69 70 81 92",
        "naissance": date(1988, 4, 17), "nationalite": "Ivoirienne",
        "adresse": "Plateau, Avenue Franchet d'Esperey", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Souscripteur en Assurance",
        "secteur": "Services financiers",
        "biographie": "Souscripteur en assurance avec 10 ans d'expérience en assurance dommages et responsabilité civile. J'évalue les risques avec rigueur pour proposer les couvertures adaptées.",
        "profilCV": "Souscripteur en assurance · 10 ans · Évaluation de risques, assurance dommages, RC professionnelle, tarification.",
        "anneePremEmploi": 2013, "mobilite": "National", "contrat": "CDI",
        "slogan": "Évaluer le risque, protéger l'avenir.",
        "couleur": "#1565C0", "portfolioFichier": "proman",
        "experiences": [
            {"entreprise": "NSIA Assurances Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2017, 5, 1), "fin": None, "enCours": True, "description": "Souscription de contrats d'assurance dommages pour entreprises. Évaluation des risques industriels et commerciaux.", "poste": "Souscripteur Senior", "missionClient": None},
            {"entreprise": "Saham Assurance CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2013, 3, 1), "fin": date(2017, 4, 30), "enCours": False, "description": "Souscription de contrats auto et habitation. Gestion de sinistres.", "poste": "Souscripteur Junior", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master Actuariat et Assurance", "ecole": "IIA (Institut International des Assurances de Yaoundé)", "ville": "Yaoundé", "pays": "CAMEROUN", "debut": date(2011, 9, 1), "fin": date(2013, 6, 30), "niveau": "Bac+5", "desc": "Spécialité gestion des risques et actuariat."},
        ],
        "competences": [("Évaluation de risques", 5), ("Tarification", 4), ("Assurance dommages", 5), ("Réassurance", 3), ("Négociation contrats", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2")],
        "interets":    ["Finance", "Tennis", "Échecs"],
        "projets": [
            {"titre": "Refonte de la grille tarifaire dommages", "contexte": "Grille tarifaire obsolète face à l'évolution des risques industriels.", "realisation": "Nouvelle grille basée sur l'historique sinistres, amélioration de la rentabilité du portefeuille de 12%.", "url": "", "debut": date(2021, 1, 1), "fin": date(2021, 8, 31)},
        ],
        "benevolats": [{"titre": "Sensibilisation à l'assurance pour PME", "organisation": "CGECI Académie", "debut": date(2019, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/theodore-anoma")],
    },

    # ── 76 ── CLINIC-PRO ──────────────────────────────────────────────────────
    {
        "prenom": "Colette", "nom": "TANOH", "sexe": "Femme",
        "email": "colette.tanoh@demo.test", "telephone": "+225 05 70 81 92 03",
        "naissance": date(1985, 11, 9), "nationalite": "Ivoirienne",
        "adresse": "Abobo Sagbé", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Secrétaire Générale de Mairie",
        "secteur": "Administration publique",
        "biographie": "Secrétaire générale de mairie avec 13 ans d'expérience dans l'administration territoriale. Je coordonne les services municipaux au service des citoyens.",
        "profilCV": "Secrétaire générale de mairie · 13 ans · Administration territoriale, gestion des services municipaux, état civil, marchés publics.",
        "anneePremEmploi": 2010, "mobilite": "Local", "contrat": "CDI",
        "slogan": "Servir la commune, servir les citoyens.",
        "couleur": "#009A44", "portfolioFichier": "clinic-pro",
        "experiences": [
            {"entreprise": "Mairie d'Abobo", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2016, 1, 1), "fin": None, "enCours": True, "description": "Coordination de 8 services municipaux (état civil, urbanisme, finances). Supervision de 45 agents.", "poste": "Secrétaire Générale", "missionClient": None},
            {"entreprise": "Mairie de Yopougon", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2010, 9, 1), "fin": date(2015, 12, 31), "enCours": False, "description": "Chef du service de l'état civil. Modernisation des procédures d'enregistrement.", "poste": "Chef de Service État Civil", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master Administration Publique", "ecole": "ENA Côte d'Ivoire", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2008, 9, 1), "fin": date(2010, 6, 30), "niveau": "Bac+5", "desc": "Spécialité gestion des collectivités territoriales."},
        ],
        "competences": [("Administration territoriale", 5), ("Gestion des marchés publics", 4), ("Management d'équipe", 5), ("État civil", 5), ("Finances locales", 4)],
        "langues":     [("Français", "C2"), ("Dioula", "C2"), ("Anglais", "A2")],
        "interets":    ["Vie associative", "Lecture", "Chant choral"],
        "projets": [
            {"titre": "Modernisation de l'état civil d'Abobo", "contexte": "Délais d'obtention des actes trop longs pour les citoyens.", "realisation": "Digitalisation partielle des registres, délai moyen de délivrance réduit de 15 à 5 jours.", "url": "", "debut": date(2019, 1, 1), "fin": date(2020, 6, 30)},
        ],
        "benevolats": [{"titre": "Facilitatrice d'accès aux papiers d'identité", "organisation": "ONG Un Papier Pour Tous", "debut": date(2018, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/colette-tanoh")],
    },

    # ── 77 ── TECH-DASHBOARD ──────────────────────────────────────────────────
    {
        "prenom": "Wilfried", "nom": "N'DA", "sexe": "Homme",
        "email": "wilfried.nda@demo.test", "telephone": "+225 07 81 92 03 14",
        "naissance": date(1990, 7, 26), "nationalite": "Ivoirienne",
        "adresse": "Cocody Angré Château", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Administrateur Systèmes et Réseaux",
        "secteur": "Numérique (Tech)",
        "biographie": "Administrateur systèmes et réseaux avec 8 ans d'expérience dans la gestion d'infrastructures IT critiques. Je garantis la disponibilité et la sécurité des systèmes d'information.",
        "profilCV": "Administrateur systèmes · 8 ans · Windows Server, Linux, virtualisation, sécurité IT, supervision d'infrastructure.",
        "anneePremEmploi": 2016, "mobilite": "National", "contrat": "CDI",
        "slogan": "Des systèmes toujours disponibles.",
        "couleur": "#1a1a2e", "portfolioFichier": "tech-dashboard",
        "experiences": [
            {"entreprise": "Société Générale Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 4, 1), "fin": None, "enCours": True, "description": "Administration de l'infrastructure serveurs (Windows/Linux) de la banque. Gestion de la virtualisation VMware. Astreinte sécurité 24/7.", "poste": "Administrateur Systèmes Senior", "missionClient": None},
            {"entreprise": "Groupe NSIA", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2016, 5, 1), "fin": date(2019, 3, 31), "enCours": False, "description": "Support et administration des serveurs et postes de travail. Gestion de l'Active Directory.", "poste": "Administrateur Systèmes Junior", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Licence Réseaux et Systèmes", "ecole": "ESATIC Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2013, 9, 1), "fin": date(2016, 6, 30), "niveau": "BAC +3", "desc": "Spécialité administration systèmes et sécurité informatique."},
        ],
        "competences": [("Windows Server", 5), ("Linux", 4), ("Virtualisation VMware", 4), ("Sécurité IT", 4), ("Active Directory", 5)],
        "langues":     [("Français", "C2"), ("Anglais", "B2")],
        "interets":    ["Cybersécurité", "Jeux vidéo", "Photographie"],
        "projets": [
            {"titre": "Migration vers infrastructure virtualisée SGCI", "contexte": "Serveurs physiques vieillissants et coûteux à maintenir.", "realisation": "Virtualisation de 60 serveurs, réduction des coûts d'infrastructure de 25%.", "url": "", "debut": date(2021, 1, 1), "fin": date(2021, 9, 30)},
        ],
        "benevolats": [{"titre": "Support informatique associations locales", "organisation": "Djelia Tech CI", "debut": date(2020, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/wilfried-nda")],
    },

    # ── 78 ── ORANGE-VIBRANT ──────────────────────────────────────────────────
    {
        "prenom": "Micheline", "nom": "DIBI", "sexe": "Femme",
        "email": "micheline.dibi@demo.test", "telephone": "+225 05 92 03 14 25",
        "naissance": date(1991, 3, 4), "nationalite": "Ivoirienne",
        "adresse": "Plateau, Rue Lecoeur", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Journaliste Économique",
        "secteur": "Médias & Journalisme",
        "biographie": "Journaliste économique avec 8 ans d'expérience en presse écrite et digitale. Je décrypte l'actualité économique ivoirienne et ouest-africaine pour un large public.",
        "profilCV": "Journaliste économique · 8 ans · Enquête, presse écrite et digitale, décryptage économique, interviews.",
        "anneePremEmploi": 2016, "mobilite": "National", "contrat": "CDI",
        "slogan": "Informer pour éclairer les décisions.",
        "couleur": "#F77F00", "portfolioFichier": "orange-vibrant",
        "experiences": [
            {"entreprise": "Fraternité Matin", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 9, 1), "fin": None, "enCours": True, "description": "Rédactrice en chef adjointe de la rubrique économie. Rédaction d'enquêtes sur les filières cacao et pétrole.", "poste": "Journaliste Économique Senior", "missionClient": None},
            {"entreprise": "Radio Côte d'Ivoire (RCI)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2016, 3, 1), "fin": date(2019, 8, 31), "enCours": False, "description": "Présentatrice de la chronique économique quotidienne. Interviews d'acteurs économiques.", "poste": "Journaliste Radio", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master en Journalisme", "ecole": "ISTC Polytechnique Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2014, 9, 1), "fin": date(2016, 6, 30), "niveau": "Bac+5", "desc": "Spécialité journalisme économique et enquête."},
        ],
        "competences": [("Enquête journalistique", 5), ("Rédaction web", 5), ("Interview", 5), ("Analyse économique", 4), ("Prise de parole publique", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Baoulé", "C1")],
        "interets":    ["Actualité économique", "Lecture", "Débats"],
        "projets": [
            {"titre": "Enquête sur la filière cacao", "contexte": "Opacité dénoncée sur la répartition des revenus du cacao.", "realisation": "Série de 5 articles primés, forte reprise dans les médias régionaux.", "url": "", "debut": date(2021, 3, 1), "fin": date(2021, 7, 31)},
        ],
        "benevolats": [{"titre": "Formatrice écriture journalistique", "organisation": "Institut de la Communication d'Abidjan", "debut": date(2020, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/micheline-dibi"), ("x", "https://x.com/michelinedibi")],
    },

    # ── 79 ── SNAPFOLIO ───────────────────────────────────────────────────────
    {
        "prenom": "Alassane", "nom": "TRAORE", "sexe": "Homme",
        "email": "alassane.traore@demo.test", "telephone": "+225 07 03 14 25 36",
        "naissance": date(1989, 9, 13), "nationalite": "Ivoirienne",
        "adresse": "Yopougon Andokoi", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Technicien Agroalimentaire",
        "secteur": "Agriculture & Agro-alimentaire",
        "biographie": "Technicien agroalimentaire avec 10 ans d'expérience en transformation de produits locaux. Je supervise les lignes de production dans le respect des normes d'hygiène.",
        "profilCV": "Technicien agroalimentaire · 10 ans · Transformation alimentaire, contrôle qualité, normes HACCP, supervision de production.",
        "anneePremEmploi": 2013, "mobilite": "National", "contrat": "CDI",
        "slogan": "Transformer localement, nourrir durablement.",
        "couleur": "#009A44", "portfolioFichier": "snapfolio",
        "experiences": [
            {"entreprise": "SIFCA (usine de transformation huile de palme)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2017, 2, 1), "fin": None, "enCours": True, "description": "Supervision de la ligne de raffinage d'huile de palme. Contrôle qualité et respect des normes HACCP.", "poste": "Technicien Agroalimentaire Senior", "missionClient": None},
            {"entreprise": "Coopérative Agricole de Yopougon", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2013, 4, 1), "fin": date(2017, 1, 31), "enCours": False, "description": "Transformation de produits vivriers (manioc, banane plantain). Contrôle des process de séchage.", "poste": "Technicien de Transformation", "missionClient": None},
        ],
        "formations": [
            {"diplome": "BTS Industries Agroalimentaires", "ecole": "INPHB Yamoussoukro", "ville": "Yamoussoukro", "pays": "COTE D'IVOIRE", "debut": date(2011, 9, 1), "fin": date(2013, 6, 30), "niveau": "BAC +2", "desc": "Spécialité transformation et conservation des aliments."},
        ],
        "competences": [("Transformation alimentaire", 5), ("HACCP", 5), ("Contrôle qualité", 4), ("Supervision de production", 4), ("Maintenance de premier niveau", 3)],
        "langues":     [("Français", "C1"), ("Dioula", "C2"), ("Anglais", "A2")],
        "interets":    ["Agriculture", "Football", "Cuisine locale"],
        "projets": [
            {"titre": "Amélioration du rendement de raffinage SIFCA", "contexte": "Taux de perte de matière première trop élevé.", "realisation": "Optimisation des réglages de la ligne, réduction des pertes de 15%.", "url": "", "debut": date(2020, 1, 1), "fin": date(2020, 8, 31)},
        ],
        "benevolats": [{"titre": "Formateur transformation agroalimentaire", "organisation": "Coopérative Agricole de Yopougon", "debut": date(2018, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/alassane-traore")],
    },

    # ── 80 ── PROMAN-GLASS ────────────────────────────────────────────────────
    {
        "prenom": "Édwige", "nom": "SESS", "sexe": "Femme",
        "email": "edwige.sess@demo.test", "telephone": "+225 05 14 25 36 47",
        "naissance": date(1987, 6, 21), "nationalite": "Ivoirienne",
        "adresse": "Cocody II Plateaux Vallon", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Responsable Formation RH",
        "secteur": "Ressources Humaines",
        "biographie": "Responsable formation avec 10 ans d'expérience dans la conception et le pilotage de plans de formation en entreprise. Je développe les compétences au service de la performance.",
        "profilCV": "Responsable formation · 10 ans · Ingénierie de formation, gestion des compétences, e-learning, budget formation.",
        "anneePremEmploi": 2013, "mobilite": "National", "contrat": "CDI",
        "slogan": "Former aujourd'hui pour performer demain.",
        "couleur": "#E85D4A", "portfolioFichier": "proman-glass",
        "experiences": [
            {"entreprise": "MTN Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2018, 6, 1), "fin": None, "enCours": True, "description": "Pilotage du plan de formation annuel (1 200 collaborateurs). Déploiement d'une plateforme e-learning interne.", "poste": "Responsable Formation", "missionClient": None},
            {"entreprise": "Orange Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2013, 9, 1), "fin": date(2018, 5, 31), "enCours": False, "description": "Chargée de formation pour les équipes commerciales et techniques.", "poste": "Chargée de Formation", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master Gestion des Ressources Humaines", "ecole": "ISTC Polytechnique Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2011, 9, 1), "fin": date(2013, 6, 30), "niveau": "Bac+5", "desc": "Spécialité ingénierie de formation et développement des compétences."},
        ],
        "competences": [("Ingénierie de formation", 5), ("Gestion des compétences", 5), ("E-learning", 4), ("Budget formation", 4), ("Animation de formation", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Baoulé", "B1")],
        "interets":    ["Développement personnel", "Lecture", "Voyages"],
        "projets": [
            {"titre": "Déploiement plateforme e-learning MTN", "contexte": "Coûts élevés de formation présentielle sur tout le territoire.", "realisation": "Migration de 40% du catalogue formation en ligne, économie de 200M FCFA/an.", "url": "", "debut": date(2020, 1, 1), "fin": date(2020, 12, 31)},
        ],
        "benevolats": [{"titre": "Formatrice bénévole insertion professionnelle", "organisation": "Fondation Jeunesse Numérique CI", "debut": date(2019, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/edwige-sess")],
    },

    # ── 81 ── STYLE ───────────────────────────────────────────────────────────
    {
        "prenom": "Désiré", "nom": "BAMBA", "sexe": "Homme",
        "email": "desire.bamba@demo.test", "telephone": "+225 07 25 36 47 58",
        "naissance": date(1985, 8, 9), "nationalite": "Ivoirienne",
        "adresse": "Vridi Zone Industrielle", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "ABCDE", "titre": "Responsable Sécurité HSE",
        "secteur": "Industrie manufacturière",
        "biographie": "Responsable sécurité HSE avec 14 ans d'expérience en milieu industriel. Ma priorité : zéro accident et une culture sécurité partagée par tous les collaborateurs.",
        "profilCV": "Responsable HSE · 14 ans · Prévention des risques, audits sécurité, formation, gestion de crise industrielle.",
        "anneePremEmploi": 2009, "mobilite": "National", "contrat": "CDI",
        "slogan": "La sécurité n'est jamais une option.",
        "couleur": "#003366", "portfolioFichier": "style",
        "experiences": [
            {"entreprise": "TotalEnergies Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2015, 4, 1), "fin": None, "enCours": True, "description": "Pilotage de la politique HSE sur le dépôt pétrolier. Conduite d'audits sécurité mensuels. Formation de 300 collaborateurs par an.", "poste": "Responsable HSE Senior", "missionClient": None},
            {"entreprise": "SOLIBRA (Heineken Côte d'Ivoire)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2009, 6, 1), "fin": date(2015, 3, 31), "enCours": False, "description": "Animateur sécurité sur les lignes de production. Enquêtes accidents du travail.", "poste": "Animateur HSE", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master QHSE", "ecole": "INPHB Yamoussoukro", "ville": "Yamoussoukro", "pays": "COTE D'IVOIRE", "debut": date(2007, 9, 1), "fin": date(2009, 6, 30), "niveau": "Bac+5", "desc": "Spécialité gestion des risques industriels."},
        ],
        "competences": [("Prévention des risques", 5), ("Audits sécurité", 5), ("Gestion de crise", 4), ("Formation HSE", 5), ("Réglementation ICPE", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Dioula", "C1")],
        "interets":    ["Sécurité civile", "Football", "Randonnée"],
        "projets": [
            {"titre": "Programme zéro accident TotalEnergies", "contexte": "Objectif de réduction drastique des accidents du travail.", "realisation": "Campagne de sensibilisation et audits renforcés, 0 accident avec arrêt sur 18 mois consécutifs.", "url": "", "debut": date(2021, 1, 1), "fin": date(2022, 6, 30)},
        ],
        "benevolats": [{"titre": "Formateur sécurité incendie", "organisation": "Sapeurs-Pompmilitaires de Côte d'Ivoire", "debut": date(2017, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/desire-bamba-hse")],
    },

    # ── 82 ── SNAPFOLIO ───────────────────────────────────────────────────────
    {
        "prenom": "Laetitia", "nom": "ANGAMAN", "sexe": "Femme",
        "email": "laetitia.angaman@demo.test", "telephone": "+225 05 36 47 58 69",
        "naissance": date(1994, 5, 27), "nationalite": "Ivoirienne",
        "adresse": "Cocody Danga Sud", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Photographe de Mode",
        "secteur": "Mode & Artisanat",
        "biographie": "Photographe de mode avec 6 ans d'expérience, je capture l'élégance et l'identité des créateurs africains. Mon regard mêle esthétique contemporaine et culture locale.",
        "profilCV": "Photographe de mode · 6 ans · Shooting mode, retouche photo, direction artistique, campagnes publicitaires.",
        "anneePremEmploi": 2018, "mobilite": "International", "contrat": "Freelance",
        "slogan": "Capturer l'élégance, révéler l'identité.",
        "couleur": "#1a1a2e", "portfolioFichier": "snapfolio",
        "experiences": [
            {"entreprise": "Studio LA Photographie (activité indépendante)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 1, 1), "fin": None, "enCours": True, "description": "Shootings pour créateurs de mode et campagnes publicitaires. Couverture de la Fashion Week d'Abidjan.", "poste": "Photographe Indépendante", "missionClient": {"client": "Sandrine Able Mode", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2022, 3, 1), "fin": date(2022, 3, 31), "desc": "Shooting de la collection 'Racines' pour la Fashion Week d'Abidjan."}},
            {"entreprise": "Magazine Amina Afrique", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2018, 2, 1), "fin": date(2019, 12, 31), "enCours": False, "description": "Photographe pour les éditoriaux mode du magazine.", "poste": "Photographe Junior", "missionClient": None},
        ],
        "formations": [
            {"diplome": "BTS Photographie", "ecole": "École Supérieure de Mode d'Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2016, 9, 1), "fin": date(2018, 6, 30), "niveau": "BAC +2", "desc": "Spécialité photographie de mode et retouche numérique."},
        ],
        "competences": [("Photographie de mode", 5), ("Retouche Photoshop", 5), ("Direction artistique", 4), ("Éclairage studio", 4), ("Storytelling visuel", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2")],
        "interets":    ["Mode africaine", "Cinéma", "Voyages"],
        "projets": [
            {"titre": "Shooting collection 'Racines'", "contexte": "Campagne de lancement pour la Fashion Week d'Abidjan.", "realisation": "Série de 60 clichés, forte reprise sur les réseaux sociaux (2M+ vues cumulées).", "url": "https://instagram.com/la.photographie.ci", "debut": date(2022, 3, 1), "fin": date(2022, 3, 31)},
        ],
        "benevolats": [{"titre": "Photographe bénévole événements caritatifs", "organisation": "Fondation Children of Africa", "debut": date(2020, 6, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/laetitia-angaman"), ("instagram", "https://instagram.com/la.photographie.ci")],
    },

    # ── 83 ── ORANGE-VIBRANT ──────────────────────────────────────────────────
    {
        "prenom": "Fulgence", "nom": "DIGBEU", "sexe": "Homme",
        "email": "fulgence.digbeu@demo.test", "telephone": "+225 07 58 69 70 81",
        "naissance": date(1987, 12, 1), "nationalite": "Ivoirienne",
        "adresse": "Grand-Bassam Centre", "ville": "Grand-Bassam", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Ingénieur Halieute",
        "secteur": "Agriculture & Agro-alimentaire",
        "biographie": "Ingénieur halieute avec 11 ans d'expérience dans la gestion des ressources maritimes et l'aquaculture. J'accompagne le développement durable de la pêche ivoirienne.",
        "profilCV": "Ingénieur halieute · 11 ans · Aquaculture, gestion des ressources maritimes, pêche durable, appui aux coopératives.",
        "anneePremEmploi": 2012, "mobilite": "National", "contrat": "CDI",
        "slogan": "Une pêche durable pour l'avenir.",
        "couleur": "#1565C0", "portfolioFichier": "orange-vibrant",
        "experiences": [
            {"entreprise": "Ministère des Ressources Animales et Halieutiques", "pays": "COTE D'IVOIRE", "ville": "Grand-Bassam", "debut": date(2017, 3, 1), "fin": None, "enCours": True, "description": "Suivi des ressources halieutiques côtières. Accompagnement de 20 coopératives de pêcheurs. Programme de développement de l'aquaculture.", "poste": "Ingénieur Halieute Senior", "missionClient": None},
            {"entreprise": "FAO Côte d'Ivoire (projet pêche)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2012, 6, 1), "fin": date(2017, 2, 28), "enCours": False, "description": "Appui technique aux projets de pêche durable financés par la FAO.", "poste": "Ingénieur Halieute Junior", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Ingénieur Halieute", "ecole": "Centre de Recherches Océanologiques (CRO)", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2009, 9, 1), "fin": date(2012, 6, 30), "niveau": "Bac+5", "desc": "Spécialité gestion des ressources marines et aquaculture."},
        ],
        "competences": [("Aquaculture", 5), ("Gestion des ressources marines", 5), ("Pêche durable", 4), ("Formation de coopératives", 4), ("Suivi environnemental", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Nzema", "C1")],
        "interets":    ["Plongée", "Environnement marin", "Football"],
        "projets": [
            {"titre": "Programme d'aquaculture communautaire", "contexte": "Diminution des stocks de poissons côtiers.", "realisation": "Mise en place de 10 fermes aquacoles communautaires, +40% de revenus pour les pêcheurs impliqués.", "url": "", "debut": date(2020, 1, 1), "fin": date(2021, 12, 31)},
        ],
        "benevolats": [{"titre": "Sensibilisation pêche durable", "organisation": "ONG Océan Vivant CI", "debut": date(2018, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/fulgence-digbeu")],
    },

    # ── 84 ── CLINIC-PRO ──────────────────────────────────────────────────────
    {
        "prenom": "Huguette", "nom": "ASSALE", "sexe": "Femme",
        "email": "huguette.assale@demo.test", "telephone": "+225 05 69 70 81 92",
        "naissance": date(1990, 2, 16), "nationalite": "Ivoirienne",
        "adresse": "Cocody Deux-Plateaux", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Dentiste",
        "secteur": "Santé & Pharmaceutique",
        "biographie": "Chirurgienne-dentiste avec 8 ans d'expérience en cabinet privé. J'allie technicité et douceur pour offrir des soins dentaires de qualité à mes patients.",
        "profilCV": "Chirurgienne-dentiste · 8 ans · Soins conservateurs, prothèses, esthétique dentaire, chirurgie buccale.",
        "anneePremEmploi": 2016, "mobilite": "Local", "contrat": "CDI",
        "slogan": "Un sourire soigné, une confiance retrouvée.",
        "couleur": "#2A9D8F", "portfolioFichier": "clinic-pro",
        "experiences": [
            {"entreprise": "Cabinet Dentaire Sourire d'Ébène", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 1, 1), "fin": None, "enCours": True, "description": "Praticienne associée. Soins conservateurs, prothétiques et esthétiques. 20 patients par jour en moyenne.", "poste": "Chirurgienne-Dentiste Associée", "missionClient": None},
            {"entreprise": "CHU de Cocody (service odontostomatologie)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2016, 9, 1), "fin": date(2018, 12, 31), "enCours": False, "description": "Chirurgie buccale et soins d'urgence dentaire.", "poste": "Dentiste Hospitalière", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Doctorat en Chirurgie Dentaire", "ecole": "Université FHB Abidjan (UFR Odontostomatologie)", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2010, 9, 1), "fin": date(2016, 6, 30), "niveau": "BAC +6", "desc": "Spécialité chirurgie buccale et prothèses dentaires."},
        ],
        "competences": [("Soins conservateurs", 5), ("Prothèses dentaires", 4), ("Chirurgie buccale", 4), ("Esthétique dentaire", 4), ("Relation patient", 5)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Baoulé", "B1")],
        "interets":    ["Santé bucco-dentaire préventive", "Yoga", "Voyages"],
        "projets": [
            {"titre": "Campagne de prévention bucco-dentaire scolaire", "contexte": "Faible sensibilisation à l'hygiène dentaire chez les enfants.", "realisation": "Sensibilisation dans 8 écoles primaires, plus de 1 500 enfants touchés.", "url": "", "debut": date(2021, 1, 1), "fin": date(2021, 6, 30)},
        ],
        "benevolats": [{"titre": "Consultations dentaires gratuites", "organisation": "Ordre des Chirurgiens-Dentistes de Côte d'Ivoire", "debut": date(2018, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/huguette-assale")],
    },

    # ── 85 ── PROMAN-PRO ──────────────────────────────────────────────────────
    {
        "prenom": "Raoul", "nom": "GOZE", "sexe": "Homme",
        "email": "raoul.goze@demo.test", "telephone": "+225 07 70 81 92 03",
        "naissance": date(1984, 4, 5), "nationalite": "Ivoirienne",
        "adresse": "Port-Bouët Gonzagueville", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Agent Portuaire",
        "secteur": "Logistique & Transport",
        "biographie": "Agent portuaire avec 16 ans d'expérience au Port Autonome d'Abidjan. Je coordonne les opérations de manutention et de chargement des navires en toute sécurité.",
        "profilCV": "Agent portuaire · 16 ans · Manutention portuaire, coordination navires, sécurité portuaire, gestion des conteneurs.",
        "anneePremEmploi": 2007, "mobilite": "Local", "contrat": "CDI",
        "slogan": "Le port ne dort jamais, ni ma vigilance.",
        "couleur": "#003366", "portfolioFichier": "proman-pro",
        "experiences": [
            {"entreprise": "Port Autonome d'Abidjan", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2013, 1, 1), "fin": None, "enCours": True, "description": "Coordination des opérations de manutention de conteneurs. Supervision d'une équipe de 15 dockers. Gestion de la sécurité portuaire.", "poste": "Chef d'Équipe Manutention", "missionClient": None},
            {"entreprise": "Bolloré Transport & Logistics CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2007, 5, 1), "fin": date(2012, 12, 31), "enCours": False, "description": "Docker puis chef d'équipe adjoint. Chargement et déchargement de navires porte-conteneurs.", "poste": "Docker", "missionClient": None},
        ],
        "formations": [
            {"diplome": "BTS Logistique Portuaire", "ecole": "Institut Supérieur de Commerce d'Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2005, 9, 1), "fin": date(2007, 6, 30), "niveau": "BAC +2", "desc": "Spécialité opérations portuaires et logistique maritime."},
        ],
        "competences": [("Manutention portuaire", 5), ("Coordination navires", 5), ("Sécurité portuaire", 5), ("Gestion d'équipe", 4), ("Gestion des conteneurs", 4)],
        "langues":     [("Français", "C1"), ("Ebrié", "C2"), ("Anglais", "A2")],
        "interets":    ["Football", "Pêche", "Musique"],
        "projets": [
            {"titre": "Réduction des temps d'escale navires", "contexte": "Temps de manutention jugés trop longs par les armateurs.", "realisation": "Réorganisation des équipes de manutention, temps d'escale moyen réduit de 20%.", "url": "", "debut": date(2020, 1, 1), "fin": date(2020, 10, 31)},
        ],
        "benevolats": [{"titre": "Formateur sécurité portuaire", "organisation": "Syndicat des Dockers d'Abidjan", "debut": date(2016, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/raoul-goze")],
    },

    # ── 86 ── PROMAN-GLASS ────────────────────────────────────────────────────
    {
        "prenom": "Sylvie", "nom": "GUEYE", "sexe": "Femme",
        "email": "sylvie.gueye@demo.test", "telephone": "+225 05 81 92 03 14",
        "naissance": date(1992, 9, 18), "nationalite": "Ivoirienne",
        "adresse": "Plateau, Avenue Delafosse", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Conseillère Clientèle Bancaire",
        "secteur": "Services financiers",
        "biographie": "Conseillère clientèle bancaire avec 6 ans d'expérience auprès de particuliers et professionnels. J'accompagne mes clients dans leurs projets avec pédagogie et disponibilité.",
        "profilCV": "Conseillère clientèle · 6 ans · Relation client, produits bancaires, crédit, épargne, vente de services financiers.",
        "anneePremEmploi": 2018, "mobilite": "Local", "contrat": "CDI",
        "slogan": "Votre projet, notre priorité.",
        "couleur": "#1565C0", "portfolioFichier": "proman-glass",
        "experiences": [
            {"entreprise": "BOA Côte d'Ivoire (Bank of Africa)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 3, 1), "fin": None, "enCours": True, "description": "Gestion d'un portefeuille de 400 clients particuliers et professionnels. Vente de crédits et produits d'épargne.", "poste": "Conseillère Clientèle Senior", "missionClient": None},
            {"entreprise": "Ecobank Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2018, 4, 1), "fin": date(2020, 2, 29), "enCours": False, "description": "Accueil et conseil clientèle en agence. Ouverture de comptes et souscription de produits.", "poste": "Chargée d'Accueil Clientèle", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Licence Banque et Finance", "ecole": "ISTC Polytechnique Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2015, 9, 1), "fin": date(2018, 6, 30), "niveau": "BAC +3", "desc": "Spécialité produits bancaires et relation client."},
        ],
        "competences": [("Relation client", 5), ("Produits bancaires", 5), ("Vente de crédit", 4), ("Gestion de portefeuille", 4), ("Conformité KYC", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B1"), ("Baoulé", "C1")],
        "interets":    ["Finance personnelle", "Danse", "Voyages"],
        "projets": [
            {"titre": "Campagne d'ouverture de comptes jeunes", "contexte": "Faible pénétration bancaire chez les 18-25 ans.", "realisation": "Animation de 6 forums universitaires, 300 nouveaux comptes ouverts en 3 mois.", "url": "", "debut": date(2021, 9, 1), "fin": date(2021, 12, 31)},
        ],
        "benevolats": [{"titre": "Éducation financière jeunes", "organisation": "Junior Achievement Côte d'Ivoire", "debut": date(2019, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/sylvie-gueye")],
    },

    # ── 87 ── TECH-DASHBOARD ──────────────────────────────────────────────────
    {
        "prenom": "Steve", "nom": "OKA", "sexe": "Homme",
        "email": "steve.oka@demo.test", "telephone": "+225 07 92 03 14 25",
        "naissance": date(1993, 1, 24), "nationalite": "Ivoirienne",
        "adresse": "Cocody Riviera 3", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Ingénieur DevOps",
        "secteur": "Numérique (Tech)",
        "biographie": "Ingénieur DevOps avec 5 ans d'expérience dans l'automatisation d'infrastructures cloud. Je fluidifie le déploiement continu pour des équipes de développement plus efficaces.",
        "profilCV": "Ingénieur DevOps · 5 ans · CI/CD, Docker, Kubernetes, AWS, Infrastructure as Code (Terraform).",
        "anneePremEmploi": 2019, "mobilite": "International", "contrat": "CDI",
        "slogan": "Automatiser pour livrer plus vite, en confiance.",
        "couleur": "#1a1a2e", "portfolioFichier": "tech-dashboard",
        "experiences": [
            {"entreprise": "WAVE Mobile Money", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2021, 6, 1), "fin": None, "enCours": True, "description": "Mise en place de pipelines CI/CD pour les équipes produit. Gestion de l'infrastructure Kubernetes sur AWS. Astreinte production.", "poste": "Ingénieur DevOps Senior", "missionClient": None},
            {"entreprise": "Baguera Digital", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 3, 1), "fin": date(2021, 5, 31), "enCours": False, "description": "Automatisation des déploiements pour plusieurs projets clients. Conteneurisation d'applications legacy.", "poste": "Ingénieur DevOps Junior", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Ingénieur Informatique", "ecole": "ESATIC Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2016, 9, 1), "fin": date(2019, 6, 30), "niveau": "Bac+5", "desc": "Spécialité cloud computing et administration systèmes."},
        ],
        "competences": [("Docker/Kubernetes", 5), ("CI/CD", 5), ("AWS", 4), ("Terraform", 4), ("Monitoring (Grafana/Prometheus)", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "C1")],
        "interets":    ["Cloud computing", "Basketball", "Musique électronique"],
        "projets": [
            {"titre": "Migration Kubernetes Wave", "contexte": "Infrastructure monolithique difficile à faire évoluer.", "realisation": "Conteneurisation de 15 services, temps de déploiement réduit de 45 à 5 minutes.", "url": "https://github.com/demo/wave-k8s", "debut": date(2022, 1, 1), "fin": date(2022, 8, 31)},
        ],
        "benevolats": [{"titre": "Mentor DevOps", "organisation": "Djelia Tech CI", "debut": date(2021, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/steve-oka"), ("github", "https://github.com/steveoka")],
    },

    # ── 88 ── RETRO-MAG ───────────────────────────────────────────────────────
    {
        "prenom": "Florentine", "nom": "AHOUA", "sexe": "Femme",
        "email": "florentine.ahoua@demo.test", "telephone": "+225 05 03 14 25 36",
        "naissance": date(1988, 6, 12), "nationalite": "Ivoirienne",
        "adresse": "Plateau, Rue du Musée", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Bibliothécaire-Documentaliste",
        "secteur": "Éducation & Formation",
        "biographie": "Bibliothécaire-documentaliste avec 9 ans d'expérience en gestion de fonds documentaires. Je facilite l'accès à la connaissance et anime des programmes de lecture publique.",
        "profilCV": "Bibliothécaire-documentaliste · 9 ans · Gestion documentaire, catalogage, animation lecture publique, numérisation.",
        "anneePremEmploi": 2014, "mobilite": "Local", "contrat": "CDI",
        "slogan": "Ouvrir les portes de la connaissance.",
        "couleur": "#C9A227", "portfolioFichier": "retro-mag",
        "experiences": [
            {"entreprise": "Bibliothèque Nationale de Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2017, 9, 1), "fin": None, "enCours": True, "description": "Gestion du fonds documentaire national. Pilotage du programme de numérisation des archives. Animation d'ateliers de lecture pour enfants.", "poste": "Bibliothécaire-Documentaliste Senior", "missionClient": None},
            {"entreprise": "Institut Français de Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2014, 9, 1), "fin": date(2017, 8, 31), "enCours": False, "description": "Gestion du centre de documentation. Organisation d'événements littéraires.", "poste": "Documentaliste", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master en Sciences de l'Information et Documentation", "ecole": "Université FHB Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2012, 9, 1), "fin": date(2014, 6, 30), "niveau": "Bac+5", "desc": "Spécialité gestion documentaire et bibliothéconomie."},
        ],
        "competences": [("Gestion documentaire", 5), ("Catalogage", 5), ("Numérisation d'archives", 4), ("Animation de lecture", 5), ("Recherche documentaire", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Baoulé", "C1")],
        "interets":    ["Littérature", "Histoire", "Écriture"],
        "projets": [
            {"titre": "Numérisation des archives nationales", "contexte": "Fonds documentaire ancien fragile et peu accessible.", "realisation": "Numérisation de 15 000 documents historiques, mise en ligne d'une partie du fonds.", "url": "", "debut": date(2020, 1, 1), "fin": date(2022, 3, 31)},
        ],
        "benevolats": [{"titre": "Bibliothèque itinérante pour enfants", "organisation": "Association Lire en Côte d'Ivoire", "debut": date(2018, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/florentine-ahoua")],
    },

    # ── 89 ── PROMAN ──────────────────────────────────────────────────────────
    {
        "prenom": "Régis", "nom": "KOUADIO", "sexe": "Homme",
        "email": "regis.kouadio@demo.test", "telephone": "+225 07 14 25 36 47",
        "naissance": date(1986, 10, 5), "nationalite": "Ivoirienne",
        "adresse": "Cocody Angré 7e Tranche", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Topographe",
        "secteur": "BTP & Génie Civil",
        "biographie": "Topographe avec 13 ans d'expérience dans les levés topographiques pour projets d'infrastructure et de construction. Précision et fiabilité sont les fondations de mon travail.",
        "profilCV": "Topographe · 13 ans · Levés topographiques, implantation de chantier, GPS RTK, cartographie SIG.",
        "anneePremEmploi": 2010, "mobilite": "National", "contrat": "CDI",
        "slogan": "Mesurer avec précision, construire avec confiance.",
        "couleur": "#009A44", "portfolioFichier": "proman",
        "experiences": [
            {"entreprise": "Eiffage Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2014, 6, 1), "fin": None, "enCours": True, "description": "Réalisation des levés topographiques pour des projets d'infrastructures routières. Implantation de chantiers de grande envergure.", "poste": "Topographe Senior", "missionClient": None},
            {"entreprise": "Cabinet de Géomètre-Expert Kouadio & Fils", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2010, 3, 1), "fin": date(2014, 5, 31), "enCours": False, "description": "Levés fonciers et bornage de terrains. Établissement de plans cadastraux.", "poste": "Topographe Junior", "missionClient": None},
        ],
        "formations": [
            {"diplome": "BTS Topographie", "ecole": "INPHB Yamoussoukro", "ville": "Yamoussoukro", "pays": "COTE D'IVOIRE", "debut": date(2008, 9, 1), "fin": date(2010, 6, 30), "niveau": "BAC +2", "desc": "Spécialité levés topographiques et cartographie."},
        ],
        "competences": [("Levés topographiques", 5), ("GPS RTK", 5), ("SIG (QGIS)", 4), ("Implantation de chantier", 5), ("AutoCAD Civil 3D", 4)],
        "langues":     [("Français", "C2"), ("Baoulé", "C2"), ("Anglais", "A2")],
        "interets":    ["Cartographie", "Randonnée", "Photographie de terrain"],
        "projets": [
            {"titre": "Levé topographique échangeur Riviera 2", "contexte": "Projet d'infrastructure routière majeure d'Abidjan.", "realisation": "Levés précis sur 4 km, implantation sans reprise, projet livré dans les délais.", "url": "", "debut": date(2019, 6, 1), "fin": date(2020, 3, 31)},
        ],
        "benevolats": [{"titre": "Formation topographie jeunes techniciens", "organisation": "Ordre des Géomètres-Experts de Côte d'Ivoire", "debut": date(2017, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/regis-kouadio")],
    },

    # ── 90 ── CLINIC-PRO ──────────────────────────────────────────────────────
    {
        "prenom": "Angeline", "nom": "OULAI", "sexe": "Femme",
        "email": "angeline.oulai@demo.test", "telephone": "+225 05 25 36 47 58",
        "naissance": date(1991, 7, 8), "nationalite": "Ivoirienne",
        "adresse": "Yopougon Maroc", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Éducatrice Spécialisée",
        "secteur": "ONG & Secteur public",
        "biographie": "Éducatrice spécialisée avec 7 ans d'expérience auprès d'enfants en situation de handicap. Chaque enfant a un potentiel unique que je m'efforce de révéler.",
        "profilCV": "Éducatrice spécialisée · 7 ans · Accompagnement d'enfants en situation de handicap, pédagogie adaptée, inclusion scolaire.",
        "anneePremEmploi": 2017, "mobilite": "Local", "contrat": "CDI",
        "slogan": "Chaque enfant a un potentiel à révéler.",
        "couleur": "#2A9D8F", "portfolioFichier": "clinic-pro",
        "experiences": [
            {"entreprise": "Centre Suzanne Aggrey (enfants en situation de handicap)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 9, 1), "fin": None, "enCours": True, "description": "Accompagnement individualisé de 15 enfants en situation de handicap. Élaboration de projets pédagogiques personnalisés avec les familles.", "poste": "Éducatrice Spécialisée Référente", "missionClient": None},
            {"entreprise": "École Inclusive Les Petits Génies", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2017, 9, 1), "fin": date(2019, 8, 31), "enCours": False, "description": "Accompagnement scolaire d'enfants à besoins spécifiques en milieu ordinaire.", "poste": "Éducatrice Spécialisée", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Diplôme d'État d'Éducatrice Spécialisée", "ecole": "INFAS Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2014, 9, 1), "fin": date(2017, 6, 30), "niveau": "BAC +3", "desc": "Spécialité accompagnement du handicap et inclusion."},
        ],
        "competences": [("Pédagogie adaptée", 5), ("Accompagnement du handicap", 5), ("Travail avec les familles", 4), ("Inclusion scolaire", 4), ("Communication non-verbale", 4)],
        "langues":     [("Français", "C2"), ("Dioula", "C1"), ("Anglais", "A2")],
        "interets":    ["Art-thérapie", "Musique", "Bénévolat"],
        "projets": [
            {"titre": "Programme d'inclusion scolaire pilote", "contexte": "Peu d'écoles ordinaires accueillant des enfants en situation de handicap.", "realisation": "Accompagnement de 8 enfants vers une inclusion réussie en école ordinaire.", "url": "", "debut": date(2020, 9, 1), "fin": date(2022, 6, 30)},
        ],
        "benevolats": [{"titre": "Sensibilisation au handicap en milieu scolaire", "organisation": "Fédération Ivoirienne des Associations de Personnes Handicapées", "debut": date(2018, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/angeline-oulai")],
    },

    # ── 91 ── STYLE ───────────────────────────────────────────────────────────
    {
        "prenom": "Blaise", "nom": "ZOKOU", "sexe": "Homme",
        "email": "blaise.zokou@demo.test", "telephone": "+225 07 36 47 58 69",
        "naissance": date(1989, 3, 21), "nationalite": "Ivoirienne",
        "adresse": "Marcory Zone 3", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Chef de Rayon Grande Distribution",
        "secteur": "Commerce & Distribution",
        "biographie": "Chef de rayon avec 9 ans d'expérience en grande distribution. Je pilote l'approvisionnement et la mise en avant des produits pour maximiser les ventes tout en satisfaisant la clientèle.",
        "profilCV": "Chef de rayon · 9 ans · Gestion de stocks, merchandising, management d'équipe, négociation fournisseurs.",
        "anneePremEmploi": 2014, "mobilite": "Local", "contrat": "CDI",
        "slogan": "Un rayon bien tenu, des clients satisfaits.",
        "couleur": "#F77F00", "portfolioFichier": "style",
        "experiences": [
            {"entreprise": "Carrefour Cap Sud Abidjan (Prosuma)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2018, 3, 1), "fin": None, "enCours": True, "description": "Gestion du rayon frais (fruits et légumes). Management d'une équipe de 6 personnes. Négociation avec les fournisseurs locaux.", "poste": "Chef de Rayon Senior", "missionClient": None},
            {"entreprise": "Casino Supermarché Deux Plateaux", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2014, 5, 1), "fin": date(2018, 2, 28), "enCours": False, "description": "Employé puis adjoint chef de rayon épicerie. Gestion des stocks et du merchandising.", "poste": "Adjoint Chef de Rayon", "missionClient": None},
        ],
        "formations": [
            {"diplome": "BTS Management des Unités Commerciales", "ecole": "Institut Supérieur de Commerce d'Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2012, 9, 1), "fin": date(2014, 6, 30), "niveau": "BAC +2", "desc": "Spécialité gestion commerciale et distribution."},
        ],
        "competences": [("Gestion de stocks", 5), ("Merchandising", 5), ("Management d'équipe", 4), ("Négociation fournisseurs", 4), ("Analyse des ventes", 4)],
        "langues":     [("Français", "C1"), ("Dioula", "C2"), ("Anglais", "A2")],
        "interets":    ["Football", "Commerce local", "Musique"],
        "projets": [
            {"titre": "Optimisation du rayon frais", "contexte": "Taux de pertes produits périssables trop élevé.", "realisation": "Nouvelle méthode de gestion des stocks (FIFO renforcé), pertes réduites de 30%.", "url": "", "debut": date(2021, 1, 1), "fin": date(2021, 6, 30)},
        ],
        "benevolats": [{"titre": "Formateur gestion de stock petits commerçants", "organisation": "Association des Commerçants de Marcory", "debut": date(2019, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/blaise-zokou")],
    },

    # ── 92 ── SNAPFOLIO ───────────────────────────────────────────────────────
    {
        "prenom": "Delphine", "nom": "ATSE", "sexe": "Femme",
        "email": "delphine.atse@demo.test", "telephone": "+225 05 47 58 69 70",
        "naissance": date(1993, 11, 2), "nationalite": "Ivoirienne",
        "adresse": "Cocody Riviera Bonoumin", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Chef de Produit Marketing",
        "secteur": "Communication & Marketing",
        "biographie": "Cheffe de produit avec 6 ans d'expérience dans l'agroalimentaire et la grande consommation. Je pilote le cycle de vie des produits, du lancement à l'optimisation.",
        "profilCV": "Cheffe de produit · 6 ans · Lancement de produits, études de marché, plan marketing, gestion de gamme.",
        "anneePremEmploi": 2018, "mobilite": "National", "contrat": "CDI",
        "slogan": "Du besoin client au produit qui marque.",
        "couleur": "#E85D4A", "portfolioFichier": "snapfolio",
        "experiences": [
            {"entreprise": "Nestlé Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 9, 1), "fin": None, "enCours": True, "description": "Gestion de la gamme de produits culinaires locaux. Pilotage du lancement de 3 nouveaux produits. Analyse de la performance commerciale.", "poste": "Cheffe de Produit Senior", "missionClient": None},
            {"entreprise": "SIFCA", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2018, 6, 1), "fin": date(2020, 8, 31), "enCours": False, "description": "Assistante chef de produit huiles alimentaires. Études de marché et suivi de la concurrence.", "poste": "Assistante Chef de Produit", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master Marketing et Gestion de Marque", "ecole": "ISTC Polytechnique Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2016, 9, 1), "fin": date(2018, 6, 30), "niveau": "Bac+5", "desc": "Spécialité gestion de produit et stratégie de marque."},
        ],
        "competences": [("Gestion de gamme", 5), ("Études de marché", 5), ("Plan marketing", 4), ("Analyse de la performance", 4), ("Coordination inter-services", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Baoulé", "B1")],
        "interets":    ["Innovation produit", "Cuisine", "Voyages"],
        "projets": [
            {"titre": "Lancement gamme culinaire 'Saveurs d'Ici'", "contexte": "Répondre à la demande croissante de produits inspirés de la cuisine locale.", "realisation": "Lancement de 3 références, objectif de vente atteint à 130% la première année.", "url": "", "debut": date(2021, 1, 1), "fin": date(2021, 12, 31)},
        ],
        "benevolats": [{"titre": "Mentorat jeunes en marketing", "organisation": "Association des Jeunes Diplômés CI", "debut": date(2020, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/delphine-atse")],
    },

    # ── 93 ── ORANGE-VIBRANT ──────────────────────────────────────────────────
    {
        "prenom": "Hamed", "nom": "SORO", "sexe": "Homme",
        "email": "hamed.soro@demo.test", "telephone": "+225 07 58 69 70 81",
        "naissance": date(1991, 5, 30), "nationalite": "Ivoirienne",
        "adresse": "Yopougon Songon", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Technicien Énergies Renouvelables",
        "secteur": "Énergie & Environnement",
        "biographie": "Technicien en énergies renouvelables avec 6 ans d'expérience dans l'installation de systèmes solaires. Je contribue à l'électrification durable des zones rurales ivoiriennes.",
        "profilCV": "Technicien énergies renouvelables · 6 ans · Installation solaire photovoltaïque, maintenance, électrification rurale.",
        "anneePremEmploi": 2018, "mobilite": "National", "contrat": "CDI",
        "slogan": "L'énergie propre pour tous, partout.",
        "couleur": "#2A9D8F", "portfolioFichier": "orange-vibrant",
        "experiences": [
            {"entreprise": "CI-ENERGIES", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 4, 1), "fin": None, "enCours": True, "description": "Installation et maintenance de centrales solaires pour l'électrification de villages. Formation de techniciens locaux.", "poste": "Technicien Énergies Renouvelables Senior", "missionClient": None},
            {"entreprise": "SolarCI (installateur privé)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2018, 2, 1), "fin": date(2020, 3, 31), "enCours": False, "description": "Installation de kits solaires résidentiels et commerciaux.", "poste": "Technicien Solaire", "missionClient": None},
        ],
        "formations": [
            {"diplome": "BTS Énergies Renouvelables", "ecole": "INPHB Yamoussoukro", "ville": "Yamoussoukro", "pays": "COTE D'IVOIRE", "debut": date(2016, 9, 1), "fin": date(2018, 6, 30), "niveau": "BAC +2", "desc": "Spécialité systèmes photovoltaïques et électrification rurale."},
        ],
        "competences": [("Installation photovoltaïque", 5), ("Maintenance de systèmes solaires", 5), ("Électrification rurale", 4), ("Dimensionnement de systèmes", 4), ("Formation technique", 3)],
        "langues":     [("Français", "C2"), ("Dioula", "C2"), ("Anglais", "B1")],
        "interets":    ["Énergies vertes", "Football", "Bricolage"],
        "projets": [
            {"titre": "Électrification solaire village de Songon", "contexte": "Village non raccordé au réseau électrique national.", "realisation": "Installation d'une mini-centrale solaire alimentant 200 foyers, formation de 3 techniciens locaux.", "url": "", "debut": date(2021, 1, 1), "fin": date(2021, 8, 31)},
        ],
        "benevolats": [{"titre": "Sensibilisation aux énergies renouvelables", "organisation": "ONG Énergie Pour Tous CI", "debut": date(2019, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/hamed-soro")],
    },

    # ── 94 ── CLINIC-PRO ──────────────────────────────────────────────────────
    {
        "prenom": "Grace", "nom": "APIA", "sexe": "Femme",
        "email": "grace.apia@demo.test", "telephone": "+225 05 70 81 92 03",
        "naissance": date(1989, 8, 27), "nationalite": "Ivoirienne",
        "adresse": "Cocody Mermoz", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Psychologue Clinicienne",
        "secteur": "Santé",
        "biographie": "Psychologue clinicienne avec 9 ans d'expérience en accompagnement thérapeutique. J'aide mes patients à traverser les épreuves de la vie avec bienveillance et écoute.",
        "profilCV": "Psychologue clinicienne · 9 ans · Thérapie individuelle, accompagnement du deuil, gestion du stress, thérapie de couple.",
        "anneePremEmploi": 2015, "mobilite": "Local", "contrat": "Freelance",
        "slogan": "Écouter pour mieux accompagner.",
        "couleur": "#2A9D8F", "portfolioFichier": "clinic-pro",
        "experiences": [
            {"entreprise": "Cabinet de Psychologie Sérénité (activité indépendante)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 1, 1), "fin": None, "enCours": True, "description": "Consultations individuelles et de couple. Accompagnement de la gestion du stress et du burn-out en entreprise.", "poste": "Psychologue Clinicienne Indépendante", "missionClient": {"client": "Ecobank Côte d'Ivoire", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2021, 1, 1), "fin": date(2021, 12, 31), "desc": "Programme de soutien psychologique des collaborateurs (cellule d'écoute interne)."}},
            {"entreprise": "CHU de Cocody (service psychiatrie)", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2015, 9, 1), "fin": date(2018, 12, 31), "enCours": False, "description": "Suivi psychologique de patients hospitalisés. Participation aux staffs pluridisciplinaires.", "poste": "Psychologue Hospitalière", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master en Psychologie Clinique", "ecole": "Université FHB Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2013, 9, 1), "fin": date(2015, 6, 30), "niveau": "Bac+5", "desc": "Spécialité psychopathologie et thérapies brèves."},
        ],
        "competences": [("Thérapie individuelle", 5), ("Gestion du stress", 5), ("Thérapie de couple", 4), ("Accompagnement du deuil", 4), ("Écoute active", 5)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Baoulé", "C1")],
        "interets":    ["Psychologie positive", "Méditation", "Lecture"],
        "projets": [
            {"titre": "Cellule d'écoute psychologique Ecobank", "contexte": "Augmentation du stress professionnel post-pandémie.", "realisation": "Mise en place d'une cellule d'écoute pour 500 collaborateurs, 85% de satisfaction.", "url": "", "debut": date(2021, 1, 1), "fin": date(2021, 12, 31)},
        ],
        "benevolats": [{"titre": "Soutien psychologique gratuit", "organisation": "SOS Détresse Côte d'Ivoire", "debut": date(2017, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/grace-apia-psychologue")],
    },

    # ── 95 ── TECH-DASHBOARD ──────────────────────────────────────────────────
    {
        "prenom": "Christian", "nom": "ABOA", "sexe": "Homme",
        "email": "christian.aboa@demo.test", "telephone": "+225 07 81 92 03 14",
        "naissance": date(1992, 2, 4), "nationalite": "Ivoirienne",
        "adresse": "Cocody Angré Djibi", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Ingénieur Cybersécurité",
        "secteur": "Numérique (Tech)",
        "biographie": "Ingénieur cybersécurité avec 6 ans d'expérience dans la protection des systèmes d'information bancaires. Je traque les vulnérabilités avant qu'elles ne deviennent des incidents.",
        "profilCV": "Ingénieur cybersécurité · 6 ans · Pentest, SOC, réponse à incident, sécurité bancaire, conformité PCI-DSS.",
        "anneePremEmploi": 2018, "mobilite": "International", "contrat": "CDI",
        "slogan": "Anticiper la menace, protéger l'essentiel.",
        "couleur": "#1a1a2e", "portfolioFichier": "tech-dashboard",
        "experiences": [
            {"entreprise": "Société Générale Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 9, 1), "fin": None, "enCours": True, "description": "Pilotage du SOC (Security Operations Center). Réalisation de tests d'intrusion réguliers. Réponse aux incidents de sécurité.", "poste": "Ingénieur Cybersécurité Senior", "missionClient": None},
            {"entreprise": "Orange Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2018, 3, 1), "fin": date(2020, 8, 31), "enCours": False, "description": "Analyste sécurité, surveillance des systèmes et détection d'anomalies.", "poste": "Analyste Sécurité", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master Cybersécurité", "ecole": "ESATIC Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2016, 9, 1), "fin": date(2018, 6, 30), "niveau": "Bac+5", "desc": "Spécialité sécurité des systèmes d'information."},
        ],
        "competences": [("Tests d'intrusion (pentest)", 5), ("SOC / SIEM", 5), ("Réponse à incident", 4), ("Conformité PCI-DSS", 4), ("Sécurité réseau", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "C1")],
        "interets":    ["Bug bounty", "Cybersécurité offensive", "Échecs"],
        "projets": [
            {"titre": "Mise en place du SOC SGCI", "contexte": "Absence de surveillance centralisée de la sécurité IT.", "realisation": "Déploiement d'un SIEM et d'une équipe de surveillance 24/7. Détection d'incidents améliorée de 60%.", "url": "", "debut": date(2021, 1, 1), "fin": date(2021, 9, 30)},
        ],
        "benevolats": [{"titre": "Formateur cybersécurité pour PME", "organisation": "Djelia Tech CI", "debut": date(2020, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/christian-aboa"), ("github", "https://github.com/christianaboa")],
    },

    # ── 96 ── SNAPFOLIO ───────────────────────────────────────────────────────
    {
        "prenom": "Amenan", "nom": "KOUASSI", "sexe": "Femme",
        "email": "amenan.kouassi@demo.test", "telephone": "+225 05 92 03 14 25",
        "naissance": date(1990, 4, 15), "nationalite": "Ivoirienne",
        "adresse": "Grand-Bassam Vitré", "ville": "Grand-Bassam", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Designer Mobilier & Décoration",
        "secteur": "Mode & Artisanat",
        "biographie": "Designer de mobilier avec 7 ans d'expérience, je conçois des pièces uniques inspirées de l'artisanat ivoirien mêlé au design contemporain. Le bois local est ma matière de prédilection.",
        "profilCV": "Designer mobilier · 7 ans · Conception de mobilier, artisanat du bois local, décoration d'intérieur, design contemporain africain.",
        "anneePremEmploi": 2017, "mobilite": "National", "contrat": "Freelance",
        "slogan": "Le design qui raconte nos racines.",
        "couleur": "#C9A227", "portfolioFichier": "snapfolio",
        "experiences": [
            {"entreprise": "Atelier Amenan Design (marque propre)", "pays": "COTE D'IVOIRE", "ville": "Grand-Bassam", "debut": date(2019, 6, 1), "fin": None, "enCours": True, "description": "Conception et fabrication de mobilier haut de gamme en bois local. Collaborations avec des architectes d'intérieur.", "poste": "Designer Créatrice", "missionClient": {"client": "Atelier d'Architecture Koffi & Associés", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2021, 3, 1), "fin": date(2021, 9, 30), "desc": "Conception du mobilier sur-mesure pour un programme résidentiel haut de gamme."}},
            {"entreprise": "Atelier de Menuiserie d'Art de Bassam", "pays": "COTE D'IVOIRE", "ville": "Grand-Bassam", "debut": date(2017, 3, 1), "fin": date(2019, 5, 31), "enCours": False, "description": "Apprentissage et conception de pièces de mobilier traditionnel revisité.", "poste": "Designer Junior", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Diplôme en Design d'Espace et Mobilier", "ecole": "École Supérieure de Mode d'Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2014, 9, 1), "fin": date(2017, 6, 30), "niveau": "BAC +3", "desc": "Spécialité design de mobilier et décoration d'intérieur."},
        ],
        "competences": [("Conception de mobilier", 5), ("Artisanat du bois", 5), ("Design contemporain", 4), ("Décoration d'intérieur", 4), ("Gestion d'atelier", 3)],
        "langues":     [("Français", "C2"), ("Anglais", "B1"), ("N'Zima", "C2")],
        "interets":    ["Artisanat africain", "Architecture d'intérieur", "Voyages"],
        "projets": [
            {"titre": "Collection 'Racines du Bois'", "contexte": "Valoriser les essences de bois locales dans le design contemporain.", "realisation": "Collection de 10 pièces exposée à la Foire Internationale d'Abidjan, plusieurs commandes de particuliers.", "url": "https://instagram.com/amenan.design", "debut": date(2022, 1, 1), "fin": date(2022, 7, 31)},
        ],
        "benevolats": [{"titre": "Formatrice artisanat du bois pour jeunes", "organisation": "Chambre des Métiers de Grand-Bassam", "debut": date(2020, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/amenan-kouassi-design"), ("instagram", "https://instagram.com/amenan.design")],
    },

    # ── 97 ── PROMAN-PRO ──────────────────────────────────────────────────────
    {
        "prenom": "Étienne", "nom": "DJEDJE", "sexe": "Homme",
        "email": "etienne.djedje@demo.test", "telephone": "+225 07 03 14 25 36",
        "naissance": date(1980, 9, 11), "nationalite": "Ivoirienne",
        "adresse": "Plateau, Rue du Commerce", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Notaire",
        "secteur": "Juridique & Compliance",
        "biographie": "Notaire avec 18 ans d'expérience en droit immobilier et successions. J'accompagne particuliers et entreprises dans la sécurisation juridique de leurs actes les plus importants.",
        "profilCV": "Notaire · 18 ans · Actes authentiques, droit immobilier, successions, droit des sociétés.",
        "anneePremEmploi": 2006, "mobilite": "Local", "contrat": "CDI",
        "slogan": "La sécurité juridique, à chaque étape de votre vie.",
        "couleur": "#003366", "portfolioFichier": "proman-pro",
        "experiences": [
            {"entreprise": "Étude Notariale Djedje & Associés", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2014, 1, 1), "fin": None, "enCours": True, "description": "Notaire titulaire de l'étude. Rédaction d'actes authentiques (ventes immobilières, successions, constitutions de sociétés).", "poste": "Notaire Titulaire", "missionClient": None},
            {"entreprise": "Étude Notariale Kouassi", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2006, 9, 1), "fin": date(2013, 12, 31), "enCours": False, "description": "Clerc de notaire puis notaire assistant. Rédaction d'actes et conseil juridique.", "poste": "Notaire Assistant", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Maîtrise en Droit Notarial", "ecole": "Université FHB Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2002, 9, 1), "fin": date(2006, 6, 30), "niveau": "Bac+5", "desc": "Spécialité droit immobilier et droit des successions."},
        ],
        "competences": [("Actes authentiques", 5), ("Droit immobilier", 5), ("Droit des successions", 5), ("Droit des sociétés", 4), ("Conseil juridique", 5)],
        "langues":     [("Français", "C2"), ("Anglais", "B2")],
        "interets":    ["Droit comparé", "Golf", "Lecture juridique"],
        "projets": [
            {"titre": "Sécurisation foncière programme résidentiel", "contexte": "Complexité foncière d'un grand programme immobilier à Abidjan.", "realisation": "Rédaction et sécurisation de plus de 200 actes de vente sans litige.", "url": "", "debut": date(2020, 1, 1), "fin": date(2021, 12, 31)},
        ],
        "benevolats": [{"titre": "Consultations juridiques gratuites", "organisation": "Chambre des Notaires de Côte d'Ivoire", "debut": date(2015, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/etienne-djedje-notaire")],
    },

    # ── 98 ── PROMAN-GLASS ────────────────────────────────────────────────────
    {
        "prenom": "Yvonne", "nom": "BROU", "sexe": "Femme",
        "email": "yvonne.brou@demo.test", "telephone": "+225 05 14 25 36 47",
        "naissance": date(1991, 12, 3), "nationalite": "Ivoirienne",
        "adresse": "Cocody Angré 8e Tranche", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Chargée de Paie",
        "secteur": "Ressources Humaines",
        "biographie": "Chargée de paie avec 7 ans d'expérience en gestion de la paie multi-conventions. Précision et respect des délais sont mes engagements envers chaque collaborateur.",
        "profilCV": "Chargée de paie · 7 ans · Gestion de la paie, déclarations sociales, SIRH, droit du travail ivoirien.",
        "anneePremEmploi": 2017, "mobilite": "National", "contrat": "CDI",
        "slogan": "Une paie juste, versée à temps.",
        "couleur": "#E85D4A", "portfolioFichier": "proman-glass",
        "experiences": [
            {"entreprise": "Groupe NSIA", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2020, 2, 1), "fin": None, "enCours": True, "description": "Gestion de la paie de 800 collaborateurs sur plusieurs filiales. Déclarations CNPS et DGI. Paramétrage du SIRH.", "poste": "Chargée de Paie Senior", "missionClient": None},
            {"entreprise": "CFAO Motors CI", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2017, 6, 1), "fin": date(2020, 1, 31), "enCours": False, "description": "Gestion de la paie de 250 salariés. Suivi des absences et congés.", "poste": "Assistante Paie", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Licence Gestion des Ressources Humaines", "ecole": "ISTC Polytechnique Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2014, 9, 1), "fin": date(2017, 6, 30), "niveau": "BAC +3", "desc": "Spécialité paie et administration du personnel."},
        ],
        "competences": [("Gestion de la paie", 5), ("Déclarations sociales (CNPS)", 5), ("SIRH", 4), ("Droit du travail ivoirien", 4), ("Excel avancé", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "B1"), ("Baoulé", "B2")],
        "interets":    ["Droit social", "Danse", "Lecture"],
        "projets": [
            {"titre": "Migration vers un nouveau SIRH", "contexte": "Ancien système de paie obsolète et source d'erreurs.", "realisation": "Participation au paramétrage et à la migration des données de 800 salariés sans incident de paie.", "url": "", "debut": date(2021, 3, 1), "fin": date(2021, 9, 30)},
        ],
        "benevolats": [{"titre": "Sensibilisation droits sociaux des travailleurs", "organisation": "Inspection du Travail (partenariat associatif)", "debut": date(2019, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/yvonne-brou-paie")],
    },

    # ── 99 ── STYLE ───────────────────────────────────────────────────────────
    {
        "prenom": "Adama", "nom": "SANOGO", "sexe": "Homme",
        "email": "adama.sanogo@demo.test", "telephone": "+225 07 25 36 47 58",
        "naissance": date(1982, 7, 14), "nationalite": "Ivoirienne",
        "adresse": "Bongouanou", "ville": "Bongouanou", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Agro-Entrepreneur / Exploitant Agricole",
        "secteur": "Agriculture & Agro-alimentaire",
        "biographie": "Agro-entrepreneur avec 15 ans d'expérience dans la production et la transformation de cacao et d'anacarde. Je développe une filière durable et rémunératrice pour ma coopérative.",
        "profilCV": "Agro-entrepreneur · 15 ans · Production cacao et anacarde, gestion de coopérative, transformation agricole, commerce équitable.",
        "anneePremEmploi": 2007, "mobilite": "National", "contrat": "CDI",
        "slogan": "Cultiver l'avenir, une récolte à la fois.",
        "couleur": "#009A44", "portfolioFichier": "style",
        "experiences": [
            {"entreprise": "Coopérative Agricole de Bongouanou (fondateur)", "pays": "COTE D'IVOIRE", "ville": "Bongouanou", "debut": date(2012, 1, 1), "fin": None, "enCours": True, "description": "Fondateur et gérant d'une coopérative de 300 producteurs de cacao et anacarde. Certification commerce équitable obtenue.", "poste": "Gérant de Coopérative", "missionClient": None},
            {"entreprise": "Exploitation Familiale Sanogo", "pays": "COTE D'IVOIRE", "ville": "Bongouanou", "debut": date(2007, 1, 1), "fin": date(2011, 12, 31), "enCours": False, "description": "Gestion de l'exploitation agricole familiale (cacao, anacarde, vivriers).", "poste": "Exploitant Agricole", "missionClient": None},
        ],
        "formations": [
            {"diplome": "BTS Agronomie", "ecole": "INPHB Yamoussoukro", "ville": "Yamoussoukro", "pays": "COTE D'IVOIRE", "debut": date(2005, 9, 1), "fin": date(2007, 6, 30), "niveau": "BAC +2", "desc": "Spécialité productions végétales tropicales."},
        ],
        "competences": [("Gestion de coopérative", 5), ("Production cacao/anacarde", 5), ("Commerce équitable", 4), ("Négociation commerciale", 4), ("Agriculture durable", 4)],
        "langues":     [("Français", "C1"), ("Dioula", "C2"), ("Anglais", "A2")],
        "interets":    ["Agriculture durable", "Football", "Vie coopérative"],
        "projets": [
            {"titre": "Certification commerce équitable de la coopérative", "contexte": "Volonté d'obtenir de meilleurs prix pour les producteurs membres.", "realisation": "Obtention de la certification Fairtrade, +22% de revenus pour les 300 producteurs membres.", "url": "", "debut": date(2019, 1, 1), "fin": date(2020, 12, 31)},
        ],
        "benevolats": [{"titre": "Formateur agriculture durable", "organisation": "Chambre d'Agriculture de Côte d'Ivoire", "debut": date(2016, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/adama-sanogo-agro")],
    },

    # ── 100 ── SNAPFOLIO ──────────────────────────────────────────────────────
    {
        "prenom": "Corinne", "nom": "EHUI", "sexe": "Femme",
        "email": "corinne.ehui@demo.test", "telephone": "+225 05 36 47 58 69",
        "naissance": date(1994, 10, 19), "nationalite": "Ivoirienne",
        "adresse": "Grand-Bassam Quartier France", "ville": "Grand-Bassam", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Guide Touristique",
        "secteur": "Hôtellerie & Restauration",
        "biographie": "Guide touristique avec 6 ans d'expérience, spécialisée dans la valorisation du patrimoine historique de Grand-Bassam et la culture ivoirienne. Je fais voyager mes visiteurs dans notre histoire.",
        "profilCV": "Guide touristique · 6 ans · Patrimoine historique, culture ivoirienne, animation de groupes, langues étrangères.",
        "anneePremEmploi": 2018, "mobilite": "National", "contrat": "Freelance",
        "slogan": "Raconter la Côte d'Ivoire, un voyage à la fois.",
        "couleur": "#F77F00", "portfolioFichier": "snapfolio",
        "experiences": [
            {"entreprise": "Office Ivoirien du Tourisme", "pays": "COTE D'IVOIRE", "ville": "Grand-Bassam", "debut": date(2020, 3, 1), "fin": None, "enCours": True, "description": "Guide officielle du quartier historique de Grand-Bassam (patrimoine UNESCO). Animation de visites pour groupes internationaux.", "poste": "Guide Touristique Senior", "missionClient": None},
            {"entreprise": "Agence de Voyage Ivoire Découverte", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2018, 5, 1), "fin": date(2020, 2, 29), "enCours": False, "description": "Accompagnement de circuits touristiques à travers la Côte d'Ivoire.", "poste": "Guide Touristique", "missionClient": None},
        ],
        "formations": [
            {"diplome": "BTS Tourisme", "ecole": "École Hôtelière d'Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2016, 9, 1), "fin": date(2018, 6, 30), "niveau": "BAC +2", "desc": "Spécialité guidage touristique et patrimoine culturel."},
        ],
        "competences": [("Guidage touristique", 5), ("Histoire et patrimoine", 5), ("Animation de groupes", 4), ("Langues étrangères", 4), ("Organisation d'événements", 3)],
        "langues":     [("Français", "C2"), ("Anglais", "C1"), ("Espagnol", "B1"), ("N'Zima", "C2")],
        "interets":    ["Histoire", "Patrimoine UNESCO", "Voyages"],
        "projets": [
            {"titre": "Circuit patrimonial Grand-Bassam UNESCO", "contexte": "Valoriser le site classé au patrimoine mondial de l'UNESCO.", "realisation": "Conception d'un nouveau parcours guidé, +40% de visiteurs satisfaits selon les retours.", "url": "", "debut": date(2021, 1, 1), "fin": date(2021, 6, 30)},
        ],
        "benevolats": [{"titre": "Sensibilisation à la préservation du patrimoine", "organisation": "Association de Sauvegarde de Grand-Bassam", "debut": date(2019, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/corinne-ehui-guide"), ("instagram", "https://instagram.com/corinne.bassam.tour")],
    },

    # ── 101 ── TECH-DASHBOARD ─────────────────────────────────────────────────
    {
        "prenom": "Olivier", "nom": "KACOU", "sexe": "Homme",
        "email": "olivier.kacou@demo.test", "telephone": "+225 07 47 58 69 70",
        "naissance": date(1988, 6, 6), "nationalite": "Ivoirienne",
        "adresse": "Cocody Riviera Golf", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Chef de Projet IT / Scrum Master",
        "secteur": "Numérique (Tech)",
        "biographie": "Chef de projet IT et Scrum Master certifié avec 10 ans d'expérience dans la conduite de projets digitaux. Je fédère les équipes autour d'objectifs clairs et d'une méthodologie agile.",
        "profilCV": "Chef de projet IT · 10 ans · Méthodologie agile (Scrum), gestion de projets digitaux, coordination d'équipes pluridisciplinaires.",
        "anneePremEmploi": 2013, "mobilite": "International", "contrat": "CDI",
        "slogan": "Fédérer les équipes, livrer la valeur.",
        "couleur": "#1a1a2e", "portfolioFichier": "tech-dashboard",
        "experiences": [
            {"entreprise": "MTN Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2019, 1, 1), "fin": None, "enCours": True, "description": "Scrum Master pour 3 équipes produit (25 personnes). Pilotage de la roadmap digitale de l'application MoMo. Coordination avec les parties prenantes métier.", "poste": "Chef de Projet IT / Scrum Master", "missionClient": None},
            {"entreprise": "Orange Côte d'Ivoire", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2013, 6, 1), "fin": date(2018, 12, 31), "enCours": False, "description": "Chef de projet pour des développements internes. Introduction des méthodes agiles dans l'équipe IT.", "poste": "Chef de Projet IT", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master Management de Projets IT", "ecole": "ESATIC Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2011, 9, 1), "fin": date(2013, 6, 30), "niveau": "Bac+5", "desc": "Spécialité gestion de projets informatiques et méthodes agiles."},
        ],
        "competences": [("Scrum / Agile", 5), ("Gestion de projet IT", 5), ("Coordination d'équipes", 5), ("JIRA/Confluence", 4), ("Communication avec les parties prenantes", 4)],
        "langues":     [("Français", "C2"), ("Anglais", "C1")],
        "interets":    ["Méthodes agiles", "Golf", "Voyages"],
        "projets": [
            {"titre": "Transformation agile IT MTN", "contexte": "Méthodes de gestion de projet traditionnelles jugées trop lentes.", "realisation": "Déploiement de Scrum sur 3 équipes, réduction du time-to-market de 35%.", "url": "", "debut": date(2020, 1, 1), "fin": date(2020, 12, 31)},
        ],
        "benevolats": [{"titre": "Formateur méthodes agiles", "organisation": "Orange Digital Center CI", "debut": date(2019, 6, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/olivier-kacou")],
    },

    # ── 102 ── CLINIC-PRO ─────────────────────────────────────────────────────
    {
        "prenom": "Henriette", "nom": "ASSI", "sexe": "Femme",
        "email": "henriette.assi@demo.test", "telephone": "+225 05 58 69 70 81",
        "naissance": date(1979, 3, 29), "nationalite": "Ivoirienne",
        "adresse": "Cocody Danga", "ville": "Abidjan", "pays": "COTE D'IVOIRE",
        "permis": "B", "titre": "Directrice d'Établissement de Santé",
        "secteur": "Santé",
        "biographie": "Directrice d'établissement de santé avec 19 ans d'expérience, dont 8 comme directrice de clinique. Je pilote la stratégie et la qualité des soins d'une équipe de plus de 100 personnes.",
        "profilCV": "Directrice d'établissement de santé · 19 ans · Management d'établissement, stratégie qualité des soins, gestion budgétaire, accréditation.",
        "anneePremEmploi": 2004, "mobilite": "National", "contrat": "CDI",
        "slogan": "Diriger pour mieux soigner.",
        "couleur": "#2A9D8F", "portfolioFichier": "clinic-pro",
        "experiences": [
            {"entreprise": "Polyclinique Internationale Sainte Anne-Marie", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2015, 6, 1), "fin": None, "enCours": True, "description": "Direction générale de l'établissement (120 collaborateurs, 80 lits). Pilotage de la démarche qualité et de l'accréditation. Gestion budgétaire annuelle.", "poste": "Directrice Générale", "missionClient": None},
            {"entreprise": "CHU de Treichville", "pays": "COTE D'IVOIRE", "ville": "Abidjan", "debut": date(2004, 9, 1), "fin": date(2015, 5, 31), "enCours": False, "description": "Infirmière puis cadre de santé, cheffe de service. Gestion des équipes soignantes.", "poste": "Cadre de Santé", "missionClient": None},
        ],
        "formations": [
            {"diplome": "Master en Management des Établissements de Santé", "ecole": "ENA Côte d'Ivoire", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2012, 9, 1), "fin": date(2014, 6, 30), "niveau": "Bac+5", "desc": "Spécialité gestion hospitalière et politique de santé."},
            {"diplome": "Diplôme d'État Infirmier", "ecole": "INFAS Abidjan", "ville": "Abidjan", "pays": "COTE D'IVOIRE", "debut": date(2001, 9, 1), "fin": date(2004, 6, 30), "niveau": "BAC +3", "desc": "Formation en soins infirmiers généraux."},
        ],
        "competences": [("Management d'établissement", 5), ("Stratégie qualité des soins", 5), ("Gestion budgétaire", 4), ("Accréditation hospitalière", 4), ("Leadership d'équipe", 5)],
        "langues":     [("Français", "C2"), ("Anglais", "B2"), ("Baoulé", "C1")],
        "interets":    ["Politique de santé publique", "Golf", "Lecture"],
        "projets": [
            {"titre": "Accréditation qualité de la polyclinique", "contexte": "Volonté de renforcer la crédibilité et la sécurité des soins de l'établissement.", "realisation": "Obtention de l'accréditation qualité en 18 mois, première clinique privée accréditée de la région.", "url": "", "debut": date(2019, 1, 1), "fin": date(2020, 6, 30)},
        ],
        "benevolats": [{"titre": "Conseil en gestion pour cliniques rurales", "organisation": "Ordre National des Médecins de Côte d'Ivoire (partenariat)", "debut": date(2017, 1, 1), "fin": None, "enCours": True}],
        "liens": [("linkedin", "https://www.linkedin.com/in/henriette-assi")],
    },
]


# ═════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _ascii(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _get(model, **kwargs):
    return model.objects.filter(**kwargs).first()


def _get_or_create(model, defaults=None, **kwargs):
    obj, _ = model.objects.get_or_create(defaults=defaults or {}, **kwargs)
    return obj


def _photo_svg(prenom, nom, bg, fg="#FFFFFF"):
    """SVG circulaire avec initiales sur fond coloré (photo profil placeholder)."""
    initiales = (prenom[:1] + nom[:1]).upper()
    svg = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">'
        f'<circle cx="100" cy="100" r="100" fill="{bg}"/>'
        f'<text x="50%" y="50%" font-family="Arial, sans-serif" font-size="80" '
        f'font-weight="800" fill="{fg}" text-anchor="middle" dominant-baseline="central">'
        f'{initiales}</text></svg>'
    )
    return svg.encode("utf-8")


PALETTE = ["#F77F00", "#009A44", "#1a1a2e", "#E85D4A", "#1565C0", "#C9A227", "#2A9D8F", "#003366"]


# ═════════════════════════════════════════════════════════════════════════════
# COMMAND
# ═════════════════════════════════════════════════════════════════════════════

class Command(BaseCommand):
    help = "Seed des candidats de démo avec profil complet (identité, rubriques, 2 CVs, portfolio)"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Supprime les candidats du demo avant de recréer")

    @transaction.atomic
    def handle(self, *args, **options):
        emails = [c["email"] for c in CANDIDATS]

        if options["reset"]:
            qs = Candidat.objects.filter(email__in=emails)
            n = qs.count()
            self.stdout.write(self.style.WARNING(f"--reset : suppression de {n} candidat(s) du demo"))
            qs.delete()

        # Préfetch des FK référentielles
        ref = {
            "sexe_homme": _get(Sexe, sexe="Homme"),
            "sexe_femme": _get(Sexe, sexe="Femme"),
            "permis_b":   _get(TypePermis, nomPermis="B"),
            "permis_abcde": _get(TypePermis, nomPermis="ABCDE"),
        }
        mob_map = {m.libelle: m for m in TypeMobilite.objects.all()}
        ctr_map = {c.libelle: c for c in Contrat.objects.all()}
        pays_map = {_ascii(p.nomPays).upper(): p for p in Pays.objects.all()}
        langue_map = {l.nomLangue: l for l in Langue.objects.all()}
        nivCEFR = {n.nomNiveau: n for n in Niveau.objects.filter(type="langue")}
        nivComp = {n.nbEtoiles: n for n in Niveau.objects.filter(type="competence") if n.nbEtoiles}
        niv_etude_map = {n.nomNiveau: n for n in NiveauEtude.objects.all()}
        reseau_map = {r.slug: r for r in ReseauSocial.objects.all()}
        modeles_cv = list(ModeleCV.objects.filter(actif=True).order_by("ordre")[:6])
        portfolios = {p.fichier: p for p in Portfolio.objects.filter(actif=True)}

        if len(modeles_cv) < 2:
            self.stdout.write(self.style.ERROR("Il faut au moins 2 ModeleCV actifs. Lancer init_modeles_cv d'abord."))
            return
        if not portfolios:
            self.stdout.write(self.style.ERROR("Aucun Portfolio actif. Créer au moins un Portfolio d'abord."))
            return

        for idx, cdata in enumerate(CANDIDATS, start=1):
            cand = self._upsert_candidat(cdata, ref, mob_map, ctr_map, pays_map, reseau_map, portfolios, idx)
            self.stdout.write(self.style.SUCCESS(f"[{idx:2d}/{len(CANDIDATS)}] {cand.prenom} {cand.nom}  ->  {cand.email}"))

            # Rubriques relationnelles
            self._sync_competences(cand, cdata, nivComp)
            self._sync_langues(cand, cdata, langue_map, nivCEFR)
            self._sync_interets(cand, cdata)
            self._sync_formations(cand, cdata, pays_map, niv_etude_map)
            xps = self._sync_experiences(cand, cdata, pays_map)
            self._sync_projets(cand, cdata, xps)
            self._sync_benevolats(cand, cdata)

            # 2 CVs par candidat (lié à 2 modeles différents)
            self._upsert_cv(cand, cdata, modeles_cv[idx % len(modeles_cv)],            ordre=1)
            self._upsert_cv(cand, cdata, modeles_cv[(idx + 1) % len(modeles_cv)],      ordre=2)

        self.stdout.write("")
        total = Candidat.objects.filter(email__in=emails).count()
        self.stdout.write(self.style.SUCCESS(
            f"Terminé : {total} candidat(s). Mot de passe : {PASSWORD}"
        ))
        for c in CANDIDATS[:5]:
            self.stdout.write(f"  Exemple : {c['email']}")
        self.stdout.write(f"  …et {total - 5} autres.")

    # ── Helpers internes ─────────────────────────────────────────────────────

    def _upsert_candidat(self, d, ref, mob_map, ctr_map, pays_map, reseau_map, portfolios, idx):
        sexe_ref = ref["sexe_femme"] if d["sexe"] == "Femme" else ref["sexe_homme"]

        cand, _ = Candidat.objects.get_or_create(
            email=d["email"], defaults={"prenom": d["prenom"], "nom": d["nom"]},
        )
        cand.prenom = d["prenom"]
        cand.nom    = d["nom"]
        cand.dateNaissance = d["naissance"]
        cand.telephone = d["telephone"]
        cand.adresse = d["adresse"]
        cand.sexe = sexe_ref
        cand.emailVerifie = True

        cand.titreProfessionnel = d["titre"]
        cand.biographie         = d["biographie"]
        cand.profilCV           = d["profilCV"]
        cand.datePremierEmploi  = d["anneePremEmploi"]
        cand.secteurActivite    = d["secteur"]
        cand.typeMobilite       = mob_map.get(d["mobilite"])
        cand.typeContratRecherche = ctr_map.get(d["contrat"])

        cand.portfolioPublic    = True
        cand.sloganPortfolio    = d["slogan"]
        cand.couleurPortfolio   = d["couleur"]
        cand.portfolioModele    = portfolios.get(d["portfolioFichier"]) or list(portfolios.values())[0]
        cand.paramsPortfolio    = {"showProjets": True, "showAbout": True, "showExperiences": True, "showFormations": True, "showCompetences": True, "showLangues": True, "showBenevs": True, "showInterets": True, "showContact": True}

        cand.rubriques = {}   # snapshot vide → reconstruit depuis le relationnel
        cand.set_password(PASSWORD)
        cand.save()

        # Permis
        if ref["permis_b"]:
            cand.typePermis.add(ref["permis_b"])
        if d["permis"] == "ABCDE" and ref["permis_abcde"]:
            cand.typePermis.add(ref["permis_abcde"])

        # Photo profil placeholder (SVG)
        if not cand.photoProfil:
            bg = PALETTE[idx % len(PALETTE)]
            svg_bytes = _photo_svg(d["prenom"], d["nom"], bg)
            cand.photoProfil.save(f"avatar-{cand.id}.svg", ContentFile(svg_bytes), save=True)

        # Information personnelle (legacy OneToOne)
        info, _ = InformationPersonnelle.objects.get_or_create(
            email=d["email"],
            defaults={"prenom": d["prenom"], "nom": d["nom"]},
        )
        info.prenom = d["prenom"]
        info.nom    = d["nom"]
        info.dateNaissance = d["naissance"]
        info.sexe        = "FEMME" if d["sexe"] == "Femme" else "HOMME"
        info.nationalite = d["nationalite"]
        info.telephone   = d["telephone"]
        info.adresse     = d["adresse"]
        info.pays        = d["pays"]
        info.ville       = d["ville"]
        info.permis      = d["permis"]
        if cand.photoProfil and not info.photoProfil:
            info.photoProfil = cand.photoProfil
        info.save()

        cand.informationPersonnelle = info
        cand.save(update_fields=["informationPersonnelle"])

        # Liens sociaux
        cand.liensSociaux.all().delete()
        for ordre, (slug, url) in enumerate(d.get("liens", [])):
            reseau = reseau_map.get(slug)
            if reseau:
                LienCandidat.objects.create(candidat=cand, reseau=reseau, url=url, ordre=ordre)

        return cand

    def _sync_competences(self, cand, d, nivComp):
        cand.competences.all().delete()
        for nom, etoiles in d["competences"]:
            niveau = nivComp.get(etoiles)
            type_comp, _ = TypeCompetence.objects.get_or_create(nomCompetence=nom, defaults={"domaine": d["secteur"]})
            Competence.objects.create(
                candidat=cand, typeCompetence=type_comp, niveau=niveau,
                nomLibre=nom, valeurEtoiles=etoiles, estVisiblePortfolio=True,
            )

    def _sync_langues(self, cand, d, langue_map, nivCEFR):
        cand.languesParlees.all().delete()
        for nom, niveau in d["langues"]:
            langue = langue_map.get(nom) or Langue.objects.create(nomLangue=nom)
            niv = nivCEFR.get(niveau)
            CandidatLangue.objects.create(
                candidat=cand, langue=langue, niveau=niv,
                nomLibre=nom, niveauCode=niveau, estVisiblePortfolio=True,
            )

    def _sync_interets(self, cand, d):
        cand.centresInteret.all().delete()
        for nom in d["interets"]:
            type_ci, _ = TypeCentreInteret.objects.get_or_create(nomCentreInteret=nom)
            CentreInteret.objects.create(
                candidat=cand, typeCentreInteret=type_ci, libelleLibre=nom,
                estVisiblePortfolio=True,
            )

    def _sync_formations(self, cand, d, pays_map, niv_etude_map):
        cand.formations.all().delete()
        for f in d["formations"]:
            pays = pays_map.get(_ascii(f["pays"]).upper())
            niveau_etude = niv_etude_map.get(f.get("niveau", ""))
            inst, _ = Institution.objects.get_or_create(nomInstitution=f["ecole"])
            Formation.objects.create(
                candidat=cand,
                institution=inst,
                niveauEtude=niveau_etude,
                pays=pays,
                typeSortie="diplome",
                diplomeLibre=f["diplome"],
                domaineLibre=d["secteur"],
                ecoleLibre=f["ecole"],
                paysLibre=f["pays"],
                ville=f.get("ville", ""),
                dateDebut=f["debut"],
                dateFin=f["fin"],
                enCours=False,
                description=f.get("desc", ""),
                estVisiblePortfolio=True,
            )

    def _sync_experiences(self, cand, d, pays_map):
        cand.experiencesProfessionnelles.all().delete()
        xps = []
        for e in d["experiences"]:
            pays = pays_map.get(_ascii(e["pays"]).upper())
            ent_ref, _ = RaisonSociale.objects.get_or_create(
                nomEntreprise=e["entreprise"],
                defaults={"secteur": d["secteur"]},
            )
            xp = ExperienceProfessionnelle.objects.create(
                candidat=cand,
                entreprise=ent_ref,
                pays=pays,
                entrepriseLibre=e["entreprise"],
                paysLibre=e["pays"],
                ville=e.get("ville", ""),
                dateDebut=e["debut"],
                dateFin=e["fin"],
                enCours=e["enCours"],
                description=e.get("description", ""),
                estVisiblePortfolio=True,
            )
            # Poste occupé
            if e.get("poste"):
                PosteOccupe.objects.create(
                    experience=xp, titreLibre=e["poste"],
                    dateDebut=e["debut"], dateFin=e["fin"], enCours=e["enCours"],
                    ordre=0,
                )
            # Mission client (optionnelle)
            mc = e.get("missionClient")
            if mc:
                mc_pays = pays_map.get(_ascii(mc["pays"]).upper())
                client_ref, _ = RaisonSociale.objects.get_or_create(
                    nomEntreprise=mc["client"], defaults={"secteur": d["secteur"]},
                )
                MissionClient.objects.create(
                    experience=xp,
                    client=client_ref,
                    pays=mc_pays,
                    clientLibre=mc["client"],
                    paysLibre=mc["pays"],
                    ville=mc.get("ville", ""),
                    dateDebut=mc["debut"],
                    dateFin=mc["fin"],
                    enCours=False,
                    description=mc.get("desc", ""),
                )
            xps.append(xp)
        return xps

    def _sync_projets(self, cand, d, xps):
        cand.projets.all().delete()
        for i, p in enumerate(d["projets"]):
            xp = xps[i % len(xps)] if xps else None
            Projet.objects.create(
                candidat=cand,
                experienceProfessionnelle=xp,
                titre=p["titre"],
                contexte=p.get("contexte", ""),
                realisation=p.get("realisation", ""),
                urlDemo=p.get("url", ""),
                dateDebut=p.get("debut"),
                dateFin=p.get("fin"),
                tailleEquipe=random.choice([None, 3, 5, 8]),
                images=[],
                videos=[],
                estVisiblePortfolio=True,
            )

    def _sync_benevolats(self, cand, d):
        cand.benevolats.all().delete()
        for b in d["benevolats"]:
            Benevolat.objects.create(
                candidat=cand,
                titre=b["titre"],
                organisation=b["organisation"],
                dateDebut=b["debut"],
                dateFin=b.get("fin"),
                enCours=bool(b.get("enCours")),
                estVisiblePortfolio=True,
            )

    def _upsert_cv(self, cand, d, modele, ordre):
        titre = f"CV {d['titre']} — v{ordre}"
        cv, created = CV.objects.get_or_create(
            candidat=cand, titre=titre,
            defaults={"modele": modele, "profil": d["profilCV"]},
        )
        cv.modele = modele
        cv.profil = d["profilCV"]
        cv.archive = False

        # Contenu : crée si absent, lie toutes les rubriques
        contenu = cv.contenu or CVContenu.objects.create(
            informationPersonnelle=cand.informationPersonnelle,
        )
        contenu.informationPersonnelle = cand.informationPersonnelle
        contenu.showProjets = True
        contenu.showBenev   = True
        contenu.showRef     = True
        contenu.elementsMasques = {}
        contenu.donneesSnapshot = {}
        contenu.save()

        contenu.formations.set(cand.formations.all())
        contenu.experiences.set(cand.experiencesProfessionnelles.all())
        contenu.competences.set(cand.competences.all())
        contenu.langues.set(cand.languesParlees.all())
        contenu.interets.set(cand.centresInteret.all())
        contenu.projets.set(cand.projets.all())
        contenu.benevolats.set(cand.benevolats.all())

        cv.contenu = contenu
        cv.save()
        return cv
