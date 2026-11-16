# Grafana setup (per-space and platform analytics)

SpaceWorks does not bundle Grafana. It gives each space a **read-only database login** that can read only
that space's curated views, the same login [Metabase](metabase-setup.md) uses. It can also hand you a
ready-made Grafana data source and starter dashboards, and show your Grafana dashboards inside the staff
console. The `analytics` module must be on (it is off by default). The views are listed in
[analytics-views.md](analytics-views.md).

You can use Metabase, Grafana or both: **Reports -> Analytics -> Connection settings -> Dashboard tool**.

## 1. Run Grafana

Any Grafana 10 or later works, either Grafana Cloud or self-hosted. For a local test, add this to a compose
file next to SpaceWorks. It joins the dev network so that the database host the app reports is reachable;
check your stack's network name with `docker network ls`.

```yaml
services:
  grafana:
    image: grafana/grafana-oss:11.3.0
    ports: ["3001:3000"]
    environment:
      GF_SECURITY_ALLOW_EMBEDDING: "true"          # lets the staff console frame public dashboards
      GF_FEATURE_TOGGLES_ENABLE: "publicDashboards" # on by default in 11; harmless otherwise
      GF_RENDERING_SERVER_URL: http://renderer:8081/render          # only for "image" dashboards
      GF_RENDERING_CALLBACK_URL: http://grafana:3000/
    volumes:
      - grafana-data:/var/lib/grafana
      # After step 4, unzip the bundle here to provision the data source and dashboards:
      # - ./spaceworks-grafana/provisioning/datasources:/etc/grafana/provisioning/datasources
      # - ./spaceworks-grafana/provisioning/dashboards:/etc/grafana/provisioning/dashboards
      # - ./spaceworks-grafana/dashboards/spaceworks:/var/lib/grafana/dashboards/spaceworks
    networks: [default, spaceworks]
  renderer:                                         # optional: only for "image" dashboards
    image: grafana/grafana-image-renderer:3.11.0
    networks: [default]
volumes:
  grafana-data:
networks:
  spaceworks:
    external: true
    name: spaceworks_default
```

Open http://localhost:3001 and sign in as `admin` / `admin`. This Grafana admin account has nothing to do
with SpaceWorks.

## 2. Create a service account and token in Grafana

In Grafana, go to **Administration -> Users and access -> Service accounts -> Add service account**. Give it
the **Viewer** role, then choose **Add service account token** and copy the token. SpaceWorks needs only
Viewer: it uses the token to test the connection and to render image dashboards. Note the
**organization ID** too. It is `1` unless you made more organizations.

## 3. Create the space's read-only login in SpaceWorks

In the staff console, go to **Reports -> Analytics -> Connection settings -> Read-only database login ->
Create login**. This needs the Space Manager or the superadmin. The password is shown **once**, so copy it
now. **Rotate** gives a new password, which you then paste into Grafana. **Revoke** removes the login. The
login can read only this space's curated views. It cannot read any table, another space, or the platform
views.

## 4. Download the provisioning bundle

Under **Grafana**, choose **Download provisioning bundle**. The zip holds:

- `provisioning/datasources/spaceworks.yaml`: a PostgreSQL data source with the host, database and user
  of the login from step 3;
- `provisioning/dashboards/spaceworks.yaml`: tells Grafana to load the dashboards folder;
- `dashboards/spaceworks/<area>.json`: one starter dashboard per area that is on for the space. The areas
  are inventory, machines, events, bookings, money (charges and the ledger, never payouts) and membership;
- `README.txt`.

**The bundle never contains a password or a token.** The password field says `PASTE_PASSWORD_HERE`; replace
it with the password from step 3. Right after you create or rotate the login, while the password is still on
screen, **Download Grafana bundle with this password** fills it in. Your browser does that; the server never
sends the password again.

