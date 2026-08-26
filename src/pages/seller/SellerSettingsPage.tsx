// @ts-nocheck
import shopAvatarImage from "../../images/shop-avatar.jpg";
import shopBannerImage from "../../images/shop-banner.jpg";

export default function SellerSettingsPage({ context }: { context: Record<string, any> }) {
  const {
    studioText,
    data,
    setData,
    chooseShopImage,
    returnPolicy,
    updateReturnPolicy,
    saveShop,
  } = context;
  return (
    <>
            <div className="studio-title">
              <div>
                <h1>{studioText("店铺设置", "Shop settings")}</h1>
                <p>{studioText("更新你的店铺介绍", "Update your shop profile")}</p>
              </div>
            </div>
            <section className="studio-panel settings-form">
              <div
                className="shop-media-settings"
                style={{
                  display: "grid",
                  gridTemplateColumns: "120px minmax(260px, 480px)",
                  gap: 22,
                  alignItems: "end",
                }}
              >
                <div className="shop-media-upload shop-avatar-upload">
                  <span>店铺头像</span>
                  <label className="shop-media-file-button">
                    <input
                      className="shop-media-file-input"
                      type="file"
                      accept="image/*"
                      onChange={(event) => {
                        chooseShopImage("avatar", event.target.files?.[0]);
                        event.currentTarget.value = "";
                      }}
                    />
                    选择文件
                  </label>
                  <img
                    className="shop-avatar-preview"
                    src={data.shop.avatar || shopAvatarImage}
                    alt="店铺头像默认占位图"
                  />
                </div>
                <div className="shop-media-upload shop-banner-upload">
                  <span>店铺横幅</span>
                  <label className="shop-media-file-button">
                    <input
                      className="shop-media-file-input"
                      type="file"
                      accept="image/*"
                      onChange={(event) => {
                        chooseShopImage("banner", event.target.files?.[0]);
                        event.currentTarget.value = "";
                      }}
                    />
                    选择文件
                  </label>
                  <img
                    className="shop-banner-preview"
                    src={data.shop.banner || shopBannerImage}
                    alt="店铺横幅默认占位图"
                  />
                </div>
              </div>
              <label className="shop-name-label">
                店铺名称
                <input
                  value={data.shop.name}
                  onChange={(e) =>
                    setData((v) => ({
                      ...v,
                      shop: { ...v.shop, name: e.target.value },
                    }))
                  }
                />
              </label>
              <div className="form-split">
                <label>
                  营业状态
                  <select
                    className="shop-status-select"
                    value={data.shop.status || "active"}
                    onChange={(event) =>
                      setData((value) => ({
                        ...value,
                        shop: {
                          ...value.shop,
                          status: event.target.value as "active" | "paused",
                        },
                      }))
                    }
                  >
                    <option value="active">营业中</option>
                    <option value="paused">暂休中</option>
                  </select>
                </label>
              </div>
              <label className="shop-description-label">
                店铺介绍
                <textarea
                  value={data.shop.description}
                  onChange={(e) =>
                    setData((v) => ({
                      ...v,
                      shop: { ...v.shop, description: e.target.value },
                    }))
                  }
                />
              </label>
              <section className="operation-settings return-policy-settings">
                <div>
                  <b>退货设置</b>
                  <small>
                    买家发起退货退款时，平台会按此规则展示可退期限与退货地址。
                  </small>
                </div>
                <label className="return-policy-toggle">
                  <input
                    type="checkbox"
                    checked={returnPolicy.acceptsReturns}
                    onChange={(event) =>
                      updateReturnPolicy({
                        acceptsReturns: event.target.checked,
                      })
                    }
                  />
                  接受退货
                </label>
                {returnPolicy.acceptsReturns && (
                  <>
                    <div className="return-policy-grid">
                      <label>
                        可退期限
                        <input
                          type="number"
                          min="1"
                          max="30"
                          value={returnPolicy.windowDays}
                          onChange={(event) =>
                            updateReturnPolicy({
                              windowDays: Math.max(
                                1,
                                Math.min(30, Number(event.target.value) || 1),
                              ),
                            })
                          }
                        />
                      </label>
                      <label>
                        收件人
                        <input
                          maxLength={80}
                          value={returnPolicy.recipientName}
                          onChange={(event) =>
                            updateReturnPolicy({
                              recipientName: event.target.value,
                            })
                          }
                          placeholder="收件人姓名"
                        />
                      </label>
                      <label>
                        联系电话
                        <input
                          maxLength={40}
                          value={returnPolicy.recipientPhone}
                          onChange={(event) =>
                            updateReturnPolicy({
                              recipientPhone: event.target.value,
                            })
                          }
                          placeholder="联系电话"
                        />
                      </label>
                      <label className="return-policy-address">
                        详细地址
                        <input
                          maxLength={300}
                          value={returnPolicy.address}
                          onChange={(event) =>
                            updateReturnPolicy({ address: event.target.value })
                          }
                          placeholder="省、市、区及详细地址"
                        />
                      </label>
                    </div>
                    <label>
                      退货说明
                      <textarea
                        maxLength={500}
                        value={returnPolicy.instructions}
                        onChange={(event) =>
                          updateReturnPolicy({
                            instructions: event.target.value,
                          })
                        }
                        placeholder="例如：商品需保持完好、未使用，并附上订单信息。"
                      />
                    </label>
                  </>
                )}
              </section>
              <button className="primary" onClick={() => void saveShop()}>
                保存更改
              </button>
            </section>
    </>
  );
}
