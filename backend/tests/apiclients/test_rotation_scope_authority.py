"""A replacement secret must not convey scopes the actor cannot grant."""

from datetime import timedelta

import pytest
from cryptography.fernet import Fernet
from django.utils import timezone

from apps.accounts import rbac
from apps.accounts.models import User
from apps.apiclients.models import ApiClient
from apps.apiclients.scope_grants import SUPERADMIN_ONLY_SCOPES
from apps.audit.models import AuditLog
from tests.return_helpers import authenticated_client, make_space, make_user

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("scope", sorted(SUPERADMIN_ONLY_SCOPES) + ["public:read", "public:write"])
@pytest.mark.parametrize("authority", ["tenant", "operator"])
def test_rotation_checks_existing_scope_authority(settings, scope, authority):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    space = make_space("rotation-authority")
    if authority == "tenant":
        actor = make_user("rotation-manager", access_status=User.AccessStatus.ACTIVE,
                          account_kind="staff", staff_makerspace=space)
        from tests.fixed_roles.helpers import assign_builtin_roles
        assign_builtin_roles(actor, space, "space_manager")
    else:
        actor = make_user("rotation-operator", role=User.Role.SUPERADMIN,
                          access_status=User.AccessStatus.ACTIVE)
    assert rbac.can(actor, rbac.Action.MANAGE_MAKERSPACE, space.pk)
    # Fixed roles: a tenant Space Manager holds every domain action, yet superadmin-only
    # scopes stay refused below -- domain authority never conveys them.

    dependencies = {
        "participants:read": ["events:read"],
        "participants:attendance:read": ["events:read", "participants:read"],
        "bookings:attendance:read": ["bookings:read"],
    }
    scopes = [*dependencies.get(scope, []), scope]
    credential, old_secret = ApiClient.issue(
        label="Operator integration", makerspace=space, client_type="server",
        allowed_origins=["https://integration.example"], scopes=scopes,
    )
    # A refused rotation must also preserve any grace window already in flight.
    credential.previous_secret_encrypted = credential.secret_encrypted
    credential.previous_secret_valid_until = timezone.now() + timedelta(hours=1)
    credential.save(update_fields=["previous_secret_encrypted", "previous_secret_valid_until"])
    fields = ("secret_encrypted", "previous_secret_encrypted", "previous_secret_valid_until", "updated_at")
    before = ApiClient.objects.values(*fields).get(pk=credential.pk)

    # This helper creates genuine recent proof for this browser session.
    response = authenticated_client(actor).post(
        f"/api/v1/admin/api-clients/{credential.pk}/rotate-secret", format="json",
    )
    credential.refresh_from_db()
    audits = AuditLog.objects.filter(action="api_client.secret_rotated", target_id=str(credential.pk))
    if scope in SUPERADMIN_ONLY_SCOPES and authority != "operator":
        assert response.status_code == 403
        assert "client_secret" not in response.data
        assert ApiClient.objects.values(*fields).get(pk=credential.pk) == before
        assert not audits.exists()
    else:
        assert response.status_code == 200, response.data
        assert response.data["client_secret"] != old_secret
        assert credential.get_secret() == response.data["client_secret"]
        assert credential.previous_secret_encrypted == before["secret_encrypted"]
        assert credential.previous_secret_valid_until > before["previous_secret_valid_until"]
        assert credential.scopes == scopes
        assert audits.get().actor_id == actor.pk
