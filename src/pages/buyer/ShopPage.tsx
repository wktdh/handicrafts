// @ts-nocheck
import { useRef } from "react";
import { Star } from "lucide-react";

export default function ShopPage({ context }: { context: Record<string, any> }) {
  const {
    shop,
    products,
    onOpen,
    onStudio,
    onImageUpload,
    preview = false,
    defaultAvatarImage,
    shopBannerImage,
    buyerShopName,
    buyerShopLocation,
    ProductGrid,
    Empty,
  } = context;
  const avatarInputRef = useRef<HTMLInputElement>(null);
  // Old development records stored Vite source paths such as
  // `/src/images/shop-banner.jpg`. They work only while running the dev
  // server, not from the production build, so treat them as missing media.
  const isLegacyBundledSourcePath = (url: unknown) =>
    typeof url === "string" && /^\/?src\/images\//.test(url);
  const avatar =
    shop.avatar && !isLegacyBundledSourcePath(shop.avatar)
      ? shop.avatar
      : defaultAvatarImage;
  const banner =
    shop.banner && !isLegacyBundledSourcePath(shop.banner)
      ? shop.banner
      : shopBannerImage;
  const shopName = buyerShopName(shop.name);
  const shopLocation = buyerShopLocation(shop.location);
  const hasAvatar = Boolean(avatar);
  const featuredIds = (shop.featuredProductIds || []).slice(0, 2);
  const featuredProducts = featuredIds
    .map((id) =>
      products.find(
        (product) => String(product.catalogId || product.id) === String(id),
      ),
    )
    .filter((product): product is Product => Boolean(product));
  const featuredKeys = new Set(featuredIds.map(String));
  const shopProducts = [
    ...featuredProducts,
    ...products.filter(
      (product) => !featuredKeys.has(String(product.catalogId || product.id)),
    ),
  ];
  const reviewCount = products.reduce(
    (total, product) => total + product.reviews,
    0,
  );
  const shopRating = reviewCount
    ? products.reduce(
        (total, product) => total + product.rating * product.reviews,
        0,
      ) / reviewCount
    : null;
  return (
    <div className={`shop-page${preview ? " shop-page-preview" : ""}`}>
      <section
        className={`shop-hero ${shop.status === "paused" ? "shop-hero-paused" : ""}`}
        style={{
          backgroundImage: `url(${banner})`,
        }}
      >
        <div className="container">
          {shop.status === "paused" && (
            <div className="shop-rest-sign" aria-label="Shop temporarily closed">
              <div
                className="shop-rest-chain shop-rest-chain-left"
                aria-hidden="true"
              >
                <i />
                <i />
                <i />
                <i />
              </div>
              <div
                className="shop-rest-chain shop-rest-chain-right"
                aria-hidden="true"
              >
                <i />
                <i />
                <i />
                <i />
              </div>
              <div className="shop-rest-sign-board">
                <b>TEMPORARILY CLOSED</b>
                <small>SHOP RESTING</small>
              </div>
            </div>
          )}
          <div className="shop-intro">
            <div className="shop-profile">
              {preview ? (
                <span className="shop-avatar-preview">
                  <img src={avatar} alt="Shop avatar" />
                </span>
              ) : (
                <label
                  className={`shop-avatar-editor ${hasAvatar ? "has-custom-avatar" : "needs-avatar"}`}
                >
                  <input
                    ref={avatarInputRef}
                    type="file"
                    accept="image/*"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      onImageUpload("avatar", file);
                      event.currentTarget.value = "";
                    }}
                  />
                  <img src={avatar} alt="Shop avatar" />
                  {!hasAvatar && <span>Upload avatar</span>}
                </label>
              )}
              <div>
                <h2>{shopName}</h2>
                <span>
                Ships from {shopLocation || "Not set"}{" \u00b7 "}Est. {shop.since}{" \u00b7 "}
                  {shop.status === "paused" ? " Temporarily closed" : " Open"}
                </span>
              </div>
            </div>
            <div>
              <b>{shop.followers.toLocaleString()}</b>
              <span>Followers</span>
            </div>
            <div>
              <b>
                {shopRating === null ? (
                  "No ratings yet"
                ) : (
                  <>
                    {shopRating.toFixed(1)} <Star size={16} fill="currentColor" />
                  </>
                )}
              </b>
              <span>Shop rating</span>
            </div>
          </div>
        </div>
      </section>
      {shop.status === "paused" && (
        <section className="shop-paused-notice">
          <div className="container">
            <b>Shop temporarily closed</b>
            <span>
              This maker is not accepting new orders right now. Existing orders
              will continue to be processed. Please leave a message if you need
              help.
            </span>
          </div>
        </section>
      )}
      {/*
        <section className="container section shop-intro-section">
        <div className="shop-intro">
          <div className="shop-profile">
            {preview ? (
              <span className="shop-avatar-preview">
                <img src={avatar} alt="Shop avatar" />
              </span>
            ) : (
              <label
                className={`shop-avatar-editor ${hasAvatar ? "has-custom-avatar" : "needs-avatar"}`}
              >
                <input
                  ref={avatarInputRef}
                  type="file"
                  accept="image/*"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    onImageUpload("avatar", file);
                    event.currentTarget.value = "";
                  }}
                />
                <img src={avatar} alt="Shop avatar" />
                {!hasAvatar && <span>Upload avatar</span>}
              </label>
            )}
            <div>
              <h2>{shopName}</h2>
              <span>
                Ships from {shopLocation || "Not set"} · Est. {shop.since} ·
                {shop.status === "paused" ? " Temporarily closed" : " Open"}
              </span>
            </div>
          </div>
          <div>
            <b>{shop.followers.toLocaleString()}</b>
            <span>Followers</span>
          </div>
          <div>
            <b>
              {shopRating === null ? (
                "No ratings yet"
              ) : (
                <>
                  {shopRating.toFixed(1)} <Star size={16} fill="currentColor" />
                </>
              )}
            </b>
            <span>Shop rating</span>
          </div>
        </div>
        </section>
      */}
      <section className="container section">
        <div className="section-heading">
          <h2>Shop collection</h2>
          <span>{products.length || 0} listed</span>
        </div>
        {products.length ? (
          <ProductGrid
            products={shopProducts}
            favorites={[]}
            onOpen={onOpen}
            onFavorite={() => {}}
            shopLayout
            placement="shop_catalog"
            featuredProductIds={featuredIds}
            openInNewTab
            localizedForSeller={false}
          />
        ) : (
          preview ? (
            <Empty title="No products listed yet" text="This shop does not have any public products yet." />
          ) : (
            <Empty
              title="No products listed yet"
              text="List your first handmade product from the shop workspace."
              action="List a product"
              onAction={onStudio}
              actionAsLink
            />
          )
        )}
      </section>
    </div>
  );
}

