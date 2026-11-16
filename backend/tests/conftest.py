import os

import pytest
from cryptography.fernet import Fernet
from apps.ed25519 import encode_key, generate_keypair
from django.core.cache import cache
from django.db import connection
from django.db.backends.base.base import BaseDatabaseWrapper
from django.test import SimpleTestCase


# Reuse the deployment key when the environment supplies one: migration 0004
# provisions the global scope key WRAPPED WITH IT, so generating a different key here
# would make that row un-unwrappable and every audit row silently unattested.
_TEST_AUDIT_MAC_MASTER_KEY = (
    os.environ.get("AUDIT_MAC_MASTER_KEY")
    or Fernet.generate_key().decode("ascii")
)
_TEST_BACKUP_PRIVATE_RAW, _TEST_BACKUP_PUBLIC_RAW = generate_keypair()
_TEST_BACKUP_PRIVATE_KEY = encode_key(_TEST_BACKUP_PRIVATE_RAW)
_TEST_BACKUP_PUBLIC_KEY = encode_key(_TEST_BACKUP_PUBLIC_RAW)


@pytest.fixture(autouse=True)
def disable_axes_by_default(settings, request):
    settings.AXES_ENABLED = False
    # S-C: never call Have I Been Pwned from the suite; its tests turn it on with a mocked transport.
    settings.PASSWORD_BREACH_CHECK_ENABLED = False
    # Browser fixtures need an explicitly trusted platform origin. Tests of origin
    # rejection override this default themselves; production trust is unchanged.
    settings.PLATFORM_STAFF_ORIGINS = ["http://localhost:5000"]
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.AUDIT_MAC_MASTER_KEY = _TEST_AUDIT_MAC_MASTER_KEY
    settings.BACKUP_ARCHIVE_SIGNING_PRIVATE_KEY = _TEST_BACKUP_PRIVATE_KEY
    settings.BACKUP_ARCHIVE_VERIFY_PUBLIC_KEY = _TEST_BACKUP_PUBLIC_KEY
    _reset_axes_state(request)
    yield
    settings.AXES_ENABLED = False
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.AUDIT_MAC_MASTER_KEY = _TEST_AUDIT_MAC_MASTER_KEY
    settings.BACKUP_ARCHIVE_SIGNING_PRIVATE_KEY = _TEST_BACKUP_PRIVATE_KEY
    settings.BACKUP_ARCHIVE_VERIFY_PUBLIC_KEY = _TEST_BACKUP_PUBLIC_KEY
    _reset_axes_state(request)


def _reset_axes_state(request):
    cache.clear()
    # The cron-mode channel-usage buffer is per-process: counts recorded against one test's (rolled
    # back) space would otherwise be written by a later test and fail its deferred FK check at teardown.
    from apps.accounts import channel_usage
    channel_usage._local.clear()

    try:
        from axes.handlers.proxy import AxesProxyHandler
        from axes.utils import reset
    except Exception:
        return

    AxesProxyHandler.implementation = None

    if not request.node.get_closest_marker("django_db"):
        return
    if connection.needs_rollback:
        return

    request.getfixturevalue("db")
    try:
        reset()
    except NotImplementedError:
        pass

@pytest.fixture(autouse=True)
def ensure_global_pii_write_fence(request):
    """Keep the singleton global PII write-fence present for DB tests.

    The H4 migration seeds ``PiiGlobalWriteFence`` (pk=1), but a transactional
    test's flush truncates it, which would make later transactional mapped
    writes and fence tests fail closed on a spuriously missing global fence.
    Re-seed it (open) before each DB test to preserve the production invariant.
    """
    if not request.node.get_closest_marker("django_db"):
        return
    if connection.needs_rollback:
        return
    request.getfixturevalue("db")
    from apps.encryption.models import PiiGlobalWriteFence

    PiiGlobalWriteFence.objects.get_or_create(pk=1)


_HANDLE_GATE_TESTS = ("test_secfix_b_handles.py", "test_username_required.py")


@pytest.fixture(autouse=True)
def handle_gate_is_opt_in(request, monkeypatch):
    """Decision 308 holds a real-token write until the person has a username.

    Production accounts get a default handle at profile creation or in the 0.12.0 backfill; test fixtures create
    bare `User` rows, so every bearer-token write in the suite would answer 403 `handle_required`. The gate is
    therefore off by default and exercised only by its own tests (`test_username_required.py`,
    `test_secfix_b_handles.py`, or any test marked `handle_gate`).
    """
    if request.node.get_closest_marker("handle_gate") or request.node.path.name in _HANDLE_GATE_TESTS:
        return
    from apps.makerspaces import handle_gate

    monkeypatch.setattr(handle_gate, "assert_handle_chosen", lambda request_, user: None)


