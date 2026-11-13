"""Real domain API contract tests; not run until the isolated slot is admitted."""
from datetime import timedelta
import pytest
from django.utils import timezone
from apps.events.models import Event
from apps.events.models_loan_context import EventLoanContext
from tests.test_request_workflow import make_space, make_member, make_product, make_hardware_request, authenticated_client

pytestmark = pytest.mark.django_db


def setup_context():
    space = make_space("event-context-proof")
    space.enabled_modules = list(set(space.enabled_modules or []) | {"events", "request_workflow"})
    space.enabled_features = list(set(space.enabled_features or []) | {"loans.enabled"})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    actor = make_member("event-context-manager", space)
    product = make_product(space)
    req = make_hardware_request(space, product)
    start = timezone.now() + timedelta(days=3)
    event = Event.objects.create(makerspace=space, title="Context event", starts_at=start, ends_at=start + timedelta(hours=1))
    url = f"/api/v1/admin/makerspace/{space.pk}/requests/{req.pk}/event-context"
    return space, req, product, event, authenticated_client(actor), url


def test_context_cas_stale_unlink_and_no_inventory_mutation():
    space, req, product, event, api, url = setup_context()
    before = (product.available_quantity, product.reserved_quantity, req.status)
    empty = api.get(url)
    assert empty.status_code == 200 and empty.data["active"] is False
    body = {"event_id": event.pk, "participant_registration_id": None,
        "expected_generation": empty.data["generation"], "expected_revision": 0}
    linked = api.put(url, body, format="json")
    assert linked.status_code == 200 and linked.data["revision"] == 1
    assert EventLoanContext.objects.get(request=req).event_id == event.pk
    stale = api.put(url, body, format="json")
    assert stale.status_code == 409
    removed = api.delete(url + f"?intended_event_id={event.pk}",
        {"expected_generation": empty.data["generation"], "expected_revision": 1}, format="json")
    assert removed.status_code == 200 and removed.data["revision"] == 2 and not removed.data["active"]
    product.refresh_from_db()
    req.refresh_from_db()
    assert (product.available_quantity, product.reserved_quantity, req.status) == before


def test_foreign_event_cannot_be_linked_or_discovered():
    space, req, product, event, api, url = setup_context()
    other = make_space("event-context-other")
    start = timezone.now() + timedelta(days=3)
    foreign = Event.objects.create(makerspace=other, title="Private event", starts_at=start, ends_at=start + timedelta(hours=1))
    empty = api.get(url)
    result = api.put(url, {"event_id": foreign.pk, "participant_registration_id": None,
        "expected_generation": empty.data["generation"], "expected_revision": 0}, format="json")
    assert result.status_code == 404
    assert not EventLoanContext.objects.filter(request=req).exists()


def test_hidden_old_event_cannot_be_overwritten_or_used_as_revision_oracle(monkeypatch):
    from apps.events import event_authority
    space, req, product, old_event, api, url = setup_context()
    start = timezone.now() + timedelta(days=4)
    new_event = Event.objects.create(makerspace=space, title="New", starts_at=start, ends_at=start + timedelta(hours=1))
    empty = api.get(url)
    body = {"event_id": old_event.pk, "participant_registration_id": None,
        "expected_generation": empty.data["generation"], "expected_revision": 0}
    assert api.put(url, body, format="json").status_code == 200
    original = event_authority.can
    monkeypatch.setattr(event_authority, "can", lambda actor, event, permission, **kw:
        False if event.pk == old_event.pk else original(actor, event, permission, **kw))
    assert api.get(url).status_code == 404
    attempt = dict(body, event_id=new_event.pk, expected_revision=0)
    assert api.put(url, attempt, format="json").status_code == 404
    assert EventLoanContext.objects.get(request=req).event_id == old_event.pk


