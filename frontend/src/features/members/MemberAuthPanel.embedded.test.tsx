import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemberAuthPanel } from "./MemberAuthPanel";

vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"),
  publicV1Request: vi.fn().mockResolvedValue({}) }));
vi.mock("../auth/SocialSignInButtons", () => ({ SocialSignInButtons: () => null }));

describe("member sign-in", () => {
  it("is a whole page on its own", async () => {
    render(<MemberAuthPanel onAuthenticated={vi.fn()} />);
    expect(await screen.findByRole("heading", { level: 1, name: "Member sign in" })).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
  });
  it("says what it is signing in to when a host names it (the staff console)", async () => {
    render(<MemberAuthPanel eyebrow="Staff console" loginTitle="Sign in to the staff console" onAuthenticated={vi.fn()} />);
    expect(await screen.findByRole("heading", { level: 1, name: "Sign in to the staff console" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Member sign in" })).not.toBeInTheDocument();
  });
  it("drops the page chrome when embedded in another page", async () => {
    render(<main><h1>Workshop</h1><MemberAuthPanel embedded context={<p>Sign in to submit a booking.</p>} onAuthenticated={vi.fn()} /></main>);
    const region = await screen.findByRole("region", { name: "Member sign in" });
    expect(region).toHaveTextContent("Sign in to submit a booking.");
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(screen.queryByRole("link", { name: "Space Works — Open makerspace listing" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });
});
