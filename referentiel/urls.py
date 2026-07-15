from django.urls import path
from . import views

app_name = 'referentiel'

urlpatterns = [
    path('api/pays/',              views.api_pays,              name='api_pays'),
    path('api/nationalites/',      views.api_nationalites,      name='api_nationalites'),
    path('api/villes/',            views.api_villes,            name='api_villes'),
    path('api/competences/',       views.api_competences,       name='api_competences'),
    path('api/interets/',          views.api_interets,          name='api_interets'),
    path('api/institutions/',      views.api_institutions,      name='api_institutions'),
    path('api/langues/',           views.api_langues,           name='api_langues'),
    path('api/diplomes/',          views.api_diplomes,          name='api_diplomes'),
    path('api/niveaux-etude/',     views.api_niveaux_etude,     name='api_niveaux_etude'),
    path('api/certificats/',       views.api_certificats,       name='api_certificats'),
    path('api/domaines/',          views.api_domaines,          name='api_domaines'),
    path('api/secteurs-activite/', views.api_secteurs_activite, name='api_secteurs_activite'),
    path('api/permis/',            views.api_permis,            name='api_permis'),
    path('api/raisons-sociales/',  views.api_raisons_sociales,  name='api_raisons_sociales'),
    path('api/entreprises/',       views.api_entreprises,       name='api_entreprises'),
    path('api/postes/',            views.api_postes,            name='api_postes'),
    path('api/niveaux/',           views.api_niveaux,           name='api_niveaux'),
    path('api/sexes/',             views.api_sexes,             name='api_sexes'),
    path('api/roles/',             views.api_roles,             name='api_roles'),
    path('api/statuts-compte/',    views.api_statuts_compte,    name='api_statuts_compte'),
    path('api/types-mobilite/',    views.api_types_mobilite,    name='api_types_mobilite'),
]
