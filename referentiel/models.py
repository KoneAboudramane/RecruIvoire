from django.contrib.auth.hashers import make_password, check_password as django_check_password
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

class Pays(models.Model):
    nomPays      = models.CharField(max_length=100, verbose_name='Nom du pays')
    codeISO      = models.CharField(max_length=3, unique=True, verbose_name='Code ISO')
    estActif     = models.BooleanField(default=True, verbose_name='Actif')
    indicatifTel = models.CharField(max_length=10, blank=True, verbose_name='Indicatif téléphonique')
    nationalite  = models.CharField(max_length=100, blank=True, verbose_name='Nationalité',
                                    help_text='Gentilé du pays (ex : française, ivoirienne, sénégalaise)')

    class Meta:
        ordering = ['nomPays']
        verbose_name = 'Pays'
        verbose_name_plural = 'Pays'

    def __str__(self):
        return self.nomPays


class Ville(models.Model):
    nomVille = models.CharField(max_length=100, verbose_name='Nom de la ville')
    region   = models.CharField(max_length=100, blank=True, verbose_name='Région')
    estActif = models.BooleanField(default=True, verbose_name='Actif')
    pays     = models.ForeignKey(Pays, on_delete=models.CASCADE, related_name='villes', verbose_name='Pays')

    class Meta:
        ordering = ['nomVille']
        verbose_name = 'Ville'
        verbose_name_plural = 'Villes'

    def __str__(self):
        return self.nomVille


class TypeCompetence(models.Model):
    nomCompetence = models.CharField(max_length=150, verbose_name='Nom de la compétence')
    domaine       = models.CharField(max_length=100, blank=True, verbose_name='Domaine')

    class Meta:
        ordering = ['domaine', 'nomCompetence']
        verbose_name = 'Type de compétence'
        verbose_name_plural = 'Types de compétences'

    def __str__(self):
        return self.nomCompetence


class TypeCentreInteret(models.Model):
    nomCentreInteret = models.CharField(max_length=150, verbose_name='Centre d\'intérêt')

    class Meta:
        ordering = ['nomCentreInteret']
        verbose_name = 'Centre d\'intérêt'
        verbose_name_plural = 'Centres d\'intérêt'

    def __str__(self):
        return self.nomCentreInteret


class Institution(models.Model):
    nomInstitution = models.CharField(max_length=200, verbose_name='Nom de l\'institution')

    class Meta:
        ordering = ['nomInstitution']
        verbose_name = 'Institution'
        verbose_name_plural = 'Institutions'

    def __str__(self):
        return self.nomInstitution


class Langue(models.Model):
    nomLangue = models.CharField(max_length=100, verbose_name='Nom de la langue')
    codeISO   = models.CharField(max_length=3, blank=True, verbose_name='Code ISO')

    class Meta:
        ordering = ['nomLangue']
        verbose_name = 'Langue'
        verbose_name_plural = 'Langues'

    def __str__(self):
        return self.nomLangue


class Statut(models.Model):
    """Statut d'une candidature (référentiel partagé).

    Utilisé par :
      - `candidat.Candidature.statut` (statut courant)
      - `candidat.HistoriqueStatut.ancienStatut` / `.nouveauStatut`
    Seedé via la data migration `referentiel/migrations/0XXX_seed_statut.py`.
    """
    code         = models.CharField(max_length=30, unique=True,
                                    verbose_name='Code')
    libelle      = models.CharField(max_length=80, verbose_name='Libellé')
    description  = models.CharField(max_length=255, blank=True, default='',
                                    verbose_name='Description')
    ordre        = models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')
    couleur      = models.CharField(max_length=7, default='#94A3B8',
                                    verbose_name='Couleur (hex)')
    icone        = models.CharField(max_length=10, blank=True, default='',
                                    verbose_name='Icône (emoji)')
    estFinal     = models.BooleanField(default=False, verbose_name='Statut final',
                                       help_text="Si vrai, plus aucune transition possible (embauche/refus/retrait).")
    estPositif   = models.BooleanField(null=True, blank=True, verbose_name='Issue positive ?',
                                       help_text="True = succès, False = échec, None = en cours.")
    estActif     = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        ordering            = ['ordre', 'libelle']
        verbose_name        = 'Statut de candidature'
        verbose_name_plural = 'Statuts de candidature'

    def __str__(self):
        return self.libelle


class TypePermis(models.Model):
    nomPermis   = models.CharField(max_length=20, verbose_name='Code permis')
    description = models.CharField(max_length=200, blank=True, verbose_name='Description')

    class Meta:
        ordering = ['nomPermis']
        verbose_name = 'Permis de conduire'
        verbose_name_plural = 'Permis de conduire'

    def __str__(self):
        return self.nomPermis


