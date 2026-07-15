"""
Commande de traduction automatique des fichiers .po.

Utilise deep-translator (Google Translate gratuit) pour remplir
les msgstr vides dans les fichiers de traduction.

Usage :
    python manage.py traduire_po                    # toutes les langues
    python manage.py traduire_po --locale en        # anglais seulement
    python manage.py traduire_po --locale en es     # anglais + espagnol
    python manage.py traduire_po --dry-run          # simulation
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


# Codes de langue pour deep-translator
LANGUE_CODES = {
    'en': 'en',
    'es': 'es',
    'ar': 'ar',
    'de': 'de',
    'it': 'it',
    'pt': 'pt',
    'zh_Hans': 'zh-CN',
    'zh-hans': 'zh-CN',
}

# Texte à ne pas traduire (variables Django, HTML, etc.)
RE_SKIP = re.compile(
    r'^\s*$'                    # vide
    r'|^[^a-zA-ZÀ-ÿ]*$'       # pas de lettres
    r'|^\d+$'                  # que des chiffres
    r'|^https?://'             # URL
    r'|^[A-Z_]+$'              # constantes
)

# Extraire les morceaux à préserver dans le texte (variables, HTML tags)
RE_PLACEHOLDER = re.compile(r'(\{\{[^}]+\}\}|<[^>]+>|%\([^)]+\)[sd]|%[sd]|\{[^}]+\})')


def _parser_po(content: str) -> list[dict]:
    """Parse un fichier .po en liste de blocs {msgid, msgstr, raw, start, end}."""
    blocs = []
    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        # Trouver un msgid
        if line.startswith('msgid "'):
            bloc_start = i
            # Lire le msgid (peut être multi-ligne)
            msgid_lines = [line]
            i += 1
            while i < len(lines) and lines[i].startswith('"'):
                msgid_lines.append(lines[i])
                i += 1
            # Lire le msgstr
            if i < len(lines) and lines[i].startswith('msgstr "'):
                msgstr_lines = [lines[i]]
                i += 1
                while i < len(lines) and lines[i].startswith('"'):
                    msgstr_lines.append(lines[i])
                    i += 1
                bloc_end = i
                blocs.append({
                    'msgid_lines':  msgid_lines,
                    'msgstr_lines': msgstr_lines,
                    'start':        bloc_start,
                    'end':          bloc_end,
                })
            continue
        i += 1
    return blocs


def _extraire_chaine(po_line_or_lines) -> str:
    """Extrait le texte d'une ou plusieurs lignes PO (gère le multi-ligne)."""
    if isinstance(po_line_or_lines, str):
        lines = [po_line_or_lines]
    else:
        lines = po_line_or_lines
    result = ''
    for line in lines:
        m = re.match(r'^(?:msgid|msgstr)\s+"(.*)"$', line)
        if m:
            result += m.group(1)
            continue
        m = re.match(r'^"(.*)"$', line)
        if m:
            result += m.group(1)
    # Décoder les séquences d'échappement PO
    return result.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')


def _encoder_po(text: str) -> str:
    """Encode le texte pour le format PO."""
    return text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


def _proteger_placeholders(text: str) -> tuple[str, dict]:
    """Remplace les variables/tags par des tokens neutres pour la traduction."""
    tokens = {}
    counter = [0]

    def replace(m):
        key = f'XPLACEHOLDERX{counter[0]}X'
        tokens[key] = m.group(0)
        counter[0] += 1
        return key

    protected = RE_PLACEHOLDER.sub(replace, text)
    return protected, tokens


def _restaurer_placeholders(text: str, tokens: dict) -> str:
    for key, val in tokens.items():
        text = text.replace(key, val)
    return text


