# Guide de déploiement — O2switch (hébergement mutualisé) via GitHub

Ce guide décrit le déploiement de RecruIvoire sur un compte **O2switch mutualisé**
(cPanel), en passant par un dépôt **GitHub** comme intermédiaire entre le poste de
développement et le serveur. Il remplace pour ce projet les fichiers `deploy.sh` /
`nginx.conf` / `supervisor.conf` de ce même dossier, qui ciblaient un VPS générique
(Nginx + Supervisor + Daphne) — **inapplicables sur O2switch mutualisé**, qui ne
propose ni accès root ni Docker ni process persistant (voir le raisonnement complet
dans les échanges du projet — hébergement mutualisé = cPanel + Passenger/WSGI).

---

## 0. Prérequis

- Un compte O2switch mutualisé (Grow / Cloud / Pro — les 58 outils cPanel sont
  identiques sur les trois paliers), avec accès cPanel.
- Un compte GitHub, et un dépôt (de préférence **privé** — le code source fait
  partie d'un mémoire académique non encore soutenu publiquement).
- Un accès **Terminal** cPanel (SSH via navigateur, inclus par défaut) ou un client
  SSH classique avec les identifiants du compte cPanel.

---

## 1. Préparer le dépôt Git en local

Le projet n'a **pas encore de dépôt Git initialisé**. Avant toute chose :

### 1.1 Vérifier le `.gitignore`

Le dossier du projet contient des répertoires `Lib/`, `Scripts/`, `Include/`,
`share/` à la racine — ce n'est **pas un venv standard** (pas de `pyvenv.cfg`), ce
sont les paquets Python du poste de dev directement dans le dossier, avec
notamment `torch`/`transformers` (plusieurs Go). Le `.gitignore` du projet a été
corrigé pour les exclure (`/Lib/`, `/Scripts/`, `/Include/`, `/share/`). **Vérifier
que ces lignes sont bien présentes avant le premier commit**, sous peine d'envoyer
plusieurs Go de paquets Python sur GitHub.

Vérifier aussi que `.env` (secrets réels) est bien ignoré — c'est déjà le cas.

### 1.2 Initialiser le dépôt

```powershell
git init
git add .
git status   # relire la liste : ne doit PAS contenir Lib/, Scripts/, media/, .env
git commit -m "Import initial RecruIvoire"
```

### 1.3 Créer le dépôt GitHub et pousser

1. Créer un dépôt vide sur GitHub (sans README/gitignore auto-généré, pour éviter
   un conflit avec l'historique local).
2. Le lier et pousser :

```powershell
git remote add origin https://github.com/<compte>/<repo>.git
git branch -M main
git push -u origin main
```

Si le dépôt est privé, prévoir un **Personal Access Token** (PAT) GitHub — le mot
de passe classique ne fonctionne plus pour l'authentification HTTPS. Ce même token
servira côté O2switch à l'étape 3.

> **Fait pour ce projet** (2026-07-15) : dépôt initialisé, premier commit poussé
> sur `https://github.com/KoneAboudramane/RecruIvoire`. Les étapes 1.1-1.3
> ci-dessus sont donc déjà réalisées — gardées ici pour référence/si le dépôt
> doit être reconstruit.

---

## 2. Côté O2switch — préparation cPanel

1. Se connecter à cPanel (lien fourni par O2switch à la création du compte).
2. **Domaine** : si le projet doit être accessible sur un sous-domaine (ex.
   `recrutepro.mondomaine.ci`), le créer via **Domaines > Sous-domaines**.
   Sinon, utiliser le domaine principal du compte.
3. **SSL** : normalement automatique (Let's Encrypt auto-renouvelé sur O2switch) —
   vérifier dans **Sécurité > SSL/TLS Status** après la création du (sous-)domaine.

---

## 3. Récupérer le code — outil "Git Version Control"

cPanel propose un outil Git natif (catégorie **Fichiers**) :

1. **cPanel > Git Version Control > Create**.
2. **Clone a Repository** : coller l'URL HTTPS du dépôt GitHub
   (`https://github.com/<compte>/<repo>.git`).
   - Si le dépôt est privé, cPanel demandera des identifiants : utiliser le nom
     d'utilisateur GitHub + le **Personal Access Token** (PAT) comme mot de passe.
3. **Repository Path** : cloner **en dehors** de `public_html/` (ex.
   `/home/<user>/recrutement`) — l'app Python (étape 5) sert le contenu elle-même
   via Passenger, pas besoin d'exposer les fichiers sources sous le webroot public.
4. Valider — cPanel clone le dépôt sur le serveur.

**Mises à jour futures** : après un `git push` depuis le poste local, revenir sur
cette page cPanel et cliquer **Pull or Deploy > Update from Remote**, ou le faire
en une commande depuis le Terminal (étape 8.4).

---

## 4. Base de données MySQL

> **Changement de moteur (2026-07-15)** : le projet ciblait initialement
> PostgreSQL 9.6 (seule version proposée sur O2switch mutualisé, sans extension
> `vector`). Après constat que ce PostgreSQL n'était en réalité pas exploitable
> pour le projet, bascule complète sur **MySQL** — disponible nativement sur
> O2switch. Le code a été adapté en conséquence : `settings.py` (driver
> `mysqlclient`), recherche plein texte (index `FULLTEXT` MySQL au lieu de
> `SearchVector`/`GinIndex` PostgreSQL, voir `recrutement/search.py`), et
> plusieurs migrations historiques contenant du SQL brut PostgreSQL ont été
> réécrites pour brancher sur `schema_editor.connection.vendor`. Les embeddings
> ATS restent en `JSONField` (déjà le cas depuis l'abandon de pgvector) —
> aucun changement de ce côté.

1. **cPanel > Bases de données MySQL**.
2. Créer une base (ex. `<user>_recrutement`).
3. Créer un utilisateur dédié avec mot de passe fort, l'associer à la base avec
   **tous les privilèges**.
4. Noter : nom de la base, utilisateur, mot de passe, hôte (`localhost`
   généralement sur mutualisé), port (`3306` par défaut) — ces valeurs iront
   dans le `.env` du serveur (étape 6).

> **Point de vigilance testé en local (WAMP)** : certaines installations MySQL
> ont encore `default_storage_engine=MyISAM` par défaut, incompatible avec les
> index `FULLTEXT` InnoDB et limité à 1000 octets de clé d'index (les champs
> `unique=True` du projet en `utf8mb4` peuvent dépasser cette limite). Le
> projet force `default_storage_engine=INNODB` via `init_command` dans les
> `OPTIONS` de `DATABASES` (`recrutement/settings.py`) — aucune action manuelle
> nécessaire côté serveur, mais utile à savoir en cas d'erreur `max key length`
> ou `Can't find FULLTEXT index` inattendue. Vérifier aussi que la base créée
> utilise bien le charset `utf8mb4` (pas `utf8`/`utf8mb3`, qui ne supporte pas
> les emoji utilisés dans certains libellés du projet) — cPanel crée
> généralement les bases MySQL en `utf8mb4` par défaut sur les hébergements
> récents, mais à vérifier (`SHOW CREATE DATABASE <base>;`).

---

## 5. Créer l'application Python — "Setup Python App"

1. **cPanel > Logiciels > Setup Python App > Create Application**.
2. **Python version** : choisir la version la plus proche de celle utilisée en
   dev (aligner sur `3.13` si disponible — le projet a été développé/testé en
   local avec Python 3.14, prendre la plus récente disponible côté O2switch).
3. **Application root** : le dossier où le dépôt a été cloné à l'étape 3
   (ex. `recrutement`).
4. **Application URL** : le (sous-)domaine préparé à l'étape 2.
5. **Application startup file** : Passenger (le moteur derrière Setup Python App)
   attend un fichier `passenger_wsgi.py` **à la racine** du projet, exposant une
   variable `application`. Le projet a déjà `recrutement/wsgi.py` (chemin
   `recrutement/wsgi.py`, pas à la racine) — créer un petit fichier relais à la
   racine du projet :

   ```python
   # passenger_wsgi.py — point d'entrée attendu par Passenger/O2switch
   import os
   import sys

   sys.path.insert(0, os.path.dirname(__file__))
   os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'recrutement.settings')

   from recrutement.wsgi import application
   ```

   Committer ce fichier dans le dépôt (il ne sert que pour O2switch, n'affecte
   rien en local).
6. Valider la création. cPanel affiche alors une commande du type :
   ```bash
   source /home/<user>/virtualenv/recrutement/3.13/bin/activate && cd /home/<user>/recrutement
   ```
   — **noter cette commande**, elle active le venv dédié créé par cPanel (différent
   du dossier `Lib/Scripts/` du poste de dev, qui ne sert pas ici).

---

## 6. Variables d'environnement (`.env`)

Le fichier `.env` n'est **jamais** commité (voir `.gitignore`). Deux options :

- **Option simple** : depuis le Terminal cPanel (ou un client SFTP), créer
  directement un fichier `.env` à la racine de `Application root`, avec le même
  format que `.env.example` du projet, valeurs de production :
  - `SECRET_KEY` (en générer une nouvelle, ne jamais réutiliser celle du dev)
  - `DEBUG=False`
  - `ALLOWED_HOSTS=<domaine choisi à l'étape 2>`
  - `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST=localhost`, `DB_PORT=3306`
    (valeurs de l'étape 4)
  - `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` (SMTP Gmail, comme en dev)
  - `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`, `GITHUB_CLIENT_ID` /
    `GITHUB_CLIENT_SECRET` (recréer des identifiants OAuth avec le domaine de
    prod dans les origines autorisées — ceux du dev pointent vers `localhost`)
  - `REDIS_HOST=localhost`, `REDIS_PORT=6379` (après activation Redis, étape 10)
  - `SITE_URL=https://<domaine choisi>`
  - `CSRF_TRUSTED_ORIGINS=https://<domaine choisi>`
- **Option "Setup Python App"** : l'interface propose aussi une section
  **Environment variables** qui injecte directement les variables au process —
  redondant avec `.env` (le projet lit via `python-dotenv`), utiliser l'une ou
  l'autre mais pas un mélange incohérent des deux.

---

## 7. Installer les dépendances

Depuis le **Terminal** cPanel :

```bash
source /home/<user>/virtualenv/recrutement/3.13/bin/activate
cd /home/<user>/recrutement
pip install -r requirements.txt
```

Points d'attention connus (voir le reste du projet pour le détail) :
- `playwright` figure dans `requirements.txt` mais **`playwright install chromium`
  n'a pas encore été validé sur O2switch** — à tester (accès Terminal +
  `playwright install chromium` + lancement d'un rendu test) avant de compter
  dessus en production. Si ça échoue, le rendu CV/lettre PDF devra basculer sur
  une alternative sans navigateur (déjà discuté : PyMuPDF `fitz.Story` ou
  xhtml2pdf — WeasyPrint est déjà écarté, confirmé non supporté).
- `torch` / `sentence-transformers` / `transformers` : poids important, à
  surveiller avec l'outil **X-Ray App** (cPanel > Mesures) pendant
  l'installation et le premier chargement du modèle.

---

## 8. Django : migrations, fichiers statiques, admin

Toujours dans le Terminal, venv activé :

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

Puis, selon les besoins (voir `CLAUDE.md`, section « Commandes utiles ») :

```bash
python manage.py init_admin
python manage.py charger_faq_initiale
python manage.py charger_pages_statiques
```

### 8.4 Workflow de mise à jour (après chaque évolution du code)

```bash
cd /home/<user>/recrutement
git pull origin main
source /home/<user>/virtualenv/recrutement/3.13/bin/activate
pip install -r requirements.txt   # si requirements.txt a changé
python manage.py migrate          # si nouvelles migrations
python manage.py collectstatic --noinput
```

Puis **redémarrer l'app** : cPanel > Setup Python App > sélectionner l'app >
bouton **Restart** (indispensable — Passenger garde le code en mémoire tant qu'on
ne lui dit pas de recharger).

---

## 9. Importer les données

Deux approches possibles. **Pour ce projet, la 9.2 est celle retenue** (reprendre
les données réelles du poste local) — la 9.1 reste documentée comme solution de
repli plus simple si le dump pose un jour souci sur le compte réel.

### 9.1 Alternative simple : réensemencer via les commandes seed du projet

Le projet a des management commands dédiées qui passent par l'ORM Django, donc
**indépendantes de la version PostgreSQL** — zéro risque de compatibilité,
contrairement à un dump SQL. Génère des données de démo plausibles mais pas
l'état exact du poste local :

```bash
python manage.py init_admin
python manage.py seed_entreprises
python manage.py seed_candidats
python manage.py seed_candidatures
python manage.py seed_photos_demo
python manage.py charger_faq_initiale
python manage.py charger_pages_statiques
```

(liste non exhaustive — voir `CLAUDE.md` et les dossiers `management/commands/`
de `candidat/`, `entreprise/`, `referentiel/`, `contenu/` pour la liste complète)

### 9.2 Option alternative — export/import via les fixtures Django (mise à jour 2026-07-15, MySQL)

Pour reprendre l'état exact de la base locale (données réelles : candidats,
entreprises, offres, candidatures, navigation, FAQ...), pas seulement des
données de démo générées par les seeds.

**Historique** : l'approche initialement testée (dump/restore SQL `pg_dump`
data-only) fonctionnait pour PostgreSQL mais s'est heurtée à des
incompatibilités de version (PG18 local vs PG9.6 cible : `\restrict`,
`GENERATED BY DEFAULT AS IDENTITY` absent en 9.6...). Suite au passage du
projet sur **MySQL**, cette approche est abandonnée au profit des **fixtures
Django** (`dumpdata`/`loaddata`) : elles passent par l'ORM des deux côtés,
donc totalement indépendantes du moteur de base de données et de sa version —
zéro risque de dialecte SQL, contrairement à un dump natif.

1. **Export local — toutes les données, sauf les tables gérées par Django
   lui-même** (`contenttypes`, `auth.permission` — doivent refléter l'état du
   *serveur cible*, régénéré par `migrate`) :

   ```powershell
   python manage.py dumpdata --natural-foreign --natural-primary `
     -e contenttypes -e auth.permission `
     --indent 2 -o data_o2switch.json
   ```

2. Transférer `data_o2switch.json` sur O2switch — **pas via Git** (pas sa
   place dans l'historique) — via le **Gestionnaire de fichiers** cPanel ou un
   client FTP/SFTP.

3. **Import, dans cet ordre précis**, depuis le Terminal cPanel :

   ```bash
   python manage.py migrate            # schéma MySQL à jour, tables vides
   python manage.py loaddata data_o2switch.json
   ```

   `loaddata` recrée les lignes avec leurs clés primaires d'origine et
   resynchronise automatiquement les compteurs `AUTO_INCREMENT` de MySQL après
   l'import — pas de commande supplémentaire nécessaire.

⚠️ Le fixture ne contient **que la base de données**. Les fichiers uploadés
(photos, logos, CV, documents KYC dans `media/`) doivent être transférés
séparément (FTP/Gestionnaire de fichiers), puisqu'ils sont exclus de Git
(`.gitignore`) et absents du fixture JSON.

---

## 10. Redis (cache)

**cPanel > Logiciels > Redis** (ou dans la catégorie « Outils exclusifs O2switch »)
: activer le service. Il tourne en général sur `localhost:6379` par défaut — les
valeurs `REDIS_HOST`/`REDIS_PORT` du `.env` (étape 6) doivent correspondre.

---

## 11. Tâches planifiées (remplace Celery)

**Fait et vérifié en local (2026-07-15)** : Celery a été entièrement retiré du
projet (aucun worker persistant possible sous Passenger de toute façon). Deux
mécanismes le remplacent, voir `CLAUDE.md` section « Tâches asynchrones » :

1. **À la demande** (calcul d'embedding à la sauvegarde d'un profil/offre,
   recommandations accueil) : thread démon via
   `recrutement/background.py::lancer_en_arriere_plan()` — fonctionne
   directement sous Passenger, aucune configuration cPanel nécessaire.
2. **Rattrapage périodique** (couvre les threads interrompus par un
   redémarrage de l'app, etc.) : **cPanel > Outils avancés > Tâches Cron** :

```bash
# Recalcul des embeddings manquants toutes les 15 min
*/15 * * * * flock -n /tmp/recrutepro_embeddings.lock /home/<user>/virtualenv/recrutement/3.13/bin/python /home/<user>/recrutement/manage.py calculer_embeddings_manquants
```

Le `flock` est **indispensable** (recommandation officielle O2switch) : sans lui,
une tâche qui dépasse son intervalle peut s'empiler indéfiniment jusqu'à saturer
le compte.

---

## 12. Vérification finale

- Visiter `https://<domaine>/candidat/` et `https://<domaine>/entreprise/` — la
  page d'accueil doit se charger sans erreur 500.
- Se connecter avec le superutilisateur créé à l'étape 8, vérifier
  `/admin/`.
- **cPanel > Mesures > Erreurs** : consulter les logs applicatifs en cas de souci
  (équivalent d'un `tail -f` sur les erreurs Passenger/Django).
- Tester un flux complet (inscription candidat, connexion entreprise) pour
  confirmer que la base de données, l'email SMTP et les sessions fonctionnent.

---

## Points encore en suspens (ne pas les considérer comme résolus)

| Sujet | Statut |
|---|---|
| Rendu PDF/PNG (Playwright) | Non testé en réel sur O2switch — WeasyPrint déjà écarté (confirmé cassé) |
| Matching sémantique / ATS (torch, sentence-transformers) | Non testé en charge réelle (RAM/CPU) |
| Celery → thread démon + cron | **Fait et vérifié en local** le 2026-07-15 : `.delay()` remplacé par `lancer_en_arriere_plan()`, commande `calculer_embeddings_manquants` créée pour le cron. Reste à créer l'entrée cron réelle sur cPanel (§11) |
| pgvector → JSONField, SSE → polling | **Fait et vérifié** en local (voir historique du projet) |
| PostgreSQL → MySQL (driver, recherche plein texte, migrations) | **Fait et vérifié en local (WAMP MySQL 8.0.21)** le 2026-07-15 : `migrate` propre, 48/48 tests, recherche FULLTEXT + scoring ATS testés avec données de démo. Reste à vérifier : version MySQL réelle sur O2switch et son `default_storage_engine` (voir §4) |

Ce guide suppose que ces points seront retestés/complétés au fur et à mesure —
ne pas lancer un déploiement de production tant que les 2 premières lignes du
tableau n'ont pas de réponse claire.
