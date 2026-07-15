"""Crée les 3 buckets MinIO et configure la policy publique."""
import json

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand


BUCKETS = ['public-media', 'private-media', 'private-kyc']

PUBLIC_POLICY = {
    'Version': '2012-10-17',
    'Statement': [{
        'Effect': 'Allow',
        'Principal': '*',
        'Action': ['s3:GetObject'],
        'Resource': ['arn:aws:s3:::public-media/*'],
    }],
}


class Command(BaseCommand):
    help = 'Initialise les buckets MinIO (public-media, private-media, private-kyc)'

    def handle(self, *args, **options):
        if not getattr(settings, 'USE_MINIO', False):
            self.stderr.write('USE_MINIO is not True in settings. Aborting.')
            return

        client = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1'),
        )

        for bucket in BUCKETS:
            try:
                client.head_bucket(Bucket=bucket)
                self.stdout.write(f'  {bucket} — existe déjà')
            except ClientError:
                client.create_bucket(Bucket=bucket)
                self.stdout.write(self.style.SUCCESS(f'  {bucket} — créé'))

        client.put_bucket_policy(
            Bucket='public-media',
            Policy=json.dumps(PUBLIC_POLICY),
        )
        self.stdout.write(self.style.SUCCESS('Policy publique appliquée sur public-media'))
        self.stdout.write(self.style.SUCCESS('Buckets MinIO prêts.'))
