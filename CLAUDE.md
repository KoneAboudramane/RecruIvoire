# RecrutePro — Documentation Projet

## Description
Application web de recrutement développée avec Django 6.0.5.
Elle met en relation **candidats** et **entreprises**.

## Stack technique
- **Backend** : Django 6.0.5 (ASGI via Daphne 4.2.2)
- **Frontend** : Tailwind CSS (CDN Play) + Alpine.js
- **Base de données** : PostgreSQL
- **Cache** : Redis (base 1)
- **Tâches async** : Celery + Redis (base 0)
- **ML/IA** : scikit-learn, sentence-transformers (paraphrase-multilingual-MiniLM-L12-v2), torch
- **Rendu CV/Lettres** : Playwright + Chromium headless
- **Auth OAuth** : django-allauth (Google, GitHub)
- **Langue par défaut** : Français (i18n : 7 langues activées)
- **Fuseau horaire** : Africa/Abidjan

---

## Structure du projet

```
recrutement/
├── CLAUDE.md
├── manage.py
├── requirements.txt
├── .env                          ← secrets (ignoré par Git)
├── .env.example                  ← modèle pour les développeurs
├── .gitignore
├── media/                        ← uploads (organisés par app via upload_to)
├── templates/                    ← templates admin personnalisés
├── static/                       ← JS partagés (alpine.js, tailwind.js)
├── locale/                       ← traductions i18n (7 langues)
│
├── recrutement/                  ← configuration du projet
│   ├── settings.py               ← secrets lus depuis .env (python-dotenv)
│   ├── urls.py
│   ├── wsgi.py
│   ├── asgi.py
│   └── celery.py                 ← configuration Celery
│
├── candidat/                     ← app espace candidat (37 modèles, 66 vues, 92 URLs)
│   ├── templates/candidat/       ← 125 templates (dont 29 modèles CV, 20 lettre, 10 portfolio)
│   ├── static/candidat/          ← js/
│   ├── views/                    ← package de vues (7 modules)
│   │   ├── __init__.py           ← réexporte tout (urls.py inchangé)
│   │   ├── public.py             ← accueil, offres, FAQ, contact (8 vues)
│   │   ├── auth.py               ← connexion, inscription, MDP (11 vues)
│   │   ├── profil.py             ← dashboard, profil, identité, portfolio (13 vues)
│   │   ├── candidatures.py       ← postuler, mes candidatures, entretiens (7 vues)
│   │   ├── notifications.py      ← notifications in-app (9 vues)
│   │   ├── messagerie.py         ← conversations, favoris, invitations (10 vues)
│   │   └── oauth.py              ← Google/GitHub OAuth (8 vues)
│   ├── models.py                 ← 37 modèles (+ 4 TextChoices)
│   ├── urls.py                   ← 92 routes
│   ├── admin.py
│   ├── signals.py                ← 7 signaux / 13 @receiver (matching + invalidation cache)
│   ├── cv.py                     ← reconstruction CV (rubriques JSON → dict)
│   ├── cv_render.py              ← rendu Playwright CV (PDF/PNG)
│   ├── cv_initial.py             ← dict initial pour éditeur Alpine
│   ├── lettreMo.py               ← éditeur et sauvegarde lettres
│   ├── lettre_render.py          ← rendu Playwright lettres (PDF/PNG)
│   ├── portfolio.py              ← portfolio public + partage token
│   ├── matching.py               ← matching rules-based (7 critères pondérés)
│   ├── matching_semantic.py      ← matching sémantique (sentence-transformers)
│   ├── matching_ml.py            ← matching ML (sklearn, joblib)
│   ├── ml_features.py            ← extraction 15 features pour ML
│   ├── rubriques_sync.py         ← sync JSON ↔ relationnel
│   ├── tasks.py                  ← tâches Celery (recommandations accueil)
│   ├── newsletter.py             ← newsletter (offres, conseils, actus)
│   ├── notifications_service.py  ← création notifs idempotente + email
│   ├── allauth_adapter.py        ← adapters OAuth (crée Utilisateur + Candidat)
│   ├── middleware.py             ← CandidatMiddleware (injecte request.candidat)
│   ├── context_processors.py     ← logo_site() (cache 1h)
│   ├── decorators.py             ← @candidat_required
│   ├── forms.py                  ← InscriptionForm, CandidatureForm, CVUploadForm
│   ├── visiteurs.py              ← compteur visiteurs uniques par IP/jour
│   ├── niveau_resolver.py        ← résolution Niveau FK depuis legacy
│   └── app_messages.py           ← wrapper messages Django auto-tag
│
├── entreprise/                   ← app espace entreprise (20 modèles, 117 vues, 90 URLs)
│   ├── templates/entreprise/     ← 57 templates
│   ├── static/entreprise/        ← js/
│   ├── views/                    ← package de vues (11 modules)
│   │   ├── __init__.py           ← réexporte tout (urls.py inchangé)
│   │   ├── _helpers.py           ← constantes, validation fichiers (magic bytes)
│   │   ├── public.py             ← accueil, portfolios, partage (9 vues)
│   │   ├── auth.py               ← connexion, inscription, MDP (10 vues)
│   │   ├── profil.py             ← dashboard, profil, préférences (15 vues)
│   │   ├── offres.py             ← CRUD offres d'emploi (16 vues)
│   │   ├── candidatures.py       ← pipeline candidatures, décisions (6 vues)
│   │   ├── entretiens.py         ← planification, report, annulation (9 vues)
│   │   ├── membres.py            ← gestion équipe recruteur (7 vues)
│   │   ├── notifications.py      ← notifications, SSE (8 vues)
│   │   ├── messagerie.py         ← conversations, messages, templates (18 vues)
│   │   ├── ia.py                 ← scoring ML, suggestions ATS (6 vues)
│   │   └── admin_panel.py        ← panel admin staff (10 vues)
│   ├── models.py                 ← 20 modèles (+ 13 TextChoices/enums)
│   ├── urls.py                   ← 90 routes
│   ├── admin.py
│   ├── signals.py                ← 5 signaux / 8 @receiver (auto-scan ATS + invalidation cache)
│   ├── ats_ml.py                 ← inférence modèle ATS re-ranking (joblib)
│   ├── ats_predict.py            ← scoring sémantique (MiniLM multilingue)
│   ├── tasks.py                  ← tâches Celery (calcul embeddings)
│   ├── messagerie.py             ← helpers rendu sécurisé templates message
│   ├── ml_scheduler.py           ← planification ré-entraînement ML
│   ├── middleware.py             ← EntrepriseMiddleware + RecruteurMiddleware
│   ├── middleware_ml.py          ← MLSchedulerMiddleware (déclencheur web-trafic)
│   ├── notifications_service.py  ← service création notifications ATS
│   ├── decorators.py             ← 7 décorateurs d'accès par rôle
│   └── app_messages.py           ← wrapper messages Django auto-tag
│
└── referentiel/                  ← app référentiels partagés (30 modèles, 21 APIs)
    ├── models.py                 ← 30 modèles (+ TypeCompte, UtilisateurManager)
    ├── backends.py               ← EmailBackend (auth par email)
    ├── views.py                  ← 21 APIs JSON autocomplete
    ├── urls.py                   ← 21 routes API
    └── admin.py                  ← 31 classes admin
```

