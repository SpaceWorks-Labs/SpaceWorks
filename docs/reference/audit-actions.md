---
title: Audit actions
group: Reference
order: 40
summary: How the audit log works, how entries are named and where the full catalogue of actions lives.
---

# Audit actions

Every state-changing operation in SpaceWorks writes an entry to the **audit log**. The log is append-only: it is protected in application code and by database triggers, so entries cannot be edited or deleted. Evidence photo records and QR scan records are likewise immutable.

## What an entry holds

| Part | Meaning |
| --- | --- |
| Action key | A stable dotted name such as `settings.changed`, `encryption.key_rotated` or `api_client.bookings_read` |
| Actor | Who did it (a person, or a client fingerprint for signed reads) |
| Space | The space the entry belongs to, if any |
| Subject | The record acted on |
| Metadata | Context, shown only where the metadata policy allows. Sensitive actions show the label and withhold the metadata |

## Where to read it

- **Space staff:** **Audit** in the staff console, narrowed to the area the person's role manages. Only the Space Manager and superadmin read the whole space.
- **Platform superadmin:** **Platform > Platform security > Audit log**.
- **Integrity checks on the server:** `python manage.py verify_audit_log` (row MACs, batch roots, signatures, chains and anchors) and `verify_audit_macs`.

## How keys are named

Keys are `<area>.<what happened>`. A few examples seen in this documentation: `settings.changed` (a setting edit, with the changed field and old and new values), `analytics.telemetry_updated` (field names only), `encryption.key_rotated`, `makerspace.public_api_key_rotated`, `charge.free_by_pricing`, `booking.price_quoted_at_approval`.

## The full catalogue

The complete list of action keys with their English labels and whether metadata is displayed is in the [audit action reference](../audit-action-reference.md). It is generated from the audit presentation catalogue, so it is the authority for what a key means. Related guidance: [logging and audit](../logging-and-audit.md).

## For integrators

- Signed integration reads append an audit row with an opaque client fingerprint and a row count, never the data read.
- Webhook consumers do not receive audit metadata.

## See also

- [Roles and permissions](permissions.md)
- [Invariants](../INVARIANTS.md) (audit and evidence rules)
