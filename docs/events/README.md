# Events programme guide

**Integration checkpoint: `f1ef7736`, 2026-10-18. Keep programme features OFF.**
The domain code, additive migrations, route mounts and generated API are present in this
checkout. This is not an accepted release: real providers, lifecycle closure, PostgreSQL
tests and browser/print acceptance remain incomplete. These guides describe the authored
workflows; a mounted route or a component is not proof of an operable journey.
See [integration status](integration-status.md) before enabling or advertising anything.

| Reader | Guide |
| --- | --- |
| Organizer / co-organizer | [Configure, review, publish and close](organizer.md) |
| Participant / team leader | [Apply, RSVP, form a team and submit](participant.md) |
| Mentor | [Assignments, help queue and rounds](mentor.md) |
| Volunteer | [Applications, shifts and verified hours](volunteer.md) |
| Judge / sponsor representative | [Frozen projects, conflicts and results](judge.md) |
| Deployment operator | [Migrations, keys, storage, scanning and video probe](operations.md) |
| File uploader / operator | [Formats, media limits and retention](media.md) |
| Reviewer / acceptance owner | [AO1–AO18 and AO23 traceability](acceptance.md) |

Hackathons are features of the existing [Events module](../MODULES.md#events), with no
separate hackathons module. `events.hackathons`, `events.mentoring`, `events.mentor_rounds`,
`events.volunteering` and `events.project_gallery` default off. An event additionally has
`HackathonConfig.enabled=False` by default. Volunteering can serve ordinary events;
mentoring requires hackathons and rounds additionally require mentoring.

Current setup caveat: choosing the Events area selects all child features in
`setup_areas.features_for()`. The integration owner must keep these unaccepted programme
features out of that blanket selection; registry defaults alone are insufficient.

Admission uses the event's existing audience: member, authenticated account or invitation.
An account audience need not have a host membership. Volunteer, mentor, judge, sponsor and
co-organizer assignments use member accounts and event-scoped authority, not staff accounts
or a new makerspace role. Application, contribution, attendance and judging are separate
records; none of their labels alone grants another workflow's authority.

The [source map](../SOURCE-MAP-EVENTS-PROGRAMME.md) identifies each writer and the
retention/runtime split. [Invariants](../INVARIANTS.md#events-programme-integration-contract-2026-10-18)
define privacy, capacity, lock and history rules. The [notice inventory](../notification-coverage.md#events-programme-checkpoint-2026-10-18)
distinguishes installed sources from pending delivery adapters.

For API integrations, use the deployment's `/docs/` or `/schema/` and the checked-in
`frontend/openapi-schema.json`; the generated client is `frontend/src/generated/api.ts`.
The frozen route fixtures are design contracts; the mounted route inventory supersedes
the original lane proposals. Current mounts include C2's completion routes.

All programme UI must use Space Works light/dark tokens, Gilroy 400–700, one Unbounded
accent per layout, lucide controls and the existing layouts inside AppShell. Original
[artwork inventory](../events-programme-artwork-inventory.md) exists; runtime seed copying,
consumer mounting, accessibility, physical QR and authoritative PDF acceptance remain
separate requirements. No alternate brand or placeholder artwork establishes completion.
