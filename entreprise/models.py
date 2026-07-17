import random
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.contrib.auth.hashers import make_password, check_password as django_check_password
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from recrutement.storages import get_public_storage, get_kyc_storage

from referentiel.models import (
    Utilisateur,
    SecteurActivite as SecteurActiviteRef,
    RaisonSociale,
    TypeRaisonSociale,
    StatutCompte as StatutCompteRef,
    Role as RoleRef,
    # Référentiels OffreEmploi (alias pour éviter les collisions avec les
    # TextChoices locales `ModeTravail` / `NiveauEtude`)
    ModeTravail      as ModeTravailRef,
    Contrat          as ContratRef,
    AnneesExperience as AnneesExperienceRef,
    Devise           as DeviseRef,
    NiveauEtude      as NiveauEtudeRef,
    Poste            as PosteRef,
    Pays             as PaysRef,
    Ville            as VilleRef,
    Langue           as LangueRef,
    TypeCompetence   as TypeCompetenceRef,
    Diplome          as DiplomeRef,
)


# ── Enums ──────────────────────────────────────────────────────────────────────

class StatutVerification(models.TextChoices):
    EN_ATTENTE = 'EN_ATTENTE', _('En attente')
    VERIFIE    = 'VERIFIE',    _('Vérifié')
    REJETE     = 'REJETE',     _('Rejeté')


class StatutCompte(models.TextChoices):
    ACTIF     = 'ACTIF',     _('Actif')
    SUSPENDU  = 'SUSPENDU',  _('Suspendu')
    DESACTIVE = 'DESACTIVE', _('Désactivé')


class PlanAbonnement(models.TextChoices):
    GRATUIT    = 'GRATUIT',    _('Gratuit')
    STARTER    = 'STARTER',    'Starter'
    PRO        = 'PRO',        'Pro'
    ENTERPRISE = 'ENTERPRISE', 'Enterprise'


class RoleMembre(models.TextChoices):
    ADMIN   = 'ADMIN',   _('Administrateur')
    RH      = 'RH',      _('Responsable RH')
    MANAGER = 'MANAGER', _('Manager')
    LECTEUR = 'LECTEUR', _('Lecteur')


# ── Constantes de choix ───────────────────────────────────────────────────────

SECTEURS = [
    ('TECH',      _('Technologie & Informatique')),
    ('FINANCE',   _('Finance & Banque')),
    ('SANTE',     _('Santé & Pharmaceutique')),
    ('EDUCATION', _('Éducation & Formation')),
    ('COMMERCE',  _('Commerce & Distribution')),
    ('INDUSTRIE', _('Industrie & Production')),
    ('BTP',       _('BTP & Immobilier')),
    ('TELECOM',   _('Télécommunications')),
    ('AGRI',      _('Agriculture & Agro-alimentaire')),
    ('TRANSPORT', _('Transport & Logistique')),
    ('MEDIA',     _('Médias & Communication')),
    ('ENERGIE',   _('Énergie & Environnement')),
    ('TOURISME',  _('Tourisme & Hôtellerie')),
    ('ONG',       _('ONG & Secteur public')),
    ('AUTRE',     _('Autre')),
]

TAILLES = [
    ('1-10',      _('1 – 10 employés (TPE)')),
    ('11-50',     _('11 – 50 employés (Petite)')),
    ('51-200',    _('51 – 200 employés (Moyenne)')),
    ('201-500',   _('201 – 500 employés (Grande)')),
    ('501-1000',  _('501 – 1 000 employés')),
    ('1001-5000', _('1 001 – 5 000 employés')),
    ('5000+',     _('+ 5 000 employés (Multinationale)')),
]

# Droits par défaut selon le rôle
DROITS_DEFAUT = {
    'ADMIN': {
        'offres':        ['create', 'read', 'update', 'delete'],
        'candidatures':  ['read', 'update', 'delete'],
        'membres':       ['create', 'read', 'update', 'delete'],
        'parametres':    ['read', 'update'],
        'statistiques':  ['read'],
        'entretiens':    ['create', 'read', 'update', 'delete'],
    },
    'RH': {
        'offres':        ['create', 'read', 'update'],
        'candidatures':  ['read', 'update'],
        'membres':       ['read'],
        'parametres':    ['read'],
        'statistiques':  ['read'],
        'entretiens':    ['create', 'read', 'update'],
    },
    'MANAGER': {
        'offres':        ['read'],
        'candidatures':  ['read', 'update'],
        'membres':       ['read'],
        'parametres':    [],
        'statistiques':  ['read'],
        'entretiens':    ['create', 'read', 'update'],
    },
    'LECTEUR': {
        'offres':        ['read'],
        'candidatures':  ['read'],
        'membres':       ['read'],
        'parametres':    [],
        'statistiques':  ['read'],
        'entretiens':    ['read'],
    },
}

COULEURS_ROLE = {
    'ADMIN':   {'bg': '#FEF3C7', 'text': '#92400E', 'dot': '#F59E0B'},
    'RH':      {'bg': '#DCFCE7', 'text': '#166534', 'dot': '#22C55E'},
    'MANAGER': {'bg': '#DBEAFE', 'text': '#1E40AF', 'dot': '#3B82F6'},
    'LECTEUR': {'bg': '#F3F4F6', 'text': '#374151', 'dot': '#9CA3AF'},
}


# ── Modèle principal ──────────────────────────────────────────────────────────

class DroitAcces(models.IntegerChoices):
    """Niveau d'accès pour le compte de l'entreprise (cf. cahier des charges)."""
    ADMIN     = 1, _('Administrateur')
    RECRUTEUR = 2, _('Recruteur')


