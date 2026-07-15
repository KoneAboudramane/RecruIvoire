from django.conf import settings
from django.core.files.storage import default_storage

try:
    from storages.backends.s3boto3 import S3Boto3Storage

    class PublicMediaStorage(S3Boto3Storage):
        bucket_name = 'public-media'
        default_acl = 'public-read'
        querystring_auth = False

    class PrivateMediaStorage(S3Boto3Storage):
        bucket_name = 'private-media'
        default_acl = 'private'
        querystring_auth = True
        querystring_expire = 3600

    class KYCStorage(S3Boto3Storage):
        bucket_name = 'private-kyc'
        default_acl = 'private'
        querystring_auth = True
        querystring_expire = 900

except ImportError:
    PublicMediaStorage = None
    PrivateMediaStorage = None
    KYCStorage = None


def get_public_storage():
    if getattr(settings, 'USE_MINIO', False) and PublicMediaStorage:
        return PublicMediaStorage()
    return default_storage


def get_private_storage():
    if getattr(settings, 'USE_MINIO', False) and PrivateMediaStorage:
        return PrivateMediaStorage()
    return default_storage


def get_kyc_storage():
    if getattr(settings, 'USE_MINIO', False) and KYCStorage:
        return KYCStorage()
    return default_storage
