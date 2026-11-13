import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { CreateMakerspaceModal } from "./CreateMakerspaceModal";
import { makerspacePayload } from "../users/forms";
import type { MakerspaceForm } from "./types";
import { useOrganizations } from "../../organizationsApi";

vi.mock("../../organizationsApi", () => ({ useOrganizations: vi.fn() }));
vi.mock("../../SpacePackProfilePicker", () => ({ SpacePackProfilePicker: () => null }));
beforeEach(() => {
  vi.mocked(useOrganizations, { partial: true }).mockReturnValue({ data: { count: 0, next: null, previous: null, results: [] }, isLoading: false, error: null });
});

function Harness({ submit }: { submit: (body: unknown) => void }) {
  const [form, setForm] = useState<MakerspaceForm>({ name: "Chess Society", public_code: "CHES", slug: "chess", location: "" });
  return <CreateMakerspaceModal open form={form} pending={false} error={null} onChange={setForm} onClose={vi.fn()} onSubmit={() => submit(makerspacePayload(form))} />;
}

it("creates an organization workspace with its owner organization (decision 295)", () => {
  const submit = vi.fn();
  render(<Harness submit={submit} />);
  expect(screen.getByRole("radio", { name: /^Makerspace/ })).toBeChecked();
  fireEvent.click(screen.getByRole("radio", { name: /Organization workspace/ }));
  expect(screen.getByRole("dialog", { name: "Create organization workspace" })).toBeInTheDocument();
  expect(screen.getByText(/own this organization, or create a new one/)).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("New organization"));
  for (let step = 0; step < 4; step += 1) fireEvent.click(screen.getByText("Next"));
  expect(screen.getByText("Events, Memberships and Bookings")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Create organization workspace" }));
  expect(submit).toHaveBeenCalledWith(expect.objectContaining({ kind: "organization", organization_name: "Chess Society" }));
});

it("leaves the makerspace creation body without a kind", () => {
  expect(makerspacePayload({ name: "Forge", public_code: "FRGE", slug: "forge", location: "Lab", organization: "new" })).not.toHaveProperty("kind");
});
