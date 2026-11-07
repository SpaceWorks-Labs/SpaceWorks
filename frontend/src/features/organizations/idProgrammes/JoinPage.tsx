// /o/:organizationSlug/ids/:programmeSlug — ask to join an ID programme. Needs a signed-in
// account (the email comes from it); photo upload with consent when the programme asks for one,
// cropped to the card's photo frame first; answers can be filled from Saved details on request.
import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { CenteredCardLayout } from "../../../components/layouts";
import { PhotoPicker } from "../../../components/photo-crop/PhotoPicker";
import { ErrorText } from "../../../components/ui";
import { memberRequest, publicV1Request } from "../../../lib/api";
import { MemberAuthPanel } from "../../members/MemberAuthPanel";

type JoinQuestion = { key: string; label: string; type: "text" | "choice" | "email" | "phone"; required: boolean; options?: string[];
  prefill?: boolean };
type PublicProgramme = { name: string; slug: string; description: string; organization_name: string;
  photo_mode: "none" | "optional" | "required"; requires_approval: boolean; registration_open: boolean; questions: JoinQuestion[];
  state: "signed_out" | "open" | "closed" | "waiting" | "approved" | "not_approved" | "revoked" };
type Presign = { object_key: string; url: string; fields?: Record<string, string>; method?: string; headers?: Record<string, string> };

const STATE_COPY: Record<string, { title: string; body: string }> = {
  waiting: { title: t`Waiting for approval`, body: t`We'll email you when the organiser decides.` },
  approved: { title: t`Approved — see your card`, body: t`Your card is in My cards.` },
  not_approved: { title: t`Not approved`, body: t`The organiser didn't approve this request.` },
  revoked: { title: t`Card revoked`, body: t`Ask the organiser if you think this is a mistake.` },
  closed: { title: t`Closed`, body: t`This programme isn't taking new people right now.` },
};

function useNoIndex() {
  useEffect(() => {
    const meta = Object.assign(document.createElement("meta"), { name: "robots", content: "noindex" });
    document.head.append(meta);
    return () => meta.remove();
  }, []);
}

