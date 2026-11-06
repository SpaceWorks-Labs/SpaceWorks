import { t } from "@lingui/core/macro";
import { useState } from "react";

import { PublicLayout } from "../../components/layouts";
import { ThemeToggle } from "../../components/ThemeToggle";
import { LICENSE_URL } from "../inventory/PublicPageChrome";
import { NotFoundPage } from "../NotFoundPage";
import { useHostingConfig, useSubmitHostingRequest } from "./hostingApi";
import { EMPTY_HOSTING_FORM, HOSTING_ACK, hostingErrorText, hostingFieldErrors, hostingRequestBody, type HostingFormKey } from "./hostingForm";
import { HostingRequestFields } from "./HostingRequestFields";

const STEPS = [
  "Confirm your email.",
  "The platform team reviews your request.",
  "We set up your space and contact you.",
];

/** The one Unbounded accent on this layout is the h1. */
function HostingHero() {
  return <section aria-labelledby="hosting-title" className="mb-8 grid gap-4 md:mb-10">
    <p className="eyebrow">{t`Managed hosting`}</p>
    <h1 id="hosting-title" className="break-words font-accent text-3xl leading-10 font-semibold text-ink sm:text-4xl sm:leading-[48px]">
      {t`Host your makerspace on Space Works`}</h1>
    <p className="max-w-2xl text-base text-muted">
      {t`Tell us about your space. The platform team runs the servers, backups and updates; you run the workshop.`}</p>
  </section>;
}

export function HostingRequestPage() {
  const config = useHostingConfig();
  const submit = useSubmitHostingRequest();
  const [form, setForm] = useState(EMPTY_HOSTING_FORM);
  if (config.data === false) return <NotFoundPage />;

  const errors = hostingFieldErrors(submit.error);
  const set = (key: HostingFormKey, value: string) => setForm((current) => ({ ...current, [key]: value }));
  return <PublicLayout makerspace={{ name: "Space Works", slug: "", homeHref: "/" }} chrome="canvas"
    nav={[{ label: t`Browse spaces`, href: "/" }, { label: t`About`, href: "/about" }]} headerAction={{ label: t`Sign in`, href: "/member" }}
    liveStatus={<ThemeToggle variant="icon" />} width="narrow" hero={<HostingHero />}
    state={config.isError ? { status: "error", error: "Couldn't load this page. Try again.", onRetry: () => { void config.refetch(); } }
      : config.isLoading ? { status: "loading" } : { status: "ready" }}
    footer={{ credit: "Space Works · Made for shared workshops", links: [{ label: t`About`, href: "/about" }, { label: t`License`, href: LICENSE_URL, external: true }] }}>
    <div className="grid gap-8">
      <section aria-labelledby="hosting-next" className="rounded-2xl border border-line bg-panel p-5">
        <h2 id="hosting-next" className="title-section">{t`What happens next`}</h2>
        <ol className="mt-3 grid list-decimal gap-2 pl-5 text-sm text-ink">
          {STEPS.map((step) => <li key={step}>{step}</li>)}
        </ol>
        <p className="mt-4 text-sm text-muted">{t`Details from declined requests are deleted after 90 days.`}</p>
      </section>
      {submit.isSuccess ? <p role="status" className="rounded-xl border border-success bg-success-soft p-4 text-base font-semibold text-success-ink">
        {HOSTING_ACK}
      </p> : <form className="grid gap-5" aria-labelledby="hosting-form-title" onSubmit={(event) => {
        event.preventDefault();
        if (!submit.isPending) submit.mutate(hostingRequestBody(form), { onSuccess: () => setForm(EMPTY_HOSTING_FORM) });
      }}>
        <h2 id="hosting-form-title" className="title-panel">{t`Your request`}</h2>
        <HostingRequestFields value={form} onChange={set} errors={errors} showExpectedMembers />
        {submit.error ? <p role="alert" className="text-sm text-danger">
          {hostingErrorText(submit.error, "Hosting requests aren't open right now.")}
        </p> : null}
        <button className="desk-button-brand w-full sm:w-fit" type="submit" disabled={submit.isPending}>
          {submit.isPending ? t`Sending…` : t`Send request`}
        </button>
      </form>}
    </div>
  </PublicLayout>;
}
