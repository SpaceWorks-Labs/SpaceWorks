import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { StageFormBuilder } from "./StageFormBuilder";
const mutate = vi.hoisted(() => vi.fn());
vi.mock("./api", () => ({ stageAdminPath: () => "/admin/events/41/", useStageDefinition: () => ({ data: undefined }),
  useDefinitionCommand: () => ({ mutate, isPending: false }) }));
afterEach(() => { mutate.mockReset(); });
describe("new stage identity", () => {
  it("creates settings first so the server issues the stable form ID before questions are authored", () => {
    render(<StageFormBuilder scope={{ actorId: 1, makerspaceId: 2, eventId: 41 }} allowedActions={["stage_create"]} onCreated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Checklist" } });
    fireEvent.change(screen.getByLabelText("Slug"), { target: { value: "checklist" } });
    fireEvent.submit(screen.getByRole("button", { name: "Create draft stage" }).closest("form")!);
    expect(mutate).toHaveBeenCalledWith({ path: "/admin/events/41/stage-forms/", method: "POST", body: expect.objectContaining({ expected_version: 0, settings: expect.objectContaining({ title: "Checklist", slug: "checklist" }) }) }, expect.anything());
    expect(mutate.mock.calls[0][0].body).not.toHaveProperty("schema");
    expect(screen.queryByRole("button", { name: "Add question" })).toBeNull();
  });
});
