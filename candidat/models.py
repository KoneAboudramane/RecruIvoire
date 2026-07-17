import random
import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from referentiel.models import Utilisateur, TypeMobilite, TypePermis, SecteurActivite
from recrutement.storages import get_public_storage, get_kyc_storage


class Sexe(models.TextChoices):
    """Conservé pour compatibilité avec l'ancien champ InformationPersonnelle.sexe.
    À terme, remplacé par la FK Utilisateur.sexe → referentiel.Sexe."""
    HOMME        = 'HOMME',        _('Homme')
    FEMME        = 'FEMME',        _('Femme')
    NON_SPECIFIE = 'NON_SPECIFIE', _('Non spécifié')


class Mobilite(models.TextChoices):
    """Conservé pour compatibilité avec l'ancien champ Candidat.mobilite.
    À terme, remplacé par la FK Candidat.typeMobilite → referentiel.TypeMobilite."""
    LOCAL         = 'LOCAL',         _('Local')
    REGIONAL      = 'REGIONAL',      _('Régional')
    NATIONAL      = 'NATIONAL',      _('National')
    INTERNATIONAL = 'INTERNATIONAL', _('International')
    REMOTE_ONLY   = 'REMOTE_ONLY',   _('Télétravail uniquement')


class InformationPersonnelle(models.Model):
    """Informations d'identité et de contact du candidat."""

    nom           = models.CharField(max_length=150, verbose_name='Nom')
    prenom        = models.CharField(max_length=150, verbose_name='Prénom')
    dateNaissance = models.DateField(null=True, blank=True, verbose_name='Date de naissance')
    sexe          = models.CharField(
        max_length=15, choices=Sexe.choices, default=Sexe.NON_SPECIFIE,
        verbose_name='Sexe',
    )
    nationalite = models.CharField(max_length=100, blank=True, verbose_name='Nationalité')
    photoProfil = models.ImageField(
        upload_to='candidat/photos/', storage=get_public_storage, blank=True, null=True,
        verbose_name='Photo de profil',
    )
    email     = models.EmailField(unique=True, verbose_name='Email')
    telephone = models.CharField(max_length=20, blank=True, verbose_name='Téléphone')
    adresse    = models.CharField(max_length=255, blank=True, verbose_name='Adresse')
    codePostal = models.CharField(max_length=20,  blank=True, verbose_name='Code postal')
    pays       = models.CharField(max_length=100, blank=True, verbose_name='Pays')
    ville      = models.CharField(max_length=100, blank=True, verbose_name='Ville')
    permis     = models.CharField(max_length=50,  blank=True, verbose_name='Permis de conduire')

    class Meta:
        verbose_name        = 'Information personnelle'
        verbose_name_plural = 'Informations personnelles'

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.email})"


class Candidat(Utilisateur):
    """Profil candidat — hérite de Utilisateur (multi-table inheritance).

    L'authentification (email, password, type_compte) est gérée par
    Utilisateur (AUTH_USER_MODEL). Les champs ci-dessous sont propres
    au profil candidat.
    """

    # ── Champs d'identité propres au candidat ────────────────────────────
    nom               = models.CharField('Nom',           max_length=255, blank=True, default='')
    prenom            = models.CharField('Prénom',        max_length=255, blank=True, default='')
    dateNaissance     = models.DateField('Date de naissance', null=True, blank=True)
    photoProfil       = models.ImageField('Photo de profil',
                                          upload_to='users/photos/',
                                          storage=get_public_storage,
                                          blank=True, null=True)
    telephone         = models.CharField('Téléphone',     max_length=20,  blank=True, default='')
    adresse           = models.CharField('Adresse',       max_length=255, blank=True, default='')
    derniereConnexion = models.DateTimeField('Dernière connexion', null=True, blank=True)
    emailVerifie      = models.BooleanField('Email vérifié', default=False)
    sexe              = models.ForeignKey(
        'referentiel.Sexe', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='Sexe',
    )

    informationPersonnelle = models.OneToOneField(
        'InformationPersonnelle',
        on_delete=models.CASCADE,
        related_name='candidat',
        null=True, blank=True,
        verbose_name='Informations personnelles (legacy)',
        help_text='Champ transitoire — sera supprimé après migration des données.',
    )

    # ── Profil professionnel (champs propres au candidat) ────────────────────
    titreProfessionnel = models.CharField(max_length=255, blank=True, verbose_name='Titre professionnel')
    biographie         = models.TextField(
        blank=True, verbose_name='Biographie (portfolio)',
        help_text="Texte d'auto-présentation affiché sur le portfolio public.",
    )
    profilCV           = models.TextField(
        blank=True, verbose_name='Profil CV',
        help_text="Résumé professionnel pré-rempli dans l'éditeur CV. Indépendant de la biographie portfolio.",
    )
    datePremierEmploi  = models.IntegerField(
        null=True, blank=True,
        verbose_name='Année du premier emploi',
        help_text='Ex : 2018',
    )
    # ── Secteur d'activité (legacy CharField + FK référentiel) ───────────────
    # `secteurActivite` (CharField) est conservé pour rétro-compat.
    # `secteurActiviteRef` (FK) est le champ actif utilisé par les formulaires.
    secteurActivite    = models.CharField(
        max_length=100, blank=True,
        verbose_name="Secteur d'activité (legacy)",
    )
    secteurActiviteRef = models.ForeignKey(
        SecteurActivite, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='candidats',
        verbose_name="Secteur d'activité",
    )

    # ── Mobilité & permis (FK / M2M sur le référentiel) ──────────────────────
    typeMobilite = models.ForeignKey(
        TypeMobilite, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='candidats',
        verbose_name='Type de mobilité',
    )
    typePermis = models.ManyToManyField(
        TypePermis, blank=True, related_name='candidats',
        verbose_name='Permis de conduire',
    )

    # ── Réinitialisation MDP (token legacy spécifique candidat) ──────────────
    tokenReset = models.BigIntegerField(null=True, blank=True, verbose_name='Token de réinitialisation')

    # ── Embedding ATS (cache) ────────────────────────────────────────────────
    # JSONField (liste de 384 floats) plutôt que VectorField/pgvector : l'extension
    # serveur PostgreSQL "vector" n'est pas disponible sur l'hébergement O2switch
    # (PostgreSQL 9.6, pgvector exige 13+). Le calcul de similarité cosinus se fait
    # déjà en Python pur côté matching_semantic.py, donc aucun impact fonctionnel.
    embedding = models.JSONField('Embedding ATS', null=True, blank=True, editable=False)
    embedding_updated = models.DateTimeField('Embedding mis à jour le', null=True, blank=True, editable=False)

    # ── Visibilité & personnalisation portfolio ──────────────────────────────
    portfolioPublic  = models.BooleanField(
        default=True, verbose_name='Portfolio public',
        help_text='Si décoché, le portfolio est privé (404 pour les visiteurs).',
    )
    tokenPortfolioPartage = models.UUIDField(
        null=True, blank=True, default=None, editable=False, unique=True,
        verbose_name='Token de partage portfolio',
        help_text='Null = aucun lien actif.',
    )
    tokenPortfolioExpiration = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Expiration du lien de partage',
        help_text='Null = lien permanent.',
    )
    sloganPortfolio  = models.CharField(max_length=200, blank=True, verbose_name='Slogan portfolio')
    couleurPortfolio = models.CharField(
        max_length=7, blank=True, default='',
        verbose_name='Couleur accent portfolio',
        help_text="Surcharge personnelle. Si vide, on utilise la couleur du modèle choisi.",
    )
    portfolioModele  = models.ForeignKey(
        'Portfolio',
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name='candidats',
        verbose_name='Modèle de portfolio choisi',
    )
    # Toggles d'affichage des sections du portfolio public (indépendants
    # des toggles CV portés par `rubriques`). Forme : `{'showProjets': True,
    # 'showAbout': True, 'showExperiences': True, …}`. Les clés absentes du
    # dict tombent sur la valeur par défaut renvoyée par
    # `get_portfolio_params()`. Toujours les lire via cette méthode pour
    # garantir des defaults cohérents.
    paramsPortfolio = models.JSONField(
        default=dict, blank=True,
        verbose_name='Paramètres du portfolio',
        help_text='Toggles d\'affichage des sections du portfolio public.',
    )

    # ── Préférences de notifications ─────────────────────────────────────────
    notificationsInApp = models.BooleanField(
        default=True,
        verbose_name="Recevoir les notifications sur le site",
        help_text="Si désactivé, le badge de la cloche est masqué et aucune nouvelle notification n'est créée.",
    )
    notificationsOffresEmail = models.BooleanField(
        default=False,
        verbose_name="Recevoir les notifications par email",
        help_text="Si activé, chaque notification reçue sur le site est aussi envoyée par email.",
    )
    recommandationsActives = models.BooleanField(
        default=True,
        verbose_name="Recommandations automatiques actives",
        help_text="Si activé, notre IA analyse votre profil et vous suggère automatiquement les offres les plus pertinentes.",
    )
    alertesActives = models.BooleanField(
        default=True,
        verbose_name="Alertes emploi actives",
        help_text="Si activé, vous êtes notifié dès qu'une offre correspond à vos alertes personnalisées.",
    )


    # ── Mobilité ancienne (TextChoices) — conservée tant que typeMobilite
    #    n'est pas peuplé à 100 % ; sera supprimée en Phase B sub-step 6.
    mobilite     = models.CharField(
        max_length=20, choices=Mobilite.choices, default=Mobilite.LOCAL,
        blank=True, verbose_name='Mobilité (legacy)',
    )
    # FK vers referentiel.Contrat — un seul type de contrat recherché
    # à la fois (CDI ou CDD ou Freelance…), pas un panier.
    typeContratRecherche = models.ForeignKey(
        'referentiel.Contrat',
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name='candidats_recherchant',
        verbose_name='Type de contrat recherché',
    )

    # ── Rubriques CV (JSON — même structure que l'éditeur CV) ───────────────
    rubriques = models.JSONField(default=dict, blank=True, verbose_name='Rubriques CV')

    class Meta:
        verbose_name        = 'Candidat'
        verbose_name_plural = 'Candidats'
        ordering            = ['-date_joined']

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.email or 'sans email'})"

    def verifier_mot_de_passe(self, raw_password):
        return self.check_password(raw_password)

    def changerMotDePasse(self, ancien, nouveau):
        if self.check_password(ancien):
            self.set_password(nouveau)
            self.save()
            return True
        return False

    # ── Helpers portfolio ───────────────────────────────────────────────
    PORTFOLIO_DEFAULTS = {
        'showProjets'    : True,
        'showAbout'      : True,
        'showExperiences': True,
        'showFormations' : True,
        'showCompetences': True,
        'showLangues'    : True,
        'showBenevs'     : True,
        'showInterets'   : True,
        'showContact'    : True,
    }

    def get_portfolio_params(self):
        """Toggles d'affichage des sections du portfolio.

        Fusionne les valeurs persistées dans `paramsPortfolio` (JSON)
        avec les défauts déclarés dans `PORTFOLIO_DEFAULTS`. Toute clé
        absente tombe sur la valeur par défaut → ajouter une nouvelle
        section ne casse pas les portfolios existants.
        """
        params = dict(self.PORTFOLIO_DEFAULTS)
        if isinstance(self.paramsPortfolio, dict):
            for k, v in self.paramsPortfolio.items():
                if k in params:
                    params[k] = bool(v)
        return params


