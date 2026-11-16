import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StageAnswerFiles } from "./StageAnswerFiles";
describe("immutable answer file projection", () => {
  it("does not turn bare asset IDs, foreign-event paths or external URLs into read controls", () => {
    render(<StageAnswerFiles eventId={41} value={[
      { asset_id: 91, generation: 1, sha256: "a".repeat(64) },
      { download_path: "https://untrusted.test/file" },
      { download_path: "/admin/events/42/stage-files/91/download/?revision=1" },
    ]} />);
    expect(screen.queryByRole("button")).toBeNull();
  });
  it("accepts only a reauthorizable same-event projected read route", () => {
    render(<StageAnswerFiles eventId={41} value={[{ download_path: "/api/v1/admin/events/41/stage-files/91/download/?response_id=111&revision=1" }]} />);
    expect(screen.getByRole("button", { name: "Download disclosed file 1" })).toBeInTheDocument();
  });
});
