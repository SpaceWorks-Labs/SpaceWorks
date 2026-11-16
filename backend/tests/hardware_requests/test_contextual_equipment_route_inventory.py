from django.urls import resolve
from rest_framework.permissions import IsAuthenticated

from apps.admin_api.permissions import IsActiveStaff
from apps.apiclients.scope_registry import lookup, validate_registry
from apps.hardware_requests.contextual_equipment_views import ContextualSelfView, ContextualStaffView


def test_contextual_routes_are_session_only_and_registry_complete():
    cases = [
        ("/api/v1/public/demo/requests/contextual", "hardware_requests:contextual-request-self", ContextualSelfView),
        ("/api/v1/admin/makerspace/1/equipment-requests/contextual", "hardware_requests:contextual-request-staff", ContextualStaffView),
    ]
    for path, name, view in cases:
        match = resolve(path)
        assert match.view_name == name
        assert match.func.cls is view
        assert lookup(name, "POST") is None
    assert IsAuthenticated in ContextualSelfView.permission_classes
    assert IsAuthenticated in ContextualStaffView.permission_classes
    assert IsActiveStaff in ContextualStaffView.permission_classes
    assert validate_registry() == ([], [])