class LienCandidat(models.Model):
    """Lien social ou professionnel d'un candidat (LinkedIn, GitHub, site web…).

    Le réseau est choisi dans le référentiel `ReseauSocial`,
    qui fournit le libellé, l'icône (slug simple-icons) et la couleur.
    """
    candidat = models.ForeignKey(
        Candidat, on_delete=models.CASCADE,
        related_name='liensSociaux', verbose_name='Candidat',
    )
    reseau   = models.ForeignKey(
        'referentiel.ReseauSocial', on_delete=models.PROTECT,
        related_name='liens', verbose_name='Réseau',
    )
    url      = models.URLField(max_length=500, verbose_name='URL')
    ordre    = models.PositiveSmallIntegerField(default=0, verbose_name="Ordre d'affichage")

    class Meta:
        ordering            = ['ordre', 'id']
        verbose_name        = 'Lien social'
        verbose_name_plural = 'Liens sociaux'
        constraints         = [
            models.UniqueConstraint(
                fields=['candidat', 'reseau'],
                name='unique_lien_candidat_reseau',
            ),
        ]

    def __str__(self):
        return f'{self.candidat} — {self.reseau}'


class ModeleCV(models.Model):
    """Modèle de CV géré par l'administrateur."""

    CATEGORIES = [
        ('Classique',   _('Classique')),
        ('Moderne',     _('Moderne')),
        ('Minimaliste', _('Minimaliste')),
        ('Élégant',     _('Élégant')),
        ('Créatif',     _('Créatif')),
    ]

    SECTEURS = [
        ('Tous secteurs',     _('Tous secteurs')),
        ('Tech & IT',         _('Tech & IT')),
        ('Finance & Banque',  _('Finance & Banque')),
        ('Design & Art',      _('Design & Art')),
        ('Cadres & Managers', _('Cadres & Managers')),
        ('Santé',             _('Santé')),
        ('Marketing',         _('Marketing')),
        ('Droit',             _('Droit')),
        ('BTP & Industrie',   _('BTP & Industrie')),
        ('Éducation',         _('Éducation')),
        ('Commerce',          _('Commerce')),
        ('Direction',         _('Direction')),
    ]

    COULEURS = [
        ('#F77F00', _('Orange')),
        ('#009A44', _('Vert')),
        ('#1a1a2e', _('Bleu Marine')),
        ('#ffffff', _('Blanc')),
        ('#2563EB', _('Bleu')),
        ('#06B6D4', _('Cyan')),
        ('#0D1117', _('Noir')),
        ('#E85D4A', _('Rouge Corail')),
        ('#2A9D8F', _('Vert Teal')),
        ('#003366', _('Bleu Nuit')),
        ('#1565C0', _('Bleu Royal')),
        ('#1a237e', _('Bleu Indigo')),
        ('#0D1F3C', _('Marine Foncé')),
        ('#1F2937', _('Gris Anthracite')),
        ('#C9A227', _('Or')),
        ('#E9C46A', _('Jaune Sable')),
    ]

    nom       = models.CharField(
        max_length=100,
        verbose_name='Nom du modèle',
        help_text='Ex : Classique Orange, Tech Sidebar…',
    )
    fichier   = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Fichier HTML',
        help_text='Nom du fichier sans extension dans candidat/templates/candidat/cv/modeles/ (ex: orange-plain)',
    )
    apercu    = models.ImageField(
        upload_to='modeles_cv/apercu/',
        storage=get_public_storage,
        blank=True,
        null=True,
        verbose_name="Image d'aperçu",
        help_text="Capture d'écran du rendu du modèle (format recommandé : 794×1123 px)",
    )
    categorie = models.CharField(
        max_length=50,
        choices=CATEGORIES,
        default='Classique',
        verbose_name='Catégorie',
    )
    secteur   = models.CharField(
        max_length=100,
        default='Tous secteurs',
        verbose_name="Secteur d'activité",
        help_text='Choisissez un secteur dans la liste ou saisissez le vôtre.',
    )
    couleur   = models.CharField(
        max_length=7,
        choices=COULEURS,
        default='#F77F00',
        verbose_name='Couleur principale',
        help_text='Utilisée pour la carte de prévisualisation',
    )
    premium   = models.BooleanField(
        default=False,
        verbose_name='Modèle Premium',
        help_text='Si coché, réservé aux abonnés Premium',
    )
    actif     = models.BooleanField(
        default=True,
        verbose_name='Actif',
        help_text='Décocher pour masquer ce modèle sans le supprimer',
    )
    ordre     = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Ordre d\'affichage',
        help_text='Les modèles sont triés par ordre croissant',
    )

    class Meta:
        verbose_name        = 'Modèle de CV'
        verbose_name_plural = 'Modèles de CV'
        ordering            = ['ordre', 'nom']

    def __str__(self):
        statut = 'Premium' if self.premium else 'Gratuit'
        return f"{self.nom} [{statut}]"


class Portfolio(models.Model):
    """Modèle de portfolio (template) géré par l'administrateur.

    Catalogue de thèmes parmi lesquels le candidat choisit pour personnaliser
    sa page portfolio publique. Mêmes conventions que `ModeleCV` :
      - `fichier` pointe vers `templates/candidat/portfolio/modeles/<fichier>.html`
      - `apercu` = capture du rendu, affichée dans la galerie de sélection
      - `couleurPrincipale` = accent par défaut (le candidat peut surcharger
        via `Candidat.couleurPortfolio`)
    """

    CATEGORIES = [
        ('Moderne',     _('Moderne')),
        ('Minimaliste', _('Minimaliste')),
        ('Créatif',     _('Créatif')),
        ('Élégant',     _('Élégant')),
        ('Sombre',      _('Sombre')),
    ]

    # Réutilise la même palette que ModeleCV pour la cohérence visuelle admin.
    COULEURS = ModeleCV.COULEURS

    nom               = models.CharField(
        max_length=100,
        verbose_name='Nom du modèle',
        help_text='Ex : Orange Vibrant, Minimaliste Sombre…',
    )
    fichier           = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Fichier HTML',
        help_text='Nom du fichier sans extension dans candidat/templates/candidat/portfolio/modeles/',
    )
    apercu            = models.ImageField(
        upload_to='portfolios/apercu/', storage=get_public_storage,
        blank=True, null=True,
        verbose_name="Image d'aperçu",
        help_text='Capture du rendu (recommandé : 1280×720 px).',
    )
    categorie         = models.CharField(
        max_length=50,
        choices=CATEGORIES,
        default='Moderne',
        verbose_name='Catégorie',
    )
    couleurPrincipale = models.CharField(
        max_length=7,
        choices=COULEURS,
        default='#F77F00',
        verbose_name='Couleur principale',
        help_text="Accent par défaut. Le candidat peut le surcharger via Candidat.couleurPortfolio.",
    )
    description       = models.CharField(
        max_length=255,
        blank=True, default='',
        verbose_name='Description courte',
        help_text='Phrase d\'accroche affichée sur la carte de prévisualisation.',
    )
    premium           = models.BooleanField(
        default=False,
        verbose_name='Modèle Premium',
        help_text='Si coché, réservé aux abonnés Premium.',
    )
    actif             = models.BooleanField(
        default=True,
        verbose_name='Actif',
        help_text='Décocher pour masquer ce modèle sans le supprimer.',
    )
    ordre             = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Ordre d'affichage",
        help_text='Les modèles sont triés par ordre croissant.',
    )
    dateCreation      = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Date de création',
    )

    class Meta:
        verbose_name        = 'Modèle de portfolio'
        verbose_name_plural = 'Modèles de portfolio'
        ordering            = ['ordre', 'nom']

    def __str__(self):
        statut = 'Premium' if self.premium else 'Gratuit'
        return f'{self.nom} [{statut}]'


class ModeleLettre(models.Model):
    """Modèle de lettre de motivation géré par l'administrateur."""

    CATEGORIES = [
        ('Classique',   _('Classique')),
        ('Moderne',     _('Moderne')),
        ('Minimaliste', _('Minimaliste')),
        ('Élégant',     _('Élégant')),
        ('Créatif',     _('Créatif')),
    ]

    FAMILLES = [
        ('classique', _('Classique — bloc unique')),
        ('sidebar',   _('Bandeau latéral persistant')),
        ('accroche',  _('Accroche mise en avant')),
        ('carte',     _('Carte encadrée')),
    ]

    COULEURS = [
        ('#F77F00', _('Orange')),
        ('#009A44', _('Vert')),
        ('#1a1a2e', _('Bleu Marine')),
        ('#ffffff', _('Blanc')),
        ('#2563EB', _('Bleu')),
        ('#1F2937', _('Gris Anthracite')),
        ('#C9A227', _('Or')),
    ]

    nom       = models.CharField(
        max_length=100,
        verbose_name='Nom du modèle',
        help_text='Ex : Classique, Orange Pro, Executive…',
    )
    slug      = models.SlugField(
        unique=True,
        verbose_name='Identifiant (slug)',
        help_text='Correspond au nom du fichier HTML dans lettreMo/modeles/ (ex: orange-pro)',
    )
    apercu    = models.ImageField(
        upload_to='modeles_lettre/apercu/', storage=get_public_storage,
        blank=True, null=True,
        verbose_name="Image d'aperçu",
        help_text="Capture A4 du rendu (794×1123 px recommandé)",
    )
    categorie = models.CharField(
        max_length=50, choices=CATEGORIES, default='Classique',
        verbose_name='Catégorie',
    )
    famille   = models.CharField(
        max_length=20, choices=FAMILLES, default='classique',
        verbose_name='Famille de mise en page',
        help_text="Structure HTML utilisée par lettre_render.html (voir bloc {% if modele.famille == ... %}).",
    )
    couleur   = models.CharField(
        max_length=7, choices=COULEURS, default='#1a1a2e',
        verbose_name='Couleur principale',
        help_text='Utilisée pour la carte de prévisualisation',
    )
    premium   = models.BooleanField(default=False, verbose_name='Modèle Premium')
    actif     = models.BooleanField(default=True,  verbose_name='Actif')
    ordre     = models.PositiveSmallIntegerField(
        default=0, verbose_name="Ordre d'affichage",
    )

    class Meta:
        verbose_name        = 'Modèle de lettre de motivation'
        verbose_name_plural = 'Modèles de lettre de motivation'
        ordering            = ['ordre', 'nom']

    def __str__(self):
        return f"{self.nom} ({'Premium' if self.premium else 'Gratuit'})"


