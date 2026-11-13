"""Security level: cross-tenant reads and writes leak neither data nor existence.

Two sweeps over routes discovered from the URLconf (a new route is covered the day it lands):

* **Existence**: a Space Manager asking about ANOTHER real makerspace gets exactly the answer they get for a
  makerspace id that does not exist, so ids cannot be probed.
* **Resource IDOR**: a Space Manager calls their OWN makerspace's routes with an object id that belongs to
  ANOTHER makerspace (request, event, bookable space, machine, member...). It must never answer with that
  object's data, and a write must never succeed.
"""
import re
import uuid

import pytest
from django.db import transaction
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.bookings.models import BookableSpace
from apps.events.models import Event
from apps.machines.models import Machine, MachineType
from apps.makerspaces.capabilities import FEATURES
from apps.makerspaces.module_registry import MODULE_KEYS
from django.urls import URLPattern, URLResolver, get_resolver
from tests.accounts.reauth_helpers import force_recent_authenticate
from tests.api_r2.route_sweep_246 import SKIP_FRAGMENTS, fill, space_routes
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import make_accepted_request, make_product, make_space

pytestmark = pytest.mark.django_db

MARKER = "zzbsecret"
GONE = 987654321
MAX_DISTINGUISHABLE = 0


def _empty_scoped_list(response):
    """A 200 for an outsider is only acceptable when the queryset scoped to them is empty."""
    if response.status_code != 200:
        return False
    if not response.content.strip():
        return True  # nothing returned
    try:
        data = response.json()
    except ValueError:
        return False
    rows = data.get("results") if isinstance(data, dict) else data
    return rows == [] or (isinstance(data, dict) and data.get("count") == 0)
WRITES = ("post", "patch", "delete")


def _everything_on(space):
    space.enabled_modules, space.enabled_features = sorted(MODULE_KEYS), sorted(FEATURES)
    space.save(update_fields=["enabled_modules", "enabled_features"])


def _client(user):
    client = APIClient(raise_request_exception=False)
    force_recent_authenticate(client, user=user)
    return client


def _call(client, verb, url):
    from django.core.cache import cache
    cache.clear()  # a throttle answering 429 to one of a pair would look like a difference
    with transaction.atomic():
        sid = transaction.savepoint()
        response = client.get(url) if verb == "get" else getattr(client, verb)(url, {}, format="json")
        transaction.savepoint_rollback(sid)
    return response


def _answer(response):
    """(status, machine-readable error code): the pair a client can tell apart."""
    data = getattr(response, "data", None)
    return response.status_code, data.get("code") if isinstance(data, dict) else None


def _retired(response):
    return response.status_code == 410 and b"certifications_retired" in response.content


@pytest.fixture
def tenants():
    mine, theirs = make_space("lvl-idor-mine"), make_space("lvl-idor-theirs")
    _everything_on(mine)
    _everything_on(theirs)
    return mine, theirs, staff_account(mine, "lvl-idor-manager", "space_manager"), \
        staff_account(theirs, "lvl-idor-owner", "space_manager")


def test_another_makerspace_answers_exactly_like_one_that_does_not_exist(tenants):
    mine, theirs, manager, _owner = tenants
    client = _client(manager)
    leaks, distinguishable = [], []
    for route in space_routes():
        for verb in ("get",) + WRITES:
            real = _call(client, verb, fill(route, theirs.pk))
            ghost = _call(client, verb, fill(route, GONE))
            if _retired(real) or real.status_code >= 500 or ghost.status_code >= 500:
                continue  # 5xx is the (other) sweep's concern; the retired surface answers 410 first
            real_key, ghost_key = _answer(real), _answer(ghost)
            if real_key != ghost_key:
                distinguishable.append(f"{verb.upper()} {route}: other space {real_key}, missing space {ghost_key}")
            own_page = route.startswith("api/v1/member/")  # filtered to the CALLER's own rows (e.g. guest passes, guardian consent)
            if real.status_code not in (400, 401, 403, 404, 405, 429) and not own_page and not _empty_scoped_list(real):
                leaks.append(f"{verb.upper()} {route}: other space answered {real.status_code} with data")
    # Decision 481(1): staff routes used to answer 403 for a real other space and 404 for a missing one (140 cases),
    # because `require_module` resolved the space before RBAC ran. Standing in the space is now decided first
    # (apps/accounts/tenant_refusal.py), so the ceiling is zero and this sweep is the regression.
    assert len(distinguishable) <= MAX_DISTINGUISHABLE, (
        f"{len(distinguishable)} routes tell a real other space from a missing one (ceiling {MAX_DISTINGUISHABLE}):\n"
        + "\n".join(distinguishable))
    assert not leaks, f"{len(leaks)} routes leak data from another makerspace:\n" + "\n".join(leaks[:60])