class Entreprise(models.Model):
    # ── Identité ──────────────────────────────────────────────────────────────
    raisonSocial        = models.CharField('Raison sociale', max_length=200)
    registreCommerce    = models.CharField('Registre du commerce', max_length=100, blank=True)
    idu                 = models.CharField('Identifiant unique (IDU)', max_length=100, blank=True)
    identifiantFiscal   = models.CharField("Identifiant fiscal", max_length=255, blank=True)
    contact             = models.CharField('Contact principal', max_length=50, blank=True)
    droiteAcces         = models.IntegerField(
        "Droits d'accès", choices=DroitAcces.choices,
        default=DroitAcces.ADMIN,
    )

    # ── Authentification ──────────────────────────────────────────────────────
    emailProfessionnel  = models.EmailField('Email professionnel', unique=True)
    motPasse            = models.CharField('Mot de passe', max_length=255)

    # ── Description & activité ────────────────────────────────────────────────
    description         = models.TextField('Description', blank=True)
    secteurActivite     = models.CharField("Secteur d'activité (legacy)", max_length=20,
                                           choices=SECTEURS, blank=True)
    tailleEntreprise    = models.CharField("Taille de l'entreprise", max_length=20,
                                           choices=TAILLES, blank=True)

    # ── Référentiels (FK — schéma cible) ─────────────────────────────────────
    secteurActiviteRef     = models.ForeignKey(
        SecteurActiviteRef, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='entreprises',
        verbose_name="Secteur d'activité",
    )
    raisonSocialeRef       = models.ForeignKey(
        RaisonSociale, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='entreprises_liees',
        verbose_name='Raison sociale',
    )
    typeRaisonSocialeRef   = models.ForeignKey(
        TypeRaisonSociale, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='entreprises_directes',
        verbose_name='Forme juridique',
    )
    statutCompteRef        = models.ForeignKey(
        StatutCompteRef, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='entreprises',
        verbose_name='Statut du compte (référentiel)',
    )

    # ── Contact & Web ─────────────────────────────────────────────────────────
    siteWeb             = models.URLField('Site web', blank=True)
    telephone           = models.CharField('Téléphone', max_length=30, blank=True)
    emailContact        = models.EmailField('Email de contact', blank=True)

    # ── Média ─────────────────────────────────────────────────────────────────
    logoEntreprise      = models.ImageField('Logo', upload_to='entreprise/logos/',
                                            storage=get_public_storage, blank=True, null=True)

    # ── Localisation ─────────────────────────────────────────────────────────
    adresse             = models.CharField('Adresse', max_length=300, blank=True)
    ville               = models.CharField('Ville', max_length=100, blank=True)
    pays                = models.CharField('Pays', max_length=100, default="Côte d'Ivoire")
    codePostal          = models.CharField('Code postal', max_length=20, blank=True)

    # ── Méta-données ──────────────────────────────────────────────────────────
    dateCreationCompte  = models.DateTimeField('Date de création', auto_now_add=True)
    derniereConnexion   = models.DateTimeField('Dernière connexion', null=True, blank=True)

    # ── Statuts ───────────────────────────────────────────────────────────────
    statutVerification  = models.CharField(
        'Statut de vérification', max_length=20,
        choices=StatutVerification.choices,
        default=StatutVerification.EN_ATTENTE,
    )
    statutCompte        = models.CharField(
        'Statut du compte', max_length=20,
        choices=StatutCompte.choices,
        default=StatutCompte.ACTIF,
    )
    emailVerifie        = models.BooleanField('Email vérifié', default=False)

    # ── Statistiques ──────────────────────────────────────────────────────────
    nombreMembre        = models.IntegerField('Nombre de membres', default=0)
    nombreOffresActives = models.IntegerField('Offres actives', default=0)
    scorePertinence     = models.DecimalField('Score de pertinence',
                                              max_digits=5, decimal_places=2, default=0)

    # ── Abonnement ────────────────────────────────────────────────────────────
    planAbonnement      = models.CharField(
        "Plan d'abonnement", max_length=20,
        choices=PlanAbonnement.choices,
        default=PlanAbonnement.GRATUIT,
    )

    # ── Confidentialité — notifications ATS (compte admin) ────────────────────
    recevoirNotifsATS       = models.BooleanField(
        'Recevoir les notifications de profils ATS',
        default=True,
        help_text="Si désactivé, ne pas recevoir d'alerte quand un profil "
                  "candidat correspond à une offre publiée par le compte admin.",
    )
    recevoirNotifsATSEmail  = models.BooleanField(
        'Recevoir les notifications ATS par email',
        default=False,
    )

    class Meta:
        verbose_name        = 'Entreprise'
        verbose_name_plural = 'Entreprises'
        ordering            = ['-dateCreationCompte']

    def __str__(self):
        return self.raisonSocial

    # ── Authentification ──────────────────────────────────────────────────────

    def set_password(self, raw_password):
        self.motPasse = make_password(raw_password)

    def check_password(self, raw_password):
        return django_check_password(raw_password, self.motPasse)

    # ── Méthodes métier ───────────────────────────────────────────────────────

    def changerMotDePasse(self, ancien, nouveau):
        if self.check_password(ancien):
            self.set_password(nouveau)
            self.save()
            return True
        return False

    def calculerScorePertinence(self):
        """Calcule le score de complétude du profil sur 100."""
        score = 0
        if self.raisonSocial:       score += 10
        if self.description:        score += 20
        if self.logoEntreprise:     score += 15
        if self.siteWeb:            score += 10
        if self.secteurActivite:    score += 10
        if self.tailleEntreprise:   score += 5
        if self.telephone:          score += 5
        if self.adresse:            score += 5
        if self.emailVerifie:       score += 20
        self.scorePertinence = score
        self.save(update_fields=['scorePertinence'])
        return self.scorePertinence


# ── Recruteur (membre de l'équipe) ────────────────────────────────────────────

class Recruteur(Utilisateur):
    """Profil recruteur — hérite de Utilisateur (multi-table inheritance).

    L'authentification (email, password, type_compte) est gérée par
    Utilisateur (AUTH_USER_MODEL). Les champs ci-dessous sont propres
    au profil recruteur.
    """

    # ── Champs d'identité propres au recruteur ───────────────────────────
    nom               = models.CharField('Nom',           max_length=255, blank=True, default='')
    prenom            = models.CharField('Prénom',        max_length=255, blank=True, default='')
    dateNaissance     = models.DateField('Date de naissance', null=True, blank=True)
    photoProfil       = models.ImageField('Photo de profil',
                                          upload_to='users/photos/',
                                          storage=get_public_storage,
                                          blank=True, null=True)
    telephone         = models.CharField('Téléphone',     max_length=20,  blank=True, default='')
    adresse           = models.CharField('Adresse',       max_length=255, blank=True, default='')
    emailVerifie      = models.BooleanField('Email vérifié', default=False)
    sexe              = models.ForeignKey(
        'referentiel.Sexe', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='Sexe',
    )

    entreprise          = models.ForeignKey(
        Entreprise, on_delete=models.CASCADE,
        related_name='recruteurs', verbose_name='Entreprise',
    )

    # ── Champs legacy conservés pendant la transition ────────────────────────
    nomComplet          = models.CharField('Nom complet (legacy)', max_length=200, blank=True, default='')
    emailProfessionnel  = models.EmailField('Email professionnel (legacy)', unique=True, null=True, blank=True)
    dateEmbauche        = models.DateField("Date d'embauche", null=True, blank=True)

    # ── Rôle (référentiel + ancienne enum conservée pour compat) ─────────────
    role                = models.ForeignKey(
        RoleRef, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='recruteurs',
        verbose_name='Rôle (référentiel)',
    )
    roleMembre          = models.CharField(
        'Rôle (legacy)', max_length=20,
        choices=RoleMembre.choices,
        default=RoleMembre.RH,
    )
    droitsAcces         = models.JSONField("Droits d'accès", default=dict)

    # ── Statuts ───────────────────────────────────────────────────────────────
    estActif            = models.BooleanField('Actif', default=True)
    statutCompte        = models.CharField(
        'Statut du compte', max_length=20,
        choices=StatutCompte.choices,
        default=StatutCompte.ACTIF,
    )
    emailVerifie        = models.BooleanField('Email vérifié', default=False)

    # ── Préférences & méta ────────────────────────────────────────────────────
    preferences         = models.JSONField('Préférences', default=dict)

    # Confidentialité — notifications ATS
    recevoirNotifsATS   = models.BooleanField(
        'Recevoir les notifications de profils ATS',
        default=True,
        help_text="Si désactivé, ne pas recevoir d'alerte quand un profil "
                  "candidat correspond à une offre publiée.",
    )
    recevoirNotifsATSEmail = models.BooleanField(
        'Recevoir les notifications ATS par email',
        default=False,
        help_text="Si activé, recevoir aussi un email pour chaque alerte ATS.",
    )

    derniereConnexion   = models.DateTimeField('Dernière connexion', null=True, blank=True)
    dateCreation        = models.DateTimeField('Date de création', auto_now_add=True)

    class Meta:
        verbose_name        = 'Recruteur'
        verbose_name_plural = 'Recruteurs'
        ordering            = ['nomComplet']

    def __str__(self):
        nom_aff = (f"{self.prenom} {self.nom}").strip() or self.nomComplet or self.email or 'Recruteur'
        return f"{nom_aff} ({self.entreprise})"

    def verifier_mot_de_passe(self, raw_password):
        return self.check_password(raw_password)

    def changerMotDePasse(self, ancien, nouveau):
        if self.check_password(ancien):
            self.set_password(nouveau)
            self.save()
            return True
        return False

    # ── Droits ────────────────────────────────────────────────────────────────

    def get_droits_par_role(self):
        return DROITS_DEFAUT.get(self.roleMembre, {})

    def initialiserDroits(self):
        self.droitsAcces = self.get_droits_par_role()

    def verifierDroit(self, ressource, action):
        droits = self.droitsAcces or self.get_droits_par_role()
        return action in droits.get(ressource, [])

    def get_couleur_role(self):
        return COULEURS_ROLE.get(self.roleMembre, COULEURS_ROLE['LECTEUR'])

    @property
    def est_lecteur(self):
        return self.roleMembre == RoleMembre.LECTEUR


# ── Paramètres de l'entreprise ────────────────────────────────────────────────

