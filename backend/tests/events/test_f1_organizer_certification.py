"""Final audit 0.12.0 (M11), decisions 221(b) and 226(b): every organizer (the creator plus
co-organizers holding manage_events) must hold the machine type's booking certification. A
non-member organizer is refused `certification_required`, never skipped; staff override with a
reason; `replace_machine_link` passes the reason through."""
import pytest
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import User
from apps.events.machine_link_access import organizer_users, require_organizer_certification
from apps.machines.models import CertificationType
from tests.events.test_event_workshop_machines import world

pytestmark = pytest.mark.django_db


def _gated_world(slug):
    maker, staff, member, event, kinds, times = world(slug, certifications=True)
    CertificationType.objects.create(makerspace=maker, machine_type=kinds[0], name="Laser induction",
                                     is_required_for_booking=True)
    outsider = User.objects.create_user(username=f"{slug}-outsider", access_status=User.AccessStatus.ACTIVE)
    event.created_by = outsider
    event.save(update_fields=["created_by"])
    return event, times[0], staff, outsider


def test_the_certification_set_includes_the_creator():
    event, _space, _staff, outsider = _gated_world("f1-org-set")
    assert [user.pk for user in organizer_users(event)] == [outsider.pk]


def test_a_non_member_organizer_is_refused_not_skipped():
    event, space, staff, _outsider = _gated_world("f1-org-refused")
    with pytest.raises(PermissionDenied) as caught:
        require_organizer_certification(event, space, staff)
    assert caught.value.detail["code"] == "certification_required"


def test_staff_with_type_authority_may_override_with_a_reason():
    event, space, staff, _outsider = _gated_world("f1-org-override")
    require_organizer_certification(event, space, staff, "Instructor supervises the whole session")


def test_individual_co_organizers_with_edit_details_are_in_the_set_but_helpers_are_not():
    from tests.events.manual_grant_fixture import create_manual_grant
    event, _space, _staff, outsider = _gated_world("f1-org-grants")
    co = User.objects.create_user(username="f1-co-organizer", access_status=User.AccessStatus.ACTIVE)
    helper = User.objects.create_user(username="f1-helper", access_status=User.AccessStatus.ACTIVE)
    create_manual_grant(event=event, makerspace=event.makerspace, user=co, permissions=["edit_details"])
    create_manual_grant(event=event, makerspace=event.makerspace, user=helper, permissions=["check_in"])
    assert {user.pk for user in organizer_users(event)} == {outsider.pk, co.pk}
