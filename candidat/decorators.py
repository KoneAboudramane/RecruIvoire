from functools import wraps
from django.shortcuts import redirect
from django.urls import reverse


def candidat_required(view_func):
    """Redirige vers la connexion si aucun candidat n'est connecté."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.candidat is None:
            login_url = reverse('candidat:connexion')
            return redirect(f'{login_url}?next={request.path}')
        return view_func(request, *args, **kwargs)
    return wrapper
