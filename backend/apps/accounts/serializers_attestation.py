"""Document native proof formats while preserving external-verifier payloads."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


@extend_schema_field({
    "anyOf": [
        {"type": "object", "required": ["type", "token"], "properties": {
            "type": {"type": "string", "enum": ["play_integrity"]},
            "token": {"type": "string", "maxLength": 65536},
        }},
        {"type": "object", "required": ["type", "key_id", "attestation"], "properties": {
            "type": {"type": "string", "enum": ["app_attest"]},
            "key_id": {"type": "string", "format": "byte", "maxLength": 64},
            "attestation": {"type": "string", "format": "byte", "maxLength": 65536},
        }},
        {"type": "object", "required": ["type"], "additionalProperties": False, "properties": {
            "type": {"type": "string", "enum": ["development"]},
        }, "description": "Only with development-insecure mode and a development registration."},
        {"type": "object", "description": "Deployment-specific external verifier proof."},
    ],
}, component_name="DeviceAttestationPayload")
class AttestationPayloadField(serializers.JSONField):
    pass


ATTESTATION_DESCRIPTION = (
    'Submit the returned challenge with the device login attestation payload: '
    'Android {"type":"play_integrity","token":"..."} uses Standard requestHash = '
    'base64url(SHA-256(challenge UTF-8)), without padding. '
    'iOS {"type":"app_attest","key_id":"<base64>","attestation":"<base64 CBOR>"} '
    'uses a fresh key and clientDataHash = SHA-256(challenge UTF-8). '
    'Development-insecure mode accepts {"type":"development"} for development registrations only. '
    'External verifiers retain their deployment-specific payload format. '
    'Verifier outages return attestation_unavailable (503); restart with a new challenge.'
)
