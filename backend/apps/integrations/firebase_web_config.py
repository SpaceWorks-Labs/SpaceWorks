"""Public Firebase SDK identifiers; platform service-account secret stays separate."""
import json
import base64
import binascii
import re

from cryptography.fernet import InvalidToken
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from django.core.exceptions import ImproperlyConfigured
from rest_framework import serializers

from apps.makerspaces.telemetry_schema import FirebaseSerializer, StrictSerializer
from django.utils.translation import gettext


class FirebaseBrowserPublicSerializer(FirebaseSerializer):
    def validate_project_id(self, value):
        if value and not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", value):
            raise serializers.ValidationError(gettext("Use a Firebase project ID."))
        return value

    def validate_vapid_public_key(self, value):
        if not value:
            return value
        try:
            if not re.fullmatch(r"[A-Za-z0-9_-]{87}", value):
                raise ValueError
            decoded = base64.urlsafe_b64decode(value + "=")
            ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), decoded)
        except (ValueError, TypeError, binascii.Error):
            raise serializers.ValidationError(gettext("Use an uncompressed P-256 VAPID public key.")) from None
        return value


class FirebaseWebWriteSerializer(StrictSerializer):
    config = FirebaseBrowserPublicSerializer(allow_null=True)

    def validate_config(self, config):
        if config is None:
            return None
        required = ("api_key", "project_id", "app_id", "messaging_sender_id", "vapid_public_key")
        if not all(config[key] for key in required):
            raise serializers.ValidationError(gettext("Complete the Firebase web project, sender and VAPID fields."))
        return config


class FirebaseWebStateSerializer(serializers.Serializer):
    configured = serializers.BooleanField()
    config = FirebaseBrowserPublicSerializer(allow_null=True)


def service_project(row):
    try:
        account = json.loads(row.get_fcm_service_account())
        if not isinstance(account, dict):
            return None
        fields = ("project_id", "client_email", "private_key", "token_uri")
        if not all(isinstance(account.get(key), str) and account[key].strip() for key in fields):
            return None
        if not account["token_uri"].startswith("https://"):
            return None
        key = load_pem_private_key(account["private_key"].encode(), password=None)
        if not isinstance(key, rsa.RSAPrivateKey):
            return None
        return account["project_id"]
    except (ImproperlyConfigured, InvalidToken, UnsupportedAlgorithm, ValueError, TypeError, UnicodeError):
        return None


def effective(row):
    if row is None:
        return {"configured": False, "config": None}
    check = FirebaseWebWriteSerializer(data={"config": row.firebase_web_config})
    if not check.is_valid():
        return {"configured": False, "config": None}
    value = check.validated_data["config"]
    if not value or service_project(row) != value["project_id"]:
        return {"configured": False, "config": None}
    return {"configured": True, "config": value}
