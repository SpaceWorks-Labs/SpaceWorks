import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";
import { BrandFacets } from "../BrandFacets";
import { MakerspaceBrand } from "../MakerspaceBrand";
import { AnimatedLogoMark } from "../brand/AnimatedLogoMark";
import { PageHeader, SegmentedControl } from "../ui";
import type { SegmentedControlProps } from "../ui";
import { LayoutFrame, QueryContent } from "./LayoutFrame";
import type { LayoutProps } from "./types";

export type AuthLayoutProps = LayoutProps & {
  brand: { headline?: string; showcase?: ReactNode; tenant?: { name: string; logo?: string } };
  eyebrow?: string;
  title: string;
  modeSwitch?: SegmentedControlProps;
  social?: ReactNode;
  dividerLabel?: string;
  form: ReactNode;
  legal?: ReactNode;
};
/**
 * Split screen. The brand panel is a colour field (styles/fields.css): Deep Ink in
 * light (brand p.1 cover), Maker Teal in dark (p.7 reversed on teal), or the tenant's own brand fill.
 * One logo per screen, in the form column; Space Works facets only on the Space Works panel.
 */
export function AuthLayout({ brand, eyebrow, title, modeSwitch, social, dividerLabel = "or with email", form, legal,
  standalone = true, width, ...query }: AuthLayoutProps) {
  const tenant = brand.tenant;
  return <LayoutFrame standalone={standalone} width={width}>
    <div className="sw-auth">
      <div className="flex min-w-0 flex-col">
        <a href="/" aria-label={t`Space Works — Open makerspace listing`} className="mb-6 inline-flex self-start rounded-control focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
          <span className="inline-flex sm:hidden"><AnimatedLogoMark variant="stacked" size={180} /></span>
          <span className="hidden sm:inline-flex"><AnimatedLogoMark variant="horizontal" size={288} /></span>
        </a>
        <div className="sw-auth-form min-w-0 py-6">
        {tenant ? <div className="mb-6"><MakerspaceBrand name={tenant.name} logoUrl={tenant.logo} /></div> : null}
        <PageHeader eyebrow={eyebrow} title={title} />
        <QueryContent {...query}>
          <div className="grid gap-6">
            {modeSwitch ? <SegmentedControl {...modeSwitch} /> : null}
            {social ? <><div className="grid gap-3 empty:hidden">{social}</div><p className="flex items-center gap-3 text-center text-sm text-muted [:empty+&]:hidden">
              <span className="h-px flex-1 bg-line" />{dividerLabel}<span className="h-px flex-1 bg-line" /></p></> : null}
            {form}
            {legal ? <div className="text-sm text-muted">{legal}</div> : null}
          </div>
        </QueryContent>
        </div>
      </div>
      <aside aria-label={tenant?.name ?? t`Space Works`}
        className={`sw-auth-brand relative min-w-0 flex-col justify-center overflow-hidden rounded-[28px] p-6 xl:p-10 ${tenant ? "sw-field-brand" : "sw-island-dark sw-field-ink"}`}>
        <p className="sw-auth-phrase relative z-10 max-w-lg break-words font-accent text-2xl font-semibold xl:text-5xl xl:leading-[56px] min-[1680px]:text-[64px] min-[1680px]:leading-[72px]">
          {brand.headline ?? t`Less searching. More making.`}</p>
        {brand.showcase ? <div aria-hidden="true" inert className="sw-auth-showcase sw-island-dark relative z-10 mt-10 hidden min-w-0 max-w-md xl:grid xl:gap-4 [&>*]:shadow-overlay">{brand.showcase}</div> : null}
        {tenant ? null : <BrandFacets size="md" className="absolute -bottom-[88px] -right-6 h-auto w-[216px] xl:-bottom-[72px] xl:-right-12 xl:w-[360px] min-[1680px]:w-[440px]" />}
      </aside>
    </div>
  </LayoutFrame>;
}
