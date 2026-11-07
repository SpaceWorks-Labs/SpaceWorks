import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { ErrorText, Skeleton, StatusPill } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";

type Check = { ready: boolean; hint: string };
type Registration = { hint: string; production: boolean; login_ready: boolean; login: Record<string, Check>; optional: Record<string, Check> };
type Platform = { hint: string; login_ready: boolean; push_ready: boolean; apple_revocation_ready: boolean; associations_ready: boolean; registrations: Registration[] };
export type MobileReadiness = { platforms: Record<string, Platform> };

const NAMES: Record<string, string> = { android: t`Android`, ios: t`iPhone and iPad` };
const CHECKS: [keyof Platform, string][] = [["login_ready", t`Sign-in`], ["push_ready", t`Push`], ["associations_ready", t`App links`], ["apple_revocation_ready", t`Apple revocation`]];

function Pill({ ok, label }: { ok: boolean; label: string }) {
  return <StatusPill label={ok ? t`${label}: ready` : t`${label}: not ready`} tone={ok ? "success" : "warn"} />;
}

/** #190: the read-only mobile readiness checks (no provider probes, no secret values) in the web console. */
export function MobileReadinessPanel() {
  const query = useQuery({ queryKey: ["platform-mobile-readiness"],
    queryFn: () => staffRequest<MobileReadiness>("/admin/platform/mobile-readiness", {}, "platform") });
  if (query.isLoading) return <Skeleton className="h-24 w-full" />;
  if (query.isError || !query.data) return <ErrorText resource={t`mobile readiness`} onRetry={() => { void query.refetch(); }} />;
  return <section className="grid gap-3" aria-label={t`Mobile readiness`}>
    <h3 className="title-section">{t`Readiness`}</h3>
    {Object.entries(query.data.platforms ?? {}).map(([key, platform]) => <div key={key} className="grid gap-2 rounded-xl border border-line bg-panel p-3">
      <div className="flex flex-wrap items-center gap-2"><span className="font-semibold text-ink">{NAMES[key] ?? key}</span>
        {CHECKS.filter(([field]) => key === "ios" || field !== "apple_revocation_ready").map(([field, label]) =>
          <Pill key={field} ok={Boolean(platform[field])} label={label} />)}</div>
      <p className="text-xs text-muted">{platform.hint}</p>
      {platform.registrations.length ? <ul className="grid gap-2">{platform.registrations.map((row, index) => <li key={index} className="grid gap-1 text-sm">
        <span className="font-medium">{row.production ? t`Production registration ${index + 1}` : t`Development registration ${index + 1}`}</span>
        <ul className="grid gap-1">{Object.entries({ ...row.login, ...row.optional }).filter(([, check]) => !check.ready).map(([name, check]) =>
          <li key={name} className="text-muted"><span className="font-medium text-ink">{name}</span>: {check.hint}</li>)}</ul>
        {row.login_ready ? <span className="text-success">{t`Sign-in checks pass.`}</span> : null}
      </li>)}</ul> : <p className="text-sm text-muted">{t`No approved registration for this platform yet.`}</p>}
    </div>)}
  </section>;
}
