import { expect, test, type Page } from "@playwright/test";

const buyerPassword = "e2e-buyer-password";
const apiBase = "http://127.0.0.1:8788";
const browserOrigin = "http://127.0.0.1:5174";
const csrfTokens = new WeakMap<Page, string>();

function stateChangeHeaders(page: Page, extra: Record<string, string> = {}) {
  const csrfToken = csrfTokens.get(page);
  return {
    Origin: browserOrigin,
    ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
    ...extra,
  };
}

function rememberCsrfToken(page: Page, response: { headers(): Record<string, string> }) {
  const csrfToken = response.headers()["x-csrf-token"];
  if (csrfToken) csrfTokens.set(page, csrfToken);
}

async function registerBuyer(page: Page, email: string) {
  await page.goto("/");
  await page.getByTestId("open-auth").click();
  await page.getByTestId("auth-register-tab").click();
  await page.getByTestId("auth-name").fill("E2E Buyer");
  await page.getByTestId("auth-email").fill(email);
  await page.getByTestId("auth-password").fill(buyerPassword);
  await page.getByTestId("auth-confirm-password").fill(buyerPassword);
  await page.getByTestId("auth-submit").click();
  await expect(page.getByTestId("open-cart")).toBeVisible();
}

async function loginApi(page: Page, identifier: string, password: string) {
  const response = await page.request.post(`${apiBase}/api/auth/login`, {
    data: { identifier, password },
    headers: stateChangeHeaders(page),
  });
  expect(response.ok()).toBeTruthy();
  rememberCsrfToken(page, response);
}

async function registerBuyerApi(page: Page, email: string) {
  const response = await page.request.post(`${apiBase}/api/auth/register`, {
    data: { name: "E2E Buyer", email, password: buyerPassword, confirmPassword: buyerPassword, role: "buyer" },
    headers: stateChangeHeaders(page),
  });
  expect(response.ok()).toBeTruthy();
  rememberCsrfToken(page, response);
}

async function createPaidOrder(buyer: Page) {
  const address = await buyer.request.post(`${apiBase}/api/addresses`, {
    data: {
      recipient: "E2E Buyer", phone: "13800138000", province: "Zhejiang", city: "Hangzhou", district: "Xihu",
      detail: `E2E address ${Date.now()}`, countryCode: "US",
    },
    headers: stateChangeHeaders(buyer),
  });
  expect(address.ok()).toBeTruthy();
  const addressId = (await address.json()).address.id as string;
  const created = await buyer.request.post(`${apiBase}/api/orders`, {
    data: { addressId, items: [{ catalogId: "product-demo-cup", quantity: 1, variants: {} }] },
    headers: stateChangeHeaders(buyer),
  });
  expect(created.status()).toBe(201);
  const orderNo = (await created.json()).orders[0].id as string;
  const payment = await buyer.request.post(`${apiBase}/api/orders/${orderNo}/pay`, {
    data: { paymentMethod: "card" }, headers: stateChangeHeaders(buyer),
  });
  expect(payment.ok()).toBeTruthy();
  const token = (await payment.json()).payment.token as string;
  const confirmed = await buyer.request.post(`${apiBase}/api/orders/${orderNo}/payment-confirm`, {
    data: { paymentToken: token }, headers: stateChangeHeaders(buyer),
  });
  expect(confirmed.ok()).toBeTruthy();
  return orderNo;
}

test("registration shows validation feedback for incomplete data", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("open-auth").click();
  await page.getByTestId("auth-register-tab").click();
  await page.getByTestId("auth-submit").click();

  await expect(page.getByRole("alert")).toBeVisible();
});

test("buyer checkout confirms payment and seller can ship the order", async ({ page, browser }, testInfo) => {
  test.skip(testInfo.project.name === "mobile", "Stateful fulfillment runs once against the isolated E2E database.");
  test.setTimeout(120_000);
  const email = `e2e-buyer-${Date.now()}@example.test`;
  await registerBuyer(page, email);

  await page.getByTestId("nav-discover").click();
  const productPagePromise = page.waitForEvent("popup");
  await page.getByTestId("product-open-product-demo-cup").click();
  const buyerPage = await productPagePromise;
  await buyerPage.getByTestId("product-add-cart").click();
  await expect(buyerPage.getByTestId("cart-count")).toBeVisible();
  await buyerPage.getByTestId("open-cart").click();
  await buyerPage.getByTestId("cart-checkout").click();
  await buyerPage.getByTestId("checkout-recipient").fill("E2E Buyer");
  await buyerPage.getByTestId("checkout-phone").fill("13800138000");
  await buyerPage.getByTestId("checkout-province").fill("Zhejiang");
  await buyerPage.getByTestId("checkout-city").fill("Hangzhou");
  await buyerPage.getByTestId("checkout-district").fill("Xihu");
  await buyerPage.getByTestId("checkout-detail").fill("E2E test address");
  await buyerPage.getByTestId("checkout-add-address").click();
  await expect(buyerPage.getByTestId("checkout-submit")).toBeEnabled();
  await buyerPage.getByTestId("checkout-submit").click();
  await expect(buyerPage.getByTestId("order-card")).toBeVisible();
  await expect(buyerPage.getByTestId("order-payment-confirmed")).toBeVisible();

  const sellerContext = await browser.newContext();
  const sellerPage = await sellerContext.newPage();
  try {
    await loginApi(sellerPage, "seller@example.test", "replace-with-argon2-hash");
    const orderId = (await buyerPage.getByTestId("order-card").first().locator("header span").first().textContent())
      ?.replace("Order ", "");
    expect(orderId).toBeTruthy();
    const shipped = await sellerPage.request.post(`${apiBase}/api/orders/${orderId}/ship`, {
      data: { carrier: "E2E Express", trackingNo: "E2E-TRACK-001" },
      headers: stateChangeHeaders(sellerPage),
    });
    expect(shipped.ok()).toBeTruthy();
  } finally {
    await sellerContext.close();
  }
});

