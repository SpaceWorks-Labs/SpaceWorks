import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../test/axe";
import { HelpArticleBody } from "./HelpArticleBody";

const state = vi.hoisted(() => ({ images: {} as Record<string, { src: string; width: number; height: number }> }));
vi.mock("./helpScreenshots", () => ({ HELP_SCREENSHOTS: state.images }));
const body = "## Borrow\n\n1. Open Inventory.\n\n![Screenshot: Your request card](screenshot:member-borrow-request)\n\nKeep the pickup note.";
beforeEach(() => { for (const key of Object.keys(state.images)) delete state.images[key]; });

describe("help screenshot publication", () => {
  it("preserves guide instructions without showing an uncaptured editorial placeholder", async () => {
    const { container } = render(<HelpArticleBody body={body} hrefFor={target => `/help/${target}`} />);
    expect(screen.getByRole("heading", { name: "Borrow" })).toBeInTheDocument();
    expect(screen.getByText("Open Inventory.")).toBeInTheDocument();
    expect(screen.getByText("Keep the pickup note.")).toBeInTheDocument();
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.queryByText("Screenshot: Your request card")).toBeNull();
    expect(container.querySelector("figure")).toBeNull();
    await expectNoA11yViolations(container);
  });

  it("renders only an explicitly reviewed capture with its exact caption and stable dimensions", async () => {
    state.images["member-borrow-request"] = { src: "/reviewed-borrow-request.webp", width: 1440, height: 1000 };
    const { container } = render(<HelpArticleBody body={body} hrefFor={target => `/help/${target}`} />);
    const image = screen.getByRole("img", { name: "Screenshot: Your request card" });
    expect(image).toHaveAttribute("src", "/reviewed-borrow-request.webp");
    expect(image).toHaveAttribute("width", "1440");
    expect(image).toHaveAttribute("height", "1000");
    expect(image).toHaveAttribute("loading", "lazy");
    expect(container.querySelector("figure[data-screenshot='member-borrow-request'] figcaption")).toHaveTextContent("Screenshot: Your request card");
    await expectNoA11yViolations(container);
  });

  it("does not substitute a capture from a different guide step", () => {
    state.images["another-step"] = { src: "/different.webp", width: 390, height: 844 };
    render(<HelpArticleBody body={body} hrefFor={target => `/help/${target}`} />);
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.getByText("Open Inventory.")).toBeInTheDocument();
  });
});
