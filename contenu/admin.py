from django import forms
from django.contrib import admin
from django.utils.html import format_html
from .models import (ContactConfig, ContactCategorie, MessageContact,
                     Categorie, FaqCategorie, FaqQuestion,
                     PageStatique, SectionPage, Fonctionnalite, OffreTarif, ChiffreCle)


# ── Formulaires de sélection (dropdown → Categorie existante) ─────────────────

class ContactCategorieForm(forms.ModelForm):
    categorie_ptr = forms.ModelChoiceField(
        queryset=Categorie.objects.none(),
        label="Catégorie",
        help_text="Sélectionnez une catégorie à associer au formulaire de contact.",
    )

    class Meta:
        model  = ContactCategorie
        fields = ['categorie_ptr']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        deja_lies = ContactCategorie.objects.values_list('categorie_ptr_id', flat=True)
        qs = Categorie.objects.exclude(id__in=deja_lies)
        if self.instance.pk:
            qs = qs | Categorie.objects.filter(pk=self.instance.pk)
        self.fields['categorie_ptr'].queryset = qs.order_by('ordre', 'label')


class FaqCategorieForm(forms.ModelForm):
    categorie_ptr = forms.ModelChoiceField(
        queryset=Categorie.objects.none(),
        label="Catégorie",
        help_text="Sélectionnez une catégorie à associer à la FAQ.",
    )

    class Meta:
        model  = FaqCategorie
        fields = ['categorie_ptr', 'slug', 'icone']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        deja_lies = FaqCategorie.objects.values_list('categorie_ptr_id', flat=True)
        qs = Categorie.objects.exclude(id__in=deja_lies)
        if self.instance.pk:
            qs = qs | Categorie.objects.filter(pk=self.instance.pk)
        self.fields['categorie_ptr'].queryset = qs.order_by('ordre', 'label')


# ── Contact configuration ─────────────────────────────────────────────────────

@admin.register(ContactConfig)
class ContactConfigAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Coordonnées", {
            "fields": ("email", "telephone", "adresse", "pays"),
        }),
        ("Horaires du support", {
            "fields": ("horaires_semaine", "horaires_samedi", "horaires_note"),
        }),
        ("Liens", {
            "fields": ("faq_texte",),
        }),
    )

    def has_add_permission(self, request):
        return not ContactConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


# ── Catégories (modèle parent) ────────────────────────────────────────────────

class ContactCategorieInline(admin.StackedInline):
    model               = ContactCategorie
    extra               = 0
    can_delete          = False
    verbose_name        = "Associer à Contact"
    verbose_name_plural = "Association Contact"


class FaqCategorieInline(admin.StackedInline):
    model               = FaqCategorie
    extra               = 0
    can_delete          = False
    verbose_name        = "Associer à FAQ"
    verbose_name_plural = "Association FAQ"
    fields              = ("slug", "icone")


def type_categorie(obj):
    if hasattr(obj, 'contactcategorie'):
        return "Contact"
    if hasattr(obj, 'faqcategorie'):
        return "FAQ"
    return "—"
type_categorie.short_description = "Type"


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display  = ("label", "ordre", "actif", type_categorie)
    list_editable = ("ordre", "actif")
    ordering      = ("ordre", "label")
    inlines       = [ContactCategorieInline, FaqCategorieInline]


# ── Contact catégories ────────────────────────────────────────────────────────

@admin.register(ContactCategorie)
class ContactCategorieAdmin(admin.ModelAdmin):
    form         = ContactCategorieForm
    fields       = ('categorie_ptr',)
    list_display = ("label", "ordre", "actif")
    ordering     = ("ordre",)


# ── Contact messages ──────────────────────────────────────────────────────────

@admin.register(MessageContact)
class MessageContactAdmin(admin.ModelAdmin):
    list_display    = ("nom", "email", "categorie", "sujet", "cree_le", "lu", "statut_reponse")
    list_filter     = ("lu", "repondu", "categorie")
    search_fields   = ("nom", "email", "sujet", "message")
    readonly_fields = ("nom", "email", "categorie", "sujet", "message", "cree_le", "repondu_le")
    ordering        = ("-cree_le",)
    date_hierarchy  = "cree_le"

    fieldsets = (
        ("Message", {
            "fields": ("nom", "email", "categorie", "sujet", "message", "cree_le"),
        }),
        ("Suivi", {
            "fields": ("lu", "repondu", "repondu_le"),
        }),
    )

    def statut_reponse(self, obj):
        if obj.repondu:
            return format_html('<span style="color:#16a34a;font-weight:bold;">✔ Répondu</span>')
        return format_html('<span style="color:#dc2626;">✘ En attente</span>')
    statut_reponse.short_description = "Statut"

    def has_add_permission(self, request):
        return False


# ── FAQ ───────────────────────────────────────────────────────────────────────

