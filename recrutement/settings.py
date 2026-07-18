"""
Django settings for recrutement project.

Généré à l'origine par 'django-admin startproject' — projet sur Django 6.0.5.

Pour plus d'informations sur ce fichier, voir
https://docs.djangoproject.com/en/6.0/topics/settings/

Pour la liste complète des réglages et leurs valeurs, voir
https://docs.djangoproject.com/en/6.0/ref/settings/
"""

from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _
import os
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Charger le fichier .env AVANT toute lecture de os.environ
load_dotenv(BASE_DIR / '.env')


# ── Clé secrète ───────────────────────────────────────────────────────────────
# Obligatoire dans .env (ex. : python -c "import secrets; print(secrets.token_urlsafe(50))").
# Pas de valeur par défaut : un déploiement sans SECRET_KEY définie doit échouer
# au démarrage plutôt que tourner avec une clé connue de tous.
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "La variable d'environnement SECRET_KEY est obligatoire "
        "(voir .env.example)."
    )

# ── Mode debug ────────────────────────────────────────────────────────────────
# Par défaut désactivé : DEBUG doit être explicitement activé en dev via .env.
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

# ── Hôtes autorisés ───────────────────────────────────────────────────────────
# En production : ALLOWED_HOSTS=recrutepro.ci,www.recrutepro.ci
_allowed = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [h.strip() for h in _allowed.split(',') if h.strip()]


# Application definition

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.sitemaps',
    # django-allauth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.github',
    # Stockage objet
    'storages',
    # Applications locales
    'recrutement',
    'candidat',
    'entreprise',
    'referentiel',
    'pages',
    'contenu',
]

SITE_ID = 1
SITE_URL = os.environ.get('SITE_URL', 'https://www.recrutepro.ci')

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'candidat.middleware.CandidatMiddleware',      # injecte request.candidat
    'entreprise.middleware.EntrepriseMiddleware',  # injecte request.entreprise
    'entreprise.middleware.RecruteurMiddleware',   # injecte request.recruteur
    'entreprise.middleware_ml.MLSchedulerMiddleware',  # déclencheur web ré-entraînement ML
]

ROOT_URLCONF = 'recrutement.urls'

ASGI_APPLICATION = 'recrutement.asgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'candidat.context_processors.logo_site',
                'pages.context_processors.navigation_groupes',
            ],
        },
    },
]

WSGI_APPLICATION = 'recrutement.wsgi.application'


# Base de données
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'recrutement_db'),
        'USER': os.environ.get('DB_USER', 'root'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            # default_storage_engine forcé : certains hébergeurs/configs
            # locales (ex. WAMP) ont encore MyISAM par défaut, incompatible
            # avec les index FULLTEXT InnoDB et la limite de clé à 767/1000o.
            'init_command': (
                "SET sql_mode='STRICT_TRANS_TABLES', "
                "default_storage_engine=INNODB"
            ),
        },
    }
}


# Modèle utilisateur personnalisé
AUTH_USER_MODEL = 'referentiel.Utilisateur'

AUTHENTICATION_BACKENDS = [
    'referentiel.backends.EmailBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Redis — cache uniquement (plus de broker Celery, voir recrutement/background.py)
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = os.environ.get('REDIS_PORT', '6379')

# Cache — Redis base 1
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': f'redis://{REDIS_HOST}:{REDIS_PORT}/1',
    }
}

# Validation des mots de passe
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalisation
LANGUAGE_CODE = 'fr'

LANGUAGES = [
    ('fr', _('Français')),
    ('en', _('English')),
    ('es', _('Español')),
    ('ar', _('العربية')),
    ('pt', _('Português')),
    ('de', _('Deutsch')),
    ('it', _('Italiano')),
]

LOCALE_PATHS = [BASE_DIR / 'locale']

TIME_ZONE = 'Africa/Abidjan'

USE_I18N = True
USE_TZ = True


# Fichiers statiques — chaque app gère son propre dossier static/
STATIC_URL = '/static/'
# Dossier statique partagé au niveau projet (librairies communes : Tailwind, Alpine.js…)
STATICFILES_DIRS = [BASE_DIR / 'static']
# Dossier où collectstatic regroupe tous les fichiers (production)
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Fichiers média — centralisé, organisé par sous-dossier via upload_to dans les modèles
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ── Stockage objet MinIO / S3 (production) ────────────────────────────────────
USE_MINIO = os.environ.get('USE_MINIO', 'False') == 'True'

