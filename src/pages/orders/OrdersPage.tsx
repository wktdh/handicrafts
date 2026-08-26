import { lazy, Suspense, useState } from "react";
import { Truck } from "lucide-react";
import type {
  AfterSaleDraft,
  AfterSaleRequest,
  AppData,
  Order,
  OrderStatus,
  PaymentMethod,
  ProductReview,
  ReturnShipmentDraft,
  ReviewDraft,
} from "../../App";

function money(value: number) {
  return `$${value.toFixed(2)}`;
}

const LazyAfterSaleForm = lazy(() =>
  import("./OrderForms").then((module) => ({ default: module.AfterSaleForm })),
);
const LazyAfterSaleProgress = lazy(() =>
  import("./OrderForms").then((module) => ({ default: module.AfterSaleProgress })),
);
const LazyReturnShipmentForm = lazy(() =>
  import("./OrderForms").then((module) => ({ default: module.ReturnShipmentForm })),
);
const LazyReviewForm = lazy(() =>
  import("./OrderForms").then((module) => ({ default: module.ReviewForm })),
);
const LazyReviewFollowupForm = lazy(() =>
  import("./OrderForms").then((module) => ({ default: module.ReviewFollowupForm })),
);

export default function OrdersPage({
  data,
  orders,
  afterSales,
  reviews,
  onShipping,
  onReceive,
  onCancel,
  onPay,
  onReview,
  onFollowup,
  onAfterSale,
  onReturnShipment,
  compressImageForUpload,
  productListImageUrl,
  buyerProductCopy,
  buyerProductTerm,
  buyerOrderStatusLabel,
}: {
  data: AppData;
  orders: Order[];
  afterSales: AfterSaleRequest[];
  reviews: ProductReview[];
  onShipping: (id: string) => void;
  onReceive: (id: string) => void;
  onCancel: (id: string) => void;
  onPay: (id: string, method: PaymentMethod) => Promise<boolean>;
  onReview: (id: string, draft: ReviewDraft) => Promise<boolean>;
  onFollowup: (
    reviewIds: Array<string | number>,
    content: string,
  ) => Promise<boolean>;
  onAfterSale: (id: string, draft: AfterSaleDraft) => Promise<boolean>;
  onReturnShipment: (
    id: string | number,
    draft: ReturnShipmentDraft,
  ) => Promise<boolean>;
  compressImageForUpload: (file: File) => Promise<string>;
  productListImageUrl: (
    url: string | null | undefined,
    width: 160 | 400 | 800,
  ) => string | undefined;
  buyerProductCopy: (product: AppData["products"][number]) => { title: string };
  buyerProductTerm: (value: string) => string;
  buyerOrderStatusLabel: (status: string) => string;
}) {
  const [statusFilter, setStatusFilter] = useState("全部");
  const [afterSaleOrder, setAfterSaleOrder] = useState<Order | null>(null);
  const [reviewOrder, setReviewOrder] = useState<Order | null>(null);
  const [followupOrder, setFollowupOrder] = useState<Order | null>(null);
  const [returnShipmentRequest, setReturnShipmentRequest] =
    useState<AfterSaleRequest | null>(null);
  const visibleOrders = orders.filter(
    (order) => statusFilter === "全部" || order.status === statusFilter,
  );
  return (
    <div className="container page section">
      <div className="page-title">
        <div>
          <h1>Orders</h1>
          <p>View and manage your purchases.</p>
        </div>
      </div>
      <div className="order-filters">
        {[
          "全部",
          "待付款",
          "待发货",
          "待收货",
          "已完成",
          "已取消",
          "已退款",
        ].map((status) => (
          <button
            className={statusFilter === status ? "selected" : ""}
            key={status}
            onClick={() => setStatusFilter(status)}
          >
            {buyerOrderStatusLabel(status as OrderStatus | "全部" | "已退款")}
          </button>
        ))}
      </div>
      {visibleOrders.length ? (
        <div className="orders">
          {visibleOrders.map((order) => {
            const orderReviews = reviews.filter(
              (review) => review.orderId === order.id,
            );
            const orderAfterSale = afterSales.find(
              (request) => request.orderId === order.id,
            );
            return (
              <article
                className="order-card"
                data-testid="order-card"
                key={order.id}
              >
                <header>
                  <span>Order {order.id}</span>
                  <span>{order.createdAt}</span>
                  <span className={`status status-${order.status}`}>
                    {buyerOrderStatusLabel(order.status)}
                  </span>
                </header>
                {order.items.map((item) => {
                  const p = data.products.find((x) => x.id === item.productId);
                  return (
                    <div
                      className="order-product"
                      key={`${item.catalogId || item.productId}-${JSON.stringify(item.variants || {})}`}
                    >
                      {item.image || p?.image ? (
                        <img
                          src={productListImageUrl(item.image || p?.image, 160)}
                          alt=""
                        />
                      ) : (
                        <span />
                      )}
                      <div>
                        <b>{p ? buyerProductCopy(p).title : item.title || "Item"}</b>
                        <span>
                          Quantity {item.quantity}
                          {Object.keys(item.variants || {}).length > 0 && (
                            <small className="selected-specs">
                              {" "}
                              ·{" "}
                              {Object.entries(item.variants || {})
                                .map(
                                  ([name, value]) =>
                                    `${buyerProductTerm(name)}: ${buyerProductTerm(value)}`,
                                )
                                .join(" · ")}
                            </small>
                          )}
                        </span>
                      </div>
                      <strong>
                        {money(
                          (item.unitPrice || p?.price || 0) * item.quantity,
                        )}
                      </strong>
                    </div>
                  );
                })}
                <footer>
                  <span>
                    Total <b>{money(order.amount)}</b>
                    {order.shippingAmount || order.discountAmount ? (
                      <small className="order-amount-detail">
                        {" "}
                        Items {money(order.itemAmount || 0)} · Shipping{" "}
                        {money(order.shippingAmount || 0)} · Discount -
                        {money(order.discountAmount || 0)}
                      </small>
                    ) : null}
                    {order.payment?.status === "succeeded" && (
                      <small
                        data-testid="order-payment-confirmed"
                        className="order-amount-detail"
                      >
                        Paid ·{" "}
                        {order.payment.method === "alipay"
                          ? "Alipay"
                          : "Bank card"}
                        {order.payment.reference
                          ? ` · ${order.payment.reference}`
                          : ""}
                      </small>
                    )}
                  </span>
                  <div>
                    {(order.status === "运输中" ||
                      order.status === "待收货") && (
                      <button
                        className="secondary"
                        onClick={() => onShipping(order.id)}
                      >
                        <Truck size={16} />
                        Track shipment
                      </button>
                    )}
                    {order.status === "待收货" && (
                      <button
                        className="primary"
                        onClick={() => onReceive(order.id)}
                      >
                        Confirm delivery
                      </button>
                    )}
                    {order.status === "待付款" && (
                      <button
                        className="primary"
                        onClick={() =>
                          void onPay(
                            order.id,
                            order.payment?.method || "alipay",
                          )
                        }
                      >
                        Pay now
                      </button>
                    )}
                    {order.status === "待付款" && (
                      <button
                        className="secondary"
                        onClick={() => onCancel(order.id)}
                      >
                        Cancel order
                      </button>
                    )}
                    {order.status === "已完成" && !order.reviewed && (
                      <button
                        className="secondary"
                        onClick={() => setReviewOrder(order)}
                      >
                        Write a review
                      </button>
                    )}
                    {order.status === "已完成" && order.reviewed && (
                      <button
                        className="secondary"
                        disabled={!orderReviews.length}
                        onClick={() => setFollowupOrder(order)}
                      >
                        {orderReviews.some((review) => review.followup)
                          ? "Edit follow-up"
                          : "Add follow-up"}
                      </button>
                    )}
                    {order.status !== "待付款" &&
                      order.status !== "已取消" &&
                      !afterSales.some((item) => item.orderId === order.id) && (
                        <button
                          className="secondary"
                          onClick={() => setAfterSaleOrder(order)}
                        >
                          Request support
                        </button>
                      )}
                  </div>
                </footer>
                {orderAfterSale && (
                  <Suspense fallback={null}>
                  <LazyAfterSaleProgress
                    request={orderAfterSale}
                    onReturnShipment={() =>
                      setReturnShipmentRequest(orderAfterSale)
                    }
                  />
                  </Suspense>
                )}
              </article>
            );
          })}
        </div>
      ) : (
        <div className="empty">
          <h2>No orders yet</h2>
          <p>Your orders will appear here after you make a purchase.</p>
          <button className="primary" onClick={() => location.reload()}>
            Discover handmade
          </button>
        </div>
      )}
      {afterSaleOrder && (
        <Suspense fallback={null}>
        <LazyAfterSaleForm
          order={afterSaleOrder}
          compressImageForUpload={compressImageForUpload}
          onCancel={() => setAfterSaleOrder(null)}
          onSubmit={async (draft) => {
            if (await onAfterSale(afterSaleOrder.id, draft)) {
              setAfterSaleOrder(null);
            }
          }}
        />
        </Suspense>
      )}
      {reviewOrder && (
        <Suspense fallback={null}>
        <LazyReviewForm
          order={reviewOrder}
          compressImageForUpload={compressImageForUpload}
          onCancel={() => setReviewOrder(null)}
          onSubmit={async (draft) => {
            if (await onReview(reviewOrder.id, draft)) setReviewOrder(null);
          }}
        />
        </Suspense>
      )}
      {followupOrder && (
        <Suspense fallback={null}>
        <LazyReviewFollowupForm
          order={followupOrder}
          reviews={reviews.filter(
            (review) => review.orderId === followupOrder.id,
          )}
          onCancel={() => setFollowupOrder(null)}
          onSubmit={async (content) => {
            const orderReviewIds = reviews
              .filter((review) => review.orderId === followupOrder.id)
              .map((review) => review.id);
            if (
              orderReviewIds.length &&
              (await onFollowup(orderReviewIds, content))
            ) {
              setFollowupOrder(null);
            }
          }}
        />
        </Suspense>
      )}
      {returnShipmentRequest && (
        <Suspense fallback={null}>
        <LazyReturnShipmentForm
          request={returnShipmentRequest}
          onCancel={() => setReturnShipmentRequest(null)}
          onSubmit={async (draft) => {
            if (await onReturnShipment(returnShipmentRequest.id, draft)) {
              setReturnShipmentRequest(null);
            }
          }}
        />
        </Suspense>
      )}
    </div>
  );
}
