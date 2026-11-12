from ..capability import Capability
from ..schema import UUID, num, obj

# Maps onto the existing label commands (device-label-commands.md): the adapter leases the
# command, downloads the ZIP and reports through the existing label routes.
CAPABILITY = Capability(
    "label.print", "Print QR label batches; maps onto the existing label commands.", targets=("space", "machine_type"),
    commands={"print": obj({"label_command_id": UUID, "batch_id": num(1, 2 ** 62, "integer"),
                            "item_count": num(1, 100000, "integer")}, ["label_command_id"])},
)
