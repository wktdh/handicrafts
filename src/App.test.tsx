import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App, { Discover, productListImageUrl, shipmentTrackingLink } from "./App";
import DataAdvisor from "./pages/seller/DataAdvisor";

const product = { id: 1, catalogId: "product-test", title: "测试陶瓷杯", category: "陶艺", price: 88, image: "", shopId: 99, analyticsShopId: "shop-demo-taoran", shop: "陶然物语", rating: 5, reviews: 0, stock: 3, tags: ["原创手作"], seoTags: ["陶瓷"], listed: true, custom: true, description: "测试描述", material: "陶瓷" } as Parameters<typeof Discover>[0]["products"][number];

describe("Discover", () => {
  it("uses responsive COS WebP thumbnails only for public product media", () => {
    expect(
      productListImageUrl(
        "https://cdn.shouzuohub.com/products/2026/08/image-demo.jpg",
        400,
      ),
    ).toBe(
      "https://cdn.shouzuohub.com/products/2026/08/image-demo.jpg?imageMogr2/thumbnail/400x400/format/webp",
    );
    expect(productListImageUrl("/media/private-image.jpg", 400)).toBe(
      "/media/private-image.jpg",
    );
    expect(
      productListImageUrl(
        "https://cdn.shouzuohub.com/products/2026/08/variant.jpg",
        160,
      ),
    ).toContain("thumbnail/160x160");
  });

  it("renders results and forwards sort selection", () => {
    const onSort = vi.fn();
    render(<Discover products={[product]} query="陶瓷" category="全部" sort="relevance" favorites={[]} onOpen={vi.fn()} onFavorite={vi.fn()} onCategory={vi.fn()} onSort={onSort} />);
    expect(screen.getByText("测试陶瓷杯")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Sort results" }), { target: { value: "price_asc" } });
    expect(onSort).toHaveBeenCalledWith("price_asc");
  });

  it("forwards related-search selection from search guidance", () => {
    const onQueryChange = vi.fn();
    render(<Discover products={[product]} query="cup" searchMeta={{ originalQuery: "cup", corrected: "cup", recommendations: ["mug"] }} category="全部" sort="relevance" favorites={[]} onOpen={vi.fn()} onFavorite={vi.fn()} onCategory={vi.fn()} onSort={vi.fn()} onQueryChange={onQueryChange} />);
    fireEvent.click(screen.getByRole("button", { name: "mug" }));
    expect(onQueryChange).toHaveBeenCalledWith("mug");
  });
});

describe("authentication route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.history.replaceState(null, "", "/");
  });

  it("keeps the login page open after a refresh", async () => {
    window.history.replaceState(null, "", "/?auth=login");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
    expect(window.location.search).toBe("?auth=login");
  });
});

describe("path-first application routes", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.history.replaceState(null, "", "/");
  });

  const restoreAccount = (account: { id: string; name: string; role: "seller" | "admin" }) => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/auth/session"))
          return Promise.resolve({ ok: true, json: async () => ({ account }) });
        if (url.includes("/api/seller/workspace"))
          return Promise.resolve({ ok: true, json: async () => ({ products: [], drafts: [] }) });
        return Promise.resolve({ ok: false, json: async () => ({}) });
      }),
    );
  };

  it("keeps the marketplace homepage at the root for a signed-in seller", async () => {
    restoreAccount({ id: "seller-route-test", name: "Route Seller", role: "seller" });

    render(<App />);

    expect(await screen.findByRole("heading", { name: /Make room for what/i })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/");
    expect(screen.getByTestId("nav-home")).toBeVisible();
    expect(screen.getByTestId("nav-discover")).toBeVisible();
  });

  it("keeps the marketplace homepage at the root for an administrator", async () => {
    restoreAccount({ id: "admin-route-test", name: "Route Admin", role: "admin" });

    render(<App />);

    expect(await screen.findByRole("heading", { name: /Make room for what/i })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/");
  });

  it("renders the administrator console only at /admin/", async () => {
    window.history.replaceState(null, "", "/admin/");
    restoreAccount({ id: "admin-route-test", name: "Route Admin", role: "admin" });

    render(<App />);

    expect(await screen.findByRole("heading", { name: "管理员后台" })).toBeInTheDocument();
  });
});

describe("DataAdvisor", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("loads business analytics, changes period, and routes an optimization task", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        analytics: {
          current: {
            startDate: "2026-08-01",
            endDate: "2026-08-07",
            overview: {
              exposureUv: 120,
              clickUv: 24,
              ctr: 20,
              favoriteAdds: 6,
              addCartUv: 4,
              orders: 2,
              revenue: 199,
              clickToOrderRate: 8.3,
            },
            funnel: { exposureUv: 120, clickUv: 24, favoriteAdds: 6, addCartUv: 4, orders: 2 },
            products: [{ id: "p-1", title: "手工陶杯", exposureUv: 120, clickUv: 24, ctr: 20, favoriteAdds: 6, addCartUv: 4, orders: 2, revenue: 199, clickToOrderRate: 8.3 }],
            insights: [{ id: "stock", title: "库存偏低", reason: "近 7 天销量增长，建议及时补货。", priority: "high", actionTarget: "inventory", actionLabel: "管理库存" }],
          },
          previous: { overview: { exposureUv: 80 } },
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const onOpenTab = vi.fn();
    render(<DataAdvisor onOpenTab={onOpenTab} />);

    expect(await screen.findByText("手工陶杯")).toBeInTheDocument();
    expect(screen.getByText("近 7 天销量增长，建议及时补货。")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "管理库存" }));
    expect(onOpenTab).toHaveBeenCalledWith("inventory");

    fireEvent.click(screen.getByRole("button", { name: "近 30 天" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenLastCalledWith(
        expect.stringContaining("/api/analytics/seller/business?days=30"),
        { credentials: "include" },
      ),
    );
  });
});

describe("shipment tracking links", () => {
  it("opens a recognized carrier's official tracking page", () => {
    expect(shipmentTrackingLink("DHL Express", "JD 01/23")).toEqual({
      url: "https://www.dhl.com/global-en/home/tracking.html?tracking-id=JD%2001%2F23",
      official: true,
      requiresPhoneLast4: false,
    });
  });

  it("uses the international tracking fallback for other carriers", () => {
    expect(shipmentTrackingLink("Other International Courier", "TRACK-123")).toEqual({
      url: "https://www.17track.net/en/track#nums=TRACK-123",
      official: false,
      requiresPhoneLast4: false,
    });
  });

  it("identifies the additional phone verification required by SF Express", () => {
    expect(shipmentTrackingLink("SF Express", "SF123").requiresPhoneLast4).toBe(true);
  });
});
