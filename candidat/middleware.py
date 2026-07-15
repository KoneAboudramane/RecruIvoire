from .models import Candidat


class CandidatMiddleware:
    """
    Injecte request.candidat depuis request.user (multi-table inheritance).
    request.candidat vaut None si aucun candidat n'est connecté.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.candidat = None

        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            try:
                request.candidat = Candidat.objects.get(utilisateur_ptr=user)
            except Candidat.DoesNotExist:
                pass

        return self.get_response(request)
