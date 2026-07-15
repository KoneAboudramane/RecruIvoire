from django.contrib.auth import get_user_model

Utilisateur = get_user_model()


class EmailBackend:
    """Authentifie un utilisateur par email + mot de passe."""

    def authenticate(self, request, email=None, password=None, **kwargs):
        if email is None or password is None:
            return None
        try:
            user = Utilisateur.objects.get(email=email)
        except Utilisateur.DoesNotExist:
            Utilisateur().set_password(password)
            return None
        if user.check_password(password) and user.is_active:
            return user
        return None

    def get_user(self, user_id):
        try:
            return Utilisateur.objects.get(pk=user_id)
        except Utilisateur.DoesNotExist:
            return None
