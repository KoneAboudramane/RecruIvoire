import json
from datetime import timedelta

from django.contrib import admin
from django.db.models import Count, Sum
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.html import format_html, mark_safe
from django.urls import reverse, path
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages as dj_messages
from .models import (
    Entreprise, Recruteur, ParametreEntreprise, OffreEmploi,
    DemandeVerification, StatutDemande, StatutVerification, TokenVerificationEmail,
    PropositionProfil, NotificationRecruteur,
    TemoignageEntreprise, TemoignageEnAttenteEntreprise,
)

MOIS_FR = ['', 'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']


def _mois_labels_data(qs, year_field, month_field, nb_mois=6):
    aujourd_hui = timezone.now().date()
    mois_map = {}
    for r in qs:
        mois_map[(r[year_field], r[month_field])] = r['n']
    labels, data = [], []
    y, m = aujourd_hui.year, aujourd_hui.month
    months = []
    for _ in range(nb_mois):
        months.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    months.reverse()
    for y, m in months:
        is_current = (y == aujourd_hui.year and m == aujourd_hui.month)
        jour = aujourd_hui.day if is_current else 1
        labels.append(f"{jour} {MOIS_FR[m]}")
        data.append(mois_map.get((y, m), 0))
    return labels, data


@admin.register(Entreprise)
class EntrepriseAdmin(admin.ModelAdmin):
    list_display    = ('raisonSocial', 'emailProfessionnel', 'secteurActivite',
                       'statutCompte', 'statutVerification', 'scorePertinence', 'dateCreationCompte')
    list_filter     = ('statutCompte', 'statutVerification', 'planAbonnement', 'secteurActivite')
    search_fields   = ('raisonSocial', 'emailProfessionnel', 'ville', 'registreCommerce')
    readonly_fields = ('dateCreationCompte', 'derniereConnexion', 'scorePertinence')
    fieldsets = (
        ('Identité',        {'fields': ('raisonSocial', 'registreCommerce', 'idu', 'description',
                                        'secteurActivite', 'tailleEntreprise', 'logoEntreprise')}),
        ('Authentification',{'fields': ('emailProfessionnel', 'motPasse')}),
        ('Contact & Web',   {'fields': ('telephone', 'emailContact', 'siteWeb')}),
        ('Localisation',    {'fields': ('adresse', 'ville', 'pays', 'codePostal')}),
        ('Statuts',         {'fields': ('statutCompte', 'statutVerification', 'emailVerifie', 'planAbonnement')}),
        ('Statistiques',    {'fields': ('nombreMembre', 'nombreOffresActives', 'scorePertinence')}),
        ('Dates',           {'fields': ('dateCreationCompte', 'derniereConnexion')}),
    )

    def get_urls(self):
        urls = super().get_urls()
        return [
            path('stats/', self.admin_site.admin_view(self.stats_view), name='entreprise_entreprise_stats'),
        ] + urls

    def stats_view(self, request):
        aujourd_hui = timezone.now().date()
        il_y_a_7j   = aujourd_hui - timedelta(days=7)
        il_y_a_30j  = aujourd_hui - timedelta(days=30)
        depuis_6m   = aujourd_hui - timedelta(days=180)

        total     = Entreprise.objects.count()
        verifiees = Entreprise.objects.filter(statutVerification='VERIFIE').count()
        new_7j    = Entreprise.objects.filter(dateCreationCompte__date__gte=il_y_a_7j).count()
        new_30j   = Entreprise.objects.filter(dateCreationCompte__date__gte=il_y_a_30j).count()

        # Par statut de vérification
        par_verif_qs   = list(Entreprise.objects.values('statutVerification').annotate(n=Count('id')))
        labels_verif   = [r['statutVerification'] or '—' for r in par_verif_qs]
        data_verif     = [r['n'] for r in par_verif_qs]

        # Demandes de vérification par statut
        par_demande_qs = list(DemandeVerification.objects.values('statut').annotate(n=Count('id')))
        labels_demande = [r['statut'] or '—' for r in par_demande_qs]
        data_demande   = [r['n'] for r in par_demande_qs]

        # Par plan d'abonnement
        par_plan_qs = list(Entreprise.objects.values('planAbonnement').annotate(n=Count('id')))
        labels_plan = [r['planAbonnement'] or '—' for r in par_plan_qs]
        data_plan   = [r['n'] for r in par_plan_qs]

        # Inscriptions par mois (6 derniers mois)
        inscrits_qs = (
            Entreprise.objects
            .filter(dateCreationCompte__date__gte=depuis_6m)
            .values('dateCreationCompte__year', 'dateCreationCompte__month')
            .annotate(n=Count('id'))
        )
        mois_labels, mois_data = _mois_labels_data(
            inscrits_qs, 'dateCreationCompte__year', 'dateCreationCompte__month', 6
        )

        context = {
            **self.admin_site.each_context(request),
            'title': 'Statistiques — Entreprises',
            'total': total,
            'verifiees': verifiees,
            'new_7j':  new_7j,
            'new_30j': new_30j,
            'labels_verif':   json.dumps(labels_verif),
            'data_verif':     json.dumps(data_verif),
            'labels_demande': json.dumps(labels_demande),
            'data_demande':   json.dumps(data_demande),
            'labels_plan':    json.dumps(labels_plan),
            'data_plan':      json.dumps(data_plan),
            'mois_labels':    json.dumps(mois_labels),
            'mois_data':      json.dumps(mois_data),
        }
        return TemplateResponse(request, 'admin/entreprise/entreprise/stats.html', context)


