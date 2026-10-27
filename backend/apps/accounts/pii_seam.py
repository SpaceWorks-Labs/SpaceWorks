"""MERGE SEAM between P1b Lane D and Lane C (owner decisions #111 Q12 and #114).

Lane C owns PII masking and the audited PII-access window
(`apps.accounts.pii_presentation`, `apps.accounts.pii_access`). Lane D opens every
Space-Manager route to the superadmin (#115) and needs one question answered: may this
viewer read this makerspace's PII unmasked? Lane C is not in Lane D's base, so this file
answers it fail-closed: a platform superadmin never sees tenant PII here, because no window
can be opened on this branch. Everyone else is decided by RBAC alone.

At merge, replace everything below the docstring with:

    from apps.accounts.pii_presentation import MASK, pii_visible  # noqa: F401
"""

from apps.accounts.platform_tenant_surface import is_platform_superadmin

MASK = "••••••"


def pii_visible(viewer, makerspace_id, *, subject=None):
    """May this viewer read unmasked PII belonging to one makerspace?"""
    return not is_platform_superadmin(viewer)
