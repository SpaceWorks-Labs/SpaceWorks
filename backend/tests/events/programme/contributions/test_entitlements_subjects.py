from dataclasses import replace
from datetime import timedelta
from django.db import IntegrityError, transaction
from django.utils import timezone
import pytest
from rest_framework.exceptions import NotFound
from django.http import Http404
from apps.events.contributions.authority import active_entitlements
from apps.events.contributions.models import EventGrantEntitlement
from apps.events.contributions.subjects import require_owner, subject_for
from apps.events.models import EventStaffGrant, EventRegistration
from tests.events.programme.contributions.helpers import setup_shift


@pytest.mark.django_db
def test_role_only_subject_owner_does_not_need_a_registration(settings):
    _, _, _, _, users, roles, _ = setup_shift(settings)
    subject = subject_for(roles[0])
    assert require_owner(users[0].pk, subject) == subject
    assert not EventRegistration.objects.filter(member=users[0]).exists()
    with pytest.raises(NotFound):
        require_owner(users[1].pk, subject)
    with pytest.raises(Http404):
        require_owner(users[0].pk, replace(subject, subject_id=roles[1].pk))


@pytest.mark.django_db
def test_role_revocation_does_not_remove_manual_entitlement(settings):
    space, event, _, _, users, roles, adapter = setup_shift(settings)
    grant = EventStaffGrant.objects.create(event=event, makerspace=space, user=users[0],
        granted_by=adapter.issuer, permissions=["check_in", "mentor_queue"])
    manual = EventGrantEntitlement.objects.create(event=event, makerspace=space, grant=grant,
        source_kind="manual", permissions=["check_in"], created_by=adapter.issuer)
    roles[0].role, roles[0].posting = "mentor", None
    roles[0].save(update_fields=["role", "posting"])
    role = EventGrantEntitlement.objects.create(event=event, makerspace=space, grant=grant,
        source_kind="role", role_assignment=roles[0], permissions=["mentor_queue"], created_by=adapter.issuer)
    assert set(active_entitlements().values_list("pk", flat=True)) == {manual.pk, role.pk}
    roles[0].state = "revoked"
    roles[0].save(update_fields=["state"])
    assert set(active_entitlements().values_list("pk", flat=True)) == {manual.pk}
    assert grant.permissions == ["check_in", "mentor_queue"]  # stale display union grants nothing


@pytest.mark.django_db
def test_imported_role_and_expired_source_are_inert_and_shape_checked(settings):
    space, event, _, _, users, roles, adapter = setup_shift(settings)
    grant = EventStaffGrant.objects.create(event=event, makerspace=space, user=users[0], granted_by=adapter.issuer, permissions=["check_in"])
    roles[0].delegated_permissions = ["check_in"]
    roles[0].save(update_fields=["delegated_permissions"])
    row = EventGrantEntitlement.objects.create(event=event, makerspace=space, grant=grant,
        source_kind="role", role_assignment=roles[0], permissions=["check_in"], created_by=adapter.issuer, valid_until=timezone.now() - timedelta(seconds=1))
    assert not active_entitlements().filter(pk=row.pk).exists()
    row.valid_until = None
    row.save(update_fields=["valid_until"])
    roles[0].imported_inert = True
    roles[0].save(update_fields=["imported_inert"])
    assert not active_entitlements().filter(pk=row.pk).exists()
    with transaction.atomic(), pytest.raises(IntegrityError):
        EventGrantEntitlement.objects.create(event=event, makerspace=space, grant=grant, source_kind="shift")
