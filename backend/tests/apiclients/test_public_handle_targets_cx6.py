"""Handle resolution keeps organization publication and decision 549 personal-card targets."""
from types import SimpleNamespace

import pytest
from django.test import RequestFactory
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.apiclients.scope_registry_public_pages import is_global_target, resolve_handle_target
from apps.makerspaces.models import Makerspace
from apps.makerspaces.models_account_profile import AccountProfile
from apps.makerspaces.models_profiles import PublicHandle
from apps.makerspaces.public_page_contract import empty_document
from apps.organizations.models import Organization
from apps.organizations.models_public_pages import OrganizationPublicPage, OrganizationPublicPageRevision
from tests.accounts.account_factories import make_membership
from tests.accounts.ua1_helpers import person

pytestmark = pytest.mark.django_db


@pytest.fixture
def public_request(settings):
    settings.INFRA_HOSTS = ["testserver", "localhost"]
    settings.PUBLIC_APP_BASE_URL = "http://testserver"
    return RequestFactory().get("/", HTTP_HOST="testserver")


def test_global_organization_target_is_tagged_and_its_tenantless_identity_is_explicit(public_request):
    owner = Organization.objects.create(name="Global", slug="cx6-global-org", public_profile_enabled=True,
                                         review_status="approved")
    page = OrganizationPublicPage.objects.create(organization=owner)
    revision = OrganizationPublicPageRevision.objects.create(page=page, document=empty_document("organization"))
    page.published_revision = revision
    page.save(update_fields=["published_revision"])
    PublicHandle.objects.create(organization=owner, handle="cx6.global.org", changed_at=timezone.now())
    match = SimpleNamespace(kwargs={"handle": "cx6.global.org"})
    target, resolved = resolve_handle_target(public_request, match)
    assert (target.kind, target.pk, resolved, is_global_target(target)) == ("global", None, True, True)
    page.published_revision = None
    page.save(update_fields=["published_revision"])
    with pytest.raises(NotFound) as error:
        resolve_handle_target(public_request, match)
    assert (error.value.status_code, error.value.get_codes()) == (404, "not_found")


@pytest.mark.parametrize("with_membership", [True, False])
def test_live_person_target_uses_its_home_space_or_is_explicitly_global(public_request, with_membership):
    user = person("cx6-public-handle")
    space = Makerspace.objects.create(name="Handle home", slug="cx6-handle-home")
    if with_membership:
        make_membership(user, space)
    AccountProfile.objects.update_or_create(user=user, defaults={"public_visible": True, "public_consented_at": timezone.now()})
    PublicHandle.objects.create(user=user, handle="cx6.person", changed_at=timezone.now())
    match = SimpleNamespace(kwargs={"handle": "cx6.person"})
    target, resolved = resolve_handle_target(public_request, match)
    # Decision 549: every live personal handle resolves, including accounts without a home space.
    expected = ("tenant", space.pk, True, False) if with_membership else ("global", None, True, True)
    assert (target.kind, target.pk, resolved, is_global_target(target)) == expected
    AccountProfile.objects.filter(user=user).update(public_visible=False)
    # Decision 549: a retained historical opt-out cannot hide the always-on public card.
    target, resolved = resolve_handle_target(public_request, match)
    assert (target.kind, target.pk, resolved, is_global_target(target)) == expected
    match = SimpleNamespace(kwargs={"handle": "cx6.missing"})
    with pytest.raises(NotFound) as error:
        resolve_handle_target(public_request, match)
    assert (error.value.status_code, error.value.get_codes()) == (404, "not_found")
