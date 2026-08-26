// @ts-nocheck
import { useEffect, useState } from "react";
import BrandSitePreview from "../seller/BrandSitePreview";

export default function PublicBrandSite({ context }: { context: Record<string, any> }) {
  const {
    apiBase,
    setDocumentTitle,
    previewDependencies,
  } = context;
  const [payload, setPayload] = useState<{
    shop: Shop;
    brandSite: BrandSiteConfig;
    products: Product[];
  } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    setDocumentTitle(payload?.shop.name || "品牌官网");
  }, [payload?.shop.name]);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const shop = params.get("shop") || "";
    const preview = (params.get("preview") || "").trim().replace(/[，,]+$/, "") === "1";
    const domain = window.location.hostname;
    const query = new URLSearchParams({ domain });
    if (shop) query.set("shop", shop);
    if (preview) query.set("preview", "1");
    fetch(`${apiBase}/api/brand-site?${query.toString()}`, { credentials: "include" })
      .then(async (response) => {
        const data = (await response.json().catch(() => ({}))) as {
          shop?: Shop;
          brandSite?: BrandSiteConfig;
          products?: Product[];
          error?: string;
        };
        if (!response.ok || !data.shop || !data.brandSite)
          throw new Error(data.error || "独立站暂不可访问");
        setPayload({
          shop: data.shop,
          brandSite: data.brandSite,
          products: data.products || [],
        });
      })
      .catch((reason: unknown) =>
        setError(reason instanceof Error ? reason.message : "独立站加载失败"),
      );
  }, []);
  if (error)
    return (
      <main className="public-brand-site-state">
        <h1>独立站暂不可访问</h1>
        <p>{error}</p>
        <a href="/">返回手作集</a>
      </main>
    );
  if (!payload)
    return (
      <main className="public-brand-site-state" aria-busy="true">
        <span />
        <p>正在加载店铺…</p>
      </main>
    );
  return (
    <main className="public-brand-site">
      <div className="public-brand-site-notice">
        <a href="/">手作集</a>
        <span>独立站</span>
      </div>
      <BrandSitePreview
        context={{
          brandSite: payload.brandSite,
          shop: payload.shop,
          products: payload.products,
          buyerFacing: true,
          ...previewDependencies,
        }}
      />
    </main>
  );
}

