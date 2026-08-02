import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App, { Discover, shipmentTrackingLink } from "./App";

const product = { id: 1, catalogId: "product-test", title: "测试陶瓷杯", category: "陶艺", price: 88, image: "", shopId: 99, analyticsShopId: "shop-demo-taoran", shop: "陶然物语", rating: 5, reviews: 0, stock: 3, tags: ["原创手作"], seoTags: ["陶瓷"], listed: true, custom: true, description: "测试描述", material: "陶瓷" } as Parameters<typeof Discover>[0]["products"][number];

describe("Discover", () => {
  it("renders results and forwards sort selection", () => {
    const onSort = vi.fn();
    render(<Discover products={[product]} query="陶瓷" category="全部" sort="relevance" favorites={[]} onOpen={vi.fn()} onFavorite={vi.fn()} onCategory={vi.fn()} onSort={onSort} />);
    expect(screen.getByText("测试陶瓷杯")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "price_asc" } });
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

    expect(await screen.findByRole("heading", { name: "欢迎回来" })).toBeInTheDocument();
    expect(window.location.search).toBe("?auth=login");
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
