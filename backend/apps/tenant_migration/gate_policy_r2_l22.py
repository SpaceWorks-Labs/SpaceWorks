"""Release 2 L22: source-gate declaration for the shop sweep."""


def gate_tasks(internal):
    internal.update({
        "apps.shop.tasks.sweep_shop_task": (
            "Each lapse runs through the shop's order services, which lock the order and call "
            "assert_write_allowed for its space; a settlement only records money already received and a "
            "reminder writes nothing but its own counter."
        ),
    })
