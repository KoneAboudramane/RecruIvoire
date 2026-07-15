from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from referentiel.models import Utilisateur, TypeCompte


class CandidatAccountAdapter(DefaultAccountAdapter):
    """Adaptateur allauth pour les comptes candidat."""

    def save_user(self, request, user, form, commit=True):
        user.type_compte = TypeCompte.CANDIDAT
        user = super().save_user(request, user, form, commit=commit)
        self._ensure_candidat_profile(user)
        return user

    def _ensure_candidat_profile(self, user):
        from .models import Candidat
        if not Candidat.objects.filter(utilisateur_ptr=user).exists():
            Candidat.objects.create(
                utilisateur_ptr=user,
                email=user.email,
                emailVerifie=True,
            )


class CandidatSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Adaptateur allauth pour les connexions sociales (Google, GitHub)."""

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form=form)
        user.type_compte = TypeCompte.CANDIDAT
        user.save(update_fields=['type_compte'])
        self._ensure_candidat_profile(user, sociallogin)
        return user

    def _ensure_candidat_profile(self, user, sociallogin):
        from .models import Candidat
        if not Candidat.objects.filter(utilisateur_ptr=user).exists():
            extra = sociallogin.account.extra_data or {}
            prenom = extra.get('given_name', '') or extra.get('name', '').split(' ')[0]
            nom = extra.get('family_name', '')
            if not nom and ' ' in extra.get('name', ''):
                nom = extra['name'].split(' ', 1)[1]
            Candidat.objects.create(
                utilisateur_ptr=user,
                email=user.email,
                prenom=prenom,
                nom=nom,
                emailVerifie=True,
            )

    def pre_social_login(self, request, sociallogin):
        """Si un Utilisateur existe déjà avec cet email, on le lie automatiquement."""
        email = sociallogin.account.extra_data.get('email')
        if not email:
            return
        if sociallogin.is_existing:
            return
        try:
            user = Utilisateur.objects.get(email=email)
            sociallogin.connect(request, user)
        except Utilisateur.DoesNotExist:
            pass
