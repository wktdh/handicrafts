import { useEffect, useState, type FormEvent } from "react";
import { ImagePlus, Star, X } from "lucide-react";
import type {
  AfterSaleDraft,
  AfterSaleRequest,
  Order,
  OrderStatus,
  ProductReview,
  ReturnShipmentDraft,
  ReviewDraft,
  ShipmentDraft,
} from "../../App";

function money(value: number) {
  return `$${value.toFixed(2)}`;
}

const buyerOrderStatusLabels: Record<string, string> = {
  "待付款": "Awaiting payment",
  "待发货": "Preparing shipment",
  "运输中": "In transit",
  "待收货": "Delivered",
  "已完成": "Complete",
  "已取消": "Cancelled",
  "待处理": "Under review",
  "待退货": "Awaiting return",
  "已同意": "Approved",
  "已拒绝": "Declined",
  "已退款": "Refunded",
};

export function StatusPill({ status, className = "" }: { status: OrderStatus; className?: string }) {
  return <span className={`status status-${status} ${className}`.trim()}>{buyerOrderStatusLabels[status] || status}</span>;
}

export function AfterSaleForm({
  order,
  onSubmit,
  onCancel,
  compressImageForUpload = async () => {
    throw new Error("Image upload is unavailable");
  },
}: {
  order: Order;
  onSubmit: (draft: AfterSaleDraft) => Promise<void>;
  onCancel: () => void;
  compressImageForUpload?: (file: File) => Promise<string>;
}) {
  const [type, setType] = useState<AfterSaleDraft["type"]>("refund");
  const [amount, setAmount] = useState(String(order.amount));
  const [reason, setReason] = useState("");
  const [evidence, setEvidence] = useState<string[]>([]);
  const [error, setError] = useState("");
  const canSubmit =
    Number(amount) > 0 && Number(amount) <= order.amount && !!reason.trim();

  const addEvidence = async (files: FileList | null) => {
    if (!files?.length) return;
    const imageFiles = Array.from(files).filter((file) =>
      file.type.startsWith("image/"),
    );
    if (!imageFiles.length) {
      setError("Please select image files only");
      return;
    }
    const available = Math.max(0, 6 - evidence.length);
    const selected = imageFiles.slice(0, available);
    if (!selected.length) {
      setError("You can upload up to 6 evidence images");
      return;
    }
    try {
      const images = await Promise.all(
        selected.map((file) => compressImageForUpload(file)),
      );
      setEvidence((items) => [...items, ...images]);
      setError(
        imageFiles.length > selected.length ? "You can upload up to 6 evidence images" : "",
      );
    } catch {
      setError("The image could not be read. Please choose it again.");
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const requestedAmount = Number(amount);
    if (!Number.isFinite(requestedAmount) || requestedAmount <= 0) {
      setError("Enter a valid refund amount");
      return;
    }
    if (requestedAmount > order.amount) {
      setError("The refund amount cannot exceed the order total");
      return;
    }
    if (!reason.trim()) {
      setError("Tell us why you need support");
      return;
    }
    await onSubmit({
      type,
      amount: requestedAmount,
      reason: reason.trim(),
      evidence,
    });
  };
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [onCancel]);

  return (
    <div
      className="after-sale-form-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <form
        data-testid="after-sale-form"
        className="after-sale-form after-sale-form-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="after-sale-form-title"
        onSubmit={submit}
      >
        <div className="after-sale-form-head">
          <div>
            <h2 id="after-sale-form-title">Request support</h2>
            <p>
              Order {order.id} · Paid {money(order.amount)}
            </p>
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="Close support request"
            title="Close"
            onClick={onCancel}
          >
            <X size={18} />
          </button>
        </div>
        <div
          className="after-sale-type"
          role="radiogroup"
          aria-label="Support request type"
        >
          <label className={type === "refund" ? "selected" : ""}>
            <input
              type="radio"
              name="after-sale-type"
              checked={type === "refund"}
              onChange={() => setType("refund")}
            />
            Refund only
          </label>
          <label className={type === "return_refund" ? "selected" : ""}>
            <input
              type="radio"
              name="after-sale-type"
              checked={type === "return_refund"}
              onChange={() => setType("return_refund")}
            />
            Return and refund
          </label>
        </div>
        <label className="after-sale-field">
          <span>Refund amount</span>
          <input
            data-testid="after-sale-amount"
            type="number"
            min="0.01"
            max={order.amount}
            step="0.01"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
          />
        </label>
        <label className="after-sale-field">
          <span>Reason</span>
          <textarea
            data-testid="after-sale-reason"
            value={reason}
            maxLength={300}
            placeholder="Tell us what went wrong"
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
        <div className="after-sale-field">
          <span>
            Evidence images <small>Up to 6</small>
          </span>
          <div className="after-sale-evidence-editor">
            {evidence.map((image, index) => (
              <div className="after-sale-evidence-item" key={image}>
                <img src={image} alt={`Evidence image ${index + 1}`} />
                <button
                  type="button"
                  aria-label={`Remove evidence image ${index + 1}`}
                  title="Remove image"
                  onClick={() =>
                    setEvidence((items) =>
                      items.filter((_, itemIndex) => itemIndex !== index),
                    )
                  }
                >
                  <X size={14} />
                </button>
              </div>
            ))}
            {evidence.length < 6 && (
              <label className="after-sale-evidence-upload">
                <ImagePlus size={20} />
                <span>Add images</span>
                <input
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={(event) => {
                    void addEvidence(event.target.files);
                    event.target.value = "";
                  }}
                />
              </label>
            )}
          </div>
        </div>
        {error && (
          <p className="after-sale-error" role="alert">
            {error}
          </p>
        )}
        <div className="after-sale-actions">
          <button className="secondary" type="button" onClick={onCancel}>
            Cancel
          </button>
          <button
            data-testid="after-sale-submit"
            className="primary"
            type="submit"
            disabled={!canSubmit}
          >
            Submit request
          </button>
        </div>
      </form>
    </div>
  );
}

