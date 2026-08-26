// @ts-nocheck
import { useEffect, useState } from "react";
import { Heart, Minus, Plus, ShoppingBag, Star, Store } from "lucide-react";

export default function ProductDetail({ context }: { context: Record<string, any> }) {
  const {
    product,
    products,
    favorite,
    onFavorite,
    favorites,
    onOpen,
    shopFollowed,
    onToggleShopFollow,
    onAdd,
    onBuy,
    onContact,
    onReport,
    apiBase,
    compressImageForUpload,
    buyerProductCopy,
    buyerProductTerm,
    swatchColor,
    productListImageUrl,
    money,
    IconButton,
    ProductGrid,
  } = context;
  const copy = buyerProductCopy(product);
  const [quantity, setQuantity] = useState(1);
  const [showReport, setShowReport] = useState(false);
  const [reportReason, setReportReason] = useState("Illegal or prohibited content");
  const [reportDetail, setReportDetail] = useState("");
  const [reportEvidence, setReportEvidence] = useState<string[]>([]);
  const addReportEvidence = async (file?: File) => {
    if (!file || reportEvidence.length >= 6) return;
    try {
      const data = await compressImageForUpload(file);
      const response = await fetch(`${apiBase}/api/media`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data, mediaType: "image" }),
      });
      const payload = (await response.json()) as { url?: string };
      if (response.ok && payload.url)
        setReportEvidence((items) => [...items, payload.url!]);
    } catch {
      /* Ignore invalid evidence uploads. */
    }
  };
  const [productReviews, setProductReviews] = useState<ProductReview[]>([]);
  const gallery = product.images?.length ? product.images : [product.image];
  const [activeImage, setActiveImage] = useState(gallery[0]);
  const [selectedVariants, setSelectedVariants] = useState<
    Record<string, string>
  >(() =>
    Object.fromEntries(
      (product.variants || []).map((variant) => [
        variant.name,
        variant.values[0],
      ]),
    ),
  );
  useEffect(() => setActiveImage(gallery[0]), [product.id]);
  useEffect(
    () =>
      setSelectedVariants(
        product.skus?.find(
          (sku) => (sku.status ?? "active") === "active" && sku.stock > 0,
        )?.optionValues ||
          Object.fromEntries(
            (product.variants || []).map((variant) => [
              variant.name,
              variant.values[0],
            ]),
          ),
      ),
    [product.id],
  );
  useEffect(() => {
    if (!product.catalogId) {
      setProductReviews([]);
      return;
    }
    let active = true;
    fetch(
      `${apiBase}/api/catalog/products/${encodeURIComponent(product.catalogId)}/reviews`,
    )
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((payload: { reviews: ProductReview[] }) => {
        if (active) setProductReviews(payload.reviews);
      })
      .catch(() => {
        if (active) setProductReviews([]);
      });
    return () => {
      active = false;
    };
  }, [product.catalogId]);
  const selectedSku = product.skus?.find((sku) =>
    Object.entries(selectedVariants).every(
      ([name, value]) => sku.optionValues[name] === value,
    ),
  );
  const availableStock =
    selectedSku && (selectedSku.status ?? "active") === "active"
      ? selectedSku.stock
      : product.skus?.length
        ? 0
        : product.stock;
  const displayPrice = selectedSku?.price ?? product.price;
  const rating = productReviews.length
    ? productReviews.reduce((total, review) => total + review.rating, 0) /
      productReviews.length
    : product.rating;
  const reviewCount = productReviews.length || product.reviews;
  const relatedProducts = [
    ...products.filter(
      (item) =>
        item.id !== product.id &&
        item.category === product.category &&
        item.listed !== false,
    ),
    ...products.filter(
      (item) =>
        item.id !== product.id &&
        item.category !== product.category &&
        item.listed !== false,
    ),
  ].slice(0, 4);
  const isVariantValueAvailable = (name: string, value: string) => {
    if (!product.skus?.length) return true;
    const nextSelection = { ...selectedVariants, [name]: value };
    return product.skus.some(
      (sku) =>
        (sku.status ?? "active") === "active" &&
        sku.stock > 0 &&
        Object.entries(nextSelection).every(
          ([optionName, optionValue]) =>
            sku.optionValues[optionName] === optionValue,
        ),
    );
  };
  useEffect(() => {
    setQuantity((current) =>
      Math.max(1, Math.min(current, availableStock || 1)),
    );
  }, [availableStock, product.id]);
  return (
    <div className="container page section">
      <div className="detail-layout">
        <div className="detail-media">
          <div className="detail-image">
            <img src={activeImage} alt={copy.title} />
          </div>
          <div className="detail-gallery">
            {gallery.map((image, index) => (
              <button
                className={image === activeImage ? "active" : ""}
                onClick={() => setActiveImage(image)}
                key={image}
              >
                <img
                  src={productListImageUrl(image, 160)}
                  alt={`${copy.title} image ${index + 1}`}
                />
              </button>
            ))}
          </div>
          {product.video && (
            <video
              className="detail-video"
              src={product.video}
              controls
              preload="metadata"
            />
          )}
        </div>
        <div className="detail-info">
          <h2 className="detail-product-title">{copy.title}</h2>
          <div className="detail-rating">
            <Star size={17} fill="currentColor" />
            {rating.toFixed(1)} <u>{reviewCount} reviews</u>
          </div>
          <h2>{money(displayPrice)}</h2>
          {product.variants?.map((variant) => (
            <div className="variant-group" key={variant.name}>
              <span className="label">
                {buyerProductTerm(variant.name)}: {" "}
                <strong className="variant-selected-value">
                  {buyerProductTerm(selectedVariants[variant.name] || "")}
                </strong>
              </span>
              <div>
                {variant.values.map((value) => (
                  <button
                    className={`${selectedVariants[variant.name] === value ? "selected" : ""} ${
                      isVariantValueAvailable(variant.name, value)
                        ? ""
                        : "sold-out"
                    }`}
                    key={value}
                    disabled={!isVariantValueAvailable(variant.name, value)}
                    onClick={() => {
                      setSelectedVariants((current) => ({
                        ...current,
                        [variant.name]: value,
                      }));
                      const variantImage = variant.valueImages?.[value];
                      if (variantImage) setActiveImage(variantImage);
                    }}
                  >
                    {variant.valueImages?.[value] ? (
                      <img
                        className="variant-value-image"
                        src={productListImageUrl(variant.valueImages[value], 160)}
                        alt=""
                      />
                    ) : (
                      variant.name.includes("颜色") && (
                        <i style={{ backgroundColor: swatchColor(value) }} />
                      )
                    )}
                  </button>
                ))}
              </div>
            </div>
          ))}
          <div className="quantity-row">
            <span>Quantity</span>
            <div>
              <IconButton
                icon={Minus}
                label="Decrease quantity"
                onClick={() => setQuantity(Math.max(1, quantity - 1))}
              />
              <b>{quantity}</b>
              <IconButton
                icon={Plus}
                label="Increase quantity"
                onClick={() =>
                  setQuantity(Math.min(availableStock, quantity + 1))
                }
              />
            </div>
            <small className="quantity-stock">
              {availableStock > 0
                ? `${availableStock} in stock · Ships in 2–4 days`
                : "This option is sold out"}
            </small>
          </div>
          <div className="buy-row">
            <button
              data-testid="product-buy-now"
              className="primary grow"
              disabled={availableStock <= 0}
              onClick={() => onBuy(quantity, selectedVariants)}
            >
              Buy now
            </button>
            <button
              data-testid="product-add-cart"
              className="secondary grow"
              disabled={availableStock <= 0}
              onClick={() => onAdd(quantity, selectedVariants)}
            >
              <ShoppingBag size={18} />
              Add to bag
            </button>
            <IconButton
              icon={Heart}
              active={favorite}
              label="Save"
              onClick={() => onFavorite(product.id)}
            />
          </div>
          <div className="product-custom-report-row">
            {product.custom && (
              <p className="product-custom-notice">
                This item can be customized. Contact the maker to confirm the design, price, and delivery time.
              </p>
            )}
            <div className="content-report">
              <button
                className="text-link"
                type="button"
                onClick={() => setShowReport((value) => !value)}
              >
                Report
              </button>
            </div>
          </div>
          {showReport && (
            <div className="content-report-form">
              <div className="report-form">
                <select
                  value={reportReason}
                  onChange={(event) => setReportReason(event.target.value)}
                >
                  <option>Illegal or prohibited content</option>
                  <option>Copyright infringement or counterfeit</option>
                  <option>Misleading claims</option>
                  <option>Inappropriate content</option>
                </select>
                <textarea
                  value={reportDetail}
                  maxLength={200}
                  placeholder="Add details (optional)"
                  onChange={(event) => setReportDetail(event.target.value)}
                />
                <label>
                  Upload evidence (up to 6 images)
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    onChange={(event) => {
                      addReportEvidence(event.target.files?.[0]);
                      event.currentTarget.value = "";
                    }}
                  />
                </label>
                {reportEvidence.length > 0 && (
                  <small>{reportEvidence.length} images uploaded</small>
                )}
                <button
                  className="secondary"
                  type="button"
                  onClick={() => {
                    void onReport(
                      reportReason,
                      reportDetail,
                      reportEvidence,
                    ).then((submitted) => {
                      if (submitted) {
                        setShowReport(false);
                        setReportDetail("");
                        setReportEvidence([]);
                      }
                    });
                  }}
                >
                  Submit report
                </button>
              </div>
            </div>
          )}
          <div className="shop-mini">
            <Store size={22} />
            <div>
              <span>Independent maker · 300+ sales</span>
            </div>
            <div className="shop-mini-actions">
              <button
                className="shop-action-link"
                type="button"
                onClick={onToggleShopFollow}
              >
                {shopFollowed ? "Following" : "Follow shop"}
              </button>
              <button
                className="shop-action-link"
                type="button"
                onClick={onContact}
              >
                Contact maker
              </button>
            </div>
          </div>
          <div className="line" />
          <p className="label">About this piece</p>
          <p>{copy.description}</p>
          <p className="label">Materials</p>
          <div className="product-specs">
            <span>{copy.material}</span>
            {product.weightGrams && <span>Weight: {product.weightGrams} g</span>}
            {product.dimensions && <span>Dimensions: {product.dimensions}</span>}
            <span>Ships in 2–4 days</span>
          </div>
          {product.craftsmanship && (
            <>
              <p className="label">Craft technique</p>
              <p>{product.craftsmanship}</p>
            </>
          )}
        </div>
      </div>
      <section className="product-reviews">
        <div className="section-heading">
          <h2>Customer reviews</h2>
          <span>{reviewCount}</span>
        </div>
        {productReviews.length ? (
          <div className="product-review-list">
            {productReviews.map((review) => (
              <article key={review.id}>
                <header>
                  <b>{review.buyerName || "Anonymous customer"}</b>
                  <span>{review.createdAt}</span>
                </header>
                <div
                  className="product-review-stars"
                  aria-label={`${review.rating}-star rating`}
                >
                  {Array.from({ length: 5 }, (_, index) => (
                    <Star
                      key={index}
                      size={15}
                      fill={index < review.rating ? "currentColor" : "none"}
                    />
                  ))}
                </div>
                <p>{review.content}</p>
                {!!review.images?.length && (
                  <div className="review-images">
                    {review.images.map((image) => (
                      <img key={image} src={image} alt="Customer review image" />
                    ))}
                  </div>
                )}
                {review.followup && (
                  <p className="review-followup">Follow-up: {review.followup}</p>
                )}
                {review.sellerReply && (
                  <p className="seller-review-reply">
                    Maker reply: {review.sellerReply}
                  </p>
                )}
              </article>
            ))}
          </div>
        ) : (
          <p className="product-review-empty">No customer reviews yet.</p>
        )}
      </section>
      <section className="related-products">
        <div className="section-heading">
          <h2>Similar pieces</h2>
        </div>
        {relatedProducts.length ? (
          <ProductGrid
            products={relatedProducts}
            favorites={favorites}
            onOpen={onOpen}
            onFavorite={onFavorite}
            openInNewTab
            placement="related_products"
          />
        ) : (
          <p className="product-review-empty">暂无同类作品</p>
        )}
      </section>
    </div>
  );
}


