from .models import Entreprise, Recruteur, StatutCompte


class EntrepriseMiddleware:
    """
    Injecte request.entreprise depuis la session.
    Inchangé : l'Entreprise garde son auth session-based.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        entreprise_id = request.session.get('entreprise_id')
        request.entreprise = None

        if entreprise_id:
            try:
                ent = Entreprise.objects.get(pk=entreprise_id)
                if ent.statutCompte != StatutCompte.DESACTIVE:
                    request.entreprise = ent
                else:
                    request.session.pop('entreprise_id', None)
            except Entreprise.DoesNotExist:
                request.session.pop('entreprise_id', None)

        return self.get_response(request)


class RecruteurMiddleware:
    """
    Injecte request.recruteur depuis request.user (multi-table inheritance).
    Si un recruteur est connecté, request.entreprise est aussi alimenté.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.recruteur = None

        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            try:
                rec = Recruteur.objects.select_related('entreprise').get(utilisateur_ptr=user)
                if (rec.estActif
                        and rec.statutCompte != StatutCompte.DESACTIVE
                        and rec.entreprise.statutCompte != StatutCompte.DESACTIVE):
                    request.recruteur = rec
                    if not getattr(request, 'entreprise', None):
                        request.entreprise = rec.entreprise
            except Recruteur.DoesNotExist:
                pass

        return self.get_response(request)