To use the bundle, either unzip it into the mounted folders in step 1 and restart Grafana, or add the data
source by hand (**Connections -> Data sources -> PostgreSQL**, using the same host, database, user and
password) and import each dashboard JSON (**Dashboards -> New -> Import**). The host shown is the address
the SpaceWorks app uses. A Grafana on another network may need the database's public address, with
`sslmode` set to `require`.

## 5. Connect Grafana in SpaceWorks

Under **Grafana**, enter:

- the **Grafana URL**, such as `https://grafana.example.org`, with no path, credentials, query or fragment;
- the **organization ID**;
- the **service-account token**. It is encrypted at rest and never shown again. **Replace token** rotates it and
  **Remove token** forgets it.

Then press **Test connection**. SpaceWorks calls Grafana's `/api/health` without the token, then
`/api/search` with it, and shows whether each one worked.

A space's Grafana must be on a public address. If SpaceWorks hosts only your own spaces and Grafana runs on
the same private network, for example the compose file above, the operator can set
`GRAFANA_ALLOW_PRIVATE_HOSTS=true` ([environment reference](environment-reference.md)). Leave it off if you
host other makerspaces, so a space setting can never point the server at your internal network. The platform
connection may always use a private address.

## 6. Show dashboards in the console

List each dashboard with its **uid** (the part after `/d/` in its URL), a title, and how to show it:

- **Public**: in Grafana, open the dashboard and choose **Share -> Share externally** (Grafana 11; in Grafana
  10 it is **Public dashboard**). Copy the 32-character access token from the link and paste it here. The
  console frames `https://<grafana>/public-dashboards/<token>`. Anyone who has that link can see that
  dashboard. Its data still comes only through this space's login.
- **Image**: the server renders a PNG with the service-account token. Grafana does not have to be reachable
  from the browser. This needs the image renderer (step 1).

Framing rules:

- **Docker and nginx installs.** SpaceWorks's own policy sets no `frame-src`, so a public dashboard frames
  without any change. Grafana must allow it: set `GF_SECURITY_ALLOW_EMBEDDING=true`.
- **Static-hosting deployments** (Cloudflare, Netlify, Vercel). Add the Grafana origin, and the Metabase
  origin if you use it, to the edge setting `FRAME_ORIGINS`, separated by spaces, for example
  `FRAME_ORIGINS="https://grafana.example.org"`. While it is unset, only same-origin frames are allowed.
- **Image dashboards** are served by the SpaceWorks API, so they need no allow-list entry.

## Platform-wide Grafana (superadmin)

**Platform settings -> Analytics** has the same screens, connected to one separate Grafana connection: the
provider choice, URL, organization, token, test, bundle and dashboards. Its login reads the
`spaceworks_analytics_platform` schema, which covers every space and never shows member details. Use a
different Grafana organization, or at least a different data source and folder, from any space's.

## Who sees what

| Who | Sees |
| --- | --- |
| Space Manager | the space's dashboards, and manages its connection, token, login and bundle |
| Staff holding `view_analytics` (a custom role or an organization grant) | the space's listed dashboards only; no settings, no bundle |
| Other staff and members | nothing; the routes answer 403 |
| Superadmin | any space's analytics, plus the platform connection and its dashboards |
| A Space Manager on the platform routes | nothing (403) |

With the `analytics` module off, every space route answers 404 and the space's views return no rows. The
connection is kept and comes back when the module is switched on again.

## Check it

- Give the data source a query such as `select distinct makerspace_id from spaceworks_analytics.inventory_products;`
  and expect only your space.
- After you revoke the login in SpaceWorks, the Grafana data source starts failing.
- Is a framed dashboard blank? Check that `GF_SECURITY_ALLOW_EMBEDDING` is on, that the dashboard is shared
  externally, and (on static hosting) that `FRAME_ORIGINS` includes the Grafana origin.
- Does an image dashboard fail? Check the token, the organization ID and that the renderer is running.

Every view of the connection, change, token save, rotation and removal, connection test, bundle download and
dashboard opened is audited (`analytics.grafana_*`). The audit entries never include the URL, the token or an
access token.
