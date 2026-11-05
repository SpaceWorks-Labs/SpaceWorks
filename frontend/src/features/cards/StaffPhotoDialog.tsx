// Staff take or upload a holder's card photo at the desk (X25). The consent rule holds for
// staff too: the photo is only attached once staff confirm the holder agreed to it being
// stored and printed. The photo is cropped to the card's frame before upload.
import { useState } from "react";

import { PhotoPicker } from "../../components/photo-crop/PhotoPicker";
import { ErrorText, Modal } from "../../components/ui";
import { staffRequest } from "../../lib/api";

type Presign = { object_key: string; url: string; fields?: Record<string, string>; method?: string; headers?: Record<string, string> };

/** Presign the staging upload, send the bytes to private storage, then attach with the holder's consent. */
export async function uploadStaffCardPhoto(photoPath: string, photo: Blob) {
  const type = photo.type || "image/jpeg";
  const presign = await staffRequest<Presign>(photoPath, { method: "POST", body: JSON.stringify({ content_type: type }) });
  const upload = presign.method === "PUT"
    ? await fetch(presign.url, { method: "PUT", body: photo, headers: presign.headers })
    : await fetch(presign.url, { method: "POST", body: (() => {
      const form = new FormData();
      Object.entries(presign.fields ?? {}).forEach(([key, value]) => form.append(key, value));
      form.append("file", photo);
      return form;
    })() });
  if (!upload.ok) throw new Error(`Upload failed (${upload.status})`);
  return staffRequest<{ photo_set: boolean }>(photoPath, { method: "PUT",
    body: JSON.stringify({ object_key: presign.object_key, content_type: type, holder_consented: true }) });
}

export function StaffPhotoDialog({ holderName, photoPath, aspect = 18 / 22, onClose, onSaved }: {
  holderName: string | null; photoPath: string; aspect?: number; onClose: () => void; onSaved: () => void;
}) {
  const [consent, setConsent] = useState(false);
  const [state, setState] = useState<{ busy: boolean; error: string | null }>({ busy: false, error: null });
  const close = () => { setConsent(false); setState({ busy: false, error: null }); onClose(); };
  async function upload(photo: Blob) {
    setState({ busy: true, error: null });
    try {
      await uploadStaffCardPhoto(photoPath, photo);
      setState({ busy: false, error: null });
      setConsent(false);
      onSaved();
    } catch (error) {
      setState({ busy: false, error: error instanceof Error ? error.message : "The photo couldn't be saved." });
    }
  }
  return <Modal open={holderName !== null} onClose={close} title={`Card photo for ${holderName ?? ""}`}
    footer={<div className="flex justify-end"><button type="button" className="desk-button min-h-11" onClick={close}>Close</button></div>}>
    <div className="grid gap-3">
      <p className="text-sm text-muted">Take the photo at the desk or choose one they sent you. It replaces any photo on the card
        and answers an open photo request.</p>
      <label className="flex min-h-11 items-start gap-2 text-sm text-ink"><input type="checkbox" className="mt-0.5 h-5 w-5"
        checked={consent} onChange={(event) => setConsent(event.target.checked)} />
        <span>{holderName} agreed to this photo being stored privately and printed on their card.</span></label>
      <PhotoPicker aspect={aspect} disabled={!consent} busy={state.busy} onPhoto={(photo) => void upload(photo)} />
      {state.error ? <ErrorText message={state.error} /> : null}
    </div>
  </Modal>;
}
