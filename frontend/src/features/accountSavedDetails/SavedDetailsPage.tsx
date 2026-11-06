import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { SettingsLayout } from "../../components/layouts/SettingsLayout";
import { StructuredApiError } from "../../lib/api";
import { ownSavedDetails } from "./api";
import { fields } from "./fieldPresentation";
import { ResumeVault } from "./ResumeVault";
import { SavedDetailEditor } from "./SavedDetailEditor";
import { SavedDetailsExport } from "./SavedDetailsExport";
import { savedDetailsKey } from "./types";

/** G mounts inside the existing member AppShell, independently of membership. */
export function SavedDetailsPage({ actorId }: { actorId: number }) {
  const client = useQueryClient();
  const [blocked, setBlocked] = useState(false);
  const details = useQuery({ queryKey: savedDetailsKey(actorId), queryFn: ownSavedDetails, enabled: !blocked, gcTime: 0, staleTime: 0, retry: false });
  useEffect(() => () => { client.removeQueries({ queryKey: savedDetailsKey(actorId) }); }, [actorId, client]);
  const records = details.data?.fields || [];
  const denied = details.error instanceof StructuredApiError && [401, 403, 404].includes(details.error.status);
  useEffect(() => { if (denied) { setBlocked(true); client.removeQueries({ queryKey: savedDetailsKey(actorId) }); } }, [denied, client, actorId]);
  useEffect(() => { setBlocked(false); }, [actorId]);
  return <SettingsLayout header={{ title: t`Saved details`, subtitle: t`Private details for your next registration. You review every form before submitting.` }}
    state={blocked ? { status: "error", error: "Sign in with an active member account to view saved details.", onRetry: () => setBlocked(false) } : details.isPending ? { status: "loading" } : details.error && (!details.data || denied) ? { status: "error", error: details.error.message, onRetry: () => void details.refetch() } : { status: "ready" }}
    sections={[
      { id: "privacy", title: t`Your private account vault`, rows: <><p>{t`These details are separate from your sign-in methods and public profile. Organisers receive only answers you submit to their event. Sensitive details are saved only when you choose. Deleting a saved value does not remove an event’s submitted answers.`}</p>{details.error ? <p role="alert" className="text-danger">{t`Refresh failed. Your drafts are still here. `}<button className="desk-button" onClick={() => void details.refetch()}>{t`Try refresh again`}</button></p> : null}</> },
      { id: "details", title: t`Personal details`, rows: <div className="grid gap-4">{fields.map(presentation => {
        const saved = records.find(row => row.field_key === presentation.key);
        return <SavedDetailEditor key={`${actorId}-${presentation.key}`} actorId={actorId} presentation={presentation} saved={saved} version={saved?.version || 0} />;
      })}</div> },
      { id: "resume", title: t`Résumé`, rows: <ResumeVault key={`resume-${actorId}`} actorId={actorId} saved={records.find(row => row.field_key === "resume")} /> },
      { id: "export", title: t`Your data`, rows: <SavedDetailsExport key={`export-${actorId}`} actorId={actorId} /> },
    ]} />;
}