@pytest.mark.django_db(transaction=True)
def test_event_lock_contention_rolls_back_without_context_write():
    from concurrent.futures import ThreadPoolExecutor
    from django.db import connection, transaction, close_old_connections
    space, req, product, event, api, url = setup_context()
    empty = api.get(url)
    body = {"event_id": event.pk, "participant_registration_id": None,
        "expected_generation": empty.data["generation"], "expected_revision": 0}
    def attempt():
        close_old_connections()
        with connection.cursor() as cursor:
            cursor.execute("SET lock_timeout = '2s'")
        try:
            return api.put(url, body, format="json").status_code
        finally:
            close_old_connections()
    with transaction.atomic():
        Event.objects.select_for_update().get(pk=event.pk)
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(attempt).result(timeout=5) == 409
        assert not EventLoanContext.objects.filter(request=req).exists()
    assert not EventLoanContext.objects.filter(request=req).exists()


def test_purge_epoch_prevents_delayed_delete_after_recreated_revision_one():
    from apps.accounts.models import User
    from apps.makerspaces.module_purge import purge_module
    space, req, product, old_event, api, url = setup_context()
    root = User.objects.create_superuser(username="context-epoch-root")
    empty = api.get(url)
    old_body = {"event_id": old_event.pk, "participant_registration_id": None,
        "expected_generation": empty.data["generation"], "expected_revision": 0}
    assert api.put(url, old_body, format="json").status_code == 200
    space.refresh_from_db()
    space.enabled_modules = [name for name in space.enabled_modules if name != "events"]
    space.save(update_fields=["enabled_modules"])
    purge_module(space, "events", root)
    space.refresh_from_db()
    space.enabled_modules = list(set(space.enabled_modules) | {"events"})
    space.save(update_fields=["enabled_modules"])
    start = timezone.now() + timedelta(days=5)
    new_event = Event.objects.create(makerspace=space, title="New", starts_at=start, ends_at=start + timedelta(hours=1))
    new_empty = api.get(url)
    assert new_empty.data["generation"] != empty.data["generation"]
    new_body = {"event_id": new_event.pk, "participant_registration_id": None,
        "expected_generation": new_empty.data["generation"], "expected_revision": 0}
    assert api.put(url, new_body, format="json").status_code == 200
    stale = api.delete(url + f"?intended_event_id={new_event.pk}",
        {"expected_generation": empty.data["generation"], "expected_revision": 1}, format="json")
    assert stale.status_code == 409
    assert EventLoanContext.objects.get(request=req).event_id == new_event.pk


def test_event_edit_details_without_registration_permission_is_uniformly_read_only(monkeypatch):
    from apps.events import event_authority, event_permissions
    space, req, product, event, api, url = setup_context()
    original = event_authority.can
    monkeypatch.setattr(event_authority, "can", lambda actor, event, permission, **kw:
        False if permission == event_permissions.MANAGE_REGISTRATIONS else original(actor, event, permission, **kw))
    empty = api.get(url + f"?intended_event_id={event.pk}")
    assert empty.status_code == 200 and empty.data["can_write"] is False
    result = api.put(url, {"event_id": event.pk, "participant_registration_id": None,
        "expected_generation": empty.data["generation"], "expected_revision": empty.data["revision"]}, format="json")
    assert result.status_code == 404
    assert not EventLoanContext.objects.filter(request=req).exists()


def test_verified_merged_shell_registration_attaches_to_survivor_borrower():
    from apps.events.models import EventRegistration
    from tests.data_export.test_merged_fields import _merge
    from tests.test_request_workflow import make_user
    space, req, product, event, api, url = setup_context()
    shell = make_user("context-api-merged-shell")
    registration = EventRegistration.objects.create(event=event, member=shell,
        name="Alias", email="alias-api@example.test", phone="", status="registered")
    _merge(shell, req.requester)
    empty = api.get(url)
    result = api.put(url, {"event_id": event.pk, "participant_registration_id": registration.pk,
        "expected_generation": empty.data["generation"], "expected_revision": 0}, format="json")
    assert result.status_code == 200
    assert EventLoanContext.objects.get(request=req).participant_registration_id == registration.pk