class ParametreEntreprise(models.Model):
    entreprise              = models.OneToOneField(
        Entreprise, on_delete=models.CASCADE,
        related_name='parametres', verbose_name='Entreprise',
    )
    parametresGeneraux      = models.JSONField('Paramètres généraux',      default=dict)
    parametresRecrutement   = models.JSONField('Paramètres recrutement',   default=dict)
    parametresNotifications = models.JSONField('Paramètres notifications', default=dict)
    parametresSecurite      = models.JSONField('Paramètres sécurité',      default=dict)
    parametresBranding      = models.JSONField('Paramètres branding',      default=dict)
    modelesCommunication    = models.JSONField('Modèles communication',    default=dict)
    integrationsActives     = models.JSONField('Intégrations actives',     default=dict)
    dateModification        = models.DateTimeField('Modifié le', auto_now=True)
    modifiePar              = models.ForeignKey(
        Recruteur, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='parametres_modifies', verbose_name='Modifié par',
    )

    class Meta:
        verbose_name        = 'Paramètres entreprise'
        verbose_name_plural = 'Paramètres entreprises'

    def __str__(self):
        return f"Paramètres — {self.entreprise}"

    # ── Méthodes ──────────────────────────────────────────────────────────────

    @classmethod
    def get_or_create_defaut(cls, entreprise):
        obj, _ = cls.objects.get_or_create(
            entreprise=entreprise,
            defaults={
                'parametresGeneraux': {
                    'langue': 'fr', 'fuseauHoraire': 'Africa/Abidjan', 'formatDate': 'DD/MM/YYYY',
                },
                'parametresRecrutement': {
                    'autoPublierOffres': False, 'delaiExpirationOffre': 30,
                    'nombreCandidaturesMax': 0, 'testRequis': False,
                },
                'parametresNotifications': {
                    'emailNouvellesCandidatures': True, 'emailEntretiens': True,
                    'emailRapportHebdo': False,
                },
                'parametresSecurite': {
                    'authDoubleFact': False, 'dureeSession': 480, 'ipWhitelist': [],
                },
                'parametresBranding': {
                    'couleurPrimaire': '#009A44', 'couleurSecondaire': '#F77F00',
                },
                'modelesCommunication': {},
                'integrationsActives':  {},
            }
        )
        return obj

    def modifier(self, params, recruteur=None):
        for key, value in params.items():
            if hasattr(self, key):
                setattr(self, key, value)
        if recruteur:
            self.modifiePar = recruteur
        self.save()

    def restaurerDefaut(self):
        self.parametresGeneraux      = {'langue': 'fr', 'fuseauHoraire': 'Africa/Abidjan', 'formatDate': 'DD/MM/YYYY'}
        self.parametresRecrutement   = {'autoPublierOffres': False, 'delaiExpirationOffre': 30}
        self.parametresNotifications = {'emailNouvellesCandidatures': True, 'emailEntretiens': True}
        self.parametresSecurite      = {'authDoubleFact': False, 'dureeSession': 480}
        self.parametresBranding      = {'couleurPrimaire': '#009A44', 'couleurSecondaire': '#F77F00'}
        self.modelesCommunication    = {}
        self.integrationsActives     = {}
        self.save()

    def exporter(self):
        return {
            'parametresGeneraux':      self.parametresGeneraux,
            'parametresRecrutement':   self.parametresRecrutement,
            'parametresNotifications': self.parametresNotifications,
            'parametresSecurite':      self.parametresSecurite,
            'parametresBranding':      self.parametresBranding,
            'modelesCommunication':    self.modelesCommunication,
            'integrationsActives':     self.integrationsActives,
        }

    def importer(self, config):
        champs = [
            'parametresGeneraux', 'parametresRecrutement', 'parametresNotifications',
            'parametresSecurite', 'parametresBranding', 'modelesCommunication', 'integrationsActives',
        ]
        for champ in champs:
            if champ in config:
                setattr(self, champ, config[champ])
        self.save()


# ── Offre d'emploi ────────────────────────────────────────────────────────────

class TypeContrat(models.TextChoices):
    CDI        = 'CDI',        'CDI'
    CDD        = 'CDD',        'CDD'
    FREELANCE  = 'FREELANCE',  _('Freelance / Mission')
    STAGE      = 'STAGE',      _('Stage')
    ALTERNANCE = 'ALTERNANCE', _('Alternance')


class ModeTravail(models.TextChoices):
    PRESENTIEL = 'PRESENTIEL', _('Présentiel')
    REMOTE     = 'REMOTE',     _('Télétravail')
    HYBRIDE    = 'HYBRIDE',    _('Hybride')


class ExperienceRequise(models.TextChoices):
    JUNIOR   = 'JUNIOR',   _('Junior (0 – 2 ans)')
    CONFIRME = 'CONFIRME', _('Confirmé (2 – 5 ans)')
    SENIOR   = 'SENIOR',   _('Senior (5 – 10 ans)')
    EXPERT   = 'EXPERT',   _('Expert (10+ ans)')


class NiveauEtude(models.TextChoices):
    BAC        = 'BAC',        _('Bac')
    BAC_PLUS_2 = 'BAC_PLUS_2', _('Bac+2 (BTS, DUT)')
    BAC_PLUS_3 = 'BAC_PLUS_3', _('Bac+3 (Licence)')
    BAC_PLUS_5 = 'BAC_PLUS_5', _('Bac+5 (Master, Ingénieur)')
    DOCTORAT   = 'DOCTORAT',   _('Doctorat')


class StatutOffre(models.TextChoices):
    BROUILLON = 'BROUILLON', _('Brouillon')
    PUBLIEE   = 'PUBLIEE',   _('Publiée')
    EXPIREE   = 'EXPIREE',   _('Expirée')
    POURVUE   = 'POURVUE',   _('Pourvue')
    FERMEE    = 'FERMEE',    _('Fermée')


# Couleurs + icônes pour l'affichage
STYLES_CONTRAT = {
    'CDI':        {'bg': '#DCFCE7', 'text': '#166534', 'icon': '♾️'},
    'CDD':        {'bg': '#FEF3C7', 'text': '#92400E', 'icon': '📅'},
    'FREELANCE':  {'bg': '#EDE9FE', 'text': '#5B21B6', 'icon': '💼'},
    'STAGE':      {'bg': '#DBEAFE', 'text': '#1E40AF', 'icon': '🎓'},
    'ALTERNANCE': {'bg': '#FCE7F3', 'text': '#9D174D', 'icon': '🔄'},
}

STYLES_STATUT = {
    'BROUILLON': {'bg': '#F3F4F6', 'text': '#374151', 'dot': '#9CA3AF'},
    'PUBLIEE':   {'bg': '#DCFCE7', 'text': '#166534', 'dot': '#22C55E'},
    'EXPIREE':   {'bg': '#FEF3C7', 'text': '#92400E', 'dot': '#F59E0B'},
    'POURVUE':   {'bg': '#EDE9FE', 'text': '#5B21B6', 'dot': '#8B5CF6'},
    'FERMEE':    {'bg': '#FEE2E2', 'text': '#991B1B', 'dot': '#EF4444'},
}

DEVISES = ['FCFA', 'EUR', 'USD', 'GBP', 'XOF', 'MAD', 'GNF', 'XAF']


