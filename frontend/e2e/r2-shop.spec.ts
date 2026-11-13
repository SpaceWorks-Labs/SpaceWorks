import { expect, test } from "@playwright/test";

import { SEED } from "./helpers";
import { StaffApi, blockThirdParty, memberArea, rowsOf, staffConsole, unique } from "./r2";

// #134 flow 6, shop (L22).
//  - Online order and pickup: a member orders from the public shop and pays at the desk; staff
//    take the payment (UPI), mark it ready and hand it over against the pickup code.
//  - Till and cash-up: staff open the cash drawer with a float, sell an item at the till for
//    cash, then count the drawer and close it balanced.
// The seed_e2e space has no `payments` module, so an online order is always "pay at the desk".

type Variant = { id: number; sku: string; price: string };
type Product = { id: number; name: string; slug: string; variants: Variant[] };
type Order = { id: number; status: string; pickup_code: string; amount_due: string; total: string };
type CashSession = { id: number; status: string; expected_now?: string; expected_cash?: string; opening_float: string; variance?: string | null };

const SHOP_FEATURES = ["shop.online", "shop.holds", "shop.public_stock", "shop.receipts", "charges.enabled", "charges.shop"];

async function stockedProduct(staff: StaffApi, label: string, price: string): Promise<{ product: Product; variant: Variant }> {
  const name = unique(label);
  const sku = `E2E-${Date.now().toString(36).toUpperCase()}`;
  const product = await staff.post<Product>(`/admin/makerspaces/${staff.makerspaceId}/shop/products/`, {
    name, kind: "merch", is_public: true, is_active: true, variants: [{ name: "Standard", sku, price }],
  });
  const variant = product.variants[0];
  await staff.post(`/admin/shop/variants/${variant.id}/stock/`, { kind: "restock", quantity: 10, reason: "E2E stock" });
  return { product, variant };
}

test.beforeEach(async ({ page }) => { await blockThirdParty(page); });

test("a member orders online, pays at the desk, and staff hand it over", async ({ page, browser, request }) => {
  const staff = await StaffApi.open(request);
  await staff.installModules("shop");
  await staff.setFeatures(SHOP_FEATURES, ["shop.guest_checkout", "payments.shop", "billing.maker_checker"]);
  const { product } = await stockedProduct(staff, "E2E Sticker Pack", "80.00");

  let placed: Order | undefined;
  await test.step("member adds the item to the basket and places the order", async () => {
    await memberArea(page);
    await page.goto(`/m/${SEED.slug}/shop`);
    await page.getByRole("button", { name: `Add ${product.name} to basket` }).click();
    await page.getByRole("button", { name: /^Basket \(1\)$/ }).click();
    const basket = page.getByRole("dialog", { name: "Your basket" });
    await expect(basket.getByRole("list", { name: "Basket" })).toContainText(product.name);
    const response = page.waitForResponse((res) => res.request().method() === "POST"
      && /\/api\/v1\/public\/m\/[^/]+\/shop\/orders\/$/.test(res.url()));
    await page.getByRole("button", { name: "Place order, pay at the desk" }).click();
    const body = await (await response).json() as { order: Order };
    placed = body.order;
    expect(placed.status).toBe("awaiting_payment");
    await expect(page.getByText("Order placed").first()).toBeVisible();
    await expect(page.getByText("Your pickup code")).toBeVisible();
    await expect(page.getByText(placed.pickup_code, { exact: true })).toBeVisible();
  });

  await test.step("staff take the payment, mark it ready and hand it over", async () => {
    const desk = await browser.newContext();
    const deskPage = await desk.newPage();
    await blockThirdParty(deskPage);
    await staffConsole(deskPage, "shop");
    await deskPage.getByRole("button", { name: new RegExp(`^#${placed!.id} ·`) }).click();
    await expect(deskPage.getByRole("heading", { name: `Order #${placed!.id}` })).toBeVisible();

    await deskPage.getByRole("button", { name: "Take payment" }).click();
    const pay = deskPage.getByRole("dialog", { name: /^Take / });
    await pay.getByRole("radio", { name: "UPI" }).check();
    await pay.getByLabel("Transaction reference").fill("E2E-UPI-0001");
    // Leave the items on the shelf so the ready-for-pickup step is exercised.
    await pay.getByLabel("Hand the items over now").uncheck();
    await pay.getByRole("button", { name: "Record payment" }).click();
    await expect(pay).toBeHidden();
    await expect(deskPage.getByText("Paid", { exact: true }).first()).toBeVisible();

    await deskPage.getByRole("button", { name: "Mark ready" }).click();
    await expect(deskPage.getByText("Ready to collect", { exact: true }).first()).toBeVisible();

    await deskPage.getByRole("button", { name: "Hand over", exact: true }).first().click();
    const handOver = deskPage.getByRole("dialog", { name: "Hand over the order" });
    await handOver.getByLabel("Pickup code").fill(placed!.pickup_code);
    await handOver.getByRole("button", { name: "Hand over", exact: true }).click();
    await expect(handOver).toBeHidden();
    await expect(deskPage.getByText("Collected", { exact: true }).first()).toBeVisible();
    await desk.close();
  });

  const final = await staff.get<Order>(`/admin/shop/orders/${placed!.id}/`);
  expect(final.status).toBe("collected");

  await test.step("the member's order page shows it collected", async () => {
    await page.goto(`/m/${SEED.slug}/member/shop-orders/${placed!.id}`);
    await expect(page.getByText("Collected", { exact: true }).first()).toBeVisible();
  });
});

