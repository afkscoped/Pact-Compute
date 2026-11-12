"""Artifact byte storage: a small interface with a local-disk default and an S3-compatible backend.

Artifacts are content-addressed by SHA-256, so writes are idempotent and every read is verified
against its digest. Select the backend with environment variables:

  PACT_ARTIFACT_BACKEND = local (default) | s3
  local: files under $PACT_STATE_DIR/artifacts
  s3:    PACT_S3_BUCKET (required), PACT_S3_PREFIX (default "artifacts/"), PACT_S3_ENDPOINT_URL
         (optional: Cloudflare R2, Backblaze B2, MinIO ...), PACT_S3_REGION (optional);
         credentials come from the standard AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY variables.
         Requires boto3 (see requirements-s3.txt).
"""
import hashlib
import os
import re
import secrets
from pathlib import Path
from typing import Protocol

from .config import STATE

DIGEST = re.compile(r'^[0-9a-f]{64}$')


class StorageError(Exception):
    """Artifact bytes are missing, unreachable or failed their integrity check."""


class MissingArtifact(StorageError):
    pass


class ArtifactStore(Protocol):
    name: str

    def put(self, digest: str, data: bytes) -> None: ...
    def get(self, digest: str) -> bytes: ...
    def exists(self, digest: str) -> bool: ...


def _check_digest(digest: str) -> None:
    if not DIGEST.match(digest):
        raise StorageError('Invalid artifact digest.')


def verified(digest: str, data: bytes) -> bytes:
    if hashlib.sha256(data).hexdigest() != digest:
        raise StorageError('Artifact content does not match its recorded SHA-256 digest.')
    return data


class LocalStore:
    name = 'local'

    def __init__(self, root: Path):
        self.root = root

    def path(self, digest: str) -> Path:
        _check_digest(digest)
        return self.root / digest

    def put(self, digest: str, data: bytes) -> None:
        verified(digest, data)
        target = self.path(digest)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            self.get(digest)  # An idempotent retry must not bless corrupt stored bytes.
            return
        staging = target.with_suffix('.' + secrets.token_hex(6) + '.part')  # temporary key, then publish atomically
        with open(staging, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        staging.replace(target)

    def get(self, digest: str) -> bytes:
        try:
            data = self.path(digest).read_bytes()
        except FileNotFoundError as error:
            raise MissingArtifact('Artifact bytes are unavailable.') from error
        return verified(digest, data)

    def exists(self, digest: str) -> bool:
        return self.path(digest).is_file()


class S3Store:
    name = 's3'

    def __init__(self, bucket: str, prefix: str = 'artifacts/', client=None, **client_options):
        if client is None:
            try:
                import boto3
            except ImportError as error:
                raise StorageError('PACT_ARTIFACT_BACKEND=s3 needs boto3: pip install -r requirements-s3.txt') from error
            client = boto3.client('s3', **{key: value for key, value in client_options.items() if value})
        self.client, self.bucket = client, bucket
        self.prefix = prefix if not prefix or prefix.endswith('/') else prefix + '/'

    def key(self, digest: str) -> str:
        _check_digest(digest)
        return self.prefix + digest

    def put(self, digest: str, data: bytes) -> None:
        verified(digest, data)
        try:
            if self.exists(digest):
                self.get(digest)
                return
            # Single-object PUT is atomic: the key becomes visible only when the whole body is stored.
            self.client.put_object(Bucket=self.bucket, Key=self.key(digest), Body=data, ContentType='application/json',
                                   Metadata={'sha256': digest})
        except StorageError:
            raise
        except Exception as error:
            raise StorageError('Artifact upload failed: ' + type(error).__name__) from error

    def get(self, digest: str) -> bytes:
        try:
            data = self.client.get_object(Bucket=self.bucket, Key=self.key(digest))['Body'].read()
        except Exception as error:
            code = getattr(error, 'response', {}).get('Error', {}).get('Code', '')
            if code in ('NoSuchKey', '404', 'NotFound'):
                raise MissingArtifact('Artifact bytes are unavailable.') from error
            raise StorageError('Artifact download failed: ' + type(error).__name__) from error
        return verified(digest, data)

    def exists(self, digest: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self.key(digest))
            return True
        except Exception as error:
            code = getattr(error, 'response', {}).get('Error', {}).get('Code', '')
            if code in ('404', 'NoSuchKey', 'NotFound'):
                return False
            raise StorageError('Artifact lookup failed: ' + type(error).__name__) from error


_store: ArtifactStore | None = None


def build_store() -> ArtifactStore:
    backend = os.getenv('PACT_ARTIFACT_BACKEND', 'local').strip().lower()
    if backend == 'local':
        return LocalStore(STATE / 'artifacts')
    if backend == 's3':
        bucket = os.getenv('PACT_S3_BUCKET', '').strip()
        if not bucket:
            raise StorageError('PACT_S3_BUCKET is required when PACT_ARTIFACT_BACKEND=s3.')
        return S3Store(bucket, os.getenv('PACT_S3_PREFIX', 'artifacts/'), endpoint_url=os.getenv('PACT_S3_ENDPOINT_URL'),
                       region_name=os.getenv('PACT_S3_REGION'))
    raise StorageError('PACT_ARTIFACT_BACKEND must be "local" or "s3".')


def store() -> ArtifactStore:
    global _store
    if _store is None:
        _store = build_store()
    return _store


def use(replacement: ArtifactStore | None) -> None:
    """Replace the process-wide store (tests, or None to rebuild from the environment)."""
    global _store
    _store = replacement