class OffreEmploi(models.Model):
    entreprise          = models.ForeignKey(
        Entreprise, on_delete=models.CASCADE,
        related_name='offres', verbose_name='Entreprise',
    )
    creePar             = models.ForeignKey(
        Recruteur, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='offres_creees', verbose_name='Créé par',
    )

    # ── Identité ──────────────────────────────────────────────────────────────
    titre               = models.CharField('Titre du poste', max_length=200)
    reference           = models.CharField('Référence', max_length=20, blank=True, unique=True)

    # ── Contrat & mode ────────────────────────────────────────────────────────
    typeContrat         = models.CharField('Type de contrat', max_length=20, choices=TypeContrat.choices)
    modeTravail         = models.CharField(
        'Mode de travail', max_length=20,
        choices=ModeTravail.choices, default=ModeTravail.PRESENTIEL,
    )

    # ── Localisation ──────────────────────────────────────────────────────────
    localisation        = models.CharField('Adresse / Quartier', max_length=300, blank=True)
    ville               = models.CharField('Ville', max_length=100, blank=True)
    pays                = models.CharField('Pays', max_length=100, default="Côte d'Ivoire")

    # ── Description ───────────────────────────────────────────────────────────
    missions            = models.TextField('Missions & responsabilités', blank=True)
    profilRecherche     = models.TextField('Profil recherché', blank=True)
    competencesRequises = models.JSONField('Compétences requises', default=list)

    # ── Exigences ─────────────────────────────────────────────────────────────
    experienceRequise   = models.CharField(
        'Expérience requise', max_length=20, choices=ExperienceRequise.choices, blank=True,
    )
    niveauEtudeRequis   = models.CharField(
        "Niveau d'études requis", max_length=100, blank=True,
    )

    # ── Rémunération ──────────────────────────────────────────────────────────
    salaireMin          = models.DecimalField('Salaire min', max_digits=10, decimal_places=2, null=True, blank=True)
    salaireMax          = models.DecimalField('Salaire max', max_digits=10, decimal_places=2, null=True, blank=True)
    devise              = models.CharField('Devise', max_length=10, default='FCFA')

    # ── Dates ─────────────────────────────────────────────────────────────────
    dateCreation        = models.DateTimeField('Date de création', auto_now_add=True)
    datePublication     = models.DateTimeField('Date de publication', null=True, blank=True)
    dateExpiration      = models.DateField("Date d'expiration", null=True, blank=True)

    # ── Statut & stats ────────────────────────────────────────────────────────
    statutOffre         = models.CharField(
        'Statut', max_length=20, choices=StatutOffre.choices, default=StatutOffre.BROUILLON,
    )
    nbVues              = models.IntegerField('Vues', default=0)
    nbCandidatures      = models.IntegerField('Candidatures', default=0)

    # ── Critères ATS ──────────────────────────────────────────────────────────
    criteresATS         = models.JSONField('Critères ATS', default=dict)

    # ── Référentiels (FK / M2M — schéma cible) ───────────────────────────────
    contrat             = models.ForeignKey(
        ContratRef, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='offres',
        verbose_name='Contrat (référentiel)',
    )
    modeTravailRef      = models.ForeignKey(
        ModeTravailRef, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='offres',
        verbose_name='Mode de travail (référentiel)',
    )
    deviseRef           = models.ForeignKey(
        DeviseRef, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='offres',
        verbose_name='Devise (référentiel)',
    )
    anneesExperience    = models.ForeignKey(
        AnneesExperienceRef, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='offres',
        verbose_name="Années d'expérience",
    )
    niveauEtudeRef      = models.ForeignKey(
        NiveauEtudeRef, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='offres',
        verbose_name="Niveau d'études (référentiel)",
    )
    posteRef            = models.ForeignKey(
        PosteRef, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='offres',
        verbose_name='Poste (référentiel)',
    )
    paysRef             = models.ForeignKey(
        PaysRef, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='offres',
        verbose_name='Pays (référentiel)',
    )
    diplome             = models.ForeignKey(
        DiplomeRef, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='offres',
        verbose_name='Diplôme requis',
    )
    dureeContratMois    = models.IntegerField(
        'Durée du contrat (mois)', null=True, blank=True,
    )
    avantages           = models.TextField('Avantages', blank=True)
    nombrePostes        = models.IntegerField('Nombre de postes', default=1)

    # ── Embedding ATS (cache) ────────────────────────────────────────────────
    # JSONField (liste de 384 floats) plutôt que VectorField/pgvector : l'extension
    # serveur PostgreSQL "vector" n'est pas disponible sur l'hébergement O2switch
    # (PostgreSQL 9.6, pgvector exige 13+). Le calcul de similarité cosinus se fait
    # déjà en Python pur côté ats_predict.py, donc aucun impact fonctionnel.
    embedding           = models.JSONField('Embedding ATS', null=True, blank=True, editable=False)
    embedding_updated   = models.DateTimeField('Embedding mis à jour le', null=True, blank=True, editable=False)

    villesRef           = models.ManyToManyField(
        VilleRef, blank=True, related_name='offres',
        verbose_name='Villes (référentiel)',
    )
    langues             = models.ManyToManyField(
        LangueRef, blank=True, related_name='offres',
        verbose_name='Langues',
    )
    typesCompetence     = models.ManyToManyField(
        TypeCompetenceRef, blank=True, related_name='offres',
        verbose_name='Types de compétence',
    )

    class Meta:
        verbose_name        = "Offre d'emploi"
        verbose_name_plural = "Offres d'emploi"
        ordering            = ['-dateCreation']

    def __str__(self):
        return f"{self.titre} — {self.entreprise}"

    def save(self, *args, **kwargs):
        if not self.reference:
            import random, string
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=7))
            self.reference = f"OFF-{code}"
        super().save(*args, **kwargs)

    # ── Méthodes métier ───────────────────────────────────────────────────────

    def publier(self):
        self.statutOffre    = StatutOffre.PUBLIEE
        self.datePublication = timezone.now()
        self.save(update_fields=['statutOffre', 'datePublication'])

    def fermer(self):
        self.statutOffre = StatutOffre.FERMEE
        self.save(update_fields=['statutOffre'])

    def marquerPourvue(self):
        self.statutOffre = StatutOffre.POURVUE
        self.save(update_fields=['statutOffre'])

    def remettreEnBrouillon(self):
        self.statutOffre = StatutOffre.BROUILLON
        self.save(update_fields=['statutOffre'])

    def verifierExpiration(self):
        if (self.dateExpiration
                and self.dateExpiration < timezone.now().date()
                and self.statutOffre == StatutOffre.PUBLIEE):
            self.statutOffre = StatutOffre.EXPIREE
            self.save(update_fields=['statutOffre'])
            self._notifier_expiration()

    def _notifier_expiration(self):
        """Envoie une notification OFFRE_EXPIREE à tous les recruteurs de l'offre."""
        from django.urls import reverse
        lien = reverse('entreprise:candidatures_offre', args=[self.pk])
        nb = self.nbCandidatures
        titre = f"📋 Offre expirée — {self.titre}"
        msg   = (
            f"Votre offre « {self.titre} » a expiré avec {nb} candidature{'s' if nb > 1 else ''}. "
            f"Vous pouvez maintenant sélectionner les candidats retenus."
        )
        recruteurs = set()
        if self.creePar_id:
            recruteurs.add(self.creePar_id)
        for lien_rec in self.recruteurs_createurs.all():
            recruteurs.add(lien_rec.recruteur_id)
        for rec_id in recruteurs:
            NotificationRecruteur.objects.get_or_create(
                recruteur_id = rec_id,
                offre        = self,
                candidat     = None,
                type         = NotificationRecruteur.Type.OFFRE_EXPIREE,
                defaults     = {'titre': titre, 'message': msg, 'lien': lien},
            )

    def get_style_contrat(self):
        return STYLES_CONTRAT.get(self.typeContrat, {'bg': '#F3F4F6', 'text': '#374151', 'icon': '📄'})

    def get_style_statut(self):
        return STYLES_STATUT.get(self.statutOffre, STYLES_STATUT['BROUILLON'])

    def salaire_display(self):
        if self.salaireMin and self.salaireMax:
            return f"{int(self.salaireMin):,} – {int(self.salaireMax):,} {self.devise}"
        if self.salaireMin:
            return f"À partir de {int(self.salaireMin):,} {self.devise}"
        if self.salaireMax:
            return f"Jusqu'à {int(self.salaireMax):,} {self.devise}"
        return None


# ── Table de liaison : qui a créé / collaboré sur l'offre ────────────────────

class OffreEmploiRecruteur(models.Model):
    """Trace les recruteurs qui ont créé / collaborent sur une offre (relation +crée).

    Permet à plusieurs recruteurs de la même entreprise d'être associés
    à une offre (binôme RH + manager, par exemple) avec horodatage.
    """

    offre        = models.ForeignKey(
        OffreEmploi, on_delete=models.CASCADE,
        related_name='recruteurs_createurs',
        verbose_name='Offre',
    )
    recruteur    = models.ForeignKey(
        Recruteur, on_delete=models.CASCADE,
        related_name='offres_createurs',
        verbose_name='Recruteur',
    )
    dateCreation = models.DateTimeField('Date de création', auto_now_add=True)

    class Meta:
        verbose_name        = "Offre / Recruteur"
        verbose_name_plural = "Offres / Recruteurs"
        unique_together     = ('offre', 'recruteur')
        ordering            = ['-dateCreation']

    def __str__(self):
        return f"{self.recruteur} → {self.offre}"


# ── Tracking des profils proposés par l'ATS au recruteur ─────────────────────

