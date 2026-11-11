import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { EmptyState, ErrorText, ListRow, RelativeTime, Skeleton, StatusPill } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";

// Open item C13. Hand-typed until the integrator regenerates the OpenAPI client
// (admin_api/views_platform_defaults.py). Superadmin only, platform session.
type ModuleDefault = { key: string; label: string; description: string; group: string; always_on: boolean;
  on_for_new_spaces: boolean; spaces_on: number };
type PlatformAdmin = { id: number; username: string; is_active: boolean; mfa_enabled: boolean; last_login: string | null };

const PLATFORM = "platform" as const;
const getDefaults = () => staffRequest<{ spaces_total: number; modules: ModuleDefault[] }>("/admin/platform/module-defaults", {}, PLATFORM);
const getAdmins = () => staffRequest<{ admins: PlatformAdmin[] }>("/admin/platform/admins", {}, PLATFORM);

/** What a new space starts with, and how many spaces use each feature today. Read-only by design. */
export function ModuleDefaultsSection() {
  const query = useQuery({ queryKey: ["platform-module-defaults"], queryFn: getDefaults });
  if (query.isLoading) return <Skeleton className="h-40 w-full" />;
  if (query.isError) return <ErrorText resource={t`the feature defaults`} onRetry={() => { void query.refetch(); }} />;
  const data = query.data;
  if (!data?.modules.length) return <EmptyState message={t`No features to show.`} />;
  return <div className="grid gap-3">
    <p className="text-sm text-muted">{t`A new space starts with the always-on features plus the areas chosen when it is set up. Each space can switch features on or off later.`}</p>
    <ul className="grid gap-2" aria-label={t`Feature defaults`}>
      {data.modules.map(row => <li key={row.key}><ListRow title={row.label}
        meta={<span className="break-words">{row.description}</span>}
        right={<div className="grid justify-items-end gap-1 text-right">
          <StatusPill label={row.always_on ? t`Always on` : row.on_for_new_spaces ? t`On for new spaces` : t`Off for new spaces`}
            tone={row.always_on || row.on_for_new_spaces ? "success" : "neutral"} />
          <span className="text-xs tabular-nums text-muted">{t`${row.spaces_on} of ${data.spaces_total} spaces`}</span>
        </div>} /></li>)}
    </ul>
  </div>;
}

/** Every platform admin account: name, status, two-step sign-in and last sign-in; no contact details. */
export function PlatformAdminsSection() {
  const query = useQuery({ queryKey: ["platform-admins"], queryFn: getAdmins });
  if (query.isLoading) return <Skeleton className="h-24 w-full" />;
  if (query.isError) return <ErrorText resource={t`the platform admins`} onRetry={() => { void query.refetch(); }} />;
  const admins = query.data?.admins ?? [];
  if (!admins.length) return <EmptyState message={t`No platform admins found.`} />;
  return <ul className="grid gap-2" aria-label={t`Platform admins`}>
    {admins.map(admin => <li key={admin.id}><ListRow title={admin.username}
      meta={admin.last_login ? <span>{t`Last signed in`} <RelativeTime date={admin.last_login} /></span> : <span>{t`Never signed in`}</span>}
      right={<div className="flex flex-wrap justify-end gap-1">
        <StatusPill label={admin.is_active ? t`Active` : t`Disabled`} tone={admin.is_active ? "success" : "neutral"} />
        <StatusPill label={admin.mfa_enabled ? t`Two-step on` : t`Two-step off`} tone={admin.mfa_enabled ? "success" : "warn"} />
      </div>} /></li>)}
  </ul>;
}