---

## Chiffres clés

| Élément | Candidat | Entreprise | Referentiel | Total |
|---------|----------|------------|-------------|-------|
| Modèles | 37 | 20 | 30 | 87 |
| Vues | 66 | 117 | 21 | 204 |
| URLs | 92 | 90 | 21 | 203 |
| Templates | 125 | 57 | — | 182 |
| Signaux | 7 (13 @receiver) | 5 (8 @receiver) | — | 12 (21 @receiver) |
| Commands | 14 | 6 | 3 | 23 |
| Tests | 25 | 23 | — | 48 |
| Dépendances | — | — | — | 27 |

---

## URLs

| URL           | App        | Description              |
|---------------|------------|--------------------------|
| `/`           | —          | Redirige vers `/candidat/` |
| `/candidat/`  | candidat   | Accueil espace candidat (92 routes) |
| `/entreprise/`| entreprise | Accueil espace entreprise (90 routes) |
| `/referentiel/` | referentiel | APIs JSON autocomplete (21 routes) |
| `/admin/`     | Django     | Interface d'administration |

---

## Conventions

### Templates
- Chaque app possède son propre `base.html` avec sa navbar et son footer distincts
- `candidat/templates/candidat/base.html` → navbar bleue
- `entreprise/templates/entreprise/base.html` → navbar verte
- Blocs disponibles : `titre`, `contenu`, `css_extra`, `js_extra`

