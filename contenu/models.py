from django.db import models
from django.utils import timezone


class ContactConfig(models.Model):
    email              = models.EmailField(default='support@recrutepro.ci', verbose_name="Email")
    telephone          = models.CharField(max_length=30,  default='+225 07 00 00 00 00', verbose_name="Téléphone")
    adresse            = models.CharField(max_length=200, default='Cocody, Abidjan',      verbose_name="Adresse")
    pays               = models.CharField(max_length=100, default="Côte d'Ivoire",        verbose_name="Pays")
    horaires_semaine   = models.CharField(max_length=100, default='Lundi – Vendredi : 8h – 18h', verbose_name="Horaires semaine")
    horaires_samedi    = models.CharField(max_length=100, blank=True, default='Samedi : 9h – 13h', verbose_name="Horaires samedi")
    horaires_note      = models.CharField(max_length=200, blank=True, default='Fermé les jours fériés', verbose_name="Note horaires")
    faq_texte          = models.CharField(max_length=100, blank=True, default='Consultez notre FAQ', verbose_name="Texte lien FAQ")

    class Meta:
        verbose_name = "Contact configuration"
        verbose_name_plural = "Contact configuration"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # singleton non supprimable

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Configuration contact"


class Categorie(models.Model):
    label  = models.CharField(max_length=80, verbose_name="Libellé")
    ordre  = models.PositiveSmallIntegerField(default=0, verbose_name="Ordre")
    actif  = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        ordering = ['ordre', 'label']
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"

    def __str__(self):
        return self.label


class ContactCategorie(Categorie):
    class Meta:
        verbose_name = "Contact catégorie"
        verbose_name_plural = "Contact catégories"


class FaqCategorie(Categorie):
    slug  = models.SlugField(max_length=50, unique=True, verbose_name="Slug")
    icone = models.CharField(max_length=10, default='❓', verbose_name="Icône (emoji)")

    class Meta:
        verbose_name = "FAQ catégorie"
        verbose_name_plural = "FAQ catégories"


class FaqQuestion(models.Model):
    categorie = models.ForeignKey(FaqCategorie, on_delete=models.CASCADE,
                                  related_name='questions', verbose_name="Catégorie")
    question  = models.CharField(max_length=300, verbose_name="Question")
    reponse   = models.TextField(verbose_name="Réponse (HTML autorisé)")
    ordre     = models.PositiveSmallIntegerField(default=0, verbose_name="Ordre")
    actif     = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        ordering = ['ordre']
        verbose_name = "FAQ question"
        verbose_name_plural = "FAQ questions"

    def __str__(self):
        return self.question


class PageStatique(models.Model):
    slug        = models.SlugField(max_length=50, unique=True, verbose_name="Slug")
    titre       = models.CharField(max_length=200, verbose_name="Titre")
    description = models.CharField(max_length=500, blank=True, verbose_name="Description / chapeau")
    mise_a_jour = models.DateField(null=True, blank=True, verbose_name="Date de mise à jour")
    actif       = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        ordering = ['slug']
        verbose_name = "Page statique"
        verbose_name_plural = "Pages statiques"

    def __str__(self):
        return self.titre


class SectionPage(models.Model):
    page    = models.ForeignKey(PageStatique, on_delete=models.CASCADE,
                                related_name='sections', verbose_name="Page")
    ancre   = models.SlugField(max_length=80, verbose_name="Ancre HTML")
    icone   = models.CharField(max_length=10, default='📄', verbose_name="Icône (emoji)")
    titre   = models.CharField(max_length=300, verbose_name="Titre")
    contenu = models.TextField(verbose_name="Contenu (HTML)")
    ordre   = models.PositiveSmallIntegerField(default=0, verbose_name="Ordre")
    actif   = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        ordering = ['ordre']
        verbose_name = "Section"
        verbose_name_plural = "Sections"

    def __str__(self):
        return f"{self.page} — {self.titre}"


