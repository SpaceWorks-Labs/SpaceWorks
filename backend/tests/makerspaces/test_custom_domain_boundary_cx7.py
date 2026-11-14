"""The boolean quota is a hosted-domain permission, rather than a numeric max."""
import pytest
from django.urls import reverse

from apps.managed_hosting.models_hosting_type import SpaceHostingType
from tests.return_helpers import authenticated_client, make_member, make_space

pytestmark = pytest.mark.django_db


def test_hosted_domain_grant_allows_change_and_revocation_refuses_next_without_erasing_it(settings):
    settings.PLATFORM_DOMAIN_SUFFIX = ".space-works.tech"
    settings.INFRA_HOSTS = {"testserver"}
    space = make_space("cx7-hosted-domain")
    SpaceHostingType.objects.update_or_create(makerspace=space, defaults={"hosting_type": "hosted"})
    actor = make_member("cx7-domain-manager", space)
    caller = authenticated_client(actor)
    caller.defaults["HTTP_HOST"] = "testserver"
    url = reverse("admin-makerspace", kwargs={"pk": space.pk})
    space.resource_limit_overrides = {"custom_domain": True}
    space.save(update_fields=["resource_limit_overrides"])
    allowed = caller.patch(url, {"frontend_domain": "first.example.org"}, format="json")
    assert allowed.status_code == 200
    space.resource_limit_overrides = {"custom_domain": False}
    space.save(update_fields=["resource_limit_overrides"])
    refused = caller.patch(url, {"frontend_domain": "second.example.org"}, format="json")
    assert refused.status_code == 400
    assert refused.json() == {"frontend_domain": [
        "Custom domains aren't available on free managed hosting; self-host to use your own domain."]}
    space.refresh_from_db()
    assert space.frontend_domain == "first.example.org"
