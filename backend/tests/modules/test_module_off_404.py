"""#183B gap 12: a module or capability that is off answers a typed 404, never a 400."""

import pytest
from django.urls import reverse
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.test import APIClient

from apps.makerspaces.guards import (
    SurfaceOff, feature_off, module_off, require_feature, require_feature_locked, require_module,
    require_module_for_servable, require_module_locked,
)
from apps.makerspaces.models import Makerspace
from tests.module_helpers import disable_module
from tests.return_helpers import authenticated_client, make_member, make_space

pytestmark = pytest.mark.django_db


def _space_without(slug, *modules):
    space = make_space(slug)
    for key in modules:
        disable_module(space, key)
    space.refresh_from_db()
    return space


def test_surface_off_is_a_404_with_the_typed_body():
    error = module_off("bookings")
    assert isinstance(error, NotFound) and isinstance(error, SurfaceOff)
    assert not isinstance(error, ValidationError)
    assert error.status_code == 404
    assert error.detail == {"detail": "bookings is turned off for this makerspace.",
                            "code": "module_disabled", "module": "bookings"}
    assert str(error) == "bookings is turned off for this makerspace."
    feature = feature_off("events.orders", "Ticket orders are off.")
    assert feature.detail == {"detail": "Ticket orders are off.", "code": "feature_disabled",
                              "feature": "events.orders"}


@pytest.mark.parametrize("guard", [require_module, require_module_locked])
def test_module_guards_raise_404(guard):
    space = _space_without("guard-module-off", "bookings")
    with pytest.raises(SurfaceOff) as error:
        guard(space, "bookings")
    assert error.value.status_code == 404
    assert error.value.detail["code"] == "module_disabled"
    assert error.value.detail["module"] == "bookings"


def test_servable_guard_raises_404():
    space = _space_without("guard-servable-off", "events")
    with pytest.raises(SurfaceOff) as error:
        require_module_for_servable(Makerspace.objects.get(pk=space.pk), "events")
    assert error.value.detail["module"] == "events"


@pytest.mark.parametrize("guard", [require_feature, require_feature_locked])
def test_feature_guards_raise_404(guard):
    space = make_space("guard-feature-off")
    space.enabled_features = [key for key in space.enabled_features if key != "staff.invitations"]
    space.save(update_fields=["enabled_features"])
    with pytest.raises(SurfaceOff) as error:
        guard(space, "staff.invitations")
    assert error.value.status_code == 404
    assert error.value.detail == {"detail": "staff.invitations is turned off for this makerspace.",
                                  "code": "feature_disabled", "feature": "staff.invitations"}


def test_guards_pass_when_on():
    space = make_space("guard-on")
    key = next(iter(space.enabled_modules))
    assert require_module(space, key) == space


def test_http_staff_route_answers_typed_404():
    space = _space_without("http-notifications-off", "notifications")
    manager = make_member("http-notifications-off-manager", space)
    response = authenticated_client(manager).get(f"/api/v1/notifications/makerspace/{space.pk}")
    assert response.status_code == 404
    assert response.data["code"] == "module_disabled"
    assert response.data["module"] == "notifications"


def test_http_public_route_answers_typed_404():
    space = _space_without("http-public-machines-off", "machines")
    space.public_inventory_enabled = True
    space.save(update_fields=["public_inventory_enabled"])
    response = APIClient().get(reverse("public-machines", args=[space.slug]))
    assert response.status_code == 404
    assert response.data == {"detail": "machines is turned off for this makerspace.",
                             "code": "module_disabled", "module": "machines"}


def test_staff_invitations_off_is_a_typed_404():
    space = make_space("http-invitations-off")
    space.enabled_features = [key for key in space.enabled_features if key != "staff.invitations"]
    space.save(update_fields=["enabled_features"])
    manager = make_member("http-invitations-off-manager", space)
    response = authenticated_client(manager).get(reverse("admin-staff-invitations", kwargs={"makerspace_id": space.pk}))
    assert response.status_code == 404
    assert response.data["code"] == "feature_disabled"
    assert response.data["feature"] == "staff.invitations"


def test_kiosk_replay_maps_surface_off_to_its_typed_failure():
    from apps.hardware_requests.replay_failures import CATALOG, mapped_failure

    assert CATALOG["module_disabled"][0] == CATALOG["feature_disabled"][0] == 404
    assert mapped_failure(module_off("guest_handover"), "direct_issue").code == "module_disabled"
    assert mapped_failure(feature_off("inventory.kiosk"), "direct_issue").code == "feature_disabled"


def test_admin_form_catch_sites_turn_surface_off_into_a_form_error():
    from django import forms
    import apps.operations.admin_forms as admin_forms

    space = _space_without("admin-stocktake-off", "stocktake")
    owner = next(value for value in vars(admin_forms).values()
                 if isinstance(value, type) and hasattr(value, "_require_visible_enabled"))
    with pytest.raises(forms.ValidationError) as error:
        owner._require_visible_enabled(object.__new__(owner), space, "stocktake")
    assert "turned off" in str(error.value)


def test_membership_feature_locked_still_answers_404_when_the_module_goes_off():
    from apps.makerspaces.membership_features import require_membership_feature_locked

    space = _space_without("membership-locked-off", "membership")
    with pytest.raises(NotFound):
        require_membership_feature_locked(space.pk, "self_service")
