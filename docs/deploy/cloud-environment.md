# Managed environment and finite setup

Read [hosting contracts](cloud-overview.md) and [recovery](cloud-recovery.md). Run setup on Linux
with backend requirements and age. Use owned 0700 state directories and 0600 secret/answers files.
Never use shell tracing, public CI artifacts or secret command arguments.

```sh
python scripts/init-cloud-environment.py wizard --state-dir /secure/spaceworks-setup
python scripts/init-cloud-environment.py validate --non-interactive --answers-file /secure/answers.json --secrets-file /secure/secrets.json --state-dir /secure/spaceworks-setup
python scripts/init-cloud-environment.py render --non-interactive --answers-file /secure/answers.json --secrets-file /secure/secrets.json --state-dir /secure/spaceworks-setup
```

Examples/contracts are in deploy/cloud/. Rendering prepares configuration; bootstrap completion needs real
probes, actual inbox confirmation and deployment-bound acceptance. Bootstrap uses the pre-settings secret
materializer and the same fixed role interface as runtime. The exact release invocation is:
`--role migrate python -m scripts.run_cloud_role release`. Only that finite job receives maintenance credentials.
Existing databases require explicit adoption; changing one environment variable is insufficient.

| Variable | Contract |
| --- | --- |
| SPACEWORKS_DEPLOYMENT_MODE / PROFILE | host/full defaults; free requires explicit managed |
| SPACEWORKS_DEPLOYMENT_ID | Stable generated UUID bound to the queried DB identity by release/adopt |
| DATABASE_CONNECTION_MODE | direct or proven session; never transaction |
| MANAGED_POSTGRES | True for managed admission; runtime remains non-owner |
| CLOUD_TASK_PROFILE / CLOUD_SCHEDULER | redis+beat or brokerless+loop/external; free requires brokerless+tick |
| DATABASE_MAINTENANCE_URL | Finite release/adopt/qualified jobs only; never common runtime groups |
| STORAGE_CAPABILITIES_FILE | Strict version-1 role/bucket JSON; required under managed |
| STORAGE_CAPABILITY_TTL_SECONDS | Proof freshness, default 900 (60..86400); arrange bounded refresh |
| AWS_SESSION_TOKEN | Optional private temporary session token |
| EMAIL_PROVIDER | Blank legacy; smtp/resend/postmark/ses/brevo/mailgun/sendgrid |
| EMAIL_PROVIDER_CONFIG_FILE | <=16 KiB runtime-only JSON; configuration is encrypted/write-only |
| EMAIL_PROVIDER_WEBHOOKS_ENABLED | False default; optional native signed callbacks |
| SPACEWORKS_SECRET_FILE_MODE | native default; inline explicitly materializes protected base64 JSON |
| SPACEWORKS_EMAIL_PROVIDER_CONFIG_B64 / SPACEWORKS_STORAGE_CAPABILITIES_B64 | Provider secrets removed from child env after materialization |
| TRUST_FORWARDED_HOST | False default; explicit managed ingress, upstream hosts and proxy count required |
| TRUSTED_EDGE_CIDRS / TRUSTED_EDGE_UPSTREAM_HOSTS | Independently restricted ingress and exact raw Host; no wildcard |

Inline files use owned paths under /tmp/spaceworks-secrets/. Native mounts must reach every consumer before startup.
Credential rotation does not change bucket identity or reset a mail allowance. Set exact ALLOWED_HOSTS, proxy count,
CORS/CSRF/staff origins and Secure cookie policy. Forwarded-host authority requires independent ingress validation.
A publicly reachable unrestricted backend is not a trusted edge. Free caps/account aliases are in [the free guide](cloud-free.md).
Missing usage means unknown, never zero/unlimited. Global/provider totals remain operator-only.

Render also writes a separate protected `edge.environment.json` for the server-side static adapter.
It contains fixed origins/CSP inputs, the independent edge proof and, for free only, the tick secret.
Deploy it only to the edge secret store; it contains no DB, object-storage or mail credentials and is
never browser runtime configuration. Keep runtime and release environment artifacts separate.


Forwarded-host enablement also requires TRUST_X_FORWARDED_PROTO=True and a protected
TRUSTED_EDGE_INGRESS_SECRET (32..256 ASCII bytes). The authenticated origin proxy must overwrite
X-SpaceWorks-Edge-Secret on upstream requests and remove any browser-supplied copy. Keep this value
in server-only edge/backend secret stores. Every static adapter strips the browser copy and overwrites
the upstream secret. Exact raw health GET/HEAD and
the separately secret-authenticated free tick can reach backend ingress without a forwarded host.
