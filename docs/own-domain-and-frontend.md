# Run your space on your own domain or frontend

A Space Manager can give their space its own address, such as `tools.alphamakerspace.org`, and can
leave the space out of the platform's shared listings. This page explains both settings, what the
platform needs from you, and what stays the same. Both settings are under **Settings › Branding &
public site** in the staff console.

## Hide this space from the platform

**Hide this space from the platform** is a switch that the Space Manager (or the platform
superadmin) can turn on or off at any time. It works on its own and does not need a custom domain.

While the switch is on, the space is left out of:

- the platform directory of spaces and **Discover**;
- cross-space search;
- the event listings on the platform's shared address;
- the sitemap of the shared address and the organization catalogue.

Nothing else changes:

- The space keeps its own address (`/m/<slug>`, or its verified domain), so members and anyone with
  the link reach every page as before.
- The platform superadmin still sees the space in every console and report. The superadmin platform
  overview leaves hidden spaces out of its totals by default; the superadmin can add them back with
  **Include archived, not-serving and directory-hidden spaces**.

Every change of the switch is written to the audit log as `settings.changed`
(`public_site` / `hidden_from_central_directory`), with who made it and from which value to which.

## Your own domain or frontend

You can point a domain you control at the space in two ways:

1. **At this deployment.** The domain serves the space's public site and staff console from the same
   servers as everything else.
2. **At your own SpaceWorks frontend.** You host the frontend yourself (see
   [single-tenant-frontend.md](single-tenant-frontend.md)) and it talks to this deployment's API.

### Steps

1. Enter the domain under **Your own domain or frontend** and save it. The status then reads
   **Waiting for DNS proof**.
2. Point the domain at its server with a CNAME record or A/AAAA records.
3. Serve the domain over **HTTPS** with a valid certificate. Forward both the public site and
   `/admin` to the frontend.
4. Add the **DNS TXT record** that the settings page shows. It looks like
   `_spaceworks-verify.<your domain>  TXT  <token>`. The record proves you control the domain.
5. Press **Verify domain**. DNS changes can take a while to spread, so you can run the check again
   at any time. When the record is found, the status turns to **Verified**.

### What "Verified" changes

Until the domain is verified, it gets **no trust at all**. Specifically:

- no sign-in and no staff console are served from it;
- browsers on the domain cannot call the API, because CORS does not list it;
- the platform does not accept it as a host and issues no certificate for it.

Visitors keep using the space's usual address until then. Once the domain is verified, the
deployment trusts it for these four things:

- the space's public pages;
- staff sign-in (exactly `https://<domain>`, never any other port or scheme);
- the space's own API calls;
- on a managed platform, an HTTPS certificate.

That trust only ever covers this space. A staff session started on the domain can act only in
this space.

### Who can set a domain

| Deployment | Set by a Space Manager | Set by the platform superadmin |
|---|---|---|
| Managed platform | Pending until the TXT record is verified | Pending until the TXT record is verified |
| Self-hosted | Pending until the TXT record is verified | Trusted immediately, because the operator's word is enough |

On a self-hosted deployment, the operator still decides which hostnames the servers answer for.
Adding a domain to the space does not change `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` or the
reverse proxy's certificates. If the domain points at this deployment, ask the operator to add it
there. If it points at your own frontend, those settings live on your own server.

Changing the domain starts over. The new domain goes back to **Waiting for DNS proof**, unless the
superadmin set it on a self-hosted deployment. The old domain loses its trust at once. Passkeys
are tied to a domain, so people whose only second factor is a passkey on the old domain need their
password and recovery codes on the new one. The settings page counts how many people this affects
before you save.

## Embeds, API clients and webhooks

A custom domain is not the only way to put the space on another site:

- **Embeds.** Event and booking pages can be embedded in another website. Each embed has an HTTPS
  allow-list of the sites that may frame it. The allow-lists are in the events and bookings
  settings.
- **API clients.** A server, such as another makerspace's backend, a university system or a script,
  gets an API client with chosen scopes under **API**. See
  [api-client-protocol.md](api-client-protocol.md) for request signing. API-client browser origins
  can make public calls only and can never hold a staff session.
- **Webhooks.** Alerts can go to chat rooms and webhooks under **Settings › Email & integrations**.
