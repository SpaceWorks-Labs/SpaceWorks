from django.db import models


class FixedRoleScope(models.Model):
    """L25 seam (#163B): a database login pinned to one makerspace by role, not by settings.

    A per-space read-only analytics login is made a member of the ``spaceworks_rls_fixed``
    group role and given one row here. The restrictive ``spaceworks_rls_fixed`` policy then
    limits it to that makerspace whatever ``app.*`` settings its own SQL sends. Rows are
    written only by the operator-side provisioning that owns those logins (lane L25).
    """

    role_name = models.CharField(max_length=63, unique=True)
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.role_name} -> {self.makerspace_id}"