@pytest.fixture(autouse=True)
def ensure_builtin_machine_types(request):
    """Re-seed the migration-seeded built-in machine types after a transactional test's flush.

    A `transaction=True` test truncates every table, including the global built-in `MachineType` rows migration
    0002 seeds; without them every later test that looks one up by slug fails with `DoesNotExist`.
    """
    if not request.node.get_closest_marker("django_db") or connection.needs_rollback:
        return
    request.getfixturevalue("db")
    from django.apps import apps as django_apps
    from apps.machines.models import MachineType

    if not MachineType.objects.filter(is_builtin=True, makerspace__isnull=True).exists():
        import importlib

        importlib.import_module("apps.machines.migrations.0002_seed_builtin_machine_types").seed_builtins(django_apps, None)
        # Migrations 0012/0017 then gave the printer and the metered packs their capability config;
        # a bare 0002 row would fail the printer-contract validators (`schema`, `accepted_materials`).
        importlib.import_module("apps.machines.migrations.0012_printer_machine_type_configuration").configure_printer_type(django_apps, None)
        importlib.import_module("apps.machines.migrations.0017_seed_machine_type_metering_packs").forward(django_apps, None)


@pytest.fixture(autouse=True)
def ensure_deployment_recovery_state(request):
    """Mirror the migration-seeded routing singleton after transactional flushes."""
    if not request.node.get_closest_marker("django_db") or connection.needs_rollback:
        return
    request.getfixturevalue("db")
    from apps.backup.models import DeploymentRecoveryState

    DeploymentRecoveryState.objects.get_or_create(pk=1)


@pytest.fixture(autouse=True)
def ensure_global_audit_mac_key(request, settings):
    """Mirror the deploy-time global-key provisioning invariant in DB tests."""
    settings.AUDIT_MAC_MASTER_KEY = _TEST_AUDIT_MAC_MASTER_KEY
    # This is a GENERATOR fixture, so every path must yield exactly once. A bare return
    # here raises "did not yield a value" and errors the test at setup -- which hits every
    # test that is not marked django_db, i.e. most of the suite.
    if (
        not request.node.get_closest_marker("django_db")
        or connection.needs_rollback
    ):
        yield
        return
    request.getfixturevalue("db")
    from apps.audit.keys import audit_mac_key_cache, provision_audit_mac_key

    audit_mac_key_cache.clear()
    provision_audit_mac_key()
    yield
    audit_mac_key_cache.clear()


@pytest.fixture(autouse=True)
def spaces_without_a_hosting_type_are_hosted(monkeypatch):
    """Decision 236: in production a space with no hosting-type row is OWN (never limited).

    The suite has hundreds of limit tests that create spaces through the ORM and set a platform
    domain plus overrides; treating a row-less space as HOSTED keeps them exercising enforcement.
    Hosting must still be on (a platform domain or the switch), and an explicit row always wins.
    Tests of the real default request the ``own_by_default`` fixture.
    """
    monkeypatch.setattr("apps.managed_hosting.hosting_type.ABSENT_TYPE", "hosted")


@pytest.fixture
def own_by_default(monkeypatch):
    """Opt back in to production's row-less default: own (decision 236)."""
    monkeypatch.setattr("apps.managed_hosting.hosting_type.ABSENT_TYPE", "own")


@pytest.fixture(autouse=True)
def evidence_objects_exist_by_default(monkeypatch):
    from apps.evidence import storage

    monkeypatch.setattr("apps.evidence.storage.object_exists", lambda key: True)

    def validate(object_key):
        if not storage.object_exists(object_key):
            raise storage.EvidenceObjectValidationError(
                "missing", "Evidence object was not found."
            )
        return storage.EvidenceValidationResult(size=123, content_type="image/jpeg")

    monkeypatch.setattr("apps.evidence.storage.validate_evidence_object", validate)



@pytest.fixture(autouse=True)
def all_modules_enabled_for_test_makerspaces(monkeypatch):
    """Give makerspaces created in tests every module.

    Modules are opt-in in production: a new makerspace gets core plus whatever
    install profile the operator chose. Almost every test here exercises a specific
    module's behaviour rather than the install default, so without this they would
    each have to enable the module under test -- noise that says nothing about the
    thing being tested.

    Only the *field* default is patched. Anything that reads
    `default_enabled_module_keys()` / `DEFAULT_ENABLED_MODULES` directly still sees
    the real opt-in value, which is how tests/makerspaces/test_module_registry.py and
    test_module_install.py keep asserting the production default.
    """
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.module_profiles import EVERYTHING, profile_modules

    field = Makerspace._meta.get_field("enabled_modules")
    monkeypatch.setattr(field, "default", lambda: profile_modules(EVERYTHING))
    # L17 (#97): every module used to include maintenance and procurement, and warranty
    # was never switchable. The folded capabilities keep that baseline for test spaces.
    from apps.makerspaces.capabilities import default_enabled_features
    from apps.makerspaces.module_profiles import profile_features
    features = Makerspace._meta.get_field("enabled_features")
    monkeypatch.setattr(features, "default", lambda: sorted(
        set(default_enabled_features()) | set(profile_features(EVERYTHING))))