class LogoSite(models.Model):
    """
    Identité visuelle du site — singleton (une seule instance active).
    L'administrateur peut définir un nom, un slogan, une image logo
    et choisir comment les afficher : texte seul, image seule, ou les deux.
    """

    MODE_TEXTE    = 'texte'
    MODE_IMAGE    = 'image'
    MODE_LES_DEUX = 'les_deux'
    MODE_CHOICES  = [
        (MODE_TEXTE,    'Texte uniquement'),
        (MODE_IMAGE,    'Image uniquement'),
        (MODE_LES_DEUX, 'Image + Texte'),
    ]

    nom_site          = models.CharField(
        max_length=100, default='RecrutePro',
        verbose_name='Nom du site',
        help_text='Utilisé dans la navbar, le footer et les onglets du navigateur.',
    )
    slogan            = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Slogan',
        help_text='Courte accroche affichée sous le logo (optionnel).',
    )
    logo_image        = models.ImageField(
        upload_to='site/logo/', storage=get_public_storage,
        blank=True, null=True,
        verbose_name='Image du logo',
        help_text='PNG transparent ou SVG recommandé. Hauteur idéale : 40–60 px.',
    )
    mode_affichage    = models.CharField(
        max_length=10, choices=MODE_CHOICES, default=MODE_LES_DEUX,
        verbose_name="Mode d'affichage",
        help_text='Choisissez ce qui s\'affiche dans la navbar.',
    )
    actif             = models.BooleanField(
        default=True, verbose_name='Configuration active',
        help_text='Une seule configuration doit être active à la fois.',
    )
    date_modification = models.DateTimeField(auto_now=True, verbose_name='Dernière modification')

    class Meta:
        verbose_name        = 'Logo & identité du site'
        verbose_name_plural = 'Logo & identité du site'

    def __str__(self):
        return f"{self.nom_site} ({'actif' if self.actif else 'inactif'})"

    # ── API publique ───────────────────────────────────────────────────────────

    @classmethod
    def get_actif(cls):
        """Retourne la config active ou un objet par défaut si aucune n'existe en base."""
        obj = cls.objects.filter(actif=True).first()
        if obj is None:
            return cls(nom_site='RecrutePro', mode_affichage=cls.MODE_TEXTE)
        return obj

    @property
    def afficher_image(self):
        return self.mode_affichage in (self.MODE_IMAGE, self.MODE_LES_DEUX) and bool(self.logo_image)

    @property
    def afficher_texte(self):
        return self.mode_affichage in (self.MODE_TEXTE, self.MODE_LES_DEUX)

    def initiales(self):
        """Retourne les 2 premières lettres du nom pour les avatars texte."""
        mots = self.nom_site.split()
        if len(mots) >= 2:
            return (mots[0][0] + mots[1][0]).upper()
        return self.nom_site[:2].upper()

    def save(self, *args, **kwargs):
        """S'il n'y a aucune instance active, active automatiquement celle-ci."""
        if self.actif:
            # Désactive les autres pour garantir le singleton actif
            LogoSite.objects.exclude(pk=self.pk).filter(actif=True).update(actif=False)
        super().save(*args, **kwargs)


class AbonneNewsletter(models.Model):
    """Abonné à la newsletter — lien de désabonnement via token UUID."""

    email               = models.EmailField(unique=True, verbose_name='Email')
    candidat            = models.OneToOneField(
        'Candidat',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='abonnement_newsletter',
        verbose_name='Candidat',
    )
    token_desabonnement = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, verbose_name='Token de désabonnement')
    date_inscription    = models.DateTimeField(auto_now_add=True, verbose_name="Date d'inscription")
    actif               = models.BooleanField(default=True, verbose_name='Actif')

    # Préférences générales (tous les abonnés)
    offres_semaine      = models.BooleanField(default=False, verbose_name='Offres de la semaine')
    conseils            = models.BooleanField(default=False, verbose_name='Conseils & astuces')
    actualites          = models.BooleanField(default=False, verbose_name='Actualités de la plateforme')

    # Préférences individuelles (candidats inscrits uniquement)
    offres_perso        = models.BooleanField(default=False, verbose_name='Offres correspondant à mon profil')
    profil_consulte     = models.BooleanField(default=False, verbose_name='Quand mon profil est consulté')
    resume_candidatures = models.BooleanField(default=False, verbose_name='Résumé de mes candidatures')

    class Meta:
        verbose_name        = 'Abonné newsletter'
        verbose_name_plural = 'Abonnés newsletter'
        ordering            = ['-date_inscription']

    def __str__(self):
        return f"{self.email} ({'actif' if self.actif else 'désabonné'})"

    @property
    def a_preferences(self):
        return any([self.offres_semaine, self.conseils, self.actualites,
                    self.offres_perso, self.profil_consulte, self.resume_candidatures])


class FrequenceNewsletter(models.TextChoices):
    HEBDOMADAIRE = 'HEBDOMADAIRE', 'Hebdomadaire (1×/semaine)'
    BIMENSUEL    = 'BIMENSUEL',   'Bimensuel (2×/mois)'
    MENSUEL      = 'MENSUEL',     'Mensuel (1×/mois)'


class PlanificationNewsletter(models.Model):
    """Singleton de configuration de l'envoi automatique de la newsletter offres.

    Gère le jour, l'heure et la fréquence d'envoi.
    La commande `envoyer_newsletter_offres` lit ce modèle au démarrage et met
    à jour `derniere_execution` / `derniere_status` après chaque envoi.
    """

    active       = models.BooleanField('Activée', default=False)
    frequence    = models.CharField(
        'Fréquence', max_length=20,
        choices=FrequenceNewsletter.choices,
        default=FrequenceNewsletter.HEBDOMADAIRE,
    )
    jour_semaine = models.IntegerField(
        'Jour de la semaine', default=0,
        help_text='0 = Lundi … 6 = Dimanche (utilisé si fréquence = HEBDOMADAIRE ou BIMENSUEL).',
    )
    jour_mois    = models.IntegerField(
        'Jour du mois', default=1,
        help_text='1-28 (utilisé si fréquence = MENSUEL).',
    )
    heure        = models.TimeField("Heure d'envoi", default='08:00')

    # Suivi des exécutions
    derniere_execution  = models.DateTimeField('Dernière exécution', null=True, blank=True)
    derniere_status     = models.CharField(
        'Dernier statut', max_length=20, blank=True, default='',
        help_text='ok / error / running',
    )
    derniere_message    = models.TextField('Message dernière exécution', blank=True, default='')
    prochaine_execution = models.DateTimeField('Prochaine exécution', null=True, blank=True)
    date_modification   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Planification newsletter'
        verbose_name_plural = 'Planification newsletter'

    def __str__(self):
        etat = 'active' if self.active else 'inactive'
        return f"Planification newsletter ({etat}, {self.get_frequence_display()})"

    @classmethod
    def singleton(cls) -> 'PlanificationNewsletter':
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def calculer_prochaine_execution(self):
        """Calcule la prochaine date d'envoi à partir de maintenant."""
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now()
        JOURS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

        if self.frequence == FrequenceNewsletter.MENSUEL:
            # Prochain mois au jour_mois
            import calendar
            annee, mois = now.year, now.month
            max_jours = calendar.monthrange(annee, mois)[1]
            jour = min(self.jour_mois, max_jours)
            candidate = now.replace(day=jour, hour=self.heure.hour,
                                    minute=self.heure.minute, second=0, microsecond=0)
            if candidate <= now:
                mois += 1
                if mois > 12:
                    mois, annee = 1, annee + 1
                max_jours = calendar.monthrange(annee, mois)[1]
                jour = min(self.jour_mois, max_jours)
                candidate = candidate.replace(year=annee, month=mois, day=jour)
            return candidate

        # HEBDOMADAIRE ou BIMENSUEL : prochain jour_semaine cible
        jours_avant = (self.jour_semaine - now.weekday()) % 7
        if jours_avant == 0:
            candidate = now.replace(hour=self.heure.hour, minute=self.heure.minute,
                                    second=0, microsecond=0)
            if candidate <= now:
                jours_avant = 7
        if jours_avant:
            candidate = (now + timedelta(days=jours_avant)).replace(
                hour=self.heure.hour, minute=self.heure.minute, second=0, microsecond=0
            )
        return candidate


class _StatutNewsletter(models.TextChoices):
    """Statut partagé par ConseilNewsletter et ActualiteNewsletter."""
    BROUILLON = 'BROUILLON', 'Brouillon'
    PLANIFIE  = 'PLANIFIE',  'Planifié'
    ENVOYE    = 'ENVOYE',    'Envoyé'


class ConseilNewsletter(models.Model):
    """Conseil ou astuce envoyé aux abonnés ayant coché `conseils`.

    Deux modes :
    - Option A : envoi immédiat depuis l'admin.
    - Option B : date_envoi_prevu définie → commande envoyer_newsletter_conseils.
    """

    # Alias pour accès depuis l'admin : ConseilNewsletter.Statut.ENVOYE
    Statut = _StatutNewsletter

    class Categorie(models.TextChoices):
        CV         = 'CV',         'CV & candidature'
        ENTRETIEN  = 'ENTRETIEN',  'Entretien'
        CARRIERE   = 'CARRIERE',   'Évolution de carrière'
        PLATEFORME = 'PLATEFORME', 'Utiliser la plateforme'

    titre             = models.CharField('Titre', max_length=200)
    contenu           = models.TextField('Contenu')
    categorie         = models.CharField(
        'Catégorie', max_length=20,
        choices=Categorie.choices, default=Categorie.CV,
    )
    statut            = models.CharField(
        'Statut', max_length=20,
        choices=_StatutNewsletter.choices, default=_StatutNewsletter.BROUILLON,
    )
    date_creation     = models.DateTimeField('Date de création', auto_now_add=True)
    date_modification = models.DateTimeField('Dernière modification', auto_now=True)
    date_envoi_prevu  = models.DateTimeField(
        "Date d'envoi planifiée", null=True, blank=True,
        help_text="Laissez vide pour un envoi immédiat depuis l'admin.",
    )
    date_envoi_reel   = models.DateTimeField("Date d'envoi réelle", null=True, blank=True)
    nb_destinataires  = models.IntegerField('Destinataires', default=0)
    envoye_par        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        verbose_name='Envoyé par',
    )

    class Meta:
        verbose_name        = 'Conseil newsletter'
        verbose_name_plural = 'Conseils newsletter'
        ordering            = ['-date_creation']

    def __str__(self):
        return f"[{self.get_categorie_display()}] {self.titre} — {self.get_statut_display()}"

    @property
    def est_envoye(self):
        return self.statut == _StatutNewsletter.ENVOYE

    @property
    def icone_categorie(self):
        return {
            'CV':        '📄',
            'ENTRETIEN': '🎤',
            'CARRIERE':  '🚀',
            'PLATEFORME':'💡',
        }.get(self.categorie, '📌')


class ActualiteNewsletter(models.Model):
    """Actualité de la plateforme envoyée aux abonnés ayant coché `actualites`.

    Deux modes :
    - Option A : envoi immédiat depuis l'admin.
    - Option B : date_envoi_prevu définie → commande envoyer_newsletter_actualites.
    """

    Statut = _StatutNewsletter  # Alias pour l'admin

    titre             = models.CharField('Titre', max_length=200)
    contenu           = models.TextField('Contenu')
    image             = models.ImageField(
        'Image', upload_to='newsletter/actualites/', storage=get_public_storage,
        null=True, blank=True,
        help_text="Optionnel. Recommandé : 600×300 px.",
    )
    legende_image     = models.CharField('Légende de l\'image', max_length=200, blank=True, default='')
    statut            = models.CharField(
        'Statut', max_length=20,
        choices=_StatutNewsletter.choices, default=_StatutNewsletter.BROUILLON,
    )
    date_creation     = models.DateTimeField('Date de création', auto_now_add=True)
    date_modification = models.DateTimeField('Dernière modification', auto_now=True)
    date_envoi_prevu  = models.DateTimeField(
        "Date d'envoi planifiée", null=True, blank=True,
        help_text="Laissez vide pour un envoi immédiat depuis l'admin.",
    )
    date_envoi_reel   = models.DateTimeField("Date d'envoi réelle", null=True, blank=True)
    nb_destinataires  = models.IntegerField('Destinataires', default=0)
    envoye_par        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        verbose_name='Envoyé par',
    )

    class Meta:
        verbose_name        = 'Actualité newsletter'
        verbose_name_plural = 'Actualités newsletter'
        ordering            = ['-date_creation']

    def __str__(self):
        return f"[Actualité] {self.titre} — {self.get_statut_display()}"

    @property
    def est_envoye(self):
        return self.statut == _StatutNewsletter.ENVOYE