function ReturnContactDetails({ request }: { request: AfterSaleRequest }) {
  const hasContact = !!(
    request.returnRecipientName ||
    request.returnRecipientPhone ||
    request.returnAddress
  );
  if (!hasContact)
    return <p className="return-address">Please contact the maker to confirm return details.</p>;
  return (
    <dl className="return-contact-details">
      {request.returnRecipientName && (
        <div>
          <dt>Recipient</dt>
          <dd>{request.returnRecipientName}</dd>
        </div>
      )}
      {request.returnRecipientPhone && (
        <div>
          <dt>Phone</dt>
          <dd>{request.returnRecipientPhone}</dd>
        </div>
      )}
      <div className="return-contact-address">
        <dt>Address</dt>
        <dd>{request.returnAddress || "Please contact the maker to confirm the return address."}</dd>
      </div>
    </dl>
  );
}

export function AfterSaleProgress({
  request,
  onReturnShipment,
}: {
  request: AfterSaleRequest;
  onReturnShipment: () => void;
}) {
  return (
    <section className="after-sale-progress">
      <div className="after-sale-progress-head">
        <div>
          <b>Support progress · {request.type === "退款" ? "Refund" : "Return & refund"}</b>
          <span>
            Refund amount {money(request.amount || 0)} · {request.currency || "USD"} · locked rate {request.exchangeRate || "1.00000000"} USD/USD
          </span>
        </div>
        <StatusPill status={request.status as OrderStatus} />
      </div>
      {request.sellerResponse && (
        <p className="after-sale-response">
          Maker response: {request.sellerResponse}
        </p>
      )}
      {request.refundStatus === "recorded" && (
        <p className="after-sale-response">
          Refund is recorded in the USD settlement ledger. The payment-provider refund will be initiated after payment integration is enabled.
        </p>
      )}
      {request.returnShipment && (
        <p className="after-sale-shipment">
          Return shipment: {request.returnShipment.carrier} ·{" "}
          {request.returnShipment.trackingNo}
        </p>
      )}
      {request.timeline?.length ? (
        <ol className="after-sale-timeline">
          {request.timeline.map((event, index) => (
            <li key={`${event.time}-${index}`}>
              <i />
              <div>
                <b>{event.label}</b>
                <span>{event.detail}</span>
                <time>{event.time}</time>
              </div>
            </li>
          ))}
        </ol>
      ) : null}
      {request.type === "退货退款" && request.status === "待退货" && (
        <div className="after-sale-return-action">
          <ReturnContactDetails request={request} />
          <button className="primary" onClick={onReturnShipment}>
            Add return shipment
          </button>
        </div>
      )}
    </section>
  );
}