@admin.register(Recruteur)
class RecruteurAdmin(admin.ModelAdmin):
    list_display    = ('nomComplet', 'emailProfessionnel', 'entreprise', 'roleMembre',
                       'estActif', 'statutCompte', 'derniereConnexion')
    list_filter     = ('roleMembre', 'estActif', 'statutCompte', 'entreprise')
    search_fields   = ('nomComplet', 'emailProfessionnel')
    readonly_fields = ('dateCreation', 'derniereConnexion')
    list_select_related = ('entreprise',)
    fieldsets = (
        ('Identité',        {'fields': ('entreprise', 'nomComplet',
                                        'telephone', 'photoProfil', 'dateEmbauche')}),
        ('Authentification',{'fields': ('emailProfessionnel', 'motPasse')}),
        ('Rôle & droits',   {'fields': ('roleMembre', 'droitsAcces')}),
        ('Statuts',         {'fields': ('estActif', 'statutCompte', 'emailVerifie')}),
        ('Préférences',     {'fields': ('preferences',)}),
        ('Dates',           {'fields': ('dateCreation', 'derniereConnexion')}),
    )


@admin.register(ParametreEntreprise)
class ParametreEntrepriseAdmin(admin.ModelAdmin):
    list_display  = ('entreprise', 'dateModification', 'modifiePar')
    readonly_fields = ('dateModification',)
    list_select_related = ('entreprise', 'modifiePar')


