"""Release 0.12.0 U1: the desk's borrower list includes live guest-pass holders, marked as such."""
import pytest
from django.urls import reverse

from apps.makerspaces import guest_pass_issue
from tests.account_split.p1_helpers import staff
from tests.makerspaces.test_guest_passes import _space as pass_space
from tests.makerspaces.test_membership_j1 import user
from tests.stage4.helpers import bearer_client

pytestmark = pytest.mark.django_db(transaction=True)


def test_live_pass_holders_are_listed_with_flag_and_end_and_expired_ones_are_not():
    space = pass_space("dl-guests")
    space.enabled_features = sorted(set(space.enabled_features) | {"inventory.self_checkout"})
    space.save(update_fields=["enabled_features"])
    manager, _ = staff(space, "dl-manager", role="space_manager")
    holder, stranger = user("dl-holder"), user("dl-stranger")
    row, _ = guest_pass_issue.issue_staff_pass(manager, space, holder)
    response = bearer_client(manager).get(reverse("hardware_requests:direct-loan-members", args=[space.pk]))
    assert response.status_code == 200, response.data
    rows = {item["user_id"]: item for item in response.data["results"]}
    assert holder.pk in rows and stranger.pk not in rows
    assert rows[holder.pk]["is_guest_pass"] is True
    assert rows[holder.pk]["membership_id"] is None
    assert rows[holder.pk]["pass_valid_until"]
    # A revoked pass is no longer a borrower.
    type(row).objects.filter(pk=row.pk).update(status="revoked")
    again = bearer_client(manager).get(reverse("hardware_requests:direct-loan-members", args=[space.pk]))
    assert holder.pk not in {item["user_id"] for item in again.data["results"]}