export function ReturnShipmentForm({
  request,
  onSubmit,
  onCancel,
}: {
  request: AfterSaleRequest;
  onSubmit: (draft: ReturnShipmentDraft) => Promise<void>;
  onCancel: () => void;
}) {
  const [carrier, setCarrier] = useState("");
  const [trackingNo, setTrackingNo] = useState("");
  return (
    <form
      className="after-sale-form return-shipment-form"
      onSubmit={async (event) => {
        event.preventDefault();
        if (!carrier.trim() || !trackingNo.trim()) return;
        await onSubmit({
          carrier: carrier.trim(),
          trackingNo: trackingNo.trim(),
        });
      }}
    >
      <div className="after-sale-form-head">
        <div>
          <h2>Add return shipment</h2>
          <p>Refund amount {money(request.amount || 0)}</p>
        </div>
        <button
          className="icon-button"
          type="button"
          aria-label="Close return shipment form"
          title="Close"
          onClick={onCancel}
        >
          <X size={18} />
        </button>
      </div>
      <ReturnContactDetails request={request} />
      <label className="after-sale-field">
        <span>Carrier</span>
        <input
          value={carrier}
          maxLength={40}
          placeholder="e.g. DHL"
          onChange={(event) => setCarrier(event.target.value)}
        />
      </label>
      <label className="after-sale-field">
        <span>Tracking number</span>
        <input
          value={trackingNo}
          maxLength={60}
          placeholder="Enter the return tracking number"
          onChange={(event) => setTrackingNo(event.target.value)}
        />
      </label>
      <div className="after-sale-actions">
        <button className="secondary" type="button" onClick={onCancel}>
          Cancel
        </button>
        <button
          className="primary"
          type="submit"
          disabled={!carrier.trim() || !trackingNo.trim()}
        >
          Submit shipment
        </button>
      </div>
    </form>
  );
}

export function AfterSaleDecisionForm({
  request,
  action,
  onSubmit,
  onCancel,
}: {
  request: AfterSaleRequest;
  action: "approve" | "reject" | "receive";
  onSubmit: (response: string) => Promise<void>;
  onCancel: () => void;
}) {
  const defaultResponse =
    action === "reject"
      ? ""
      : action === "receive"
        ? "已确认收到退回作品，退款已完成"
        : request.type === "退货退款"
          ? "同意退货退款，请按退货地址寄回作品"
          : "已同意退款，退款已完成";
  const [response, setResponse] = useState(defaultResponse);
  const title =
    action === "reject"
      ? "拒绝售后申请"
      : action === "receive"
        ? "确认收到退货"
        : request.type === "退货退款"
          ? "同意退货退款"
          : "同意退款";
  return (
    <form
      className="studio-panel after-sale-decision-form"
      onSubmit={async (event) => {
        event.preventDefault();
        if (!response.trim()) return;
        await onSubmit(response.trim());
      }}
    >
      <div className="panel-head">
        <h3>{title}</h3>
        <button
          className="icon-button"
          type="button"
          aria-label="关闭售后处理表单"
          title="关闭"
          onClick={onCancel}
        >
          <X size={18} />
        </button>
      </div>
      <p>
        订单 {request.orderId} · 退款金额 {money(request.amount || 0)}
      </p>
      {action === "approve" && request.type === "退货退款" && (
        <>
          <p className="return-address">买家会看到以下退货信息：</p>
          <ReturnContactDetails request={request} />
        </>
      )}
      {action === "receive" && request.returnShipment && (
        <p className="return-address">
          退回物流：{request.returnShipment.carrier} ·{" "}
          {request.returnShipment.trackingNo}
        </p>
      )}
      <label>
        {action === "reject" ? "拒绝原因" : "处理说明"}
        <textarea
          value={response}
          maxLength={300}
          placeholder={
            action === "reject" ? "请说明拒绝原因" : "填写给买家的处理说明"
          }
          onChange={(event) => setResponse(event.target.value)}
        />
      </label>
      <div className="after-sale-actions">
        <button className="secondary" type="button" onClick={onCancel}>
          取消
        </button>
        <button className="primary" type="submit" disabled={!response.trim()}>
          {action === "reject"
            ? "确认拒绝"
            : action === "receive"
              ? "确认收货并退款"
              : "确认处理"}
        </button>
      </div>
    </form>
  );
}

