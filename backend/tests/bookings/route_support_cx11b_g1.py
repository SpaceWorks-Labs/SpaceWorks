"""Real authenticated bookings worlds; no production gate or serializer doubles."""
from dataclasses import dataclass
from datetime import timedelta
from types import SimpleNamespace

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.bookings.models import BookableSpace, Booking
from tests.accounts.account_factories import make_staff
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.modules.switch_matrix_object_helpers import client_for, response_pair
from tests.modules.test_switch_matrix_objects_rest_isolation import rolled_back
from tests.modules.test_switch_matrix_objects_rest_support import domain_rows, no_domain_writes, switch
from tests.rbac_f6_helpers import community_member


@dataclass(frozen=True)
class Route:
    name: str
    method: str = "GET"
    keys: tuple = ("bookings",)
    status: int = 200
    audit: tuple = ()
    feature_code: str = "feature_disabled"
    standing: str = "private"

    @property
    def id(self):
        return self.name + ":" + self.method


def world(route, native):
    tenant = live_space("g1-bookings", MODULE_KEYS)
    actor = make_staff(tenant, username="g1-manager", password="G1-step-up-password-526!", access_status="active",
        email="g1-manager@example.test", email_verified_at=timezone.now())
    membership = community_member(tenant, "booker")
    member = membership.user
    room = BookableSpace.objects.create(makerspace=tenant, name="G1 retained studio", is_public=True,
        approval_mode="instant", show_public_availability=True, requester_notifications_enabled=False)
    now = timezone.now()
    start = (now + timedelta(days=3)).replace(microsecond=0)
    booking = Booking.objects.create(space=room, member=member, name="G1 booker", email=member.email,
        starts_at=start, ends_at=start + timedelta(hours=1), status="confirmed", note="Retained private note")
    foreign_tenant = live_space("g1-foreign", MODULE_KEYS)
    outsider = make_staff(foreign_tenant, username="g1-foreign-manager", access_status="active",
        password="G1-step-up-password-526!")
    foreign_room = BookableSpace.objects.create(makerspace=foreign_tenant, name="Foreign G1 room", is_public=True)
    Booking.objects.create(space=foreign_room, member=outsider, name="Foreign private booker",
        email="foreign-booker@example.test", starts_at=start, ends_at=start + timedelta(hours=1),
        status="confirmed", note="Foreign private booking note")
    foreign_tenant.frontend_domain = "g1-foreign.example.test"
    foreign_tenant.frontend_domain_status = "verified"
    foreign_tenant.save(update_fields=["frontend_domain", "frontend_domain_status"])
    client, foreign = client_for(actor, tenant, native), client_for(outsider, foreign_tenant, native)
    # This caller is admitted without an Origin pin; pin refusal is probed separately.
    return SimpleNamespace(route=route, native=native, tenant=tenant, actor=actor, member=member,
        membership=membership, room=room, booking=booking, start=start, now=now, foreign_tenant=foreign_tenant,
        outsider=outsider, client=client, foreign=foreign, kwargs={"pk": room.pk}, body={},
        off={}, foreign_off={}, foreign_pair=(404, "not_found"), foreign_check=None, media=None)


def window(w, *, moved=True):
    start = w.start + timedelta(days=1 if moved else 0)
    return {"starts_at": start.isoformat(), "ends_at": (start + timedelta(hours=1)).isoformat()}


def person_client(actor, tenant, native):
    """A real member device grant has no staff tenant or delegated staff authority."""
    if not native:
        return client_for(actor, tenant, False)
    from rest_framework.test import APIClient
    from apps.accounts import mfa_policy
    from apps.accounts.services_device_tokens import issue_device_token_pair
    from tests.accounts.account_factories import device_grant
    from tests.accounts.mfa_helpers import enrolled
    row, _ = enrolled(actor)
    mfa_policy.stamp(actor, row)
    grant = device_grant(actor)
    access, _refresh, _family = issue_device_token_pair(actor, grant)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}", HTTP_X_MAKERSPACE_ID=str(tenant.pk))
    return client


def equals(actual, expected):
    assert actual == expected


