from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Groupe, Element, GroupeElement,
    MenuDeroulant, MenuDeroulantElement, MenuDeroulantGroupe,
    NavbarItemProxy, FooterGroupe,
)


# ────────────────────────────────────────────────────────────────────────────
# Inlines
# ────────────────────────────────────────────────────────────────────────────

class GroupeElementInline(admin.TabularInline):
    model = GroupeElement
    fk_name = 'groupe'
    extra = 1
    fields = ('element', 'ordre')
    verbose_name = "Élément"
    verbose_name_plural = "Éléments"


class SousLienForm(forms.ModelForm):
    class Meta:
        model = GroupeElement
        fields = ['element', 'ordre']


class SousLienInline(admin.TabularInline):
    model = GroupeElement
    fk_name = 'parent'
    form = SousLienForm
    extra = 2
    fields = ('element', 'ordre')
    verbose_name = "Sous-lien"
    verbose_name_plural = "Sous-liens du menu"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'element':
            kwargs['queryset'] = Element.objects.exclude(type='MENU').order_by('label')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class MenuDeroulantElementInline(admin.TabularInline):
    model = MenuDeroulantElement
    extra = 1
    fields = ('element', 'ordre')
    verbose_name = "Élément (lien direct)"
    verbose_name_plural = "Éléments (liens directs)"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'element':
            kwargs['queryset'] = Element.objects.exclude(type=Element.MENU).order_by('label')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class MenuDeroulantGroupeInline(admin.TabularInline):
    model = MenuDeroulantGroupe
    extra = 1
    fields = ('groupe', 'ordre')
    verbose_name = "Groupe (liens du groupe)"
    verbose_name_plural = "Groupes (liens du groupe)"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'groupe':
            kwargs['queryset'] = Groupe.objects.filter(actif=True).order_by('titre')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# ────────────────────────────────────────────────────────────────────────────
# Groupes — bibliothèque (titre + éléments, sans configuration de placement)
# ────────────────────────────────────────────────────────────────────────────

class GroupeAdminForm(forms.ModelForm):
    class Meta:
        model = Groupe
        fields = ['titre', 'actif']

    def _post_clean(self):
        self.instance.pour_candidat = False
        self.instance.pour_entreprise = False
        self.instance.en_footer = False
        self.instance.en_navbar = False
        super()._post_clean()


@admin.register(Groupe)
class GroupeAdmin(admin.ModelAdmin):
    form = GroupeAdminForm
    list_display = ('titre', 'nb_elements', 'actif')
    list_editable = ('actif',)
    search_fields = ('titre',)
    ordering = ('titre',)
    fields = ('titre', 'actif')
    inlines = [GroupeElementInline]

    @admin.display(description='Éléments')
    def nb_elements(self, obj):
        return obj.groupeelement_set.filter(parent__isnull=True).count()


# ────────────────────────────────────────────────────────────────────────────
# Footer — groupes assignés au footer
# ────────────────────────────────────────────────────────────────────────────

@admin.register(FooterGroupe)
class FooterAdmin(admin.ModelAdmin):
    list_display = ('groupe', 'pour_candidat', 'pour_entreprise',
                    'ordre_candidat', 'ordre_entreprise', 'actif')
    list_editable = ('pour_candidat', 'pour_entreprise',
                     'ordre_candidat', 'ordre_entreprise', 'actif')
    list_filter = ('pour_candidat', 'pour_entreprise', 'actif')
    search_fields = ('groupe__titre',)
    ordering = ('ordre_candidat', 'ordre_entreprise')
    fields = ('groupe', 'pour_candidat', 'pour_entreprise',
              'ordre_candidat', 'ordre_entreprise', 'actif')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'groupe':
            kwargs['queryset'] = Groupe.objects.filter(actif=True).order_by('titre')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# ────────────────────────────────────────────────────────────────────────────
# Menus déroulants — modèle dédié avec plusieurs éléments et groupes
# ────────────────────────────────────────────────────────────────────────────

@admin.register(MenuDeroulant)
class MenuDeroulantAdmin(admin.ModelAdmin):
    list_display = ('titre', 'visibilite', 'nb_elements', 'nb_groupes', 'actif')
    list_editable = ('actif',)
    list_filter = ('visibilite', 'actif')
    search_fields = ('titre',)
    ordering = ('titre',)
    fields = ('titre', 'icone', 'visibilite', 'actif')
    inlines = [MenuDeroulantElementInline, MenuDeroulantGroupeInline]

    @admin.display(description='Éléments')
    def nb_elements(self, obj):
        return obj.menu_elements.count()

    @admin.display(description='Groupes')
    def nb_groupes(self, obj):
        return obj.menu_groupes.count()


