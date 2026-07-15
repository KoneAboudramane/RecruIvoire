from django.urls import path
from . import views

app_name = 'contenu'

urlpatterns = [
    path('mentions-legales/',  views.mentions_legales,  name='mentions_legales'),
    path('tarifs/',            views.tarifs,            name='tarifs'),
    path('faq/',               views.faq,               name='faq'),
    path('contact/',           views.contact,           name='contact'),
    path('confidentialite/',   views.confidentialite,   name='confidentialite'),
    path('cgu/',               views.cgu,               name='cgu'),
    path('a-propos/',          views.a_propos,          name='a_propos'),
]