@admin.register(DemandeVerification)
class DemandeVerificationAdmin(admin.ModelAdmin):
    list_display        = ('entreprise', 'statut_badge', 'date_soumission',
                           'date_traitement', 'traite_par', 'a_rccm', 'a_identite', 'lien_revision')
    list_filter         = ('statut',)
    search_fields       = ('entreprise__raisonSocial', 'entreprise__emailProfessionnel')
    readonly_fields     = ('date_soumission', 'date_traitement', 'traite_par')
    list_select_related = ('entreprise', 'traite_par')
    actions             = ['approuver_demandes', 'rejeter_demandes']
    fieldsets = (
        ('Entreprise',        {'fields': ('entreprise', 'statut')}),
        ('Documents soumis',  {'fields': ('document_rccm', 'document_identite', 'notes_entreprise')}),
        ('Traitement admin',  {'fields': ('notes_admin', 'date_traitement', 'traite_par')}),
        ('Date de soumission',{'fields': ('date_soumission',)}),
    )

    def get_urls(self):
        from . import views as ent_views
        urls = super().get_urls()
        custom = [
            path('dashboard/',
                 self.admin_site.admin_view(ent_views.admin_tableau_bord),
                 name='entreprise_demandeverification_dashboard'),
            path('liste-traitement/',
                 self.admin_site.admin_view(ent_views.admin_verifications_liste),
                 name='entreprise_demandeverification_liste_traitement'),
            path('reviser/<int:pk>/',
                 self.admin_site.admin_view(ent_views.admin_verification_detail),
                 name='entreprise_demandeverification_reviser'),
            path('verifier-email/<int:pk>/',
                 self.admin_site.admin_view(ent_views.admin_verifier_email),
                 name='entreprise_demandeverification_verifier_email'),
            path('ml/',
                 self.admin_site.admin_view(ent_views.admin_ml_status),
                 name='entreprise_demandeverification_ml_status'),
            path('ml/dashboard/',
                 self.admin_site.admin_view(ent_views.admin_ml_dashboard),
                 name='entreprise_demandeverification_ml_dashboard'),
            path('ml/reentrainer/',
                 self.admin_site.admin_view(ent_views.admin_ml_reentrainer),
                 name='entreprise_demandeverification_ml_reentrainer'),
            path('ml/planification/enregistrer/',
                 self.admin_site.admin_view(ent_views.admin_ml_planification_enregistrer),
                 name='entreprise_demandeverification_ml_planif_save'),
            path('ml/planification/supprimer/',
                 self.admin_site.admin_view(ent_views.admin_ml_planification_supprimer),
                 name='entreprise_demandeverification_ml_planif_delete'),
        ]
        return custom + urls

    @admin.display(description='Révision')
    def lien_revision(self, obj):
        url = reverse('admin:entreprise_demandeverification_reviser', args=[obj.pk])
        label = '→ Réviser' if obj.statut == StatutDemande.EN_ATTENTE else '→ Voir'
        color = '#F77F00' if obj.statut == StatutDemande.EN_ATTENTE else '#6b7280'
        return format_html(
            '<a href="{}" style="color:{};font-weight:700;text-decoration:none;">{}</a>',
            url, color, label,
        )

    @admin.display(description='Statut', ordering='statut')
    def statut_badge(self, obj):
        colors = {
            StatutDemande.EN_ATTENTE: '#F59E0B',
            StatutDemande.APPROUVEE:  '#22C55E',
            StatutDemande.REJETEE:    '#EF4444',
        }
        color = colors.get(obj.statut, '#9CA3AF')
        return format_html(
            '<span style="color:{};font-weight:700;">{}</span>',
            color, obj.get_statut_display(),
        )

    @admin.display(description='RCCM', boolean=True)
    def a_rccm(self, obj):
        return bool(obj.document_rccm)

    @admin.display(description='Identité', boolean=True)
    def a_identite(self, obj):
        return bool(obj.document_identite)

    def approuver_demandes(self, request, queryset):
        count = 0
        for demande in queryset.filter(statut=StatutDemande.EN_ATTENTE):
            demande.statut        = StatutDemande.APPROUVEE
            demande.date_traitement = timezone.now()
            demande.traite_par    = request.user
            demande.save()
            demande.entreprise.statutVerification = StatutVerification.VERIFIE
            demande.entreprise.save(update_fields=['statutVerification'])
            count += 1
        self.message_user(request,
            f'{count} demande(s) approuvée(s). Les entreprises sont maintenant "Vérifiées".')
    approuver_demandes.short_description = '✅ Approuver les demandes sélectionnées'

    def rejeter_demandes(self, request, queryset):
        count = 0
        for demande in queryset.filter(statut=StatutDemande.EN_ATTENTE):
            demande.statut        = StatutDemande.REJETEE
            demande.date_traitement = timezone.now()
            demande.traite_par    = request.user
            demande.save()
            demande.entreprise.statutVerification = StatutVerification.REJETE
            demande.entreprise.save(update_fields=['statutVerification'])
            count += 1
        self.message_user(request,
            f'{count} demande(s) rejetée(s).', level=dj_messages.WARNING)
    rejeter_demandes.short_description = '❌ Rejeter les demandes sélectionnées'


