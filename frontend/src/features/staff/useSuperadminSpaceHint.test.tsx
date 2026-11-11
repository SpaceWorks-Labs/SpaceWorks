import { render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { StaffAuthUser } from "../../lib/api";
import type { Makerspace } from "./panels/shared";
import { useSuperadminSpaceHint } from "./useSuperadminSpaceHint";

const spaces = [{ id: 4, slug: "alpha" }, { id: 9, slug: "beta" }] as Makerspace[];
const platform = { username: "root", is_superuser: true, role: "superadmin", makerspaces: [] } as unknown as StaffAuthUser;

function Probe({ user, setSelected, context = "platform" as const }: { user: StaffAuthUser; setSelected: (id: number | null) => void; context?: "platform" | "person" }) {
  useSuperadminSpaceHint({ context, user, makerspaces: spaces, selected: null, setSelected });
  const location = useLocation();
  return <output>{location.pathname}{location.search}</output>;
}

describe("useSuperadminSpaceHint", () => {
  it("opens the hinted space for the superadmin and drops the hint", () => {
    const setSelected = vi.fn();
    render(<MemoryRouter initialEntries={["/admin/reports?context=platform&space=beta"]}><Probe user={platform} setSelected={setSelected} /></MemoryRouter>);
    expect(setSelected).toHaveBeenCalledWith(9);
    expect(screen.getByRole("status")).toHaveTextContent("/admin/reports?context=platform");
  });

  it("reads the collision-free for_space hint the platform overview sends (#183A)", () => {
    const setSelected = vi.fn();
    render(<MemoryRouter initialEntries={["/admin/bookings?context=platform&for_space=4"]}><Probe user={platform} setSelected={setSelected} /></MemoryRouter>);
    expect(setSelected).toHaveBeenCalledWith(4);
    expect(screen.getByRole("status")).toHaveTextContent("/admin/bookings?context=platform");
  });

  it("ignores the hint outside the platform context and for staff", () => {
    const setSelected = vi.fn();
    const staffUser = { ...platform, is_superuser: false, role: "person" } as StaffAuthUser;
    render(<MemoryRouter initialEntries={["/admin/reports?space=beta"]}><Probe user={platform} setSelected={setSelected} context="person" /></MemoryRouter>);
    render(<MemoryRouter initialEntries={["/admin/reports?context=platform&space=beta"]}><Probe user={staffUser} setSelected={setSelected} /></MemoryRouter>);
    expect(setSelected).not.toHaveBeenCalled();
  });
});
