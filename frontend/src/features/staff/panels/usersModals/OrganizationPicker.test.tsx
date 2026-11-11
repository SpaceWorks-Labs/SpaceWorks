import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useOrganizations } from "../../organizationsApi";
import { emptyMakerspaceForm, makerspacePayload } from "../users/forms";
import { CreateMakerspaceModal } from "./CreateMakerspaceModal";
import { OrganizationPicker } from "./OrganizationPicker";
import type { MakerspaceForm } from "./types";

vi.mock("../../organizationsApi", () => ({ useOrganizations: vi.fn() }));
vi.mock("../../SpacePackProfilePicker", () => ({ SpacePackProfilePicker: () => null }));

const initial: MakerspaceForm = {
  ...emptyMakerspaceForm, name: "Community Lab", slug: "community-lab", public_code: "CLAB",
};

function Picker() {
  const [form, setForm] = useState(initial);
  return <OrganizationPicker form={form} onChange={setForm} error={null} />;
}

function Wizard({ onSubmit }: { onSubmit: (payload: ReturnType<typeof makerspacePayload>) => void }) {
  const [form, setForm] = useState(initial);
  return <CreateMakerspaceModal open form={form} pending={false} error={null}
    onChange={setForm} onClose={() => {}} onSubmit={() => onSubmit(makerspacePayload(form))} />;
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(useOrganizations, { partial: true }).mockReturnValue({
    data: { count: 1, next: null, previous: null, results: [
      { id: 7, name: "Existing Network", slug: "existing-network", is_active: true, governance_actions: [], granted_actions: [] },
    ] }, isLoading: false, error: null,
  });
});

describe("OrganizationPicker", () => {
  it("defaults a new organization name to the makerspace name and allows editing", () => {
    render(<Picker />);
    fireEvent.click(screen.getByRole("radio", { name: "New organization" }));
    const name = screen.getByRole("textbox", { name: "New organization name" });
    expect(name).toHaveValue("Community Lab");
    fireEvent.change(name, { target: { value: "Community Network" } });
    expect(name).toHaveValue("Community Network");
  });

  it("queries active organizations with the trimmed search term", () => {
    render(<Picker />);
    expect(useOrganizations).toHaveBeenLastCalledWith({ page: 1, search: "", active: true });
    fireEvent.change(screen.getByRole("searchbox", { name: "Search organizations" }), { target: { value: " Network " } });
    expect(useOrganizations).toHaveBeenLastCalledWith({ page: 1, search: "Network", active: true });
    fireEvent.click(screen.getByRole("radio", { name: /Existing Network/ }));
    expect(screen.getByRole("status")).toHaveTextContent("Selected organization: Existing Network");
  });
});

describe("CreateMakerspaceModal ownership", () => {
  it.each(["existing", "new"])("requires a choice and submits the %s owner", choice => {
    const submit = vi.fn();
    render(<Wizard onSubmit={submit} />);
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    fireEvent.click(screen.getByRole("radio", { name: choice === "new" ? "New organization" : /Existing Network/ }));
    expect(screen.getByRole("button", { name: "Next" })).toBeEnabled();
    for (let step = 0; step < 4; step++) fireEvent.click(screen.getByRole("button", { name: "Next" }));
    const create = screen.getByRole("button", { name: "Create makerspace" });
    expect(create).toBeEnabled();
    fireEvent.click(create);
    expect(submit).toHaveBeenCalledOnce();
    const payload = submit.mock.calls[0][0];
    expect(Object.keys(payload).filter(key => key.startsWith("organization_"))).toEqual([
      choice === "new" ? "organization_name" : "organization_id",
    ]);
    expect(payload).toMatchObject(choice === "new" ? { organization_name: "Community Lab" } : { organization_id: 7 });
  });

  it("disables progression again when a new organization name is emptied", () => {
    render(<Wizard onSubmit={vi.fn()} />);
    fireEvent.click(screen.getByRole("radio", { name: "New organization" }));
    fireEvent.change(screen.getByRole("textbox", { name: "New organization name" }), { target: { value: "   " } });
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });
});
