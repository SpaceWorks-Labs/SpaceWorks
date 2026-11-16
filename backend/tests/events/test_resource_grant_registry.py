"""Future domain adapters must work without event-specific account imports."""

from types import SimpleNamespace

import pytest

from apps.accounts.mfa_policy import required
from apps.accounts.services_social_login import assert_staff_authority
from apps.makerspaces import resource_grant_sources as sources
from tests.events.ticketing_helpers import account, event_space

pytestmark = pytest.mark.django_db


def test_registration_is_query_free_idempotent_and_rejects_conflicts(monkeypatch, django_assert_num_queries):
    monkeypatch.setattr(sources, "_sources", {})
    source = sources.ResourceGrantSource("booking_grants", lambda *a, **k: False, lambda *a, **k: [])
    with django_assert_num_queries(0):
        sources.register(source)
        sources.register(source)
        assert sources.registered_sources() == (source,)
    with pytest.raises(ValueError):
        sources.register(sources.ResourceGrantSource("booking_grants", lambda *a, **k: True, source.entries))


def test_an_independent_domain_source_supplies_sign_in_payload_and_mfa(monkeypatch):
    monkeypatch.setattr(sources, "_sources", {})
    actor = account("booking-source-only")
    space = event_space("booking-source-policy")
    space.enabled_modules.remove("events")
    space.enabled_features = ["security.staff_mfa_required"]
    # Security keys change only through the security service; write the fixture row directly.
    type(space).objects.filter(pk=space.pk).update(enabled_modules=space.enabled_modules, enabled_features=space.enabled_features)
    calls = []

    def authority(user, *, makerspace_ids=None):
        calls.append(makerspace_ids)
        return user == actor and (makerspace_ids is None or space.pk in makerspace_ids)

    sources.register(sources.ResourceGrantSource(
        "booking_grants", authority,
        lambda user, **kwargs: [{"source": "booking_grant", "permissions": ["check_in"]}],
    ))
    assert_staff_authority(actor, SimpleNamespace(headers={}, selected_makerspace_id=space.pk))
    assert sources.payload_entries(actor)["booking_grants"][0]["source"] == "booking_grant"
    assert required(actor)
    assert any(ids is not None and space.pk in ids for ids in calls)


def test_tombstoned_event_ready_registers_no_source(monkeypatch, django_assert_num_queries):
    from django.apps import apps

    monkeypatch.setattr(sources, "_sources", {})
    monkeypatch.setattr("apps.separability.tombstones.app_is_tombstoned", lambda label: label == "events")
    monkeypatch.setattr("apps.separability.tombstones.register_separable_app", lambda label: None)
    with django_assert_num_queries(0):
        apps.get_app_config("events").ready()
    assert sources.registered_sources() == ()