class PropositionProfil(models.Model):
    """Profil candidat proposé par l'ATS à un recruteur pour une offre donnée.

    Chaque ligne est un signal pour l'apprentissage de l'ATS :
      * `propose` : profil affiché dans la liste de recommandations
      * `vu`      : recruteur a consulté le portfolio
      * `contacte`: recruteur a contacté le candidat
      * `invite`  : recruteur a invité le candidat à postuler
      * `ignore`  : recruteur a masqué le profil

    Les actions servent de labels pour entraîner `entreprise/ats_ml.py`
    (cf. `python manage.py entrainer_ats`).
    """

    class Action(models.TextChoices):
        PROPOSE  = 'propose',  'Proposé'
        VU       = 'vu',       'Portfolio consulté'
        CONTACTE = 'contacte', 'Candidat contacté'
        INVITE   = 'invite',   'Invité à postuler'
        IGNORE   = 'ignore',   'Profil ignoré'

    offre = models.ForeignKey(
        OffreEmploi, on_delete=models.CASCADE,
        related_name='propositions_profils',
        verbose_name='Offre',
    )
    candidat = models.ForeignKey(
        'candidat.Candidat', on_delete=models.CASCADE,
        related_name='propositions_recues',
        verbose_name='Candidat proposé',
    )
    recruteur = models.ForeignKey(
        Recruteur, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='propositions_creees',
        verbose_name='Recruteur',
    )
    scoreATS = models.FloatField(
        'Score ATS au moment de la proposition',
        help_text="Score 0-100 calculé par le sentence-transformer ATS.",
    )
    action = models.CharField(
        'Action recruteur',
        max_length=12, choices=Action.choices,
        default=Action.PROPOSE,
    )
    dateProposition = models.DateTimeField('Date de proposition', auto_now_add=True)
    dateAction      = models.DateTimeField('Date de l\'action', null=True, blank=True)

    class Meta:
        verbose_name        = 'Profil proposé'
        verbose_name_plural = 'Profils proposés'
        unique_together     = ('offre', 'candidat')
        ordering            = ['-dateProposition']
        indexes = [
            models.Index(fields=['offre', '-dateProposition']),
            models.Index(fields=['candidat', '-dateProposition']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        return f"{self.candidat} → {self.offre} ({self.get_action_display()}, {self.scoreATS:.0f}%)"

    def marquer_action(self, action):
        """Met à jour l'action et la date — utilisé par les endpoints de tracking."""
        if action not in dict(self.Action.choices):
            raise ValueError(f"Action inconnue : {action}")
        self.action = action
        self.dateAction = timezone.now()
        self.save(update_fields=['action', 'dateAction'])


# ── Notifications côté recruteur (in-app + email optionnel) ─────────────────

class NotificationRecruteur(models.Model):
    """Notification destinée à un recruteur — déclenchée par l'ATS et le système.

    Types supportés :
      • PROFIL_MATCH : un profil candidat correspond à une offre publiée (score ≥ seuil)
      • CANDIDATURE  : nouvelle candidature reçue (futur)
      • SYSTEME      : message système (annonces, modération, etc.)

    Idempotent : la contrainte unique (recruteur, offre, candidat, type) empêche
    les doublons. Le flag `emailEnvoye` évite tout spam.
    """

    class Type(models.TextChoices):
        PROFIL_MATCH         = 'PROFIL_MATCH',         "Profil correspondant"
        CANDIDATURE          = 'CANDIDATURE',           "Nouvelle candidature"
        MESSAGE              = 'MESSAGE',               "Message d'un candidat"
        OFFRE_EXPIREE        = 'OFFRE_EXPIREE',         "Offre expirée"
        SUGGESTION_COLLEGUE  = 'SUGGESTION_COLLEGUE',   "Suggestion d'un collègue"
        SYSTEME              = 'SYSTEME',               "Système"

    # Destinataire : soit un Recruteur, soit le compte Entreprise admin.
    # Exactement l'un des deux DOIT être renseigné (vérifié par contrainte BD).
    recruteur = models.ForeignKey(
        Recruteur, on_delete=models.CASCADE,
        related_name='notifications', verbose_name='Recruteur',
        null=True, blank=True,
    )
    entreprise = models.ForeignKey(
        Entreprise, on_delete=models.CASCADE,
        related_name='notifications_admin', verbose_name='Entreprise (compte admin)',
        null=True, blank=True,
    )
    type = models.CharField(
        max_length=20, choices=Type.choices, default=Type.PROFIL_MATCH,
        verbose_name='Type',
    )
    titre   = models.CharField(max_length=200, verbose_name='Titre')
    message = models.TextField(blank=True, default='', verbose_name='Message')
    lien    = models.CharField(
        max_length=500, blank=True, default='',
        verbose_name="Lien d'action",
    )

    # Références — toutes nullables pour permettre différents types
    offre = models.ForeignKey(
        OffreEmploi, on_delete=models.CASCADE,
        null=True, blank=True, related_name='notifications_recruteurs',
        verbose_name='Offre concernée',
    )
    candidat = models.ForeignKey(
        'candidat.Candidat', on_delete=models.CASCADE,
        null=True, blank=True, related_name='notifications_recruteurs',
        verbose_name='Candidat concerné',
    )
    expediteur = models.ForeignKey(
        Recruteur, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='suggestions_envoyees',
        verbose_name='Expéditeur (suggestion)',
    )
    expediteur_nom = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Nom expéditeur (admin ou texte libre)',
    )
    score = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Score ATS',
        help_text="Pour les PROFIL_MATCH, score 0-100 calculé par l'ATS.",
    )

    # État de lecture
    lue          = models.BooleanField(default=False, verbose_name='Lue')
    dateLecture  = models.DateTimeField(null=True, blank=True)
    dateCreation = models.DateTimeField(auto_now_add=True)

    # Suivi email
    emailEnvoye        = models.BooleanField(default=False)
    dateEnvoiEmail     = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = "Notification recruteur"
        verbose_name_plural = "Notifications recruteurs"
        ordering            = ['-dateCreation']
        # Idempotence : pas de doublon (destinataire, offre, candidat, type)
        # Le destinataire est soit un recruteur, soit une entreprise.
        constraints = [
            models.UniqueConstraint(
                fields=['recruteur', 'offre', 'candidat', 'type'],
                condition=models.Q(recruteur__isnull=False),
                name='uniq_notif_recruteur_offre_candidat_type',
            ),
            models.UniqueConstraint(
                fields=['entreprise', 'offre', 'candidat', 'type'],
                condition=models.Q(entreprise__isnull=False),
                name='uniq_notif_entreprise_offre_candidat_type',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(recruteur__isnull=False, entreprise__isnull=True)
                    | models.Q(recruteur__isnull=True, entreprise__isnull=False)
                ),
                name='notif_target_exclusif',
            ),
        ]
        indexes = [
            models.Index(fields=['recruteur', '-dateCreation']),
            models.Index(fields=['entreprise', '-dateCreation']),
            models.Index(fields=['recruteur', 'lue']),
            models.Index(fields=['entreprise', 'lue']),
            models.Index(fields=['type']),
        ]

    def __str__(self):
        cible = self.recruteur or self.entreprise
        return f"[{self.get_type_display()}] {cible} — {self.titre[:50]}"

    def marquer_lue(self):
        if not self.lue:
            self.lue = True
            self.dateLecture = timezone.now()
            self.save(update_fields=['lue', 'dateLecture'])

    @property
    def expediteur_affiche(self):
        """Nom affiché de l'expéditeur, avec fallbacks successifs."""
        if self.expediteur_nom:
            return self.expediteur_nom
        if self.expediteur:
            nom = (f"{self.expediteur.prenom} {self.expediteur.nom}").strip()
            return nom or self.expediteur.nomComplet or self.expediteur.email or ''
        # Fallback : extraire depuis le titre "👥 Prénom Nom vous suggère un profil"
        import re
        m = re.match(r'^👥\s+(.+?)\s+vous suggère un profil', self.titre or '')
        return m.group(1) if m else ''

    @property
    def expediteur_photo_url(self):
        """URL de la photo de l'expéditeur, ou None."""
        if self.expediteur and self.expediteur.photoProfil:
            try:
                return self.expediteur.photoProfil.url
            except Exception:
                return None
        return None

    @property
    def expediteur_initiales(self):
        """Deux premières lettres du nom affiché, en majuscules."""
        nom = self.expediteur_affiche
        return nom[:2].upper() if nom else ''


