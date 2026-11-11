"""Per-person machine authority: whole machine types and/or individual machines."""

from django.utils.translation import gettext
from django.core.exceptions import ValidationError
from django.db import models


class MembershipMachineTypeScope(models.Model):
    membership = models.ForeignKey(
        "makerspaces.MakerspaceMembership", on_delete=models.CASCADE,
        related_name="machine_type_scopes",
    )
    machine_type = models.ForeignKey(
        "machines.MachineType", on_delete=models.CASCADE,
        related_name="membership_scopes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "machine_type"], name="membershipmachinetypescope_uniq",
            ),
        ]

    def clean(self):
        machine_type = self.machine_type
        if machine_type.makerspace_id is None:
            return
        if machine_type.makerspace_id != self.membership.makerspace_id:
            raise ValidationError({
                "machine_type": gettext("A membership can only be scoped to its own makerspace's machine types."),
            })


class MembershipMachineScope(models.Model):
    """One individual machine a staff membership reaches, unioned with its type links."""

    membership = models.ForeignKey(
        "makerspaces.MakerspaceMembership", on_delete=models.CASCADE,
        related_name="machine_scopes",
    )
    machine = models.ForeignKey(
        "machines.Machine", on_delete=models.CASCADE,
        related_name="membership_scopes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "machine"], name="membershipmachinescope_uniq",
            ),
        ]

    def clean(self):
        if self.machine.makerspace_id != self.membership.makerspace_id:
            raise ValidationError({
                "machine": gettext("A membership can only be scoped to its own makerspace's machines."),
            })
