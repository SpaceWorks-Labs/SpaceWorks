"""U-C: a tenant purge deletes that tenant's rows on BOTH tracks and retires nobody."""

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.makerspaces.lifecycle_purge import purge
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from tests.accounts.account_factories import grant_staff_role, make_membership

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("managed", [False, True])
def test_purge_deletes_both_tracks_and_keeps_people(settings, managed):
    settings.MANAGED_POSTGRES = managed
    gone = Makerspace.objects.create(name="Purge tracks", slug=f"purge-tracks-{int(managed)}")
    kept = Makerspace.objects.create(name="Kept tracks", slug=f"kept-tracks-{int(managed)}")
    person = User.objects.create_user(f"purge-tracks-person-{int(managed)}", email=f"p{int(managed)}@example.test")
    make_membership(person, gone)
    grant_staff_role(person, gone, role_slug="space_manager")
    grant_staff_role(person, kept, role_slug="inventory_manager")
    root = User.objects.create_superuser(f"purge-root-{int(managed)}", f"r{int(managed)}@example.test", "pw-strong-123")
    Makerspace.objects.filter(pk=gone.pk).update(archived_at=timezone.now())
    gone.refresh_from_db()
    purge(gone, root)
    person.refresh_from_db()
    assert not Makerspace.objects.filter(pk=gone.pk).exists()
    assert not MakerspaceMembership.all_tracks.filter(makerspace_id=gone.pk).exists()
    # Nobody is retired: the person keeps their account and their other space's staff row.
    assert person.account_kind == "member" and person.is_active and person.retired_at is None
    assert MakerspaceMembership.staff_tracks.filter(user=person, makerspace=kept, status="active").exists()


def test_staff_rows_are_still_never_deleted_outside_the_purge():
    from django.db import IntegrityError, transaction

    space = Makerspace.objects.create(name="No delete", slug="no-delete-tracks")
    person = User.objects.create_user("no-delete-person")
    row = grant_staff_role(person, space, role_slug="inventory_manager")
    with pytest.raises(IntegrityError), transaction.atomic():
        MakerspaceMembership.all_tracks.filter(pk=row.pk).delete()
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