test("order APIs complete review, refund, and administrator approval workflows", async ({ browser }, testInfo) => {
  test.skip(testInfo.project.name === "mobile", "Stateful API lifecycle runs once against the isolated E2E database.");
  test.setTimeout(120_000);
  const buyerContext = await browser.newContext();
  const sellerContext = await browser.newContext();
  const adminContext = await browser.newContext();
  const buyer = await buyerContext.newPage();
  const seller = await sellerContext.newPage();
  const admin = await adminContext.newPage();
  try {
    await registerBuyerApi(buyer, `e2e-api-buyer-${Date.now()}@example.test`);
    await loginApi(seller, "seller@example.test", "replace-with-argon2-hash");

    const reviewOrderNo = await createPaidOrder(buyer);
    const shipped = await seller.request.post(`${apiBase}/api/orders/${reviewOrderNo}/ship`, {
      data: { carrier: "E2E Express", trackingNo: "E2E-REVIEW-001" }, headers: stateChangeHeaders(seller),
    });
    expect(shipped.ok()).toBeTruthy();
    const received = await buyer.request.post(`${apiBase}/api/orders/${reviewOrderNo}/receive`, { data: {}, headers: stateChangeHeaders(buyer) });
    expect(received.ok()).toBeTruthy();
    const review = await buyer.request.post(`${apiBase}/api/orders/${reviewOrderNo}/review`, {
      data: { rating: 4, content: "E2E review", images: ["data:image/png;base64,AA=="] },
      headers: stateChangeHeaders(buyer),
    });
    expect(review.status()).toBe(201);
    const buyerReviews = await buyer.request.get(`${apiBase}/api/reviews/buyer`);
    expect(buyerReviews.ok()).toBeTruthy();
    const reviewId = (await buyerReviews.json()).reviews.find((item: { orderId: string }) => item.orderId === reviewOrderNo).id as string;
    const reply = await seller.request.post(`${apiBase}/api/reviews/${reviewId}/reply`, { data: { reply: "Thanks for the review" }, headers: stateChangeHeaders(seller) });
    expect(reply.ok()).toBeTruthy();
    const followup = await buyer.request.post(`${apiBase}/api/reviews/${reviewId}/followup`, { data: { content: "E2E follow-up" }, headers: stateChangeHeaders(buyer) });
    expect(followup.ok()).toBeTruthy();

    const refundOrderNo = await createPaidOrder(buyer);
    const requested = await buyer.request.post(`${apiBase}/api/orders/${refundOrderNo}/after-sales`, {
      data: { type: "refund", amount: 1, reason: "E2E refund", evidence: ["data:image/png;base64,AA=="] },
      headers: stateChangeHeaders(buyer),
    });
    expect(requested.status()).toBe(201);
    const requestId = (await requested.json()).afterSales[0].id as string;
    const approved = await seller.request.post(`${apiBase}/api/after-sales/${requestId}/approve`, { data: { response: "Approved by E2E seller" }, headers: stateChangeHeaders(seller) });
    expect(approved.ok()).toBeTruthy();
    const afterSales = await buyer.request.get(`${apiBase}/api/after-sales/buyer`);
    const completed = (await afterSales.json()).afterSales.find((item: { id: string }) => item.id === requestId);
    expect(completed.refundStatus).toBe("recorded");

    await loginApi(admin, "admin@example.test", "platform-admin");
    const stepUpRequest = await admin.request.post(`${apiBase}/api/auth/request-admin-step-up`, { data: {}, headers: stateChangeHeaders(admin) });
    expect(stepUpRequest.ok(), await stepUpRequest.text()).toBeTruthy();
    const code = (await stepUpRequest.json()).developmentCode as string;
    expect(code).toBeTruthy();
    const stepUpConfirmation = await admin.request.post(`${apiBase}/api/auth/confirm-admin-step-up`, { data: { code }, headers: stateChangeHeaders(admin) });
    expect(stepUpConfirmation.ok()).toBeTruthy();
    const ticket = (await stepUpConfirmation.json()).ticket as string;
    const moderation = await admin.request.post(`${apiBase}/api/admin/moderation/products/product-e2e-moderation`, {
      data: { decision: "rejected", reason: "E2E moderation review" }, headers: stateChangeHeaders(admin, { "X-Admin-Step-Up": ticket }),
    });
    expect(moderation.ok()).toBeTruthy();
  } finally {
    await buyerContext.close();
    await sellerContext.close();
    await adminContext.close();
  }
});

test("admin operations reject anonymous and buyer sessions", async ({ request }) => {
  const anonymous = await request.get("http://127.0.0.1:8788/api/admin/operations");
  expect(anonymous.status()).toBe(401);

  const registration = await request.post("http://127.0.0.1:8788/api/auth/register", {
    data: { name: "E2E Restricted Buyer", email: `e2e-restricted-${Date.now()}@example.test`, password: buyerPassword, confirmPassword: buyerPassword, role: "buyer" },
    headers: { Origin: browserOrigin },
  });
  expect(registration.ok()).toBeTruthy();
  const buyerAttempt = await request.get("http://127.0.0.1:8788/api/admin/operations");
  expect(buyerAttempt.status()).toBe(403);
});
