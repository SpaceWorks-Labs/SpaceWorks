"""Station credentials are revoked when data comes back from a backup (#77 C#6, release 2 L11)."""
import pytest
from cryptography.fernet import Fernet
from django.core.cache import cache

from apps.audit.models import AuditLog
from apps.backup.recovery import enter_quarantine
from apps.backup.station_revocation import revoke_station_credentials
from apps.makerspaces.models_stations import StationCredential
from tests.account_split.sweep_g1_helpers import event_staff as make_staff
from tests.makerspaces.test_kiosk_stations import create, kiosk_space, start

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def kiosk_keys(settings):
    from tests.makerspaces.test_kiosk_stations import ORIGIN
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode("ascii")
    settings.EVENT_STATION_PIN_PEPPER = "test-only-independent-station-pepper"
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]
    cache.clear()
    yield
    cache.clear()


def _station(slug):
    space = kiosk_space(slug)
    staff = make_staff(space)
    payload = create(staff, space).data
    return space, payload


def test_a_deployment_quarantine_revokes_every_station_url_and_pin():
    from tests.backup.test_recovery import recovery_fixture
    first, first_payload = _station("station-q-1")
    second, _second_payload = _station("station-q-2")
    _admin, _other, restore = recovery_fixture()
    enter_quarantine(restore, "disaster restore")
    rows = StationCredential.objects.all()
    assert rows.count() == 2 and not rows.filter(is_enabled=True).exists()
    assert str(rows.get(station__makerspace=first).public_token) != first_payload["public_token"]
    # The quarantined deployment answers 503 to everyone; the old token no longer names a station.
    assert not StationCredential.objects.filter(public_token=first_payload["public_token"]).exists()
    audit = AuditLog.objects.get(action="station_credentials.revoked_on_restore")
    assert audit.meta == {"scope": "deployment", "revoked": 2}


def test_a_per_space_revocation_leaves_other_spaces_working():
    first, first_payload = _station("station-s-1")
    second, second_payload = _station("station-s-2")
    assert revoke_station_credentials(makerspace=first) == 1
    assert not StationCredential.objects.get(station__makerspace=first).is_enabled
    assert StationCredential.objects.get(station__makerspace=second).is_enabled
    _client, response = start(second_payload)
    assert response.status_code in (200, 201)
    assert AuditLog.objects.get(action="station_credentials.revoked_on_restore").makerspace_id == first.pk


def test_the_per_space_restore_calls_the_revocation_inside_its_transaction():
    import inspect
    from apps.backup import space_restore_runner
    source = inspect.getsource(space_restore_runner._apply_and_restore_objects)
    assert source.index("apply_space_restore(locked, archive)") < source.index("revoke_station_credentials(")
    assert source.index("revoke_station_credentials(") < source.index("finally:")


def test_a_real_per_space_restore_revokes_that_spaces_station_credentials(restore_keys):
    from apps.backup import space_restore_runner as runner, space_restore_services as services
    from tests.backup.test_space_restore_flow import _backup, _superadmin
    from tests.encryption.conftest import enabled_encryption

    with enabled_encryption():
        root = _superadmin()
        space, payload = _station("station-restore")
        archive = _backup(space, root)
        op = services.request_restore(root, space, archive)
        runner.run_preview(op.pk)
        services.confirm_restore(root, op.__class__.objects.get(pk=op.pk), space.slug)
        done = runner.run_apply(op.pk)
        assert done.stage == "completed", (done.error_code, done.error_detail)
        assert done.report["station_credentials_revoked"] == 1
        credential = StationCredential.objects.get(station__makerspace=space)
        assert not credential.is_enabled and str(credential.public_token) != payload["public_token"]


from tests.backup.test_space_restore_flow import restore_keys  # noqa: E402,F401  (fixture)