@admin.register(TokenVerificationEmail)
class TokenVerificationEmailAdmin(admin.ModelAdmin):
    list_display    = ('entreprise', 'token', 'date_creation', 'date_expiration', 'utilise')
    list_filter     = ('utilise',)
    readonly_fields = ('token', 'date_creation', 'date_expiration')
    search_fields   = ('entreprise__raisonSocial', 'entreprise__emailProfessionnel')


@admin.register(OffreEmploi)
class OffreEmploiAdmin(admin.ModelAdmin):
    list_display    = ('titre', 'entreprise', 'typeContrat', 'modeTravail', 'statutOffre',
                       'nbVues', 'nbCandidatures', 'dateCreation')
    list_filter     = ('statutOffre', 'typeContrat', 'modeTravail', 'experienceRequise')
    search_fields   = ('titre', 'reference', 'ville', 'entreprise__raisonSocial')
    readonly_fields = ('dateCreation', 'datePublication', 'nbVues', 'nbCandidatures', 'reference')
    list_select_related = ('entreprise', 'creePar')
    fieldsets = (
        ('Identité',     {'fields': ('entreprise', 'creePar', 'titre', 'reference', 'typeContrat', 'modeTravail')}),
        ('Localisation', {'fields': ('localisation', 'ville', 'pays')}),
        ('Description',  {'fields': ('missions', 'profilRecherche', 'competencesRequises')}),
        ('Exigences',    {'fields': ('experienceRequise', 'niveauEtudeRequis', 'salaireMin', 'salaireMax', 'devise')}),
        ('Dates',        {'fields': ('dateCreation', 'datePublication', 'dateExpiration')}),
        ('Statut',       {'fields': ('statutOffre', 'nbVues', 'nbCandidatures')}),
        ('ATS',          {'fields': ('criteresATS',)}),
    )

    def get_urls(self):
        urls = super().get_urls()
        return [
            path('stats/', self.admin_site.admin_view(self.stats_view), name='entreprise_offreemploi_stats'),
        ] + urls

    def stats_view(self, request):
        aujourd_hui = timezone.now().date()
        il_y_a_7j   = aujourd_hui - timedelta(days=7)
        il_y_a_30j  = aujourd_hui - timedelta(days=30)
        depuis_6m   = aujourd_hui - timedelta(days=180)

        total     = OffreEmploi.objects.count()
        publiees  = OffreEmploi.objects.filter(statutOffre='PUBLIEE').count()
        new_7j    = OffreEmploi.objects.filter(
            datePublication__isnull=False, datePublication__date__gte=il_y_a_7j
        ).count()
        new_30j   = OffreEmploi.objects.filter(
            datePublication__isnull=False, datePublication__date__gte=il_y_a_30j
        ).count()
        total_vues        = OffreEmploi.objects.aggregate(t=Sum('nbVues'))['t'] or 0
        total_candidatures = OffreEmploi.objects.aggregate(t=Sum('nbCandidatures'))['t'] or 0

        TRAD_STATUT = {
            'BROUILLON': 'Brouillon', 'PUBLIEE': 'Publiée',
            'EXPIREE': 'Expirée', 'POURVUE': 'Pourvue', 'FERMEE': 'Fermée',
        }
        # Par statut
        par_statut_qs  = list(OffreEmploi.objects.values('statutOffre').annotate(n=Count('id')))
        labels_statut  = [TRAD_STATUT.get(r['statutOffre'], r['statutOffre']) for r in par_statut_qs]
        data_statut    = [r['n'] for r in par_statut_qs]

        # Par type de contrat
        par_contrat_qs = list(OffreEmploi.objects.values('typeContrat').annotate(n=Count('id')).order_by('-n'))
        labels_contrat = [r['typeContrat'] or '—' for r in par_contrat_qs]
        data_contrat   = [r['n'] for r in par_contrat_qs]

        # Par mode de travail
        par_mode_qs = list(OffreEmploi.objects.values('modeTravail').annotate(n=Count('id')))
        labels_mode = [r['modeTravail'] or '—' for r in par_mode_qs]
        data_mode   = [r['n'] for r in par_mode_qs]

        # Publications par mois (6 derniers mois)
        publiees_qs = (
            OffreEmploi.objects
            .filter(datePublication__isnull=False, datePublication__date__gte=depuis_6m)
            .values('datePublication__year', 'datePublication__month')
            .annotate(n=Count('id'))
        )
        mois_labels, mois_data = _mois_labels_data(
            publiees_qs, 'datePublication__year', 'datePublication__month', 6
        )

        context = {
            **self.admin_site.each_context(request),
            'title': 'Statistiques — Offres d\'emploi',
            'total': total,
            'publiees': publiees,
            'new_7j':  new_7j,
            'new_30j': new_30j,
            'total_vues': total_vues,
            'total_candidatures': total_candidatures,
            'labels_statut':  json.dumps(labels_statut),
            'data_statut':    json.dumps(data_statut),
            'labels_contrat': json.dumps(labels_contrat),
            'data_contrat':   json.dumps(data_contrat),
            'labels_mode':    json.dumps(labels_mode),
            'data_mode':      json.dumps(data_mode),
            'mois_labels':    json.dumps(mois_labels),
            'mois_data':      json.dumps(mois_data),
        }
        return TemplateResponse(request, 'admin/entreprise/offreemploi/stats.html', context)