test("a till sale for cash, then the drawer is counted and closed balanced", async ({ page, request }) => {
  const staff = await StaffApi.open(request);
  await staff.installModules("shop");
  // With maker-checker off, closing the drawer is final (no second person confirms).
  await staff.setFeatures([...SHOP_FEATURES, "shop.cash_up"], ["billing.maker_checker"]);
  const { product, variant } = await stockedProduct(staff, "E2E Solder Spool", "80.00");

  // A drawer left open by an earlier, interrupted run would refuse a new one: close it first.
  const sessions = rowsOf(await staff.get<CashSession[] | { results: CashSession[] }>(`/admin/makerspaces/${staff.makerspaceId}/shop/cash-sessions/`));
  for (const open of sessions.filter((row) => row.status === "open")) {
    await staff.post(`/admin/shop/cash-sessions/${open.id}/close/`, {
      counted_cash: open.expected_now ?? open.opening_float, note: "E2E: closing a drawer left open by an earlier run",
    });
  }

  await staffConsole(page, "shop");
  const sections = page.getByRole("tablist", { name: "Shop sections" });

  await test.step("open the drawer with a float", async () => {
    await sections.getByRole("tab", { name: "Cash-up" }).click();
    await page.getByLabel("Opening float").fill("500.00");
    await page.getByRole("button", { name: "Open the drawer" }).click();
    await expect(page.getByText("Expected in the drawer now")).toBeVisible();
  });

  await test.step("sell one item at the till for cash", async () => {
    await sections.getByRole("tab", { name: "Till" }).click();
    const scan = page.getByLabel("Scan or type an item");
    await scan.fill(variant.sku);
    await scan.press("Enter");
    await expect(page.getByText(/^Added /)).toBeVisible();
    const payment = page.getByRole("complementary", { name: "Payment" }).or(page.getByRole("region", { name: "Payment", exact: true })).first();
    await expect(payment.getByRole("radio", { name: "Cash" })).toBeChecked();
    await payment.getByRole("button", { name: "Sell" }).click();
    await expect(page.getByText(/^Sale recorded: order #\d+\.$/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Start a new sale" })).toBeVisible();
  });

  await test.step("count the cash and close the drawer", async () => {
    await sections.getByRole("tab", { name: "Cash-up" }).click();
    await page.getByLabel("Counted cash").fill("580.00");
    await page.getByLabel("Note (optional)").fill(`E2E till check for ${product.name}`);
    await page.getByRole("button", { name: "Close and record the count" }).click();
    await expect(page.getByRole("heading", { name: "Drawer closed" })).toBeVisible();
    await expect(page.getByText(/Balanced\./)).toBeVisible();
  });

  const closed = rowsOf(await staff.get<CashSession[] | { results: CashSession[] }>(`/admin/makerspaces/${staff.makerspaceId}/shop/cash-sessions/`))
    .sort((a, b) => b.id - a.id)[0];
  expect(closed.status).toBe("closed");
  expect(Number(closed.expected_cash)).toBe(580);
  expect(Number(closed.variance)).toBe(0);
});
