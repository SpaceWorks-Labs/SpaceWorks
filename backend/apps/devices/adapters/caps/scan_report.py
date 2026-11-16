from ..capability import Capability
from ..schema import obj, text

CAPABILITY = Capability(
    "scan.report", "A scanner reports a code it read.", targets=("storage_location", "item", "box", "space", "door"),
    events={"scan.reported": obj({"code_type": {"type": "string", "enum": ["qr", "barcode", "rfid", "nfc"]},
                                  "value": text(256, minLength=1)}, ["code_type", "value"])},
)
