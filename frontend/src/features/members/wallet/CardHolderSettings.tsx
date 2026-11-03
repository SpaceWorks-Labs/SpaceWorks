// The holder's own card settings: what the public check page may show, the optional extras
// (blood group, emergency contact — printed on your card and seen by you only), a new check
// link, and the card photo (uploaded with consent).
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { ErrorText } from "../../../components/ui";
import { myCardsKey, uploadCardPhoto, useCardSettings, useRotateCheckLink, useSaveCardSettings,
  type CardSettings, type MyCard } from "./api";

const BLOOD_GROUPS = ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];

export function CardHolderSettings({ card }: { card: MyCard }) {
  const settings = useCardSettings(card, true);
  const save = useSaveCardSettings(card);
  const rotate = useRotateCheckLink(card);
  const client = useQueryClient();
  const [draft, setDraft] = useState<CardSettings | null>(null);
  const [consent, setConsent] = useState(false);
  const [photo, setPhoto] = useState<{ busy: boolean; error: string | null; done: boolean }>({ busy: false, error: null, done: false });
  useEffect(() => { if (settings.data) setDraft(settings.data); }, [settings.data]);
  if (settings.error) return <ErrorText message={settings.error.message} />;
  if (!draft) return <p className="text-sm text-muted">Loading…</p>;
  const set = <K extends keyof CardSettings>(key: K, value: CardSettings[K]) => setDraft({ ...draft, [key]: value });
  const toggle = (key: "verify_show_name" | "verify_show_photo" | "extras_opted_in", text: string) =>
    <label className="flex min-h-11 items-center gap-2 text-sm text-ink">
      <input type="checkbox" className="h-5 w-5" checked={draft[key]} onChange={(event) => set(key, event.target.checked)} />{text}</label>;

  return <div className="grid gap-4 border-t border-line pt-4">
    {draft.public_check_on ? <fieldset className="grid gap-1"><legend className="text-sm font-semibold text-ink">Public check page</legend>
      {toggle("verify_show_name", "Show my name")}{toggle("verify_show_photo", "Show my photo")}
      <button type="button" className="desk-button-ghost min-h-11 w-fit" disabled={rotate.isPending} onClick={() => rotate.mutate()}>
        {rotate.isSuccess ? "New link made — reprint your card" : "Make a new check link"}</button>
      <p className="text-xs text-muted">A new link stops the old QR on printed cards from working.</p>
    </fieldset> : null}
    <fieldset className="grid gap-2"><legend className="text-sm font-semibold text-ink">Emergency details on my card</legend>
      {toggle("extras_opted_in", "Print these on my card (you see them; organisers don't)")}
      {draft.extras_opted_in ? <div className="grid gap-2 sm:grid-cols-3">
        <label className="grid gap-1 text-xs font-semibold text-muted"><span>Blood group</span>
          <select className="desk-input min-h-11" value={draft.blood_group} onChange={(event) => set("blood_group", event.target.value)}>
            {BLOOD_GROUPS.map((value) => <option key={value} value={value}>{value || "Not set"}</option>)}</select></label>
        <label className="grid gap-1 text-xs font-semibold text-muted"><span>Emergency contact</span>
          <input className="desk-input min-h-11" maxLength={80} value={draft.emergency_contact_name}
            onChange={(event) => set("emergency_contact_name", event.target.value)} /></label>
        <label className="grid gap-1 text-xs font-semibold text-muted"><span>Their phone</span>
          <input className="desk-input min-h-11" type="tel" maxLength={32} value={draft.emergency_contact_phone}
            onChange={(event) => set("emergency_contact_phone", event.target.value)} /></label>
      </div> : null}
    </fieldset>
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" className="desk-button-primary min-h-11" disabled={save.isPending} onClick={() => {
        const { public_check_on: _ignored, ...patch } = draft;
        save.mutate(patch, { onSuccess: () => void client.invalidateQueries({ queryKey: ["member", "card-image"] }) });
      }}>{save.isPending ? "Saving…" : "Save"}</button>
      {save.isSuccess ? <span role="status" className="text-sm text-success">Saved.</span> : null}
    </div>
    {save.error ? <ErrorText message={save.error.message} /> : null}
    {card.kind === "member_card" ? <p className="text-xs text-muted">Change your member card photo from your member card in the member area.</p> : null}
    {card.kind !== "member_card" ? <fieldset className="grid gap-2"><legend className="text-sm font-semibold text-ink">Card photo</legend>
      <label className="flex min-h-11 items-center gap-2 text-sm text-ink"><input type="checkbox" className="h-5 w-5" checked={consent}
        onChange={(event) => setConsent(event.target.checked)} />I agree my photo is stored privately and printed on this card.</label>
      <label className={`desk-button min-h-11 w-fit cursor-pointer ${!consent || photo.busy ? "pointer-events-none opacity-60" : ""}`}>
        {photo.busy ? "Uploading…" : "Choose or take a photo"}
        <input type="file" accept="image/png,image/jpeg,image/webp" capture="user" className="sr-only" disabled={!consent || photo.busy}
          onChange={async (event) => {
            const file = event.target.files?.[0]; event.target.value = "";
            if (!file) return;
            setPhoto({ busy: true, error: null, done: false });
            try {
              await uploadCardPhoto(card, file);
              setPhoto({ busy: false, error: null, done: true });
              await client.invalidateQueries({ queryKey: myCardsKey });
              await client.invalidateQueries({ queryKey: ["member", "card-image"] });
            } catch (error) {
              setPhoto({ busy: false, error: error instanceof Error ? error.message : "The photo couldn't be uploaded.", done: false });
            }
          }} /></label>
      {photo.done ? <p role="status" className="text-sm text-success">Photo saved.</p> : null}
      {photo.error ? <ErrorText message={photo.error} /> : null}
    </fieldset> : null}
  </div>;
}
