"""Stable import surface for audited, locked makerspace role services."""
from apps.audit import services as audit  # noqa: F401 - existing test patch surface
from apps.makerspaces.role_authority import (  # noqa: F401
    MEMBER_ROLE_SLUG,
    _locked_actor_actions,
    _locked_organization_actions,
    _superadmin,
)
from apps.makerspaces.role_assignments import (  # noqa: F401
    assign_role, can_assign_role, can_assign_roles, set_membership_roles,
)
