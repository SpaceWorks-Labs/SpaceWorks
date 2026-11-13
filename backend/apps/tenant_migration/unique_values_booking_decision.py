"""Portable uniqueness policy for the retained venue decision."""
from .unique_value_generators import _refuses_collision
from .unique_values_policy import PRESERVE, _policy


@_refuses_collision
def refuse_generation_collision(row, target, source_value):
    raise RuntimeError("A retained booking-decision generation cannot be regenerated.")


# `event` and `booking` are one-to-one, but both are tenant ownership roots of the dataset
# (`event__makerspace`, `booking__space__makerspace`), so their uniqueness is tenant-scoped
# and the projection guard does not treat them as deployment-global risks.
RULES = {
    ("events.EventBookingDecision", "field:generation"): _policy(PRESERVE, "Decision generation is retained CAS identity.", field="generation", generator=refuse_generation_collision),
}
