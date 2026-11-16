"""Decision 244: every built-in role (and anonymous) is refused on the superadmin hosting/limits routes (233-236)."""
import pytest

from apps.audit.models import AuditLog
from apps.makerspaces.role_catalog import ROLE_CATALOG
from apps.managed_hosting import hosting_type
from apps.managed_hosting.models import PlatformHostingBillingSettings, PlatformThrottleRate
from tests.fixed_roles.helpers import staff_account

from .helpers import api, space, superadmin

pytestmark = pytest.mark.django_db
PLATFORM = "/api/v1/admin/platform"
REFUSED = (401, 403, 404)


@pytest.fixture
def hosting(settings, own_by_default):
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.MANAGED_PLANS_ENABLED = True
    return settings


def _routes(lab):
    return [
        ("put", f"{PLATFORM}/hosting-switch", {"enabled": False}),
        ("put", f"{PLATFORM}/spaces/{lab.pk}/hosting-type", {"hosting_type": "hosted"}),
        ("put", f"{PLATFORM}/spaces/{lab.pk}/limits", {"overrides": {"members": 1}}),
        ("put", f"{PLATFORM}/request-limits/login", {"rate": "20/min"}),
        ("get", f"{PLATFORM}/request-limits", None),
        ("get", f"{PLATFORM}/spaces/{lab.pk}/limits", None),
    ]


def _call(client, verb, url, body):
    return getattr(client, verb)(url, body, format="json") if body is not None else getattr(client, verb)(url)


@pytest.mark.parametrize("slug", [role.slug for role in ROLE_CATALOG])
def test_no_built_in_role_reaches_the_platform_hosting_routes(hosting, slug):
    lab = space(f"plat-{slug}".replace("_", "-"))
    actor = staff_account(lab, f"plat-actor-{slug}", slug)
    client = api(actor)
    for verb, url, body in _routes(lab):
        assert _call(client, verb, url, body).status_code in REFUSED, (verb, url)
    assert hosting_type.stored_type(lab) == "own"
    assert not PlatformThrottleRate.objects.exists()
    assert not AuditLog.objects.filter(action__startswith="managed_hosting.").exists()


def test_anonymous_is_refused_on_every_platform_hosting_route(hosting):
    lab = space("plat-anon")
    for verb, url, body in _routes(lab):
        assert _call(api(), verb, url, body).status_code in (401, 403), (verb, url)


def test_superadmin_validation_and_unknown_space_answers(hosting):
    root = superadmin()
    assert api(root).put(f"{PLATFORM}/spaces/999999/hosting-type", {"hosting_type": "own"},
                         format="json").status_code == 404
    lab = space("plat-valid")
    url = f"{PLATFORM}/spaces/{lab.pk}/hosting-type"
    assert api(root).put(url, {}, format="json").status_code == 400
    assert api(root).put(f"{PLATFORM}/hosting-switch", {}, format="json").status_code == 400
    assert hosting_type.stored_type(lab) == "own"


def test_changing_the_type_twice_to_the_same_value_keeps_one_row(hosting):
    from apps.managed_hosting.models import SpaceHostingType
    lab, root = space("plat-idem"), superadmin()
    url = f"{PLATFORM}/spaces/{lab.pk}/hosting-type"
    assert api(root).put(url, {"hosting_type": "hosted"}, format="json").status_code == 200
    assert api(root).put(url, {"hosting_type": "hosted"}, format="json").status_code == 200
    assert SpaceHostingType.objects.filter(makerspace=lab).count() == 1
    assert PlatformHostingBillingSettings.load().pk == 1
