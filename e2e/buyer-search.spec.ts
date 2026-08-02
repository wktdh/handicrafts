import { expect, test } from "@playwright/test";

test("guest can search and sort discovered products", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const search = page.getByPlaceholder("搜索手作、原创设计、复古好物");
  await search.fill("陶瓷");
  await search.press("Enter");
  await expect(page.locator(".discover-heading")).toContainText("陶瓷");
  await page.locator(".search-sort select").selectOption("price_asc");
});

test("guest can use autocomplete to open a search result", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".search-autocomplete")).toBeHidden();
  await page.getByPlaceholder("搜索手作、原创设计、复古好物").fill("咖");
  const suggestions = page.locator(".search-autocomplete");
  await expect(suggestions).toBeVisible();
  await page.locator(".hero").click({ position: { x: 8, y: 340 } });
  await expect(suggestions).toBeHidden();
  await page.getByPlaceholder("搜索手作、原创设计、复古好物").focus();
  await expect(suggestions).toBeVisible();
  await suggestions.getByRole("option").first().click();
  await expect(page.locator(".discover-heading")).toBeVisible();
  await expect(page.locator(".product-grid .product-card").first()).toBeVisible();
});