export function ReviewForm({
  order,
  onSubmit,
  onCancel,
  compressImageForUpload = async () => {
    throw new Error("Image upload is unavailable");
  },
}: {
  order: Order;
  onSubmit: (draft: ReviewDraft) => Promise<void>;
  onCancel: () => void;
  compressImageForUpload?: (file: File) => Promise<string>;
}) {
  const [rating, setRating] = useState(5);
  const [content, setContent] = useState("");
  const [images, setImages] = useState<string[]>([]);
  const [error, setError] = useState("");

  const addImages = async (files: FileList | null) => {
    if (!files?.length) return;
    const selectedFiles = Array.from(files).filter((file) =>
      file.type.startsWith("image/"),
    );
    if (!selectedFiles.length) {
      setError("Please select image files only");
      return;
    }
    const available = Math.max(0, 6 - images.length);
    const filesToRead = selectedFiles.slice(0, available);
    if (!filesToRead.length) {
      setError("You can upload up to 6 review images");
      return;
    }
    try {
      const nextImages = await Promise.all(
        filesToRead.map((file) => compressImageForUpload(file)),
      );
      setImages((value) => [...value, ...nextImages]);
      setError(
        selectedFiles.length > filesToRead.length
            ? "You can upload up to 6 review images"
          : "",
      );
    } catch {
      setError("The image could not be read. Please choose it again.");
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!content.trim()) {
      setError("Write a review before submitting");
      return;
    }
    await onSubmit({ rating, content: content.trim(), images });
  };

  return (
    <form data-testid="review-form" className="review-form" onSubmit={submit}>
      <div className="review-form-head">
        <div>
          <h2>Review your item</h2>
          <p>Order {order.id}</p>
        </div>
        <button
          className="icon-button"
          type="button"
          aria-label="Close review form"
          title="Close"
          onClick={onCancel}
        >
          <X size={18} />
        </button>
      </div>
      <div className="review-field">
        <span>Overall rating</span>
        <div className="review-rating" role="radiogroup" aria-label="Overall rating">
          {[1, 2, 3, 4, 5].map((value) => (
            <button
              className={value <= rating ? "selected" : ""}
              key={value}
              type="button"
              aria-label={`${value} stars`}
              aria-pressed={value === rating}
              onClick={() => setRating(value)}
            >
              <Star size={26} fill="currentColor" />
            </button>
          ))}
          <b>{rating} stars</b>
        </div>
      </div>
      <label className="review-field">
        <span>Your review</span>
        <textarea
          data-testid="review-content"
          value={content}
          maxLength={500}
          placeholder="Share how the piece feels and how it fits into your day"
          onChange={(event) => setContent(event.target.value)}
        />
      </label>
      <div className="review-field">
        <span>
          Review images <small>Up to 6</small>
        </span>
        <div className="review-image-editor">
          {images.map((image, index) => (
            <div className="review-image-item" key={image}>
              <img src={image} alt={`Review image ${index + 1}`} />
              <button
                type="button"
                aria-label={`Remove review image ${index + 1}`}
                title="Remove image"
                onClick={() =>
                  setImages((items) =>
                    items.filter((_, itemIndex) => itemIndex !== index),
                  )
                }
              >
                <X size={14} />
              </button>
            </div>
          ))}
          {images.length < 6 && (
            <label className="review-image-upload">
              <ImagePlus size={20} />
              <span>Add images</span>
              <input
                type="file"
                accept="image/*"
                multiple
                onChange={(event) => {
                  void addImages(event.target.files);
                  event.target.value = "";
                }}
              />
            </label>
          )}
        </div>
      </div>
      {error && (
        <p className="review-form-error" role="alert">
          {error}
        </p>
      )}
      <div className="review-form-actions">
        <button className="secondary" type="button" onClick={onCancel}>
          Cancel
        </button>
        <button
          data-testid="review-submit"
          className="primary"
          type="submit"
          disabled={!content.trim()}
        >
          Submit review
        </button>
      </div>
    </form>
  );
}

