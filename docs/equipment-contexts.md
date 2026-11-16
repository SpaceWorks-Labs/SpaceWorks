# Equipment loan context

An equipment loan can be ordinary, linked to an event, linked to one specific booking, or linked to both. A context explains the purpose of a loan. It does not create a booking, register a participant, change the borrower, approve a request or issue equipment.

## Add or change context

Open the existing request detail in the staff console. For a direct handout, select **Context** on its loan row. Enabled contextual modules expose separate **Event context** and **Booking context** panels.

1. For an existing link, choose **Edit or remove** before changing it.
2. Choose **Choose a different resource**. For bookings, choose a space and then its exact booking; selecting a room alone is insufficient.
3. For a new link, use **Prepare link** after the server checks the chosen target.
4. For an event, explicitly choose a participant or **No participant**. A selected registration must belong to the accountable borrower or their verified merged-account identity. Contact-text matches do not establish identity.
5. Use **Save context**. To remove an existing link, choose **Edit or remove**, then **Remove context**.

The available choices follow your delegated access. Seeing a resource in a picker does not guarantee that the loan is editable or that you may link that particular combination. The server rechecks both records at the time of the change.

Changing event context requires the loan's existing source action and registration-management authority for both the old and new event. Booking changes require the loan's source action and reservation-management authority for the relevant resource. A link grants no new access. Read access to an event does not itself disclose its participant; the participant field is omitted without registration-management permission.

If another operator changes the link, a request is interrupted, or the outcome is uncertain, the panel asks you to **Review latest state**. Review the current values before making another change. It does not automatically replay the mutation. Switching account, makerspace or access scope clears the private editor state.

## Equipment accountability stays in the loan workflow

Approval, reservation, issue, evidence, QR scans, partial returns, damage/loss resolution and charges remain in the existing inventory and request workflows. Adding or removing context changes none of those facts. Direct handouts and public self-checkout retain their canonical request record; a context does not create a second loan or count equipment twice.

Cancelling an event or booking does not silently return hardware or settle debt. Complete those obligations through the existing authorized return, loss and settlement flows. A contextual link is not a confirmed venue reservation.

## Module switches and retained data

| Configuration | Effect |
| --- | --- |
| Events and Bookings enabled | Independently authorized loans may have neither, either or both contexts. |
| Events disabled | No event editor or new event link. Ordinary and authorized booking workflows retain their own gates. |
| Bookings disabled | No booking editor or new booking link. Ordinary and authorized event workflows retain their own gates. |
| Both disabled | Ordinary Inventory loans continue under their existing capability and permissions. |
| Reports or Analytics disabled | Their respective report entry points are hidden; operational loan work has its own gates. |
| A contextual module re-enabled | Access is rechecked against current roles, capabilities and record eligibility. No automatic issue, booking or replay occurs. |

Disabling a module retains its records under the existing lifecycle policy. Purging removes its owned context rows and invalidates old edit versions, while retaining core loan accountability subject to the normal obligation and tenant-retention guards. Restore and supported tenant import invalidate previous context edit versions before admission. An operator must reload the current record after those operations.

See [module lifecycle](MODULES-LIFECYCLE.md) before uninstall or purge. Supported deployment tombstones remove runtime surfaces while retaining required historical models and registrations.

## Reports and privacy

The loan-purpose summary counts each canonical issued loan once, including a loan linked to both domains. Event and booking equipment reports require their exact authorized subject. Hidden context is not revealed by reporting an "ordinary" versus "linked" split; a reader without complete dimension authority receives a uniform **Context not shown** cohort.

These reports count issued/history records, not pending equipment requests. Context selection and reports do not compute or change availability. See [equipment reports](equipment-reports.md) for the reporting boundary and export behavior.
