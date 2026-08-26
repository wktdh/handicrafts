// @ts-nocheck
import { useState, type FormEvent } from "react";
import { Menu, Search, ShoppingBag } from "lucide-react";
import shopBannerImage from "../../images/shop-banner.jpg";

function BrandSiteNewsletter({
  section,
  shopId,
  themeColor,
  apiBase,
}: {
  section: BrandSiteSection;
  shopId?: string;
  themeColor: string;
}) {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState("");
  const subscribe = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!/^\S+@\S+\.\S+$/.test(email.trim()))
      return setStatus("请输入正确的邮箱地址");
    if (!shopId) return setStatus("预览模式：公开后可接收订阅");
    try {
      const response = await fetch(`${apiBase}/api/brand-site/subscribers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ shopId, email: email.trim().toLowerCase() }),
      });
      const payload = (await response.json().catch(() => ({}))) as {
        error?: string;
      };
      if (!response.ok)
        throw new Error(payload.error || "订阅失败，请稍后重试");
      setStatus("订阅成功，感谢关注！");
      setEmail("");
    } catch (error) {
      setStatus(
        error instanceof Error ? error.message : "订阅失败，请稍后重试",
      );
    }
  };
  return (
    <div className="brand-site-preview-copy">
      <small>{section.label}</small>
      <h3>{section.title}</h3>
      <p>{section.content}</p>
      <form className="brand-site-newsletter-form" onSubmit={subscribe}>
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="请输入你的邮箱"
          aria-label="邮箱地址"
          required
        />
        <button
          type="submit"
          style={{ background: section.buttonColor || themeColor }}
        >
          {" "}
          {section.buttonLabel || "订阅"}
        </button>
      </form>
      {status && (
        <small className="brand-site-newsletter-status">{status}</small>
      )}
    </div>
  );
}

export default function BrandSitePreview({ context }: { context: Record<string, any> }) {
  const {
    brandSite,
    shop,
    products,
    selectedSectionId,
    selectedBrandLogo,
    onSelectSection,
    buyerFacing = false,
    apiBase,
    normalizeBrandSiteTemplate,
    ensureBrandSiteSections,
    productListImageUrl,
    bundledCatalogImages,
    bundledMediaImages,
    buyerProductCopy,
    money,
  } = context;
  const template = normalizeBrandSiteTemplate(brandSite.template);
  const siteName = brandSite.siteName || shop.name;
  const sections = ensureBrandSiteSections(brandSite.sections, template);
  const headerSection = sections.find((section) => section.id === "header");
  const announcementSection = sections.find(
    (section) => section.id === "announcement",
  );
  const collectionFor = (section: BrandSiteSection) => {
    const selected = new Set((section.productIds || []).map(String));
    return (
      selected.size
        ? products.filter((product) => selected.has(String(product.id)))
        : products
    ).slice(0, 3);
  };
  const navigationLabelsFor = (section: BrandSiteSection) =>
    section.navLabels?.length
      ? section.navLabels.filter((label) => label.trim())
      : ["作品", "关于", "联系"];
  const navigationTargetFor = (index: number) => {
    const configuredLink = headerSection?.navLinks?.[index]?.trim();
    if (configuredLink) return configuredLink;
    if (index === 0) return "#brand-site-collection";
    if (index === 1)
      return sections.some((item) => item.id === "story" && item.enabled)
        ? "#brand-site-story"
        : sections.some((item) => item.id === "maker" && item.enabled)
          ? "#brand-site-maker"
          : "#brand-site-columns";
    return "#brand-site-footer";
  };
  const columnDescriptionFor = (title: string) => {
    if (title.includes("选材")) return "挑选适合日常使用的材料。";
    if (title.includes("手工")) return "由创作者耐心完成每一道工序。";
    if (title.includes("包装")) return "认真包好每一件即将出发的作品。";
    return "用一段简短文字介绍这一项内容。";
  };
  const renderAnnouncement = (section: BrandSiteSection) => (
    <section
      id="brand-site-announcement"
      className={`brand-site-preview-section brand-site-preview-announcement ${selectedSectionId === "announcement" ? "is-selected" : ""}`}
      onPointerDown={(event) => {
        if (!onSelectSection) return;
        event.stopPropagation();
        onSelectSection("announcement");
      }}
      onClick={() => onSelectSection?.("announcement")}
      style={{
        ...(section.backgroundColor
          ? { backgroundColor: section.backgroundColor }
          : {}),
        ...(section.textColor ? { color: section.textColor } : {}),
      }}
    >
      <div className="brand-site-preview-copy">
        <span>{section.content || section.title}</span>
      </div>
    </section>
  );
  return (
    <section className={`brand-site-preview brand-site-preview-${template}`}>
      {announcementSection?.enabled && renderAnnouncement(announcementSection)}
      {headerSection?.enabled && (
        <section
          id="brand-site-header"
          className={`brand-site-preview-section brand-site-preview-header ${selectedSectionId === "header" ? "is-selected" : ""}`}
          onPointerDown={(event) => {
            if (!onSelectSection) return;
            event.stopPropagation();
            onSelectSection("header");
          }}
          onClick={() => onSelectSection?.("header")}
          style={{
            ...(headerSection.backgroundColor
              ? { backgroundColor: headerSection.backgroundColor }
              : {}),
            ...(headerSection.textColor
              ? { color: headerSection.textColor }
              : {}),
          }}
        >
          <header
            className={`brand-site-preview-nav ${selectedSectionId === "header" ? "is-selected" : ""}`}
            style={{
              borderColor: brandSite.themeColor,
              ...(headerSection.backgroundColor
                ? { backgroundColor: headerSection.backgroundColor }
                : {}),
            }}
          >
            <div
              className={`brand-site-preview-identity ${selectedBrandLogo ? "is-selected" : ""}`}
            >
              {brandSite.logoUrl && (
                <img src={brandSite.logoUrl} alt="站点 Logo" />
              )}
              <div>
                <b>{siteName}</b>
                {brandSite.tagline && <small>{brandSite.tagline}</small>}
              </div>
            </div>
            <nav className="brand-site-preview-links" aria-label="站内导航">
              {navigationLabelsFor(headerSection).map((label, index) => (
                <a key={`${label}-${index}`} href={navigationTargetFor(index)}>
                  {label}
                </a>
              ))}
            </nav>
            <div
              className="brand-site-preview-nav-actions"
              aria-label="站点工具"
            >
              <button
                type="button"
                className="brand-site-preview-menu-action"
                aria-label="打开导航菜单"
              >
                <Menu size={18} strokeWidth={1.7} />
              </button>
              <button type="button" aria-label="搜索">
                <Search size={17} strokeWidth={1.7} />
              </button>
              <button type="button" aria-label="购物袋">
                <ShoppingBag size={17} strokeWidth={1.7} />
              </button>
            </div>
          </header>
        </section>
      )}
      {sections
        .filter(
          (section) =>
            section.enabled &&
            section.id !== "header" &&
            section.id !== "announcement",
        )
        .map((section) => (
          <section
            key={section.id}
            id={`brand-site-${section.id}`}
            className={`brand-site-preview-section brand-site-preview-${section.id} ${section.id === "hero" ? `brand-site-preview-hero-position-${section.heroContentPosition || "center"}` : ""} ${selectedSectionId === section.id ? "is-selected" : ""}`}
            onPointerDown={(event) => {
              if (!onSelectSection) return;
              event.stopPropagation();
              onSelectSection(section.id);
            }}
            onClick={() => onSelectSection?.(section.id)}
            style={{
              ...(section.id === "hero"
                ? {
                    backgroundImage: `url(${section.imageUrl || shop.banner || shopBannerImage})`,
                  }
                : {}),
              ...(section.backgroundColor
                ? { backgroundColor: section.backgroundColor }
                : {}),
              ...(section.textColor ? { color: section.textColor } : {}),
            }}
          >
            {section.id === "collection" ? (
              <>
                <div className="brand-site-preview-copy">
                  <h3>{section.title}</h3>
                  <p>{section.content}</p>
                </div>
                <div className="brand-site-preview-products">
                  {collectionFor(section).map((product) => (
                    <article key={product.id}>
                      <img
                        src={
                          productListImageUrl(
                            bundledCatalogImages[product.catalogId || ""] ||
                              bundledMediaImages[product.image] ||
                              product.image,
                            400,
                          )
                        }
                        alt=""
                      />
                      <b>
                        {buyerFacing
                          ? buyerProductCopy(product).title
                          : product.title}
                      </b>
                      <span>{money(product.price)}</span>
                    </article>
                  ))}
                  {!collectionFor(section).length && (
                    <p>已上架作品会显示在这里</p>
                  )}
                </div>
                {section.buttonLabel && (
                  <span
                    className="brand-site-preview-button"
                    style={{
                      background: section.buttonColor || brandSite.themeColor,
                    }}
                  >
                    {section.buttonLabel}
                  </span>
                )}
              </>
            ) : section.id === "newsletter" ? (
              <BrandSiteNewsletter
                section={section}
                shopId={shop.analyticsShopId}
                themeColor={brandSite.themeColor}
                apiBase={apiBase}
              />
            ) : section.id === "image-text" ? (
              <>
                <div className="brand-site-preview-image-text-copy">
                  <small>{section.label}</small>
                  <h3>{section.title}</h3>
                  <p>{section.content}</p>
                  {section.buttonLabel && (
                    <span
                      className="brand-site-preview-button"
                      style={{
                        background: section.buttonColor || brandSite.themeColor,
                      }}
                    >
                      {section.buttonLabel}
                    </span>
                  )}
                </div>
                <div className="brand-site-preview-image-text-media">
                  {section.imageUrl ? (
                    <img src={section.imageUrl} alt="模块配图" />
                  ) : (
                    <div className="brand-site-preview-image-placeholder">
                      上传模块图片
                    </div>
                  )}
                </div>
              </>
            ) : section.id === "testimonials" ? (
              <div className="brand-site-preview-copy">
                <small>{section.label}</small>
                <h3>{section.title}</h3>
                <blockquote>“{section.content}”</blockquote>
              </div>
            ) : section.id === "faq" ? (
              <div className="brand-site-preview-copy">
                <small>{section.label}</small>
                <h3>{section.title}</h3>
                <details open>
                  <summary>制作、定制与配送说明</summary>
                  <p>{section.content}</p>
                </details>
              </div>
            ) : section.id === "columns" ? (
              <>
                <small className="brand-site-preview-columns-label">
                  {section.label}
                </small>
                <h3 className="brand-site-preview-columns-title">
                  {section.title}
                </h3>
                <div className="brand-site-preview-copy brand-site-preview-columns-copy">
                  {section.content
                    .split(/[·｜|]/)
                    .map((item) => item.trim())
                    .filter(Boolean)
                    .map((item, index) => (
                      <div
                        className="brand-site-preview-columns"
                        key={`${item}-${index}`}
                      >
                        <article>
                          <b>{item}</b>
                          <p>{columnDescriptionFor(item)}</p>
                        </article>
                      </div>
                    ))}
                </div>
              </>
            ) : (
              <div className="brand-site-preview-copy">
                <small>{section.label}</small>
                <h3>{section.title}</h3>
                <p>{section.content}</p>
                {section.buttonLabel && (
                  <span
                    className="brand-site-preview-button"
                    style={{
                      background: section.buttonColor || brandSite.themeColor,
                    }}
                  >
                    {section.buttonLabel}
                  </span>
                )}
              </div>
            )}
          </section>
        ))}
    </section>
  );
}

