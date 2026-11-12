// The holder's own card settings: what the public check page may show, the optional extras
// (blood group, emergency contact — printed on your card and seen by you only), a new check
// link, how the card is emailed (PDF or PNG), and the card photo (cropped, uploaded with consent).
import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { ErrorText } from "../../../components/ui";
import { useCardSettings, useRotateCheckLink, useSaveCardSettings, type CardSettings, type MyCard } from "./api";
import { CardPhotoSection } from "./CardPhotoSection";
import { LogoLoader } from "../../../components/LogoLoader";
import { BoxArt } from "../../../components/BoxSpinner";

const BLOOD_GROUPS = ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];

export function CardHolderSettings({ card }: { card: MyCard }) {
  const settings = useCardSettings(card, true);
  const save = useSaveCardSettings(card);
  const rotate = useRotateCheckLink(card);
  const client = useQueryClient();
  const [draft, setDraft] = useState<CardSettings | null>(null);
  useEffect(() => { if (settings.data) setDraft(settings.data); }, [settings.data]);
  if (settings.error) return <ErrorText message={settings.error.message} />;
  if (!draft) return <LogoLoader label={t`Loading…`} size={48} className="min-h-16 py-3" />;
  const set = <K extends keyof CardSettings>(key: K, value: CardSettings[K]) => setDraft({ ...draft, [key]: value });
  const toggle = (key: "verify_show_name" | "verify_show_photo" | "extras_opted_in", text: string) =>
    <label className="flex min-h-11 items-center gap-2 text-sm text-ink">
      <input type="checkbox" className="h-5 w-5" checked={draft[key]} onChange={(event) => set(key, event.target.checked)} />{text}</label>;

  return <div className="grid gap-4 border-t border-line pt-4">
    {draft.public_check_on ? <fieldset className="grid gap-1"><legend className="text-sm font-semibold text-ink">{t`Public check page`}</legend>
      {toggle("verify_show_name", "Show my name")}{toggle("verify_show_photo", "Show my photo")}
      <button type="button" className="desk-button-ghost min-h-11 w-fit" disabled={rotate.isPending} onClick={() => rotate.mutate()}>
        {rotate.isSuccess ? t`New link made — reprint your card` : t`Make a new check link`}</button>
      <p className="text-xs text-muted">{t`A new link stops the old QR on printed cards from working.`}</p>
    </fieldset> : null}
    <fieldset className="grid gap-2"><legend className="text-sm font-semibold text-ink">{t`Emergency details on my card`}</legend>
      {toggle("extras_opted_in", "Print these on my card (you see them; organisers don't)")}
      {draft.extras_opted_in ? <div className="grid gap-2 sm:grid-cols-3">
        <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Blood group`}</span>
          <select className="desk-input min-h-11" value={draft.blood_group} onChange={(event) => set("blood_group", event.target.value)}>
            {BLOOD_GROUPS.map((value) => <option key={value} value={value}>{value || t`Not set`}</option>)}</select></label>
        <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Emergency contact`}</span>
          <input className="desk-input min-h-11" maxLength={80} value={draft.emergency_contact_name}
            onChange={(event) => set("emergency_contact_name", event.target.value)} /></label>
        <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Their phone`}</span>
          <input className="desk-input min-h-11" type="tel" maxLength={32} value={draft.emergency_contact_phone}
            onChange={(event) => set("emergency_contact_phone", event.target.value)} /></label>
      </div> : null}
    </fieldset>
    {card.email_available ? <label className="grid max-w-xs gap-1 text-xs font-semibold text-muted"><span>{t`Email my card as`}</span>
      <select className="desk-input min-h-11" value={draft.email_format}
        onChange={(event) => set("email_format", event.target.value as CardSettings["email_format"])}>
        <option value="pdf">{t`PDF (prints at the right size)`}</option><option value="png">{t`PNG images (front and back)`}</option></select></label> : null}
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" className="desk-button-primary min-h-11" disabled={save.isPending} onClick={() => {
        const { public_check_on: _ignored, ...patch } = draft;
        save.mutate(patch, { onSuccess: () => { void client.invalidateQueries({ queryKey: ["member", "card-image"] });
          void client.invalidateQueries({ queryKey: ["member", "card-face"] }); } });
      }}>{save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save`}</button>
      {save.isSuccess ? <span role="status" className="text-sm text-success-ink">{t`Saved.`}</span> : null}
    </div>
    {save.error ? <ErrorText message={save.error.message} /> : null}
    <CardPhotoSection card={card} />
  </div>;
}
