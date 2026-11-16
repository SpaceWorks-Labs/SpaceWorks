"""The identity seam: who is a person, platform or shell, and who holds staff roles."""

import pytest
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts import staff_identity as identity
from apps.accounts.models import User

from .ua1_helpers import community, merged_shell, person, platform, space, staff_row

pytestmark = pytest.mark.django_db


def test_kinds_and_predicates():
    alice, root = person("alice"), platform()
    shell = merged_shell(person("old"), alice)
    assert identity.is_person(alice) and not identity.is_person(root) and not identity.is_person(shell)
    assert identity.is_platform(root) and identity.is_shell(shell)
    assert set(User.objects.filter(identity.person_q()).values_list("pk", flat=True)) >= {alice.pk}
    assert not User.objects.filter(identity.person_q(), pk__in=[root.pk, shell.pk]).exists()


def test_staff_role_reads_the_staff_track_only():
    a, b = space("id-a"), space("id-b")
    member, staff = person("member"), person("staff")
    community(member, a)
    staff_row(staff, b, "event_manager")
    assert identity.staff_makerspace_ids(member) == set()
    assert identity.staff_makerspace_ids(staff) == {b.pk}
    assert identity.has_staff_role(staff) and identity.has_staff_role(staff, b.pk)
    assert not identity.has_staff_role(staff, a.pk) and not identity.has_staff_role(member)
    assert not identity.has_staff_role(staff, "not-a-number")
    staff_row(person("revoked"), a, "event_manager", status="revoked")
    assert not identity.has_staff_role(User.objects.get(username="revoked"))
    assert set(User.objects.filter(identity.staff_holder_q(b.pk)).values_list("username", flat=True)) == {"staff"}


def test_platform_and_shell_never_hold_staff_authority():
    root = platform()
    assert identity.staff_makerspace_ids(root) == set()
    assert not identity.has_elevated_authority(root)


def test_elevated_authority_covers_staff_roles():
    makerspace, staff, member = space("elevated"), person("elevated"), person("plain")
    staff_row(staff, makerspace, "booking_manager")
    community(member, makerspace)
    assert identity.has_elevated_authority(staff)
    assert not identity.has_elevated_authority(member)


def test_actor_ids_follow_merged_shells_transitively():
    survivor = person("survivor")
    middle = person("middle")
    first = merged_shell(person("first"), middle)
    merged_shell(middle, survivor)
    assert identity.actor_ids_for(survivor) == {survivor.pk, middle.pk, first.pk}
    assert identity.actor_ids_for(person("alone")) == {User.objects.get(username="alone").pk}


def test_require_staff_mfa_refuses_provider_proof_for_elevated_people(settings):
    makerspace, staff, member = space("mfa"), person("mfa-staff"), person("mfa-member")
    staff_row(staff, makerspace, "event_manager")
    from datetime import timedelta
    from django.utils import timezone
    from rest_framework.exceptions import PermissionDenied
    from apps.accounts.mfa_grace import open_grace
    from apps.accounts.models_mfa_grace import StaffMfaGrace
    identity.require_staff_mfa(staff, {"mfa_source": "provider"})  # inside the 3-day grace
    open_grace(staff)
    StaffMfaGrace.objects.filter(user=staff).update(started_at=timezone.now() - timedelta(days=4),
                                                    ends_at=timezone.now() - timedelta(days=1))
    with pytest.raises(PermissionDenied) as caught:  # 403: the member session itself keeps working
        identity.require_staff_mfa(staff, {"mfa_source": "provider"})
    assert caught.value.detail["code"] == "mfa_enrollment_required"
    identity.require_staff_mfa(member, {"mfa_source": "provider"})
