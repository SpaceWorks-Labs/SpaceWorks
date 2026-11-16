from ..capability import Capability
from ..schema import CODE, EPOCH, PERCENT, UUID, num, obj, text

CONSUMPTION = obj({"machine_consumable_id": num(1, 2 ** 31, "integer"), "quantity": num(0.01, 10 ** 9)},
                  ["machine_consumable_id", "quantity"])
# Decision 341: measured use by the machine type's profile key (e.g. "filament" in g, "sheet" in sheets).
# Additive: `consumptions` by per-machine id keeps working unchanged.
PROFILE_CONSUMPTION = obj({
    "key": {"type": "string", "format": "code", "maxLength": 50},
    "quantity": num(0.001, 10 ** 9),
    "attributes": obj({name: text(100, minLength=1) for name in ("material", "colour", "thickness", "size")}),
}, ["key", "quantity"])
CAPABILITY = Capability(
    "job.dispatch", "Lease, acknowledge, progress and report a machine-service job.", targets=("machine",),
    events={"job.needs_attention": obj({"job_id": UUID, "reason": CODE}, ["job_id", "reason"])},
    routes=("POST jobs/lease", "POST jobs/{id}/ack", "POST jobs/{id}/progress", "POST jobs/{id}/report"),
    commands={"cancel_job": obj({"job_id": UUID}, ["job_id"])},
)
PROGRESS = obj({"progress_percent": PERCENT, "eta_seconds": num(0, 31536000, "integer"), "observed_at": EPOCH})
REPORT = obj({"operation_id": UUID, "outcome": {"type": "string", "enum": ["completed", "failed"]},
              "actual_minutes": num(0, 10 ** 6, "integer"),
              "consumptions": {"type": "array", "items": CONSUMPTION, "maxItems": 32},
              "profile_consumptions": {"type": "array", "items": PROFILE_CONSUMPTION, "maxItems": 32},
              "actual_grams": num(0, 10 ** 9), "actual_quantity": num(0, 10 ** 9),
              "error_code": CODE, "failure_reason": text(500), "percent_complete": PERCENT},
             ["operation_id", "outcome", "actual_minutes", "consumptions"])
ACK = obj({"lease_token": text(128, minLength=32), "external_job_id": text(120, minLength=1)},
          ["lease_token", "external_job_id"])