class TypeRaisonSociale(models.Model):
    nomRaisonSocial = models.CharField(max_length=200, verbose_name='Forme juridique')
    secteur         = models.CharField(max_length=100, blank=True, verbose_name='Secteur d\'activité')

    class Meta:
        ordering = ['nomRaisonSocial']
        verbose_name = 'Type de raison sociale'
        verbose_name_plural = 'Types de raison sociale'

    def __str__(self):
        return self.nomRaisonSocial


class RaisonSociale(models.Model):
    nomEntreprise    = models.CharField(max_length=200, verbose_name='Nom de l\'entreprise')
    secteur          = models.CharField(max_length=100, blank=True, verbose_name='Secteur d\'activité')
    typeRaisonSocial = models.ForeignKey(
        TypeRaisonSociale,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='entreprises',
        verbose_name='Forme juridique',
    )

    class Meta:
        ordering = ['nomEntreprise']
        verbose_name = 'Raison sociale'
        verbose_name_plural = 'Raisons sociales'

    def __str__(self):
        return self.nomEntreprise


class Poste(models.Model):
    nomPoste = models.CharField(max_length=200, verbose_name='Intitulé du poste')
    domaine  = models.CharField(max_length=100, blank=True, verbose_name='Domaine')

    class Meta:
        ordering = ['domaine', 'nomPoste']
        verbose_name = 'Poste / Métier'
        verbose_name_plural = 'Postes / Métiers'

    def __str__(self):
        return self.nomPoste


class Niveau(models.Model):
    TYPE_LANGUE     = 'langue'
    TYPE_COMPETENCE = 'competence'
    TYPE_CHOICES = [
        (TYPE_LANGUE,     'Langue'),
        (TYPE_COMPETENCE, 'Compétence'),
    ]

    type      = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name='Catégorie de niveau')
    nomNiveau = models.CharField(max_length=100, verbose_name='Code / nom du niveau')
    libelle   = models.CharField(max_length=100, blank=True, verbose_name='Libellé')
    nbEtoiles = models.PositiveSmallIntegerField(default=0, verbose_name='Nombre d\'étoiles (1-5)')
    ordre     = models.PositiveSmallIntegerField(default=0, verbose_name='Ordre d\'affichage')

    class Meta:
        ordering = ['type', 'ordre', 'nomNiveau']
        verbose_name = 'Niveau'
        verbose_name_plural = 'Niveaux'

    def __str__(self):
        suffixe = self.libelle if self.libelle else (f"{self.nbEtoiles}★" if self.nbEtoiles else '')
        return f"[{self.get_type_display()}] {self.nomNiveau} — {suffixe}" if suffixe else f"[{self.get_type_display()}] {self.nomNiveau}"


class Diplome(models.Model):
    nomDiplome = models.CharField(max_length=200, verbose_name='Intitulé du diplôme')
    domaine    = models.CharField(max_length=100, blank=True, verbose_name='Domaine')

    class Meta:
        ordering = ['domaine', 'nomDiplome']
        verbose_name = 'Diplôme'
        verbose_name_plural = 'Diplômes'

    def __str__(self):
        return self.nomDiplome


class NiveauEtude(models.Model):
    nomNiveau = models.CharField(max_length=100, verbose_name='Niveau d\'étude')
    ordre     = models.PositiveSmallIntegerField(default=0, verbose_name='Ordre d\'affichage')

    class Meta:
        ordering = ['ordre', 'nomNiveau']
        verbose_name = 'Niveau d\'étude'
        verbose_name_plural = 'Niveaux d\'étude'

    def __str__(self):
        return self.nomNiveau


class Certificat(models.Model):
    nomCertificat = models.CharField(max_length=200, verbose_name='Intitulé du certificat')
    organisme     = models.CharField(max_length=150, blank=True, verbose_name='Organisme certificateur')
    domaine       = models.CharField(max_length=100, blank=True, verbose_name='Domaine')

    class Meta:
        ordering = ['domaine', 'nomCertificat']
        verbose_name = 'Certificat'
        verbose_name_plural = 'Certificats'

    def __str__(self):
        return self.nomCertificat


class Domaine(models.Model):
    nomDomaine  = models.CharField(max_length=150, unique=True, verbose_name='Nom du domaine')
    description = models.CharField(max_length=255, blank=True, verbose_name='Description')

    class Meta:
        ordering = ['nomDomaine']
        verbose_name = 'Domaine'
        verbose_name_plural = 'Domaines'

    def __str__(self):
        return self.nomDomaine


