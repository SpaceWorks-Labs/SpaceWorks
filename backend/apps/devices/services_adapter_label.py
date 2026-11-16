"""label.print: a label command for an adapter rides the EXISTING label path (lease, content ZIP, result).

The device command and its ``LabelPrintCommand`` are created by ``services_label_commands`` exactly as for a label
printer (batch freeze, idempotency, audit). All an adapter needs on top is to hear about it: this queues the
capability's ``print`` command (carrying the label command id) on the adapter's own queue, so it can then fetch
the content and report the result through the ordinary label routes.
"""
from datetime import timedelta

from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.devices.models import AdapterBinding, AdapterCommand

TTL_SECONDS = 3600


def notify_adapter(actor, label, device):
    binding = next((row for row in AdapterBinding.objects.filter(device=device, enabled=True)
                    if "label.print" in row.capabilities), None)
    if binding is None:  # an adapter command always rides a binding; refusing rolls the label command back too
        raise ValidationError(gettext("This adapter has no enabled binding that prints labels."))
    row = AdapterCommand.objects.create(
        makerspace_id=device.makerspace_id, device=device, binding=binding, device_key_version=device.key_version,
        capability="label.print", command="print", created_by=actor,
        params={"label_command_id": str(label.pk), "batch_id": label.batch_id_snapshot,
                "item_count": label.item_count_snapshot},
        expires_at=timezone.now() + timedelta(seconds=TTL_SECONDS))
    audit.record(actor, "devices.adapter_label_queued", makerspace=device.makerspace, target=device, meta={
        "device_id": str(device.pk), "label_command_id": str(label.pk), "command_id": str(row.pk)})
    from apps.devices.services_adapter_webhook import wake
    wake(device, "command.queued", binding_id=binding.pk, capability="label.print", command="print")
    return row
