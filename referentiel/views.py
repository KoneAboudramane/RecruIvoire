from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from .models import (
    Pays, Ville,
    TypeCompetence, TypeCentreInteret, Institution, Langue,
    Diplome, NiveauEtude, Certificat, Domaine, SecteurActivite,
    TypePermis, TypeRaisonSociale, RaisonSociale, Poste, Niveau,
    Sexe, Role, StatutCompte, TypeMobilite,
)

# Toutes les APIs ci-dessous exposent des données de référentiel (pays,
# villes, compétences...) qui ne changent que par action admin, jamais par
# signal applicatif — mises en cache 1h (comme les autres pages statiques du
# projet, cf. CLAUDE.md) plutôt que rechargées à chaque appel.
_CACHE_TTL = 3600


@cache_page(_CACHE_TTL)
def api_pays(request):
    qs = Pays.objects.filter(estActif=True).values('id', 'nomPays', 'codeISO', 'indicatifTel', 'nationalite')
    return JsonResponse(list(qs), safe=False)


@cache_page(_CACHE_TTL)
def api_nationalites(request):
    """Liste des nationalités distinctes issues du référentiel Pays."""
    qs = (Pays.objects
              .filter(estActif=True)
              .exclude(nationalite='')
              .values_list('nationalite', flat=True)
              .distinct()
              .order_by('nationalite'))
    return JsonResponse([{'id': n, 'nationalite': n} for n in qs], safe=False)


@cache_page(_CACHE_TTL)
def api_villes(request):
    """Liste des villes filtrables par pays.

    Accepte ?pays_id=X ou ?pays_nom=X (équivalents). Le filtre par nom est
    utile au chargement initial des formulaires quand on connait juste la
    chaîne du pays (rendu côté serveur) sans son id.
    """
    pays_id  = request.GET.get('pays_id')
    pays_nom = request.GET.get('pays_nom')
    qs = Ville.objects.filter(estActif=True)
    if pays_id:
        qs = qs.filter(pays_id=pays_id)
    elif pays_nom:
        qs = qs.filter(pays__nomPays__iexact=pays_nom.strip())
    return JsonResponse(list(qs.values('id', 'nomVille', 'region')), safe=False)


@cache_page(_CACHE_TTL)
def api_competences(request):
    qs = TypeCompetence.objects.values('id', 'nomCompetence', 'domaine')
    return JsonResponse(list(qs), safe=False)


@cache_page(_CACHE_TTL)
def api_interets(request):
    qs = TypeCentreInteret.objects.values('id', 'nomCentreInteret')
    return JsonResponse(list(qs), safe=False)


@cache_page(_CACHE_TTL)
def api_institutions(request):
    qs = Institution.objects.values('id', 'nomInstitution')
    return JsonResponse(list(qs), safe=False)


@cache_page(_CACHE_TTL)
def api_langues(request):
    qs = Langue.objects.values('id', 'nomLangue', 'codeISO')
    return JsonResponse(list(qs), safe=False)


@cache_page(_CACHE_TTL)
def api_diplomes(request):
    qs = Diplome.objects.values('id', 'nomDiplome', 'domaine')
    return JsonResponse(list(qs), safe=False)


@cache_page(_CACHE_TTL)
def api_niveaux_etude(request):
    qs = NiveauEtude.objects.values('id', 'nomNiveau', 'ordre')
    return JsonResponse(list(qs), safe=False)


@cache_page(_CACHE_TTL)
def api_certificats(request):
    qs = Certificat.objects.values('id', 'nomCertificat', 'organisme', 'domaine')
    return JsonResponse(list(qs), safe=False)


@cache_page(_CACHE_TTL)
def api_domaines(request):
    qs = Domaine.objects.values('id', 'nomDomaine', 'description')
    return JsonResponse(list(qs), safe=False)


@cache_page(_CACHE_TTL)
def api_secteurs_activite(request):
    qs = SecteurActivite.objects.values('id', 'nomSecteur', 'description')
    return JsonResponse(list(qs), safe=False)


@cache_page(_CACHE_TTL)
def api_permis(request):
    qs = TypePermis.objects.values('id', 'nomPermis', 'description')
    return JsonResponse(list(qs), safe=False)


@cache_page(_CACHE_TTL)
def api_raisons_sociales(request):
    qs = TypeRaisonSociale.objects.values('id', 'nomRaisonSocial', 'secteur')
    return JsonResponse(list(qs), safe=False)


@cache_page(_CACHE_TTL)
def api_entreprises(request):
    type_id = request.GET.get('type_id')
    qs = RaisonSociale.objects.all()
    if type_id:
        qs = qs.filter(typeRaisonSocial_id=type_id)
    return JsonResponse(
        list(qs.values('id', 'nomEntreprise', 'secteur', 'typeRaisonSocial_id')),
        safe=False,
    )


@cache_page(_CACHE_TTL)
def api_sexes(request):
    qs = Sexe.objects.values('id', 'sexe')
    return JsonResponse(list(qs), safe=False)


@cache_page(_CACHE_TTL)
def api_roles(request):
    qs = Role.objects.values('id', 'libelle')
    return JsonResponse(list(qs), safe=False)


@cache_page(_CACHE_TTL)
def api_statuts_compte(request):
    qs = StatutCompte.objects.values('id', 'libelle')
    return JsonResponse(list(qs), safe=False)


@cache_page(_CACHE_TTL)
def api_types_mobilite(request):
    qs = TypeMobilite.objects.values('id', 'libelle')
    return JsonResponse(list(qs), safe=False)


@cache_page(_CACHE_TTL)
def api_postes(request):
    qs = Poste.objects.values('id', 'nomPoste', 'domaine')
    return JsonResponse(list(qs), safe=False)


@cache_page(_CACHE_TTL)
def api_niveaux(request):
    type_filtre = request.GET.get('type')
    qs = Niveau.objects.all()
    if type_filtre in (Niveau.TYPE_LANGUE, Niveau.TYPE_COMPETENCE):
        qs = qs.filter(type=type_filtre)
    return JsonResponse(list(qs.values('id', 'type', 'nomNiveau', 'libelle', 'nbEtoiles', 'ordre')), safe=False)