```html
{% extends "candidat/base.html" %}

{% block titre %}Ma page — Candidat{% endblock %}

{% block contenu %}
  <!-- contenu ici -->
{% endblock %}
```

### Fichiers statiques
- Chaque app gère ses propres fichiers dans `<app>/static/<app>/js/`
- Fichiers partagés dans `static/js/` (alpine.js, tailwind.js)
- Chargement dans un template : `{% load static %}` puis `{% static 'candidat/js/voice_recorder.js' %}`

### Fichiers média (uploads)
- Centralisés dans `media/`
- Sous-dossiers : `candidat/`, `entreprise/`, `messages/`, `ml_models/`, `modeles_cv/`, `modeles_lettre/`, `portfolios/`, `users/`
- Organisés par app via `upload_to` dans les modèles :

```python
photo = models.ImageField(upload_to='candidat/photos/')
logo  = models.ImageField(upload_to='entreprise/logos/')
```

### URLs des apps
- Chaque app a son propre `urls.py` avec un `app_name`
- Utiliser les namespaces pour les liens : `{% url 'candidat:accueil' %}`

### Vues
- Les vues sont organisées en **packages** (`views/`) et non en fichiers uniques
- Chaque module a ses propres imports et un `logger` dédié
- `__init__.py` réexporte tout → `urls.py` n'a pas besoin de changer
- Pour ajouter une vue : l'écrire dans le module approprié, elle sera automatiquement accessible

---

## Configuration & Secrets

Les secrets sont dans le fichier `.env` (jamais commité). `settings.py` les lit via `os.environ.get()`.

```bash
# Copier le modèle et renseigner les valeurs
cp .env.example .env
```

Variables requises :
- `SECRET_KEY` — clé secrète Django
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` — PostgreSQL
- `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` — SMTP Gmail
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` — OAuth Google
- `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` — OAuth GitHub

---

## Sécurité

- **Rate limiting** : `django-ratelimit` sur les endpoints d'auth (connexion 5/min, codes 7/min, emails 3/min)
- **Cookies** : `HttpOnly`, `SameSite=Lax`, `Secure` en production
- **CSRF** : activé partout
- **Session Entreprise** : rotation (`cycle_key`) + expiration 8h
- **HTTPS** : HSTS 1 an + SSL redirect en production
- **Transactions** : `transaction.atomic()` sur 27 opérations multi-tables
- **Tests** : 48 tests (workflows candidatures, permissions rôles, rate limiting, session)

---

## Cache

Backend Redis (base 1, séparé de Celery). Invalidation automatique via signaux Django (21 @receiver).

| Donnée | Durée | Invalidation |
|--------|-------|-------------|
| Logo du site | 1h | Signal `LogoSite` save/delete |
| Pages FAQ, Contact, Confidentialité | 1h | `@cache_page` |
| Offres vedette, stats, top secteurs/villes | 5 min | Signal `OffreEmploi` save/delete |
| Modèles CV / Lettres | 30 min | Signal `ModeleCV`/`ModeleLettre` save/delete |
| Accueil entreprise | 5 min | Signaux multi-modèles |
| Témoignages | 5 min | Signal `Temoignage` save/delete |

---

## Tâches asynchrones (Celery) & monitoring (Flower)

Backend Redis base 0 (`CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` dans `settings.py`),
séparé du cache (base 1). Les tâches ne s'exécutent que si un **worker Celery tourne** —
sans worker actif, elles restent en attente indéfiniment dans la file Redis.

