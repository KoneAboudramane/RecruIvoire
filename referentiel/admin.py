from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    Pays, Ville,
    TypeCompetence, TypeCentreInteret, Institution, Langue,
    Diplome, NiveauEtude, Certificat, Domaine, SecteurActivite,
    TypePermis, TypeRaisonSociale, RaisonSociale, Poste, Niveau,
    Sexe, Role, StatutCompte, TypeMobilite, Statut,
    ModeTravail, Contrat, AnneesExperience, Devise, ReseauSocial,
    TypeEntretien, ModeEntretien,
    Utilisateur, Administrateur,
)


@admin.register(Utilisateur)
class UtilisateurAdmin(BaseUserAdmin):
    list_display  = ['email', 'type_compte', 'is_active', 'date_joined']
    list_filter   = ['type_compte', 'is_active']
    search_fields = ['email']
    ordering      = ['-date_joined']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Informations', {'fields': ('type_compte',)}),
        ('Permissions', {'fields': ('is_active',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'type_compte', 'password1', 'password2'),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_superuser=False)


@admin.register(Administrateur)
class AdministrateurAdmin(BaseUserAdmin):
    list_display  = ['email', 'is_active', 'is_staff', 'date_joined']
    list_filter   = ['is_active']
    search_fields = ['email']
    ordering      = ['-date_joined']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_superuser=True)

    def save_model(self, request, obj, form, change):
        obj.is_staff = True
        obj.is_superuser = True
        super().save_model(request, obj, form, change)


class VilleInline(admin.TabularInline):
    model = Ville
    extra = 1
    fields = ['nomVille', 'region', 'estActif']


@admin.register(Pays)
class PaysAdmin(admin.ModelAdmin):
    list_display  = ['nomPays', 'codeISO', 'indicatifTel', 'nationalite', 'estActif']
    list_filter   = ['estActif']
    search_fields = ['nomPays', 'codeISO', 'nationalite']
    inlines       = [VilleInline]


@admin.register(Ville)
class VilleAdmin(admin.ModelAdmin):
    list_display  = ['nomVille', 'region', 'pays', 'estActif']
    list_filter   = ['estActif', 'pays']
    search_fields = ['nomVille', 'region']
    autocomplete_fields = ['pays']


@admin.register(TypeCompetence)
class TypeCompetenceAdmin(admin.ModelAdmin):
    list_display  = ['nomCompetence', 'domaine']
    list_filter   = ['domaine']
    search_fields = ['nomCompetence', 'domaine']


@admin.register(TypeCentreInteret)
class TypeCentreInteretAdmin(admin.ModelAdmin):
    list_display  = ['nomCentreInteret']
    search_fields = ['nomCentreInteret']


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display  = ['nomInstitution']
    search_fields = ['nomInstitution']


@admin.register(Langue)
class LangueAdmin(admin.ModelAdmin):
    list_display  = ['nomLangue', 'codeISO']
    search_fields = ['nomLangue', 'codeISO']


@admin.register(Diplome)
class DiplomeAdmin(admin.ModelAdmin):
    list_display  = ['nomDiplome', 'domaine']
    list_filter   = ['domaine']
    search_fields = ['nomDiplome', 'domaine']


@admin.register(NiveauEtude)
class NiveauEtudeAdmin(admin.ModelAdmin):
    list_display  = ['nomNiveau', 'ordre']
    search_fields = ['nomNiveau']
    ordering      = ['ordre']


@admin.register(Certificat)
class CertificatAdmin(admin.ModelAdmin):
    list_display  = ['nomCertificat', 'organisme', 'domaine']
    list_filter   = ['domaine', 'organisme']
    search_fields = ['nomCertificat', 'organisme', 'domaine']


@admin.register(Domaine)
class DomaineAdmin(admin.ModelAdmin):
    list_display  = ['nomDomaine', 'description']
    search_fields = ['nomDomaine', 'description']


@admin.register(SecteurActivite)
class SecteurActiviteAdmin(admin.ModelAdmin):
    list_display  = ['nomSecteur', 'description']
    search_fields = ['nomSecteur', 'description']


@admin.register(TypePermis)
class TypePermisAdmin(admin.ModelAdmin):
    list_display  = ['nomPermis', 'description']
    search_fields = ['nomPermis', 'description']