class _EveryDatabase(frozenset):
    """A `databases` allow-set that also admits aliases created after setup.

    Iteration still yields only the real aliases, so Django's teardown flushes
    exactly the databases it created.
    """

    def __contains__(self, alias):
        return True


def _guarded_test_case():
    """The TestCase whose undeclared-database guard is currently installed.

    Django closes over the test class when it patches `ensure_connection`, and
    that class attribute is the only place the allow-set can be widened.
    """
    patched = BaseDatabaseWrapper.ensure_connection
    for cell in patched.__closure__ or ():
        value = cell.cell_contents
        if isinstance(value, type) and issubclass(value, SimpleTestCase):
            return value
    return None


@pytest.fixture
def allow_projection_databases():
    """Let a test open the short-lived databases it creates mid-test.

    Django rejects connections to aliases that did not exist when the test class
    was set up, which is the right default. The readable-main projection, the E7
    reconstruction verifier and the Lane D scratch projection each create,
    register and drop a real database mid-test, and `databases="__all__"` cannot
    express that because it is snapshotted at setup. The allow-set is widened for
    the duration and restored before class teardown unwraps the guard.

    Lives here rather than in one test module because three separate test
    packages need it.
    """
    case = _guarded_test_case()
    if case is None:
        yield
        return
    original = case.databases
    case.databases = _EveryDatabase(original)
    try:
        yield
    finally:
        case.databases = original


@pytest.fixture(autouse=True)
def activated_notification_deployment(request):
    """Ordinary domain tests use a reconciled deployment, never production defaults."""
    if (not request.node.get_closest_marker("django_db")
            or "receipt_only_cutover" in request.fixturenames
            or "push_migration_case" in request.fixturenames
            # Schema-migration tests manage their own state; match the file name only,
            # so the whole tests/tenant_migration/ directory is not excluded.
            or "migration" in request.node.path.name.lower()
            or request.node.get_closest_marker("notification_cutover_unactivated")):
        return
    request.getfixturevalue("db")
    from apps.integrations.models_cutover import NotificationCutover
    from django.utils import timezone
    now = timezone.now()
    NotificationCutover.objects.update_or_create(pk=1, defaults={
        "route": "canonical", "sending_enabled": True, "barrier_at": now,
        "copied_at": now, "reconciled_at": now, "activated_at": now})


@pytest.fixture(autouse=True)
def open_new_machines():
    """Decision 319: a new machine needs a machine access grant by default. The pre-319 suites build machines
    and expect members to use them, so every machine created in a test starts "open to all members" (what the
    upgrade migration gives ungated machines). `tests/parity_0120/machine_access` overrides this fixture to
    exercise the real default (grant required)."""
    from django.db.models.signals import pre_save

    from apps.machines.models import Machine

    def receiver(sender, instance, **kwargs):
        if instance._state.adding:
            instance.open_to_all_members = True

    pre_save.connect(receiver, sender=Machine, dispatch_uid="tests.open_new_machines")
    yield
    pre_save.disconnect(sender=Machine, dispatch_uid="tests.open_new_machines")


# LOCAL ONLY (R3 test phase): `--narrow-role` runs the whole session as the narrow runtime role
# spaceworks_app (RLS enforce), not the owner. Off unless the flag is passed.
def pytest_addoption(parser):
    parser.addoption("--narrow-role", action="store_true", default=False,
                     help="Reconnect every test as the narrow spaceworks_app role (RLS enforced).")


@pytest.fixture(scope="session", autouse=True)
def _narrow_runtime_role(request):
    if not request.config.getoption("--narrow-role"):
        yield
        return
    from tests._narrow.narrow_role import narrow_session
    yield from narrow_session(request)


@pytest.fixture(autouse=True)
def restore_contributions_ports():
    """`setup_shift` installs a fake programme adapter process-wide; put the real one back afterwards.

    Without this, any later test that runs a programme command (the showcase seed, for one) is
    answered by the previous test's fake bound to that test's event.
    """
    from apps.events.contributions import ports
    saved = ports._adapter
    yield
    ports._adapter = saved