class TokenConfirmationInscription(models.Model):
    """
    Code à 4 chiffres envoyé par email lors de l'inscription pour vérifier
    l'adresse mail du candidat (valide 10 minutes).
    """

    candidat     = models.OneToOneField(
        Candidat,
        on_delete=models.CASCADE,
        related_name='token_confirmation',
        verbose_name='Candidat',
    )
    token        = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    code         = models.CharField(max_length=4, blank=True, default='')
    dateCreation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Token de confirmation d'inscription"
        verbose_name_plural = "Tokens de confirmation d'inscription"

    def __str__(self):
        return f"Confirmation {self.token} — {self.candidat.email}"

    def est_valide(self):
        from django.utils import timezone
        from datetime import timedelta
        return (timezone.now() - self.dateCreation) < timedelta(minutes=10)

    @staticmethod
    def generer_code():
        return str(random.randint(1000, 9999))


class TokenReinitialisationMDP(models.Model):
    """Token à usage unique pour la réinitialisation du mot de passe (valide 10 minutes)."""

    METHODE_CHOICES = [('code', 'Code 5 chiffres'), ('lien', 'Lien')]

    candidat     = models.ForeignKey(Candidat, on_delete=models.CASCADE, related_name='tokens_reinitialisation')
    token        = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    code         = models.CharField(max_length=5, blank=True, default='')
    methode      = models.CharField(max_length=4, choices=METHODE_CHOICES, default='lien')
    dateCreation = models.DateTimeField(auto_now_add=True)
    utilise      = models.BooleanField(default=False)
    verifie      = models.BooleanField(default=False)

    class Meta:
        verbose_name        = 'Token réinitialisation MDP'
        verbose_name_plural = 'Tokens réinitialisation MDP'

    def __str__(self):
        return f"Token {self.token} — {self.candidat.email}"

    def est_valide(self):
        from django.utils import timezone
        from datetime import timedelta
        return not self.utilise and (timezone.now() - self.dateCreation) < timedelta(minutes=10)

    @staticmethod
    def generer_code():
        return str(random.randint(10000, 99999))


# ══════════════════════════════════════════════════════════════════════════════
# Rubriques du profil candidat — stockage relationnel
# ══════════════════════════════════════════════════════════════════════════════
# `Candidat.rubriques` (JSONField) reste utilisé par l'éditeur Alpine.js comme
# snapshot rapide. Les modèles ci-dessous sont la source de vérité relationnelle
# (admin, recherche, exports, statistiques). Synchronisation JSON↔relationnel
# dans candidat.views.api_sauvegarder_rubriques.
#
# Pattern : pour chaque champ "lookup" (diplôme, langue, poste…), on a une FK
# vers le référentiel ET un champ "libre" texte. Le frontend autorise la saisie
# libre ; le sync upserte alors la valeur dans le référentiel via get_or_create
# et garde aussi le texte original dans le champ libre (pour compat éditeur).


class Competence(models.Model):
    """Compétence déclarée par le candidat."""

    candidat            = models.ForeignKey(
        Candidat, on_delete=models.CASCADE, related_name='competences',
        verbose_name='Candidat',
    )
    typeCompetence      = models.ForeignKey(
        'referentiel.TypeCompetence', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        verbose_name='Type de compétence',
    )
    niveau              = models.ForeignKey(
        'referentiel.Niveau', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        limit_choices_to={'type': 'competence'},
        verbose_name='Niveau',
    )
    nomLibre            = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Nom (saisie libre)',
        help_text="Utilisé si typeCompetence n'est pas dans le référentiel.",
    )
    valeurEtoiles       = models.PositiveSmallIntegerField(
        default=3, verbose_name='Étoiles (1-5)',
        help_text="Valeur d'étoiles utilisée par l'éditeur (1 à 5).",
    )
    estVisiblePortfolio = models.BooleanField(default=True, verbose_name='Visible sur le portfolio')

    class Meta:
        verbose_name        = 'Compétence'
        verbose_name_plural = 'Compétences'
        ordering            = ['id']

    def __str__(self):
        if self.nomLibre:
            return self.nomLibre
        if self.typeCompetence:
            return self.typeCompetence.nomCompetence
        return f'Compétence #{self.pk}'


class CandidatLangue(models.Model):
    """Langue maîtrisée par le candidat."""

    candidat            = models.ForeignKey(
        Candidat, on_delete=models.CASCADE, related_name='languesParlees',
        verbose_name='Candidat',
    )
    langue              = models.ForeignKey(
        'referentiel.Langue', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='Langue',
    )
    niveau              = models.ForeignKey(
        'referentiel.Niveau', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        limit_choices_to={'type': 'langue'},
        verbose_name='Niveau',
    )
    nomLibre            = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='Langue (saisie libre)',
    )
    niveauCode          = models.CharField(
        max_length=10, blank=True, default='',
        verbose_name='Niveau CECRL',
        help_text="Code rapide utilisé par l'éditeur (A1…C2).",
    )
    estVisiblePortfolio = models.BooleanField(default=True, verbose_name='Visible sur le portfolio')

    class Meta:
        verbose_name        = 'Langue du candidat'
        verbose_name_plural = 'Langues des candidats'
        ordering            = ['id']

    def __str__(self):
        if self.nomLibre:
            return self.nomLibre
        if self.langue:
            return self.langue.nomLangue
        return f'Langue #{self.pk}'


class CentreInteret(models.Model):
    """Centre d'intérêt du candidat (rubrique Divers)."""

    candidat            = models.ForeignKey(
        Candidat, on_delete=models.CASCADE, related_name='centresInteret',
        verbose_name='Candidat',
    )
    typeCentreInteret   = models.ForeignKey(
        'referentiel.TypeCentreInteret', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        verbose_name="Type de centre d'intérêt",
    )
    libelleLibre        = models.CharField(
        max_length=150, blank=True, default='',
        verbose_name='Libellé (saisie libre)',
    )
    estVisiblePortfolio = models.BooleanField(default=True, verbose_name='Visible sur le portfolio')

    class Meta:
        verbose_name        = "Centre d'intérêt"
        verbose_name_plural = "Centres d'intérêt"
        ordering            = ['id']

    def __str__(self):
        if self.libelleLibre:
            return self.libelleLibre
        if self.typeCentreInteret:
            return self.typeCentreInteret.nomCentreInteret
        return f'Centre #{self.pk}'


class Formation(models.Model):
    """Formation suivie par le candidat (diplôme / attestation / certification / formation)."""

    TYPE_DIPLOME       = 'diplome'
    TYPE_ATTESTATION   = 'attestation'
    TYPE_CERTIFICATION = 'certification'
    TYPE_FORMATION     = 'formation'
    TYPE_CHOICES = [
        (TYPE_DIPLOME,       'Diplôme'),
        (TYPE_ATTESTATION,   'Attestation'),
        (TYPE_CERTIFICATION, 'Certification'),
        (TYPE_FORMATION,     'Formation'),
    ]

    candidat            = models.ForeignKey(
        Candidat, on_delete=models.CASCADE, related_name='formations',
        verbose_name='Candidat',
    )
    diplomeRef          = models.ForeignKey(
        'referentiel.Diplome', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        verbose_name='Diplôme (référentiel)',
    )
    domaine             = models.ForeignKey(
        'referentiel.Domaine', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='Domaine',
    )
    niveauEtude         = models.ForeignKey(
        'referentiel.NiveauEtude', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name="Niveau d'étude",
    )
    institution         = models.ForeignKey(
        'referentiel.Institution', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='Établissement',
    )
    pays                = models.ForeignKey(
        'referentiel.Pays', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='Pays',
    )
    typeSortie          = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default=TYPE_DIPLOME,
        verbose_name='Type de formation',
    )
    diplomeLibre        = models.CharField(max_length=200, blank=True, default='', verbose_name='Diplôme (libre)')
    domaineLibre        = models.CharField(max_length=150, blank=True, default='', verbose_name='Domaine (libre)')
    ecoleLibre          = models.CharField(max_length=200, blank=True, default='', verbose_name='Établissement (libre)')
    paysLibre           = models.CharField(max_length=100, blank=True, default='', verbose_name='Pays (libre)')
    ville               = models.CharField(max_length=100, blank=True, default='', verbose_name='Ville')
    dateDebut           = models.DateField(null=True, blank=True, verbose_name='Date de début')
    dateFin             = models.DateField(null=True, blank=True, verbose_name='Date de fin')
    enCours             = models.BooleanField(default=False, verbose_name='En cours')
    description         = models.TextField(blank=True, default='', verbose_name='Description')
    numero              = models.CharField(max_length=100, blank=True, default='', verbose_name='Numéro / référence')
    expiration          = models.DateField(null=True, blank=True, verbose_name="Date d'expiration")
    estVisiblePortfolio = models.BooleanField(default=True, verbose_name='Visible sur le portfolio')

    class Meta:
        verbose_name        = 'Formation'
        verbose_name_plural = 'Formations'
        ordering            = ['-dateFin', '-dateDebut', 'id']

    def __str__(self):
        diplome = self.diplomeLibre or (self.diplomeRef.nomDiplome if self.diplomeRef else 'Formation')
        ecole   = self.ecoleLibre   or (self.institution.nomInstitution if self.institution else '')
        return f"{diplome} — {ecole}" if ecole else diplome


class ExperienceProfessionnelle(models.Model):
    """Période d'expérience professionnelle chez un employeur."""

    candidat            = models.ForeignKey(
        Candidat, on_delete=models.CASCADE, related_name='experiencesProfessionnelles',
        verbose_name='Candidat',
    )
    entreprise          = models.ForeignKey(
        'referentiel.RaisonSociale', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='Entreprise',
    )
    pays                = models.ForeignKey(
        'referentiel.Pays', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='Pays',
    )
    entrepriseLibre     = models.CharField(max_length=200, blank=True, default='', verbose_name='Entreprise (libre)')
    paysLibre           = models.CharField(max_length=100, blank=True, default='', verbose_name='Pays (libre)')
    ville               = models.CharField(max_length=150, blank=True, default='', verbose_name='Ville')
    dateDebut           = models.DateField(null=True, blank=True, verbose_name='Date de début')
    dateFin             = models.DateField(null=True, blank=True, verbose_name='Date de fin')
    enCours             = models.BooleanField(default=False, verbose_name='En cours')
    description         = models.TextField(blank=True, default='', verbose_name='Description')
    estVisiblePortfolio = models.BooleanField(default=True, verbose_name='Visible sur le portfolio')

    class Meta:
        verbose_name        = 'Expérience professionnelle'
        verbose_name_plural = 'Expériences professionnelles'
        ordering            = ['-dateDebut', 'id']

    def __str__(self):
        ent = self.entrepriseLibre or (self.entreprise.nomEntreprise if self.entreprise else 'Expérience')
        return f"{ent} — {self.candidat}"


