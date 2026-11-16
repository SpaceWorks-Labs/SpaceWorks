import { t } from "@lingui/core/macro";

/** Decision 338: the "GitHub" badge marks a username proven to be the owner's linked sign-in; otherwise it is a plain link. */
export function GitHubIdentity({ username, verified }: { username: string; verified: boolean }) {
  if (!username || !/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$/.test(username)) return null;
  return <p className="flex items-center gap-2 text-sm">
    <a className="underline" href={`https://github.com/${username}`} rel="noopener noreferrer nofollow" target="_blank">{username}</a>
    {verified ? <span className="rounded-full border border-border px-2 text-xs" data-testid="github-badge">{t`GitHub`}</span> : null}
  </p>;
}