# --- resource-level IDOR --------------------------------------------------------------------------------

_PARAM = re.compile(r"<(?:(?P<conv>[a-z]+):)?(?P<name>[a-zA-Z_]+)>")


def _walk(patterns, prefix=""):
    for entry in patterns:
        route = getattr(entry.pattern, "_route", None)
        if route is None:
            continue
        if isinstance(entry, URLResolver):
            yield from _walk(entry.url_patterns, prefix + route)
        elif isinstance(entry, URLPattern):
            yield prefix + route


@pytest.fixture
def their_objects(tenants):
    mine, theirs, _manager, owner = tenants
    product = make_product(theirs, name=f"{MARKER} product")
    request = make_accepted_request(theirs, product, 1)
    from datetime import timedelta
    from django.utils import timezone
    start = timezone.now() + timedelta(days=2)
    event = Event.objects.create(makerspace=theirs, title=f"{MARKER} event", starts_at=start,
                                 ends_at=start + timedelta(hours=1), status=Event.Status.PUBLISHED, is_public=True)
    room = BookableSpace.objects.create(makerspace=theirs, name=f"{MARKER} room", is_public=True, is_active=True)
    mtype = MachineType.objects.create(slug="lvl-idor-type", name=f"{MARKER} type", makerspace=theirs, is_builtin=False,
                                       managing_action="")
    machine = Machine.objects.create(makerspace=theirs, machine_type=mtype, name=f"{MARKER} machine")
    return {"request_id": request.pk, "product_id": product.pk, "event_id": event.pk, "space_id": room.pk,
            "machine_id": machine.pk, "type_id": mtype.pk, "machine_type_id": mtype.pk, "user_id": owner.pk}


def _routes_for(their_objects):
    found = set()
    for route in _walk(get_resolver().url_patterns):
        if "<int:makerspace_id>" not in route or not route.startswith("api/v1/") or "<int:pk>" in route:
            continue
        if any(fragment in route for fragment in SKIP_FRAGMENTS):
            continue
        names = {m["name"] for m in _PARAM.finditer(route)} - {"makerspace_id"}
        if names & set(their_objects):
            found.add(route)
    return sorted(found)


def _fill(route, makerspace_id, objects):
    def sub(match):
        name, conv = match["name"], match["conv"]
        if name == "makerspace_id":
            return str(makerspace_id)
        if name in objects:
            return str(objects[name])
        if conv == "int":
            return "987654"
        return str(uuid.UUID(int=987654)) if conv == "uuid" else "zz-none"
    return "/" + _PARAM.sub(sub, route)


def test_the_resource_sweep_finds_routes(their_objects):
    assert len(_routes_for(their_objects)) > 20


def test_my_manager_cannot_reach_another_makerspaces_objects_through_my_own_routes(tenants, their_objects):
    mine, _theirs, manager, _owner = tenants
    client = _client(manager)
    failures = []
    for route in _routes_for(their_objects):
        url = _fill(route, mine.pk, their_objects)
        for verb in ("get",) + WRITES:
            response = _call(client, verb, url)
            if _retired(response):
                continue
            body = response.content.decode("utf8", "ignore")
            if response.status_code >= 500:
                failures.append(f"{verb.upper()} {route}: crashed {response.status_code}")
            elif MARKER in body:
                failures.append(f"{verb.upper()} {route}: returned another makerspace's data")
            elif verb == "get" and response.status_code not in (403, 404, 405):
                failures.append(f"{verb.upper()} {route}: read answered {response.status_code}, expected 403, 404 or 405 (no GET)")
            elif verb != "get" and response.status_code not in (400, 403, 404, 405):
                failures.append(f"{verb.upper()} {route}: write answered {response.status_code}, expected a refusal")
    assert not failures, f"{len(failures)} cross-tenant object reaches:\n" + "\n".join(failures[:60])


def test_the_same_routes_do_serve_the_owner_so_the_sweep_is_not_vacuous(tenants, their_objects):
    _mine, theirs, _manager, owner = tenants
    client = _client(owner)
    served = [r for r in _routes_for(their_objects)
              if _call(client, "get", _fill(r, theirs.pk, their_objects)).status_code == 200]
    assert len(served) >= 3, served
