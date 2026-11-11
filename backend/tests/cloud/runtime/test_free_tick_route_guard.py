"""The free tick must pass the staff-route guard, or every free management command fails.

The accounts URL walk sees the bare leaf name `tick` under the `free_tick` namespace;
the exemption therefore matches the exact mounted path, never any route named `tick`.
"""
from apps.accounts.route_exemptions import route_exemption


def test_the_mounted_free_tick_is_provider_only():
    assert route_exemption("api/v1/internal/free/tick", "tick") == "provider-only"


def test_another_route_named_tick_is_not_exempted():
    assert route_exemption("api/v1/admin/tick", "tick") is None
    assert route_exemption("api/v1/internal/free/tick", "other") is None