export function ReviewFollowupForm({
  order,
  reviews,
  onSubmit,
  onCancel,
}: {
  order: Order;
  reviews: ProductReview[];
  onSubmit: (content: string) => Promise<void>;
  onCancel: () => void;
}) {
  const [content, setContent] = useState(
    reviews.find((review) => review.followup)?.followup || "",
  );
  return (
    <form
      className="review-form review-followup-form"
      onSubmit={async (event) => {
        event.preventDefault();
        if (!content.trim()) return;
        await onSubmit(content.trim());
      }}
    >
      <div className="review-form-head">
        <div>
          <h2>Add a follow-up</h2>
          <p>Order {order.id}</p>
        </div>
        <button
          className="icon-button"
          type="button"
          aria-label="Close follow-up form"
          title="Close"
          onClick={onCancel}
        >
          <X size={18} />
        </button>
      </div>
      <label className="review-field">
        <span>Follow-up</span>
        <textarea
          value={content}
          maxLength={500}
          placeholder="Add thoughts after using your item"
          onChange={(event) => setContent(event.target.value)}
        />
      </label>
      <div className="review-form-actions">
        <button className="secondary" type="button" onClick={onCancel}>
          Cancel
        </button>
        <button className="primary" type="submit" disabled={!content.trim()}>
          Submit follow-up
        </button>
      </div>
    </form>
  );
}

export function ShipmentForm({
  order,
  onSubmit,
  onCancel,
}: {
  order: Order;
  onSubmit: (draft: ShipmentDraft) => Promise<void>;
  onCancel: () => void;
}) {
  const [carrier, setCarrier] = useState("");
  const [trackingNo, setTrackingNo] = useState("");
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [onCancel]);
  return (
    <div
      className="shipment-form-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <form
        data-testid="shipment-form"
        className="studio-panel shipment-form shipment-form-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="shipment-form-title"
        onSubmit={async (event) => {
          event.preventDefault();
          if (carrier.trim() && trackingNo.trim())
            await onSubmit({
              carrier: carrier.trim(),
              trackingNo: trackingNo.trim(),
            });
        }}
      >
        <div className="panel-head">
          <h3 id="shipment-form-title">填写发货信息</h3>
          <button
            className="icon-button"
            type="button"
            aria-label="关闭发货表单"
            title="关闭"
            onClick={onCancel}
          >
            <X size={18} />
          </button>
        </div>
        <p>
          订单 {order.id} · {money(order.amount)}
        </p>
        <label>
          快递公司
          <input
            data-testid="shipment-carrier"
            value={carrier}
            maxLength={40}
            placeholder="例如：顺丰速运"
            onChange={(event) => setCarrier(event.target.value)}
          />
        </label>
        <label>
          运单号
          <input
            data-testid="shipment-tracking"
            value={trackingNo}
            maxLength={60}
            placeholder="请输入快递单号"
            onChange={(event) => setTrackingNo(event.target.value)}
          />
        </label>
        <div className="after-sale-actions">
          <button className="secondary" type="button" onClick={onCancel}>
            取消
          </button>
          <button
            data-testid="shipment-submit"
            className="primary"
            type="submit"
            disabled={!carrier.trim() || !trackingNo.trim()}
          >
            确认发货
          </button>
        </div>
      </form>
    </div>
  );
}

export function ShipmentEventForm({
  order,
  onSubmit,
  onCancel,
}: {
  order: Order;
  onSubmit: (label: string, detail: string) => Promise<void>;
  onCancel: () => void;
}) {
  const [label, setLabel] = useState("");
  const [detail, setDetail] = useState("");
  return (
    <form
      className="studio-panel shipment-form"
      onSubmit={async (event) => {
        event.preventDefault();
        if (label.trim()) await onSubmit(label.trim(), detail.trim());
      }}
    >
      <div className="panel-head">
        <h3>更新物流节点</h3>
        <button
          className="icon-button"
          type="button"
          aria-label="关闭物流表单"
          title="关闭"
          onClick={onCancel}
        >
          <X size={18} />
        </button>
      </div>
      <p>
        {order.shipment?.carrier} · {order.shipment?.trackingNo}
      </p>
      <label>
        物流状态
        <input
          value={label}
          maxLength={60}
          placeholder="例如：包裹已到达杭州转运中心"
          onChange={(event) => setLabel(event.target.value)}
        />
      </label>
      <label>
        补充说明
        <input
          value={detail}
          maxLength={120}
          placeholder="可选"
          onChange={(event) => setDetail(event.target.value)}
        />
      </label>
      <div className="after-sale-actions">
        <button className="secondary" type="button" onClick={onCancel}>
          取消
        </button>
        <button className="primary" type="submit" disabled={!label.trim()}>
          更新物流
        </button>
      </div>
    </form>
  );
}
