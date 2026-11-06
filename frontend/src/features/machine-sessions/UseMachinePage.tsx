import { t } from "@lingui/core/macro";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { DetailLayout } from "../../components/layouts";
import { Callout, KeyValueCard, StatusPill } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { MemberJobsShell, type MemberJobsContext } from "../machine-jobs/MemberJobsShell";
import {
  fetchSessionPreview, refusalText, sessionErrorMessage, sessionKeys, startSession, stopSession, type SessionPreview,
} from "./api";
import { SessionTimerCard } from "./SessionTimerCard";
import { duration, rateLine, when } from "./sessionFormat";

/** The "Use this machine" sheet: what a session costs and its rules, then Start. */
function StartSheet({ preview, onStart, starting, error }: {
  preview: SessionPreview; onStart: () => void; starting: boolean; error?: string;
}) {
  return <section className="desk-panel grid gap-4 p-5" aria-labelledby="use-machine-title">
    <div><h2 id="use-machine-title" className="title-panel">{t`Use this machine`}</h2>
      <p className="mt-1 text-sm text-muted">{t`Start when you begin and tap Stop when you finish. Your time is recorded from Start to Stop.`}</p></div>
    <dl className="grid gap-2 text-sm">
      <div className="flex flex-wrap justify-between gap-2"><dt className="text-muted">{t`Rate`}</dt>
        <dd>{preview.billing && preview.rate ? rateLine(preview.rate) : t`Free to use`}</dd></div>
      {preview.rate?.discount_name ? <div className="flex flex-wrap justify-between gap-2"><dt className="text-muted">{t`Your discount`}</dt>
        <dd>{preview.rate.discount_name}</dd></div> : null}
      <div className="flex flex-wrap justify-between gap-2"><dt className="text-muted">{t`Longest session`}</dt><dd>{duration(preview.max_minutes)}</dd></div>
      {preview.closes_at ? <div className="flex flex-wrap justify-between gap-2"><dt className="text-muted">{t`Space closes`}</dt>
        <dd>{when(preview.closes_at)}</dd></div> : null}
    </dl>
    <p className="text-sm text-muted">{t`A session you forget to stop ends by itself at the longest length, when you check out or at closing time.`}{preview.billing ? t` The price shown is the price used; staff confirm any charge.` : ""}</p>
    {preview.can_start ? null : <div role="status"><Callout size="inline" tone="warn" lead={refusalText(preview.refusal)} /></div>}
    {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
    <button type="button" className="desk-button-brand min-h-12 justify-self-stretch sm:justify-self-start"
      disabled={!preview.can_start || starting} onClick={onStart}>{starting ? t`Starting…` : t`Start session`}</button>
  </section>;
}

function UseMachine({ machineId, context }: { machineId: number; context: MemberJobsContext }) {
  const client = useQueryClient();
  const preview = useQuery({ queryKey: sessionKeys.preview(machineId), queryFn: () => fetchSessionPreview(machineId),
    enabled: context.ready && machineId > 0, retry: false,
    refetchInterval: current => current.state.data?.live_session ? 60_000 : false });
  const refresh = () => {
    void client.invalidateQueries({ queryKey: sessionKeys.preview(machineId) });
    void client.invalidateQueries({ queryKey: sessionKeys.allMine });
  };
  const start = useMutation({ mutationFn: (digest: string) => startSession(machineId, digest), onSuccess: refresh,
    onError: error => { if (error instanceof StructuredApiError && error.code === "price_changed") refresh(); } });
  const stop = useMutation({ mutationFn: (id: number) => stopSession(id), onSuccess: refresh });
  const data = preview.data;
  const missing = preview.error instanceof StructuredApiError && [403, 404].includes(preview.error.status);
  const live = data?.live_session ?? null;
  const history = context.path("member/machine-sessions");
  return <DetailLayout back={{ label: t`My machine sessions`, href: history }}
    state={context.bootstrapError ? { status: "error", error: t`Couldn't load this makerspace. Try again.` }
      : !context.ready || (preview.isPending && machineId > 0) ? { status: "loading" }
      : preview.isError && !missing ? { status: "error", error: t`Couldn't load this machine. Try again.`, onRetry: () => { void preview.refetch(); } }
      : { status: "ready" }}
    isEmpty={missing || machineId <= 0}
    empty={{ message: t`This machine isn't available for sessions here. Ask staff if you think it should be.`, action: { label: t`My machine sessions`, href: history } }}
    title={data?.machine_name ?? t`Machine`} identity={{ kind: "icon", icon: "Cog", tone: "accent" }}
    status={data ? <StatusPill tone={live ? "info" : data.can_start ? "success" : "warn"} label={live ? t`In use by you` : data.can_start ? t`Ready` : t`Not available now`} /> : undefined}
    meta={data ? [data.machine_type_name] : undefined}
    main={data ? <div className="grid gap-5">
      {live ? <SessionTimerCard session={live} maxMinutes={data.max_minutes} onStop={() => stop.mutate(live.id)} stopping={stop.isPending}
        error={stop.isError ? sessionErrorMessage(stop.error) : undefined} />
        : <StartSheet preview={data} onStart={() => start.mutate(data.digest)} starting={start.isPending}
          error={start.isError ? sessionErrorMessage(start.error) : undefined} />}
      {stop.isSuccess && !live ? <p role="status" className="text-sm">{t`Session stopped after ${duration(stop.data.minutes)}.`}{stop.data.charge_state === "raised" ? t` Its charge is in your payments.` : ""}</p> : null}
    </div> : null}
    aside={data ? <KeyValueCard items={[{ label: t`Machine`, value: data.machine_name }, { label: t`Type`, value: data.machine_type_name }]} /> : undefined} />;
}

/** `machines/:machineId/use`: where the machine's QR lands. */
export function UseMachinePage() {
  const { machineId = "" } = useParams();
  const id = /^\d+$/.test(machineId) ? Number(machineId) : 0;
  return <MemberJobsShell>{context => <UseMachine machineId={id} context={context} />}</MemberJobsShell>;
}
