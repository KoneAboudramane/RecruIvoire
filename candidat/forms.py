from django import forms
from referentiel.models import SecteurActivite
from .models import Candidat, Candidature, CV, LettreMotivation, TokenConfirmationInscription

INPUT_CLASS    = 'block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 disabled:bg-transparent disabled:border-transparent disabled:shadow-none disabled:cursor-default disabled:p-0 disabled:text-gray-800 disabled:font-medium transition-all'
SELECT_CLASS   = 'block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 disabled:bg-transparent disabled:border-transparent disabled:shadow-none disabled:cursor-default disabled:p-0 disabled:text-gray-800 disabled:font-medium transition-all'
TEXTAREA_CLASS = 'block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 disabled:bg-transparent disabled:border-transparent disabled:shadow-none disabled:cursor-default disabled:p-0 disabled:text-gray-800 disabled:resize-none transition-all'

_I = 'mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500'


# ─── Inscription ──────────────────────────────────────────────────────────────

class InscriptionForm(forms.Form):
    prenom    = forms.CharField(max_length=150, label='Prénom',
                    widget=forms.TextInput(attrs={'class': _I, 'placeholder': 'Votre prénom'}))
    nom       = forms.CharField(max_length=150, label='Nom',
                    widget=forms.TextInput(attrs={'class': _I, 'placeholder': 'Votre nom'}))
    email     = forms.EmailField(label='Adresse email',
                    widget=forms.EmailInput(attrs={'class': _I, 'placeholder': 'exemple@email.com'}))
    password1 = forms.CharField(label='Mot de passe',
                    widget=forms.PasswordInput(attrs={'class': _I, 'placeholder': '••••••••'}))
    password2 = forms.CharField(label='Confirmer le mot de passe',
                    widget=forms.PasswordInput(attrs={'class': _I, 'placeholder': '••••••••'}))
    consentementRGPD = forms.BooleanField(
        required=True,
        label="J'accepte les conditions d'utilisation et la politique de confidentialité",
        widget=forms.CheckboxInput(attrs={'class': 'h-4 w-4 rounded border-gray-300', 'style': 'accent-color:#F77F00;'}),
    )

    # Newsletter — options générales (cochées par défaut)
    nl_offres_semaine = forms.BooleanField(required=False, initial=True, label='Recevoir les meilleures offres chaque semaine',
        widget=forms.CheckboxInput(attrs={'class': 'h-4 w-4 rounded border-gray-300', 'style': 'accent-color:#F77F00;'}))
    nl_conseils       = forms.BooleanField(required=False, initial=True, label='Recevoir des conseils CV et entretien',
        widget=forms.CheckboxInput(attrs={'class': 'h-4 w-4 rounded border-gray-300', 'style': 'accent-color:#F77F00;'}))
    nl_actualites     = forms.BooleanField(required=False, initial=True, label="Recevoir les actualités de la plateforme",
        widget=forms.CheckboxInput(attrs={'class': 'h-4 w-4 rounded border-gray-300', 'style': 'accent-color:#F77F00;'}))

    # Newsletter — options individuelles (cochées par défaut)
    nl_offres_perso        = forms.BooleanField(required=False, initial=True, label='Recevoir des offres correspondant à mon profil',
        widget=forms.CheckboxInput(attrs={'class': 'h-4 w-4 rounded border-gray-300', 'style': 'accent-color:#F77F00;'}))
    nl_profil_consulte     = forms.BooleanField(required=False, initial=True, label='Être notifié(e) quand un recruteur consulte mon profil',
        widget=forms.CheckboxInput(attrs={'class': 'h-4 w-4 rounded border-gray-300', 'style': 'accent-color:#F77F00;'}))
    nl_resume_candidatures = forms.BooleanField(required=False, initial=True, label='Recevoir un résumé hebdomadaire de mes candidatures',
        widget=forms.CheckboxInput(attrs={'class': 'h-4 w-4 rounded border-gray-300', 'style': 'accent-color:#F77F00;'}))

    def clean_email(self):
        email = self.cleaned_data['email']
        candidat_existant = Candidat.objects.filter(email=email).first()

        if candidat_existant:
            if candidat_existant.emailVerifie:
                raise forms.ValidationError('Cette adresse email est déjà utilisée.')
            # Compte en attente de confirmation
            try:
                token = candidat_existant.token_confirmation
                if token.est_valide():
                    raise forms.ValidationError(
                        'Un email de confirmation a déjà été envoyé à cette adresse. '
                        'Vérifiez votre boîte mail (valide 10 minutes).'
                    )
            except TokenConfirmationInscription.DoesNotExist:
                pass
            # Token expiré → on supprime le compte en attente pour permettre la réinscription
            candidat_existant.delete()

        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'Les deux mots de passe ne correspondent pas.')
        if p1 and len(p1) < 8:
            self.add_error('password1', 'Le mot de passe doit contenir au moins 8 caractères.')
        return cleaned


