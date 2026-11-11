---
title: Rate limits
group: API
order: 50
summary: How throttling works, the default rates and how operators tune them.
---

# Rate limits

A request over its limit gets `429 Too Many Requests` with a `Retry-After` header. Limits protect sign-in, public forms and credentials from abuse; ordinary use stays far below them.

## Who is counted

| Caller | Counted by |
| --- | --- |
| A signed API client | The client, by **tier** |
| A personal access token or OAuth app connection | The credential (120 requests per minute by default) |
| A signed-in person on a member route | The person |
| Anyone else | The client IP address |

Only a **signed server client** earns a tier. A browser client or publishable key is identified but never elevated, because those values are public.

## API client tiers

| Tier | Default |
| --- | --- |
| `public` | 30 per minute |
| `standard` (the default tier) | 120 per minute |
| `trusted` | 600 per minute |

Operators change them with `THROTTLE_CLIENT_PUBLIC`, `THROTTLE_CLIENT_STANDARD` and `THROTTLE_CLIENT_TRUSTED`. Credential-bearing token requests share `PERSON_CREDENTIAL_RATE_PER_MINUTE` (120).

## Some default scoped limits

| Scope | Default |
| --- | --- |
| Sign-in (`login`) | 10 per minute |
| Two-step verification (`mfa_verify`, `mfa_challenge`) | 10 per minute |
| Member sign-up | 5 per minute |
| Phone code request | 5 per minute, 5 per hour per number |
| Social sign-in | 10 per minute |
| Public read routes | 120 per minute |
| Hardware request submit | 10 per minute |
| Event registration | 10 per hour |
| Shop orders | 30 per hour |
| Personal token management, OAuth consent | 30 per hour |
| API client management | 120 per hour |

These are defaults from the server settings. Each has an environment variable named `THROTTLE_<SCOPE>` (for example `THROTTLE_LOGIN=20/min`), listed in the [environment reference](../environment-reference.md).

## Behind a proxy

IP-based limits need the real client address. Set `TRUSTED_PROXY_COUNT` to the number of proxies in front of the backend; production refuses to start unless it is set explicitly. Without it every client could look like your proxy.

## Handling 429

1. Stop sending, wait `Retry-After` seconds.
2. Retry with exponential backoff and jitter.
3. Spread polling; prefer [webhooks](webhooks.md) to polling for changes.

## See also

- [Errors](errors.md)
- [Authentication](authentication.md)
