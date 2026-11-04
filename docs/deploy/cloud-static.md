# Static frontend adapters

The contract is deploy/static/contract.json. Build the frontend, then stage a NEW output directory:

```sh
node deploy/static/prepare.mjs pages /secure/new-pages-output
node deploy/static/prepare.mjs vercel /secure/new-vercel-output
```

Deploy staged output with the provider CLI. For Netlify, copy deploy/static/netlify/netlify.same-origin.toml
into an isolated deployment root as netlify.toml; the repository root retains its original split-origin recipe.
Worker full/free configs live under deploy/static/cloudflare/. Set production edge env through provider UI/API;
preview deployments must not become production authorities. Never overwrite an existing publish directory.

PUBLIC_ORIGIN, BACKEND_ORIGIN, optional LIVE_ORIGIN and CSP source arrays are public configuration.
FREE_TICK_SECRET is server-only. Same-origin browser apiUrl is /api. config.js is no-store. Deep links,
backend metadata/share/embed, /e and /share/pages precede SPA fallback. Preserve original Cookie/Origin/CSRF,
strip spoofed forwarded/internal headers and preserve signed URL hosts. Redact bearer/share paths and query
strings from logs; never cache API/auth/share/config responses.

Forwarded host requires independent restricted backend ingress, exact raw upstream Host and proxy count.
Configure TRUST_FORWARDED_HOST, TRUSTED_EDGE_CIDRS and TRUSTED_EDGE_UPSTREAM_HOSTS; never use wildcard host trust
on a public backend. Deny browser internal/control/metrics access. Only the scheduled free handler may call
its fixed backend tick path, without redirects or secret logging. Provider access logs/cache rules must not
bypass no-store or disclose bearer routes. Pages Functions must fail closed on quota exhaustion.

Split-origin deployments need exact CORS/CSRF/public/staff-origin allowlists, Secure cookies and supported
SameSite policy. Third-party cookie blocking can prevent unrelated provider-domain sessions; prefer one verified
same origin. Never rewrite cookie Domain to hide this limitation. Verify actual provider account terms/limits,
including all guarded asset requests in Worker CPU/request/cron/subrequest measurements.

Validate deep-link refresh, config secrecy, login/MFA/cookie rotation/logout, tenant boundaries, QR camera/WASM/
PWA, presigned upload/finalization/private reads and theme/accessibility on each adapter. Browser/live checks
have not run here. Static hosting does not change [recovery guarantees](cloud-recovery.md).


Forwarded-host enablement also requires TRUST_X_FORWARDED_PROTO=True and a protected
TRUSTED_EDGE_INGRESS_SECRET (32..256 ASCII bytes). The authenticated origin proxy must overwrite
X-SpaceWorks-Edge-Secret on upstream requests and remove any browser-supplied copy. Keep this value
in server-only edge/backend secret stores. F's adapters still need that reviewed secret-header wiring;
until then forwarded-host enablement correctly refuses their requests. Exact raw health GET/HEAD and
the separately secret-authenticated free tick can reach backend ingress without a forwarded host.
