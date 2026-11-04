"""Repairs, issue reporting, technicians and per-parent maintenance (release 2 lane L16).

An internal package of the `maintenance` app (#97: no new top-level module). Every
surface sits behind its parent's own switch (#128 C-9): `machines.*`, `inventory.*`
and `bookings.*`. The single repair job model is L12's `WorkOrder`; an issue report is
linked to one when staff triage it with repairs switched on.
"""
