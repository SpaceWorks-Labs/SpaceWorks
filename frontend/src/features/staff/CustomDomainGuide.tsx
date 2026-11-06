import { t } from "@lingui/core/macro";
export type DomainStatus = "pending" | "verified" | "failed";
export type DomainRecord = { host: string; type: "TXT"; value: string };

/** #192: what a Space Manager does to run the space on their own domain or frontend, in order. */
export function CustomDomainGuide({ domain, record, status }: {
  domain: string; record: DomainRecord | null; status: DomainStatus;
}) {
  const verified = status === "verified";
  return <div className="grid min-w-0 gap-3">
    {verified ? <p className="text-sm text-ink">
      {t`This domain is verified: sign-in, the staff console and browser API calls from it are trusted.`}</p> : <p role="status" className="text-sm text-ink">
      {t`Until the domain is verified it gets no trust: no sign-in or staff console from it, and browsers on it cannot call the API (CORS). Visitors keep using the space's usual address meanwhile.`}</p>}
    <ol className="grid list-decimal gap-2 pl-5 text-sm text-muted">
      <li>{t`Point `}<code>{domain}</code> {t` at this deployment (a CNAME, or A/AAAA records), or at your own SpaceWorks frontend that talks to this API.`}</li>
      <li>{t`Serve it over HTTPS with a valid certificate for `}<code>{domain}</code>{t`, and forward both the public site and`}<code> /admin</code> {t` to the frontend.`}</li>
      {record ? <li>{t`Add this DNS TXT record to prove you control the domain:`}<DnsRecord record={record} /></li> : null}
      {record ? <li>{t`Press `}<span className="font-semibold">{t`Verify domain`}</span>. DNS changes can take a while to reach
        everyone; you can check again at any time.</li> : null}
    </ol>
    <p className="text-sm text-muted">
      {t`Building something else on top of the space? Use `}<a className="underline underline-offset-4" href="/admin/api">{t`API clients`}</a> {t` for server access, the webhooks under `}<a className="underline underline-offset-4"
      href="/admin/settings">{t`Settings › Email & integrations`}</a> {t` for alerts, and the event and booking embeds for other websites. The guide is docs/own-domain-and-frontend.md.`}</p>
  </div>;
}

export function DnsRecord({ record }: { record: DomainRecord }) {
  return (
    <div className="mt-2 grid min-w-0 gap-2">
      <dl className="grid min-w-0 gap-2 @sm:grid-cols-[96px_minmax(0,1fr)]">
        <dt className="text-xs uppercase text-muted">{t`Host`}</dt>
        <dd className="break-all code-text text-xs text-ink">{record.host}</dd>
        <dt className="text-xs uppercase text-muted">{t`Type`}</dt>
        <dd className="code-text text-xs text-ink">{record.type}</dd>
        <dt className="text-xs uppercase text-muted">{t`Value`}</dt>
        <dd className="break-all code-text text-xs text-ink">{record.value}</dd>
      </dl>
    </div>
  );
}

export function domainStatusTone(status: DomainStatus) {
  return status === "verified" ? "success" : status === "failed" ? "danger" : "warn";
}

export function domainStatusLabel(status: DomainStatus) {
  return { pending: "Waiting for DNS proof", verified: "Verified", failed: "Check failed" }[status];
}
