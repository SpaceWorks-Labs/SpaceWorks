---
title: Run behind a reverse proxy and reach the control plane
group: How-to guides
order: 200
summary: Put nginx or another proxy in front of SpaceWorks, and open /control/ safely over an SSH tunnel.
---

# Run behind a reverse proxy and reach the control plane

Two separate jobs: terminating HTTPS in front of SpaceWorks, and reaching the server-side `/control/` console, which is hidden by default.

## Put your own proxy in front

If you already run nginx, choose **HTTPS option 3** during setup. Setup writes `spaceworks-proxy.nginx.conf` in the install directory and prints these steps. nginx must be running with the Certbot nginx plugin.

1. Point DNS `A`/`AAAA` for `<domain>` at the server (and `files.<domain>` when you use bundled storage).
2. Get a certificate (add the second `-d` only for bundled storage):

```bash
sudo certbot certonly --nginx --cert-name <domain> -d <domain> [-d files.<domain>]
```

3. Install the generated file and reload:

```bash
sudo cp "<install-dir>/spaceworks-proxy.nginx.conf" /etc/nginx/conf.d/spaceworks.conf
sudo nginx -t && sudo systemctl reload nginx
```

4. Check `https://<domain>/api/v1/health/`.

The generated config redirects HTTP to HTTPS, forwards to `127.0.0.1:8080`, keeps `/api/v1/live/` streams unbuffered, keeps calendar `.ics` URLs out of logs (they are bearer credentials), allows uploads up to `128m` and the tenant-migration import route up to `20g`.

### If you write the proxy yourself

- Tell the backend how many proxies sit in front with `TRUSTED_PROXY_COUNT`. In production it **must be set explicitly**; the backend refuses to start without it.
- Add the hostname to `ALLOWED_HOSTS` and `https://<domain>` to `CSRF_TRUSTED_ORIGINS`.
- Set `TRUST_X_FORWARDED_PROTO=true` only when your proxy is the trusted TLS boundary and strips client-supplied forwarded headers.
- Keep direct backend and frontend HTTP ports private.
- Strip `X-SpaceWorks-Control-Tunnel` from client requests.

## Reach the control plane

`/control/` (with its MFA step at `/mfa/control/` and re-authentication at `/mfa/reauth/`) is the superadmin's server-side power tool. Day-to-day platform work lives in the web console under **Platform**. By default `/control/` answers **404** everywhere except on the server itself or through an SSH tunnel.

### Recommended: SSH tunnel (automatic HTTPS only)

1. Set `CONTROL_PLANE_TUNNEL_PORT` to a free port, for example `8444`. The installer asks about this; to change an existing install rerun it and choose **6) Turn web access to the control panel (/control/) on or off**, or run `bash scripts/control-plane-settings.sh`.
2. The server then listens on `127.0.0.1:<port>` only. It needs Docker Engine 28 or newer.
3. From your computer:

```bash
ssh -N -L 8443:127.0.0.1:<port> you@your-server
```

4. Open `https://localhost:8443/control/` and accept the certificate warning once. Use `localhost`, not `127.0.0.1`.

### Through the website (opt-in)

Set `CONTROL_PLANE_PROXY=true` to also serve `/control/` on the site's own address, and list your own address or VPN range in `CONTROL_PLANE_ALLOW_CIDRS` (space-separated). The allowlist sees the address the proxy sees; behind your own reverse proxy every client looks like that proxy, so leave it empty and restrict `/control/`, `/mfa/control/` and `/mfa/reauth/` in your proxy instead.

| Setting | Default | Meaning |
| --- | --- | --- |
| `CONTROL_PLANE_TUNNEL_PORT` | empty (off) | Loopback-only HTTPS port for the tunnel |
| `CONTROL_PLANE_PROXY` | `false` | Also serve `/control/` on the public address |
| `CONTROL_PLANE_ALLOW_CIDRS` | empty (anyone) | With the proxy route only: who may reach it; others get 403 |

Apply changes without changing the release:

```bash
bash scripts/apply-settings.sh --control-plane on --tunnel-port 8444
```

> **Warning** Exposing `/control/` on the public address shares an origin with the website, and an unenrolled superadmin's password alone signs in. Prefer the tunnel; if you keep the website route, enrol two-step sign-in and use the allowlist.

## See also

- [Self-hosting guide](../self-hosting.md#reaching-the-control-plane)
- [Use your own domain with HTTPS](custom-domain.md)