class SecteurActivite(models.Model):
    nomSecteur  = models.CharField(max_length=150, unique=True, verbose_name="Nom du secteur d'activité")
    description = models.CharField(max_length=255, blank=True, verbose_name='Description')

    class Meta:
        ordering = ['nomSecteur']
        verbose_name = "Secteur d'activité"
        verbose_name_plural = "Secteurs d'activité"

    def __str__(self):
        return self.nomSecteur


# ══════════════════════════════════════════════════════════════════════════════
# Tables de référence (énumérations métier persistées en base)
# ══════════════════════════════════════════════════════════════════════════════

class Sexe(models.Model):
    sexe = models.CharField(max_length=50, unique=True, verbose_name='Sexe')

    class Meta:
        ordering = ['sexe']
        verbose_name = 'Sexe'
        verbose_name_plural = 'Sexes'

    def __str__(self):
        return self.sexe


class Role(models.Model):
    libelle = models.CharField(max_length=255, unique=True, verbose_name='Libellé du rôle')

    class Meta:
        ordering = ['libelle']
        verbose_name = 'Rôle'
        verbose_name_plural = 'Rôles'

    def __str__(self):
        return self.libelle


class StatutCompte(models.Model):
    libelle = models.CharField(max_length=255, unique=True, verbose_name='Libellé du statut')

    class Meta:
        ordering = ['libelle']
        verbose_name = 'Statut de compte'
        verbose_name_plural = 'Statuts de compte'

    def __str__(self):
        return self.libelle


class TypeMobilite(models.Model):
    libelle = models.CharField(max_length=255, unique=True, verbose_name='Libellé de la mobilité')

    class Meta:
        ordering = ['libelle']
        verbose_name = 'Type de mobilité'
        verbose_name_plural = 'Types de mobilité'

    def __str__(self):
        return self.libelle


# ══════════════════════════════════════════════════════════════════════════════
# Référentiels spécifiques aux offres d'emploi
# ══════════════════════════════════════════════════════════════════════════════

class ModeTravail(models.Model):
    libelle = models.CharField(max_length=255, unique=True, verbose_name='Libellé du mode de travail')

    class Meta:
        ordering = ['libelle']
        verbose_name = 'Mode de travail'
        verbose_name_plural = 'Modes de travail'

    def __str__(self):
        return self.libelle


class TypeEntretien(models.Model):
    """Référentiel des types d'entretien (RH, Technique, Manager, Final…)."""
    code    = models.CharField(max_length=30, unique=True, verbose_name='Code')
    libelle = models.CharField(max_length=255, unique=True, verbose_name='Libellé')
    icone   = models.CharField(max_length=10, blank=True, default='', verbose_name='Icône (emoji)')
    ordre   = models.PositiveIntegerField(default=0, verbose_name='Ordre d\'affichage')

    class Meta:
        ordering = ['ordre', 'libelle']
        verbose_name = 'Type d\'entretien'
        verbose_name_plural = 'Types d\'entretien'

    def __str__(self):
        return self.libelle


class ModeEntretien(models.Model):
    """Référentiel des modes d'entretien (Présentiel, Visio, Téléphonique…)."""
    code    = models.CharField(max_length=30, unique=True, verbose_name='Code')
    libelle = models.CharField(max_length=255, unique=True, verbose_name='Libellé')
    icone   = models.CharField(max_length=10, blank=True, default='', verbose_name='Icône (emoji)')
    ordre   = models.PositiveIntegerField(default=0, verbose_name='Ordre d\'affichage')

    class Meta:
        ordering = ['ordre', 'libelle']
        verbose_name = 'Mode d\'entretien'
        verbose_name_plural = 'Modes d\'entretien'

    def __str__(self):
        return self.libelle


class Contrat(models.Model):
    libelle = models.CharField(max_length=255, unique=True, verbose_name='Libellé du contrat')

    class Meta:
        ordering = ['libelle']
        verbose_name = 'Type de contrat'
        verbose_name_plural = 'Types de contrat'

    def __str__(self):
        return self.libelle


class AnneesExperience(models.Model):
    libelle = models.CharField(max_length=255, unique=True, verbose_name="Libellé d'expérience")
    ordre   = models.PositiveSmallIntegerField(default=0, verbose_name="Ordre d'affichage")

    class Meta:
        ordering = ['ordre', 'libelle']
        verbose_name = "Années d'expérience"
        verbose_name_plural = "Années d'expérience"

    def __str__(self):
        return self.libelle


