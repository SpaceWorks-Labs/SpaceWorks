---
title: Security hardening
group: Hosting
order: 100
summary: Running a safe server - HTTPS, built-in protections, MFA, control-plane access, secrets and encryption keys.
---

# Security hardening

Space Works ships with sensible protections on. This page covers what you should decide and check on your own
server. The detailed reference is in the [self-hosting guide](../self-hosting.md#https--security-hardening).

## Use HTTPS

Plain HTTP is for a trial on `localhost` only. Anything other people use needs HTTPS, either through the
bundled **Caddy** with automatic certificates (give the installer a domain name and a certificate email) or
your own trusted reverse proxy. HTTPS deployments use secure cookies with `SameSite=None`. The bundled website
proxy does not trust an inbound `X-Forwarded-Proto`; it forwards only its own scheme to Django. Keep direct
backend and website ports private once HTTPS is on.

## Always-on protections

- Brute-force lockout on admin sign-in (`django-axes`, keyed by IP and username).
- Scoped request throttles on login, one-time codes, uploads and public submissions. Tune them with
  `THROTTLE_<SCOPE>` environment variables, or per scope under **Platform, Spaces, Request rate limits**.
- A Content-Security-Policy on every response. The website proxy derives it from settings such as
  `TURNSTILE_SITE_KEY`; a static host must add the Turnstile origin to its policy by hand.
- Evidence photos live in a private bucket behind short-lived signed URLs and are never public.
- Audit logs are append-only, enforced in the database as well as in code.

## MFA

The installer asks whether to require platform two-step sign-in (default yes). Staff who gain a role without
a second factor get a three-day grace with a banner, then staff screens block until they enrol. Superadmin
sign-in to `/control/` also needs a TOTP challenge when the superadmin has enrolled an authenticator or
platform policy requires one, so enrol one. Superadmin and re-authentication steps apply on top of the
password.

## Control-plane access

The Django control plane at `/control/` is a superadmin-only server-side tool. Everyday platform work happens
in the web superadmin console under **Platform**. By default (`CONTROL_PLANE_PROXY=false`) the control plane
answers only from the server itself or through an SSH tunnel; everywhere else, including the website's own
address, it answers 404. Django enforces this as well as the proxies.

| Setting | Default | What it does |
| --- | --- | --- |
| `CONTROL_PLANE_TUNNEL_PORT` | empty (off) | With automatic HTTPS: a `127.0.0.1`-only HTTPS port serving only the control plane, for an SSH tunnel. The recommended way in. |
| `CONTROL_PLANE_PROXY` | `false` | `true` also serves `/control/` on the site's own address. Opt-in. |
| `CONTROL_PLANE_ALLOW_CIDRS` | empty (anyone) | With the proxy on: space-separated addresses or ranges allowed. Others get 403. |

```bash
ssh -N -L 8443:127.0.0.1:<port> you@your-server
# then open https://localhost:8443/control/ and accept the certificate warning once
```

If you keep the website route, set an allowlist and enrol MFA, because `/control/` shares an origin with the
website. Behind your own reverse proxy, restrict `/control/`, `/mfa/control/` and `/mfa/reauth/` there, and
strip the `X-SpaceWorks-Control-Tunnel` header from client requests. Change these settings with the installer
menu or `bash scripts/control-plane-settings.sh`, which uses `scripts/apply-settings.sh` under the update lock.
On a plain-HTTP or own-proxy install the tunnel is not available; with no route and no tunnel, `/control/` is
off.

## Secrets and encryption keys

The installer generates the secrets and keys on a fresh install: `SECRET_KEY`, `API_CLIENT_ENC_KEY`,
`AUDIT_MAC_MASTER_KEY`, `PII_MASTER_KEY`, `PII_SEARCH_HASH_KEY`, `ACCOUNT_PII_MASTER_KEY`, the event
registration credential keys and `PUSH_TOKEN_HMAC_KEY`. Updates and reruns never regenerate an existing key.
Losing or changing any of them makes the data it protects unreadable, so:

- keep `.env` backed up off the server, in separate custody from the database backups;
- do not rotate `API_CLIENT_ENC_KEY` casually, or stored integration secrets can no longer be decrypted;
- keep the backup platform key off the server.

Per-space integration secrets (payment, email, chat) are stored encrypted per space and are never visible to
another space. Secrets stay in the backend; the website never holds them.

## Network and operations

- Keep `/api/v1/internal/*` and `/api/v1/metrics*` unreachable from the internet.
- Treat a GitHub Actions runner as root on the server; see [Upgrades](upgrades.md#automatic-deploys).
- The container image runs as a non-root user; see [Container images](images.md).
- Report vulnerabilities as described in the [security policy](../project/security-policy.md).
