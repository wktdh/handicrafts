import { useEffect } from "react";
import { ChevronRight, Truck, X } from "lucide-react";

type Order = {
  status: string;
  shipment?: {
    carrier: string;
    trackingNo: string;
    trackingPhoneLast4?: string;
    events: { time: string; label: string; detail: string }[];
  };
};
function shipmentTrackingLink(carrier: string, trackingNo: string) {
  const number = encodeURIComponent(trackingNo.trim());
  const normalizedCarrier = carrier.trim().toLowerCase();
  const official = (url: string, requiresPhoneLast4 = false) => ({ url, official: true, requiresPhoneLast4 });
  if (normalizedCarrier.includes("dhl")) return official(`https://www.dhl.com/global-en/home/tracking.html?tracking-id=${number}`);
  if (normalizedCarrier.includes("fedex")) return official(`https://www.fedex.com/fedextrack/?trknbr=${number}`);
  if (normalizedCarrier.includes("ups")) return official(`https://www.ups.com/track?tracknum=${number}`);
  if (normalizedCarrier.includes("usps")) return official(`https://tools.usps.com/go/TrackConfirmAction?tLabels=${number}`);
  if (normalizedCarrier.includes("sf express") || carrier.includes("顺丰")) return official(`https://www.sf-express.com/cn/sc/dynamic_function/waybill/#search/bill-number/${number}`, true);
  return { url: `https://www.17track.net/en/track#nums=${number}`, official: false, requiresPhoneLast4: false };
}

export default function ShippingModal({
  order,
  onClose,
}: {
  order?: Order;
  onClose: () => void;
}) {
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return (
    <div
      className="shipping-modal-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="shipping-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="shipping-modal-title"
      >
        <header>
          <h2 id="shipping-modal-title">Shipment details</h2>
          <button type="button" className="icon-button" aria-label="Close shipment details" onClick={onClose}><X size={20} /></button>
        </header>
        {!order?.shipment ? (
          <div className="shipping-modal-empty">
            <Truck size={28} />
            <b>No shipment details yet</b>
            <p>Carrier and tracking updates will appear here once the maker ships your order.</p>
          </div>
        ) : (
          <section className="shipping-card">
            <div className="shipping-head">
              <span className="truck-circle">
                <Truck size={25} />
              </span>
              <div>
                <b>{order.status === "已完成" ? "Delivered" : "In transit"}</b>
                <p>
                  {order.shipment.carrier} · {order.shipment.trackingNo}
                </p>
              </div>
            </div>
            {(() => {
              const tracking = shipmentTrackingLink(
                order.shipment.carrier,
                order.shipment.trackingNo,
              );
              return (
                <div className="shipping-tracking-actions">
                  <a
                    className="primary shipping-tracking-link"
                    href={tracking.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {tracking.official
                        ? `Track with ${order.shipment.carrier}`
                        : "Use international tracking"}
                    <ChevronRight size={16} />
                  </a>
                  {tracking.requiresPhoneLast4 &&
                    order.shipment.trackingPhoneLast4 && (
                      <span className="shipping-phone-hint">
                        To check tracking updates, enter this 4-digit code:
                        {order.shipment.trackingPhoneLast4}
                      </span>
                    )}
                </div>
              );
            })()}
            <div className="timeline">
              {order.shipment.events.map((event, index) => (
                <div className="timeline-item" key={event.time + index}>
                  <i />
                  <div>
                    <b>{event.label}</b>
                    <p>{event.detail}</p>
                    <time>{event.time}</time>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
      </section>
    </div>
  );
}

