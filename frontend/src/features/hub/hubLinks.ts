// Fixed addresses the hub pages link to. Every /docs/<id> link names a page the in-app docs index
// publishes (docs/<folder>/<file>.md -> /docs/<folder>/<file>, an index.md -> its folder);
// hubLinks.test.ts fails if one stops resolving.
export const GITHUB_URL = "https://github.com/SpaceWorks-Labs/SpaceWorks";
/** The native apps' own public repositories (the apps are released; owner, 2026-11-12). */
export const ANDROID_REPO_URL = "https://github.com/SpaceWorks-Labs/SpaceWorks-Android";
export const IOS_REPO_URL = "https://github.com/SpaceWorks-Labs/SpaceWorks-iOS";
/** The apps ship through GitHub Releases only (no Play Store or App Store; owner, 2026-11-12). */
export const ANDROID_RELEASES_URL = `${ANDROID_REPO_URL}/releases/latest`;
export const IOS_RELEASES_URL = `${IOS_REPO_URL}/releases/latest`;
export const LICENSE_URL = `${GITHUB_URL}/blob/main/LICENSE`;
export const ISSUES_URL = `${GITHUB_URL}/issues`;
export const INSTALL_COMMAND = "curl -fsSL https://github.com/SpaceWorks-Labs/SpaceWorks/releases/latest/download/install.sh | sh";
/** The repository VERSION, injected at build time (vite.config.ts `define`), so a release bump needs no edit here. */
export const HUB_VERSION = __SPACEWORKS_VERSION__;
export const LICENSE_SPDX = "AGPL-3.0-or-later";

export const DOCS_LINKS = {
  home: "/docs",
  install: "/docs/install-and-update",
  hosting: "/docs/choose-your-hosting",
  gettingStarted: "/docs/guide/getting-started",
  tutorials: "/docs/tutorials/overview",
  hostingGroup: "/docs/hosting",
  areas: "/docs/modules",
  architecture: "/docs/architecture/overview",
  apiReference: "/docs/api/reference",
  license: "/docs/project/license",
  thirdParty: "/docs/project/third-party",
  securityPolicy: "/docs/project/security-policy",
  contributing: "/docs/project/contributing",
  changelog: "/docs/changelog",
  search: (query: string) => `/docs?q=${encodeURIComponent(query)}`,
} as const;
