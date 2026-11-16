"""Staff delivery responses include the one-time link in DRF and OpenAPI."""

import pytest
from drf_spectacular.generators import SchemaGenerator

from apps.accounts.serializers_staff_invitations import (
    StaffInvitationDeliverySerializer,
    StaffInvitationSerializer,
)


def test_delivery_serializer_extends_the_invitation_fields_without_secrets():
    fields = StaffInvitationDeliverySerializer().fields
    # 23498a5e: the invite link is never handed to the inviter any more (redeemed with a code).
    assert set(fields) == set(StaffInvitationSerializer.Meta.fields) | {"delivery_status"}
    assert not {"token_digest", "email_ciphertext", "created_by", "accept_url"} & set(fields)


@pytest.mark.django_db
def test_staff_invitation_delivery_openapi_documents_link_and_errors():
    schema = SchemaGenerator().get_schema(request=None, public=True)
    properties = schema["components"]["schemas"]["StaffInvitationDelivery"]["properties"]
    assert {"delivery_status", "role_name"} <= set(properties) and "accept_url" not in properties  # 23498a5e
    for path, success in (
        ("/api/v1/admin/makerspaces/{makerspace_id}/staff-invitations/{invitation_id}/resend", "200"),
    ):
        responses = schema["paths"][path]["post"]["responses"]
        assert {success, "400", "401", "403", "404", "429"} <= set(responses)
        assert responses[success]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/StaffInvitationDelivery",
        }
    # The legacy create-by-POST is gone: the list path is read-only now (invitations are issued by granting a role).
    assert "post" not in schema["paths"]["/api/v1/admin/makerspaces/{makerspace_id}/staff-invitations"]
