---
title: Connected devices
summary: Enrol devices that report to Space Works, and keep an eye on whether they're online.
order: 60
keywords: devices, enrol, enroll, integration, online, offline, token, connected machine
modules: devices
actions: manage_devices
---
## Enrol a device

1. Open **Devices** and press **Add device**, then **Create device**.
2. Under **One-time device enrollment**, copy the enrolment identifier and token into the device. Press **Copy enrollment**, then confirm you've copied it.

![Screenshot: the one-time device enrollment panel](screenshot:mm-devices)

The token is shown once. If you lose it before the device enrols, open the device and press **Issue
enrollment**: the old token stops working and a new one is shown once.

## Watch them

The list shows how many devices are **Online**, **Offline** and **Revoked**, with each one's **Last seen** time.

Machines that report their own sessions and jobs are switched on by the platform administrator for your space. Printing support in this release is the foundation: enrolled printers and label printers can collect work and report back, and vendor adapters are built separately against the Device Adapter API, so a printer brand is supported only once an adapter for it exists.

> **Who can do this:** the Space Manager, or anyone given the devices action. Machine Managers don't hold it by default.
