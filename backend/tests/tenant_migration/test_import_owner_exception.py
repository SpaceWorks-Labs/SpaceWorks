"""Tenant import is an exception to the owner-at-creation rule."""

import pytest

from apps.makerspaces.models import Makerspace
from apps.organizations.models import Organization, OrganizationMakerspace
from apps.tenant_migration.materialization import materialize_tenant
from tests.data_export.portable_helpers import make_space, make_user
from tests.encryption.conftest import enabled_encryption
from tests.tenant_migration.materialization_helpers import portable_import_case


pytestmark = pytest.mark.django_db(transaction=True)


def test_import_creates_target_without_an_owner_even_when_the_source_had_one():
    with enabled_encryption():
        user = make_user("owner-import")
        source = make_space("owner-import")
        owner = Organization.objects.create(name="Source Owner", slug="source-owner")
        OrganizationMakerspace.objects.create(
            organization=owner, makerspace=source,
            relationship=OrganizationMakerspace.Relationship.OWNER,
        )
        organizations_before = Organization.objects.count()

        with portable_import_case(source, user) as case:
            case.decide_walk_in(user)
            result = materialize_tenant(
                case.root, case.job, case.carried,
                target_identity={"slug": "owner-import-target"},
            )

    target = Makerspace.objects.get(pk=result.target_makerspace_id)
    assert target.slug == "owner-import-target"
    assert not OrganizationMakerspace.objects.filter(makerspace=target).exists()
    assert Organization.objects.count() == organizations_before
    assert OrganizationMakerspace.objects.get(makerspace=source).organization == owner
