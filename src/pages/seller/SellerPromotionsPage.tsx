// @ts-nocheck
import { X } from "lucide-react";

export default function SellerPromotionsPage({ context }: { context: Record<string, any> }) {
  const {
    studioText,
    couponDraft,
    setCouponDraft,
    data,
    setData,
    saveShop,
    toast,
    money,
  } = context;
  return (
    <>
            <div className="studio-title">
              <div>
                <h1>{studioText("优惠管理", "Promotions")}</h1>
                <p>{studioText("创建并管理满减、满折、优惠券和限时活动", "Create and manage discounts, coupons, and timed offers")}</p>
              </div>
            </div>
            <section className="studio-panel settings-form promotions-form">
              <div className="promotion-mode-grid">
                {(
                  [
                    ["full_reduction", "满减", "满足金额后立减"],
                    ["full_discount", "满折", "满足金额后打折"],
                    ["coupon", "优惠券", "店铺自动优惠券"],
                    ["limited_time", "限时活动", "在指定时段生效"],
                  ] as const
                ).map(([type, title, description]) => (
                  <button
                    key={type}
                    type="button"
                    className={couponDraft.type === type ? "active" : ""}
                    onClick={() => setCouponDraft({ ...couponDraft, type })}
                  >
                    <b>{title}</b>
                    <small>{description}</small>
                  </button>
                ))}
              </div>
              <div className="coupon-editor promotion-editor">
                <label>
                  门槛金额
                  <input
                    type="number"
                    min="0.01"
                    value={couponDraft.threshold}
                    onChange={(event) =>
                      setCouponDraft({
                        ...couponDraft,
                        threshold: event.target.value,
                      })
                    }
                    placeholder="满多少元"
                  />
                </label>
                <label>
                  {couponDraft.type === "full_discount" ? "折扣" : "优惠金额"}
                  <input
                    type="number"
                    min="0.01"
                    max={
                      couponDraft.type === "full_discount" ? "10" : undefined
                    }
                    step={couponDraft.type === "full_discount" ? "0.1" : "0.01"}
                    value={couponDraft.value}
                    onChange={(event) =>
                      setCouponDraft({
                        ...couponDraft,
                        value: event.target.value,
                      })
                    }
                    placeholder={
                      couponDraft.type === "full_discount"
                        ? "例如：9 表示 9 折"
                        : "减多少元"
                    }
                  />
                </label>
                {couponDraft.type === "limited_time" && (
                  <div className="promotion-time-range">
                    <label>
                      开始时间
                      <input
                        type="datetime-local"
                        value={couponDraft.startsAt}
                        onChange={(event) =>
                          setCouponDraft({
                            ...couponDraft,
                            startsAt: event.target.value,
                          })
                        }
                      />
                    </label>
                    <label>
                      结束时间
                      <input
                        type="datetime-local"
                        value={couponDraft.endsAt}
                        onChange={(event) =>
                          setCouponDraft({
                            ...couponDraft,
                            endsAt: event.target.value,
                          })
                        }
                      />
                    </label>
                  </div>
                )}
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    const threshold = Number(couponDraft.threshold);
                    const value = Number(couponDraft.value);
                    if (!(threshold > 0) || !(value > 0))
                      return toast("请填写有效的优惠门槛和优惠数值");
                    if (couponDraft.type === "full_discount" && value > 10)
                      return toast("折扣请填写 0 到 10，例如 9 表示 9 折");
                    if (
                      couponDraft.type === "limited_time" &&
                      (!couponDraft.startsAt ||
                        !couponDraft.endsAt ||
                        Date.parse(couponDraft.startsAt) >=
                          Date.parse(couponDraft.endsAt))
                    )
                      return toast("请填写有效的活动起止时间");
                    const promotion: ShopPromotion = {
                      id: Date.now(),
                      type: couponDraft.type,
                      threshold,
                      ...(couponDraft.type === "full_discount"
                        ? { rate: value }
                        : { discount: value }),
                      ...(couponDraft.type === "limited_time"
                        ? {
                            startsAt: couponDraft.startsAt,
                            endsAt: couponDraft.endsAt,
                          }
                        : {}),
                    };
                    const nextShop = {
                      ...data.shop,
                      coupons: [...(data.shop.coupons || []), promotion],
                    };
                    setData((value) => ({ ...value, shop: nextShop }));
                    void saveShop(nextShop);
                    setCouponDraft({
                      type: couponDraft.type,
                      threshold: "",
                      value: "",
                      startsAt: "",
                      endsAt: "",
                    });
                  }}
                >
                  添加活动
                </button>
              </div>
              {!!data.shop.coupons?.length ? (
                <div className="coupon-list promotion-list">
                  {data.shop.coupons.map((coupon) => {
                    const type = coupon.type || "full_reduction";
                    const title =
                      type === "full_discount"
                        ? "满折"
                        : type === "coupon"
                          ? "优惠券"
                          : type === "limited_time"
                            ? "限时活动"
                            : "满减";
                    const benefit =
                      type === "full_discount"
                        ? `满 ${money(coupon.threshold)} 打 ${coupon.rate || 0} 折`
                        : `满 ${money(coupon.threshold)} 减 ${money(coupon.discount || 0)}`;
                    return (
                      <article key={coupon.id}>
                        <div>
                          <b>{title}</b>
                          <span>{benefit}</span>
                          {type === "limited_time" && (
                            <small>
                              {coupon.startsAt?.replace("T", " ")} 至{" "}
                              {coupon.endsAt?.replace("T", " ")}
                            </small>
                          )}
                        </div>
                        <button
                          type="button"
                          title={`删除${title}`}
                          aria-label={`删除${title}`}
                          onClick={() => {
                            const nextShop = {
                              ...data.shop,
                              coupons: (data.shop.coupons || []).filter(
                                (item) => item.id !== coupon.id,
                              ),
                            };
                            setData((value) => ({ ...value, shop: nextShop }));
                            void saveShop(nextShop);
                          }}
                        >
                          <X size={14} />
                        </button>
                      </article>
                    );
                  })}
                </div>
              ) : (
                <p>还没有创建优惠活动。</p>
              )}
            </section>
    </>
  );
}

