---
title: Manage device adapters
group: How-to guides
order: 256
summary: Enrol a bridge, bind it to machines, shelves and doors, and use the staff console for status, controls, camera, audio, timelapses, offline access and kiosk checkout.
---

# Manage device adapters

A **device adapter** is a small program that sits next to your hardware, such as a printer, a door or a shelf pointer.
It connects to SpaceWorks over a signed connection. SpaceWorks provides the contract and this console; vendor adapters
are separate programs you or others write ([Build an adapter](../device-adapters/build-an-adapter.md)).

**Automation is not part of SpaceWorks.** SpaceWorks stores, shows and notifies. It does not decide to pause a print
after a failure is detected, or to power off a machine because it is hot. Any such rule runs in the adapter. The only
automatic actions the server takes are the per-machine safety settings below.

## What you need first

- The Machines module and the switch **Device adapters** (`machines.integrations`, off by default). Several features
  have their own child switch under it, all off by default: `.access`, `.usage_billing`, `.video`, `.recording`,
  `.audio`, `.talk`, `.audio_recording`, `.artifacts`, `.detections`, `.telemetry_history`, `.diagnostics`,
  `.offline_cache` and `.kiosk`.
- The *manage devices* action in the space, and, for a machine, authority over that machine.

Open **Machines**, then **Device adapters**.

## Enrol a bridge

1. Press **Enrol a bridge**, give it a name and save.
2. Copy the one-time token and give it to the adapter. It is shown once and cannot be read again.
3. When the adapter first connects it shows as **Online** and lists what it can do. Until then it reads *Waiting to connect*.

To rotate its key, issue a new enrolment from its page. **Revoke adapter** disconnects it at once.

## Bind it to something

On the adapter's **Bindings** tab, join the adapter to a machine, machine type, storage location, item, box, door or the
space, and pick which of its capabilities to use there. SpaceWorks refuses a capability the adapter did not declare or
one that cannot serve that kind of target.

## The tabs on an adapter

| Tab | What it does |
|---|---|
| Status and controls | Current state, progress and errors per binding; pause, resume, cancel, power on and off; per-machine safety settings (idle auto-off, area-clear confirmation, longest session). Controls are audited with your name. |
| Shelf pointer | Calibrate a pointer by aiming and nudging it, save the position for each storage location, item or box, then point at or light one. Saved positions are staff only and never reach a public page or a data export. |
| Watch | A short camera view, audited by viewer. With the audio switches on, staff can listen (listen-only by default) and use push-to-talk. The device must announce audio at the location; the console shows the same notice. |
| Timelapses and previews | Saved timelapses, job thumbnails and previews, failure snapshots. Timelapses and failure snapshots are kept 30 days, thumbnails and previews 90 (audio clips 3 days, log bundles 7) unless an operator changes them. |
| Detections | Failure, spaghetti, fire, smoke, person or other detections the adapter reported, with confidence and the evidence frame. Staff and the job owner are notified. |
| Charts | Temperatures and readings: raw for 24 hours, then one-minute (7 days) and fifteen-minute (90 days) summaries. |
| Diagnostics | Firmware, health and a log bundle you can request. |
| Offline and config | Offline access list status and remote configuration (below). |
| Kiosk | For adapters that run a self-checkout kiosk. |
| Webhook | Optional wake-up call so the adapter polls only when work is waiting. It carries no member or job details. |
| Logs | Recent commands, events, access decisions and usage. |

Credentials (NFC or PIN, per member) are on the **Credentials** tab of the screen, and per-type defaults on **Machine
types**. A credential's secret is never shown after saving. A new PIN is 6 to 12 digits and cannot be an easy one
(one repeated digit, a straight run such as 123456, or a well-known PIN); PINs set before 0.12.0 keep working. A
member card's QR code only says who someone is: at a reader or kiosk it works only together with that member's PIN,
and the public check link printed on a card never opens anything. Five wrong PINs lock that member's PIN for 15
minutes, and a reader that sees many wrong PINs pauses PIN entry for a while (the access log shows
`too_many_attempts`).

## Offline access for doors and machines

With `.offline_cache` on, a door adapter can keep a short list of who may enter while the network is down. The list
holds only hashed NFC credentials, never PINs, names or member ids, and only members who are allowed right now,
including machine access. It is signed with an Ed25519 key from the server and lasts 15 minutes by default. The
adapter must reject it when it is expired or the signature is wrong. Decisions made offline are sent back and appear in
the access log marked offline. Standing, presence and booking rules only apply online, so an adapter that needs them
must refuse while offline. Operators rotate the signing key with the settings in the
[environment reference](../environment-reference-delivery.md#device-adapters).

## Push configuration and time

On **Offline and config**, push a JSON settings object (up to 16 KiB; keys that look like secrets are refused, so keep
passwords and tokens on the adapter). The adapter fetches it, applies it and reports applied or rejected, and the
console shows the last versions. A signed **time** call lets an adapter with a drifting clock check the server's time.

## Kiosk checkout

With `.kiosk`, a kiosk adapter runs public self-checkout. The member signs in with their credential, scans the tool,
takes an evidence photo and the server issues or returns it through the normal self-checkout rules. A kiosk can never
skip a step. If the tool has a saved position on a bound shelf pointer, the shelf light is switched on automatically.

## Limits

A platform operator can limit the number of bridges, concurrent watch streams, snapshots and stored artifacts
(`adapter_bridges`, `adapter_watch_streams`, `adapter_snapshots`, `adapter_artifacts`). None are set by default.

## Check it worked

- The adapter shows **Online** and its bindings show a status that changes.
- A **Pause** from the console reaches the adapter and appears under Logs.
- Switching a child switch off hides its tab and the routes answer `404`.

## See also

[Device Adapter API](../device-adapters/README.md), [Media and data](../device-adapters/media-and-data.md),
[Machine printing](machine-printing.md) and [Machines](../modules/machines.md).
