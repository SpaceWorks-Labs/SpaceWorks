"""#184 money-mode matrix: the three modes every chargeable domain must support (local, untracked).

* FREE    -- `charges.<domain>` off (the master `charges.enabled` stays on, so a mixed space is
             the default shape): no charge row, the flow completes with no payment step.
* OFFLINE -- tracking on, no `payments` module: a PENDING charge, provider `unclaimed`.
* ONLINE  -- tracking on plus the rail (`payments` module, `payments.enabled`,
             `payments.<domain>`) with a test provider: `resolve_payment_source` is faked and the
             hosted-checkout call is a Mock, so a checkout is created for the charge and nothing
             leaves the process.

`set_mode` edits the stored capability lists directly (like the domain seam tests do), so a test
never depends on install-time pruning.
"""

from types import SimpleNamespace
from unittest.mock import Mock

FREE, OFFLINE, ONLINE = "free", "offline", "online"
MODES = (FREE, OFFLINE, ONLINE)
#: The rail key each domain's online mode needs, and any feature that key itself requires.
RAIL_FEATURES = {
    "loans": ("payments.loans",),
    "machines": ("payments.machines",),
    "bookings": ("payments.bookings",),
    "events": ("payments.events",),
    "membership": ("payments.membership",),
    "shop": ("payments.shop",),
    "donations": ("payments.donations", "finance.donations"),
}


def _store(space, modules=(), features=(), drop_modules=(), drop_features=()):
    space.enabled_modules = sorted((set(space.enabled_modules or []) | set(modules)) - set(drop_modules))
    space.enabled_features = sorted((set(space.enabled_features or []) | set(features)) - set(drop_features))
    space.save(update_fields=["enabled_modules", "enabled_features"])
    space.refresh_from_db()
    return space


def set_mode(space, domain, mode, *, extra_modules=()):
    """Put ONE domain of `space` into `mode`; every other domain keeps whatever it had."""
    rail = RAIL_FEATURES[domain]
    if mode == FREE:
        return _store(space, modules=extra_modules, features=("charges.enabled",),
                      drop_features=(f"charges.{domain}", *rail[:1]))
    if mode == OFFLINE:
        return _store(space, modules=extra_modules, features=("charges.enabled", f"charges.{domain}"),
                      drop_modules=("payments",), drop_features=rail[:1])
    return _store(space, modules=("payments", *extra_modules),
                  features=("charges.enabled", f"charges.{domain}", "payments.enabled", *rail))


def master_off(space):
    """The other road to FREE: the `charges.enabled` master switch off, every domain key kept."""
    return _store(space, drop_features=("charges.enabled",))


def fake_provider(monkeypatch):
    """A test gateway: the source resolves and the hosted checkout is recorded, never sent.

    Patched on both bindings a seam reaches it through: the checkout barrel the on-commit
    scheduler calls, and the `payments.services` name the donation page imports directly."""
    source = SimpleNamespace(vendor="stripe", provider="direct", connected_account_id="",
                             application_fee_bps=0)
    monkeypatch.setattr("apps.payments.availability.resolve_payment_source", lambda _space: source)
    checkout = Mock(return_value="https://checkout.test/session")
    monkeypatch.setattr("apps.payments.services_checkout.create_checkout_url", checkout)
    monkeypatch.setattr("apps.payments.services.create_checkout_url", checkout)
    return checkout


def checkout_ids(checkout):
    """The payment ids the fake provider was asked to open a checkout for."""
    return {call.args[0] for call in checkout.call_args_list}


def charges(space, subject_type):
    from apps.payments.models import Payment
    return list(Payment.objects.filter(makerspace=space, subject_type=subject_type).order_by("pk"))


def assert_mode_outcome(mode, rows, checkout=None):
    """FREE: no row. OFFLINE: one pending, unclaimed row, no checkout. ONLINE: one pending row
    with a checkout opened for it."""
    from apps.payments.models import Payment
    if mode == FREE:
        assert rows == []
        return None
    assert len(rows) == 1, rows
    payment = rows[0]
    assert payment.status == Payment.Status.PENDING
    if mode == OFFLINE:
        assert payment.provider == Payment.Provider.UNCLAIMED
        assert checkout is None or payment.pk not in checkout_ids(checkout)
    else:
        assert checkout is not None and payment.pk in checkout_ids(checkout)
    return payment
