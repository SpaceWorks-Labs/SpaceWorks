"""Resource permissions never imply tenant, finance or machine authority."""

from apps.makerspaces.resource_grants_models import validate_permission_set

EDIT_DETAILS = "edit_details"
MANAGE_RESERVATIONS = "manage_reservations"
CHECK_IN = "check_in"
PUBLISH_PAGE = "publish_page"
PERMISSIONS = (EDIT_DETAILS, MANAGE_RESERVATIONS, CHECK_IN, PUBLISH_PAGE)
VIEW = "view"
DESCRIPTIVE_FIELDS = frozenset({"name", "kind", "description", "capacity", "location", "custom_form"})


def validate_permissions(value):
    validate_permission_set(value, PERMISSIONS)
