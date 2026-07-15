from functools import wraps
from django.shortcuts import redirect


def entreprise_required(view_func):
    """Redirige vers la connexion entreprise si aucune entreprise n'est connectée."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.entreprise is None:
            return redirect('entreprise:connexion')
        return view_func(request, *args, **kwargs)
    return wrapper


def recruteur_required(view_func):
    """Redirige vers la connexion recruteur si aucun recruteur n'est connecté."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or getattr(request, 'recruteur', None) is None:
            return redirect('entreprise:recruteur_connexion')
        return view_func(request, *args, **kwargs)
    return wrapper


def role_required(*roles):
    """Vérifie que le recruteur connecté possède l'un des rôles spécifiés."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if getattr(request, 'recruteur', None) is None:
                return redirect('entreprise:recruteur_connexion')
            if request.recruteur.roleMembre not in roles:
                from . import app_messages as messages
                messages.error(request, "Vous n'avez pas les droits nécessaires pour accéder à cette page.")
                return redirect('entreprise:recruteur_tableau_bord')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def recruteur_ou_admin_required(view_func):
    """Autorise l'accès aux recruteurs ET au compte entreprise (admin principal)."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if getattr(request, 'recruteur', None) is not None:
            return view_func(request, *args, **kwargs)
        if getattr(request, 'entreprise', None) is not None:
            return view_func(request, *args, **kwargs)
        return redirect('entreprise:recruteur_connexion')
    return wrapper


def bloque_roles(*roles_bloques):
    """Bloque les recruteurs dont le rôle est dans roles_bloques.

    Générique et réutilisable. Retourne JSON sur les requêtes AJAX/fetch.
    Le compte Entreprise (admin principal) n'est jamais bloqué.

    Usage :
        @bloque_roles('MANAGER', 'LECTEUR')
        def ma_vue(request): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            recruteur = getattr(request, 'recruteur', None)
            if recruteur is not None and recruteur.roleMembre in roles_bloques:
                is_ajax = (
                    request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                    or request.content_type == 'application/json'
                    or request.headers.get('Accept', '').startswith('application/json')
                )
                if is_ajax:
                    from django.http import JsonResponse
                    return JsonResponse({'ok': False, 'message': "Accès refusé — droits insuffisants."}, status=403)
                from . import app_messages as msgs
                msgs.error(request, "Vous n'avez pas les droits nécessaires pour cette action.")
                return redirect('entreprise:recruteur_tableau_bord')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def lecteur_bloque(view_func):
    """Bloque les recruteurs LECTEUR sur toutes les vues d'action (écriture).

    Un LECTEUR peut consulter toutes les pages mais ne peut pas créer,
    modifier, supprimer ni déclencher aucune action.
    Le compte Entreprise (admin principal) n'est jamais bloqué.
    Retourne JSON si la requête vient d'un fetch (évite l'erreur de parsing côté client).
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        recruteur = getattr(request, 'recruteur', None)
        if recruteur is not None and recruteur.roleMembre == 'LECTEUR':
            is_ajax = (
                request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                or request.content_type == 'application/json'
                or request.headers.get('Accept', '').startswith('application/json')
            )
            if is_ajax:
                from django.http import JsonResponse
                return JsonResponse({'ok': False, 'message': "Accès refusé — rôle lecteur."}, status=403)
            from . import app_messages as msgs
            msgs.error(request, "Les lecteurs ont accès en lecture seule. Cette action n'est pas autorisée.")
            return redirect('entreprise:recruteur_tableau_bord')
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_required(view_func):
    """Autorise l'accès aux administrateurs uniquement.

    Sont considérés comme administrateurs :
    - Le compte Entreprise lui-même (administrateur principal — créateur de
      l'entreprise, intouchable).
    - Tout recruteur dont le rôle est `ADMIN`.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from . import app_messages as messages
        recruteur = getattr(request, 'recruteur', None)
        entreprise = getattr(request, 'entreprise', None)

        if recruteur is not None:
            if recruteur.roleMembre == 'ADMIN':
                return view_func(request, *args, **kwargs)
            messages.error(request,
                "Seuls les administrateurs peuvent gérer les membres de l'entreprise.")
            return redirect('entreprise:recruteur_tableau_bord')

        if entreprise is not None:
            return view_func(request, *args, **kwargs)

        return redirect('entreprise:connexion')
    return wrapper