def fields(row, **expected):
    row.refresh_from_db()
    assert {key: getattr(row, key) for key in expected} == expected


def send(w, client):
    cache.clear()
    if getattr(w, "signed_send", None):
        return w.signed_send(client is w.foreign)
    body = w.body() if callable(w.body) else w.body
    if client is w.foreign and hasattr(w, "foreign_body"):
        body = w.foreign_body
    kwargs = {} if w.route.method == "GET" else {"format": "multipart" if w.media else "json"}
    url = getattr(w, "foreign_url", w.url) if client is w.foreign else w.url
    return getattr(client, w.route.method.lower())(url, body, **kwargs)


def audit_ids():
    return set(AuditLog.objects.values_list("pk", flat=True))


def success(w):
    before = audit_ids()
    response = send(w, w.client)
    assert response_pair(response) == (w.route.status, None), (w.route.id, getattr(response, "data", None))
    w.check(response)
    assert list(AuditLog.objects.exclude(pk__in=before).order_by("pk").values_list("action", flat=True)) == list(w.route.audit)
    return response


def refusal(w, key):
    return w.off.get(key, (404, w.route.feature_code if "." in key else "module_disabled"))


def outsider_probe(w, key=None):
    before = domain_rows()
    io = list(getattr(w, "io", []))
    if (not w.native and w.route.name.startswith("admin-")
            and w.route.standing in {"private", "discovery"}
            and "makerspace_id" not in w.kwargs):
        # The verified Origin pin refuses before the object lookup. Keep that
        # real 403 independently of the unpinned caller's concealment proof.
        w.foreign._credentials["HTTP_ORIGIN"] = "https://" + w.foreign_tenant.frontend_domain
        try:
            with no_domain_writes():
                pinned = send(w, w.foreign)
            assert response_pair(pinned) == (403, "permission_denied"), getattr(pinned, "data", None)
        finally:
            w.foreign._credentials.pop("HTTP_ORIGIN")
        assert domain_rows() == before
    with no_domain_writes():
        response = send(w, w.foreign)
    expected = w.foreign_off.get(key, w.foreign_pair)
    if key and w.route.standing == "public":
        expected = refusal(w, key)
    assert response_pair(response) == expected, (w.route.id, getattr(response, "data", None))
    if key and expected[0] == 200 and w.route.standing == "public":
        w.policy_off(key, response)
    elif w.foreign_check and expected[0] == 200:
        w.foreign_check(response)
    assert domain_rows() == before
    assert getattr(w, "io", []) == io
    if hasattr(w, "same"):
        with no_domain_writes():
            response = send(w, w.same)
        assert response_pair(response) == (404, "not_found"), (w.route.id, "same-space non-owner", getattr(response, "data", None))
        assert domain_rows() == before


def prove(w):
    """An actual effect, every dependency alone, standing in all states, retained writes."""
    w.url = reverse(w.route.name, kwargs=w.kwargs)
    w.url += getattr(w, "query_suffix", "")
    if w.native and w.route.standing in {"private", "owner", "personal-list", "discovery"}:
        # 494/524 preserve the native tenant-selection refusal at authentication.
        w.foreign_pair = (403, "permission_denied")
        w.foreign_off = {key: w.foreign_pair for key in w.route.keys}
    with rolled_back():
        success(w)
    outsider_probe(w)
    for key in w.route.keys:
        before = domain_rows()
        original = switch(w.tenant, key)
        outsider_probe(w, key)
        io = list(getattr(w, "io", []))
        with no_domain_writes():
            response = send(w, w.client)
        expected = refusal(w, key)
        assert response_pair(response) == expected, (w.route.id, key, getattr(response, "data", None))
        if expected[0] == 200:
            w.policy_off(key, response)
        assert domain_rows() == before
        assert getattr(w, "io", []) == io
        switch(w.tenant, key, original=original)
        assert domain_rows() == before
        outsider_probe(w)
        with rolled_back():
            success(w)
    success(w)
    written = domain_rows()
    for key in w.route.keys:
        original = switch(w.tenant, key)
        assert domain_rows() == written
        switch(w.tenant, key, original=original)
        assert domain_rows() == written