class Devise(models.Model):
    libelle = models.CharField(max_length=20, unique=True, verbose_name='Libellé / code de la devise')
    codeISO = models.CharField(max_length=10, blank=True, default='', verbose_name='Code ISO 4217')
    symbole = models.CharField(max_length=5,  blank=True, default='', verbose_name='Symbole')

    class Meta:
        ordering = ['libelle']
        verbose_name = 'Devise'
        verbose_name_plural = 'Devises'

    def __str__(self):
        return self.libelle


class ReseauSocial(models.Model):
    """Référentiel des réseaux sociaux et plateformes professionnelles.

    L'icône est rendue côté front via le CDN simple-icons : un slug
    (ex. 'linkedin', 'github') suffit pour récupérer le SVG officiel à
    `https://cdn.simpleicons.org/<slug>` (ou `<slug>/<couleur>` pour
    forcer la couleur de marque).
    """
    libelle = models.CharField(max_length=80, unique=True, verbose_name='Nom du réseau')
    slug    = models.SlugField(
        max_length=80, unique=True,
        verbose_name='Identifiant simple-icons',
        help_text="Slug officiel sur simpleicons.org (ex. 'linkedin', 'github', 'x').",
    )
    couleur = models.CharField(
        max_length=7, blank=True, default='',
        verbose_name='Couleur de marque (hex)',
        help_text="Code couleur hexadécimal sans #, ex. '0A66C2'. Vide = couleur par défaut.",
    )
    ordre   = models.PositiveSmallIntegerField(default=0, verbose_name="Ordre d'affichage")
    actif   = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        ordering = ['ordre', 'libelle']
        verbose_name = 'Réseau social'
        verbose_name_plural = 'Réseaux sociaux'

    _BI_MAP = {
        'linkedin':      'linkedin',
        'github':        'github',
        'gitlab':        'git',
        'googlechrome':  'globe2',
        'x':             'twitter-x',
        'twitter':       'twitter',
        'youtube':       'youtube',
        'instagram':     'instagram',
        'facebook':      'facebook',
        'behance':       'behance',
        'dribbble':      'dribbble',
        'medium':        'medium',
        'stackoverflow': 'stack-overflow',
        'whatsapp':      'whatsapp',
        'telegram':      'telegram',
        'tiktok':        'tiktok',
        'pinterest':     'pinterest',
        'slack':         'slack',
        'discord':       'discord',
        'spotify':       'spotify',
        'twitch':        'twitch',
    }

    @property
    def bi_class(self):
        """Classe Bootstrap Icons (ex. 'bi-linkedin') pour afficher l'icône sans dépendre du CDN simpleicons."""
        return 'bi-' + self._BI_MAP.get(self.slug, 'link-45deg')

    @property
    def couleur_hex(self):
        """Couleur CSS avec # (ex. '#0A66C2'). Vide → '#333333' par défaut."""
        return ('#' + self.couleur) if self.couleur else '#333333'

    def __str__(self):
        return self.libelle


# ══════════════════════════════════════════════════════════════════════════════
# Utilisateur — modèle d'authentification (AUTH_USER_MODEL)
# ══════════════════════════════════════════════════════════════════════════════


class TypeCompte(models.TextChoices):
    CANDIDAT  = 'CANDIDAT',  'Candidat'
    RECRUTEUR = 'RECRUTEUR', 'Recruteur'


class UtilisateurManager(BaseUserManager):

    def create_user(self, email, type_compte=None, password=None, **extra):
        if not email:
            raise ValueError("L'adresse email est obligatoire.")
        email = self.normalize_email(email)
        user = self.model(email=email, type_compte=type_compte or '', **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        return self.create_user(email, type_compte='', password=password, **extra)


class Utilisateur(AbstractBaseUser, PermissionsMixin):
    """Compte d'authentification unique pour Candidat et Recruteur.

    Remplace l'ancien modèle abstrait. Un email = un seul type de compte.
    L'Entreprise garde son propre système d'auth (session-based).
    """

    email        = models.EmailField('Email', unique=True)
    type_compte  = models.CharField(
        'Type de compte', max_length=10,
        choices=TypeCompte.choices, blank=True, default='',
    )
    is_active    = models.BooleanField('Actif', default=True)
    is_staff     = models.BooleanField('Staff', default=False)
    date_joined  = models.DateTimeField("Date d'inscription", auto_now_add=True)

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = []

    objects = UtilisateurManager()

    class Meta:
        verbose_name        = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'

    def __str__(self):
        return self.email


class Administrateur(Utilisateur):
    """Proxy pour afficher les superusers séparément dans l'admin Django."""
    class Meta:
        proxy = True
        verbose_name = 'Administrateur'
        verbose_name_plural = 'Administrateurs'


