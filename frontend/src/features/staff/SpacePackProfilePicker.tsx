import { t } from "@lingui/core/macro";
import { SettingsQueryState } from "./SettingsQueryState";
import { ErrorBlock, PagePager } from "../../components/ui";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Field } from "../../components/ui";
import { listPackProfiles, type PackProfile } from "./spacePacksApi";

export function SpacePackProfilePicker({ value, onChange, disabled = false, enabled = true }: {
  value: number | ""; onChange: (profile: PackProfile | null) => void; disabled?: boolean; enabled?: boolean;
}) {
  const [page, setPage] = useState(1);
  const profiles = useQuery({ queryKey: ["space-pack-profiles", page], queryFn: () => listPackProfiles(page), enabled });
  return <SettingsQueryState query={profiles} resource={t`space pack profile`}><div className="grid gap-2">
    <Field label={t`Saved install profile`}>
      <select className="desk-input w-full" value={value} disabled={disabled || profiles.isLoading}
        onChange={(event) => onChange(profiles.data?.results.find((profile) => profile.id === Number(event.target.value)) ?? null)}>
        <option value="">{t`No saved profile`}</option>
        {(profiles.data?.results ?? []).map((profile) => <option key={profile.id} value={profile.id}>{profile.name}</option>)}
      </select>
    </Field>
    {profiles.error ? <ErrorBlock error={new Error(t`Couldn't load space pack profile. Try again.`)} onRetry={() => { void profiles.refetch(); }} /> : null}
    <PagePager page={page} setPage={next => { onChange(null); setPage(next); }} count={profiles.data?.count} next={profiles.data?.next} disabled={disabled} />
  </div></SettingsQueryState>;
}
