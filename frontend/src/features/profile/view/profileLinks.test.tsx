import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AccountProfile } from "../accountProfileTypes";
import { safeProfileHref } from "../profileFormat";
import { AchievementsSection } from "./ResumeSections";
import { LinksSection, ProjectsSection } from "./WorkSections";

const HOSTILE = ["javascript:alert(1)", "JaVaScRiPt:alert(1)", "data:text/html,<script>alert(1)</script>",
  "http://plain.example", "https://user:pw@evil.example", " https://evil.example", "https://a.example/\u0000", "/relative", "//evil.example"];

// Rows that skipped the server serializer (tenant import, a /control/ edit) can carry any string.
const profile = (overrides: Partial<AccountProfile>) => ({
  shown: { links: true, projects: true, achievements: true }, audience: "member",
  links: [], projects: [], achievements: { verified: [], self_reported: [] }, ...overrides,
}) as unknown as AccountProfile;

describe("profile links are https-only hrefs (SECURITY-REVIEW L-F1)", () => {
  it("keeps absolute https links and refuses every other scheme or shape", () => {
    expect(safeProfileHref("https://maker.example/portfolio")).toBe("https://maker.example/portfolio");
    for (const value of [...HOSTILE, null, undefined, ""]) expect(safeProfileHref(value)).toBeUndefined();
  });

  it("drops hostile links and renders the safe one", () => {
    render(<LinksSection profile={profile({ links: [...HOSTILE, "https://github.com/maker"].map(url => ({ kind: "", url })) } as Partial<AccountProfile>)} />);
    const anchors = screen.getAllByRole("link");
    expect(anchors.map(a => a.getAttribute("href"))).toEqual(["https://github.com/maker"]);
  });

  it("renders nothing when every link is hostile", () => {
    const { container } = render(<LinksSection profile={profile({ links: HOSTILE.map(url => ({ kind: "", url })) } as Partial<AccountProfile>)} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("filters project links the same way", () => {
    const project = { id: 1, title: "Robot", subtitle: "", description: "", tags: [], image_url: "", imported: false, public_visible: true,
      links: [{ label: "Evil", url: "javascript:alert(1)" }, { label: "Repo", url: "https://git.example/robot" }] };
    render(<ProjectsSection profile={profile({ projects: [project] } as unknown as Partial<AccountProfile>)} />);
    expect(screen.queryByText(/Evil/)).toBeNull();
    expect(screen.getByRole("link", { name: /Repo/ })).toHaveAttribute("href", "https://git.example/robot");
  });

  it("shows a self-reported achievement with a hostile url as plain text", () => {
    const own = [{ id: 1, title: "Won a thing", url: "javascript:alert(1)", issuer: "", achieved_on: null, description: "" },
      { id: 2, title: "Spoke", url: "https://talk.example/1", issuer: "", achieved_on: null, description: "" }];
    render(<AchievementsSection profile={profile({ achievements: { verified: [], self_reported: own } } as unknown as Partial<AccountProfile>)} />);
    expect(screen.getByText("Won a thing").closest("a")).toBeNull();
    expect(screen.getByRole("link", { name: "Spoke" })).toHaveAttribute("href", "https://talk.example/1");
  });
});
