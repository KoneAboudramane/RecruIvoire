from django.db import models
from django.core.exceptions import ValidationError
from django.utils.html import mark_safe


class Groupe(models.Model):
    titre = models.CharField(max_length=80, verbose_name="Titre")

    pour_candidat = models.BooleanField(default=True, verbose_name="Candidat")
    pour_entreprise = models.BooleanField(default=False, verbose_name="Entreprise")

    en_footer = models.BooleanField(default=True, verbose_name="Footer")
    en_navbar = models.BooleanField(default=False, verbose_name="Navbar")

    ordre_candidat = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Ordre (Candidat)")
    ordre_entreprise = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Ordre (Entreprise)")
    actif = models.BooleanField(default=True, verbose_name="Actif")

    elements = models.ManyToManyField(
        'Element',
        through='GroupeElement',
        through_fields=('groupe', 'element'),
        related_name='groupes',
        blank=True,
        verbose_name="Éléments",
    )

    class Meta:
        ordering = ['ordre_candidat', 'ordre_entreprise']
        verbose_name = "Groupe"
        verbose_name_plural = "Groupes"

    def clean(self):
        # Groupe sans ciblage = groupe bibliothèque, aucune validation de placement
        if not self.pour_candidat and not self.pour_entreprise:
            return

        errors = {}

        if not self.en_footer and not self.en_navbar:
            errors['en_footer'] = "Cochez au moins un placement (Footer ou Navbar)."

        if self.pour_candidat and not self.ordre_candidat:
            errors['ordre_candidat'] = "Ce champ est requis pour la cible Candidat."

        if self.pour_entreprise and not self.ordre_entreprise:
            errors['ordre_entreprise'] = "Ce champ est requis pour la cible Entreprise."

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        cibles = []
        if self.pour_candidat:
            cibles.append('Candidat')
        if self.pour_entreprise:
            cibles.append('Entreprise')
        placements = []
        if self.en_footer:
            placements.append('Footer')
        if self.en_navbar:
            placements.append('Navbar')
        return f"{self.titre} ({' + '.join(cibles)} / {' + '.join(placements)})"


class GroupeFooterProxy(Groupe):
    class Meta:
        proxy = True
        verbose_name = "Footer"
        verbose_name_plural = "Footer"


class GroupeNavbarProxy(Groupe):
    class Meta:
        proxy = True
        verbose_name = "Navbar"
        verbose_name_plural = "Navbar"


class Element(models.Model):
    LIEN = 'LIEN'
    BOUTON = 'BOUTON'
    MENU = 'MENU'
    TYPES = [
        (LIEN, 'Lien'),
        (BOUTON, 'Bouton'),
        (MENU, 'Menu déroulant'),
    ]

    TOUJOURS = 'TOUJOURS'
    CANDIDAT_CONNECTE = 'CANDIDAT_CONNECTE'
    CANDIDAT_NON_CONNECTE = 'CANDIDAT_NON_CONNECTE'
    ENTREPRISE = 'ENTREPRISE'
    RECRUTEUR = 'RECRUTEUR'
    RECRUTEUR_ADMIN = 'RECRUTEUR_ADMIN'
    ENTREPRISE_OU_RECRUTEUR = 'ENTREPRISE_OU_RECRUTEUR'
    VISIBILITES = [
        (TOUJOURS, 'Toujours'),
        (CANDIDAT_CONNECTE, 'Candidat connecté'),
        (CANDIDAT_NON_CONNECTE, 'Candidat non connecté'),
        (ENTREPRISE, 'Entreprise connectée'),
        (RECRUTEUR, 'Recruteur connecté'),
        (RECRUTEUR_ADMIN, 'Recruteur admin'),
        (ENTREPRISE_OU_RECRUTEUR, 'Entreprise ou Recruteur'),
    ]

    type = models.CharField(max_length=6, choices=TYPES, default=LIEN, verbose_name="Type")
    icone = models.CharField(
        max_length=10, blank=True, default='', verbose_name="Icône",
        help_text="Emoji optionnel affiché devant le label (ex: 📄 ✉️ 🏠).",
    )
    label = models.CharField(max_length=120, verbose_name="Label")
    url = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="URL",
        help_text=mark_safe(
            "<strong>Candidat</strong> → commence par <code>/candidat/</code><br>"
            "<strong>Entreprise</strong> → commence par <code>/entreprise/</code><br>"
            "<strong>Les deux</strong> → ex: <em>/faq/</em> · <em>/contact/</em><br>"
            "<strong>Lien externe</strong> → <code>https://exemple.com</code><br>"
            "<strong>Menu déroulant</strong> → laisser vide."
        ),
    )
    visibilite = models.CharField(max_length=25, choices=VISIBILITES, default=TOUJOURS, verbose_name="Visibilité")
    actif = models.BooleanField(default=True, verbose_name="Actif")
    nouvel_onglet = models.BooleanField(default=False, verbose_name="Nouvel onglet")
    correspondance_exacte = models.BooleanField(
        default=False,
        verbose_name="URL exacte",
        help_text="Cocher pour les URLs racines (ex: /candidat/) afin d'éviter qu'elles soient toujours actives.",
    )

    class Meta:
        ordering = ['label']
        verbose_name = "Élément"
        verbose_name_plural = "Éléments"

    def __str__(self):
        return f"{self.label} ({self.url or 'menu'})"


