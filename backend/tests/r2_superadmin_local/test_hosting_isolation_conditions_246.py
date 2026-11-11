"""Decision 246: hosting type, plans and limits are per space; one space's setting never reaches another."""
import pytest

from apps.makerspaces import limits
from apps.managed_hosting import hosting_type, plans
from apps.managed_hosting.models import HostingPlan, SpaceHostingType, SpacePlanAssignment

from .helpers import space, superadmin

pytestmark = pytest.mark.django_db


@pytest.fixture
def hosting(settings, own_by_default):
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.MANAGED_PLANS_ENABLED = True
    return settings


def test_hosting_a_space_leaves_every_other_space_own_and_unlimited(hosting):
    hosted, bystander, root = space(), space(), superadmin()
    hosting_type.set_type(root, hosted, hosting_type.HOSTED)
    plan = HostingPlan.objects.create(key="tiny-246", name="Tiny", limits={"members": 1})
    plans.assign(root, hosted.pk, plan.pk, trial_days=0)
    assert hosting_type.is_hosted(hosted) and limits.resource_limit(hosted, "members") == 1
    assert not hosting_type.is_hosted(bystander)
    assert limits.resource_limit(bystander, "members") is None
    limits.check_quota(bystander, "members", adding=1000)
    assert SpaceHostingType.objects.filter(makerspace=bystander).count() == 0
    assert SpacePlanAssignment.objects.filter(makerspace=bystander).count() == 0


def test_a_per_space_override_on_one_hosted_space_does_not_change_a_sibling(hosting):
    first, second, root = space(), space(), superadmin()
    for lab in (first, second):
        hosting_type.set_type(root, lab, hosting_type.HOSTED)
    first.resource_limit_overrides = {"members": 3}
    first.save(update_fields=["resource_limit_overrides"])
    assert limits.resource_limit(first, "members") == 3
    assert limits.resource_limit(second, "members") is None


def test_setting_the_same_hosting_type_twice_keeps_one_row(hosting):
    lab, root = space(), superadmin()
    hosting_type.set_type(root, lab, hosting_type.HOSTED)
    hosting_type.set_type(root, lab, hosting_type.HOSTED)
    assert SpaceHostingType.objects.filter(makerspace=lab).count() == 1