class Command(BaseCommand):
    help = 'Traduit automatiquement les msgstr vides dans les fichiers .po'

    def add_arguments(self, parser):
        parser.add_argument(
            '--locale', nargs='+',
            help='Codes de langue à traiter (ex: en es de). Par défaut: toutes.',
        )
        parser.add_argument('--dry-run', action='store_true', help='Simulation sans écriture')
        parser.add_argument(
            '--batch', type=int, default=50,
            help='Nombre de chaînes à traduire avant pause (défaut: 50)',
        )
        parser.add_argument(
            '--pause', type=float, default=1.0,
            help='Secondes de pause entre batches (défaut: 1)',
        )

    def handle(self, *args, **options):
        try:
            from deep_translator import GoogleTranslator
        except ImportError:
            self.stderr.write(self.style.ERROR(
                'deep-translator non installé. Lancez : python -m pip install deep-translator'
            ))
            return

        dry_run    = options['dry_run']
        locales    = options.get('locale') or list(LANGUE_CODES.keys())
        batch_size = options['batch']
        pause      = options['pause']

        base = Path(settings.BASE_DIR) / 'locale'

        for locale in locales:
            # Chercher le fichier .po
            po_path = base / locale / 'LC_MESSAGES' / 'django.po'
            if not po_path.exists():
                # Essayer variantes (zh_Hans / zh-hans)
                for variant in [locale.replace('-', '_'), locale.replace('_', '-')]:
                    candidate = base / variant / 'LC_MESSAGES' / 'django.po'
                    if candidate.exists():
                        po_path = candidate
                        break
                else:
                    self.stdout.write(self.style.WARNING(f'Fichier non trouvé : {locale}'))
                    continue

            lang_code = LANGUE_CODES.get(locale, locale)
            self.stdout.write(f'\n🌐 Traitement de {locale} ({lang_code})…')

            content = po_path.read_text(encoding='utf-8')
            lines   = content.split('\n')
            blocs   = _parser_po(content)

            # Filtrer les blocs avec msgstr vide
            a_traduire = []
            for bloc in blocs:
                msgid = _extraire_chaine(bloc['msgid_lines'])
                msgstr = _extraire_chaine(bloc['msgstr_lines'])
                if msgstr:
                    continue  # Déjà traduit
                if not msgid or RE_SKIP.match(msgid):
                    continue
                a_traduire.append((bloc, msgid))

            self.stdout.write(f'  {len(a_traduire)} chaînes à traduire')

            if not a_traduire or dry_run:
                if dry_run:
                    self.stdout.write(self.style.WARNING(f'  [DRY RUN] {len(a_traduire)} traductions ignorées'))
                continue

            translator = GoogleTranslator(source='fr', target=lang_code)

            nb_ok    = 0
            nb_erreur = 0
            modifs: dict[int, str] = {}  # ligne_msgstr → nouvelle valeur

            for i, (bloc, msgid) in enumerate(a_traduire):
                # Protection des variables
                protected, tokens = _proteger_placeholders(msgid)

                try:
                    traduit = translator.translate(protected)
                    if traduit:
                        traduit = _restaurer_placeholders(traduit, tokens)
                        traduit_encoded = _encoder_po(traduit)
                        # Index de la ligne msgstr dans le fichier
                        msgstr_line_idx = bloc['start'] + len(bloc['msgid_lines'])
                        modifs[msgstr_line_idx] = f'msgstr "{traduit_encoded}"'
                        nb_ok += 1
                except Exception as e:
                    nb_erreur += 1
                    if nb_erreur <= 5:
                        self.stdout.write(self.style.WARNING(f'  ⚠ Erreur sur "{msgid[:40]}": {e}'))

                # Pause entre batches
                if (i + 1) % batch_size == 0:
                    self.stdout.write(f'  … {i + 1}/{len(a_traduire)} ({nb_ok} ok, {nb_erreur} erreurs)')
                    time.sleep(pause)

            # Appliquer les modifications
            for line_idx, new_line in modifs.items():
                if line_idx < len(lines):
                    lines[line_idx] = new_line
                    # Supprimer les lignes de continuation si l'original était multi-ligne
                    # (on repart d'un msgstr simple ligne)

            new_content = '\n'.join(lines)
            po_path.write_text(new_content, encoding='utf-8')

            self.stdout.write(self.style.SUCCESS(
                f'  ✅ {nb_ok} chaînes traduites, {nb_erreur} erreurs → {po_path.name}'
            ))

        if not dry_run:
            self.stdout.write('\nCompilation des fichiers .mo…')
            from django.core.management import call_command
            import os
            os.environ['PATH'] = r'C:\gettext\bin;' + os.environ.get('PATH', '')
            try:
                call_command('compilemessages', verbosity=0)
                self.stdout.write(self.style.SUCCESS('✅ Fichiers .mo compilés.'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Compilation manuelle requise : {e}'))
                self.stdout.write('  python manage.py compilemessages')
