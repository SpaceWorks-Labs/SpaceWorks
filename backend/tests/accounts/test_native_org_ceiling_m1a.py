"""Every organization-authority reader honours the native membership-only ceiling."""

from types import SimpleNamespace

import pytest
from django.db.models import Q
from django.http import Http404

from apps.accounts import rbac
from apps.events import organizer_authority, series_authority
from apps.operations import views_org_reports
from tests.return_helpers import make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def native_actor():
    user = make_user("native-org-ceiling")
    user.native_device_session = True
    return user


def test_organizer_predicates_are_empty_for_native_sessions(native_actor):
    assert organizer_authority.organizer_event_q(native_actor) == Q(pk__in=[])
    assert series_authority.organizer_series_q(native_actor) == Q(pk__in=[])


def test_organizer_checks_refuse_native_sessions_without_local_authority(
    native_actor, monkeypatch,
):
    monkeypatch.setattr(rbac, "can", lambda *args, **kwargs: False)
    monkeypatch.setattr(rbac, "archived_makerspace_ids", lambda: set())
    target = SimpleNamespace(makerspace_id=1)

    assert organizer_authority.can_manage_event(native_actor, target) is False
    assert series_authority.can_manage_series(native_actor, target) is False


def test_local_authority_still_applies_to_native_sessions(native_actor, monkeypatch):
    monkeypatch.setattr(rbac, "can", lambda *args, **kwargs: True)
    target = SimpleNamespace(makerspace_id=1)

    assert organizer_authority.can_manage_event(native_actor, target) is True
    assert series_authority.can_manage_series(native_actor, target) is True


def test_organization_reports_are_unreachable_for_native_sessions(native_actor):
    with pytest.raises(Http404):
        views_org_reports._organization_for_report(native_actor, 1, SimpleNamespace(required_action="x"))


def test_native_marker_survives_an_actor_reload(monkeypatch):
    from apps.accounts.models import User
    from apps.accounts.native_session import _NATIVE_USER_ID, is_native_session, mark_native_session
    from apps.accounts.rbac_organizations import _organization_authority_memberships

    user = make_user("native-org-reload")
    token = _NATIVE_USER_ID.set(None)
    try:
        mark_native_session(user)
        reloaded = User.objects.get(pk=user.pk)
        assert not hasattr(reloaded, "native_device_session")
        assert is_native_session(reloaded)
        assert not _organization_authority_memberships(reloaded).exists()
        other = make_user("native-org-reload-other")
        assert not is_native_session(other)
    finally:
        _NATIVE_USER_ID.reset(token)
