import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { CenteredCardLayout } from "../../components/layouts";
import { publicV1Request } from "../../lib/api";

type OptIn = { makerspace_name: string; technician_name: string; has_phone: boolean; telegram_start: string;
  consent: { email: boolean; telegram: boolean; whatsapp: boolean; sms: boolean } };

/**
 * `technician-opt-in/:token`: the one-time link staff send a technician (#128 C-4). They agree
 * to repair requests by WhatsApp and/or SMS here; Telegram is a `/start` message to the bot.
 * Nothing else is possible from this page and it never shows their contact details.
 */
export function TechnicianOptInPage() {
  const { token = "" } = useParams();
  const client = useQueryClient();
  const path = `/public/technician-opt-in/${encodeURIComponent(token)}`;
  const query = useQuery({ queryKey: ["technician-opt-in", token], queryFn: () => publicV1Request<OptIn>(path), retry: false });
  const [channels, setChannels] = useState<("whatsapp" | "sms")[]>(["whatsapp"]);
  const accept = useMutation({
    mutationFn: () => publicV1Request<OptIn>(path, { method: "POST", body: JSON.stringify({ channels }) }),
    onSuccess: data => client.setQueryData(["technician-opt-in", token], data),
  });
  const data = query.data;
  const agreed = data ? (["whatsapp", "sms"] as const).filter(channel => data.consent[channel]) : [];
  return <CenteredCardLayout media={{ icon: "HardHat", tone: "accent" }} eyebrow={data?.makerspace_name}
    title={data ? t`Repair requests for ${data.technician_name}` : t`Repair requests`}
    state={query.isLoading ? { status: "loading" } : query.isError ? { status: "error", error: "This link is invalid or has expired. Ask the space for a new one." } : { status: "ready" }}
    body={data ? <>{t`${data.makerspace_name} would like to send you repair requests. Email always works. Choose the chat channels you agree to.`}</> : ""}
    content={data ? <div className="grid gap-3">
      {data.has_phone ? <fieldset className="grid gap-2"><legend className="eyebrow mb-1">{t`On the number the space has for you`}</legend>
        {(["whatsapp", "sms"] as const).map(channel => <label key={channel} className="flex min-h-11 items-center gap-2 text-sm">
          <input type="checkbox" checked={channels.includes(channel) || data.consent[channel]} disabled={data.consent[channel]}
            onChange={() => setChannels(current => current.includes(channel) ? current.filter(item => item !== channel) : [...current, channel])} />
          {channel === "whatsapp" ? t`WhatsApp` : "SMS"}{data.consent[channel] ? " (agreed)" : ""}</label>)}
      </fieldset> : <p className="text-sm text-muted">{t`The space has no phone number for you, so only Telegram and email are possible.`}</p>}
      <p className="text-sm">{t`For Telegram, send `}<span className="font-mono">{data.telegram_start}</span> {t` to the space's Telegram bot${data.consent.telegram ? " (done)" : ""}.`}</p>
      {agreed.length ? <p role="status" className="text-sm text-success-ink">{t`Thanks, you agreed to ${agreed.join(" and ")}.`}</p> : null}
      {accept.error ? <p role="alert" className="text-sm text-danger">{accept.error.message}</p> : null}
    </div> : null}
    primary={{ label: t`I agree`, pending: accept.isPending, disabled: !data?.has_phone || !channels.some(channel => !data?.consent[channel]),
      disabledReason: "Choose a channel you have not agreed to yet.", onClick: () => accept.mutate() }} />;
}
