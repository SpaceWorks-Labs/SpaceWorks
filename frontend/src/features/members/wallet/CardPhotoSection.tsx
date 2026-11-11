// The holder's card photo in "My cards": take or choose a photo, crop it to the card's photo
// frame, upload it with consent, and optionally clean up its background on the server.
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { PhotoPicker } from "../../../components/photo-crop/PhotoPicker";
import { ErrorText } from "../../../components/ui";
import { myCardsKey, uploadCardPhoto, type MyCard } from "./api";
import { PhotoCleanup } from "./PhotoCleanup";

export function CardPhotoSection({ card }: { card: MyCard }) {
  const client = useQueryClient();
  const [consent, setConsent] = useState(false);
  const [state, setState] = useState<{ busy: boolean; error: string | null; done: boolean }>({ busy: false, error: null, done: false });

  async function upload(photo: Blob) {
    setState({ busy: true, error: null, done: false });
    try {
      await uploadCardPhoto(card, photo);
      setState({ busy: false, error: null, done: true });
      await client.invalidateQueries({ queryKey: myCardsKey });
      await client.invalidateQueries({ queryKey: ["member", "card-image"] });
      await client.invalidateQueries({ queryKey: ["member", "card-face"] });
    } catch (error) {
      setState({ busy: false, error: error instanceof Error ? error.message : t`The photo couldn't be uploaded.`, done: false });
    }
  }

  return <fieldset className="grid gap-2"><legend className="text-sm font-semibold text-ink">{t`Card photo`}</legend>
    <p className="text-xs text-muted">{card.photo_set ? t`A photo is on this card.` : t`No photo on this card yet.`}
      {t`${" "}You crop it to the card's photo spot before it is uploaded.`}</p>
    <label className="flex min-h-11 items-center gap-2 text-sm text-ink"><input type="checkbox" className="h-5 w-5" checked={consent}
      onChange={(event) => setConsent(event.target.checked)} />{t`I agree my photo is stored privately and printed on this card.`}</label>
    <PhotoPicker aspect={card.photo_aspect || 18 / 22} disabled={!consent} busy={state.busy}
      chooseLabel={card.photo_set ? t`Change the photo` : t`Choose a photo`} onPhoto={(photo) => void upload(photo)} />
    <p role="status" aria-live="polite" className="text-sm text-success-ink">{state.done ? t`Photo saved.` : ""}</p>
    {state.error ? <ErrorText message={state.error} /> : null}
    <PhotoCleanup card={card} />
  </fieldset>;
}
