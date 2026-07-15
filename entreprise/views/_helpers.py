"""Shared constants, validation helpers, and utility functions used across view modules."""
import logging

from django.core.exceptions import ValidationError

from ..models import (
    TypeContrat, ModeTravail, ExperienceRequise,
)

logger = logging.getLogger(__name__)


# ── Reverse mapping referentiel -> TextChoices legacy ─────────────────────────
# Permet de conserver la compatibilite avec les filtres / templates existants
# qui lisent encore les CharField legacy (typeContrat, modeTravail, experienceRequise).

_REV_CONTRAT_LIBELLE_TO_CODE = {
    'CDI':                  TypeContrat.CDI,
    'CDD':                  TypeContrat.CDD,
    'Freelance / Mission':  TypeContrat.FREELANCE,
    'Stage':                TypeContrat.STAGE,
    'Alternance':           TypeContrat.ALTERNANCE,
}

_REV_MODE_LIBELLE_TO_CODE = {
    'Présentiel':   ModeTravail.PRESENTIEL,
    'Télétravail':  ModeTravail.REMOTE,
    'Hybride':      ModeTravail.HYBRIDE,
}

_REV_EXPERIENCE_LIBELLE_TO_CODE = {
    'Junior (0 – 2 ans)':   ExperienceRequise.JUNIOR,
    'Confirmé (2 – 5 ans)': ExperienceRequise.CONFIRME,
    'Senior (5 – 10 ans)':  ExperienceRequise.SENIOR,
    'Expert (10+ ans)':     ExperienceRequise.EXPERT,
}


# ── Validation des fichiers uploades ─────────────────────────────────────────

# Signatures binaires (magic bytes) des types MIME autorises.
# Chaque entree : (offset, octets_attendus)
_MAGIC_BYTES = {
    'image/jpeg': [(0, b'\xff\xd8\xff')],
    'image/png':  [(0, b'\x89PNG\r\n\x1a\n')],
    'image/gif':  [(0, b'GIF87a'), (0, b'GIF89a')],
    'image/webp': [(0, b'RIFF'), (8, b'WEBP')],
    'application/pdf': [(0, b'%PDF')],
}

_EXTENSIONS_IMAGE    = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
_EXTENSIONS_DOCUMENT = {'.pdf', '.jpg', '.jpeg', '.png'}


def _verifier_magic_bytes(file_obj, mime_types_autorises):
    """Lit les premiers octets du fichier pour verifier sa signature reelle."""
    file_obj.seek(0)
    header = file_obj.read(12)
    file_obj.seek(0)
    for mime in mime_types_autorises:
        for offset, signature in _MAGIC_BYTES.get(mime, []):
            if header[offset:offset + len(signature)] == signature:
                return True
    return False


def _valider_fichier_image(file_obj, max_mo=2):
    """
    Valide un fichier image uploade :
      - Taille maximale
      - Extension autorisee
      - Signature binaire reelle (protection contre les fichiers renommes)
    Leve ValidationError si invalide.
    """
    if file_obj.size > max_mo * 1024 * 1024:
        raise ValidationError(f'Le fichier ne doit pas dépasser {max_mo} Mo.')

    ext = '.' + file_obj.name.rsplit('.', 1)[-1].lower() if '.' in file_obj.name else ''
    if ext not in _EXTENSIONS_IMAGE:
        raise ValidationError('Format non autorisé. Utilisez JPG, PNG, GIF ou WebP.')

    mimes_images = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if not _verifier_magic_bytes(file_obj, mimes_images):
        raise ValidationError('Le fichier ne semble pas être une image valide.')


def _valider_fichier_document(file_obj, max_mo=5):
    """
    Valide un document (PDF ou image) uploade :
      - Taille maximale
      - Extension autorisee
      - Signature binaire reelle
    Leve ValidationError si invalide.
    """
    if file_obj.size > max_mo * 1024 * 1024:
        raise ValidationError(f'Le fichier ne doit pas dépasser {max_mo} Mo.')

    ext = '.' + file_obj.name.rsplit('.', 1)[-1].lower() if '.' in file_obj.name else ''
    if ext not in _EXTENSIONS_DOCUMENT:
        raise ValidationError('Format non autorisé. Utilisez PDF, JPG ou PNG.')

    mimes_docs = ['application/pdf', 'image/jpeg', 'image/png']
    if not _verifier_magic_bytes(file_obj, mimes_docs):
        raise ValidationError('Le fichier ne semble pas être un document valide.')
