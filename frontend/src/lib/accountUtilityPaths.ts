/** These routes use the personal account even on a tenant URL. */
export function isAccountUtilityPath(pathname: string) {
  return /^\/(?:m\/[^/]+\/)?member\/account\/(?:saved-details|security-activity)\/?$/.test(pathname);
}
