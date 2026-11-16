import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { PublicDetailLayout } from "./PublicDetailLayout";

const actionCard = { title: "Join", state: "open" as const, primary: { label: "Register", href: "#register" }, mobileBar: { summary: "Open", label: "Register" } };

it("links a chip that has an href and leaves plain chips as labels (E-F3 tag chips)", () => {
  render(<PublicDetailLayout state={{ status: "ready" }} title="Repair night" actionCard={actionCard}
    sections={[{ id: "about", label: "About", content: <p>Details</p> }]}
    chips={[{ label: "Members only", tone: "info" }, { label: "robotics", href: "/discover?tag=robotics" }]} />);
  expect(screen.getByRole("link", { name: /robotics/ })).toHaveAttribute("href", "/discover?tag=robotics");
  expect(screen.queryByRole("link", { name: /Members only/ })).not.toBeInTheDocument();
  expect(screen.getByText("Members only")).toBeInTheDocument();
});
