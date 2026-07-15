"""Migre les fichiers locaux media/ vers les buckets MinIO."""
import os

import boto3
from django.conf import settings
from django.core.management.base import BaseCommand


PUBLIC_PREFIXES = [
    'users/photos/', 'candidat/photos/', 'entreprise/logos/',
    'modeles_cv/apercu/', 'portfolios/apercu/', 'modeles_lettre/apercu/',
    'site/logo/', 'newsletter/actualites/',
]

KYC_PREFIXES = [
    'entreprise/verifications/rccm/',
    'entreprise/verifications/identite/',
]

EXCLUDE_PREFIXES = ['ml_models/']


def _bucket_for_path(rel_path):
    for prefix in EXCLUDE_PREFIXES:
        if rel_path.startswith(prefix):
            return None
    for prefix in KYC_PREFIXES:
        if rel_path.startswith(prefix):
            return 'private-kyc'
    for prefix in PUBLIC_PREFIXES:
        if rel_path.startswith(prefix):
            return 'public-media'
    return 'private-media'


class Command(BaseCommand):
    help = 'Migre les fichiers de media/ vers MinIO'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Affiche ce qui serait migré sans rien faire')
        parser.add_argument('--skip-existing', action='store_true',
                            help='Ne pas réécrire les fichiers déjà présents')

    def handle(self, *args, **options):
        if not getattr(settings, 'USE_MINIO', False):
            self.stderr.write('USE_MINIO is not True in settings. Aborting.')
            return

        dry_run = options['dry_run']
        skip_existing = options['skip_existing']
        media_root = str(settings.MEDIA_ROOT)

        client = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1'),
        )

        stats = {'uploaded': 0, 'skipped': 0, 'excluded': 0}

        for dirpath, _dirs, filenames in os.walk(media_root):
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(full_path, media_root).replace('\\', '/')

                bucket = _bucket_for_path(rel_path)
                if bucket is None:
                    stats['excluded'] += 1
                    continue

                if skip_existing:
                    try:
                        client.head_object(Bucket=bucket, Key=rel_path)
                        stats['skipped'] += 1
                        continue
                    except client.exceptions.ClientError:
                        pass

                if dry_run:
                    self.stdout.write(f'  [DRY] {rel_path} → {bucket}')
                    stats['uploaded'] += 1
                    continue

                client.upload_file(full_path, bucket, rel_path)
                stats['uploaded'] += 1

                if stats['uploaded'] % 50 == 0:
                    self.stdout.write(f'  ... {stats["uploaded"]} fichiers uploadés')

        action = 'seraient uploadés' if dry_run else 'uploadés'
        self.stdout.write(self.style.SUCCESS(
            f'Terminé — {stats["uploaded"]} {action}, '
            f'{stats["skipped"]} ignorés, {stats["excluded"]} exclus (ml_models)'
        ))
