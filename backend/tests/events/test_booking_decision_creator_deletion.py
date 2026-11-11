"""Real PostgreSQL guard and creator-deletion behavior; not run in source preparation."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from apps.accounts.booking_decision_deletion import clear_booking_decision_creators
from apps.accounts.models import User
from apps.events.models import Event
from apps.events.models_booking_decision import EventBookingDecision
from apps.makerspaces.models import Makerspace

pytestmark = pytest.mark.django_db(transaction=True)


def decision():
    maker = Makerspace.objects.create(name="Creator deletion", slug="creator-delete-decision")
    actor = User.objects.create_user(username="creator-delete-person", password="not-a-real-secret")
    start = timezone.now() + timedelta(days=2)
    event = Event.objects.create(makerspace=maker, title="Workshop", starts_at=start,
                                 ends_at=start + timedelta(hours=1))
    row = EventBookingDecision.objects.create(makerspace=maker, event=event, creator=actor,
                                               operation_id=uuid4(), intent={})
    return actor, row


def test_authorized_creator_clear_and_user_delete_preserve_the_decision():
    actor, row = decision()
    with transaction.atomic():
        User.objects.select_for_update().get(pk=actor.pk)
        clear_booking_decision_creators([actor.pk])
        actor.delete()
    row.refresh_from_db()
    assert row.creator_id is None and row.billing_owner == "booking" and row.revision == 1
    assert row.intent == {"version": 1, "unavailable": True}


def test_wrong_creator_and_additional_mutation_refuse_and_rollback():
    actor, row = decision()
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            for key, value in (("row", row.pk), ("maker", row.makerspace_id), ("user", actor.pk)):
                cursor.execute("SELECT set_config(%s, %s, true)", ["app.booking_decision_creator_" + key, str(value)])
        EventBookingDecision.objects.filter(pk=row.pk).update(creator=None, intent={"altered": True})
    row.refresh_from_db()
    assert row.creator_id == actor.pk and row.revision == 1 and row.intent == {}
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            for key, value in (("row", row.pk), ("maker", row.makerspace_id), ("user", actor.pk + 1)):
                cursor.execute("SELECT set_config(%s, %s, true)", ["app.booking_decision_creator_" + key, str(value)])
        EventBookingDecision.objects.filter(pk=row.pk).update(creator=None, intent={"version": 1, "unavailable": True})
    row.refresh_from_db()
    assert row.creator_id == actor.pk


def test_admin_single_and_bulk_delete_use_the_atomic_creator_clear():
    from django.contrib import admin
    from django.test import RequestFactory
    from apps.accounts.admin import UserAdmin

    user_admin = UserAdmin(User, admin.site)
    request = RequestFactory().post("/control/accounts/user/")
    one, one_row = decision("admin-one")
    user_admin.delete_model(request, one)
    one_row.refresh_from_db()
    assert one_row.creator_id is None and not User.objects.filter(pk=one.pk).exists()
    first, first_row = decision("admin-two")
    second, second_row = decision("admin-three")
    user_admin.delete_queryset(request, User.objects.filter(pk__in=[first.pk, second.pk]))
    first_row.refresh_from_db()
    second_row.refresh_from_db()
    assert first_row.creator_id is None and second_row.creator_id is None
    assert not User.objects.filter(pk__in=[first.pk, second.pk]).exists()


def test_protected_audit_rolls_back_creator_clear_before_hard_delete():
    from django.contrib import admin
    from django.db.models import ProtectedError
    from django.test import RequestFactory
    from apps.accounts.admin import UserAdmin
    from apps.audit.services import record

    actor, row = decision("admin-protected")
    record(actor, "test.creator_reference", makerspace=row.makerspace, target=row.event)
    with pytest.raises(ProtectedError):
        UserAdmin(User, admin.site).delete_model(RequestFactory().post("/control/accounts/user/"), actor)
    row.refresh_from_db()
    assert row.creator_id == actor.pk and User.objects.filter(pk=actor.pk).exists()