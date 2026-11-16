import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { retryControls } from "./refusals.census-D12";
import { routeInventory } from "./source.census-D12";

it("identifies exact visible native retry controls by accessible name", () => {
  const row = routeInventory().find(item => item.screen === "UnsubscribePage")!;
  render(<main>
    <button aria-label="Retry">An icon</button><button>Try again</button><button>Check again</button><button>Reload</button>
    <button aria-label="Other action">Retry</button><button>Retry later</button><button hidden>Retry</button>
    <div role="button" tabIndex={0}>Another action</div>
  </main>);
  const controls = retryControls(row);
  expect(controls).toEqual([screen.getByRole("button", { name: "Retry" }), screen.getByRole("button", { name: "Try again" }),
    screen.getByRole("button", { name: "Check again" }), screen.getByRole("button", { name: "Reload" })]);
  expect(controls.map(node => node.tagName)).toEqual(["BUTTON", "BUTTON", "BUTTON", "BUTTON"]);
});