export function JoinPage() {
  const { organizationSlug = "", programmeSlug = "" } = useParams();
  useNoIndex();
  const base = `/public/organizations/${organizationSlug}/id-programmes/${programmeSlug}`;
  const programme = useQuery({ queryKey: ["id-programme-join", organizationSlug, programmeSlug], retry: false,
    queryFn: () => publicV1Request<PublicProgramme>(base) });
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [photo, setPhoto] = useState<Blob | null>(null);
  const [filled, setFilled] = useState<number | null>(null);
  // Opt-in: Saved details are read only when the person presses the button, and only kept in this form.
  const prefill = useMutation({ mutationFn: () => memberRequest<{ values: Record<string, string> }>(`${base}/prefill`),
    onSuccess: ({ values }) => {
      setAnswers((current) => ({ ...current, ...Object.fromEntries(Object.entries(values).filter(([key]) => !(current[key] ?? "").trim())) }));
      setFilled(Object.keys(values).length);
    } });
  const [consent, setConsent] = useState(false);
  const join = useMutation({ mutationFn: async () => {
    let photoKey = "";
    if (photo) {
      const presign = await memberRequest<Presign>(`${base}/join/photo`, { method: "POST", body: JSON.stringify({ content_type: photo.type || "image/jpeg" }) });
      const form = new FormData();
      Object.entries(presign.fields ?? {}).forEach(([key, value]) => form.append(key, value));
      form.append("file", photo);
      const upload = presign.method === "PUT" ? await fetch(presign.url, { method: "PUT", body: photo, headers: presign.headers })
        : await fetch(presign.url, { method: "POST", body: form });
      if (!upload.ok) throw new Error(t`Upload failed (${upload.status})`);
      photoKey = presign.object_key;
    }
    return memberRequest<{ state: string }>(`${base}/join`, { method: "POST",
      body: JSON.stringify({ answers, photo_object_key: photoKey, photo_consent: Boolean(photo) && consent }) });
  }, onSuccess: () => void programme.refetch() });

  const data = programme.data;
  if (data?.state === "signed_out") return <MemberAuthPanel onAuthenticated={() => { void programme.refetch(); }} />;
  if (!data) return <CenteredCardLayout state={programme.isLoading ? { status: "loading" } : { status: "ready" }}
    title={t`We can't find this programme`} body={t`The link may be wrong, or the programme has closed.`} primary={{ label: t`Home`, href: "/" }} />;
  const done = STATE_COPY[data.state];
  if (done) return <CenteredCardLayout state={{ status: "ready" }} eyebrow={data.organization_name} title={done.title} body={done.body}
    primary={data.state === "approved" ? { label: t`Open My cards`, href: "/member/cards" } : { label: t`Home`, href: "/" }} />;
  const missing = data.questions.some((question) => question.required && !(answers[question.key] ?? "").trim())
    || (data.photo_mode === "required" && !photo) || (Boolean(photo) && !consent);

  return <CenteredCardLayout state={{ status: "ready" }} width="wide" eyebrow={data.organization_name} title={data.name}
    body={data.description || (data.requires_approval ? t`The organiser approves each request.` : t`Your card is issued straight away.`)}
    content={<form className="grid gap-3" onSubmit={(event) => { event.preventDefault(); join.mutate(); }}>
      {data.questions.some((question) => question.prefill) ? <div className="flex flex-wrap items-center gap-2">
        <button type="button" className="desk-button-ghost min-h-11" disabled={prefill.isPending} onClick={() => prefill.mutate()}>
          {prefill.isPending ? t`Filling…` : t`Fill from my Saved details`}</button>
        <span role="status" aria-live="polite" className="text-xs text-muted">{filled === null ? t`Only fills empty answers; check them before sending.`
          : filled ? t`Filled ${filled} answer${filled === 1 ? "" : "s"}. Check them before sending.` : t`Nothing in your Saved details matches these questions.`}</span>
      </div> : null}
      {data.questions.map((question) => <label key={question.key} className="grid gap-1 text-sm font-semibold text-ink">
        <span>{question.label}{question.required ? "" : " (optional)"}</span>
        {question.type === "choice" ? <select className="desk-input min-h-11" value={answers[question.key] ?? ""} required={question.required}
          onChange={(event) => setAnswers({ ...answers, [question.key]: event.target.value })}>
          <option value="">{t`Choose…`}</option>{(question.options ?? []).map((option) => <option key={option}>{option}</option>)}</select>
          : <input className="desk-input min-h-11" type={question.type === "email" ? "email" : question.type === "phone" ? "tel" : "text"}
            required={question.required} value={answers[question.key] ?? ""} maxLength={200}
            onChange={(event) => setAnswers({ ...answers, [question.key]: event.target.value })} />}
      </label>)}
      {data.photo_mode !== "none" ? <div className="grid gap-2">
        <p className="text-sm font-semibold text-ink">{t`Photo${data.photo_mode === "optional" ? " (optional)" : ""}`}</p>
        <PhotoPicker aspect={18 / 22} chooseLabel={photo ? "Change the photo" : "Choose a photo"} onPhoto={setPhoto} />
        {photo ? <p className="text-xs text-muted">{t`Photo cropped and ready. It is only uploaded when you send this request.`}</p> : null}
        {photo ? <label className="flex min-h-11 items-center gap-2 text-sm text-ink"><input type="checkbox" className="h-5 w-5" checked={consent}
          onChange={(event) => setConsent(event.target.checked)} />{t`I agree my photo is stored privately and printed on my card.`}</label> : null}
      </div> : null}
      {join.error || prefill.error ? <ErrorText message={(join.error ?? prefill.error)?.message} /> : null}
      <div><button type="submit" className="desk-button-primary min-h-11" disabled={missing || join.isPending}>
        {join.isPending ? t`Sending…` : t`Ask to join`}</button></div>
    </form>}
    primary={{ label: t`Home`, href: "/" }} />;
}
