# Single-Tenant Branded Frontend

The same React frontend can run as either the central portal or as one
makerspace's branded site.

## Runtime Config

Single-tenant mode is enabled by `/config.js`:

```js
window.__TENANT__ = {
  apiUrl: "https://tinkerspace.example/api",
  tenantToken: "ABCD"
};
```

`tenantToken` is the makerspace **`public_code`**. It is only used for
`GET /api/v1/bootstrap?tenant=...`. Do not put the makerspace `public_api_key` in
config; bootstrap returns that publishable key and the frontend uses it for public
data calls.

The makerspace `public_code` is shown in the staff console and the `/control/`
Django admin. It is a public bootstrap identifier, not a staff session token. (A
branded site is also resolved automatically by its own domain — see Backend
Registration — but `config.js` must still carry the `public_code` so the frontend
knows at startup that it is in single-tenant mode rather than central mode.)

The production frontend container writes `/config.js` at startup from:

- `TENANT_API_URL` - backend API base, for example `https://host.example/api`
- `TENANT_TOKEN` - the makerspace `public_code`

If those are unset, the same startup script falls back to `VITE_API_URL` and
`VITE_TENANT_TOKEN`.

Startup validation rejects unsafe runtime config before writing `/config.js`.
`TENANT_API_URL` uses a loose prefix check: values starting with `/`, `http://`,
or `https://` are accepted. `TENANT_TOKEN` may only contain letters, numbers,
dot, underscore, colon, and dash, up to 256 characters. Control characters,
quotes, backslashes, backticks, and angle brackets are rejected.

`/config.js` is served with `Cache-Control: no-store`, so changing those env vars
and restarting the container re-points the site without rebuilding the bundle.

## Backend Registration

Each makerspace can stay on the central multi-tenant portal or run a single-tenant
branded site. Both are served by the same React build and the same backend.

Central multi-tenant mode is the default and needs no configuration:

- public catalog: `/m/<slug>`
- staff console: shared `/admin`

For a branded site, set the makerspace's **Custom domain** in the staff console
Settings tab (Makerspace settings → Custom domain), for example
`alphamakerspace.com`. This is the single `Makerspace.frontend_domain` field, and
it is the only setting required. That one value:

- serves all of the makerspace's public and staff routes from that domain
  (`/`, `/items/:id`, `/print`, `/checkout`, `/admin`, `/guest-admin`, `/scanner`),
- resolves the tenant by request origin at `GET /api/v1/bootstrap`, and
- feeds general CORS, the staff refresh/logout CSRF allowlist, and publishable-key
  public API validation.

You do **not** need to register the origin anywhere else for the branded domain —
there is no separate frontend-registry step and no `cors_allowed_origins` entry to
add. (`makerspace.cors_allowed_origins`, synced from active API-client
`allowed_origins`, remains for third-party / API-client origins only. Those origins
are **public-only**: they can make publishable-key API calls but can never pass the
staff refresh/CSRF flow or hold a staff session.)

Optionally, a makerspace can switch on **Hide this space from the platform**
(`Makerspace.hidden_from_central_directory`; no custom domain needed) to drop
itself from the central directory, Discover and the shared listings. Its `/m/<slug>`
deep link still resolves — it is a discovery hide, not a hard block. See
[own-domain-and-frontend.md](own-domain-and-frontend.md).

Staff refresh/logout rejects non-localhost `http://` origins and matches the exact
`https://<domain>` origin (host-only or odd-port variants are rejected). Use HTTPS
for hosted staff dashboards; local development may keep `http://localhost`.

## Routes

Central mode remains unchanged:

- `/` - makerspace directory
- `/m/:slug` - public catalog
- `/m/:slug/items/:id` - item detail
- `/m/:slug/print` - public print requests
- `/m/:slug/checkout` - public self-checkout
- `/admin` - shared staff console with makerspace switching
- `/guest-admin` - guest handover console with makerspace switching
- `/scanner` - shared staff scanner
- `/superadmin` - platform superadmin console
- `/kiosk/:slug` - public kiosk view
- `/reset-password` - staff password reset

Single-tenant mode uses clean root routes:

- `/` - configured makerspace catalog
- `/items/:id` - item detail
- `/print` - public print requests
- `/checkout` - public self-checkout
- `/admin` - staff console locked to the configured makerspace
- `/guest-admin` - guest handover console locked to the configured makerspace
- `/scanner` - staff scanner locked to the configured makerspace
- `/reset-password` - staff password reset

## Isolation

The branded site hides the makerspace switcher. For **browser** staff requests
(those carrying an `Origin`/`Referer`), the backend hard-scopes actions to the
domain's makerspace — acting on another makerspace is rejected — and public data is
scoped by slug plus the publishable-key↔slug validation. Requests with no
`Origin`/`Referer` (e.g. raw server-to-server calls) are not origin-scoped and fall
back to `MakerspaceMembership`, which remains the underlying authority: a user can
only act on makerspaces their membership allows.
