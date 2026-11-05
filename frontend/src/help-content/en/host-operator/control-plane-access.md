---
title: Reach /control/ safely
summary: Open the control plane through the bundled proxy with an address allow-list, or through an SSH tunnel.
order: 60
keywords: control plane, control, proxy, ssh tunnel, allow list, cidr, port forward, admin access
---
`/control/` is off the public address by default. Choose one way in.

## Through the proxy

1. Run the installer menu's option 6, or the control-plane settings script, and turn web access on.
2. Restrict it to your own networks with the allowed address ranges.
3. Open `https://<your-domain>/control/`.

## Through an SSH tunnel

1. Turn on the tunnel port (automatic HTTPS installs, recent Docker Engine).
2. From your computer, forward a local port to it with `ssh -N -L`.
3. Open `https://localhost:<port>/control/`. Use `localhost`, not `127.0.0.1`.

![Screenshot: the installer's control-plane access option](screenshot:op-control-access)

Changes are applied under a lock, and the previous `.env` is kept beside it. Behind your own proxy, restrict the path in that proxy instead. Turn on two-step sign-in for the superadmin before exposing `/control/`, or prefer the tunnel.

> **Who can do this:** the host operator.
