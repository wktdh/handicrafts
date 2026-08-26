import { expect, test } from "@playwright/test";

test("guest can search and sort discovered products", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const search = page.locator(".search input");
  await search.fill("ceramic");
  await search.press("Enter");
  await expect(page.locator(".discover-heading")).toContainText("Search results");
  await page.locator(".search-sort select").selectOption("price_asc");
});

test("guest can submit a search with the header button", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const search = page.locator(".search input");
  await search.fill("coffee");
  await page.locator(".search button").click();
  await expect(page.locator(".discover-heading")).toBeVisible();
  await expect(page.locator(".product-grid .product-card").first()).toBeVisible();
});
