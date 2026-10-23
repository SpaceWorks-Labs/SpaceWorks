"""Account-specific brokers and bounded health probes; never tenant plaintext mode."""

import hashlib
import secrets
import struct

from django.conf import settings

from apps.encryption.brokers.base import WrappedDek, require_dek
from apps.encryption.brokers.local import BinaryFernet
from apps.encryption.crypto import PiiUnavailable
from apps.transaction_guards import in_domain_transaction


class SavedDetailsUnavailable(PiiUnavailable):
    code = "saved_details_unavailable"
    status_code = 503


def require_outside_transaction():
    if in_domain_transaction():
        raise RuntimeError("Account broker preparation must run outside database transactions.")


class AccountLocalBroker:
    backend = "local"

    def __init__(self):
        self.current = BinaryFernet(getattr(settings, "ACCOUNT_PII_MASTER_KEY", ""))
        previous = getattr(settings, "ACCOUNT_PII_MASTER_KEY_PREVIOUS", "")
        self.previous = BinaryFernet(previous) if previous else None

    @property
    def broker_key_id(self):
        import base64
        key = settings.ACCOUNT_PII_MASTER_KEY
        raw = base64.urlsafe_b64decode(key.encode() if isinstance(key, str) else key)
        return "sha256:" + hashlib.sha256(raw).hexdigest()

    def create_dek(self, user_id, version):
        return self.wrap_dek(secrets.token_bytes(32), user_id, version)

    def wrap_dek(self, dek, user_id, version):
        require_outside_transaction()
        payload = b"account-pii-v1\0" + struct.pack(">QQ", user_id, version) + require_dek(dek)
        return WrappedDek(dek, self.current.encrypt(payload), self.broker_key_id)

    def unwrap_dek(self, wrapped_dek, user_id, version, **kwargs):
        require_outside_transaction()
        expected = b"account-pii-v1\0" + struct.pack(">QQ", user_id, version)
        for wrapping_key in (self.current, self.previous):
            if wrapping_key is None:
                continue
            try:
                payload = wrapping_key.decrypt(bytes(wrapped_dek))
                if payload[:len(expected)] != expected:
                    raise SavedDetailsUnavailable()
                return require_dek(payload[len(expected):])
            except Exception:
                continue
        raise SavedDetailsUnavailable()


class AccountKmsBroker:
    backend = "aws_kms"

    @staticmethod
    def _context(user_id, version):
        return {"application": "spaceworks-account-pii-v1", "account_id": str(user_id),
                "dek_version": str(version)}

    def _client(self):
        require_outside_transaction()
        import boto3
        from botocore.config import Config

        return boto3.client("kms", config=Config(connect_timeout=2, read_timeout=2,
                                                 retries={"total_max_attempts": 1}))

    def create_dek(self, user_id, version):
        return self.wrap_dek(secrets.token_bytes(32), user_id, version)

    def wrap_dek(self, dek, user_id, version):
        try:
            response = self._client().encrypt(
                KeyId=settings.ACCOUNT_PII_AWS_KMS_KEY_ID, Plaintext=require_dek(dek),
                EncryptionContext=self._context(user_id, version),
            )
            return WrappedDek(dek, bytes(response["CiphertextBlob"]), response["KeyId"])
        except Exception as exc:
            raise SavedDetailsUnavailable() from exc

    def unwrap_dek(self, wrapped_dek, user_id, version, *, broker_key_id=None):
        try:
            response = self._client().decrypt(
                CiphertextBlob=bytes(wrapped_dek),
                KeyId=broker_key_id or settings.ACCOUNT_PII_AWS_KMS_KEY_ID,
                EncryptionContext=self._context(user_id, version),
            )
            return require_dek(response["Plaintext"])
        except Exception as exc:
            raise SavedDetailsUnavailable() from exc


def get_broker(backend=None):
    try:
        configured = backend or getattr(settings, "ACCOUNT_PII_KEY_BROKER", "local")
        if configured == "local":
            return AccountLocalBroker()
        if configured == "aws_kms" and getattr(settings, "ACCOUNT_PII_AWS_KMS_KEY_ID", ""):
            return AccountKmsBroker()
    except Exception as exc:
        raise SavedDetailsUnavailable() from exc
    raise SavedDetailsUnavailable()


def assert_ready():
    require_outside_transaction()
    if not getattr(settings, "ACCOUNT_SAVED_DETAILS_ENABLED", False):
        raise SavedDetailsUnavailable()
    try:
        broker = get_broker()
        wrapped = broker.create_dek(0, 1)
        decoded = broker.unwrap_dek(wrapped.wrapped_dek, 0, 1,
                                    broker_key_id=wrapped.broker_key_id)
        if not secrets.compare_digest(decoded, wrapped.dek):
            raise SavedDetailsUnavailable()
    except Exception as exc:
        raise SavedDetailsUnavailable() from exc
    return True
