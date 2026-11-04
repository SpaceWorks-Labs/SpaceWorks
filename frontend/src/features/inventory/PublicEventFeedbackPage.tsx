import { PublicLayout, CenteredCardLayout } from "../../components/layouts";
import { publicPageChrome } from "./PublicPageChrome";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { Card } from "../../components/ui";
import { getAccessToken, refreshAccessToken, StructuredApiError, tenantPublicRequest } from "../../lib/api";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { useTenantBranding } from "../../lib/useTenantBranding";
import { useTenantBootstrap } from "./usePublicInventory";
import { EventFeedbackFields } from "../events/programme/EventFeedbackFields";
import { customAnswerErrors, validateCustomAnswers, type CustomAnswers, type CustomFormQuestion } from "../forms/customFormTypes";

type FeedbackForm = {
  event: { title: string; starts_at: string; ends_at: string };
  survey: { title: string; thank_you_text: string; questions: CustomFormQuestion[] };
  mode: "anonymous" | "certificate" | "identified";
  requires_auth: boolean;
  certificate: { id: number; status: string; revision: number } | null;
};

function feedbackPath(slug: string, token: string) {
  return `/public/${encodeURIComponent(slug)}/events/${encodeURIComponent(token)}/feedback/`;
}

export function PublicEventFeedbackPage() {
  const { slug, publicToken = "" } = useParams();
  const tenant = useTenant();
  const makerspaceSlug = tenant.mode === "single" ? tenant.slug : slug ?? "";
  const bootstrapQuery = useTenantBootstrap(makerspaceSlug, tenant.mode === "central");
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const brandStyle = useTenantBranding(bootstrap);
  const tenantPath = useTenantPath(makerspaceSlug);
  const client = useQueryClient();
  const path = feedbackPath(makerspaceSlug, publicToken);
  const [answers, setAnswers] = useState<CustomAnswers>({});
  const [email, setEmail] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [restored, setRestored] = useState(Boolean(getAccessToken()));
  const form = useQuery({
    queryKey: ["public-event-feedback", makerspaceSlug, publicToken],
    queryFn: () => tenantPublicRequest<FeedbackForm>(makerspaceSlug, path),
  });
  useEffect(() => {
    if (form.data?.requires_auth && !restored) refreshAccessToken().then(setRestored);
  }, [form.data?.requires_auth, restored]);
  const submit = useMutation({
    mutationFn: () => tenantPublicRequest<{ thank_you_text: string; certificate: FeedbackForm["certificate"] }>(makerspaceSlug, path, {
      method: "POST", body: JSON.stringify({ answers, ...(form.data?.mode === "certificate" ? { email } : {}) }),
    }),
    onSuccess: async () => {
      setAnswers({}); setEmail(""); setErrors({});
      await client.invalidateQueries({ queryKey: ["public-event-feedback", makerspaceSlug, publicToken] });
    },
  });
  const apiErrors = submit.error instanceof StructuredApiError ? submit.error.body.answers : undefined;

  if (form.error || (!form.isLoading && !form.data)) return <div style={brandStyle}><CenteredCardLayout state={{ status: "ready" }} title="Feedback unavailable" body="This survey is closed, the event has not ended yet, or the link is invalid." primary={{ label: "Back to events", href: tenantPath("events") }} /></div>;
  if (submit.data) return <div style={brandStyle}><CenteredCardLayout state={{ status: "ready" }} media={{ icon: "CheckCircle", tone: "success" }} title="Thank you"
    body={<>{submit.data.thank_you_text || "Your response was recorded."}{submit.data.certificate ? <p className="mt-3">Your certificate is being prepared. Download it from Member activity.</p> : null}</>}
    primary={{ label: "Open member area", href: tenantPath("member") }} /></div>;
  const data = form.data;
  const name = bootstrap?.branding.display_name || bootstrap?.makerspace.name || "Makerspace";
  return <div style={brandStyle}><PublicLayout {...publicPageChrome(makerspaceSlug, name, tenantPath, bootstrap)} width="narrow"
    header={{ eyebrow: data?.event.title, title: data?.survey.title ?? "Event feedback", subtitle: data?.mode === "anonymous" ? "We don't store who sent this." : data?.mode === "identified" ? "Sign in so the organisers know this came from an attendee." : "Certificates go to people marked as attended." }}
    state={form.isLoading ? { status: "loading" } : { status: "ready" }}>
    {data ? <>
      {data.requires_auth && !restored ? <Card><p>{data.mode === "certificate" ? "Sign in to get your certificate." : "Sign in to share your feedback."}</p><Link className="desk-button-brand mt-3" to={tenantPath("member")}>Member sign in</Link></Card> : null}
      <form className="desk-panel mt-5 grid gap-5 p-5" onSubmit={event => { event.preventDefault(); const next = validateCustomAnswers(data.survey.questions, answers); setErrors(next); if (!Object.keys(next).length) submit.mutate(); }}>
        <EventFeedbackFields schema={data.survey.questions} answers={answers} onChange={setAnswers} errors={{ ...errors, ...customAnswerErrors(apiErrors) }} yesNoAsCheckbox />
        {data.mode === "certificate" ? <label className="grid gap-1"><span className="text-sm font-semibold text-ink">Registration email</span><input className="desk-input" type="email" required value={email} onChange={event => setEmail(event.target.value)} /></label> : null}
        <button className="desk-button-brand" type="submit" disabled={submit.isPending || (data.requires_auth && !restored)}>{submit.isPending ? "Submitting…" : "Submit feedback"}</button>
        {submit.error ? <p className="text-sm text-danger" role="alert">{submit.error.message}</p> : null}
      </form>
    </> : null}
  </PublicLayout></div>;
}