class PosteOccupe(models.Model):
    """Poste tenu durant une expérience (une expérience peut comporter plusieurs postes)."""

    experience  = models.ForeignKey(
        ExperienceProfessionnelle, on_delete=models.CASCADE, related_name='postes',
        verbose_name='Expérience',
    )
    poste       = models.ForeignKey(
        'referentiel.Poste', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='Poste (référentiel)',
    )
    titreLibre  = models.CharField(max_length=200, blank=True, default='', verbose_name='Intitulé (libre)')
    dateDebut   = models.DateField(null=True, blank=True, verbose_name='Date de début')
    dateFin     = models.DateField(null=True, blank=True, verbose_name='Date de fin')
    enCours     = models.BooleanField(default=False, verbose_name='En cours')
    ordre       = models.PositiveSmallIntegerField(default=0, verbose_name="Ordre d'affichage")

    class Meta:
        verbose_name        = 'Poste occupé'
        verbose_name_plural = 'Postes occupés'
        ordering            = ['ordre', 'id']

    def __str__(self):
        return self.titreLibre or (self.poste.nomPoste if self.poste else f'Poste #{self.pk}')


class MissionClient(models.Model):
    """Mission effectuée chez un client durant une expérience (consulting / prestation)."""

    experience      = models.ForeignKey(
        ExperienceProfessionnelle, on_delete=models.CASCADE, related_name='missionsClient',
        verbose_name='Expérience',
    )
    client          = models.ForeignKey(
        'referentiel.RaisonSociale', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='Client',
    )
    pays            = models.ForeignKey(
        'referentiel.Pays', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='Pays',
    )
    clientLibre     = models.CharField(max_length=200, blank=True, default='', verbose_name='Client (libre)')
    paysLibre       = models.CharField(max_length=100, blank=True, default='', verbose_name='Pays (libre)')
    ville           = models.CharField(max_length=100, blank=True, default='', verbose_name='Ville')
    dateDebut       = models.DateField(null=True, blank=True, verbose_name='Date de début')
    dateFin         = models.DateField(null=True, blank=True, verbose_name='Date de fin')
    enCours         = models.BooleanField(default=False, verbose_name='En cours')
    description     = models.TextField(blank=True, default='', verbose_name='Description / réalisations')

    class Meta:
        verbose_name        = 'Mission client'
        verbose_name_plural = 'Missions clients'
        ordering            = ['-dateDebut', 'id']

    def __str__(self):
        client = self.clientLibre or (self.client.nomEntreprise if self.client else 'Client')
        return f'Mission — {client}'


class Projet(models.Model):
    """Projet / réalisation du candidat (rubrique Réalisations)."""

    candidat                  = models.ForeignKey(
        Candidat, on_delete=models.CASCADE, related_name='projets',
        verbose_name='Candidat',
    )
    experienceProfessionnelle = models.ForeignKey(
        ExperienceProfessionnelle, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='projets',
        verbose_name='Expérience associée',
    )
    titre                     = models.CharField(max_length=255, verbose_name='Titre')
    dateDebut                 = models.DateField(null=True, blank=True, verbose_name='Date de début')
    dateFin                   = models.DateField(null=True, blank=True, verbose_name='Date de fin')
    tailleEquipe              = models.PositiveIntegerField(null=True, blank=True, verbose_name="Taille d'équipe")
    contexte                  = models.TextField(blank=True, default='', verbose_name='Contexte')
    realisation               = models.TextField(blank=True, default='', verbose_name='Réalisation')
    urlDemo                   = models.URLField(max_length=500, blank=True, default='', verbose_name='URL démo')
    images                    = models.JSONField(default=list, blank=True, verbose_name='Images')
    videos                    = models.JSONField(default=list, blank=True, verbose_name='Vidéos')
    estVisiblePortfolio       = models.BooleanField(default=True, verbose_name='Visible sur le portfolio')

    class Meta:
        verbose_name        = 'Projet'
        verbose_name_plural = 'Projets'
        ordering            = ['-dateDebut', 'id']

    def __str__(self):
        return self.titre or f'Projet #{self.pk}'


class Benevolat(models.Model):
    """Activité bénévole du candidat."""

    candidat            = models.ForeignKey(
        Candidat, on_delete=models.CASCADE, related_name='benevolats',
        verbose_name='Candidat',
    )
    competences         = models.ManyToManyField(
        Competence, blank=True, related_name='benevolats',
        verbose_name='Compétences associées',
    )
    titre               = models.CharField(max_length=255, blank=True, default='', verbose_name='Titre / rôle')
    organisation        = models.CharField(max_length=255, blank=True, default='', verbose_name='Organisation')
    dateDebut           = models.DateField(null=True, blank=True, verbose_name='Date de début')
    dateFin             = models.DateField(null=True, blank=True, verbose_name='Date de fin')
    enCours             = models.BooleanField(default=False, verbose_name='En cours')
    estVisiblePortfolio = models.BooleanField(default=True, verbose_name='Visible sur le portfolio')

    class Meta:
        verbose_name        = 'Bénévolat'
        verbose_name_plural = 'Bénévolats'
        ordering            = ['-dateDebut', 'id']

    def __str__(self):
        if self.titre and self.organisation:
            return f"{self.titre} — {self.organisation}"
        return self.titre or self.organisation or f'Bénévolat #{self.pk}'


# ══════════════════════════════════════════════════════════════════════════════
# CV sauvegardé — modèles de persistance
# ══════════════════════════════════════════════════════════════════════════════
# Un candidat peut sauvegarder N CVs. Chaque CV référence le ModeleCV utilisé,
# stocke un PDF (FileField), un snapshot JSON du contenu structuré (CVContenu)
# et N images (PhotoCV — une par page rendue).


class CVContenu(models.Model):
    """Classe associative : lie un CV aux entités du profil candidat.

    Référence par FK l'identité (snapshot des informations personnelles au moment
    de la sauvegarde) et par M2M chaque rubrique du candidat utilisée dans ce CV.
    Plus de stockage JSON : toutes les données affichées dans le CV sont issues
    des tables relationnelles (Candidat, InformationPersonnelle, Formation,
    ExperienceProfessionnelle, Competence, CandidatLangue, CentreInteret,
    Projet, Benevolat).

    Toggles d'affichage portés par cette classe car ils sont propres à un CV
    donné (un même candidat peut avoir un CV avec ses bénévolats visibles et
    un autre où ils sont masqués).
    """

    informationPersonnelle = models.ForeignKey(
        'InformationPersonnelle', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        verbose_name='Informations personnelles',
    )
    formations   = models.ManyToManyField('Formation',                  blank=True, related_name='contenusCv', verbose_name='Formations')
    experiences  = models.ManyToManyField('ExperienceProfessionnelle', blank=True, related_name='contenusCv', verbose_name='Expériences')
    competences  = models.ManyToManyField('Competence',                 blank=True, related_name='contenusCv', verbose_name='Compétences')
    langues      = models.ManyToManyField('CandidatLangue',             blank=True, related_name='contenusCv', verbose_name='Langues')
    interets     = models.ManyToManyField('CentreInteret',              blank=True, related_name='contenusCv', verbose_name="Centres d'intérêt")
    projets      = models.ManyToManyField('Projet',                     blank=True, related_name='contenusCv', verbose_name='Projets')
    benevolats   = models.ManyToManyField('Benevolat',                  blank=True, related_name='contenusCv', verbose_name='Bénévolats')

    showCertif   = models.BooleanField(default=False, verbose_name='Afficher certifications (legacy)')
    showProjets  = models.BooleanField(default=False, verbose_name='Afficher projets')
    showBenev    = models.BooleanField(default=False, verbose_name='Afficher bénévolats')
    showRef      = models.BooleanField(default=True,  verbose_name='Afficher mention « Références disponibles »')

    # Carte des éléments masqués sur ce CV. Format :
    #   {
    #     "experiences": [2, 5],    # indices (basés sur l'ordre du JSON éditeur)
    #     "formations":  [],
    #     "competences": [1],
    #     "langues":     [],
    #     "interets":    [3],
    #     "projets":     [],
    #     "benevs":      [],
    #     "postes":      {"0": [1]},                         # indices par index d'expérience
    #     "missionsClient": {"0": [0]},                      # idem
    #   }
    # Source de vérité pour la visibilité. Items absents = visibles.
    elementsMasques = models.JSONField(default=dict, blank=True, verbose_name='Éléments masqués')

    # Snapshot complet du CV (rubriques + identité + toggles + masques) au moment
    # du save. Source de vérité pour la **modification** d'un CV existant : à
    # l'ouverture en édition, on lit ce snapshot directement → le CV apparaît
    # exactement tel qu'il a été sauvegardé. Découple les CV entre eux : le
    # delete+recreate des rubriques candidat ne casse plus les CV antérieurs.
    donneesSnapshot = models.JSONField(default=dict, blank=True, verbose_name='Snapshot du CV')

    class Meta:
        verbose_name        = 'Contenu CV'
        verbose_name_plural = 'Contenus CV'

    def __str__(self):
        return f'CVContenu #{self.pk}'


