"""The 3-day staff two-step grace (#128 C-1; #135 Q-A1-Q-A3), schema only (lane S0).

A person who gains a staff role without a second factor may use staff screens until
``ends_at``; afterwards staff screens refuse until they enrol (member features are never
blocked). One row per person, ever (Q-A2): the one-to-one key is the "one grace" rule,
and a re-grant after the grace is blocked at once. For staff who existed before release
2 the row is created at their first sign-in after the upgrade (``source=upgrade``, Q-A1).
S-A creates rows and enforces them.
"""

from django.conf import settings
from django.db import models

from .login_security_contract import GRACE_SOURCES


class StaffMfaGrace(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="staff_mfa_grace")
    started_at = models.DateTimeField()
    source = models.CharField(max_length=8, choices=[(value, value) for value in GRACE_SOURCES])
    ends_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(source__in=GRACE_SOURCES), name="staff_mfa_grace_source_known"),
            models.CheckConstraint(condition=models.Q(ends_at__gt=models.F("started_at")),
                                   name="staff_mfa_grace_ends_after_start"),
        ]

    def __str__(self):
        return f"staff_mfa_grace:{self.user_id}"
