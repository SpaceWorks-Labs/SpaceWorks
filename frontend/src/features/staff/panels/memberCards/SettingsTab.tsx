// Member-card settings: issuing, email, the public check page and design approval.
// Each switch saves on its own; the server checks the settings authority per key.
import { ErrorBlock, Skeleton } from "../../../../components/ui";
import { useMemberCardSettings, useSaveMemberCardSettings } from "./apiCards";
import type { MemberCardSettings } from "./types";

type Key = "auto_issue" | "email_on_issue" | "public_verify" | "verify_show_plan" | "design_approval_required";

const ROWS: { key: Key; label: string; help: string }[] = [
  { key: "auto_issue", label: "Issue a card when a membership starts",
    help: "New members get a card straight away. Existing members keep theirs." },
  { key: "email_on_issue", label: "Email the card when it is issued",
    help: "The holder gets their card as a PDF. Needs email to be on for this space." },
  { key: "public_verify", label: "Public check page",
    help: "A QR on the card opens a page that says whether the card is valid. It never shows the desk code." },
  { key: "verify_show_plan", label: "Show the plan on the check page", help: "Off shows only that the person is a member." },
  { key: "design_approval_required", label: "Design changes need approval",
    help: "Staff who are not Space Managers submit design changes; a Space Manager approves them." },
];

export function SettingsTab({ makerspaceId }: { makerspaceId: number }) {
  const settings = useMemberCardSettings(makerspaceId);
  const save = useSaveMemberCardSettings(makerspaceId);
  if (settings.isLoading) return <Skeleton className="h-48 w-full" />;
  if (settings.isError || !settings.data) return <ErrorBlock error={settings.error} resource="card settings" onRetry={() => void settings.refetch()} />;
  const values: MemberCardSettings = settings.data;
  return <div className="grid max-w-2xl gap-3">
    {save.error ? <ErrorBlock error={save.error} /> : null}
    <ul className="grid gap-2">
      {ROWS.map((row) => {
        const disabled = save.isPending || (row.key === "email_on_issue" && !values.email_available)
          || (row.key === "verify_show_plan" && !values.public_verify);
        return <li key={row.key} className="rounded-control border border-line bg-panel p-3">
          <label className="flex min-h-11 items-start gap-3">
            <input type="checkbox" className="mt-1 h-5 w-5" checked={values[row.key]} disabled={disabled}
              onChange={(event) => save.mutate({ [row.key]: event.target.checked })} />
            <span className="grid gap-1"><span className="text-sm font-semibold text-ink">{row.label}</span>
              <span className="text-xs text-muted">{row.help}
                {row.key === "email_on_issue" && !values.email_available ? " Email is off for this space." : ""}</span></span>
          </label>
        </li>;
      })}
    </ul>
    <p className="text-xs text-muted">The member number and its pattern are set under Membership settings.
      {values.photo_cleanup_available ? " Members can tidy their photo's background on the server." : ""}
      {values.wallet_platforms.length ? ` Wallet passes: ${values.wallet_platforms.join(", ")}.` : ""}</p>
  </div>;
}