class CV(models.Model):
    """CV sauvegardé par un candidat (PDF + images + snapshot du contenu)."""

    candidat         = models.ForeignKey(
        Candidat, on_delete=models.CASCADE,
        related_name='cvs', verbose_name='Candidat',
    )
    modele           = models.ForeignKey(
        ModeleCV, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='cvs',
        verbose_name='Modèle de CV',
    )
    contenu          = models.OneToOneField(
        CVContenu, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='cv',
        verbose_name='Contenu structuré',
    )
    # Nom identifiant choisi par le candidat (ex: "CV Marketing", "CV Junior").
    # Distinct du `titre` (= titre professionnel affiché dans l'en-tête du CV).
    # blank=True au niveau BD pour ne pas casser les CVs antérieurs ; la
    # validation "obligatoire + unique par candidat" est portée par l'API
    # de sauvegarde et par la contrainte UNIQUE conditionnelle ci-dessous.
    nomCv            = models.CharField(max_length=200, blank=True, default='', verbose_name='Nom du CV')
    titre            = models.CharField(max_length=200, blank=True, default='', verbose_name='Titre du CV')
    profil           = models.TextField(blank=True, default='', verbose_name='Profil / résumé')
    # Photo propre au CV — snapshot au moment du save, indépendante de la photo
    # de profil générale du candidat. Permet à un candidat d'avoir des photos
    # distinctes sur ses différents CVs sans que cela n'écrase sa photo de profil.
    photoProfil      = models.ImageField(
        upload_to='candidat/cv/photos/', blank=True, null=True,
        verbose_name='Photo du CV',
    )
    cvPdf            = models.FileField(
        upload_to='candidat/cv/pdf/', blank=True, null=True,
        verbose_name='Fichier PDF',
    )
    archive          = models.BooleanField(default=False, verbose_name='Archivé')
    estImporte       = models.BooleanField(
        default=False,
        verbose_name='CV importé',
        help_text="True si ce CV a été importé depuis l'appareil du candidat (pas généré par l'éditeur).",
    )
    dateCreation     = models.DateTimeField(auto_now_add=True, verbose_name='Date de création')
    dateModification = models.DateTimeField(auto_now=True,     verbose_name='Dernière modification')

    class Meta:
        verbose_name        = 'CV'
        verbose_name_plural = 'CVs'
        ordering            = ['-dateModification']
        constraints         = [
            # Unicité du nomCv par candidat. Les CVs sans nom (legacy) ne sont
            # pas concernés par la contrainte — ils sont tolérés en BD mais
            # le candidat devra saisir un nom à la prochaine modification.
            models.UniqueConstraint(
                fields=['candidat', 'nomCv'],
                condition=~models.Q(nomCv=''),
                name='unique_nomcv_par_candidat',
            ),
        ]

    def __str__(self):
        nom = self.nomCv or self.titre or f'#{self.pk}'
        return f'CV {nom} — {self.candidat}'

    def archiver(self):
        """Marque le CV comme archivé (le rend inactif)."""
        self.archive = True
        self.save(update_fields=['archive', 'dateModification'])

    def generer_artefacts(self, request, cv_data=None) -> bool:
        """Génère/regénère le PDF + les images de pages du CV et les attache.

        Pipeline :
          1. Reconstruction du dict via `_cv_to_dict(self)` (sauf si fourni).
          2. Pré-traitement (`_preprocess_cv`).
          3. Rendu Playwright → PDF + N images PNG (une par page).
          4. Stockage : `cvPdf` (FileField) + remplacement des `PhotoCV` existantes.

        Best-effort : si Playwright/Chromium est absent ou casse, retourne
        `False` sans toucher aux artefacts existants. La sauvegarde DB du CV
        reste valide.
        """
        from django.core.files.base import ContentFile
        from .cv import _cv_to_dict, _preprocess_cv
        from .cv_render import render_pages

        if not (self.modele and self.contenu):
            return False

        if cv_data is None:
            cv_data = _cv_to_dict(self)
        cv_data = _preprocess_cv(cv_data)

        try:
            pdf_bytes, pages = render_pages(self.modele, cv_data, request, fmt='png')
        except Exception:
            return False

        # ── Cleanup des anciens artefacts AVANT d'écrire les nouveaux ────────
        # FileField.save() crée un nouveau fichier (suffixe unique si collision)
        # mais ne supprime PAS le précédent sur le disque. De même,
        # `photos.all().delete()` ne supprime que les lignes DB, pas les
        # images sur le disque. Sans cleanup, l'écrasement laisse derrière lui
        # des fichiers orphelins qui s'accumulent dans media/.
        if self.cvPdf:
            try:
                self.cvPdf.delete(save=False)   # supprime le fichier ET clear le field
            except Exception:
                pass  # best-effort : on continue même si le fichier était déjà absent
        for old_photo in self.photos.all():
            try:
                if old_photo.image:
                    old_photo.image.delete(save=False)
            except Exception:
                pass
            old_photo.delete()

        # ── Écriture des nouveaux artefacts ──────────────────────────────────
        self.cvPdf.save(
            f'cv_{self.candidat_id}_{self.pk}.pdf',
            ContentFile(pdf_bytes),
            save=True,
        )
        for i, page_bytes in enumerate(pages, start=1):
            photo = PhotoCV(cv=self, numeroPage=i)
            photo.image.save(
                f'cv_{self.candidat_id}_{self.pk}_p{i}.png',
                ContentFile(page_bytes),
                save=True,
            )
        return True


class PhotoCV(models.Model):
    """Image d'une page du CV rendu (1 PhotoCV par page — un CV peut être multi-pages)."""

    cv          = models.ForeignKey(
        CV, on_delete=models.CASCADE,
        related_name='photos', verbose_name='CV',
    )
    image       = models.ImageField(
        upload_to='candidat/cv/pages/',
        verbose_name='Image de la page',
    )
    numeroPage  = models.PositiveSmallIntegerField(default=1, verbose_name='Numéro de page')

    class Meta:
        verbose_name        = 'Photo CV'
        verbose_name_plural = 'Photos CV'
        ordering            = ['cv', 'numeroPage']
        unique_together     = ('cv', 'numeroPage')

    def __str__(self):
        return f'CV #{self.cv_id} — page {self.numeroPage}'


# ══════════════════════════════════════════════════════════════════════════════
#  Lettre de motivation — modèles de persistance
# ══════════════════════════════════════════════════════════════════════════════

class LettreContenu(models.Model):
    """Contenu structuré d'une lettre de motivation (classe associative)."""

    informationPersonnelle = models.ForeignKey(
        'InformationPersonnelle', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        verbose_name='Informations personnelles',
    )
    entreprise = models.ForeignKey(
        'referentiel.RaisonSociale', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        verbose_name='Entreprise',
    )
    titreDestinataire     = models.CharField(max_length=10,  blank=True, default='', verbose_name='Titre')
    nomDestinataire       = models.CharField(max_length=150, blank=True, default='', verbose_name='Nom du destinataire')
    posteDestinataire     = models.ForeignKey(
        'referentiel.Poste', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        verbose_name='Poste du destinataire',
    )
    pays = models.ForeignKey(
        'referentiel.Pays', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        verbose_name='Pays',
    )
    villeEntreprise = models.ForeignKey(
        'referentiel.Ville', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        verbose_name="Ville de l'entreprise",
    )
    lieu         = models.CharField(max_length=100, blank=True, default='', verbose_name='Lieu de rédaction')
    dateLettre   = models.DateField(null=True, blank=True, verbose_name='Date')
    objet        = models.CharField(max_length=300, blank=True, default='', verbose_name='Objet')
    corps        = models.TextField(blank=True, default='', verbose_name='Corps')
    formuleConge = models.TextField(blank=True, default='', verbose_name='Formule de politesse')

    class Meta:
        verbose_name        = 'Contenu lettre de motivation'
        verbose_name_plural = 'Contenus lettres de motivation'

    def __str__(self):
        return f'LettreContenu #{self.pk}'


class LettreMotivation(models.Model):
    """Lettre de motivation sauvegardée par un candidat."""

    candidat         = models.ForeignKey(
        Candidat, on_delete=models.CASCADE,
        related_name='lettres', verbose_name='Candidat',
    )
    modele           = models.ForeignKey(
        ModeleLettre, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lettres',
        verbose_name='Modèle',
    )
    contenu          = models.OneToOneField(
        LettreContenu, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lettre',
        verbose_name='Contenu',
    )
    nomLettre        = models.CharField(max_length=200, blank=True, default='', verbose_name='Nom de la lettre')
    lettrePdf        = models.FileField(
        upload_to='candidat/lettres/pdf/', blank=True, null=True,
        verbose_name='Fichier PDF',
    )
    archive          = models.BooleanField(default=False, verbose_name='Archivée')
    dateCreation     = models.DateTimeField(auto_now_add=True, verbose_name='Date de création')
    dateModification = models.DateTimeField(auto_now=True,     verbose_name='Dernière modification')

    class Meta:
        verbose_name        = 'Lettre de motivation'
        verbose_name_plural = 'Lettres de motivation'
        ordering            = ['-dateModification']

    def __str__(self):
        return f'{self.nomLettre or f"Lettre #{self.pk}"} — {self.candidat}'

    def archiver(self):
        self.archive = True
        self.save(update_fields=['archive'])

    def generer_artefacts(self, request) -> bool:
        """Génère/regénère le PDF + l'image miniature de la lettre."""
        from django.core.files.base import ContentFile
        from . import lettre_render
        from .lettreMo import _lettre_to_dict_for_render

        if not (self.modele and self.contenu):
            return False

        lettre_data = _lettre_to_dict_for_render(self)
        try:
            pdf_bytes = lettre_render.render_pdf(self.modele, lettre_data, request)
        except Exception:
            return False

        image_bytes = None
        try:
            image_bytes = lettre_render._pdf_to_image(pdf_bytes, fmt='png')
        except Exception:
            pass

        # Cleanup anciens artefacts
        if self.lettrePdf:
            try:
                self.lettrePdf.delete(save=False)
            except Exception:
                pass
        for old in self.photos.all():
            try:
                if old.image:
                    old.image.delete(save=False)
            except Exception:
                pass
            old.delete()

        self.lettrePdf.save(
            f'lettre_{self.candidat_id}_{self.pk}.pdf',
            ContentFile(pdf_bytes),
            save=True,
        )
        if image_bytes:
            photo = PhotoLettre(lettre=self, numeroPage=1)
            photo.image.save(
                f'lettre_{self.candidat_id}_{self.pk}_p1.png',
                ContentFile(image_bytes),
                save=True,
            )
        return True


class PhotoLettre(models.Model):
    """Miniature PNG d'une lettre de motivation rendue."""

    lettre     = models.ForeignKey(
        LettreMotivation, on_delete=models.CASCADE,
        related_name='photos', verbose_name='Lettre',
    )
    image      = models.ImageField(
        upload_to='candidat/lettres/pages/',
        verbose_name='Image de la page',
    )
    numeroPage = models.PositiveSmallIntegerField(default=1, verbose_name='Numéro de page')

    class Meta:
        verbose_name        = 'Photo lettre'
        verbose_name_plural = 'Photos lettres'
        ordering            = ['lettre', 'numeroPage']
        unique_together     = ('lettre', 'numeroPage')

    def __str__(self):
        return f'Lettre #{self.lettre_id} — page {self.numeroPage}'


class VisiteurJournalier(models.Model):
    """Compteur agrégé de visiteurs uniques par jour."""

    date         = models.DateField(unique=True, verbose_name='Date')
    nb_visiteurs = models.PositiveIntegerField(default=0, verbose_name='Visiteurs uniques')

    class Meta:
        verbose_name        = 'Visiteur journalier'
        verbose_name_plural = 'Visiteurs journaliers'
        ordering            = ['-date']

    def __str__(self):
        return f"{self.date} — {self.nb_visiteurs} visiteur(s)"


# ══════════════════════════════════════════════════════════════════════════════
#  Candidature  +  HistoriqueStatut
# ══════════════════════════════════════════════════════════════════════════════

