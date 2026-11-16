"""Decision 545: every member machine route resolves its native tenant; no fallback grants."""
from uuid import UUID

import pytest
from django.test import RequestFactory
from django.urls import resolve, reverse
from django.urls.converters import UUIDConverter
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.machines import urls
from apps.machines.models import MachineSession, SupervisedSession, SupervisedUse
from apps.machines.models_type_setup import MachineTypeDocument
from apps.makerspaces.origin_scope import validate_native_makerspace_scope
from apps.makerspaces.origin_scope_routes import request_route_targets
from tests.accounts.account_factories import device_grant
from tests.machines.eta_helpers import job
from tests.machines.member_support_cx11b_g2 import member_world
from tests.machines.route_support_cx11b_g2 import toggle

pytestmark = [pytest.mark.django_db, pytest.mark.area_machines, pytest.mark.area_machine_service]


def request(name, kwargs, space, query=None):
    value = RequestFactory().get(reverse(name, kwargs=kwargs), query or {}, HTTP_X_MAKERSPACE_ID=str(space.pk))
    value.resolver_match = resolve(value.path)
    return value


def test_every_member_machine_route_has_a_native_target_resolver():
    # One domain URL inventory per test, including future routes. Surface admission
    # alone cannot catch the missing target mappings that broke the r4 phone proofs.
    seen = []
    for entry in urls.urlpatterns:
        if not str(entry.pattern).startswith("member/"):
            continue
        kwargs = {key: UUID(int=7) if isinstance(converter, UUIDConverter) else 7
                  for key, converter in entry.pattern.converters.items()}
        value = RequestFactory().get(reverse(entry.name, kwargs=kwargs), {"makerspace": 7})
        value.resolver_match = resolve(value.path)
        assert request_route_targets(value)[3] is True, entry.name
        seen.append(entry.name)
    assert seen and "member-machine-session-start" in seen


def subjects(w):
    now = timezone.now()
    session = MachineSession.objects.create(makerspace=w.space, machine=w.machine, machine_type=w.kind,
        member=w.member, source="member_qr", started_at=now)
    supervised = SupervisedSession.objects.create(makerspace=w.space, machine=w.machine,
        instructor=w.member, opened_at=now)
    use = SupervisedUse.objects.create(session=supervised, user=w.bystander, instructor=w.member, started_at=now)
    document = MachineTypeDocument.objects.create(makerspace=w.space, machine_type=w.kind, title="Native guide",
        object_key=f"machine-guides/{w.space.pk}/native.pdf", original_filename="native.pdf", content_type="application/pdf")
    return {"machine": w.machine, "job": job(w, member=w.member), "session": session,
            "supervised": supervised, "use": use, "document": document}


# Independent expected ownership: do not derive this table from the production catalogue.
ROUTES = [
    ("member-machine-job-detail", "job", "pk"),
    ("member-machine-job-approve-quote", "job", "pk"),
    ("member-machine-job-decline-quote", "job", "pk"),
    ("member-machine-job-resubmit", "job", "pk"),
    ("member-machine-job-consumables", "job", "pk"),
    ("member-machine-session-preview", "machine", "machine_id"),
    ("member-machine-session-start", "machine", "machine_id"),
    ("member-supervised-session-open", "machine", "machine_id"),
    ("member-machine-session-stop", "session", "pk"),
    ("member-supervised-session", "supervised", "pk"),
    ("member-supervised-supervisees", "supervised", "pk"),
    ("member-supervised-people", "supervised", "pk"),
    ("member-supervised-supervisee-remove", "supervised", "pk"),
    ("member-supervised-use-start", "supervised", "pk"),
    ("member-supervised-session-close", "supervised", "pk"),
    ("member-supervised-use-end", "use", "pk"),
    ("member-machine-type-document-url", "document", "pk"),
]


@pytest.mark.parametrize("key", ["machines", "machine_service", "machines.sessions", "machines.supervised_sessions"])
def test_native_object_targets_survive_switches_and_keep_foreign_selection_refused(key):
    w = member_world(False)
    rows = subjects(w)
    own, foreign = device_grant(w.member), device_grant(w.outsider)
    original = None
    for disabled in (False, True, False):
        if disabled:
            original = toggle(w.space, key)
        elif original is not None:
            toggle(w.space, key, original)
        for name, subject, kwarg in ROUTES:
            kwargs = {kwarg: rows[subject].pk}
            if name == "member-supervised-supervisee-remove":
                kwargs["user_id"] = w.bystander.pk
            value = request(name, kwargs, w.space)
            assert request_route_targets(value) == (name, {w.space.pk}, False, True)
            assert validate_native_makerspace_scope(value, w.member, own) == w.space.pk
            wrong = request(name, kwargs, w.other)
            with pytest.raises(PermissionDenied) as error:
                validate_native_makerspace_scope(wrong, w.outsider, foreign)
            assert (error.value.status_code, error.value.get_codes()) == (403, "permission_denied")
            assert str(error.value.detail) == "Makerspace target does not match the selected makerspace."
            missing = request(name, {**kwargs, kwarg: 9223372036854775807}, w.space)
            assert request_route_targets(missing) == (name, set(), True, True)
            with pytest.raises(PermissionDenied) as error:
                validate_native_makerspace_scope(missing, w.member, own)
            assert (error.value.status_code, error.value.get_codes()) == (403, "permission_denied")
            assert str(error.value.detail) == "Makerspace target could not be resolved."


@pytest.mark.parametrize("name", ["member-machine-jobs", "member-machine-sessions"])
def test_native_lists_require_the_parameter_the_view_actually_filters(name):
    w = member_world(False)
    grant = device_grant(w.member)
    value = request(name, {}, w.space, {"makerspace": w.space.pk})
    assert request_route_targets(value) == (name, {w.space.pk}, False, True)
    assert validate_native_makerspace_scope(value, w.member, grant) == w.space.pk
    for query in ({}, {"makerspace_id": w.space.pk}, {"makerspace": "invalid"},
                  {"makerspace": w.space.pk, "makerspace_id": w.other.pk}):
        with pytest.raises(PermissionDenied) as error:
            validate_native_makerspace_scope(request(name, {}, w.space, query), w.member, grant)
        assert (error.value.status_code, error.value.get_codes()) == (403, "permission_denied")
    # Browser callers may still read their complete owner history without selection.
    browser = RequestFactory().get(reverse(name))
    browser.resolver_match = resolve(browser.path)
    assert request_route_targets(browser) == (name, set(), False, True)
