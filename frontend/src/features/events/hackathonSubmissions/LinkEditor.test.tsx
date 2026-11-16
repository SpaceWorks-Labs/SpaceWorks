import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LinkEditor } from "./LinkEditor";

describe("private maker links", () => {
  it("defaults a new link to private and labels its type, URL and sharing choice", () => {
    const change = vi.fn();
    render(<LinkEditor value={[]} onChange={change} />);
    fireEvent.click(screen.getByRole("button", { name: "Add a link" }));
    expect(change).toHaveBeenCalledWith([{ kind: "repo", url: "", public_requested: false }]);
  });
  it("does not create an executable anchor for hostile schemes", () => {
    render(<LinkEditor value={[{ kind: "demo", url: "javascript:alert(1)", public_requested: false }]} onChange={() => {}} />);
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByRole("textbox", { name: "Link 1 URL" })).toBeTruthy();
    expect(screen.getByRole("checkbox")).not.toBeChecked();
  });
  it("uses safe external navigation and permits owner withdrawal", () => {
    const change = vi.fn();
    render(<LinkEditor value={[{ kind: "repo", url: "https://github.com/example/project", public_requested: true }]} onChange={change} />);
    expect(screen.getByRole("link")).toHaveAttribute("rel", "noopener noreferrer");
    fireEvent.click(screen.getByRole("checkbox"));
    expect(change.mock.calls[0][0][0].public_requested).toBe(false);
  });
});