class Candidature(models.Model):
    """Acte de candidature d'un Candidat à une OffreEmploi.

    Le candidat peut :
      • réutiliser un CV/lettre généré sur le site (FK vers `CV` / future LettreCandidat) ;
      • OU uploader un fichier depuis sa machine (FileField).

    Workflow :
      1. Construction (statut = POSTULEE par défaut au save initial).
      2. `soumettre()` → crée la 1ʳᵉ entrée d'historique + incrémente le compteur de l'offre.
      3. Recruteur change le statut → on appelle `HistoriqueStatut.creer(...)` qui
         met aussi à jour `candidature.statut`.
      4. `retirer(motif)` → marque RETIREE + historique.
    """

    candidat        = models.ForeignKey(
        'Candidat', on_delete=models.CASCADE,
        related_name='candidatures', verbose_name='Candidat',
    )
    offre           = models.ForeignKey(
        'entreprise.OffreEmploi', on_delete=models.CASCADE,
        related_name='candidatures', verbose_name='Offre',
    )
    reference       = models.CharField(
        max_length=30, unique=True, blank=True,
        verbose_name='Référence',
        help_text='Généré automatiquement au save (ex: CAND-2026-00042).',
    )
    dateCandidature = models.DateTimeField(auto_now_add=True, verbose_name='Date de candidature')

    # ── CV : réutilisation site OU upload externe ────────────────────────────
    cvSauvegarde    = models.ForeignKey(
        'CV', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='candidatures',
        verbose_name='CV RecrutePro (réutilisé)',
        help_text="Si le candidat réutilise un CV qu'il a généré sur le site.",
    )
    cv              = models.FileField(
        upload_to='candidat/candidatures/cv/', blank=True, null=True,
        verbose_name='CV (upload)',
        help_text="Sinon, fichier PDF/DOCX uploadé depuis la machine du candidat.",
    )

    # ── Lettre : réutilisation site OU upload externe ───────────────────────
    lettreSauvegardee = models.ForeignKey(
        'LettreMotivation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='candidatures',
        verbose_name='Lettre RecrutePro (réutilisée)',
        help_text="Si le candidat réutilise une lettre qu'il a créée sur le site.",
    )
    lettreMotivation = models.FileField(
        upload_to='candidat/candidatures/lettres/', blank=True, null=True,
        verbose_name='Lettre de motivation (upload)',
    )

    # ── Portfolio (lien externe) ─────────────────────────────────────────────
    urlPortfolio    = models.URLField(blank=True, default='',
                                      verbose_name='URL du portfolio')

    # ── Statut courant (FK référentiel) ──────────────────────────────────────
    statut          = models.ForeignKey(
        'referentiel.Statut', on_delete=models.PROTECT,
        related_name='candidatures', verbose_name='Statut courant',
        null=True, blank=True,
    )

    class Meta:
        verbose_name        = 'Candidature'
        verbose_name_plural = 'Candidatures'
        ordering            = ['-dateCandidature']
        # Un candidat ne peut postuler qu'une seule fois à une offre donnée
        constraints = [
            models.UniqueConstraint(fields=['candidat', 'offre'],
                                    name='unique_candidature_par_offre'),
        ]

    def __str__(self):
        return f'{self.reference or f"#{self.pk}"} — {self.candidat} → {self.offre}'

    # ── Génération de la référence ───────────────────────────────────────────
    def _generer_reference(self) -> str:
        from datetime import datetime
        annee = datetime.now().year
        # Compteur basé sur l'ID après save (atomique en SQLite suffit pour le dev)
        return f'CAND-{annee}-{self.pk:05d}'

    def save(self, *args, **kwargs):
        creation = self._state.adding
        super().save(*args, **kwargs)
        if creation and not self.reference:
            self.reference = self._generer_reference()
            super().save(update_fields=['reference'])

    # ── Workflow : soumettre / retirer ───────────────────────────────────────
    def soumettre(self) -> bool:
        """Marque la candidature comme POSTULEE et trace l'événement.

        Idempotent : si déjà soumise (statut non None), no-op.
        Retourne True si la soumission a effectivement eu lieu.
        """
        from referentiel.models import Statut
        if self.statut_id:
            return False
        statut_postulee = Statut.objects.filter(code='POSTULEE').first()
        if not statut_postulee:
            return False
        self.statut = statut_postulee
        self.save(update_fields=['statut'])
        HistoriqueStatut.creer(
            candidature=self,
            nouveau=statut_postulee,
            ancien=None,
            commentaire='Candidature soumise par le candidat.',
        )
        # Incrémente le compteur dénormalisé sur l'offre
        type(self.offre).objects.filter(pk=self.offre_id).update(
            nbCandidatures=models.F('nbCandidatures') + 1,
        )
        return True

    def retirer(self, motif: str = '') -> bool:
        """Le candidat retire sa candidature. Idempotent."""
        from referentiel.models import Statut
        statut_retiree = Statut.objects.filter(code='RETIREE').first()
        if not statut_retiree or (self.statut_id == statut_retiree.id):
            return False
        ancien = self.statut
        self.statut = statut_retiree
        self.save(update_fields=['statut'])
        HistoriqueStatut.creer(
            candidature=self, nouveau=statut_retiree, ancien=ancien,
            commentaire=motif or 'Candidature retirée par le candidat.',
        )
        return True

    # ── Helpers ──────────────────────────────────────────────────────────────
    def timeline(self):
        """Renvoie l'historique chronologique (ordre d'occurrence)."""
        return self.historiques.select_related('ancienStatut', 'nouveauStatut').order_by('dateChangement')

    @property
    def cv_url(self) -> str:
        """URL du CV à présenter (priorité : upload > CV sauvegardé)."""
        if self.cv:
            return self.cv.url
        if self.cvSauvegarde and self.cvSauvegarde.cvPdf:
            return self.cvSauvegarde.cvPdf.url
        return ''


class Entretien(models.Model):
    """Rendez-vous d'entretien planifié pour une candidature acceptée.

    Une candidature peut avoir 0, 1 ou plusieurs entretiens (entretien RH,
    technique, manager…). Lié à un Recruteur planificateur.
    """

    class ModeEntretien(models.TextChoices):
        PRESENTIEL    = 'PRESENTIEL',    'Présentiel'
        VISIO         = 'VISIO',         'Visioconférence'
        TELEPHONIQUE  = 'TELEPHONIQUE',  'Téléphonique'

    class TypeEntretien(models.TextChoices):
        PRE_QUALIF = 'PRE_QUALIF', 'Pré-qualification'
        RH         = 'RH',         'Entretien RH'
        TECHNIQUE  = 'TECHNIQUE',  'Entretien technique'
        MANAGER    = 'MANAGER',    'Entretien manager'
        FINAL      = 'FINAL',      'Entretien final'

    class StatutEntretien(models.TextChoices):
        PLANIFIE   = 'PLANIFIE',   'Planifié'
        REPORTE    = 'REPORTE',    'Reporté'
        ANNULE     = 'ANNULE',     'Annulé'
        REALISE    = 'REALISE',    'Réalisé'

    candidature    = models.ForeignKey(
        'Candidature', on_delete=models.CASCADE,
        related_name='entretiens', verbose_name='Candidature',
    )
    dateEntretien  = models.DateTimeField('Date & heure')
    duree          = models.IntegerField(
        'Durée (minutes)', default=60,
        help_text='Durée prévue en minutes.',
    )
    mode           = models.CharField(
        'Mode (legacy)', max_length=20,
        choices=ModeEntretien.choices, default=ModeEntretien.PRESENTIEL,
        help_text='Conservé pour compatibilité — la valeur de référence est modeRef.',
    )
    modeRef        = models.ForeignKey(
        'referentiel.ModeEntretien', on_delete=models.PROTECT,
        null=True, blank=True, related_name='entretiens',
        verbose_name='Mode',
    )
    typeEntretien  = models.CharField(
        'Type (legacy)', max_length=20,
        choices=TypeEntretien.choices, default=TypeEntretien.RH,
        help_text='Conservé pour compatibilité — la valeur de référence est typeEntretienRef.',
    )
    typeEntretienRef = models.ForeignKey(
        'referentiel.TypeEntretien', on_delete=models.PROTECT,
        null=True, blank=True, related_name='entretiens',
        verbose_name='Type d\'entretien',
    )
    lieu           = models.CharField(
        'Lieu / Lien', max_length=300, blank=True,
        help_text='Adresse physique (présentiel) ou URL Meet/Zoom (visio).',
    )
    notes          = models.TextField('Notes / Consignes', blank=True)
    statut         = models.CharField(
        'Statut', max_length=20,
        choices=StatutEntretien.choices, default=StatutEntretien.PLANIFIE,
    )
    createPar      = models.ForeignKey(
        'entreprise.Recruteur', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='entretiens_planifies',
        verbose_name='Planifié par',
    )
    dateCreation     = models.DateTimeField(auto_now_add=True)
    dateModification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Entretien'
        verbose_name_plural = 'Entretiens'
        ordering            = ['dateEntretien']

    def __str__(self):
        return f"Entretien {self.candidature.reference} — {self.dateEntretien:%d/%m/%Y %H:%M}"


class HistoriqueStatut(models.Model):
    """Trace chaque changement de statut d'une Candidature.

    Une entrée par transition. Permet de reconstruire la timeline d'un dossier.
    """

    candidature   = models.ForeignKey(
        Candidature, on_delete=models.CASCADE,
        related_name='historiques', verbose_name='Candidature',
    )
    ancienStatut  = models.ForeignKey(
        'referentiel.Statut', on_delete=models.PROTECT,
        null=True, blank=True, related_name='+',
        verbose_name='Ancien statut',
    )
    nouveauStatut = models.ForeignKey(
        'referentiel.Statut', on_delete=models.PROTECT,
        related_name='+', verbose_name='Nouveau statut',
    )
    dateChangement = models.DateTimeField(auto_now_add=True, verbose_name='Date du changement')
    commentaire    = models.TextField(blank=True, default='', verbose_name='Commentaire')

    class Meta:
        verbose_name        = 'Historique de statut'
        verbose_name_plural = 'Historiques de statut'
        ordering            = ['-dateChangement']

    def __str__(self):
        ancien = self.ancienStatut.libelle if self.ancienStatut else '∅'
        return f'{self.candidature.reference} : {ancien} → {self.nouveauStatut.libelle}'

    # ── Factory : créer une entrée et mettre à jour la candidature ──────────
    @classmethod
    def creer(cls, candidature: 'Candidature', nouveau, ancien=None,
              commentaire: str = '') -> 'HistoriqueStatut':
        """Crée une entrée et synchronise `candidature.statut`.

        Args:
            candidature: l'instance de Candidature concernée
            nouveau: instance Statut (nouveau statut)
            ancien: instance Statut (optionnel, déduit de candidature.statut sinon)
            commentaire: motif libre

        Cette méthode est le SEUL point d'entrée pour changer un statut côté
        métier (sauf soumettre/retirer qui l'appellent en interne).
        """
        if ancien is None:
            ancien = candidature.statut
        h = cls.objects.create(
            candidature   = candidature,
            ancienStatut  = ancien,
            nouveauStatut = nouveau,
            commentaire   = commentaire or '',
        )
        # Synchronise le statut courant de la candidature si nécessaire
        if candidature.statut_id != nouveau.id:
            candidature.statut = nouveau
            candidature.save(update_fields=['statut'])
        return h

    # ── Helper de présentation ─────────────────────────────────────────────
    @classmethod
    def genererTimeline(cls, candidature: 'Candidature') -> list:
        """Construit une liste prête à afficher (template) :
        [{'date', 'ancien', 'nouveau', 'commentaire', 'couleur', 'icone'}, …]
        """
        return [
            {
                'date':        h.dateChangement,
                'ancien':      h.ancienStatut,
                'nouveau':     h.nouveauStatut,
                'commentaire': h.commentaire,
                'couleur':     h.nouveauStatut.couleur,
                'icone':       h.nouveauStatut.icone,
            }
            for h in candidature.historiques
                .select_related('ancienStatut', 'nouveauStatut')
                .order_by('dateChangement')
        ]


# ══════════════════════════════════════════════════════════════════════════════
#  Notifications candidat (alertes d'offres correspondantes, statut, etc.)
# ══════════════════════════════════════════════════════════════════════════════

