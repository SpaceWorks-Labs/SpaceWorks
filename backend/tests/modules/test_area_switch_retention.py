"""Each optional module switches through the real service without losing core history.

One small persisted loan/stock/debt fixture per case; no seed world, storage calls,
URL crawling or migration rewinds. Retries must not duplicate capability audits.
"""
from decimal import Decimal

import pytest

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.hardware_requests.models import HardwareRequest
from apps.inventory.models import InventoryProduct
from apps.makerspaces.guards import require_module
from apps.makerspaces.models import Makerspace
from apps.makerspaces.module_install import install_module, uninstall_module
from apps.makerspaces.module_registry import MODULE_KEYS, core_module_keys, with_dependencies
from apps.payments.models import MakerspacePaymentSettings, Payment
from apps.payments.services import create_payment
from tests.modules.test_area_gate_contracts import _assert_off

OPTIONAL = sorted(MODULE_KEYS - core_module_keys())


@pytest.mark.django_db
@pytest.mark.parametrize("module_key", OPTIONAL)
def test_each_area_switch_retains_stock_loan_and_unclaimed_debt_and_audits_once(module_key):
    space = Makerspace.objects.create(
        name="Retained area history", slug="retained-area-history",
        enabled_modules=sorted(core_module_keys() | with_dependencies({module_key})),
        enabled_features=["loans.enabled"],
    )
    payment_settings = MakerspacePaymentSettings.objects.create(makerspace=space, default_currency="inr")
    borrower = User.objects.create_user(username="area-borrower", email="area-borrower@example.test")
    product = InventoryProduct.objects.create(
        makerspace=space, name="Retained stock", total_quantity=3, available_quantity=3,
    )
    loan = HardwareRequest.objects.create(
        makerspace=space, requester=borrower, requester_username=borrower.username, requested_for="Retained history",
    )
    debt = create_payment(
        makerspace=space, member=borrower, subject_type=Payment.SubjectType.LOAN_RENTAL, subject_id=loan.pk,
        amount=Decimal("12.34"), currency=payment_settings.default_currency, created_by=borrower,
    )
    assert debt.provider == Payment.Provider.UNCLAIMED
    original_modules = list(space.enabled_modules)
    before_audits = list(AuditLog.objects.filter(makerspace=space).values_list("pk", flat=True))

    def retained():
        return (
            InventoryProduct.objects.filter(pk=product.pk).values().get(),
            HardwareRequest.objects.filter(pk=loan.pk).values().get(),
            Payment.objects.filter(pk=debt.pk).values().get(),
        )

    def actions():
        return list(AuditLog.objects.filter(makerspace=space).exclude(pk__in=before_audits)
                    .order_by("pk").values_list("action", flat=True))

    before = retained()
    assert require_module(space, module_key) is space
    assert uninstall_module(space, module_key) == [module_key]
    _assert_off(require_module, space, module_key, "module")
    assert retained() == before
    assert actions() == ["makerspace.capabilities_changed"]

    assert uninstall_module(space, module_key) == []
    assert retained() == before
    assert actions() == ["makerspace.capabilities_changed"]

    assert install_module(space, module_key) == [module_key]
    assert require_module(space, module_key) is space
    assert space.enabled_modules == original_modules
    assert retained() == before
    assert actions() == ["makerspace.capabilities_changed", "makerspace.capabilities_changed"]

    assert install_module(space, module_key) == []
    assert retained() == before
    assert actions() == ["makerspace.capabilities_changed", "makerspace.capabilities_changed"]