@admin.register(TypeRaisonSociale)
class TypeRaisonSocialeAdmin(admin.ModelAdmin):
    list_display  = ['nomRaisonSocial', 'secteur']
    list_filter   = ['secteur']
    search_fields = ['nomRaisonSocial', 'secteur']


@admin.register(RaisonSociale)
class RaisonSocialeAdmin(admin.ModelAdmin):
    list_display        = ['nomEntreprise', 'secteur', 'typeRaisonSocial']
    list_filter         = ['secteur', 'typeRaisonSocial']
    search_fields       = ['nomEntreprise', 'secteur']
    autocomplete_fields = ['typeRaisonSocial']


@admin.register(Sexe)
class SexeAdmin(admin.ModelAdmin):
    list_display  = ['sexe']
    search_fields = ['sexe']


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display  = ['libelle']
    search_fields = ['libelle']


@admin.register(StatutCompte)
class StatutCompteAdmin(admin.ModelAdmin):
    list_display  = ['libelle']
    search_fields = ['libelle']


@admin.register(TypeMobilite)
class TypeMobiliteAdmin(admin.ModelAdmin):
    list_display  = ['libelle']
    search_fields = ['libelle']


@admin.register(Poste)
class PosteAdmin(admin.ModelAdmin):
    list_display  = ['nomPoste', 'domaine']
    list_filter   = ['domaine']
    search_fields = ['nomPoste', 'domaine']


@admin.register(Niveau)
class NiveauAdmin(admin.ModelAdmin):
    list_display  = ['type', 'nomNiveau', 'libelle', 'nbEtoiles', 'ordre']
    list_filter   = ['type']
    search_fields = ['nomNiveau', 'libelle']
    ordering      = ['type', 'ordre']


@admin.register(ModeTravail)
class ModeTravailAdmin(admin.ModelAdmin):
    list_display = ['libelle']
    search_fields = ['libelle']


@admin.register(Contrat)
class ContratAdmin(admin.ModelAdmin):
    list_display = ['libelle']
    search_fields = ['libelle']


@admin.register(AnneesExperience)
class AnneesExperienceAdmin(admin.ModelAdmin):
    list_display = ['libelle', 'ordre']
    ordering = ['ordre']
    search_fields = ['libelle']


@admin.register(Devise)
class DeviseAdmin(admin.ModelAdmin):
    list_display = ['libelle', 'codeISO', 'symbole']
    search_fields = ['libelle', 'codeISO']


@admin.register(ReseauSocial)
class ReseauSocialAdmin(admin.ModelAdmin):
    list_display       = ['libelle', 'slug', 'couleur', 'ordre', 'actif']
    list_display_links = ['libelle']
    list_editable      = ['ordre', 'actif']
    list_filter        = ['actif']
    search_fields      = ['libelle', 'slug']


@admin.register(Statut)
class StatutAdmin(admin.ModelAdmin):
    """Référentiel des statuts de candidature.

    Utilisé par `candidat.Candidature.statut`, `HistoriqueStatut` et les
    modèles de message côté entreprise (`ModeleMessage.statut`).
    """
    list_display       = ['code', 'libelle', 'ordre', 'couleur', 'icone', 'estFinal', 'estPositif', 'estActif']
    list_display_links = ['code', 'libelle']
    list_editable      = ['ordre', 'estFinal', 'estPositif', 'estActif']
    list_filter        = ['estFinal', 'estPositif', 'estActif']
    search_fields      = ['code', 'libelle', 'description']
    fieldsets = (
        (None, {
            'fields': ('code', 'libelle', 'description'),
        }),
        ('Affichage', {
            'fields': ('ordre', 'couleur', 'icone'),
        }),
        ('Logique métier', {
            'fields': ('estFinal', 'estPositif', 'estActif'),
        }),
    )


@admin.register(TypeEntretien)
class TypeEntretienAdmin(admin.ModelAdmin):
    list_display       = ['ordre', 'code', 'icone', 'libelle']
    list_display_links = ['code', 'libelle']
    list_editable      = ['ordre']
    search_fields      = ['code', 'libelle']


@admin.register(ModeEntretien)
class ModeEntretienAdmin(admin.ModelAdmin):
    list_display       = ['ordre', 'code', 'icone', 'libelle']
    list_display_links = ['code', 'libelle']
    list_editable      = ['ordre']
    search_fields      = ['code', 'libelle']