# ────────────────────────────────────────────────────────────────────────────
# Navbar — liens directs et menus déroulants
# ────────────────────────────────────────────────────────────────────────────

class NavbarItemForm(forms.ModelForm):
    lien = forms.ModelChoiceField(
        queryset=Element.objects.exclude(type=Element.MENU).order_by('label'),
        required=False,
        label="Lien direct",
        help_text="Lien ou bouton affiché directement dans la navbar.",
    )
    menu = forms.ModelChoiceField(
        queryset=MenuDeroulant.objects.filter(actif=True).order_by('titre'),
        required=False,
        label="Menu déroulant",
        help_text="Menu avec ses éléments et groupes configurés dans 'Menus déroulants'.",
    )

    class Meta:
        model = GroupeElement
        fields = ['groupe', 'ordre']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        if instance and instance.pk:
            if instance.menu_deroulant_id:
                self.fields['menu'].initial = instance.menu_deroulant_id
            elif instance.element_id:
                self.fields['lien'].initial = instance.element_id
        self.fields['groupe'].queryset = Groupe.objects.filter(en_navbar=True, actif=True).order_by('titre')

    def clean(self):
        cleaned = super().clean()
        lien = cleaned.get('lien')
        menu = cleaned.get('menu')
        if not lien and not menu:
            raise forms.ValidationError("Choisissez un lien direct ou un menu déroulant.")
        if lien and menu:
            raise forms.ValidationError("Choisissez soit un lien direct, soit un menu déroulant — pas les deux.")
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        lien = self.cleaned_data.get('lien')
        menu = self.cleaned_data.get('menu')
        if menu:
            instance.menu_deroulant = menu
            # Créer/récupérer un Element MENU fantôme pour satisfaire la contrainte NOT NULL
            el, _ = Element.objects.get_or_create(
                type=Element.MENU, label=menu.titre,
                defaults={'url': '', 'visibilite': Element.TOUJOURS, 'actif': True},
            )
            instance.element = el
        else:
            instance.element = lien
            instance.menu_deroulant = None
        if commit:
            instance.save()
            self.save_m2m()
        return instance


@admin.register(NavbarItemProxy)
class NavbarAdmin(admin.ModelAdmin):
    form = NavbarItemForm
    list_display = ('get_label', 'get_groupe', 'get_type', 'get_visibilite', 'ordre')
    list_filter = ('groupe', 'element__type')
    search_fields = ('element__label', 'groupe__titre')
    ordering = ('groupe__titre', 'ordre')
    fields = ('groupe', 'lien', 'menu', 'ordre')

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .filter(groupe__en_navbar=True, parent__isnull=True)
            .select_related('element', 'groupe', 'menu_deroulant')
        )

    @admin.display(description='Lien / Menu')
    def get_label(self, obj):
        if obj.menu_deroulant_id:
            return format_html('▾ {}', obj.menu_deroulant.titre)
        return obj.element.label

    @admin.display(description='Groupe navbar')
    def get_groupe(self, obj):
        return obj.groupe.titre

    @admin.display(description='Type')
    def get_type(self, obj):
        return 'Menu déroulant' if obj.menu_deroulant_id else obj.element.get_type_display()

    @admin.display(description='Visibilité')
    def get_visibilite(self, obj):
        if obj.menu_deroulant_id:
            return obj.menu_deroulant.get_visibilite_display()
        return obj.element.get_visibilite_display()


# ────────────────────────────────────────────────────────────────────────────
# Éléments
# ────────────────────────────────────────────────────────────────────────────

@admin.register(Element)
class ElementAdmin(admin.ModelAdmin):
    list_display = ('label', 'url', 'type', 'visibilite', 'nb_groupes', 'actif')
    list_editable = ('type', 'visibilite', 'actif')
    list_filter = ('type', 'visibilite', 'actif')
    search_fields = ('label', 'url')
    fields = ('type', 'icone', 'label', 'url', 'visibilite', 'actif', 'nouvel_onglet', 'correspondance_exacte')

    @admin.display(description='Groupes')
    def nb_groupes(self, obj):
        return obj.groupes.count()
