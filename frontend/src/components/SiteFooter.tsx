import { SupportContact } from "./SupportContact";
import { Link } from "react-router-dom";
import { SpaceWorksLogo } from "./SpaceWorksLogo";

// Shared public footer: copyright + a link out to the in-app About page.
export function SiteFooter({ branding }: { branding?: Record<string, string> }) {
  const year = new Date().getFullYear();
  return (
    <footer className="mt-auto border-t border-line bg-panel">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-5 py-5 text-xs text-muted">
        <Link to="/" className="inline-flex items-center gap-2 rounded-control hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
          <SpaceWorksLogo variant="symbol" size={48} decorative />
          <span>&copy; {year} Space Works &mdash; Open Source Makerspace Manager</span>
        </Link>
        <SupportContact branding={branding} />
        <nav className="flex items-center gap-4">
          <Link className="hover:text-ink" to="/about">
            About
          </Link>
          <a
            className="hover:text-ink"
            href="https://github.com/SpaceWorks-HQ/SpaceWorks/blob/main/LICENSE"
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