# ── PropositionProfil (signaux d'apprentissage ATS) ──────────────────────────

@admin.register(PropositionProfil)
class PropositionProfilAdmin(admin.ModelAdmin):
    list_display       = ('offre', 'candidat', 'recruteur', 'scoreATS', 'action', 'dateProposition', 'dateAction')
    list_filter        = ('action', 'dateProposition', 'offre__entreprise')
    search_fields      = ('offre__titre', 'candidat__nom', 'candidat__prenom', 'candidat__email')
    raw_id_fields      = ('offre', 'candidat', 'recruteur')
    readonly_fields    = ('dateProposition', 'dateAction')
    list_select_related = ('offre', 'candidat', 'recruteur')
    ordering           = ('-dateProposition',)
    date_hierarchy     = 'dateProposition'


@admin.register(NotificationRecruteur)
class NotificationRecruteurAdmin(admin.ModelAdmin):
    list_display       = ('recruteur', 'type', 'titre', 'score', 'lue', 'dateCreation')
    list_filter        = ('type', 'lue', 'dateCreation')
    search_fields      = ('recruteur__email', 'titre', 'message')
    raw_id_fields      = ('recruteur', 'offre', 'candidat')
    readonly_fields    = ('dateCreation', 'dateLecture', 'dateEnvoiEmail')
    list_select_related = ('recruteur', 'offre', 'candidat')
    ordering           = ('-dateCreation',)
    date_hierarchy     = 'dateCreation'


# ─── Témoignages clients ──────────────────────────────────────────────────────

