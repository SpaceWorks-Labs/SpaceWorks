import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { OverlayPortal } from "./OverlayPortal";

it("blocks portalled and nested overlay content from replay", () => {
  render(<OverlayPortal><div><OverlayPortal><p>private action</p></OverlayPortal></div></OverlayPortal>);
  expect(screen.getByText("private action").closest("[data-replay-block]")).not.toBeNull();
});
