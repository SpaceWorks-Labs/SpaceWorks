from ..capability import Capability
from ..schema import CODE, num, obj, text

CAPABILITY = Capability(
    "sensor.report", "Sensor readings and alarms.", targets=("machine", "door", "space", "storage_location"),
    events={"sensor.reading": obj({"sensor": text(60, minLength=1), "value": num(-10 ** 9, 10 ** 9), "unit": text(16)},
                                  ["sensor", "value"]),
            "sensor.alarm": obj({"sensor": text(60, minLength=1), "code": CODE}, ["sensor", "code"])},
)