@admin.register(TemoignageEntreprise)
class TemoignageEntrepriseAdmin(admin.ModelAdmin):
    """Témoignages clients publiés et rejetés — gestion éditoriale.
    Masqué de la liste des modules (accessible via les cartes KPI du dashboard).
    """
    list_display    = ['apercu_avatar', 'prenom_nom', 'statut_badge', 'source_badge',
                       'note_etoiles', 'poste', 'ordre', 'date_soumission']
    list_editable   = ['ordre']
    list_filter     = ['statut', 'source']
    search_fields   = ['prenom_nom', 'texte', 'poste']
    ordering        = ['ordre', '-date_soumission']
    readonly_fields = ['date_soumission', 'entreprise_lien']
    actions         = ['action_publier', 'action_rejeter']
    list_per_page   = 20

    fieldsets = (
        ('Contenu', {
            'fields': ('prenom_nom', 'poste', 'texte', 'note'),
        }),
        ('Affichage', {
            'fields': ('ordre',),
        }),
        ('Modération', {
            'fields': ('statut', 'source', 'entreprise_lien', 'date_soumission'),
        }),
    )

    def has_module_perms(self, request):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            statut__in=[TemoignageEntreprise.STATUT_PUBLIE, TemoignageEntreprise.STATUT_REJETE]
        )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.source = TemoignageEntreprise.SOURCE_ADMIN
            if obj.statut == TemoignageEntreprise.STATUT_EN_ATTENTE:
                obj.statut = TemoignageEntreprise.STATUT_PUBLIE
        super().save_model(request, obj, form, change)

    @admin.display(description='Avatar')
    def apercu_avatar(self, obj):
        initiales = (obj.prenom_nom or '??')[:2].upper()
        return format_html(
            '<div style="width:36px;height:36px;border-radius:50%;background:#009A44;'
            'display:flex;align-items:center;justify-content:center;'
            'color:white;font-weight:700;font-size:12px;">{}</div>',
            initiales,
        )

    @admin.display(description='Statut')
    def statut_badge(self, obj):
        couleurs = {
            TemoignageEntreprise.STATUT_PUBLIE:     ('#009A44', '✓ Publié'),
            TemoignageEntreprise.STATUT_EN_ATTENTE: ('#F77F00', '⏳ En attente'),
            TemoignageEntreprise.STATUT_REJETE:     ('#ef4444', '✗ Rejeté'),
        }
        couleur, label = couleurs.get(obj.statut, ('#6b7280', obj.statut))
        return format_html('<span style="color:{};font-weight:700;">{}</span>', couleur, label)

    @admin.display(description='Source')
    def source_badge(self, obj):
        if obj.source == TemoignageEntreprise.SOURCE_ENTREPRISE:
            return mark_safe('<span style="color:#009A44;font-weight:700;">🏢 Entreprise</span>')
        return mark_safe('<span style="color:#6b7280;font-weight:600;">🛠 Admin</span>')

    @admin.display(description='Note')
    def note_etoiles(self, obj):
        etoiles = '★' * obj.note + '☆' * (5 - obj.note)
        return format_html('<span style="color:#F77F00;font-size:14px;">{}</span>', etoiles)

    @admin.display(description='Entreprise liée')
    def entreprise_lien(self, obj):
        if obj.entreprise:
            return format_html(
                '<a href="/admin/entreprise/entreprise/{}/change/">{}</a>',
                obj.entreprise.pk, obj.entreprise.nomEntreprise,
            )
        return '—'

    @admin.action(description='✓ Publier les témoignages sélectionnés')
    def action_publier(self, request, queryset):
        nb = queryset.update(statut=TemoignageEntreprise.STATUT_PUBLIE)
        self.message_user(request, f'{nb} témoignage(s) publié(s).')

    @admin.action(description='✗ Rejeter les témoignages sélectionnés')
    def action_rejeter(self, request, queryset):
        nb = queryset.update(statut=TemoignageEntreprise.STATUT_REJETE)
        self.message_user(request, f'{nb} témoignage(s) rejeté(s).')


@admin.register(TemoignageEnAttenteEntreprise)
class TemoignageEnAttenteEntrepriseAdmin(TemoignageEntrepriseAdmin):
    """File de modération — témoignages clients en attente de validation."""
    list_display  = ['apercu_avatar', 'prenom_nom', 'source_badge',
                     'note_etoiles', 'poste', 'date_soumission']
    list_editable = []
    list_filter   = ['source']
    ordering      = ['-date_soumission']
    readonly_fields = ['date_soumission', 'entreprise_lien', 'statut', 'source']
    actions       = ['action_publier', 'action_rejeter']

    fieldsets = (
        ('Contenu du témoignage', {
            'fields': ('prenom_nom', 'poste', 'texte', 'note'),
        }),
        ('Informations', {
            'fields': ('statut', 'source', 'entreprise_lien', 'date_soumission'),
        }),
    )

    def get_queryset(self, request):
        return TemoignageEntreprise.objects.filter(
            statut=TemoignageEntreprise.STATUT_EN_ATTENTE
        ).select_related('entreprise')

    def has_add_permission(self, request):
        return False
