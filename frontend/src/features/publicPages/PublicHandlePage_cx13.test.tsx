import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useParams } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PublicHandlePage } from "./PublicHandlePage";
import { usePageHandle } from "./pageApi";

vi.mock("./pageApi", () => ({ usePageHandle: vi.fn(), pageApiPath: vi.fn() }));
vi.mock("../profile/PublicProfilePage", () => ({ PublicProfilePage: () => <h1>Profile {useParams().handle}</h1> }));
vi.mock("../public/MakerspacePage", () => ({ MakerspacePage: () => null }));
vi.mock("../organizations/PublicOrganizationPage", () => ({ PublicOrganizationPage: () => null }));

function show(path: string) {
  render(<MemoryRouter initialEntries={[path]}><Routes><Route path="/:handle" element={<PublicHandlePage />} /></Routes></MemoryRouter>);
}

describe("/@<handle> route (decision 549)", () => {
  beforeEach(() => {
    vi.mocked(usePageHandle).mockReset();
    vi.mocked(usePageHandle).mockReturnValue({ data: undefined, error: null } as ReturnType<typeof usePageHandle>);
  });

  it("opens the member card directly without requesting a space or organization resolution", () => {
    show("/@Maker.Name");
    expect(screen.getByRole("heading", { name: "Profile @Maker.Name" })).toBeVisible();
    expect(usePageHandle).toHaveBeenCalledExactlyOnceWith("maker.name", false);
  });

  it("retains the legacy member URL alias", () => {
    vi.mocked(usePageHandle).mockReturnValue({ data: null, error: null } as ReturnType<typeof usePageHandle>);
    show("/maker.name");
    expect(screen.getByRole("heading", { name: "Profile maker.name" })).toBeVisible();
    expect(usePageHandle).toHaveBeenCalledExactlyOnceWith("maker.name", true);
  });

  it("rejects malformed @ handles before either public lookup", () => {
    show("/@bad!");
    expect(screen.getByRole("heading", { name: "Loan slip not found" })).toBeVisible();
    expect(usePageHandle).toHaveBeenCalledExactlyOnceWith("bad!", false);
  });
});
