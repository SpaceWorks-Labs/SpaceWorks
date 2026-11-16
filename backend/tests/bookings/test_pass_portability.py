"""Real portable archive/materialization, with target-owned feature authority."""
from copy import deepcopy

import pytest
from rest_framework.exceptions import NotFound

from apps.bookings.models import BookableSpace
from apps.bookings.pass_templates import DEFAULT_PASS_TEMPLATE, normalize_pass_template
from apps.bookings.services_passes import require_passes
from apps.tenant_migration.materialization import materialize_tenant
from tests.data_export.portable_helpers import make_space, make_user
from tests.encryption.conftest import enabled_encryption
from tests.tenant_migration.materialization_helpers import portable_import_case

pytestmark = pytest.mark.django_db(transaction=True)


def test_bounded_layout_roundtrips_without_source_printing_authority_or_objects():
    with enabled_encryption():
        user = make_user("booking-pass-roundtrip")
        source = make_space("booking-pass-roundtrip")
        source.enabled_modules = sorted(set(source.enabled_modules) | {"bookings"})
        source.enabled_features = ["bookings.confirmations", "bookings.passes"]
        source.save(update_fields=["enabled_modules", "enabled_features"])
        resource = BookableSpace.objects.create(
            makerspace=source, name="Portable room", pass_template=deepcopy(DEFAULT_PASS_TEMPLATE),
        )
        with portable_import_case(source, user) as case:
            case.decide_walk_in(user)
            result = materialize_tenant(case.root, case.job, case.carried,
                                       target_identity={"slug": "booking-pass-target"})
        imported = BookableSpace.objects.select_related("makerspace").get(
            makerspace_id=result.target_makerspace_id,
        )
        assert result.imported["bookings.BookableSpace"] == 1
        assert imported.pk != resource.pk and imported.public_token != resource.public_token
        assert imported.pass_template == DEFAULT_PASS_TEMPLATE
        assert normalize_pass_template(imported.pass_template) == DEFAULT_PASS_TEMPLATE
        assert imported.makerspace_id != source.pk
        # Source configuration is not authority to activate target PDF disclosure.
        with pytest.raises(NotFound):
            require_passes(imported)
        resource.refresh_from_db()
        assert resource.pass_template == DEFAULT_PASS_TEMPLATE
