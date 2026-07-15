import json
from datetime import timedelta

from django import forms
from django.contrib import admin, messages
from django.db.models import Count, Sum
from django.shortcuts import render
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html, mark_safe

from .models import (
    Candidat, InformationPersonnelle, LienCandidat,
    ModeleCV, ModeleLettre, LogoSite, Portfolio,
    AbonneNewsletter, PlanificationNewsletter, FrequenceNewsletter,
    ConseilNewsletter, ActualiteNewsletter, VisiteurJournalier,
    Competence, CandidatLangue, CentreInteret,
    Formation, ExperienceProfessionnelle, PosteOccupe, MissionClient,
    Projet, Benevolat,
    CV, CVContenu, PhotoCV,
    Temoignage, TemoignageEnAttente,
    Mobilite,
)


class SecteurWidget(forms.TextInput):
    """TextInput avec <datalist> proposant les secteurs prédéfinis (saisie libre possible)."""

    def render(self, name, value, attrs=None, renderer=None):
        datalist_id = f'{name}_suggestions'
        attrs = {**(attrs or {}), 'list': datalist_id}
        html = super().render(name, value, attrs, renderer)
        options = mark_safe(''.join(
            f'<option value="{val}"></option>'
            for val, _ in ModeleCV.SECTEURS
        ))
        return html + format_html('<datalist id="{}">{}</datalist>', datalist_id, options)


class ModeleCVAdminForm(forms.ModelForm):
    secteur = forms.CharField(
        label="Secteur d'activité",
        required=False,
        widget=SecteurWidget(attrs={'style': 'width:100%'}),
        help_text='Choisissez un secteur dans la liste ou saisissez un secteur personnalisé.',
    )

    class Meta:
        model  = ModeleCV
        fields = '__all__'


# ─── Modèles de CV ────────────────────────────────────────────────────────────

@admin.register(ModeleCV)
class ModeleCVAdmin(admin.ModelAdmin):
    form          = ModeleCVAdminForm
    list_display  = ['apercu_miniature', 'nom', 'couleur_pastille', 'categorie',
                     'secteur', 'premium', 'actif', 'ordre']
    list_editable = ['premium', 'actif', 'ordre']
    list_filter   = ['premium', 'actif', 'categorie']
    search_fields = ['nom', 'fichier', 'secteur']
    ordering      = ['ordre', 'nom']
    list_per_page = 20

    fieldsets = (
        ('Identification', {
            'fields': ('nom', 'fichier', 'apercu'),
            'description': 'Le fichier HTML doit exister dans candidat/templates/candidat/cv/modeles/.',
        }),
        ('Classification', {
            'fields': ('categorie', 'secteur', 'couleur'),
        }),
        ('Disponibilité', {
            'fields': ('premium', 'actif', 'ordre'),
        }),
    )

    @admin.display(description='Aperçu')
    def apercu_miniature(self, obj):
        if obj.apercu:
            return format_html(
                '<img src="{}" style="height:52px;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.15)">',
                obj.apercu.url,
            )
        return format_html(
            '<div style="width:36px;height:52px;border-radius:6px;background:{}"></div>',
            obj.couleur,
        )

    @admin.display(description='Couleur')
    def couleur_pastille(self, obj):
        return format_html(
            '<span style="display:inline-flex;align-items:center;gap:6px">'
            '<span style="width:14px;height:14px;border-radius:3px;background:{};'
            'border:1px solid #d1d5db;display:inline-block"></span>'
            '<code style="font-size:11px">{}</code></span>',
            obj.couleur,
            obj.couleur,
        )


# ─── Modèles de portfolio ────────────────────────────────────────────────────

