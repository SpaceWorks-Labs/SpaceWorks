// /o/:organizationSlug/ids/:programmeSlug — ask to join an ID programme. Needs a signed-in
// account (the email comes from it); photo upload with consent when the programme asks for one.
import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { CenteredCardLayout } from "../../../components/layouts";
import { ErrorText } from "../../../components/ui";
import { memberRequest, publicV1Request } from "../../../lib/api";
import { MemberAuthPanel } from "../../members/MemberAuthPanel";

type JoinQuestion = { key: string; label: string; type: "text" | "choice" | "email" | "phone"; required: boolean; options?: string[] };
type PublicProgramme = { name: string; slug: string; description: string; organization_name: string;
  photo_mode: "none" | "optional" | "required"; requires_approval: boolean; registration_open: boolean; questions: JoinQuestion[];
  state: "signed_out" | "open" | "closed" | "waiting" | "approved" | "not_approved" | "revoked" };
type Presign = { object_key: string; url: string; fields?: Record<string, string>; method?: string; headers?: Record<string, string> };

const STATE_COPY: Record<string, { title: string; body: string }> = {
  waiting: { title: "Waiting for approval", body: "We'll email you when the organiser decides." },
  approved: { title: "Approved — see your card", body: "Your card is in My cards." },
  not_approved: { title: "Not approved", body: "The organiser didn't approve this request." },
  revoked: { title: "Card revoked", body: "Ask the organiser if you think this is a mistake." },
  closed: { title: "Closed", body: "This programme isn't taking new people right now." },
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
  const [photo, setPhoto] = useState<File | null>(null);
  const [consent, setConsent] = useState(false);
  const join = useMutation({ mutationFn: async () => {
    let photoKey = "";
    if (photo) {
      const presign = await memberRequest<Presign>(`${base}/join/photo`, { method: "POST", body: JSON.stringify({ content_type: photo.type }) });
      const form = new FormData();
      Object.entries(presign.fields ?? {}).forEach(([key, value]) => form.append(key, value));
      form.append("file", photo);
      const upload = presign.method === "PUT" ? await fetch(presign.url, { method: "PUT", body: photo, headers: presign.headers })
        : await fetch(presign.url, { method: "POST", body: form });
      if (!upload.ok) throw new Error(`Upload failed (${upload.status})`);
      photoKey = presign.object_key;
    }
    return memberRequest<{ state: string }>(`${base}/join`, { method: "POST",
      body: JSON.stringify({ answers, photo_object_key: photoKey, photo_consent: Boolean(photo) && consent }) });
  }, onSuccess: () => void programme.refetch() });

  const data = programme.data;
  if (data?.state === "signed_out") return <MemberAuthPanel onAuthenticated={() => { void programme.refetch(); }} />;
  if (!data) return <CenteredCardLayout state={programme.isLoading ? { status: "loading" } : { status: "ready" }}
    title="We can't find this programme" body="The link may be wrong, or the programme has closed." primary={{ label: "Home", href: "/" }} />;
  const done = STATE_COPY[data.state];
  if (done) return <CenteredCardLayout state={{ status: "ready" }} eyebrow={data.organization_name} title={done.title} body={done.body}
    primary={data.state === "approved" ? { label: "Open My cards", href: "/member/cards" } : { label: "Home", href: "/" }} />;
  const missing = data.questions.some((question) => question.required && !(answers[question.key] ?? "").trim())
    || (data.photo_mode === "required" && !photo) || (Boolean(photo) && !consent);

  return <CenteredCardLayout state={{ status: "ready" }} width="wide" eyebrow={data.organization_name} title={data.name}
    body={data.description || (data.requires_approval ? "The organiser approves each request." : "Your card is issued straight away.")}
    content={<form className="grid gap-3" onSubmit={(event) => { event.preventDefault(); join.mutate(); }}>
      {data.questions.map((question) => <label key={question.key} className="grid gap-1 text-sm font-semibold text-ink">
        <span>{question.label}{question.required ? "" : " (optional)"}</span>
        {question.type === "choice" ? <select className="desk-input min-h-11" value={answers[question.key] ?? ""} required={question.required}
          onChange={(event) => setAnswers({ ...answers, [question.key]: event.target.value })}>
          <option value="">Choose…</option>{(question.options ?? []).map((option) => <option key={option}>{option}</option>)}</select>
          : <input className="desk-input min-h-11" type={question.type === "email" ? "email" : question.type === "phone" ? "tel" : "text"}
            required={question.required} value={answers[question.key] ?? ""} maxLength={200}
            onChange={(event) => setAnswers({ ...answers, [question.key]: event.target.value })} />}
      </label>)}
      {data.photo_mode !== "none" ? <div className="grid gap-2">
        <label className="grid gap-1 text-sm font-semibold text-ink"><span>Photo{data.photo_mode === "optional" ? " (optional)" : ""}</span>
          <input type="file" className="desk-input" accept="image/png,image/jpeg,image/webp" capture="user"
            onChange={(event) => setPhoto(event.target.files?.[0] ?? null)} /></label>
        {photo ? <label className="flex min-h-11 items-center gap-2 text-sm text-ink"><input type="checkbox" className="h-5 w-5" checked={consent}
          onChange={(event) => setConsent(event.target.checked)} />I agree my photo is stored privately and printed on my card.</label> : null}
      </div> : null}
      {join.error ? <ErrorText message={join.error.message} /> : null}
      <div><button type="submit" className="desk-button-primary min-h-11" disabled={missing || join.isPending}>
        {join.isPending ? "Sending…" : "Ask to join"}</button></div>
    </form>}
    primary={{ label: "Home", href: "/" }} />;
}
