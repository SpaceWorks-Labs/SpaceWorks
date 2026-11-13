import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render as rtlRender, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { describe, expect, it } from "vitest";

import { ActivityFields } from "../edit/ActivityFields";
import type { ProfileDraft } from "../edit/profileDraft";
import { GitHubIdentity } from "./GitHubIdentity";

const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
const wrap = (node: ReactElement) => <QueryClientProvider client={client}>{node}</QueryClientProvider>;
const render = (node: ReactElement) => { const result = rtlRender(wrap(node)); return { ...result, rerender: (next: ReactElement) => result.rerender(wrap(next)) }; };

describe("GitHub ownership (decision 338, L-P4)", () => {
  it("shows the badge only for a verified username", () => {
    const { rerender } = render(<GitHubIdentity username="octocat" verified />);
    expect(screen.getByTestId("github-badge")).toBeTruthy();
    rerender(<GitHubIdentity username="octocat" verified={false} />);
    expect(screen.queryByTestId("github-badge")).toBeNull();
    expect(screen.getByRole("link").getAttribute("href")).toBe("https://github.com/octocat");
  });

  it("refuses a username that is not a GitHub login", () => {
    const { container } = render(<GitHubIdentity username="evil/../x" verified={false} />);
    expect(container.innerHTML).toBe("");
  });

  it("tells the owner an unverified username is unverified, and says nothing once verified", () => {
    const draft = { github: "octocat" } as unknown as ProfileDraft;
    const { rerender } = render(<ActivityFields draft={draft} onChange={() => {}} savedGithub="octocat" />);
    expect(screen.getByTestId("github-unverified")).toBeTruthy();
    rerender(<ActivityFields draft={draft} onChange={() => {}} savedGithub="octocat" githubVerified />);
    expect(screen.queryByTestId("github-unverified")).toBeNull();
  });
});
