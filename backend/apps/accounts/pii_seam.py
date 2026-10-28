"""The one place Lane D's superadmin-parity code asks about PII (#111 Q12, #114, #115).

Lane C owns PII masking and the audited PII-access window
(`apps.accounts.pii_presentation`, `apps.accounts.pii_access`). Lane D opens every
Space-Manager route to the superadmin and asks one question through this module: may this
viewer read this makerspace's PII unmasked? Since both lanes merged it re-exports Lane C's
real window, so there is exactly one answer.
"""

from apps.accounts.pii_presentation import MASK, pii_visible, require_pii_access  # noqa: F401
