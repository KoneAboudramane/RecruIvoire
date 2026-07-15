"""
Commande de traduction automatique des templates Django.

Traite les fichiers .html pour envelopper le texte hardcodé dans {% trans %}.

Usage :
    python manage.py traduire_templates                     # toutes les apps
    python manage.py traduire_templates --app candidat      # une seule app
    python manage.py traduire_templates --dry-run           # simulation sans écriture
    python manage.py traduire_templates --rapport           # rapport seul

Ce que la commande fait :
  1. Ajoute {% load i18n %} si absent
  2. Wraps le texte simple  →  {% trans "Texte" %}
  3. Wraps le texte avec variables  →  {% blocktrans %}...{% endblocktrans %}
  4. Wraps les attributs  placeholder/title/aria-label/alt  →  {% trans "..." %}
  5. Ignore : texte déjà traduit, scripts, styles, commentaires HTML, balises vides

Ce qu'elle ne fait PAS (à traiter manuellement) :
  - Texte mixte complexe avec multiples variables imbriquées
  - Chaînes dans les blocs <script>
  - Texte dans les attributs Alpine.js (:title, @click, x-text…)
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


# ── Patterns ──────────────────────────────────────────────────────────────────

# Texte entre balises HTML (capture uniquement le contenu texte pur)
RE_TEXT_NODE = re.compile(
    r'(?<=>)'                       # après un >
    r'(\s*[A-ZÀ-ÿa-z][^\n<>{%]{2,}?)'  # texte FR (commence par lettre, min 3 chars)
    r'(?=\s*(?:<|{[%{#]))',         # suivi d'une balise ou d'un tag Django
    re.UNICODE,
)

# Attributs HTML traduisibles
RE_ATTR = re.compile(
    r'((?:placeholder|title|aria-label|alt|data-title|data-tooltip)'
    r'\s*=\s*")'                    # nom=
    r'([^"{}%#\n]{3,})'            # valeur texte (pas de template tags)
    r'(")',
    re.UNICODE | re.IGNORECASE,
)

# Détecter si une chaîne contient des variables Django {{ }}
RE_HAS_VAR = re.compile(r'\{\{.+?\}\}')

# Blocs à ignorer (script, style, commentaires, balises auto-fermantes)
RE_SKIP_OPEN  = re.compile(r'<(script|style|pre|code|textarea)[^>]*>', re.IGNORECASE)
RE_SKIP_CLOSE = re.compile(r'</(script|style|pre|code|textarea)>', re.IGNORECASE)
RE_HTML_COMMENT = re.compile(r'<!--.*?-->', re.DOTALL)

# Déjà traduit
RE_ALREADY = re.compile(r'\{%[-\s]*(?:trans|blocktrans)\b')

# Texte inutile (espaces, ponctuation seule, chiffres, URLs, emojis seuls)
RE_SKIP_TEXT = re.compile(
    r'^[\s\d\W]*$'          # que des espaces/chiffres/ponctuation
    r'|^https?://'          # URL
    r'|^[•·–—:,;.!?/\\]+$',
    re.UNICODE,
)

# Texte trop court ou trop long pour être traduit
MIN_LEN = 3
MAX_LEN = 300


# ── Helpers ───────────────────────────────────────────────────────────────────

def _nettoyer(text: str) -> str:
    return text.strip()


def _est_traduisible(text: str) -> bool:
    t = _nettoyer(text)
    if len(t) < MIN_LEN or len(t) > MAX_LEN:
        return False
    if RE_SKIP_TEXT.search(t):
        return False
    # Ignorer si que des majuscules et chiffres (ex. ID techniques)
    if re.match(r'^[A-Z0-9_\-]+$', t):
        return False
    return True


def _wrapper_texte(text: str) -> str:
    """Enveloppe text dans {% trans %} ou {% blocktrans %}."""
    t = _nettoyer(text)
    if RE_HAS_VAR.search(t):
        # Remplacer {{ var }} par {{ var }} dans blocktrans (syntaxe valide)
        return '{%% blocktrans %%}%s{%% endblocktrans %%}' % t
    # Échapper les guillemets doubles
    escaped = t.replace('"', '\\"')
    return '{%% trans "%s" %%}' % escaped


def _traiter_template(content: str) -> tuple[str, int, list[str]]:
    """
    Traite le contenu d'un template HTML.
    Retourne (nouveau_contenu, nb_remplacement, avertissements).
    """
    warnings: list[str] = []
    replacements = 0

    # 1. Supprimer commentaires HTML temporairement (ne pas les modifier)
    html_comments: dict[str, str] = {}

    def save_comment(m):
        key = f'__HTMLCOMMENT_{len(html_comments)}__'
        html_comments[key] = m.group(0)
        return key

    content = RE_HTML_COMMENT.sub(save_comment, content)

    # 2. Identifier les blocs à ignorer (script/style) → les marquer
    skip_blocks: dict[str, str] = {}

    def save_skip(m):
        key = f'__SKIPBLOCK_{len(skip_blocks)}__'
        skip_blocks[key] = m.group(0)
        return key

    content = re.sub(
        r'<(script|style|pre|code|textarea)[^>]*>.*?</(script|style|pre|code|textarea)>',
        save_skip, content, flags=re.DOTALL | re.IGNORECASE,
    )

    # 3. Ignorer les blocs de tags Django complexes ({% block %}, {% for %}, etc.)
    # On ne touche pas aux lignes qui contiennent déjà des tags Django
    lines = content.split('\n')
    new_lines = []

    for line in lines:
        # Ne pas modifier les lignes qui sont des tags Django purs
        stripped = line.strip()
        if stripped.startswith('{%') or stripped.startswith('{{') or stripped.startswith('{#'):
            new_lines.append(line)
            continue

        # Ne pas modifier si déjà traduit sur cette ligne
        if RE_ALREADY.search(line):
            new_lines.append(line)
            continue

        # 4. Traiter les attributs traduisibles
        def replace_attr(m):
            nonlocal replacements
            prefix, value, suffix = m.group(1), m.group(2), m.group(3)
            if not _est_traduisible(value):
                return m.group(0)
            if RE_ALREADY.search(value) or RE_HAS_VAR.search(value):
                return m.group(0)
            escaped = value.strip().replace('"', '\\"')
            replacements += 1
            return f'{prefix}{{% trans "{escaped}" %}}{suffix}'

        line = RE_ATTR.sub(replace_attr, line)

        # 5. Traiter le texte entre balises
        def replace_text(m):
            nonlocal replacements
            text = m.group(1)
            clean = _nettoyer(text)
            if not _est_traduisible(clean):
                return m.group(0)
            # Vérifier qu'il n'y a pas de tag Django dans le texte
            if '{%' in text or '{{' in text or '{#' in text:
                warnings.append(f'Texte complexe (manuel) : {clean[:60]}')
                return m.group(0)
            wrapped = _wrapper_texte(clean)
            # Préserver les espaces autour
            leading  = text[: len(text) - len(text.lstrip())]
            trailing = text[len(text.rstrip()):]
            replacements += 1
            return leading + wrapped + trailing

        line = RE_TEXT_NODE.sub(replace_text, line)
        new_lines.append(line)

    content = '\n'.join(new_lines)

    # 6. Restaurer les blocs sauvegardés
    for key, val in skip_blocks.items():
        content = content.replace(key, val)
    for key, val in html_comments.items():
        content = content.replace(key, val)

    return content, replacements, warnings


def _ajouter_load_i18n(content: str) -> tuple[str, bool]:
    """Ajoute {% load i18n %} si pas encore présent."""
    if re.search(r'\{%\s*load\b[^%]*\bi18n\b', content):
        return content, False

    # Chercher le premier {% load ... %} existant pour y ajouter i18n
    m = re.search(r'(\{%\s*load\s+)([^%]+?)(\s*%\})', content)
    if m:
        new = m.group(1) + m.group(2).strip() + ' i18n' + m.group(3)
        return content.replace(m.group(0), new, 1), True

    # Pas de {% load %} du tout → insérer au tout début
    # Après {% extends %} si présent
    m_extends = re.search(r'(\{%\s*extends\s+[^%]+%\})', content)
    if m_extends:
        pos = m_extends.end()
        return content[:pos] + '\n{% load i18n %}' + content[pos:], True

    # Sinon tout au début
    return '{% load i18n %}\n' + content, True


# ── Commande ──────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Enveloppe le texte hardcodé des templates dans {% trans %} / {% blocktrans %}'

    def add_arguments(self, parser):
        parser.add_argument('--app',      help='Limiter à une app (candidat, entreprise, …)')
        parser.add_argument('--dry-run',  action='store_true', help='Simulation sans écriture')
        parser.add_argument('--rapport',  action='store_true', help='Rapport seul, pas de modification')

    def handle(self, *args, **options):
        dry_run   = options['dry_run'] or options['rapport']
        app_filtre = options.get('app')

        # Trouver les dossiers templates
        base = Path(settings.BASE_DIR)
        template_dirs: list[Path] = []
        for app in settings.INSTALLED_APPS:
            app_name = app.split('.')[-1]
            if app_filtre and app_name != app_filtre:
                continue
            td = base / app_name / 'templates'
            if td.exists():
                template_dirs.append(td)

        if not template_dirs:
            self.stdout.write(self.style.ERROR('Aucun dossier templates trouvé.'))
            return

        total_fichiers  = 0
        total_modifies  = 0
        total_rempl     = 0
        tous_warnings   = []

        for td in template_dirs:
            for html_path in sorted(td.rglob('*.html')):
                total_fichiers += 1
                try:
                    original = html_path.read_text(encoding='utf-8')
                except UnicodeDecodeError:
                    continue

                # Traitement
                content, nb_rempl, warns = _traiter_template(original)
                content, load_ajoute     = _ajouter_load_i18n(content)

                if content == original:
                    continue

                total_modifies += 1
                total_rempl    += nb_rempl
                rel = html_path.relative_to(base)
                self.stdout.write(
                    f'  {"[DRY] " if dry_run else "✏️  "}'
                    f'{rel}  '
                    f'({nb_rempl} rempl.'
                    + (', +load i18n' if load_ajoute else '')
                    + ')'
                )

                for w in warns:
                    tous_warnings.append(f'  ⚠  {rel}: {w}')

                if not dry_run:
                    html_path.write_text(content, encoding='utf-8')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'{"[DRY RUN] " if dry_run else ""}'
            f'{total_modifies}/{total_fichiers} templates modifiés — '
            f'{total_rempl} remplacements.'
        ))

        if tous_warnings:
            self.stdout.write(self.style.WARNING(
                f'\n{len(tous_warnings)} cas complexes à traiter manuellement :'
            ))
            for w in tous_warnings[:40]:
                self.stdout.write(w)
            if len(tous_warnings) > 40:
                self.stdout.write(f'  … et {len(tous_warnings) - 40} autres.')

        if not dry_run:
            self.stdout.write('')
            self.stdout.write('Prochaines étapes :')
            self.stdout.write('  python manage.py makemessages -a --no-wrap')
            self.stdout.write('  python manage.py compilemessages')
