"""Final audit m21: the Postgres guard on makerspaces_guestpass (migration 0139)."""
import pytest
from django.db import connection, transaction

from apps.makerspaces import guest_pass_issue, guest_pass_lifecycle
from apps.makerspaces.models import GuestPass
from tests.makerspaces.test_guest_passes import _space
from tests.makerspaces.test_membership_j1 import manager, user

pytestmark = pytest.mark.django_db(transaction=True)
_DB_ERRORS = Exception


def _pass(slug):
    makerspace = _space(slug)
    guest = user(f"{slug}-guest")
    row, _ = guest_pass_issue.issue_staff_pass(manager(makerspace, f"{slug}-staff"), makerspace, guest)
    return makerspace, row


def test_delete_is_refused_outside_the_purge_scope_and_allowed_inside_it():
    _makerspace, row = _pass("gp-trg-del")
    with pytest.raises(_DB_ERRORS), transaction.atomic():
        GuestPass.objects.filter(pk=row.pk)._raw_delete(using="default")
    assert GuestPass.objects.filter(pk=row.pk).exists()
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL app.allow_immutable_delete = 'on'")
        GuestPass.objects.filter(pk=row.pk)._raw_delete(using="default")
    assert not GuestPass.objects.filter(pk=row.pk).exists()


def test_frozen_columns_cannot_change_but_status_waiver_and_revoke_transitions_can():
    _makerspace, row = _pass("gp-trg-frozen")
    with pytest.raises(_DB_ERRORS), transaction.atomic():
        GuestPass.objects.filter(pk=row.pk).update(entitlements={"borrow": "full_with_deposit"})
    with pytest.raises(_DB_ERRORS), transaction.atomic():
        GuestPass.objects.filter(pk=row.pk).update(kind=GuestPass.Kind.DAY)
    revoked = guest_pass_lifecycle.revoke_pass(manager(row.makerspace, "gp-trg-revoker"), row, "left early")
    assert revoked.status == GuestPass.Status.REVOKED


def test_a_closed_pass_never_changes_status_again():
    _makerspace, row = _pass("gp-trg-closed")
    GuestPass.objects.filter(pk=row.pk).update(status=GuestPass.Status.EXPIRED)
    with pytest.raises(_DB_ERRORS), transaction.atomic():
        GuestPass.objects.filter(pk=row.pk).update(status=GuestPass.Status.CONVERTED)
    assert GuestPass.objects.get(pk=row.pk).status == GuestPass.Status.EXPIRED