class MenuDeroulant(models.Model):
    """Menu déroulant navbar avec plusieurs liens et/ou groupes comme sources."""
    titre = models.CharField(max_length=120, verbose_name="Titre")
    visibilite = models.CharField(
        max_length=25, choices=Element.VISIBILITES, default=Element.TOUJOURS, verbose_name="Visibilité"
    )
    icone = models.CharField(max_length=10, blank=True, default='', verbose_name="Icône")
    actif = models.BooleanField(default=True, verbose_name="Actif")

    elements = models.ManyToManyField(
        Element,
        through='MenuDeroulantElement',
        related_name='menus_deroulants',
        blank=True,
        verbose_name="Éléments (liens directs)",
    )
    groupes = models.ManyToManyField(
        Groupe,
        through='MenuDeroulantGroupe',
        related_name='menus_deroulants',
        blank=True,
        verbose_name="Groupes (liens du groupe)",
    )

    class Meta:
        verbose_name = "Menu déroulant"
        verbose_name_plural = "Menus déroulants"
        ordering = ['titre']

    def __str__(self):
        return self.titre


class MenuDeroulantElement(models.Model):
    """Lien direct dans un menu déroulant."""
    menu = models.ForeignKey(MenuDeroulant, on_delete=models.CASCADE, related_name='menu_elements')
    element = models.ForeignKey(Element, on_delete=models.CASCADE)
    ordre = models.PositiveSmallIntegerField(default=0, verbose_name="Ordre")

    class Meta:
        ordering = ['ordre']
        verbose_name = "Élément du menu"
        verbose_name_plural = "Éléments du menu"

    def __str__(self):
        return f"{self.menu.titre} › {self.element.label}"


class MenuDeroulantGroupe(models.Model):
    """Groupe de liens dans un menu déroulant (tous ses éléments sont affichés)."""
    menu = models.ForeignKey(MenuDeroulant, on_delete=models.CASCADE, related_name='menu_groupes')
    groupe = models.ForeignKey(Groupe, on_delete=models.CASCADE)
    ordre = models.PositiveSmallIntegerField(default=0, verbose_name="Ordre")

    class Meta:
        ordering = ['ordre']
        verbose_name = "Groupe du menu"
        verbose_name_plural = "Groupes du menu"

    def __str__(self):
        return f"{self.menu.titre} › {self.groupe.titre}"


class GroupeElement(models.Model):
    groupe = models.ForeignKey(Groupe, on_delete=models.CASCADE)
    element = models.ForeignKey(Element, on_delete=models.CASCADE)
    parent = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='enfants',
        verbose_name="Élément parent",
    )
    menu_deroulant = models.ForeignKey(
        MenuDeroulant,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='navbar_items',
        verbose_name="Menu déroulant",
    )
    ordre = models.PositiveSmallIntegerField(default=0, verbose_name="Ordre")

    class Meta:
        ordering = ['ordre']
        unique_together = [('groupe', 'element')]
        verbose_name = "Élément du groupe"
        verbose_name_plural = "Éléments du groupe"

    def __str__(self):
        return f"{self.groupe} › {self.element.label}"


class MenuDeroulantProxy(GroupeElement):
    """Proxy conservé pour compatibilité migrations."""
    class Meta:
        proxy = True
        verbose_name = "Menu déroulant (ancien)"
        verbose_name_plural = "Menus déroulants (anciens)"


class NavbarItemProxy(GroupeElement):
    """Vue admin Navbar : liens directs et menus déroulants dans la navbar."""
    class Meta:
        proxy = True
        verbose_name = "Navbar"
        verbose_name_plural = "Navbar"


class FooterGroupe(models.Model):
    """Assigne un groupe au footer avec son ciblage app et son ordre."""
    groupe = models.ForeignKey(
        Groupe,
        on_delete=models.CASCADE,
        related_name='footer_configs',
        verbose_name="Groupe",
    )
    pour_candidat = models.BooleanField(default=True, verbose_name="Candidat")
    pour_entreprise = models.BooleanField(default=False, verbose_name="Entreprise")
    ordre_candidat = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Ordre (Candidat)")
    ordre_entreprise = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Ordre (Entreprise)")
    actif = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        verbose_name = "Footer"
        verbose_name_plural = "Footer"
        ordering = ['ordre_candidat', 'ordre_entreprise']

    def __str__(self):
        return str(self.groupe.titre)
