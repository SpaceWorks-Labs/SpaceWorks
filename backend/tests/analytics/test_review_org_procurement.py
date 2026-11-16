"""Organization dispatch preserves printing purchase authority and type scope."""

import pytest

from apps.machines.models import MachineType
from apps.makerspaces.models import Makerspace
from apps.operations.org_reports import organization_report_data
from apps.operations.report_registry import report_definition
from apps.operations.report_scope import combined_report_scope
from apps.operations.reports import report_data
from apps.procurement.models import ToBuyItem
from tests.analytics.test_ab_inventory_m1f2 import enable
from tests.fixed_roles.helpers import assign_builtin_roles, staff_account
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


def test_organization_printing_purchases_match_tenant_type_scope():
    space = make_space("review-org-purchases")
    enable(space, "procurement", "machines", "printing")
    allowed = MachineType.objects.create(makerspace=space, name="Allowed", slug="allowed")
    denied = MachineType.objects.create(makerspace=space, name="Denied", slug="denied")
    actor = staff_account(space, "review-purchase-reader", "inventory_manager", "machine_manager",
                          machine_types=[allowed])
    for name, kind, machine_type in (("Hardware", "hardware", None), ("Allowed", "printing", allowed),
                                     ("Denied", "printing", denied)):
        ToBuyItem.objects.create(makerspace=space, name=name, kind=kind, machine_type=machine_type, quantity=1)
    definition = report_definition("procurement-performance")
    scope = combined_report_scope(Makerspace.objects.filter(pk=space.pk))
    tenant = report_data(definition.key, space.pk, actor=actor)["typed_rows"]
    org = organization_report_data(definition, scope, actor=actor, limit=100)
    assert {row["item_name"] for row in tenant} == {"Hardware", "Allowed"}
    assert {row["item_name"] for row in org["total"]["rows"]} == {"Hardware", "Allowed"}
    assert {row["item_name"] for row in org["breakdown"][0]["rows"]} == {"Hardware", "Allowed"}
    assign_builtin_roles(actor, space, "inventory_manager")
    org = organization_report_data(definition, scope, actor=actor, limit=100)
    assert {row["item_name"] for row in org["total"]["rows"]} == {"Hardware"}
