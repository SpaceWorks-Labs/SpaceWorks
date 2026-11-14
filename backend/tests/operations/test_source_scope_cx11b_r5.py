"""Aggregate report SQL must honor the same Inventory master gate as tenant reads."""
import pytest

from apps.makerspaces.loan_visibility import INVENTORY_ONLY_MODULES
from apps.makerspaces.models import Makerspace
from apps.operations.report_sources import source_enabled, source_q
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.modules.test_switch_matrix_objects_rest_support import switch

pytestmark = [pytest.mark.django_db, pytest.mark.area_reports, pytest.mark.area_inventory]


@pytest.mark.parametrize("source", sorted(INVENTORY_ONLY_MODULES))
def test_inventory_source_sql_matches_runtime_gate_before_disable_and_after_restore(source):
    space = live_space("r5-source-scope", MODULE_KEYS)
    before = list(space.enabled_modules)
    def admitted():
        runtime = source_enabled(space, source)
        stored = Makerspace.objects.filter(pk=space.pk).filter(source_q(source)).exists()
        assert stored is runtime
        return runtime
    assert admitted() is True
    original = switch(space, "loans.enabled")
    assert admitted() is False
    # Other domains keep their independent scope; no source row is removed.
    assert source_enabled(space, "machines") is True
    assert Makerspace.objects.filter(pk=space.pk).filter(source_q("machines")).exists() is True
    assert space.enabled_modules == before
    switch(space, "loans.enabled", original=original)
    assert admitted() is True
    original = switch(space, source)
    assert admitted() is False
    switch(space, source, original=original)
    assert admitted() is True



def test_inventory_master_filter_keeps_any_other_live_source_and_honors_relation_prefix():
    from apps.inventory.models import InventoryProduct
    from tests.return_helpers import make_product

    space = live_space("r5-prefixed-scope", MODULE_KEYS)
    product = make_product(space)
    rows = InventoryProduct.objects.filter(pk=product.pk)
    retained = rows.values().get()
    def inventory_visible():
        return rows.filter(source_q("public_inventory", prefix="makerspace__")).exists()
    assert inventory_visible() is True
    original = switch(space, "loans.enabled")
    assert inventory_visible() is False
    assert rows.filter(source_q("public_inventory|machines", prefix="makerspace__")).exists() is True
    assert rows.values().get() == retained
    switch(space, "loans.enabled", original=original)
    assert inventory_visible() is True
    assert rows.values().get() == retained
