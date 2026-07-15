from django.urls import path
from . import views

app_name = 'pages'

urlpatterns = [
    path('api/contact/', views.api_contact, name='api_contact'),
]
