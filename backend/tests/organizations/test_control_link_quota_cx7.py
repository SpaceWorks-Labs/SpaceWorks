"""Organization links use the service quota and keep its code in the admin form."""
import pytest
from django.urls import reverse

from apps.organizations.models import Organization, OrganizationMakerspace
from tests.accounts.reauth_helpers import force_recent_control_login
from tests.r2_superadmin_local.helpers import superadmin
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


def test_control_link_max_and_next_keep_exact_service_error(client):
    space = make_space("cx7-link-quota")
    space.resource_limit_overrides = {"organizations_linked": 1}
    space.save(update_fields=["resource_limit_overrides"])
    actor = superadmin("cx7-link-root")
    force_recent_control_login(client, actor)
    organizations = [Organization.objects.create(name=name, slug=name, review_status="approved") for name in ("cx7-a", "cx7-b")]
    url = reverse("admin:organizations_organizationmakerspace_add")
    maximum = client.post(url, {"organization": organizations[0].pk, "makerspace": space.pk, "relationship": "affiliate"})
    assert maximum.status_code == 302
    refused = client.post(url, {"organization": organizations[1].pk, "makerspace": space.pk, "relationship": "affiliate"})
    assert refused.status_code == 200
    errors = refused.context["adminform"].form.non_field_errors().as_data()
    assert [error.code for error in errors] == ["organizations_linked_quota_reached"]
    assert OrganizationMakerspace.objects.filter(makerspace=space).count() == 1