# ─── Connexion ────────────────────────────────────────────────────────────────

class ConnexionForm(forms.Form):
    email      = forms.EmailField(label='Adresse email',
                     widget=forms.EmailInput(attrs={'class': _I, 'placeholder': 'exemple@email.com', 'autofocus': True}))
    motdepasse = forms.CharField(label='Mot de passe',
                     widget=forms.PasswordInput(attrs={'class': _I + ' pr-10', 'placeholder': '••••••••'}))


# ─── Profil — Informations personnelles ───────────────────────────────────────

def _apply_widget_classes(form, edition_flag):
    """Applique les classes Tailwind + x-bind:disabled sur tous les widgets d'un form.

    `edition_flag` est le nom de la variable Alpine.js qui contrôle le mode édition
    (ex : 'editionIdentite' ou 'editionPortfolio').
    """
    bind = '!' + edition_flag
    for name, field in form.fields.items():
        w = field.widget
        w.attrs['x-bind:disabled'] = bind
        if isinstance(w, forms.Textarea):
            w.attrs.setdefault('class', TEXTAREA_CLASS)
        elif isinstance(w, forms.Select):
            w.attrs.setdefault('class', SELECT_CLASS)
        else:
            w.attrs.setdefault('class', INPUT_CLASS)


class InformationPersonnelleForm(forms.ModelForm):
    """
    Formulaire pour les données d'identité et de contact.

    Bind sur Candidat (depuis le refactor Utilisateur), uniquement les
    champs personnels (nom, prenom, email, telephone, adresse, etc.).
    Le champ photoProfil est géré manuellement dans le template (upload custom).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_widget_classes(self, 'editionIdentite')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            return email
        qs = Candidat.objects.filter(email=email)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Cette adresse email est déjà utilisée.')
        return email

    class Meta:
        model  = Candidat
        fields = [
            'nom', 'prenom', 'dateNaissance', 'sexe',
            'email', 'telephone', 'adresse',
        ]
        widgets = {
            'dateNaissance': forms.DateInput(attrs={
                'type': 'date',
                'class': INPUT_CLASS,
                'x-bind:disabled': '!editionIdentite',
            }),
        }


# ─── Profil — Informations professionnelles ───────────────────────────────────

class ProfilIdentiteForm(forms.ModelForm):
    """Onglet Identité — champs professionnels du Candidat (titre, secteur, première expérience).

    Le secteur est saisi librement via `secteurActiviteNom` (autocomplete côté UI
    sur `referentiel:api_secteurs_activite`) :
      • si la valeur existe déjà dans `referentiel.SecteurActivite` (match insensible
        à la casse), la FK `secteurActiviteRef` est liée à l'entrée existante ;
      • sinon, un nouveau `SecteurActivite` est créé à la volée et lié au candidat.
    Le CharField legacy `secteurActivite` est synchronisé pour rétro-compat
    (matching, templates portfolio).
    """

    secteurActiviteNom = forms.CharField(
        required=False,
        max_length=150,
        label="Secteur d'activité",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_widget_classes(self, 'editionIdentite')
        # Pré-remplit le champ libre avec le nom du secteur courant (FK ou legacy)
        if self.instance and self.instance.pk:
            current = (
                self.instance.secteurActiviteRef.nomSecteur
                if self.instance.secteurActiviteRef_id
                else (self.instance.secteurActivite or '')
            )
            self.fields['secteurActiviteNom'].initial = current

    def save(self, commit=True):
        instance = super().save(commit=False)
        nom = (self.cleaned_data.get('secteurActiviteNom') or '').strip()
        if nom:
            secteur = SecteurActivite.objects.filter(nomSecteur__iexact=nom).first()
            if secteur is None:
                secteur = SecteurActivite.objects.create(nomSecteur=nom)
            instance.secteurActiviteRef = secteur
            instance.secteurActivite    = secteur.nomSecteur
        else:
            instance.secteurActiviteRef = None
            instance.secteurActivite    = ''
        if commit:
            instance.save()
        return instance

    class Meta:
        model  = Candidat
        fields = ['titreProfessionnel', 'datePremierEmploi']


class ProfilPortfolioForm(forms.ModelForm):
    """Onglet Portfolio — biographie, préférences de recherche, liens sociaux.

    - `typeMobilite` : FK vers `referentiel.TypeMobilite` (dropdown peuplé en BD).
    - `typeContratRecherche` : FK vers `referentiel.Contrat` (radio — un seul choix).
    - `portfolioPublic` : booléen (toggle dans l'UI).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_widget_classes(self, 'editionPortfolio')
        # Affichage convivial des dropdowns : libellé "non renseigné" plutôt
        # que "---------" par défaut Django.
        self.fields['typeMobilite'].empty_label = 'Non renseigné'
        self.fields['typeContratRecherche'].empty_label = 'Aucun'

    class Meta:
        model  = Candidat
        fields = [
            'biographie',
            'typeMobilite',
            'typeContratRecherche',
            'portfolioPublic',
            'sloganPortfolio',
            'portfolioModele',
            'couleurPortfolio',
        ]
        widgets = {
            'biographie': forms.Textarea(attrs={
                'rows': 4,
                'class': TEXTAREA_CLASS,
                'x-bind:disabled': '!editionPortfolio',
            }),
            'typeContratRecherche': forms.RadioSelect(attrs={
                'class': 'contrat-radio',
                'x-bind:disabled': '!editionPortfolio',
            }),
            'portfolioPublic': forms.CheckboxInput(attrs={
                'class': 'sr-only peer',
                'x-bind:disabled': '!editionPortfolio',
            }),
            # La sélection se fait via une galerie de cartes Alpine.js
            # qui pilote ce champ caché.
            'portfolioModele': forms.HiddenInput(),
        }


class ProfilCandidatForm(forms.ModelForm):
    """Conservé pour compatibilité — préférer ProfilIdentiteForm + ProfilPortfolioForm."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_widget_classes(self, 'editionIdentite')

    class Meta:
        model   = Candidat
        fields  = [
            'titreProfessionnel', 'biographie', 'datePremierEmploi', 'secteurActivite',
            'typeContratRecherche', 'typeMobilite', 'portfolioPublic',
            'sloganPortfolio', 'couleurPortfolio',
        ]
        widgets = {
            'biographie': forms.Textarea(attrs={
                'rows': 4,
                'class': TEXTAREA_CLASS,
                'x-bind:disabled': '!editionIdentite',
            }),
        }


# ─── Candidature ──────────────────────────────────────────────────────────────

# Tailles & types acceptés pour les uploads (validation côté serveur)
TAILLE_MAX_FICHIER       = 5 * 1024 * 1024  # 5 Mo
EXT_FICHIER_AUTORISEES   = {'.pdf', '.doc', '.docx'}


class CandidatureForm(forms.ModelForm):
    """Form de candidature : CV (réutilisation OU upload) + lettre + portfolio.

    Règles métier (au-delà des champs Django) :
      • si `criteresATS.cvObligatoire` côté offre  → au moins un CV doit être fourni
        (`cvSauvegarde` ou `cv` uploadé) ;
      • si `criteresATS.lettreMotivationnObligatoire` → lettre obligatoire ;
      • un même candidat ne peut postuler 2 fois à la même offre (contrainte BD).

    L'instanciation doit recevoir `candidat=` et `offre=` (kwargs) pour pouvoir
    valider correctement et limiter la liste des CV sauvegardés au candidat.
    """

    cvSauvegarde = forms.ModelChoiceField(
        queryset=CV.objects.none(),  # filtré dans __init__
        required=False,
        empty_label='— Aucun (j\'upload mon CV) —',
        label='Réutiliser un de mes CV',
    )
    lettreSauvegardee = forms.ModelChoiceField(
        queryset=LettreMotivation.objects.none(),  # filtré dans __init__
        required=False,
        empty_label='— Aucune (j\'upload ma lettre) —',
        label='Réutiliser une de mes lettres',
    )

    class Meta:
        model  = Candidature
        # `urlPortfolio` est volontairement ABSENT du form : la vue `postuler`
        # le remplit automatiquement avec l'URL absolue du portfolio public du
        # candidat (généré sur RecrutePro), afin que l'entreprise puisse y
        # accéder lorsqu'elle consulte la candidature.
        fields = ['cvSauvegarde', 'cv', 'lettreSauvegardee', 'lettreMotivation']
        widgets = {
            'cv': forms.ClearableFileInput(attrs={
                'accept': '.pdf,.doc,.docx',
                'class': INPUT_CLASS,
            }),
            'lettreMotivation': forms.ClearableFileInput(attrs={
                'accept': '.pdf,.doc,.docx',
                'class': INPUT_CLASS,
            }),
        }

    def __init__(self, *args, **kwargs):
        self.candidat = kwargs.pop('candidat', None)
        self.offre    = kwargs.pop('offre', None)
        super().__init__(*args, **kwargs)
        # Liste des CV sauvegardés du candidat (non archivés, avec PDF généré)
        if self.candidat:
            self.fields['cvSauvegarde'].queryset = (
                CV.objects
                .filter(candidat=self.candidat, archive=False)
                .order_by('-dateModification')
            )
            self.fields['cvSauvegarde'].widget.attrs['class'] = SELECT_CLASS
            self.fields['lettreSauvegardee'].queryset = (
                LettreMotivation.objects
                .filter(candidat=self.candidat, archive=False)
                .order_by('-dateModification')
            )
            self.fields['lettreSauvegardee'].widget.attrs['class'] = SELECT_CLASS

    # ── Validations ──────────────────────────────────────────────────────────

    def _check_fichier(self, f):
        """Vérifie taille + extension d'un fichier uploadé."""
        if not f:
            return
        nom = (f.name or '').lower()
        ext = nom[nom.rfind('.'):] if '.' in nom else ''
        if ext not in EXT_FICHIER_AUTORISEES:
            raise forms.ValidationError(
                f"Format non accepté ({ext or 'sans extension'}). "
                f"Formats autorisés : {', '.join(sorted(EXT_FICHIER_AUTORISEES))}."
            )
        if f.size > TAILLE_MAX_FICHIER:
            raise forms.ValidationError(
                f"Fichier trop volumineux ({f.size // 1024} Ko). Maximum : 5 Mo."
            )

    def clean_cv(self):
        f = self.cleaned_data.get('cv')
        self._check_fichier(f)
        return f

    def clean_lettreMotivation(self):
        f = self.cleaned_data.get('lettreMotivation')
        self._check_fichier(f)
        return f

    def clean(self):
        cleaned = super().clean()
        if not self.offre or not self.candidat:
            return cleaned

        # Double protection : pas de doublon hors candidatures retirées (la contrainte BD garantit aussi)
        if Candidature.objects.filter(candidat=self.candidat, offre=self.offre).exclude(statut__code='RETIREE').exists():
            raise forms.ValidationError(
                "Vous avez déjà postulé à cette offre."
            )

        ats = self.offre.criteresATS or {}

        # CV obligatoire ?
        if ats.get('cvObligatoire'):
            if not (cleaned.get('cvSauvegarde') or cleaned.get('cv')):
                self.add_error('cv',
                    "Cette offre exige un CV. Choisissez un CV enregistré ou uploadez un fichier.")

        # Lettre obligatoire ? (orthographe d'origine : "lettreMotivationnObligatoire")
        if ats.get('lettreMotivationnObligatoire') or ats.get('lettreMotivationObligatoire'):
            if not (cleaned.get('lettreSauvegardee') or cleaned.get('lettreMotivation')):
                self.add_error('lettreMotivation',
                    "Cette offre exige une lettre. Choisissez une lettre enregistrée ou uploadez un fichier.")

        return cleaned
