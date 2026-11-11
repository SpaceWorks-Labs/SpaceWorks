"""Self-host move (#128 C-18/C-23, #137 Q-B1, #160): SM request -> superadmin export -> import -> sign in.

Source and target are the same test database: the "target" is this server, whose restore
key is the one-shot recipient. Emails are blanked first, because a created person whose
email the target already holds refuses the import (#160(3)).
"""
import shutil
import subprocess

import pytest
from django.contrib.auth.hashers import check_password
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts.mfa_crypto import new_secret
from apps.accounts.models import User
from apps.accounts.models_mfa import UserMFA
from apps.audit.models import AuditLog
from apps.encryption.services import get_or_create_active_dek
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.secrets import decrypt_value, encrypt_value
from apps.tenant_migration import selfhost_move as moves
from apps.tenant_migration.models_selfhost_move import SelfHostMoveRequest
from apps.tenant_migration.selfhost_move_import import import_selfhost_move
from tests.accounts.account_factories import grant_staff_role, make_membership, make_staff
from tests.data_export.portable_helpers import make_space, make_user
from tests.encryption.conftest import enabled_encryption
from tests.tenant_migration.protocol_helpers import superadmin

pytestmark = pytest.mark.django_db(transaction=True)
SECRET = new_secret()


@pytest.fixture
def move_keys(settings, tmp_path, monkeypatch):
    if not all(shutil.which(binary) for binary in ("age", "age-keygen")):
        pytest.skip("the move round trip needs age and age-keygen")
    keys = {}
    for name in ("platform", "target"):
        identity = tmp_path / f"{name}.key"
        subprocess.run(["age-keygen", "-o", str(identity)], check=True, capture_output=True)
        keys[name] = (identity, subprocess.run(["age-keygen", "-y", str(identity)], check=True,
                                               capture_output=True, text=True).stdout.strip())
    settings.BACKUP_AGE_RECIPIENT = keys["platform"][1]
    settings.TENANT_MIGRATION_AGE_RECIPIENT = keys["target"][1]
    settings.TENANT_MIGRATION_AGE_IDENTITY_FILE = str(keys["target"][0])
    settings.BACKUP_OPS_DIR = str(tmp_path / "ops")
    settings.BACKUP_PRESIGN_DRAIN_SECONDS = 0
    settings.TENANT_MIGRATION_PRESIGN_DRAIN_SECONDS = 0
    settings.PUBLIC_APP_BASE_URL = "https://lab.example.test"
    monkeypatch.setattr(moves, "_dispatch", lambda *args: None)
    return keys


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_a_space_moves_to_a_fresh_server_and_its_staff_sign_in_there(move_keys):
    with enabled_encryption():
        root = superadmin("selfhost-root")
        space = make_space("selfhost-source")
        get_or_create_active_dek(space.pk)
        manager = make_staff(space, username="selfhost-manager", email="manager@selfhost.test")
        person = make_user("selfhost-tech")
        person.set_password("travelled-password-1")
        person.save(update_fields=["password"])
        make_membership(person, space)
        grant_staff_role(person, space, role_slug="machine_manager")
        UserMFA.objects.create(user=person, secret=encrypt_value(SECRET), enabled_at=person.date_joined,
                               recovery_digests=["pbkdf2_sha256$1$salt$digest"])
        url = f"/api/v1/admin/makerspace/{space.pk}/selfhost-move-request"

        created = _client(manager).post(url, {"note": "We are going self-hosted."}, format="json")
        assert created.status_code == 201, created.data
        assert created.data["request"]["status"] == "requested"
        again = _client(manager).post(url, {"note": "again"}, format="json")
        assert again.status_code == 409 and again.data["code"] == "move_request_exists"
        other = make_staff(make_space("selfhost-other"), username="selfhost-other-manager")
        assert _client(other).get(url).status_code in (403, 404)
        move = SelfHostMoveRequest.objects.get()
        with pytest.raises(moves.MoveConflict):
            moves.start_export(root, move, move_keys["target"][1])
        moves.decide(root, move, approve=True)
        with pytest.raises(ValidationError):
            moves.start_export(root, move, "not-a-key")
        moves.start_export(root, move, move_keys["target"][1])
        User.objects.exclude(pk=root.pk).update(email="")  # same database: no email may clash
        done = moves.run_export(move.pk, move_keys["target"][1], root.pk)
        assert done.status == "exported", done.failure_code
        status = _client(manager).get(url).data["request"]
        assert status["status"] == "exported" and "artifact_path" not in status

        job = import_selfhost_move(root, done.artifact_path, done.artifact_sha256, slug="selfhost-target")
        target = Makerspace.objects.get(pk=job.target_makerspace_id)
        assert target.slug == "selfhost-target" and target.lifecycle_state == "active"
        tech = MakerspaceMembership.staff_tracks.get(makerspace=target, assigned_role__slug="machine_manager")
        assert tech.status == "active" and tech.user_id != person.pk
        assert check_password("travelled-password-1", tech.user.password)
        assert decrypt_value(UserMFA.objects.get(user=tech.user).secret) == SECRET
        assert MakerspaceMembership.staff_tracks.filter(makerspace=target, assigned_role__slug="space_manager",
                                                        status="active").exists()
        actions = set(AuditLog.objects.filter(action__startswith="selfhost_move.").values_list("action", flat=True))
        assert {"selfhost_move.requested", "selfhost_move.approved", "selfhost_move.exported",
                "selfhost_move.imported"} <= actions


def test_only_the_superadmin_runs_a_move():
    space = make_space("selfhost-perm")
    manager = make_staff(space, username="selfhost-perm-manager")
    move = moves.request_move(manager, space, "please")
    with pytest.raises(Exception):
        moves.decide(manager, move, approve=True)
    assert SelfHostMoveRequest.objects.get().status == "requested"
