import type { ReactNode } from "react";
import { MakerspaceBrand } from "../MakerspaceBrand";
import { SpaceWorksLogo } from "../SpaceWorksLogo";
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
export function AuthLayout({ brand, eyebrow, title, modeSwitch, social, dividerLabel = "or with email", form, legal,
  standalone = true, width, ...query }: AuthLayoutProps) {
  return <LayoutFrame standalone={standalone} width={width}>
    <div className="sw-auth">
      <div className="flex min-w-0 flex-col">
        <a href="/" aria-label="Open makerspace listing" className="mb-6 inline-flex self-start rounded-control focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
          <SpaceWorksLogo variant="stacked" size={180} />
        </a>
        <div className="sw-auth-form min-w-0 py-6">
        {brand.tenant ? <div className="mb-6"><MakerspaceBrand name={brand.tenant.name} logoUrl={brand.tenant.logo} /></div> : null}
        <PageHeader eyebrow={eyebrow} title={title} />
        <QueryContent {...query}>
          <div className="grid gap-6">
            {modeSwitch ? <SegmentedControl {...modeSwitch} /> : null}
            {social ? <><div className="grid gap-3">{social}</div><p className="flex items-center gap-3 text-center text-sm text-muted">
              <span className="h-px flex-1 bg-line" />{dividerLabel}<span className="h-px flex-1 bg-line" /></p></> : null}
            {form}
            {legal ? <div className="text-sm text-muted">{legal}</div> : null}
          </div>
        </QueryContent>
        </div>
      </div>
      <aside aria-label="Space Works" className="sw-auth-brand min-w-0 flex-col justify-center rounded-[28px] bg-accent-soft p-6 xl:p-10">
        <div className="hidden xl:block"><SpaceWorksLogo variant="stacked" size={240} /></div>
        <p className="max-w-lg break-words font-accent text-xl text-ink xl:mt-8 xl:text-4xl">{brand.headline ?? "Less searching. More making."}</p>
        {brand.showcase ? <div aria-hidden="true" inert className="sw-auth-showcase relative mt-10 hidden min-w-0 xl:grid xl:gap-4 [&>*]:shadow-overlay">{brand.showcase}</div> : null}
      </aside>
    </div>
  </LayoutFrame>;
}
