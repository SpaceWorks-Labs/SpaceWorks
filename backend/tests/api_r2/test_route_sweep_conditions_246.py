"""Decision 246: whole-API condition sweep over every makerspace-scoped route in the URLconf.

The routes are discovered at run time (so a new route is covered without editing this file) and
each scenario asserts one universal condition across all of them:

* anonymous callers are refused on every verb (no data, no state change);
* a Space Manager of ANOTHER space never reads or writes this space's data (cross-space isolation);
* a plain Member never gets a 201/204 from a mutating call on staff routes;
* no built-in role crashes a route (no 5xx) with every module on or every module off.

Failures are collected and reported together so one run shows every offending route.
"""
import re

import pytest
from rest_framework.test import APIClient

from apps.makerspaces.capabilities import FEATURES
from apps.makerspaces.module_registry import MODULE_KEYS
from apps.makerspaces.role_catalog import ROLE_CATALOG
from tests.accounts.reauth_helpers import force_recent_authenticate
from tests.api_r2.route_sweep_246 import fill, space_routes
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db

ROUTES = space_routes()
MUTATING = ("post", "patch", "delete")
REFUSED = {401, 403, 404, 405, 429}
MARKER = "zz-sweep-marker-space"


def _client(user=None):
    client = APIClient()
    client.raise_request_exception = False
    if user is not None:
        force_recent_authenticate(client, user=user)
    return client


def _everything_on(space):
    space.enabled_modules = sorted(MODULE_KEYS)
    space.enabled_features = sorted(FEATURES)
    space.save(update_fields=["enabled_modules", "enabled_features"])


def _call(client, verb, url):
    body = {} if verb in MUTATING else None
    try:
        return getattr(client, verb)(url, body, format="json") if body is not None else client.get(url)
    except Exception as error:  # a crashing view is itself a finding
        return error


def _retired(response):
    return response.status_code == 410 and b"certifications_retired" in response.content


def _sweep(client, space, verbs, accept):
    failures = []
    for route in ROUTES:
        url = fill(route, space.pk)
        for verb in verbs:
            response = _call(client, verb, url)
            if not isinstance(response, Exception) and _retired(response):
                continue  # decision 319 addendum: the retired certification surface answers 410 before auth or lookup
            if isinstance(response, Exception):
                failures.append(f"{verb.upper()} {route}: raised {type(response).__name__}")
            elif response.status_code >= 500 or not accept(response, verb):
                failures.append(f"{verb.upper()} {route}: {response.status_code}")
    return failures


def test_the_sweep_discovers_a_meaningful_route_set():
    assert len(ROUTES) > 100


def test_anonymous_is_refused_on_every_makerspace_route_and_verb():
    space = make_space(MARKER)
    _everything_on(space)
    failures = _sweep(_client(), space, ("get",) + MUTATING, lambda r, v: r.status_code in REFUSED)
    assert not failures, "anonymous reached:\n" + "\n".join(failures)


def test_a_manager_of_another_space_never_reads_or_writes_this_space():
    mine, theirs = make_space(MARKER), make_space("zz-sweep-other-space")
    for space in (mine, theirs):
        _everything_on(space)
    outsider = staff_account(theirs, "sweep-outsider", "space_manager")

    def refused(response, verb):
        if response.status_code in REFUSED:
            return True
        # A write with an empty body can be rejected as invalid before the tenant lookup on many routes; it still
        # writes nothing, so a 400 is accepted for mutating verbs only (a 2xx or 5xx never is).
        if verb != "get" and response.status_code == 400:
            return True
        return verb == "get" and response.status_code == 200 and MARKER.encode() not in response.content

    failures = _sweep(_client(outsider), mine, ("get",) + MUTATING, refused)
    assert not failures, "cross-space reach:\n" + "\n".join(failures)
    mine.refresh_from_db()
    assert mine.name == MARKER


# A member's own self-service writes (their erasure request, calendar feed token and public handle) are the
# member's right, not a staff route reached by mistake.
_OWN_DATA = re.compile(r"/member/makerspaces/\d+/(erasure-requests|event-calendar-feed/|profile/handle)")


def test_a_plain_member_never_creates_or_deletes_through_a_staff_route():
    space = make_space(MARKER)
    _everything_on(space)
    member = staff_account(space, "sweep-member", "member")
    failures = _sweep(_client(member), space, MUTATING, lambda r, v: r.status_code not in (201, 204) or _OWN_DATA.search(r.request["PATH_INFO"]))
    assert not failures, "member mutated:\n" + "\n".join(failures)


@pytest.mark.parametrize("slug", [role.slug for role in ROLE_CATALOG])
@pytest.mark.parametrize("modules_on", [True, False], ids=["all-modules-on", "all-modules-off"])
def test_no_built_in_role_crashes_any_route_with_modules_on_or_off(slug, modules_on):
    space = make_space(f"zz-sweep-{slug}-{'on' if modules_on else 'off'}".replace("_", "-"))
    if modules_on:
        _everything_on(space)
    else:
        space.enabled_modules, space.enabled_features = [], []
        space.save(update_fields=["enabled_modules", "enabled_features"])
    actor = staff_account(space, f"sweep-{slug}-{modules_on}", slug)
    failures = _sweep(_client(actor), space, ("get", "post"), lambda r, v: True)
    assert not failures, f"{slug} (modules_on={modules_on}) crashed:\n" + "\n".join(failures)