@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display       = ['apercu_miniature', 'nom', 'fichier', 'couleur_pastille',
                          'categorie', 'premium', 'actif', 'ordre']
    list_display_links = ['nom']
    list_editable      = ['premium', 'actif', 'ordre']
    list_filter        = ['premium', 'actif', 'categorie']
    search_fields      = ['nom', 'fichier', 'description']
    ordering           = ['ordre', 'nom']
    list_per_page      = 20

    fieldsets = (
        ('Identification', {
            'fields': ('nom', 'fichier', 'apercu', 'description'),
            'description': 'Le fichier HTML doit exister dans candidat/templates/candidat/portfolio/modeles/.',
        }),
        ('Style', {
            'fields': ('categorie', 'couleurPrincipale'),
        }),
        ('Disponibilité', {
            'fields': ('premium', 'actif', 'ordre'),
        }),
        ('Métadonnées', {
            'fields': ('dateCreation',),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ['dateCreation']

    @admin.display(description='Aperçu')
    def apercu_miniature(self, obj):
        if obj.apercu:
            return format_html(
                '<img src="{}" style="height:48px;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.15)">',
                obj.apercu.url,
            )
        return format_html(
            '<div style="width:64px;height:48px;border-radius:6px;background:{}"></div>',
            obj.couleurPrincipale,
        )

    @admin.display(description='Couleur')
    def couleur_pastille(self, obj):
        return format_html(
            '<span style="display:inline-flex;align-items:center;gap:6px">'
            '<span style="width:14px;height:14px;border-radius:3px;background:{};'
            'border:1px solid #d1d5db;display:inline-block"></span>'
            '<code style="font-size:11px">{}</code></span>',
            obj.couleurPrincipale,
            obj.couleurPrincipale,
        )


# ─── Modèles de lettre de motivation ─────────────────────────────────────────

@admin.register(ModeleLettre)
class ModeleLetreAdmin(admin.ModelAdmin):
    list_display  = ['apercu_miniature', 'nom', 'slug', 'couleur_pastille',
                     'categorie', 'premium', 'actif', 'ordre']
    list_editable = ['premium', 'actif', 'ordre']
    list_filter   = ['premium', 'actif', 'categorie']
    search_fields = ['nom', 'slug']
    ordering      = ['ordre', 'nom']
    prepopulated_fields = {'slug': ('nom',)}

    fieldsets = (
        ('Identification', {
            'fields': ('nom', 'slug', 'apercu'),
            'description': 'Le slug doit correspondre au fichier HTML dans candidat/templates/candidat/lettreMo/modeles/.',
        }),
        ('Classification', {
            'fields': ('categorie', 'couleur'),
        }),
        ('Disponibilité', {
            'fields': ('premium', 'actif', 'ordre'),
        }),
    )

    @admin.display(description='Aperçu')
    def apercu_miniature(self, obj):
        if obj.apercu:
            return format_html(
                '<img src="{}" style="height:52px;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.15)">',
                obj.apercu.url,
            )
        return format_html(
            '<div style="width:36px;height:52px;border-radius:6px;background:{};'
            'display:flex;align-items:center;justify-content:center;">'
            '<span style="color:white;font-size:9px;font-weight:700;">LM</span></div>',
            obj.couleur,
        )

    @admin.display(description='Couleur')
    def couleur_pastille(self, obj):
        return format_html(
            '<span style="display:inline-flex;align-items:center;gap:6px">'
            '<span style="width:14px;height:14px;border-radius:3px;background:{};'
            'border:1px solid #d1d5db;display:inline-block"></span>'
            '<code style="font-size:11px">{}</code></span>',
            obj.couleur,
            obj.couleur,
        )


# ─── Logo & Identité du site ──────────────────────────────────────────────────

@admin.register(LogoSite)
class LogoSiteAdmin(admin.ModelAdmin):
    list_display  = ['apercu_logo', 'nom_site', 'mode_affichage', 'actif', 'date_modification']
    list_editable = ['actif']
    ordering      = ['-actif', '-date_modification']

    fieldsets = (
        ('🏷️ Identité', {
            'fields': ('nom_site', 'slogan'),
            'description': (
                'Le nom du site remplace partout "RecrutePro" : navbar, footer, onglets du navigateur.'
            ),
        }),
        ('🖼️ Logo visuel', {
            'fields': ('logo_image', 'mode_affichage', 'apercu_rendu'),
            'description': 'Importez votre logo et choisissez comment il s\'affiche.',
        }),
        ('⚙️ Statut', {
            'fields': ('actif',),
            'description': 'Activer cette configuration désactive automatiquement les autres.',
        }),
    )
    readonly_fields = ['apercu_rendu', 'date_modification']

    @admin.display(description='Aperçu')
    def apercu_logo(self, obj):
        if obj.logo_image:
            return format_html(
                '<img src="{}" style="height:36px;max-width:120px;object-fit:contain;'
                'border-radius:6px;border:1px solid #e5e7eb;padding:2px 6px;background:#f9fafb;">',
                obj.logo_image.url,
            )
        return format_html(
            '<span style="font-weight:800;font-size:15px;'
            'background:linear-gradient(90deg,#009A44,#F77F00);'
            '-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
            'background-clip:text;">{}</span>',
            obj.nom_site,
        )

    @admin.display(description='Aperçu dans la navbar')
    def apercu_rendu(self, obj):
        parts = []

        if obj.logo_image and obj.logo_image.name:
            try:
                parts.append(format_html(
                    '<img src="{}" alt="{}" '
                    'style="height:40px;max-width:160px;object-fit:contain;'
                    'filter:brightness(0) invert(1);margin-right:10px;">',
                    obj.logo_image.url,
                    obj.nom_site,
                ))
            except Exception:
                pass

        if obj.mode_affichage in (LogoSite.MODE_TEXTE, LogoSite.MODE_LES_DEUX):
            parts.append(format_html(
                '<span style="font-size:18px;font-weight:800;color:white;letter-spacing:-0.5px;">{}</span>',
                obj.nom_site,
            ))
            if obj.slogan:
                parts.append(format_html(
                    '<span style="font-size:11px;color:rgba(255,255,255,.65);margin-left:8px;">{}</span>',
                    obj.slogan,
                ))

        if not parts:
            content = mark_safe(
                '<span style="color:rgba(255,255,255,.5);font-size:13px;font-style:italic;">'
                'Aucun contenu à afficher</span>'
            )
        else:
            content = mark_safe(''.join(parts))

        wrapper = (
            '<div style="display:inline-flex;align-items:center;'
            'background:#F77F00;padding:10px 20px;border-radius:10px;">'
            '{content}'
            '</div>'
            '<div style="display:inline-flex;align-items:center;'
            'background:#009A44;padding:10px 20px;border-radius:10px;margin-left:8px;">'
            '{content}'
            '</div>'
        )
        return mark_safe(wrapper.format(content=content))


# ─── Newsletter ───────────────────────────────────────────────────────────────

@admin.register(AbonneNewsletter)
class AbonneNewsletterAdmin(admin.ModelAdmin):
    list_display    = [
        'email', 'statut_badge', 'type_abonne', 'prefs_badge',
        'date_inscription',
    ]
    list_filter     = [
        'actif',
        'offres_semaine', 'conseils', 'actualites',
        'offres_perso', 'profil_consulte', 'resume_candidatures',
    ]
    search_fields   = ['email', 'candidat__nom', 'candidat__prenom']
    ordering        = ['-date_inscription']
    readonly_fields = ['email', 'token_desabonnement', 'date_inscription', 'candidat']
    actions         = ['action_envoyer_offres_semaine']
    fieldsets = (
        (None, {
            'fields': ('email', 'candidat', 'actif', 'token_desabonnement', 'date_inscription'),
        }),
        ('Préférences générales', {
            'fields': ('offres_semaine', 'conseils', 'actualites'),
        }),
        ('Préférences individuelles (candidats inscrits)', {
            'fields': ('offres_perso', 'profil_consulte', 'resume_candidatures'),
        }),
    )

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom = [
            path('planification/',
                 self.admin_site.admin_view(self.vue_planification),
                 name='newsletter_planification'),
            path('planification/enregistrer/',
                 self.admin_site.admin_view(self.vue_planification_enregistrer),
                 name='newsletter_planification_enregistrer'),
            path('planification/supprimer/',
                 self.admin_site.admin_view(self.vue_planification_supprimer),
                 name='newsletter_planification_supprimer'),
            path('envoyer-maintenant/',
                 self.admin_site.admin_view(self.vue_envoyer_maintenant),
                 name='newsletter_envoyer_maintenant'),
            # Ancien URL conservé pour compatibilité
            path('envoyer-offres-semaine/',
                 self.admin_site.admin_view(self.vue_envoyer_maintenant),
                 name='newsletter_envoyer_offres'),
        ]
        return custom + urls

    def vue_planification(self, request):
        """Page de configuration de la planification newsletter."""
        from .models import PlanificationNewsletter, FrequenceNewsletter

        planif = PlanificationNewsletter.singleton()
        qs     = AbonneNewsletter.objects.all()

        stats = {
            'total':         qs.count(),
            'actifs':        qs.filter(actif=True).count(),
            'offres_semaine': qs.filter(actif=True, offres_semaine=True).count(),
            'inscrits':      qs.filter(actif=True, candidat__isnull=False).count(),
        }

        jours_semaine = [
            (0, 'Lundi'), (1, 'Mardi'), (2, 'Mercredi'), (3, 'Jeudi'),
            (4, 'Vendredi'), (5, 'Samedi'), (6, 'Dimanche'),
        ]

        return render(request, 'candidat/admin/newsletter_planification.html', {
            **self.admin_site.each_context(request),
            'title':        'Planification Newsletter',
            'planif':       planif,
            'frequences':   FrequenceNewsletter.choices,
            'jours_semaine': jours_semaine,
            'stats':        stats,
            'messages':     messages.get_messages(request),
        })

    def vue_planification_enregistrer(self, request):
        """Enregistre la configuration de planification newsletter."""
        from .models import PlanificationNewsletter, FrequenceNewsletter
        from django.shortcuts import redirect

        if request.method != 'POST':
            return redirect('admin:newsletter_planification')

        planif = PlanificationNewsletter.singleton()

        frequence = request.POST.get('frequence', FrequenceNewsletter.HEBDOMADAIRE)
        try:
            jour_semaine = int(request.POST.get('jour_semaine', 0))
            jour_mois    = int(request.POST.get('jour_mois', 1))
        except (TypeError, ValueError):
            jour_semaine, jour_mois = 0, 1

        heure_str = request.POST.get('heure', '08:00')
        try:
            h, m = heure_str.split(':')
            from django.utils import timezone as tz
            heure = tz.datetime.strptime(f'{int(h):02d}:{int(m):02d}', '%H:%M').time()
        except (ValueError, AttributeError):
            from django.utils import timezone as tz
            heure = tz.datetime.strptime('08:00', '%H:%M').time()

        planif.frequence    = frequence if frequence in FrequenceNewsletter.values else FrequenceNewsletter.HEBDOMADAIRE
        planif.jour_semaine = max(0, min(6, jour_semaine))
        planif.jour_mois    = max(1, min(28, jour_mois))
        planif.heure        = heure
        planif.active       = True
        planif.prochaine_execution = planif.calculer_prochaine_execution()
        planif.save()

        messages.success(request,
            f'✅ Planification enregistrée — prochain envoi le '
            f'{planif.prochaine_execution.strftime("%A %d %B %Y à %Hh%M") if planif.prochaine_execution else "N/A"}.'
        )
        return redirect('admin:newsletter_planification')

    def vue_planification_supprimer(self, request):
        """Désactive la planification newsletter."""
        from .models import PlanificationNewsletter
        from django.shortcuts import redirect

        if request.method != 'POST':
            return redirect('admin:newsletter_planification')

        planif = PlanificationNewsletter.singleton()
        planif.active = False
        planif.prochaine_execution = None
        planif.save(update_fields=['active', 'prochaine_execution'])

        messages.success(request, '✅ Planification désactivée.')
        return redirect('admin:newsletter_planification')

    def vue_envoyer_maintenant(self, request):
        """Déclenche la commande envoyer_newsletter_offres depuis l'admin."""
        from django.core.management import call_command
        from django.shortcuts import redirect
        import io

        buf = io.StringIO()
        try:
            call_command('envoyer_newsletter_offres', stdout=buf)
            sortie = buf.getvalue()
            resume = ' | '.join(
                l.strip() for l in sortie.splitlines()
                if any(mot in l for mot in ('Envoyés', 'Ignorés', 'Erreurs'))
            )
            messages.success(request, f'📨 Newsletter envoyée. {resume}')
        except Exception as e:
            messages.error(request, f'Erreur lors de l\'envoi : {e}')

        return redirect('admin:newsletter_planification')

    @admin.action(description='📨 Envoyer les offres de la semaine aux abonnés sélectionnés')
    def action_envoyer_offres_semaine(self, request, queryset):
        from candidat.management.commands.envoyer_newsletter_offres import (
            _top_offres_generales, _top_offres_candidat, _envoyer_email
        )
        from candidat.models import LogoSite
        from entreprise.models import OffreEmploi, StatutOffre
        from datetime import timedelta

        depuis = timezone.now() - timedelta(days=30)
        offres_liste = list(
            OffreEmploi.objects
            .filter(statutOffre=StatutOffre.PUBLIEE, datePublication__gte=depuis)
            .select_related('entreprise')
        )
        offres_generales = _top_offres_generales(offres_liste, nb=5)
        logo_site = LogoSite.get_actif()

        envoyes, erreurs = 0, 0
        for abonne in queryset.filter(actif=True, offres_semaine=True):
            offres = (
                _top_offres_candidat(abonne.candidat, offres_liste, nb=5)
                if abonne.candidat else offres_generales
            )
            if not offres:
                continue
            try:
                _envoyer_email(abonne, offres, logo_site)
                envoyes += 1
            except Exception:
                erreurs += 1

        self.message_user(
            request,
            f'{envoyes} email(s) envoyé(s). {erreurs} erreur(s).',
            level='SUCCESS' if not erreurs else 'WARNING',
        )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['url_envoyer_offres'] = 'envoyer-offres-semaine/'
        from django.urls import reverse
        extra_context['url_planification'] = reverse('admin:newsletter_planification')
        planif = PlanificationNewsletter.singleton()
        extra_context['planif_active'] = planif.active
        extra_context['planif_prochaine'] = planif.prochaine_execution
        qs = self.get_queryset(request)
        total   = qs.count()
        actifs  = qs.filter(actif=True).count()
        inscrits = qs.filter(candidat__isnull=False).count()
        extra_context['newsletter_stats'] = {
            'total':    total,
            'actifs':   actifs,
            'anonymes': actifs - qs.filter(actif=True, candidat__isnull=False).count(),
            'inscrits': qs.filter(actif=True, candidat__isnull=False).count(),
            'offres_semaine':      qs.filter(actif=True, offres_semaine=True).count(),
            'conseils':            qs.filter(actif=True, conseils=True).count(),
            'actualites':          qs.filter(actif=True, actualites=True).count(),
            'offres_perso':        qs.filter(actif=True, offres_perso=True).count(),
            'profil_consulte':     qs.filter(actif=True, profil_consulte=True).count(),
            'resume_candidatures': qs.filter(actif=True, resume_candidatures=True).count(),
        }
        return super().changelist_view(request, extra_context=extra_context)

    @admin.display(description='Statut')
    def statut_badge(self, obj):
        if obj.actif:
            return mark_safe('<span style="color:#009A44;font-weight:700;">✓ Actif</span>')
        return mark_safe('<span style="color:#ef4444;font-weight:700;">✗ Désabonné</span>')

    @admin.display(description='Type')
    def type_abonne(self, obj):
        if obj.candidat_id:
            return mark_safe('<span style="color:#3b82f6;font-weight:600;">👤 Candidat</span>')
        return mark_safe('<span style="color:#6b7280;">👁 Anonyme</span>')

    @admin.display(description='Préférences')
    def prefs_badge(self, obj):
        icones = []
        if obj.offres_semaine:      icones.append('📋')
        if obj.conseils:            icones.append('💡')
        if obj.actualites:          icones.append('📰')
        if obj.offres_perso:        icones.append('🎯')
        if obj.profil_consulte:     icones.append('👀')
        if obj.resume_candidatures: icones.append('📊')
        if not icones:
            return mark_safe('<span style="color:#9ca3af;font-size:11px;">Aucune</span>')
        return mark_safe(' '.join(icones))


@admin.register(ConseilNewsletter)
class ConseilNewsletterAdmin(admin.ModelAdmin):
    list_display  = ['titre', 'categorie_badge', 'statut_badge', 'nb_destinataires', 'date_envoi_reel', 'date_envoi_prevu']
    list_filter   = ['statut', 'categorie']
    search_fields = ['titre', 'contenu']
    ordering      = ['-date_creation']
    readonly_fields = ['statut', 'date_envoi_reel', 'nb_destinataires', 'envoye_par', 'date_creation', 'date_modification']
    actions       = ['action_envoyer_maintenant']
    fieldsets = (
        (None, {
            'fields': ('titre', 'categorie', 'contenu'),
        }),
        ('Planification (Option B)', {
            'fields': ('date_envoi_prevu',),
            'description': 'Définissez une date pour l\'envoi automatique par la commande planifiée.',
        }),
        ('Suivi', {
            'fields': ('statut', 'date_envoi_reel', 'nb_destinataires', 'envoye_par', 'date_creation', 'date_modification'),
            'classes': ('collapse',),
        }),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('composer/',
                 self.admin_site.admin_view(self.vue_composer),
                 name='conseil_composer'),
            path('<int:conseil_id>/modifier/',
                 self.admin_site.admin_view(self.vue_modifier),
                 name='conseil_modifier'),
        ]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        from django.urls import reverse
        extra_context['url_composer'] = reverse('admin:conseil_composer')
        return super().changelist_view(request, extra_context=extra_context)

    def vue_composer(self, request, conseil_id=None):
        from candidat.models import AbonneNewsletter
        from django.shortcuts import redirect

        conseil = None
        nb_conseils   = AbonneNewsletter.objects.filter(actif=True, conseils=True).count()
        nb_actualites = AbonneNewsletter.objects.filter(actif=True, actualites=True).count()

        # Pré-sélection de catégorie via ?categorie=ACTUALITE
        categorie_preselect = request.GET.get('categorie', '')

        if request.method == 'POST':
            return self._traiter_formulaire(request, conseil)

        return render(request, 'candidat/admin/conseil_composer.html', {
            **self.admin_site.each_context(request),
            'title':               'Nouveau contenu',
            'titre_page':          'Actualité de la plateforme' if categorie_preselect == 'ACTUALITE' else 'Composer un conseil',
            'conseil':             None,
            'nb_conseils':         nb_conseils,
            'nb_actualites':       nb_actualites,
            'categorie_preselect': categorie_preselect,
            'messages':            messages.get_messages(request),
        })

    def vue_modifier(self, request, conseil_id):
        from candidat.models import AbonneNewsletter
        from django.shortcuts import get_object_or_404, redirect

        conseil       = get_object_or_404(ConseilNewsletter, pk=conseil_id)
        nb_conseils   = AbonneNewsletter.objects.filter(actif=True, conseils=True).count()
        nb_actualites = AbonneNewsletter.objects.filter(actif=True, actualites=True).count()

        if request.method == 'POST':
            return self._traiter_formulaire(request, conseil)

        return render(request, 'candidat/admin/conseil_composer.html', {
            **self.admin_site.each_context(request),
            'title':         f'Modifier — {conseil.titre}',
            'titre_page':    'Modifier le contenu',
            'conseil':       conseil,
            'nb_conseils':   nb_conseils,
            'nb_actualites': nb_actualites,
            'messages':      messages.get_messages(request),
        })

    def _traiter_formulaire(self, request, conseil=None):
        from django.shortcuts import redirect
        from candidat.models import AbonneNewsletter, LogoSite

        titre     = request.POST.get('titre', '').strip()
        contenu   = request.POST.get('contenu', '').strip()
        categorie = request.POST.get('categorie', ConseilNewsletter.Categorie.CV)
        action    = request.POST.get('action', 'brouillon')
        date_str  = request.POST.get('date_envoi_prevu', '').strip()

        if not titre or not contenu:
            messages.error(request, 'Le titre et le contenu sont obligatoires.')
            redirect_url = 'admin:conseil_modifier' if conseil else 'admin:conseil_composer'
            if conseil:
                from django.urls import reverse
                return redirect(reverse(redirect_url, args=[conseil.pk]))
            return redirect(redirect_url)

        if conseil is None:
            conseil = ConseilNewsletter()

        conseil.titre          = titre
        conseil.contenu        = contenu
        conseil.categorie      = categorie
        conseil.legende_image  = request.POST.get('legende_image', '').strip()

        # Image uploadée
        if 'image' in request.FILES:
            conseil.image = request.FILES['image']
        elif request.POST.get('supprimer_image'):
            if conseil.image:
                conseil.image.delete(save=False)
            conseil.image = None

        # Date planifiée
        if date_str:
            try:
                from django.utils.dateparse import parse_datetime
                conseil.date_envoi_prevu = parse_datetime(date_str)
            except Exception:
                conseil.date_envoi_prevu = None
        else:
            conseil.date_envoi_prevu = None

        if action == 'envoyer_maintenant':
            filtre  = {'conseils': True, 'actif': True}
            abonnes = list(AbonneNewsletter.objects.filter(**filtre))
            logo_site = LogoSite.get_actif()
            envoyes, erreurs = 0, 0
            for abonne in abonnes:
                try:
                    from candidat.management.commands.envoyer_newsletter_conseils import _envoyer_email
                    _envoyer_email(abonne, conseil, logo_site)
                    envoyes += 1
                except Exception:
                    erreurs += 1

            conseil.statut           = ConseilNewsletter.Statut.ENVOYE
            conseil.date_envoi_reel  = timezone.now()
            conseil.nb_destinataires = envoyes
            conseil.envoye_par       = request.user if request.user.is_authenticated else None
            conseil.save()
            messages.success(request,
                f'✅ Conseil envoyé à {envoyes} abonné(s).'
                + (f' {erreurs} erreur(s).' if erreurs else '')
            )

        elif action == 'planifier' and conseil.date_envoi_prevu:
            conseil.statut = ConseilNewsletter.Statut.PLANIFIE
            conseil.save()
            messages.success(request,
                f'📅 Conseil planifié pour le {conseil.date_envoi_prevu.strftime("%d/%m/%Y à %Hh%M")}.'
            )
        else:
            conseil.statut = ConseilNewsletter.Statut.BROUILLON
            conseil.save()
            messages.success(request, '💾 Conseil enregistré en brouillon.')

        return redirect('admin:candidat_conseilnewsletter_changelist')

    @admin.action(description='🚀 Envoyer maintenant aux abonnés "Conseils"')
    def action_envoyer_maintenant(self, request, queryset):
        from candidat.models import AbonneNewsletter, LogoSite
        from candidat.management.commands.envoyer_newsletter_conseils import _envoyer_email

        non_envoyes = queryset.exclude(statut=ConseilNewsletter.Statut.ENVOYE)
        if not non_envoyes.exists():
            self.message_user(request, 'Tous les conseils sélectionnés sont déjà envoyés.', level='WARNING')
            return

        abonnes       = list(AbonneNewsletter.objects.filter(conseils=True, actif=True))
        logo_site     = LogoSite.get_actif()
        total_envoyes = 0
        nb_conseils   = 0

        for conseil in non_envoyes:
            envoyes = 0
            for abonne in abonnes:
                try:
                    _envoyer_email(abonne, conseil, logo_site)
                    envoyes += 1
                except Exception:
                    pass
            conseil.statut           = ConseilNewsletter.Statut.ENVOYE
            conseil.date_envoi_reel  = timezone.now()
            conseil.nb_destinataires = envoyes
            conseil.envoye_par       = request.user if request.user.is_authenticated else None
            conseil.save(update_fields=['statut', 'date_envoi_reel', 'nb_destinataires', 'envoye_par'])
            total_envoyes += envoyes
            nb_conseils   += 1

        self.message_user(request,
            f'✅ {nb_conseils} conseil(s) envoyé(s) à {len(abonnes)} abonné(s) ({total_envoyes} emails au total).'
        )

    @admin.display(description='Catégorie')
    def categorie_badge(self, obj):
        couleurs = {
            'CV':         ('background:#dbeafe;color:#1e40af', '📄'),
            'ENTRETIEN':  ('background:#fce7f3;color:#9d174d', '🎤'),
            'CARRIERE':   ('background:#ede9fe;color:#5b21b6', '🚀'),
            'PLATEFORME': ('background:#fef9c3;color:#854d0e', '💡'),
            'ACTUALITE':  ('background:#dcfce7;color:#166534', '📰'),
        }
        style, icone = couleurs.get(obj.categorie, ('background:#f3f4f6;color:#374151', '📌'))
        return mark_safe(
            f'<span style="display:inline-flex;align-items:center;gap:4px;{style};'
            f'padding:2px 10px;border-radius:999px;font-size:11px;font-weight:700;">'
            f'{icone} {obj.get_categorie_display()}</span>'
        )

    @admin.display(description='Statut')
    def statut_badge(self, obj):
        cfg = {
            'BROUILLON': ('color:#6b7280;font-weight:600', '✎ Brouillon'),
            'PLANIFIE':  ('color:#F77F00;font-weight:700', '📅 Planifié'),
            'ENVOYE':    ('color:#009A44;font-weight:700', '✓ Envoyé'),
        }
        style, label = cfg.get(obj.statut, ('color:#374151', obj.statut))
        return mark_safe(f'<span style="{style}">{label}</span>')


# ─── Actualités newsletter ────────────────────────────────────────────────────

@admin.register(ActualiteNewsletter)
class ActualiteNewsletterAdmin(admin.ModelAdmin):
    list_display  = ['titre', 'statut_badge', 'apercu_image', 'nb_destinataires', 'date_envoi_reel', 'date_envoi_prevu']
    list_filter   = ['statut']
    search_fields = ['titre', 'contenu']
    ordering      = ['-date_creation']
    readonly_fields = ['statut', 'date_envoi_reel', 'nb_destinataires', 'envoye_par', 'date_creation', 'date_modification']
    actions       = ['action_envoyer_maintenant']
    fieldsets = (
        (None, {
            'fields': ('titre', 'contenu', 'image', 'legende_image'),
        }),
        ('Planification', {
            'fields': ('date_envoi_prevu',),
            'description': "Définissez une date pour l'envoi automatique planifié.",
        }),
        ('Suivi', {
            'fields': ('statut', 'date_envoi_reel', 'nb_destinataires', 'envoye_par', 'date_creation', 'date_modification'),
            'classes': ('collapse',),
        }),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('composer/',
                 self.admin_site.admin_view(self.vue_composer),
                 name='actualite_composer'),
            path('<int:actualite_id>/modifier/',
                 self.admin_site.admin_view(self.vue_modifier),
                 name='actualite_modifier'),
        ]
        return custom + urls

    def vue_composer(self, request):
        from django.shortcuts import redirect
        nb_abonnes = AbonneNewsletter.objects.filter(actif=True, actualites=True).count()
        if request.method == 'POST':
            return self._traiter_formulaire(request, None)
        return render(request, 'candidat/admin/actualite_composer.html', {
            **self.admin_site.each_context(request),
            'title':      'Nouvelle actualité',
            'titre_page': 'Composer une actualité',
            'actualite':  None,
            'nb_abonnes': nb_abonnes,
            'messages':   messages.get_messages(request),
        })

    def vue_modifier(self, request, actualite_id):
        from django.shortcuts import get_object_or_404, redirect
        actualite  = get_object_or_404(ActualiteNewsletter, pk=actualite_id)
        nb_abonnes = AbonneNewsletter.objects.filter(actif=True, actualites=True).count()
        if request.method == 'POST':
            return self._traiter_formulaire(request, actualite)
        return render(request, 'candidat/admin/actualite_composer.html', {
            **self.admin_site.each_context(request),
            'title':      f'Modifier — {actualite.titre}',
            'titre_page': 'Modifier l\'actualité',
            'actualite':  actualite,
            'nb_abonnes': nb_abonnes,
            'messages':   messages.get_messages(request),
        })

    def _traiter_formulaire(self, request, actualite=None):
        from django.shortcuts import redirect
        from candidat.models import LogoSite, _StatutNewsletter

        titre    = request.POST.get('titre', '').strip()
        contenu  = request.POST.get('contenu', '').strip()
        action   = request.POST.get('action', 'brouillon')
        date_str = request.POST.get('date_envoi_prevu', '').strip()

        if not titre or not contenu:
            messages.error(request, 'Le titre et le contenu sont obligatoires.')
            return redirect('admin:actualite_composer')

        if actualite is None:
            actualite = ActualiteNewsletter()

        actualite.titre         = titre
        actualite.contenu       = contenu
        actualite.legende_image = request.POST.get('legende_image', '').strip()

        if 'image' in request.FILES:
            actualite.image = request.FILES['image']
        elif request.POST.get('supprimer_image') and actualite.image:
            actualite.image.delete(save=False)
            actualite.image = None

        if date_str:
            try:
                from django.utils.dateparse import parse_datetime
                actualite.date_envoi_prevu = parse_datetime(date_str)
            except Exception:
                actualite.date_envoi_prevu = None
        else:
            actualite.date_envoi_prevu = None

        if action == 'envoyer_maintenant':
            abonnes   = list(AbonneNewsletter.objects.filter(actif=True, actualites=True))
            logo_site = LogoSite.get_actif()
            envoyes, erreurs = 0, 0
            for abonne in abonnes:
                try:
                    from candidat.management.commands.envoyer_newsletter_actualites import _envoyer_email
                    _envoyer_email(abonne, actualite, logo_site)
                    envoyes += 1
                except Exception:
                    erreurs += 1

            actualite.statut           = _StatutNewsletter.ENVOYE
            actualite.date_envoi_reel  = timezone.now()
            actualite.nb_destinataires = envoyes
            actualite.envoye_par       = request.user if request.user.is_authenticated else None
            actualite.save()
            messages.success(request,
                f'✅ Actualité envoyée à {envoyes} abonné(s).'
                + (f' {erreurs} erreur(s).' if erreurs else '')
            )

        elif action == 'planifier' and actualite.date_envoi_prevu:
            actualite.statut = _StatutNewsletter.PLANIFIE
            actualite.save()
            messages.success(request,
                f'📅 Actualité planifiée pour le {actualite.date_envoi_prevu.strftime("%d/%m/%Y à %Hh%M")}.'
            )
        else:
            actualite.statut = _StatutNewsletter.BROUILLON
            actualite.save()
            messages.success(request, '💾 Actualité enregistrée en brouillon.')

        return redirect('admin:candidat_actualitenewsletter_changelist')

    @admin.action(description='🚀 Envoyer maintenant aux abonnés "Actualités"')
    def action_envoyer_maintenant(self, request, queryset):
        from candidat.models import LogoSite, _StatutNewsletter
        from candidat.management.commands.envoyer_newsletter_actualites import _envoyer_email

        abonnes       = list(AbonneNewsletter.objects.filter(actif=True, actualites=True))
        logo_site     = LogoSite.get_actif()
        total_envoyes = 0

        for actualite in queryset.exclude(statut=_StatutNewsletter.ENVOYE):
            envoyes = 0
            for abonne in abonnes:
                try:
                    _envoyer_email(abonne, actualite, logo_site)
                    envoyes += 1
                except Exception:
                    pass
            actualite.statut           = _StatutNewsletter.ENVOYE
            actualite.date_envoi_reel  = timezone.now()
            actualite.nb_destinataires = envoyes
            actualite.envoye_par       = request.user if request.user.is_authenticated else None
            actualite.save(update_fields=['statut', 'date_envoi_reel', 'nb_destinataires', 'envoye_par'])
            total_envoyes += envoyes

        self.message_user(request, f'✅ Actualités envoyées à {len(abonnes)} abonné(s) ({total_envoyes} emails).')

    @admin.display(description='Statut')
    def statut_badge(self, obj):
        cfg = {
            'BROUILLON': ('color:#6b7280;font-weight:600', '✎ Brouillon'),
            'PLANIFIE':  ('color:#F77F00;font-weight:700', '📅 Planifié'),
            'ENVOYE':    ('color:#009A44;font-weight:700', '✓ Envoyé'),
        }
        style, label = cfg.get(obj.statut, ('color:#374151', obj.statut))
        return mark_safe(f'<span style="{style}">{label}</span>')

    @admin.display(description='Image')
    def apercu_image(self, obj):
        if obj.image:
            return mark_safe(
                f'<img src="{obj.image.url}" style="height:36px;border-radius:4px;object-fit:cover;">'
            )
        return '—'


def _mois_labels_data(qs, year_field, month_field, nb_mois=6):
    """Construit labels + données mensuels sur nb_mois mois."""
    MOIS = ['', 'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']
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
        labels.append(f"{jour} {MOIS[m]}")
        data.append(mois_map.get((y, m), 0))
    return labels, data


# ─── Informations personnelles ────────────────────────────────────────────────

@admin.register(InformationPersonnelle)
class InformationPersonnelleAdmin(admin.ModelAdmin):
    list_display  = ['__str__', 'ville', 'telephone', 'sexe']
    list_filter   = ['sexe']
    search_fields = ['nom', 'prenom', 'email', 'ville']
    readonly_fields = ['photoProfil']
    fieldsets = (
        ('Identité', {
            'fields': ('nom', 'prenom', 'dateNaissance', 'sexe', 'nationalite', 'photoProfil'),
        }),
        ('Contact', {
            'fields': ('email', 'telephone', 'adresse', 'ville'),
        }),
    )


# ─── Rubriques profil (inlines pour CandidatAdmin) ───────────────────────────

class FormationInline(admin.TabularInline):
    model  = Formation
    extra  = 0
    fields = ['typeSortie', 'diplomeLibre', 'ecoleLibre', 'dateDebut', 'dateFin', 'enCours']
    autocomplete_fields = ['diplomeRef', 'domaine', 'niveauEtude', 'institution', 'pays']
    show_change_link = True


class ExperienceInline(admin.TabularInline):
    model  = ExperienceProfessionnelle
    extra  = 0
    fields = ['entrepriseLibre', 'paysLibre', 'ville', 'dateDebut', 'dateFin', 'enCours']
    autocomplete_fields = ['entreprise', 'pays']
    show_change_link = True


class CompetenceInline(admin.TabularInline):
    model  = Competence
    extra  = 0
    fields = ['nomLibre', 'typeCompetence', 'niveau', 'valeurEtoiles', 'estVisiblePortfolio']
    autocomplete_fields = ['typeCompetence', 'niveau']


class CandidatLangueInline(admin.TabularInline):
    model  = CandidatLangue
    extra  = 0
    fields = ['nomLibre', 'langue', 'niveau', 'niveauCode', 'estVisiblePortfolio']
    autocomplete_fields = ['langue', 'niveau']


class CentreInteretInline(admin.TabularInline):
    model  = CentreInteret
    extra  = 0
    fields = ['libelleLibre', 'typeCentreInteret', 'estVisiblePortfolio']
    autocomplete_fields = ['typeCentreInteret']


class ProjetInline(admin.TabularInline):
    model  = Projet
    extra  = 0
    fields = ['titre', 'dateDebut', 'dateFin', 'urlDemo', 'estVisiblePortfolio']
    show_change_link = True


class BenevolatInline(admin.TabularInline):
    model  = Benevolat
    extra  = 0
    fields = ['titre', 'organisation', 'dateDebut', 'dateFin', 'enCours']
    show_change_link = True


class PosteOccupeInline(admin.TabularInline):
    model  = PosteOccupe
    extra  = 0
    fields = ['titreLibre', 'poste', 'dateDebut', 'dateFin', 'enCours', 'ordre']
    autocomplete_fields = ['poste']


class MissionClientInline(admin.TabularInline):
    model  = MissionClient
    extra  = 0
    fields = ['clientLibre', 'client', 'ville', 'dateDebut', 'dateFin', 'enCours']
    autocomplete_fields = ['client', 'pays']


# ─── Candidats ────────────────────────────────────────────────────────────────

@admin.register(Candidat)
class CandidatAdmin(admin.ModelAdmin):
    inlines         = [
        ExperienceInline, FormationInline,
        CompetenceInline, CandidatLangueInline,
        ProjetInline, BenevolatInline, CentreInteretInline,
    ]
    list_display    = ['__str__', 'get_ville', 'titreProfessionnel', 'typeMobilite', 'date_joined']
    list_filter     = ['typeMobilite', 'portfolioPublic', 'sexe']
    search_fields   = ['prenom', 'nom', 'email', 'titreProfessionnel']
    readonly_fields = ['date_joined', 'derniereConnexion']
    list_select_related = ['sexe', 'typeMobilite', 'informationPersonnelle']
    autocomplete_fields = ['sexe', 'typeMobilite', 'typePermis']

    fieldsets = (
        ('Identité', {
            'fields': ('nom', 'prenom', 'dateNaissance', 'sexe', 'photoProfil'),
        }),
        ('Contact', {
            'fields': ('email', 'telephone', 'adresse'),
        }),
        ('Authentification', {
            'fields': ('emailVerifie', 'tokenReset'),
        }),
        ('Profil professionnel', {
            'fields': ('titreProfessionnel', 'biographie', 'datePremierEmploi', 'secteurActivite', 'typeContratRecherche'),
        }),
        ('Mobilité & permis', {
            'fields': ('typeMobilite', 'typePermis'),
        }),
        ('Portfolio', {
            'fields': ('portfolioPublic', 'portfolioModele', 'sloganPortfolio', 'couleurPortfolio'),
        }),
        ('Métadonnées', {
            'fields': ('date_joined', 'derniereConnexion', 'informationPersonnelle'),
        }),
    )

    @admin.display(description='Ville')
    def get_ville(self, obj):
        info = obj.informationPersonnelle
        return (info.ville if info else '') or '—'

    def get_urls(self):
        urls = super().get_urls()
        return [
            path('stats/', self.admin_site.admin_view(self.stats_view), name='candidat_candidat_stats'),
        ] + urls

    def stats_view(self, request):
        from referentiel.models import Contrat as ContratRef
        aujourd_hui = timezone.now().date()
        il_y_a_30j  = aujourd_hui - timedelta(days=30)
        il_y_a_7j   = aujourd_hui - timedelta(days=7)

        total   = Candidat.objects.count()
        actifs  = Candidat.objects.filter(statutCompte='ACTIF').count() if hasattr(Candidat, 'statutCompte') else total
        new_7j  = Candidat.objects.filter(date_joined__date__gte=il_y_a_7j).count()
        new_30j = Candidat.objects.filter(date_joined__date__gte=il_y_a_30j).count()

        # ── Mobilité : typeMobilite (FK actif) + fallback legacy mobilite ────
        # Candidats avec typeMobilite renseigné
        par_mob_fk = {
            r['typeMobilite__libelle']: r['n']
            for r in Candidat.objects
                .filter(typeMobilite__isnull=False)
                .values('typeMobilite__libelle')
                .annotate(n=Count('id'))
                .order_by('-n')
        }
        # Candidats sans typeMobilite → utiliser champ legacy mobilite
        for r in (Candidat.objects
                  .filter(typeMobilite__isnull=True)
                  .exclude(mobilite='')
                  .values('mobilite')
                  .annotate(n=Count('id'))):
            label = dict(Mobilite.choices).get(r['mobilite'], r['mobilite']) or '—'
            par_mob_fk[label] = par_mob_fk.get(label, 0) + r['n']
        # Trier par valeur décroissante, exclure les 0
        par_mob_sorted  = sorted(par_mob_fk.items(), key=lambda x: -x[1])
        labels_mobilite = [k for k, v in par_mob_sorted if v > 0]
        data_mobilite   = [v for k, v in par_mob_sorted if v > 0]

        # ── Disponibilité : proxy via typeContratRecherche ───────────────────
        en_recherche   = Candidat.objects.filter(typeContratRecherche__isnull=False).count()
        sans_recherche = total - en_recherche
        labels_dispo = []
        data_dispo   = []
        if en_recherche:
            labels_dispo.append('En recherche active')
            data_dispo.append(en_recherche)
        if sans_recherche:
            labels_dispo.append('Profil en veille')
            data_dispo.append(sans_recherche)

        # ── Type de contrat recherché ────────────────────────────────────────
        par_contrat_qs = list(
            ContratRef.objects
            .annotate(n=Count('candidats_recherchant'))
            .order_by('-n', 'libelle')
            .values('libelle', 'n')
        )
        labels_contrat = [r['libelle'] or '—' for r in par_contrat_qs]
        data_contrat   = [r['n'] for r in par_contrat_qs]

        # ── Inscriptions par mois ────────────────────────────────────────────
        inscrits_qs = (
            Candidat.objects
            .values('date_joined__year', 'date_joined__month')
            .annotate(n=Count('id'))
        )
        mois_labels, mois_data = _mois_labels_data(
            inscrits_qs, 'date_joined__year', 'date_joined__month', 6
        )

        context = {
            **self.admin_site.each_context(request),
            'title':          'Statistiques — Candidats',
            'total':          total,
            'actifs':         actifs if actifs > 0 else total,
            'new_7j':         new_7j,
            'new_30j':        new_30j,
            'labels_statut':  json.dumps(labels_mobilite, ensure_ascii=False),
            'data_statut':    json.dumps(data_mobilite),
            'labels_dispo':   json.dumps(labels_dispo, ensure_ascii=False),
            'data_dispo':     json.dumps(data_dispo),
            'labels_contrat': json.dumps(labels_contrat, ensure_ascii=False),
            'data_contrat':   json.dumps(data_contrat),
            'mois_labels':    json.dumps(mois_labels, ensure_ascii=False),
            'mois_data':      json.dumps(mois_data),
        }
        return TemplateResponse(request, 'admin/candidat/candidat/stats.html', context)


# ─── Rubriques (admin standalone) ─────────────────────────────────────────────

@admin.register(ExperienceProfessionnelle)
class ExperienceProfessionnelleAdmin(admin.ModelAdmin):
    list_display    = ['__str__', 'candidat', 'entreprise', 'paysLibre', 'ville', 'dateDebut', 'dateFin', 'enCours']
    list_filter     = ['enCours', 'estVisiblePortfolio']
    search_fields   = ['entrepriseLibre', 'paysLibre', 'ville', 'description', 'candidat__nom', 'candidat__prenom']
    autocomplete_fields = ['candidat', 'entreprise', 'pays']
    inlines         = [PosteOccupeInline, MissionClientInline]


@admin.register(Formation)
class FormationAdmin(admin.ModelAdmin):
    list_display    = ['__str__', 'candidat', 'typeSortie', 'dateDebut', 'dateFin', 'enCours']
    list_filter     = ['typeSortie', 'enCours', 'estVisiblePortfolio']
    search_fields   = ['diplomeLibre', 'ecoleLibre', 'description', 'candidat__nom', 'candidat__prenom']
    autocomplete_fields = ['candidat', 'diplomeRef', 'domaine', 'niveauEtude', 'institution', 'pays']


@admin.register(Competence)
class CompetenceAdmin(admin.ModelAdmin):
    list_display    = ['__str__', 'candidat', 'valeurEtoiles', 'estVisiblePortfolio']
    list_filter     = ['valeurEtoiles', 'estVisiblePortfolio']
    search_fields   = ['nomLibre', 'candidat__nom', 'candidat__prenom']
    autocomplete_fields = ['candidat', 'typeCompetence', 'niveau']


@admin.register(CandidatLangue)
class CandidatLangueAdmin(admin.ModelAdmin):
    list_display    = ['__str__', 'candidat', 'niveauCode', 'estVisiblePortfolio']
    list_filter     = ['niveauCode', 'estVisiblePortfolio']
    search_fields   = ['nomLibre', 'candidat__nom', 'candidat__prenom']
    autocomplete_fields = ['candidat', 'langue', 'niveau']


@admin.register(CentreInteret)
class CentreInteretAdmin(admin.ModelAdmin):
    list_display    = ['__str__', 'candidat', 'estVisiblePortfolio']
    search_fields   = ['libelleLibre', 'candidat__nom', 'candidat__prenom']
    autocomplete_fields = ['candidat', 'typeCentreInteret']


@admin.register(Projet)
class ProjetAdmin(admin.ModelAdmin):
    list_display    = ['titre', 'candidat', 'dateDebut', 'dateFin', 'estVisiblePortfolio']
    list_filter     = ['estVisiblePortfolio']
    search_fields   = ['titre', 'realisation', 'contexte', 'candidat__nom', 'candidat__prenom']
    autocomplete_fields = ['candidat', 'experienceProfessionnelle']


@admin.register(Benevolat)
class BenevolatAdmin(admin.ModelAdmin):
    list_display    = ['__str__', 'candidat', 'dateDebut', 'dateFin', 'enCours']
    list_filter     = ['enCours', 'estVisiblePortfolio']
    search_fields   = ['titre', 'organisation', 'candidat__nom', 'candidat__prenom']
    autocomplete_fields = ['candidat']
    filter_horizontal = ['competences']


# ─── CV sauvegardés ───────────────────────────────────────────────────────────

class PhotoCVInline(admin.TabularInline):
    model         = PhotoCV
    extra         = 0
    readonly_fields = ['numeroPage', 'apercu']
    fields        = ['numeroPage', 'apercu', 'image']

    @admin.display(description='Aperçu')
    def apercu(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:80px;border-radius:4px;'
                'box-shadow:0 1px 4px rgba(0,0,0,.15)">', obj.image.url,
            )
        return '—'


@admin.register(CV)
class CVAdmin(admin.ModelAdmin):
    list_display       = ['__str__', 'nomCv', 'candidat', 'modele', 'archive', 'dateModification']
    list_filter        = ['archive', 'modele']
    search_fields      = ['nomCv', 'titre', 'candidat__nom', 'candidat__prenom', 'candidat__email']
    autocomplete_fields = ['candidat', 'modele', 'contenu']
    readonly_fields    = ['dateCreation', 'dateModification']
    inlines            = [PhotoCVInline]


@admin.register(CVContenu)
class CVContenuAdmin(admin.ModelAdmin):
    list_display       = ['__str__']
    search_fields      = ['id']
    filter_horizontal  = ['formations', 'experiences', 'competences', 'langues',
                          'interets', 'projets', 'benevolats']


@admin.register(PhotoCV)
class PhotoCVAdmin(admin.ModelAdmin):
    list_display    = ['__str__', 'cv', 'numeroPage']
    list_filter     = ['cv']
    autocomplete_fields = ['cv']


# ─── Témoignages ─────────────────────────────────────────────────────────────

@admin.register(Temoignage)
class TemoignageAdmin(admin.ModelAdmin):
    """Témoignages publiés et rejetés — gestion éditoriale."""
    list_display  = ['photo_miniature', 'prenom_nom', 'statut_badge', 'source_badge',
                     'note_etoiles', 'style', 'ordre', 'date_soumission']
    list_editable = ['ordre']
    list_filter   = ['statut', 'source', 'style']
    search_fields = ['prenom_nom', 'texte', 'titre_poste']
    ordering      = ['ordre', '-date_soumission']
    readonly_fields = ['date_soumission', 'candidat_lien', 'photo_profil_apercu']
    actions       = ['action_publier', 'action_rejeter']
    list_per_page = 20

    fieldsets = (
        ('Contenu', {
            'fields': ('prenom_nom', 'titre_poste', 'texte', 'note'),
        }),
        ('Affichage', {
            'fields': ('style', 'ordre'),
        }),
        ('Modération', {
            'fields': ('statut', 'source', 'candidat_lien', 'photo_profil_apercu', 'date_soumission'),
        }),
    )

    def has_module_perms(self, request):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            statut__in=[Temoignage.STATUT_PUBLIE, Temoignage.STATUT_REJETE]
        )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.source = Temoignage.SOURCE_ADMIN
            if obj.statut == Temoignage.STATUT_EN_ATTENTE:
                obj.statut = Temoignage.STATUT_PUBLIE
        super().save_model(request, obj, form, change)

    @admin.display(description='Photo')
    def photo_miniature(self, obj):
        if obj.candidat and obj.candidat.photoProfil:
            return format_html(
                '<img src="{}" style="width:36px;height:36px;border-radius:50%;object-fit:cover;">',
                obj.candidat.photoProfil.url,
            )
        initiales = (obj.prenom_nom or '??')[:2].upper()
        couleur = '#009A44' if obj.style == 'vert' else '#F77F00'
        return format_html(
            '<div style="width:36px;height:36px;border-radius:50%;background:{};'
            'display:flex;align-items:center;justify-content:center;'
            'color:white;font-weight:700;font-size:12px;">{}</div>',
            couleur, initiales,
        )

    @admin.display(description='Statut')
    def statut_badge(self, obj):
        couleurs = {
            Temoignage.STATUT_PUBLIE:     ('#009A44', '✓ Publié'),
            Temoignage.STATUT_EN_ATTENTE: ('#F77F00', '⏳ En attente'),
            Temoignage.STATUT_REJETE:     ('#ef4444', '✗ Rejeté'),
        }
        couleur, label = couleurs.get(obj.statut, ('#6b7280', obj.statut))
        return format_html('<span style="color:{};font-weight:700;">{}</span>', couleur, label)

    @admin.display(description='Source')
    def source_badge(self, obj):
        if obj.source == Temoignage.SOURCE_CANDIDAT:
            return mark_safe('<span style="color:#2563EB;font-weight:700;">\U0001f464 Candidat</span>')
        return mark_safe('<span style="color:#6b7280;font-weight:600;">\U0001f6e0 Admin</span>')

    @admin.display(description='Note')
    def note_etoiles(self, obj):
        etoiles = '★' * obj.note + '☆' * (5 - obj.note)
        return format_html('<span style="color:#F77F00;font-size:14px;">{}</span>', etoiles)

    @admin.display(description='Candidat lié')
    def candidat_lien(self, obj):
        if obj.candidat:
            return format_html(
                '<a href="/admin/candidat/candidat/{}/change/">{} {}</a>',
                obj.candidat.pk, obj.candidat.prenom, obj.candidat.nom,
            )
        return '—'

    @admin.display(description='Photo de profil')
    def photo_profil_apercu(self, obj):
        if obj.candidat and obj.candidat.photoProfil:
            return format_html(
                '<img src="{}" style="width:64px;height:64px;border-radius:50%;object-fit:cover;">',
                obj.candidat.photoProfil.url,
            )
        return 'Pas de photo de profil'

    @admin.action(description='✓ Publier les témoignages sélectionnés')
    def action_publier(self, request, queryset):
        nb = queryset.update(statut=Temoignage.STATUT_PUBLIE)
        self.message_user(request, f'{nb} témoignage(s) publié(s).')

    @admin.action(description='✗ Rejeter les témoignages sélectionnés')
    def action_rejeter(self, request, queryset):
        nb = queryset.update(statut=Temoignage.STATUT_REJETE)
        self.message_user(request, f'{nb} témoignage(s) rejeté(s).')


@admin.register(TemoignageEnAttente)
class TemoignageEnAttenteAdmin(TemoignageAdmin):
    """File de modération — témoignages candidats en attente de validation."""
    list_display  = ['photo_miniature', 'prenom_nom', 'source_badge',
                     'note_etoiles', 'titre_poste', 'date_soumission']
    list_editable = []
    list_filter   = ['source']
    ordering      = ['-date_soumission']
    readonly_fields = ['date_soumission', 'candidat_lien', 'photo_profil_apercu', 'statut', 'source']
    actions       = ['action_publier', 'action_rejeter']

    fieldsets = (
        ('Contenu du témoignage', {
            'fields': ('prenom_nom', 'titre_poste', 'texte', 'note'),
        }),
        ('Candidat & informations', {
            'fields': ('statut', 'source', 'candidat_lien', 'photo_profil_apercu', 'date_soumission'),
        }),
    )

    def get_queryset(self, request):
        return Temoignage.objects.filter(
            statut=Temoignage.STATUT_EN_ATTENTE
        ).select_related('candidat')

    def has_add_permission(self, request):
        return False


# ─── Visiteurs journaliers ────────────────────────────────────────────────────

@admin.register(VisiteurJournalier)
class VisiteurJournalierAdmin(admin.ModelAdmin):
    list_display    = ['date', 'nb_visiteurs']
    readonly_fields = ['date', 'nb_visiteurs']
    ordering        = ['-date']
    list_per_page   = 30

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_urls(self):
        urls = super().get_urls()
        return [
            path('stats/', self.admin_site.admin_view(self.stats_view), name='candidat_visiteurjournalier_stats'),
        ] + urls

    def stats_view(self, request):
        aujourd_hui = timezone.now().date()
        il_y_a_7j   = aujourd_hui - timedelta(days=7)
        il_y_a_30j  = aujourd_hui - timedelta(days=30)

        auj_obj    = VisiteurJournalier.objects.filter(date=aujourd_hui).first()
        nb_auj     = auj_obj.nb_visiteurs if auj_obj else 0
        nb_7j      = VisiteurJournalier.objects.filter(date__gte=il_y_a_7j).aggregate(t=Sum('nb_visiteurs'))['t'] or 0
        nb_30j     = VisiteurJournalier.objects.filter(date__gte=il_y_a_30j).aggregate(t=Sum('nb_visiteurs'))['t'] or 0
        total_all  = VisiteurJournalier.objects.aggregate(t=Sum('nb_visiteurs'))['t'] or 0
        record_obj = VisiteurJournalier.objects.order_by('-nb_visiteurs').first()
        record_val  = record_obj.nb_visiteurs if record_obj else 0
        record_date = record_obj.date if record_obj else '—'

        qs_30j  = list(
            VisiteurJournalier.objects.filter(date__gte=il_y_a_30j).order_by('date')
            .values('date', 'nb_visiteurs')
        )
        dates_30  = [aujourd_hui - timedelta(days=i) for i in range(29, -1, -1)]
        map_30    = {r['date']: r['nb_visiteurs'] for r in qs_30j}
        labels_30 = [d.strftime('%d/%m') for d in dates_30]
        data_30   = [map_30.get(d, 0) for d in dates_30]

        labels_sem, data_sem = [], []
        for i in range(11, -1, -1):
            debut     = aujourd_hui - timedelta(days=aujourd_hui.weekday() + 7 * i)
            fin       = debut + timedelta(days=6)
            total_sem = VisiteurJournalier.objects.filter(
                date__gte=debut, date__lte=fin
            ).aggregate(t=Sum('nb_visiteurs'))['t'] or 0
            labels_sem.append(debut.strftime('%d/%m'))
            data_sem.append(total_sem)

        context = {
            **self.admin_site.each_context(request),
            'title':       'Statistiques — Visiteurs',
            'nb_auj':      nb_auj,
            'nb_7j':       nb_7j,
            'nb_30j':      nb_30j,
            'total_all':   total_all,
            'record_val':  record_val,
            'record_date': record_date,
            'labels_30':   json.dumps(labels_30),
            'data_30':     json.dumps(data_30),
            'labels_sem':  json.dumps(labels_sem),
            'data_sem':    json.dumps(data_sem),
        }
        return TemplateResponse(request, 'admin/candidat/visiteurjournalier/stats.html', context)