| Tâche | Fichier | Déclenchée par |
|-------|---------|----------------|
| `calculer_embedding_candidat` / `calculer_embedding_offre` | `entreprise/tasks.py` | Sauvegarde profil candidat / offre |
| `calculer_tous_embeddings_manquants` | `entreprise/tasks.py` | Ponctuel / commande |
| `calculer_recommandations_accueil` | `candidat/tasks.py` | Vue `candidat:accueil` quand le cache des recommandations est froid (voir ci-dessous) |

**Recommandations de la page d'accueil candidat** : le calcul sémantique + ML est trop
lent pour tourner dans le cycle requête/réponse HTTP. La vue ne calcule jamais rien
elle-même — elle lit deux clés de cache (`accueil_reco_{id}` frais, 30 min ;
`accueil_reco_stale_{id}` de secours, 7 jours) et déclenche `calculer_recommandations_accueil`
en arrière-plan si le cache frais est vide (verrou `accueil_reco_computing_{id}`, 60 s,
anti-doublon). Tant que le calcul n'est pas prêt, la page retombe sur le dernier résultat
personnalisé connu, ou sur une liste générique si le candidat n'a encore jamais été calculé.

**Monitoring (Flower)** : dashboard web temps réel des tâches Celery (en attente, en
cours, échouées, avec relance manuelle possible) — comble un point mort historique où une
tâche en échec silencieux n'était visible que dans les logs. Toujours lancer avec
`--basic_auth` (jamais exposer sans authentification, il permet d'annuler/relancer des
tâches). Voir commande dans « Commandes utiles ».

---

## Téléchargement / Impression CV & Lettres (Playwright)

Le rendu PDF / PNG / JPG des CV et lettres passe par **Playwright + Chromium headless**
(modules `candidat/cv_render.py` et `candidat/lettre_render.py`) — fidélité 100 % avec l'aperçu navigateur.
Le DOCX continue d'utiliser `python-docx` (best-effort, pas de WYSIWYG strict).
L'impression dans l'éditeur se fait côté client via `window.print()` + le CSS
`@media print` défini dans `_form_styles.html`.

### Setup à faire une fois
```bash
pip install -r requirements.txt
playwright install chromium
```

Le binaire Chromium pèse ~300 Mo et est installé dans le profil utilisateur
(`%LOCALAPPDATA%\ms-playwright\` sous Windows).

---

## Commandes utiles

```bash
# Installer les dépendances
pip install -r requirements.txt

# Configurer les secrets
cp .env.example .env  # puis éditer .env

# Lancer le serveur
python manage.py runserver

# Migrations
python manage.py makemigrations
python manage.py migrate

# Créer un superutilisateur
python manage.py createsuperuser

# Lancer les tests
python manage.py test candidat entreprise

# Vérifier la configuration
python manage.py check

# Collecter les fichiers statiques (production)
python manage.py collectstatic

# Entraîner le modèle ML matching
python manage.py entrainer_matching

# Entraîner le modèle ATS
python manage.py entrainer_ats

# Envoyer la newsletter offres
python manage.py envoyer_newsletter_offres

# Lancer un worker Celery (traite les tâches asynchrones : embeddings ATS,
# recommandations accueil...)
celery -A recrutement worker --loglevel=info

# Lancer Flower (dashboard de supervision Celery, http://localhost:5555)
celery -A recrutement flower --port=5555 --basic_auth=admin:CHANGEZ_MOI
```

---

## Authentification

- **AUTH_USER_MODEL** : `referentiel.Utilisateur` (AbstractBaseUser + PermissionsMixin, email-based)
- **Candidat** : `class Candidat(Utilisateur)` — héritage multi-table direct → `auth_login()`
- **Recruteur** : `class Recruteur(Utilisateur)` — héritage multi-table direct → `auth_login()`
- **Entreprise** : modèle autonome (`models.Model`) → auth session-based (`session['entreprise_id']`)
- **OAuth** : django-allauth (Google + GitHub) pour les candidats, adapters dans `candidat/allauth_adapter.py`
- **Middlewares** : `CandidatMiddleware`, `EntrepriseMiddleware`, `RecruteurMiddleware`, `MLSchedulerMiddleware`
- `LOGIN_URL` : `/candidat/connexion/`
- `LOGIN_REDIRECT_URL` : `/candidat/`
- `LOGOUT_REDIRECT_URL` : `/`