class FaqQuestionInline(admin.TabularInline):
    model    = FaqQuestion
    extra    = 1
    fields   = ("question", "reponse", "ordre", "actif")
    ordering = ("ordre",)


@admin.register(FaqCategorie)
class FaqCategorieAdmin(admin.ModelAdmin):
    form         = FaqCategorieForm
    fields       = ('categorie_ptr', 'slug', 'icone')
    list_display = ("label", "slug", "icone", "ordre", "actif")
    ordering     = ("ordre",)
    inlines      = [FaqQuestionInline]


@admin.register(FaqQuestion)
class FaqQuestionAdmin(admin.ModelAdmin):
    list_display  = ("question", "categorie", "ordre", "actif")
    list_filter   = ("categorie", "actif")
    search_fields = ("question", "reponse")
    ordering      = ("categorie__ordre", "ordre")


# ── Pages statiques ───────────────────────────────────────────────────────────

class SectionPageInline(admin.TabularInline):
    model               = SectionPage
    extra               = 1
    fields              = ("ordre", "ancre", "icone", "titre", "contenu", "actif")
    ordering            = ("ordre",)
    show_change_link    = True
    verbose_name        = "Section"
    verbose_name_plural = "Sections (confidentialité, CGU, mentions légales…)"


class OffreTarifInline(admin.TabularInline):
    model               = OffreTarif
    extra               = 1
    fields              = ("ordre", "groupe", "nom", "prix", "unite", "badge",
                           "cta_texte", "cta_url", "cta_desactive", "mise_en_avant", "actif")
    ordering            = ("groupe", "ordre")
    show_change_link    = True
    verbose_name        = "Offre tarifaire"
    verbose_name_plural = "Offres tarifaires (page Tarifs)"


class ChiffreCleInline(admin.TabularInline):
    model               = ChiffreCle
    extra               = 1
    fields              = ("ordre", "chiffre", "label", "actif")
    ordering            = ("ordre",)
    verbose_name        = "Chiffre clé"
    verbose_name_plural = "Chiffres clés (page À propos)"


@admin.register(PageStatique)
class PageStatiqueAdmin(admin.ModelAdmin):
    list_display  = ("titre", "slug", "mise_a_jour", "actif", "nb_elements")
    list_editable = ("actif",)
    search_fields = ("titre", "slug")
    prepopulated_fields = {"slug": ("titre",)}
    inlines       = [SectionPageInline, OffreTarifInline, ChiffreCleInline]

    fieldsets = (
        ("Identification", {
            "fields": ("slug", "titre", "description", "mise_a_jour", "actif"),
        }),
    )

    def nb_elements(self, obj):
        s = obj.sections.filter(actif=True).count()
        o = obj.offres.filter(actif=True).count()
        c = obj.chiffres.filter(actif=True).count()
        parts = []
        if s: parts.append(f"{s} section(s)")
        if o: parts.append(f"{o} offre(s)")
        if c: parts.append(f"{c} chiffre(s)")
        return ", ".join(parts) or "—"
    nb_elements.short_description = "Contenu"


@admin.register(SectionPage)
class SectionPageAdmin(admin.ModelAdmin):
    list_display  = ("titre", "page", "ancre", "icone", "ordre", "actif")
    list_filter   = ("page", "actif")
    list_editable = ("ordre", "actif")
    search_fields = ("titre", "contenu")
    ordering      = ("page__slug", "ordre")


@admin.register(Fonctionnalite)
class FonctionnaliteAdmin(admin.ModelAdmin):
    list_display  = ("texte", "ordre")
    list_editable = ("ordre",)
    search_fields = ("texte",)
    ordering      = ("ordre", "texte")


@admin.register(OffreTarif)
class OffreTarifAdmin(admin.ModelAdmin):
    list_display      = ("nom", "groupe", "prix", "badge", "mise_en_avant", "cta_desactive", "ordre", "actif")
    list_filter       = ("groupe", "mise_en_avant", "cta_desactive", "actif")
    list_editable     = ("ordre", "actif")
    search_fields     = ("nom",)
    ordering          = ("groupe", "ordre")
    filter_horizontal = ("fonctionnalites_choisies",)
    fieldsets = (
        ("Identification", {
            "fields": ("page", "groupe", "nom", "ordre", "actif"),
        }),
        ("Tarification", {
            "fields": ("prix", "unite", "badge", "mise_en_avant"),
        }),
        ("Bouton d'action", {
            "fields": ("cta_texte", "cta_url", "cta_desactive"),
        }),
        ("Fonctionnalités", {
            "fields": ("fonctionnalites_choisies",),
        }),
    )


@admin.register(ChiffreCle)
class ChiffreCleAdmin(admin.ModelAdmin):
    list_display  = ("chiffre", "label", "page", "ordre", "actif")
    list_editable = ("ordre", "actif")
    ordering      = ("ordre",)
