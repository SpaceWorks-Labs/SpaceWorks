---
title: Machine printing and connecting machines
group: How-to guides
order: 260
summary: What printing support ships in 0.12.0, how members request prints, how a printer or label printer is enrolled, and how vendor adapters plug in later.
---

# Machine printing and connecting machines

SpaceWorks 0.12.0 ships the **foundation** for printing and connected machines. Members can request prints, staff run them through the normal job workflow, and a signed device such as a printer or label printer can already pull work and report back. What it does not include is a finished adapter for any particular printer brand. Those are built separately against a stable contract, described at the end of this page.

## What you can use today

### Print requests and the job workflow

- Members and visitors send a **print request** from the space's public print page (`/m/<slug>/print`, or `/print` on a space's own domain). It is one of the machine job requests that every machine type shares.
- Staff review, quote, accept, run and finish the job in the machine-service console. Every step is recorded, and there is a visible state for needs-changes, rejected, failed and cancelled jobs. See [Machines](../modules/machines.md).
- Prices follow the [rates and fees](rate-cards-and-fees.md) settings where the space charges for machine work.

### Label printers for QR batches

An operator who may manage QR codes can send a QR print batch to an enrolled label printer in the same space. The printer collects the labels, prints them and reports success or a short, fixed failure code such as out of labels. Both the Devices module and QR print batches must be on. The protocol is in [Label commands](../device-label-commands.md).

### Enrolled printers

A printer device is an enrolled piece of hardware with its own signing key. It is not a user account and never appears in the audit log as a person. When the `machines.integrations` switch is on for the space (it is **off by default**), an enrolled printer bound to a machine type can:

1. pull the approved jobs for its machines;
2. report that a job started, finished or failed, through the same machine-service workflow staff use;
3. send a small status snapshot with each heartbeat (state, progress, temperatures, spool levels).

Staff enrol devices from **Devices** in the console. The token is shown once; the in-app help article "Connected devices" has the steps, and the protocol pages [Device protocol](../device-protocol.md) and [Printer delivery and measured reports](../device-printer-protocol.md) for the wire format.

SpaceWorks stays the system of record. A device can report what happened, but it cannot approve a job, issue equipment or skip the evidence and audit rules.

## What is not included yet

These are planned for a later release and are not in 0.12.0:

- an on-device printer agent program,
- vendor adapters (for example for Bambu, Prusa, OctoPrint or Klipper machines),
- automatic scheduling across a fleet of printers,
- live controls and a richer camera view,
- the staff-only shelf pointer for locating tools.

## Building adapters against the Device Adapter API

So that adapters can be written without changing SpaceWorks, 0.12.0 defines one vendor-neutral contract, the **Device Adapter API v1**. An adapter is an enrolled, signed bridge that may manage many machines or other targets. It declares what it can do (status, telemetry, job dispatch, controls, access decisions, usage logs and more) and SpaceWorks decides what is allowed, using the existing permissions, certifications and session rules.

Vendor adapters live in their own repositories. Start with [Device Adapter API v1](../device-adapters/README.md) and [Build an adapter](../device-adapters/build-an-adapter.md). The switch that turns it on for a space is `machines.integrations`, with child switches for access control, usage records and camera watching.

## Check it worked

1. Submit a print request from the public page and follow it through the machine-service console.
2. For a label printer, send a small QR batch and confirm its status changes to printed.
3. For an enrolled printer, open **Devices** and confirm it shows as **Online** with a recent last-seen time.

## See also

- [Machines](../modules/machines.md)
- [Machine integrations (server side)](../machine-integrations/INTEGRATION.md)
- [Turn an area or add-on on or off safely](turn-areas-on-off.md)
