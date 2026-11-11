import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { DocsMarkdown } from "./DocsMarkdown";
import type { DocEntry } from "./docsTypes";

const INDEX: DocEntry[] = [{ id: "hosting/docker", source: "hosting/docker.md", group: "Hosting", order: 1, title: "Docker", summary: "", headings: [] }];

const BODY = `Intro with a [Docker link](hosting/docker.md#ports), an [invariant](INVARIANTS.md) and \`inline\`.

## Set up the server

> **Note:** Back up first.

> **Warning** This deletes data.

> [!TIP]
> Use the installer.

> A plain quote.

\`\`\`bash
./install.sh
\`\`\`

\`\`\`powershell
.\\install.ps1
\`\`\`

\`\`\`yaml
key: value
\`\`\`

## Set up the server

| Setting | Default |
| --- | --- |
| PORT | 8000 |

<script>alert(1)</script>
`;

function renderBody() {
  return render(<MemoryRouter><DocsMarkdown body={BODY} source="install-and-update.md" index={INDEX} /></MemoryRouter>);
}

describe("DocsMarkdown", () => {
  it("anchors headings uniquely and links to them", () => {
    renderBody();
    const headings = screen.getAllByRole("heading", { level: 2 });
    expect(headings.map(heading => heading.id)).toEqual(["set-up-the-server", "set-up-the-server-1"]);
    expect(within(headings[0]).getByRole("link", { name: "Link to this section" })).toHaveAttribute("href", "#set-up-the-server");
  });

  it("rewrites links: published pages in the app, the rest to GitHub in a new tab", () => {
    renderBody();
    expect(screen.getByRole("link", { name: "Docker link" })).toHaveAttribute("href", "/docs/hosting/docker#ports");
    const external = screen.getByRole("link", { name: /invariant/ });
    expect(external).toHaveAttribute("href", "https://github.com/SpaceWorks-Labs/SpaceWorks/blob/main/docs/INVARIANTS.md");
    expect(external).toHaveAttribute("target", "_blank");
  });

  it("turns Note, Warning and GitHub-style quotes into labelled callouts, leaving plain quotes alone", () => {
    renderBody();
    const note = screen.getByRole("complementary", { name: "Note" });
    expect(note).toHaveAttribute("data-kind", "note");
    expect(note).toHaveTextContent("Back up first.");
    expect(note.textContent).not.toContain("Note:");
    expect(screen.getByRole("complementary", { name: "Warning" })).toHaveTextContent("This deletes data.");
    expect(screen.getByRole("complementary", { name: "Tip" })).toHaveTextContent("Use the installer.");
    expect(screen.getByText("A plain quote.").closest("blockquote")).not.toBeNull();
  });

  it("groups adjacent bash and PowerShell blocks into keyboard tabs with one copy button", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    renderBody();
    const tabs = screen.getAllByRole("tab");
    expect(tabs.map(tab => tab.textContent)).toEqual(["Bash", "PowerShell"]);
    expect(screen.getByRole("tabpanel")).toHaveTextContent("./install.sh");
    fireEvent.keyDown(tabs[0], { key: "ArrowRight" });
    expect(tabs[1]).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent(".\\install.ps1");
    const tabFigure = screen.getByRole("tabpanel").closest("figure")!;
    fireEvent.click(within(tabFigure).getByRole("button", { name: "Copy code" }));
    expect(writeText).toHaveBeenCalledWith(".\\install.ps1");
    expect(await within(tabFigure).findByRole("button", { name: "Copied" })).toBeInTheDocument();
  });

  it("labels a lone code block with its language, wraps tables and never renders raw HTML", () => {
    const { container } = renderBody();
    expect(screen.getByText("YAML")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Table" }).querySelector("table")).not.toBeNull();
    expect(container.querySelector("script")).toBeNull();
  });
});
