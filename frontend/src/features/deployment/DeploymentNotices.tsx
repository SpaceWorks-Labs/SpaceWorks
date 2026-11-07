import { t } from "@lingui/core/macro";
import { Callout } from "../../components/ui";
import type { DeploymentNoticeData } from "./types";

export function DeploymentNotices({ data }: { data: DeploymentNoticeData }) {
  return <div className="grid gap-3" aria-label={t`Deployment notices`}>
    {data.mode === "managed" && data.scanner === "none" ? <Callout size="inline" tone="warn"
      lead="Malware scanning is off."
      body={t`Files are validated by type and size, but are not scanned for malware. Configure an external ClamAV service to enable scanning.`} /> : null}
    {data.mode === "managed" ? <Callout size="inline" tone="warn" lead="Managed recovery"
      body={t`Deployment recovery uses your database provider's backups/PITR and object-store durability, with the limitations documented for your providers. Portable tenant recovery uses a separately exported tenant dump and its supported import target. Ordinary tenant archives are archive-and-purge records and cannot be restored.`} /> : null}
    {data.profile === "free" ? <>
      <Callout size="inline" tone="warn" lead="Free hosting is best effort."
        body={t`Cold starts, missed ticks, provider restarts or pauses, and quota suspension can delay requests and reminders. Schedules run at the tick interval plus backlog and outages. There is no always-awake guarantee or SLA.`} />
      {!data.media_validation_available ? <Callout size="inline" tone="warn" lead="Some media uploads are unavailable."
        body={t`This profile omits video validation and previews that require ffmpeg or ffprobe. Supported ordinary uploads remain available; unsupported types are refused before acceptance.`} /> : null}
      <Callout size="inline" tone="warn" lead="Scheduled database backups are unavailable in this profile."
        body={t`Arrange a daily external encrypted backup with verified private storage, object and key custody, or an eligible portable tenant export. Provider recovery may be unavailable on your plan. These alternatives do not provide coordinated host recovery.`} />
    </> : null}
  </div>;
}