# ── Vérification email ────────────────────────────────────────────────────────

class TokenVerificationEmail(models.Model):
    entreprise      = models.ForeignKey(
        Entreprise, on_delete=models.CASCADE,
        related_name='tokens_verification_email',
        verbose_name='Entreprise',
    )
    token           = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    code            = models.CharField('Code', max_length=6, blank=True, default='')
    date_creation   = models.DateTimeField('Créé le', auto_now_add=True)
    date_expiration = models.DateTimeField('Expire le')
    utilise         = models.BooleanField('Utilisé', default=False)

    class Meta:
        verbose_name = 'Token vérification email'
        ordering     = ['-date_creation']

    def __str__(self):
        return f"Token {self.entreprise} — {'utilisé' if self.utilise else 'actif'}"

    def save(self, *args, **kwargs):
        if not self.pk:
            self.date_expiration = timezone.now() + timedelta(minutes=15)
        super().save(*args, **kwargs)

    def est_valide(self):
        return not self.utilise and timezone.now() < self.date_expiration

    @staticmethod
    def generer_code():
        return f"{random.randint(0, 999999):06d}"


# ── Demande de vérification du compte ────────────────────────────────────────

class StatutDemande(models.TextChoices):
    EN_ATTENTE = 'EN_ATTENTE', "En attente d'examen"
    APPROUVEE  = 'APPROUVEE',  'Approuvée'
    REJETEE    = 'REJETEE',    'Rejetée'


class DemandeVerification(models.Model):
    entreprise        = models.ForeignKey(
        Entreprise, on_delete=models.CASCADE,
        related_name='demandes_verification',
        verbose_name='Entreprise',
    )
    statut            = models.CharField(
        'Statut', max_length=20,
        choices=StatutDemande.choices,
        default=StatutDemande.EN_ATTENTE,
    )
    date_soumission   = models.DateTimeField('Soumise le', auto_now_add=True)
    document_rccm     = models.FileField(
        'Registre du commerce', upload_to='entreprise/verifications/rccm/',
        storage=get_kyc_storage, blank=True, null=True,
    )
    document_identite = models.FileField(
        "Pièce d'identité dirigeant", upload_to='entreprise/verifications/identite/',
        storage=get_kyc_storage,
        blank=True, null=True,
    )
    notes_entreprise  = models.TextField("Message de l'entreprise", blank=True)
    notes_admin       = models.TextField('Notes administrateur', blank=True)
    date_traitement   = models.DateTimeField('Traitée le', null=True, blank=True)
    traite_par        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='demandes_traitees',
        verbose_name='Traitée par',
    )

    class Meta:
        verbose_name        = 'Demande de vérification'
        verbose_name_plural = 'Demandes de vérification'
        ordering            = ['-date_soumission']

    def __str__(self):
        return f"Demande — {self.entreprise} ({self.get_statut_display()})"


# ── Réinitialisation du mot de passe entreprise ───────────────────────────────

class TokenReinitialisationEntreprise(models.Model):
    """Token à usage unique pour la réinitialisation du mot de passe entreprise (valide 10 minutes)."""

    METHODE_CHOICES = [('code', 'Code 5 chiffres'), ('lien', 'Lien')]

    entreprise   = models.ForeignKey(
        Entreprise, on_delete=models.CASCADE,
        related_name='tokens_reinitialisation',
        verbose_name='Entreprise',
    )
    token        = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    code         = models.CharField(max_length=5, blank=True, default='')
    methode      = models.CharField(max_length=4, choices=METHODE_CHOICES, default='lien')
    dateCreation = models.DateTimeField('Créé le', auto_now_add=True)
    utilise      = models.BooleanField('Utilisé', default=False)
    verifie      = models.BooleanField('Vérifié', default=False)

    class Meta:
        verbose_name        = 'Token réinitialisation MDP entreprise'
        verbose_name_plural = 'Tokens réinitialisation MDP entreprises'

    def __str__(self):
        return f"Token {self.token} — {self.entreprise.emailProfessionnel}"

    def est_valide(self):
        return not self.utilise and (timezone.now() - self.dateCreation) < timedelta(minutes=10)

    @staticmethod
    def generer_code():
        return str(random.randint(10000, 99999))


# ══════════════════════════════════════════════════════════════════════════════
# Messagerie : modèles de message + envois
# ══════════════════════════════════════════════════════════════════════════════

class ModeleMessage(models.Model):
    """Template de message créé par l'admin entreprise.

    Lié à un `referentiel.Statut` : lors d'un changement de statut sur une
    candidature (acceptation, refus, etc.), le système propose au recruteur
    les modèles associés au statut cible.

    Le `corps_message` peut contenir des variables `{{ candidat.prenom }}`,
    `{{ offre.titre }}`, etc., rendues côté serveur au moment de l'envoi
    (cf. `entreprise.messagerie.rendre_template`).
    """

    entreprise            = models.ForeignKey(
        Entreprise, on_delete=models.CASCADE,
        related_name='modeles_messages',
        verbose_name='Entreprise',
    )
    # Exactement UN des deux est renseigné : soit statut (flow réponse à
    # candidature), soit typeEntretien (flow planification d'entretien).
    statut                = models.ForeignKey(
        'referentiel.Statut', on_delete=models.PROTECT,
        null=True, blank=True, related_name='modeles_messages',
        verbose_name='Statut associé',
        help_text="Pour les modèles déclenchés par un changement de statut de candidature.",
    )
    typeEntretien         = models.ForeignKey(
        'referentiel.TypeEntretien', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='modeles_messages',
        verbose_name="Type d'entretien associé",
        help_text="Pour les modèles utilisés lors de la planification d'un entretien (RH, Technique…).",
    )
    sujet_modele          = models.CharField('Sujet', max_length=255)
    corps_message         = models.TextField('Corps du message')
    variables_disponibles = models.TextField(
        'Variables disponibles', blank=True, default='',
        help_text=(
            "Liste des variables utilisables dans le corps. "
            "Ex : {{ candidat.prenom }}, {{ candidat.nom }}, {{ offre.titre }}, "
            "{{ entreprise.raisonSocial }}, {{ recruteur.nomComplet }}."
        ),
    )
    est_actif             = models.BooleanField('Actif', default=True)
    creePar               = models.ForeignKey(
        'Recruteur', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='modeles_crees',
        verbose_name='Créé par',
    )
    date_creation         = models.DateTimeField(auto_now_add=True)
    date_modification     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Modèle de message'
        verbose_name_plural = 'Modèles de message'
        ordering            = ['-date_modification']
        constraints = [
            models.UniqueConstraint(
                fields=['entreprise', 'sujet_modele'],
                name='unique_modele_par_entreprise_sujet',
            ),
        ]

    def __str__(self):
        return self.sujet_modele


