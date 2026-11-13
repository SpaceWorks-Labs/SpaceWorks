---
title: The request lifecycle
group: Architecture
order: 30
summary: The request state machine and the evidence that issue and return each require.
---
# The request lifecycle

A hardware **request** is a proposal to borrow equipment. It moves through a fixed set of states, and only the workflow module may move it. Every move writes an audit entry.

## State machine

```mermaid
stateDiagram-v2
  [*] --> pending_approval: submit
  [*] --> draft: saved draft
  draft --> pending_approval: submit
  pending_approval --> accepted: staff accept (reserves stock)
  pending_approval --> rejected: staff reject
  pending_approval --> cancelled: withdrawn
  accepted --> cancelled: withdrawn
  accepted --> expired: pickup window passed
  accepted --> issued: handover with scan and photo
  issued --> partially_returned: some items back
  issued --> returned: all items back
  partially_returned --> returned: remaining items back
  issued --> closed_with_issue: all items resolved, some lost or damaged
  partially_returned --> closed_with_issue: all items resolved, some lost or damaged
  rejected --> [*]
  cancelled --> [*]
  expired --> [*]
  returned --> [*]
  closed_with_issue --> [*]
```

The main path starts at `pending_approval` (submission creates requests there; `draft` exists as a status), then `rejected` or `accepted`, then `issued`, then `partially_returned`, `returned` or `closed_with_issue`. `cancelled` and `expired` are terminal exits from pending or accepted: a borrower can withdraw their own request while the loan-withdrawals feature is on, staff can cancel, and an accepted request that is never collected can expire. Both release any reservation through the availability module.

A return closes the request only when every issued unit is accounted for as returned, damaged or missing. If any unit is damaged or missing (or an accountability record exists), the final status is `closed_with_issue` instead of `returned`; otherwise the request stays `partially_returned`.

`closed_with_issue` is how lost or damaged hardware ties back to the requester's **access status**: a restriction can follow, and charges can be raised.

## Hard rules

- Reviewed-request hardware **cannot be issued** without both a box QR scan and an issue photo.
- Public self-checkout and staff direct handouts **cannot be issued** without uploaded issue evidence and an eligible scanned or selected tool.
- Hardware **cannot be returned** without a return photo and a return remark.
- Issued quantity cannot exceed accepted quantity without authorised permission.
- Evidence rows and QR scan records are immutable; the audit log is append-only.

## Issue sequence

```mermaid
sequenceDiagram
  autonumber
  actor Staff as Handover staff
  participant UI as Console
  participant API as API
  participant Store as Object storage
  participant WF as Workflow module
  participant Av as Availability module
  participant Log as Audit log

  Staff->>UI: Scan box QR, check borrower, confirm items
  Staff->>UI: Take issue photo
  UI->>API: Ask for an upload slot
  API-->>UI: Presigned URL for a staging key
  UI->>Store: Upload photo
  UI->>API: Issue request with photo reference, scans and remark
  API->>API: Check role, makerspace and status
  API->>WF: issue
  WF->>Av: Move reserved quantity to issued
  WF->>Store: Promote photo to its final key
  WF->>Log: Record issue
  WF-->>API: Status issued
  API-->>UI: Receipt data
```

Every presigned upload lands on a **staging** key, and the final object key is never writable by the client. The workflow promotes the staged photo exactly once, so an accepted photo cannot be swapped through a still-valid upload link.

## Return sequence

```mermaid
sequenceDiagram
  autonumber
  actor Staff as Staff or borrower
  participant UI as Console
  participant API as API
  participant Store as Object storage
  participant WF as Workflow module
  participant Av as Availability module
  participant Log as Audit log

  Staff->>UI: Scan returned items, add remark
  Staff->>UI: Take return photo
  UI->>Store: Upload photo with presigned URL
  UI->>API: Return with photo, remark and lines
  API->>API: Refuse if photo or remark is missing
  API->>WF: return
  WF->>Av: Return, or mark lost or damaged
  WF->>Log: Record return
  WF-->>API: returned, partially_returned or closed_with_issue
  API-->>UI: Updated request
```

## Variants

- **Direct handout:** staff issue without a prior request. The same evidence rules apply.
- **Self-checkout and kiosks:** eligible QR tools can be issued and returned by an authenticated person with evidence, where the space has enabled it.
- **Renewals, waitlists and pickup windows** are optional loan features layered on this lifecycle.
- **Equipment kits and context:** a request can name an event or booking purpose; the purpose explains the request and grants nothing.

For the screens and steps staff follow, see the in-app help. For the rules in force, see [data and privacy](data-and-privacy.md) and [loan policy](../loan-policy.md).
