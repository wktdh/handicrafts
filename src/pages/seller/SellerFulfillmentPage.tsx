// @ts-nocheck
import { lazy, Suspense } from "react";

const LazyShipmentForm = lazy(() =>
  import("../orders/OrderForms").then((module) => ({ default: module.ShipmentForm })),
);
const LazyShipmentEventForm = lazy(() =>
  import("../orders/OrderForms").then((module) => ({ default: module.ShipmentEventForm })),
);
const LazyAfterSaleDecisionForm = lazy(() =>
  import("../orders/OrderForms").then((module) => ({ default: module.AfterSaleDecisionForm })),
);

export default function SellerFulfillmentPage({ context }: { context: Record<string, any> }) {
  const {
    studioText,
    sellerOrders,
    data,
    money,
    StatusPill,
    setShipmentOrder,
    shipmentOrder,
    onShip,
    onShipping,
    setShipmentEventOrder,
    shipmentEventOrder,
    onAddShipmentEvent,
    afterSales,
    setAfterSaleDecision,
    afterSaleDecision,
    onReceiveReturn,
    onResolveAfterSale,
    productListImageUrl,
  } = context;
  return (
    <>
            <div className="studio-title">
              <div>
                <h1>{studioText("订单管理", "Orders")}</h1>
                <p>{studioText("处理买家的订单与发货", "Manage buyer orders and fulfillment")}</p>
              </div>
            </div>
            <section className="studio-panel">
              {sellerOrders.length ? (
                sellerOrders.map((o) => (
                  <div className="seller-order" key={o.id}>
                    <div className="seller-order-summary">
                      <div className="seller-order-summary-head">
                        <b>{o.id}</b>
                        <StatusPill
                          status={o.status}
                          className="seller-order-status"
                        />
                      </div>
                      <small>{money(o.amount)}</small>
                    </div>
                    <div className="seller-order-actions">
                      {o.status === "待发货" ? (
                        <button
                          data-testid={`seller-ship-${o.id}`}
                          className="primary"
                          onClick={() => setShipmentOrder(o)}
                        >
                          填写发货信息
                        </button>
                      ) : (
                        <>
                          <button
                            className="text-link seller-shipping-link"
                            type="button"
                            onClick={() => onShipping(o.id)}
                          >
                            查看物流
                          </button>
                          {o.shipment && (
                            <button
                              className="text-link seller-shipping-link"
                              type="button"
                              onClick={() => setShipmentEventOrder(o)}
                            >
                              更新物流
                            </button>
                          )}
                        </>
                      )}
                    </div>
                    <div className="seller-order-products">
                      {o.items.map((item) => {
                        const product = data.products.find(
                          (value) => value.id === item.productId,
                        );
                        return (
                          <div
                            className="seller-order-product"
                            key={`${o.id}-${item.catalogId || item.productId}-${JSON.stringify(item.variants || {})}`}
                          >
                            {item.image || product?.image ? (
                              <img
                                src={productListImageUrl(item.image || product?.image, 160)}
                                alt=""
                              />
                            ) : (
                              <span className="seller-order-image-placeholder" />
                            )}
                            <span>
                              <b>{item.title || product?.title || "作品"}</b>
                              <small>
                                数量 {item.quantity}
                                {Object.keys(item.variants || {}).length > 0 &&
                                  ` · ${Object.entries(item.variants || {})
                                    .map(([name, value]) => `${name}: ${value}`)
                                    .join(" · ")}`}
                              </small>
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))
              ) : (
                <p>目前没有来自你店铺的订单。</p>
              )}
            </section>
            {shipmentOrder && (
              <Suspense fallback={null}>
              <LazyShipmentForm
                order={shipmentOrder}
                onCancel={() => setShipmentOrder(null)}
                onSubmit={async (draft) => {
                  if (await onShip(shipmentOrder.id, draft))
                    setShipmentOrder(null);
                }}
              />
              </Suspense>
            )}
            {shipmentEventOrder && (
              <Suspense fallback={null}>
              <LazyShipmentEventForm
                order={shipmentEventOrder}
                onCancel={() => setShipmentEventOrder(null)}
                onSubmit={async (label, detail) => {
                  if (
                    await onAddShipmentEvent(
                      shipmentEventOrder.id,
                      label,
                      detail,
                    )
                  )
                    setShipmentEventOrder(null);
                }}
              />
              </Suspense>
            )}
            <section className="studio-panel after-sale-panel">
              <div className="panel-head">
                <h3>售后申请</h3>
                <span>{afterSales.length} 条待处理记录</span>
              </div>
              {afterSales.length ? (
                afterSales.map((request) => (
                  <div className="after-sale-row" key={request.id}>
                    <span>
                      <b>
                        {request.type} · {request.orderId}
                      </b>
                      <small>
                        {request.reason} · {request.createdAt}
                      </small>
                      <small>退款金额 {money(request.amount || 0)}</small>
                      {!!request.evidence?.length && (
                        <span className="after-sale-evidence">
                          {request.evidence.map((image) => (
                            <img key={image} src={image} alt="售后凭证" />
                          ))}
                        </span>
                      )}
                      {request.sellerResponse && (
                        <small>处理说明：{request.sellerResponse}</small>
                      )}
                    </span>
                    <StatusPill status={request.status as OrderStatus} />
                    {request.status === "待处理" && (
                      <div>
                        <button
                          className="secondary"
                          onClick={() =>
                            setAfterSaleDecision({ request, action: "reject" })
                          }
                        >
                          拒绝
                        </button>
                        <button
                          className="primary"
                          onClick={() =>
                            setAfterSaleDecision({ request, action: "approve" })
                          }
                        >
                          {request.type === "退货退款"
                            ? "同意退货"
                            : "同意退款"}
                        </button>
                      </div>
                    )}
                    {request.status === "待收货" && (
                      <button
                        className="primary"
                        onClick={() =>
                          setAfterSaleDecision({ request, action: "receive" })
                        }
                      >
                        确认收到退货
                      </button>
                    )}
                  </div>
                ))
              ) : (
                <p>暂时没有售后申请。</p>
              )}
            </section>
            {afterSaleDecision && (
              <Suspense fallback={null}>
              <LazyAfterSaleDecisionForm
                key={`${afterSaleDecision.request.id}-${afterSaleDecision.action}`}
                request={afterSaleDecision.request}
                action={afterSaleDecision.action}
                onCancel={() => setAfterSaleDecision(null)}
                onSubmit={async (response) => {
                  const completed =
                    afterSaleDecision.action === "receive"
                      ? await onReceiveReturn(
                          afterSaleDecision.request.id,
                          response,
                        )
                      : await onResolveAfterSale(
                          afterSaleDecision.request.id,
                          afterSaleDecision.action,
                          response,
                        );
                  if (completed) setAfterSaleDecision(null);
                }}
              />
              </Suspense>
            )}
    </>
  );
}

