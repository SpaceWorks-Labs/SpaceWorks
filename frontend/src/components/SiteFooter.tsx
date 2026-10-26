import { SupportContact } from "./SupportContact";
import { Link } from "react-router-dom";
import { SpaceWorksLogo } from "./SpaceWorksLogo";

// Shared public footer: copyright + a link out to the in-app About page.
export function SiteFooter({ branding }: { branding?: Record<string, string> }) {
  const year = new Date().getFullYear();
  return (
    <footer className="mt-auto border-t border-line bg-panel">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 py-5 pr-[max(1.25rem,env(safe-area-inset-right))] pb-[max(1.25rem,env(safe-area-inset-bottom))] pl-[max(1.25rem,env(safe-area-inset-left))] text-xs text-muted">
        <Link to="/" className="inline-flex items-center gap-2 rounded-control hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
          <SpaceWorksLogo variant="symbol" size={48} decorative />
          <span className="min-w-0">&copy; {year} Space Works &mdash; Open Source Makerspace Manager</span>
        </Link>
        <SupportContact branding={branding} />
        <nav aria-label="Site" className="flex items-center gap-4">
          <Link className="inline-flex min-h-11 items-center rounded-control hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" to="/about">
            About
          </Link>
          <a
            className="inline-flex min-h-11 items-center rounded-control hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
            href="https://github.com/SpaceWorks-Labs/SpaceWorks/blob/main/LICENSE"
            target="_blank"
            rel="noreferrer"
          >
            License
          </a>
        </nav>
      </div>
    </footer>
  );
}
