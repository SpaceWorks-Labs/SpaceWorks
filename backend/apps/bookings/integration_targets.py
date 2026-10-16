"""Typed booking targets registered only by a live Bookings app."""

from apps.apiclients.read_contract import ReadTarget, register_read_target


def register_targets():
    register_read_target("integration-booking-resource-list", ReadTarget())
    register_read_target("integration-booking-list", ReadTarget())
    for name in ("integration-booking-resource-detail", "integration-booking-resource-reservations"):
        register_read_target(name, ReadTarget("bookings.BookableSpace"))
    register_read_target("integration-booking-detail", ReadTarget(
        "bookings.Booking", tenant_path="space__makerspace",
    ))