class Message(models.Model):
    """Message envoyé par un recruteur à un candidat (suite à une décision
    sur une candidature, ou de manière standalone).

    Une copie du `sujet` et du `contenu` rendus est stockée afin que la
    suppression du modèle n'affecte pas les messages déjà envoyés.
    """

    # ── Destinataire ─────────────────────────────────────────────────────────
    candidat       = models.ForeignKey(
        'candidat.Candidat', on_delete=models.CASCADE,
        related_name='messages_recus',
        verbose_name='Candidat destinataire',
    )
    # ── Émetteur ─────────────────────────────────────────────────────────────
    recruteur      = models.ForeignKey(
        'Recruteur', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='messages_envoyes',
        verbose_name='Recruteur émetteur',
    )
    # ── Contexte (optionnel) — candidature à laquelle le message se rapporte
    candidature    = models.ForeignKey(
        'candidat.Candidature', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='messages',
        verbose_name='Candidature liée',
    )
    # ── Référence au template utilisé (SET_NULL pour conserver l'historique)
    modele_message = models.ForeignKey(
        ModeleMessage, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='messages',
        verbose_name='Modèle utilisé',
    )
    modele_utilise = models.CharField(
        'Snapshot du nom du modèle', max_length=255, blank=True, default='',
        help_text='Conservé même si le modèle est supprimé.',
    )

    # ── Contenu rendu (snapshot — résiste à la suppression du template) ─────
    sujet          = models.CharField('Sujet', max_length=255, blank=True, default='')
    contenu        = models.TextField('Contenu')
    piece_jointe   = models.FileField(
        'Pièce jointe', upload_to='messages/pieces_jointes/',
        blank=True, null=True,
    )

    # ── Suivi ───────────────────────────────────────────────────────────────
    date_envoi     = models.DateTimeField(auto_now_add=True)
    date_lecture   = models.DateTimeField(blank=True, null=True)
    est_lu         = models.BooleanField(default=False)

    class Meta:
        verbose_name        = 'Message'
        verbose_name_plural = 'Messages'
        ordering            = ['-date_envoi']

    def __str__(self):
        return f"Message #{self.pk} → {self.candidat}"

    @property
    def expediteur_display(self):
        """Nom affiché de l'expéditeur : recruteur ou nom de l'entreprise."""
        if self.recruteur_id:
            return self.recruteur.nomComplet or self.recruteur.email
        if self.candidature_id:
            return self.candidature.offre.entreprise.raisonSocial
        return "L'entreprise"

    def marquer_lu(self):
        if not self.est_lu:
            self.est_lu      = True
            self.date_lecture = timezone.now()
            self.save(update_fields=['est_lu', 'date_lecture'])


# ── Planification du ré-entraînement ML ────────────────────────────────────────

class FrequencePlanif(models.TextChoices):
    QUOTIDIEN     = 'QUOTIDIEN',     _('Quotidien')
    HEBDOMADAIRE  = 'HEBDOMADAIRE',  _('Hebdomadaire')
    MENSUEL       = 'MENSUEL',       _('Mensuel')


class ModePlanif(models.TextChoices):
    OS_NATIF   = 'OS_NATIF',   _('Tâche système (Windows / cron)')
    WEB_TRAFIC = 'WEB_TRAFIC', _('Déclencheur via trafic web')