class NotificationCandidat(models.Model):
    """Notification destinée à un candidat (in-app + email optionnel).

    Types supportés :
      • OFFRE_MATCH    : nouvelle offre qui correspond au profil (score >= seuil)
      • CANDIDATURE    : changement de statut sur une candidature en cours
      • SYSTEME        : message système (annonces, MAJ profil, etc.)

    L'envoi par email est conditionné par `candidat.notificationsOffresEmail`
    et le flag `emailEnvoye` évite les doublons.
    """

    class Type(models.TextChoices):
        OFFRE_MATCH = 'OFFRE_MATCH', "Offre correspondante"
        CANDIDATURE = 'CANDIDATURE', "Suivi de candidature"
        SYSTEME     = 'SYSTEME',     "Système"
        INVITATION  = 'INVITATION',  "Invitation à postuler"
        ENTRETIEN   = 'ENTRETIEN',   "Invitation à un entretien"
        MESSAGE     = 'MESSAGE',     "Message d'un recruteur"
        PROFIL_VU   = 'PROFIL_VU',   "Profil consulté par un recruteur"

    candidat       = models.ForeignKey(
        Candidat, on_delete=models.CASCADE,
        related_name='notifications', verbose_name='Candidat',
    )
    type           = models.CharField(
        max_length=20, choices=Type.choices, default=Type.OFFRE_MATCH,
        verbose_name='Type',
    )
    titre          = models.CharField(max_length=200, verbose_name='Titre')
    message        = models.TextField(blank=True, default='', verbose_name='Message')
    lien           = models.CharField(
        max_length=500, blank=True, default='',
        verbose_name="Lien d'action",
        help_text="URL relative ou absolue à laquelle mène la notification.",
    )
    # Pour les notifications de type OFFRE_MATCH : référence à l'offre concernée.
    # FK nullable car d'autres types n'ont pas d'offre associée.
    offre          = models.ForeignKey(
        'entreprise.OffreEmploi', on_delete=models.CASCADE,
        null=True, blank=True, related_name='notifications',
        verbose_name='Offre concernée',
    )
    score          = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Score de matching',
        help_text="Pour les OFFRE_MATCH, score 0-100 calculé par le moteur.",
    )
    # Lien optionnel vers le Message du recruteur qui a déclenché la notif.
    # Permet à la page Mes notifications d'ouvrir le contenu exact du message.
    messageRecruteur = models.ForeignKey(
        'entreprise.Message', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='notifications_candidat',
        verbose_name='Message du recruteur lié',
    )

    # ── État ────────────────────────────────────────────────────────────────
    lue            = models.BooleanField(default=False, verbose_name='Lue')
    dateLecture    = models.DateTimeField(null=True, blank=True, verbose_name='Date de lecture')
    dateCreation   = models.DateTimeField(auto_now_add=True, verbose_name='Date de création')

    # ── Suivi email ─────────────────────────────────────────────────────────
    emailEnvoye    = models.BooleanField(default=False, verbose_name='Email envoyé')
    emailEnvoyeAt  = models.DateTimeField(null=True, blank=True, verbose_name='Date envoi email')

    class Meta:
        verbose_name        = 'Notification candidat'
        verbose_name_plural = 'Notifications candidat'
        ordering            = ['-dateCreation']
        indexes = [
            models.Index(fields=['candidat', '-dateCreation']),
            models.Index(fields=['candidat', 'lue']),
        ]
        # Évite les doublons (1 notif d'alerte par offre & candidat)
        constraints = [
            models.UniqueConstraint(
                fields=['candidat', 'offre', 'type'],
                condition=models.Q(offre__isnull=False),
                name='unique_notification_par_offre',
            ),
        ]

    def __str__(self):
        return f"{self.get_type_display()} -> {self.candidat} : {self.titre}"

    # ── Helpers ──────────────────────────────────────────────────────────────
    def marquer_lue(self) -> bool:
        """Marque la notification comme lue (idempotent)."""
        if self.lue:
            return False
        from django.utils import timezone
        self.lue = True
        self.dateLecture = timezone.now()
        self.save(update_fields=['lue', 'dateLecture'])
        return True

    def marquer_email_envoye(self) -> None:
        from django.utils import timezone
        self.emailEnvoye   = True
        self.emailEnvoyeAt = timezone.now()
        self.save(update_fields=['emailEnvoye', 'emailEnvoyeAt'])


class AlerteEmploi(models.Model):
    """Alerte emploi personnalisée définie par le candidat.

    Quand une offre est publiée, elle est comparée aux alertes actives.
    Si elle correspond, une notification OFFRE_MATCH est créée (idempotente).
    Fonctionne indépendamment des recommandations automatiques (ML matching).
    """

    candidat    = models.ForeignKey(
        Candidat, on_delete=models.CASCADE,
        related_name='alertesEmploi', verbose_name='Candidat',
    )
    motsCles    = models.CharField(
        'Mots-clés', max_length=500, blank=True,
        help_text="Intitulés de postes séparés par des virgules (ex : Comptable, Ingénieur).",
    )
    typeContrat = models.JSONField(
        'Types de contrat', default=list, blank=True,
        help_text='Liste des types souhaités (ex : ["CDI","CDD"]). Vide = tous.',
    )
    secteur     = models.ForeignKey(
        'referentiel.SecteurActivite', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+', verbose_name="Secteur d'activité",
    )
    ville       = models.JSONField(
        'Villes', default=list, blank=True,
        help_text='Liste des villes souhaitées (ex : ["Abidjan","Yamoussoukro"]). Vide = toutes.',
    )
    salaireMin  = models.IntegerField('Salaire min (FCFA)', null=True, blank=True)
    active      = models.BooleanField('Active', default=True)
    creeLe      = models.DateTimeField('Créée le', auto_now_add=True)

    class Meta:
        ordering            = ['-creeLe']
        verbose_name        = "Alerte emploi"
        verbose_name_plural = "Alertes emploi"

    def __str__(self):
        parts = [self.motsCles or '(tous postes)']
        if self.typeContrat:
            parts.append(', '.join(self.typeContrat))
        if self.ville:
            parts.append(', '.join(self.ville))
        return ' · '.join(parts)

    def correspond_a(self, offre) -> bool:
        """Vérifie si une offre correspond aux critères de cette alerte."""
        # Au moins un poste doit apparaître dans le titre de l'offre
        if self.motsCles:
            mots = [m.strip().lower() for m in self.motsCles.split(',') if m.strip()]
            titre_lower = offre.titre.lower()
            if not any(m in titre_lower for m in mots):
                return False
        # Au moins un type de contrat doit correspondre
        if self.typeContrat:
            if offre.typeContrat not in self.typeContrat:
                return False
        # Secteur unique (FK)
        if self.secteur_id:
            secteur_offre = getattr(offre.entreprise, 'secteurActiviteRef_id', None)
            if secteur_offre != self.secteur_id:
                return False
        # Au moins une ville doit correspondre
        if self.ville:
            offre_ville = offre.ville.lower()
            if not any(v.strip().lower() in offre_ville for v in self.ville):
                return False
        # Salaire minimum
        if self.salaireMin and offre.salaireMin:
            if float(offre.salaireMin) < self.salaireMin:
                return False
        return True


class Temoignage(models.Model):
    """Témoignage affiché sur la page d'accueil.

    Peut être créé directement par l'admin (source='admin') ou soumis par
    un candidat depuis son espace profil (source='candidat', statut='en_attente')
    puis validé par l'admin avant publication.
    """

    STATUT_EN_ATTENTE = 'en_attente'
    STATUT_PUBLIE     = 'publie'
    STATUT_REJETE     = 'rejete'
    STATUT_CHOICES = [
        (STATUT_EN_ATTENTE, 'En attente'),
        (STATUT_PUBLIE,     'Publié'),
        (STATUT_REJETE,     'Rejeté'),
    ]

    SOURCE_ADMIN    = 'admin'
    SOURCE_CANDIDAT = 'candidat'
    SOURCE_CHOICES = [
        (SOURCE_ADMIN,    'Admin'),
        (SOURCE_CANDIDAT, 'Candidat'),
    ]

    STYLE_BLANC = 'blanc'
    STYLE_VERT  = 'vert'
    STYLE_CHOICES = [
        (STYLE_BLANC, 'Carte blanche'),
        (STYLE_VERT,  'Carte verte'),
    ]

    candidat    = models.ForeignKey(
        'Candidat', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='temoignages',
        verbose_name='Candidat',
        help_text='Lié automatiquement pour les soumissions candidat. Vide pour les témoignages admin.',
    )
    prenom_nom  = models.CharField(max_length=100, verbose_name='Nom affiché')
    titre_poste = models.CharField(
        max_length=150, blank=True, default='',
        verbose_name='Titre / poste affiché',
        help_text='Ex : Développeur Web · Abidjan',
    )
    texte       = models.TextField(verbose_name='Témoignage')
    note        = models.PositiveSmallIntegerField(
        default=5, verbose_name='Note (étoiles)',
        help_text='Valeur entre 1 et 5.',
    )
    style       = models.CharField(
        max_length=10, choices=STYLE_CHOICES, default=STYLE_BLANC,
        verbose_name='Style de carte',
        help_text='Alterne blanc / vert pour varier l\'apparence des cartes.',
    )
    statut      = models.CharField(
        max_length=15, choices=STATUT_CHOICES, default=STATUT_EN_ATTENTE,
        verbose_name='Statut',
    )
    source      = models.CharField(
        max_length=10, choices=SOURCE_CHOICES, default=SOURCE_ADMIN,
        verbose_name='Source',
    )
    ordre       = models.PositiveSmallIntegerField(
        default=0, verbose_name="Ordre d'affichage",
        help_text='Les témoignages publiés sont triés par ordre croissant.',
    )
    date_soumission = models.DateTimeField(auto_now_add=True, verbose_name='Date de soumission')

    class Meta:
        verbose_name        = 'Témoignage'
        verbose_name_plural = 'Témoignages'
        ordering            = ['ordre', '-date_soumission']
        constraints = [
            models.UniqueConstraint(
                fields=['candidat'],
                condition=models.Q(candidat__isnull=False),
                name='unique_temoignage_par_candidat',
            ),
        ]

    def __str__(self):
        return f'{self.prenom_nom} — {self.get_statut_display()}'


class TemoignageEnAttente(Temoignage):
    """Proxy pour la file de modération admin — uniquement les témoignages en attente."""
    class Meta:
        proxy               = True
        verbose_name        = 'Témoignage en attente'
        verbose_name_plural = 'Témoignages en attente'
        ordering            = ['-date_soumission']


class OffreFavori(models.Model):
    """Offre sauvegardée (mise en favori) par un candidat."""
    candidat   = models.ForeignKey(
        'Candidat', on_delete=models.CASCADE, related_name='offres_favorites',
    )
    offre      = models.ForeignKey(
        'entreprise.OffreEmploi', on_delete=models.CASCADE, related_name='mis_en_favori',
    )
    date_ajout = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together     = ('candidat', 'offre')
        verbose_name        = 'Offre favorite'
        verbose_name_plural = 'Offres favorites'
        ordering            = ['-date_ajout']

    def __str__(self):
        return f'{self.candidat} ❤ {self.offre}'


class VisiteIP(models.Model):
    """Enregistre les adresses IP ayant visité le site par jour.
    Permet de ne compter chaque visiteur qu'une seule fois par jour.
    """

    date       = models.DateField(verbose_name='Date')
    adresse_ip = models.GenericIPAddressField(verbose_name='Adresse IP')

    class Meta:
        unique_together     = ('date', 'adresse_ip')
        verbose_name        = 'Visite IP'
        verbose_name_plural = 'Visites IP'
        ordering            = ['-date']

    def __str__(self):
        return f"{self.date} — {self.adresse_ip}"
