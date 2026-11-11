import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { NotFoundPage } from "./NotFoundPage";
import { DelightProvider } from "../components/delight/DelightProvider";
import { expectNoA11yViolations } from "../test/axe";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it("escapes the path, provides keyboard button tearing and a local inventory escape", async () => {
  vi.stubGlobal("matchMedia", () => ({ matches: true, addEventListener() {}, removeEventListener() {} }));
  const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
  const result = render(<MemoryRouter initialEntries={["/m/workshop/lost-tool"]}><NotFoundPage /></MemoryRouter>);
  expect(screen.getByText("/m/workshop/lost-tool")).toBeTruthy();
  expect(screen.getByRole("link", { name: "Back to home" })).toHaveAttribute("href", "/m/workshop");
  fireEvent.click(screen.getByRole("button", { name: "Tear off the tag" }));
  expect(screen.getByText("Tag removed. Return to the space to explore what’s available.")).toBeTruthy();
  expect(screen.queryByText("/m/workshop/lost-tool")).toBeNull();
  expect(result.container.querySelector(".sw-delight-pass")).toBeNull();
  expect(fetch).not.toHaveBeenCalled();
  await expectNoA11yViolations(result.container);
});

it("keeps normal navigation when delight is disabled", () => {
  render(<MemoryRouter initialEntries={["/missing"]}><DelightProvider enabled={false}><NotFoundPage /></DelightProvider></MemoryRouter>);
  expect(screen.getByText("We couldn't find that page")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Tear off the tag" })).toBeNull();
  expect(screen.getByRole("link", { name: "Back to home" })).toHaveAttribute("href", "/");
});