class Fonctionnalite(models.Model):
    texte = models.CharField(max_length=200, unique=True, verbose_name="Fonctionnalité")
    ordre = models.PositiveSmallIntegerField(default=0, verbose_name="Ordre")

    class Meta:
        ordering = ['ordre', 'texte']
        verbose_name = "Tarifaires fonctionnalité"
        verbose_name_plural = "Tarifaires fonctionnalités"

    def __str__(self):
        return self.texte


class OffreTarif(models.Model):
    GROUPE = [('candidat', 'Espace Candidat'), ('entreprise', 'Espace Entreprise')]

    page                   = models.ForeignKey(PageStatique, on_delete=models.CASCADE,
                                               related_name='offres', verbose_name="Page")
    groupe                 = models.CharField(max_length=20, choices=GROUPE, verbose_name="Groupe")
    nom                    = models.CharField(max_length=100, verbose_name="Nom de l'offre")
    prix                   = models.CharField(max_length=50, verbose_name="Prix affiché")
    unite                  = models.CharField(max_length=50, blank=True, verbose_name="Unité (ex: FCFA / mois)")
    fonctionnalites_choisies = models.ManyToManyField(
        Fonctionnalite, blank=True,
        verbose_name="Fonctionnalités",
        related_name='offres',
    )
    badge                  = models.CharField(max_length=50, blank=True, verbose_name="Badge (ex: Bientôt, Populaire)")
    cta_texte              = models.CharField(max_length=100, verbose_name="Texte du bouton")
    cta_url                = models.CharField(max_length=200, blank=True, verbose_name="URL du bouton (vide si désactivé)")
    cta_desactive          = models.BooleanField(default=False, verbose_name="Bouton désactivé")
    mise_en_avant          = models.BooleanField(default=False, verbose_name="Mise en avant")
    ordre                  = models.PositiveSmallIntegerField(default=0, verbose_name="Ordre")
    actif                  = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        ordering = ['groupe', 'ordre']
        verbose_name = "Tarifaires offre"
        verbose_name_plural = "Tarifaires offres"

    def __str__(self):
        return f"{self.get_groupe_display()} — {self.nom}"


class ChiffreCle(models.Model):
    page    = models.ForeignKey(PageStatique, on_delete=models.CASCADE,
                                related_name='chiffres', verbose_name="Page")
    chiffre = models.CharField(max_length=20, verbose_name="Chiffre affiché")
    label   = models.CharField(max_length=100, verbose_name="Label")
    ordre   = models.PositiveSmallIntegerField(default=0, verbose_name="Ordre")
    actif   = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        ordering = ['ordre']
        verbose_name = "Chiffre clé"
        verbose_name_plural = "Chiffres clés"

    def __str__(self):
        return f"{self.chiffre} — {self.label}"


class MessageContact(models.Model):
    nom       = models.CharField(max_length=150, verbose_name="Nom")
    email     = models.EmailField(verbose_name="Email")
    categorie = models.CharField(max_length=80, verbose_name="Catégorie")
    sujet     = models.CharField(max_length=200, verbose_name="Sujet")
    message   = models.TextField(verbose_name="Message")
    cree_le   = models.DateTimeField(auto_now_add=True, verbose_name="Reçu le")
    lu        = models.BooleanField(default=False, verbose_name="Lu")
    repondu   = models.BooleanField(default=False, verbose_name="Répondu")
    repondu_le = models.DateTimeField(null=True, blank=True, verbose_name="Répondu le")

    class Meta:
        ordering = ['-cree_le']
        verbose_name = "Contact message"
        verbose_name_plural = "Contact messages"

    def marquer_repondu(self):
        self.repondu = True
        self.repondu_le = timezone.now()
        self.save(update_fields=['repondu', 'repondu_le'])

    def __str__(self):
        return f"{self.nom} — {self.sujet} ({self.cree_le:%d/%m/%Y})"