class PlanificationML(models.Model):
    """Configuration de la planification du ré-entraînement des modèles ML.

    Singleton : il ne doit y avoir qu'une seule instance en BD (id=1).
    L'adapter OS approprié est sélectionné automatiquement par `ml_scheduler.py`.
    """

    active = models.BooleanField('Activée', default=False)

    mode = models.CharField(
        'Mode de déclenchement', max_length=20,
        choices=ModePlanif.choices, default=ModePlanif.OS_NATIF,
        help_text=(
            "OS_NATIF : utilise schtasks (Windows) ou crontab (Linux/Mac). "
            "WEB_TRAFIC : déclenché par une visite HTTP après l'heure prévue."
        ),
    )

    frequence = models.CharField(
        'Fréquence', max_length=20,
        choices=FrequencePlanif.choices, default=FrequencePlanif.HEBDOMADAIRE,
    )
    # Jour de la semaine pour HEBDOMADAIRE (0=lundi, 6=dimanche)
    jour_semaine = models.IntegerField(
        'Jour de la semaine', default=6,
        help_text='0=lundi, 6=dimanche (utilisé si fréquence=HEBDOMADAIRE).',
    )
    # Jour du mois pour MENSUEL (1-28)
    jour_mois = models.IntegerField(
        'Jour du mois', default=1,
        help_text='1-28 (utilisé si fréquence=MENSUEL).',
    )
    heure = models.TimeField('Heure d\'exécution', default='03:00')

    # ── Suivi ─────────────────────────────────────────────────────────────────
    derniere_execution = models.DateTimeField('Dernière exécution', null=True, blank=True)
    derniere_status    = models.CharField(
        'Dernier statut', max_length=20, blank=True, default='',
        help_text='ok / error / running',
    )
    derniere_duree_sec = models.FloatField('Durée dernière (s)', null=True, blank=True)
    derniere_message   = models.TextField('Message dernière', blank=True, default='')

    prochaine_execution = models.DateTimeField('Prochaine exécution', null=True, blank=True)

    # ── Métadonnées ───────────────────────────────────────────────────────────
    date_modification = models.DateTimeField(auto_now=True)
    modifie_par       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )

    class Meta:
        verbose_name        = 'Planification ML'
        verbose_name_plural = 'Planification ML'

    def __str__(self):
        etat = 'active' if self.active else 'inactive'
        return f"Planification ML ({etat}, {self.get_frequence_display()})"

    @classmethod
    def singleton(cls) -> 'PlanificationML':
        """Renvoie l'unique instance (la crée si elle n'existe pas)."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# ─── Témoignages clients (espace entreprise) ──────────────────────────────────

class TemoignageEntreprise(models.Model):
    STATUT_EN_ATTENTE = 'en_attente'
    STATUT_PUBLIE     = 'publie'
    STATUT_REJETE     = 'rejete'
    STATUT_CHOICES = [
        (STATUT_EN_ATTENTE, 'En attente'),
        (STATUT_PUBLIE,     'Publié'),
        (STATUT_REJETE,     'Rejeté'),
    ]
    SOURCE_ADMIN      = 'admin'
    SOURCE_ENTREPRISE = 'entreprise'
    SOURCE_CHOICES = [
        (SOURCE_ADMIN,      'Admin'),
        (SOURCE_ENTREPRISE, 'Entreprise'),
    ]

    entreprise  = models.ForeignKey(
        'Entreprise', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='temoignages',
        verbose_name='Entreprise liée',
    )
    prenom_nom  = models.CharField(max_length=100, verbose_name='Nom complet')
    poste       = models.CharField(max_length=150, blank=True, default='', verbose_name='Poste / Entreprise')
    texte       = models.TextField(verbose_name='Témoignage')
    note        = models.PositiveSmallIntegerField(default=5, verbose_name='Note (1-5)')
    statut      = models.CharField(max_length=15, choices=STATUT_CHOICES, default=STATUT_EN_ATTENTE, verbose_name='Statut')
    source      = models.CharField(max_length=15, choices=SOURCE_CHOICES, default=SOURCE_ADMIN, verbose_name='Source')
    ordre       = models.PositiveSmallIntegerField(default=0, verbose_name="Ordre d'affichage")
    date_soumission = models.DateTimeField(auto_now_add=True, verbose_name='Date de soumission')

    class Meta:
        verbose_name        = 'Témoignage client'
        verbose_name_plural = 'Témoignages clients'
        ordering            = ['ordre', '-date_soumission']
        constraints = [
            models.UniqueConstraint(
                fields=['entreprise'],
                condition=models.Q(entreprise__isnull=False),
                name='unique_temoignage_par_entreprise',
            ),
        ]

    def __str__(self):
        return f'{self.prenom_nom} — {self.get_statut_display()}'


class TemoignageEnAttenteEntreprise(TemoignageEntreprise):
    """Proxy pour la file de modération admin — témoignages clients en attente."""
    class Meta:
        proxy               = True
        verbose_name        = 'Témoignage client en attente'
        verbose_name_plural = 'Témoignages clients en attente'
        ordering            = ['-date_soumission']


# ── Partage de profil candidat vers entreprise externe ───────────────────────

class PartageProfilExterne(models.Model):
    """Lien de partage d'un profil candidat envoyé à une entreprise tierce.

    Accessible publiquement via un token UUID (sans authentification).
    Expire après 30 jours. Seuls ADMIN / RH / MANAGER peuvent créer un lien.
    Les coordonnées du candidat ne sont jamais exposées dans la vue publique.
    """

    recruteur          = models.ForeignKey(
        'Recruteur', on_delete=models.CASCADE,
        related_name='partages_profils',
        verbose_name='Recruteur partageur',
        null=True, blank=True,
    )
    entreprise_partageur = models.ForeignKey(
        'Entreprise', on_delete=models.CASCADE,
        related_name='partages_profils_admin',
        verbose_name='Entreprise partageur (admin)',
        null=True, blank=True,
    )
    candidat           = models.ForeignKey(
        'candidat.Candidat', on_delete=models.CASCADE,
        related_name='partages_externes',
        verbose_name='Candidat partagé',
    )
    token              = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False,
        verbose_name='Token de partage',
    )
    email_destinataire = models.EmailField(
        blank=True, verbose_name='Email destinataire',
        help_text="Email de l'entreprise tierce (optionnel, pour envoi direct).",
    )
    message            = models.TextField(
        blank=True, verbose_name="Message d'accompagnement",
        help_text="Message personnalisé affiché sur la page publique du profil.",
    )
    date_creation      = models.DateTimeField(auto_now_add=True, verbose_name='Créé le')
    date_expiration    = models.DateTimeField(verbose_name='Expire le')
    date_premiere_vue  = models.DateTimeField(
        null=True, blank=True, verbose_name='Première consultation',
    )
    nb_vues            = models.PositiveIntegerField(default=0, verbose_name='Nombre de vues')
    actif              = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        verbose_name        = 'Partage de profil externe'
        verbose_name_plural = 'Partages de profils externes'
        ordering            = ['-date_creation']
        indexes             = [models.Index(fields=['token'])]

    def __str__(self):
        return f"Partage {self.candidat} → {self.email_destinataire or 'lien direct'}"

    def save(self, *args, **kwargs):
        if not self.pk:
            self.date_expiration = timezone.now() + timedelta(days=30)
        super().save(*args, **kwargs)

    @property
    def est_expire(self):
        return timezone.now() > self.date_expiration

    @property
    def est_valide(self):
        return self.actif and not self.est_expire

    def enregistrer_vue(self):
        """Incrémente le compteur et note la première consultation."""
        self.nb_vues += 1
        if not self.date_premiere_vue:
            self.date_premiere_vue = timezone.now()
        self.save(update_fields=['nb_vues', 'date_premiere_vue'])

    def get_url_absolue(self, request=None):
        from django.urls import reverse
        path = reverse('entreprise:profil_partage_public', kwargs={'token': str(self.token)})
        if request:
            return request.build_absolute_uri(path)
        return path


# ── Contact candidat ─────────────────────────────────────────────────────────

class InvitationPostuler(models.Model):
    STATUT_EN_ATTENTE = 'en_attente'
    STATUT_ACCEPTEE   = 'acceptee'
    STATUT_IGNOREE    = 'ignoree'
    STATUT_CHOICES = [
        (STATUT_EN_ATTENTE, 'En attente'),
        (STATUT_ACCEPTEE,   'Acceptée'),
        (STATUT_IGNOREE,    'Ignorée'),
    ]

    offre     = models.ForeignKey(
        'OffreEmploi', on_delete=models.CASCADE, related_name='invitations',
    )
    recruteur = models.ForeignKey(
        'Recruteur', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='invitations_envoyees',
    )
    candidat  = models.ForeignKey(
        'candidat.Candidat', on_delete=models.CASCADE, related_name='invitations_recues',
    )
    message   = models.TextField(blank=True, default='')
    statut    = models.CharField(max_length=15, choices=STATUT_CHOICES, default=STATUT_EN_ATTENTE)
    date_envoi = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Invitation à postuler'
        verbose_name_plural = 'Invitations à postuler'
        unique_together     = [['offre', 'candidat']]
        ordering            = ['-date_envoi']

    def __str__(self):
        return f'Invitation {self.offre} → {self.candidat} ({self.get_statut_display()})'


class InvitationEntretien(models.Model):
    """Profil retenu pour entretien depuis le portfolio.

    Signal d'intérêt du recruteur : le candidat est notifié que son profil
    a été retenu et qu'il sera contacté. La planification réelle se fait
    ensuite dans l'espace dédié.
    """

    STATUT_EN_ATTENTE = 'en_attente'
    STATUT_PLANIFIE   = 'planifie'
    STATUT_ANNULE     = 'annule'
    STATUT_CHOICES = [
        (STATUT_EN_ATTENTE, 'En attente de planification'),
        (STATUT_PLANIFIE,   'Entretien planifié'),
        (STATUT_ANNULE,     'Annulé'),
    ]

    offre        = models.ForeignKey(
        'OffreEmploi', on_delete=models.CASCADE,
        related_name='invitations_entretien',
    )
    recruteur    = models.ForeignKey(
        'Recruteur', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='entretiens_invites',
    )
    candidat     = models.ForeignKey(
        'candidat.Candidat', on_delete=models.CASCADE,
        related_name='invitations_entretien',
    )
    MODE_CHOICES = [
        ('PRESENTIEL',   'Présentiel'),
        ('VISIO',        'Visioconférence'),
        ('TELEPHONIQUE', 'Téléphonique'),
    ]

    statut        = models.CharField(max_length=15, choices=STATUT_CHOICES, default=STATUT_EN_ATTENTE)
    dateCreation  = models.DateTimeField(auto_now_add=True)
    dateEntretien = models.DateTimeField('Date & heure', null=True, blank=True)
    duree         = models.IntegerField('Durée (minutes)', default=60)
    mode          = models.CharField('Mode', max_length=20, choices=MODE_CHOICES, default='PRESENTIEL')
    lieu          = models.CharField('Lieu / Lien', max_length=300, blank=True, default='')
    notes         = models.TextField('Notes', blank=True, default='')

    class Meta:
        verbose_name        = 'Profil retenu pour entretien'
        verbose_name_plural = 'Profils retenus pour entretien'
        unique_together     = [['offre', 'candidat']]
        ordering            = ['-dateCreation']

    def __str__(self):
        return f'Retenu — {self.offre} → {self.candidat}'


class ConversationDirecte(models.Model):
    recruteur = models.ForeignKey(
        'Recruteur', on_delete=models.CASCADE, related_name='conversations',
    )
    candidat  = models.ForeignKey(
        'candidat.Candidat', on_delete=models.CASCADE, related_name='conversations',
    )
    date_creation        = models.DateTimeField(auto_now_add=True)
    date_dernier_message = models.DateTimeField(auto_now_add=True)

    # Gestion par recruteur
    archivee_recruteur   = models.BooleanField(default=False)
    silencieux_recruteur = models.BooleanField(default=False)
    supprimee_recruteur  = models.BooleanField(default=False)

    # Gestion par candidat
    archivee_candidat    = models.BooleanField(default=False)
    silencieux_candidat  = models.BooleanField(default=False)
    supprimee_candidat   = models.BooleanField(default=False)

    class Meta:
        verbose_name        = 'Conversation directe'
        verbose_name_plural = 'Conversations directes'
        unique_together     = [['recruteur', 'candidat']]
        ordering            = ['-date_dernier_message']

    def __str__(self):
        return f'{self.recruteur} ↔ {self.candidat}'


class MessageDirect(models.Model):
    EXPEDITEUR_RECRUTEUR = 'recruteur'
    EXPEDITEUR_CANDIDAT  = 'candidat'
    EXPEDITEUR_CHOICES   = [
        (EXPEDITEUR_RECRUTEUR, 'Recruteur'),
        (EXPEDITEUR_CANDIDAT,  'Candidat'),
    ]

    TYPE_TEXTE   = 'texte'
    TYPE_IMAGE   = 'image'
    TYPE_FICHIER = 'fichier'
    TYPE_AUDIO   = 'audio'
    TYPE_CHOICES = [
        (TYPE_TEXTE,   'Texte'),
        (TYPE_IMAGE,   'Image'),
        (TYPE_FICHIER, 'Fichier'),
        (TYPE_AUDIO,   'Note vocale'),
    ]

    conversation = models.ForeignKey(
        ConversationDirecte, on_delete=models.CASCADE, related_name='messages',
    )
    expediteur   = models.CharField(max_length=15, choices=EXPEDITEUR_CHOICES)
    contenu      = models.TextField(blank=True, default='')
    type_msg     = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_TEXTE)
    fichier      = models.FileField(upload_to='messages/%Y/%m/', null=True, blank=True)
    nom_fichier  = models.CharField(max_length=255, blank=True)
    date_envoi   = models.DateTimeField(auto_now_add=True)
    lu           = models.BooleanField(default=False)
    supprime     = models.BooleanField(default=False)
    epingle      = models.BooleanField(default=False)

    class Meta:
        verbose_name        = 'Message direct'
        verbose_name_plural = 'Messages directs'
        ordering            = ['date_envoi']

    def __str__(self):
        return f'[{self.expediteur}] {self.contenu[:60] or self.type_msg}'