if USE_MINIO:
    AWS_ACCESS_KEY_ID = os.environ.get('MINIO_ACCESS_KEY', '')
    AWS_SECRET_ACCESS_KEY = os.environ.get('MINIO_SECRET_KEY', '')
    AWS_S3_ENDPOINT_URL = os.environ.get('MINIO_ENDPOINT_URL', 'http://localhost:9000')
    AWS_S3_REGION_NAME = os.environ.get('MINIO_REGION', 'us-east-1')
    AWS_S3_USE_SSL = os.environ.get('MINIO_USE_SSL', 'False') == 'True'
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = True

    STORAGES = {
        'default': {
            'BACKEND': 'recrutement.storages.PrivateMediaStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }

    MEDIA_URL = f'{AWS_S3_ENDPOINT_URL}/public-media/'

# Clé primaire par défaut
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Redirection après connexion/déconnexion
LOGIN_URL = '/candidat/connexion/'
LOGIN_REDIRECT_URL = '/candidat/'
LOGOUT_REDIRECT_URL = '/'


# ── Email ──────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True

EMAIL_HOST_USER     = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', f'Recruivoire <{EMAIL_HOST_USER}>')

ADMINS = [('Admin Recruivoire', os.environ.get('ADMIN_EMAIL', 'admin@gmail.com'))]
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# ── django-allauth ─────────────────────────────────────────────────────────────
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_ADAPTER = 'candidat.allauth_adapter.CandidatAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'candidat.allauth_adapter.CandidatSocialAccountAdapter'
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = True

# ── OAuth (secrets lus depuis .env) ──────────────────────────────────────────
GOOGLE_CLIENT_ID     = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
GITHUB_CLIENT_ID     = os.environ.get('GITHUB_CLIENT_ID', '')
GITHUB_CLIENT_SECRET = os.environ.get('GITHUB_CLIENT_SECRET', '')

# ── Google Gemini (adaptation IA de CV) ──────────────────────────────────────
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

# ── Mistral AI (secours manuel si quota Gemini épuisé, non branché dans le code actif) ──
MISTRAL_API_KEY = os.environ.get('MISTRAL_API_KEY', '')

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': GOOGLE_CLIENT_ID,
            'secret':    GOOGLE_CLIENT_SECRET,
        },
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    },
    'github': {
        'APP': {
            'client_id': GITHUB_CLIENT_ID,
            'secret':    GITHUB_CLIENT_SECRET,
        },
        'SCOPE': ['user:email'],
    },
}

# ── Sécurité des cookies (actifs en dev ET en prod) ───────────────────────────
SESSION_COOKIE_HTTPONLY = True   # Cookie session inaccessible à JavaScript
SESSION_COOKIE_SAMESITE = 'Lax' # Protection CSRF de base
CSRF_COOKIE_HTTPONLY    = True   # Cookie CSRF inaccessible à JavaScript
CSRF_COOKIE_SAMESITE    = 'Lax' # Protection CSRF de base
X_FRAME_OPTIONS         = 'DENY' # Protection clickjacking

# ── Paramètres de sécurité supplémentaires (production uniquement) ────────────
if not DEBUG:
    # Forcer HTTPS
    SESSION_COOKIE_SECURE      = True
    CSRF_COOKIE_SECURE         = True
    SECURE_SSL_REDIRECT        = True

    # HTTP Strict Transport Security (HSTS) — 1 an
    SECURE_HSTS_SECONDS            = 31_536_000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD            = True

    # Autres headers de sécurité
    SECURE_CONTENT_TYPE_NOSNIFF = True  # Empêche le MIME-sniffing
    SECURE_REFERRER_POLICY      = 'strict-origin-when-cross-origin'

    # Origines CSRF de confiance (derrière Nginx/proxy)
    _csrf_origins = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
    if _csrf_origins:
        CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins.split(',') if o.strip()]

    # Proxy de confiance (Nginx transmet l'IP réelle via X-Forwarded-For)
    if os.environ.get('BEHIND_PROXY', 'False') == 'True':
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
        USE_X_FORWARDED_HOST = True
        USE_X_FORWARDED_PORT = True

_LOG_HANDLERS = {
    'console': {
        'class': 'logging.StreamHandler',
        'formatter': 'verbose',
    },
}

if not DEBUG:
    _LOG_HANDLERS['file'] = {
        'class': 'logging.handlers.RotatingFileHandler',
        'filename': BASE_DIR / 'logs' / 'recrutement.log',
        'maxBytes': 5_242_880,  # 5 Mo
        'backupCount': 5,
        'formatter': 'verbose',
    }

_PROD_HANDLERS = ['console', 'file'] if not DEBUG else ['console']

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name} {message}',
            'style': '{',
        },
    },
    'handlers': _LOG_HANDLERS,
    'loggers': {
        'candidat': {
            'handlers': _PROD_HANDLERS,
            'level': 'INFO' if not DEBUG else 'DEBUG',
            'propagate': True,
        },
        'entreprise': {
            'handlers': _PROD_HANDLERS,
            'level': 'INFO' if not DEBUG else 'DEBUG',
            'propagate': True,
        },
        'django': {
            'handlers': _PROD_HANDLERS,
            'level': 'WARNING' if not DEBUG else 'INFO',
            'propagate': False,
        },
    },
}
