/** Lane L18: the giving pages, routed before the per-mode tables (like programme and card paths). */
export function isDonationPath(pathname: string) {
  return /^(?:\/m\/[^/]+)?\/donate(?:\/(?:gift|pledge|campaign)\/[^/]+)?\/?$/.test(pathname);
}
