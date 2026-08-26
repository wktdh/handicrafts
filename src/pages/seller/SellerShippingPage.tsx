// @ts-nocheck
const SELLER_SHIPPING_COUNTRY_OPTIONS = [
  ["US", "美国"], ["CA", "加拿大"], ["GB", "英国"], ["DE", "德国"],
  ["FR", "法国"], ["IT", "意大利"], ["ES", "西班牙"], ["NL", "荷兰"],
  ["BE", "比利时"], ["AT", "奥地利"], ["IE", "爱尔兰"], ["SE", "瑞典"],
  ["DK", "丹麦"], ["FI", "芬兰"], ["PT", "葡萄牙"], ["PL", "波兰"],
  ["CZ", "捷克"], ["LU", "卢森堡"],
] as const;

export default function SellerShippingPage({ context }: { context: Record<string, any> }) {
  const {
    studioText,
    data,
    setData,
    shippingTemplate,
    sellerShippingText,
    updateShippingTemplate,
    defaultInternationalShippingTemplate,
    listedSellerProducts,
    productListImageUrl,
    saveShop,
  } = context;
  return (
    <>
            <div className="studio-title">
              <div>
                <h1>{studioText("运费管理", "Shipping")}</h1>
                <p>{studioText("配置发货地与店铺配送规则", "Configure your origin and shipping rules")}</p>
              </div>
            </div>
            <section className="studio-panel settings-form operations-form">
              <label className="shipping-origin-label">
                发货地
                <input
                  value={data.shop.shippingOrigin || ""}
                  placeholder="例如：浙江省杭州市西湖区"
                  onChange={(event) =>
                    setData((value) => ({
                      ...value,
                      shop: {
                        ...value.shop,
                        shippingOrigin: event.target.value,
                      },
                    }))
                  }
                />
              </label>
              <div className="operation-settings">
                <div>
                  <b>国际物流与运费模板</b>
                  <small>按目的国家报价；结账时将自动校验可配送性。所有金额均为 USD。</small>
                </div>
                <label>
                  模板名称
                  <input
                    value={sellerShippingText(shippingTemplate?.name || "国际配送")}
                    onChange={(event) => updateShippingTemplate((template) => ({ ...template, name: event.target.value }))}
                  />
                </label>
                {(shippingTemplate?.zones || defaultInternationalShippingTemplate().zones || []).map((zone, index) => (
                  <div className="shipping-zone-editor" key={zone.id}>
                    <div className="shipping-zone-editor-heading">
                      <b>配送区域 {index + 1}</b>
                      <label>
                        <input
                          type="checkbox"
                          checked={zone.enabled}
                          onChange={(event) => updateShippingTemplate((template) => ({
                            ...template,
                            zones: (template.zones || []).map((item) => item.id === zone.id ? { ...item, enabled: event.target.checked } : item),
                          }))}
                        /> 启用
                      </label>
                      {(shippingTemplate?.zones?.length || 0) > 1 && (
                        <button type="button" className="secondary" onClick={() => updateShippingTemplate((template) => ({
                          ...template, zones: (template.zones || []).filter((item) => item.id !== zone.id),
                        }))}>移除</button>
                      )}
                    </div>
                    <div className="form-split">
                      <label>区域名称<input value={sellerShippingText(zone.name)} onChange={(event) => updateShippingTemplate((template) => ({ ...template, zones: (template.zones || []).map((item) => item.id === zone.id ? { ...item, name: event.target.value } : item) }))} /></label>
                      <label>物流商<input value={sellerShippingText(zone.carrier)} onChange={(event) => updateShippingTemplate((template) => ({ ...template, zones: (template.zones || []).map((item) => item.id === zone.id ? { ...item, carrier: event.target.value } : item) }))} /></label>
                      <label>首件运费（美元）<input type="number" min="0" value={zone.firstFee} onChange={(event) => updateShippingTemplate((template) => ({ ...template, zones: (template.zones || []).map((item) => item.id === zone.id ? { ...item, firstFee: Number(event.target.value) || 0 } : item) }))} /></label>
                      <label>续件运费（美元）<input type="number" min="0" value={zone.additionalFee} onChange={(event) => updateShippingTemplate((template) => ({ ...template, zones: (template.zones || []).map((item) => item.id === zone.id ? { ...item, additionalFee: Number(event.target.value) || 0 } : item) }))} /></label>
                      <label>免邮门槛（美元，0=不免邮）<input type="number" min="0" value={zone.freeShippingThreshold ?? 0} onChange={(event) => updateShippingTemplate((template) => ({ ...template, zones: (template.zones || []).map((item) => item.id === zone.id ? { ...item, freeShippingThreshold: Number(event.target.value) || 0 } : item) }))} /></label>
                      <label>预计送达（工作日）<span className="form-inline"><input type="number" min="1" max="90" value={zone.minDeliveryDays} onChange={(event) => updateShippingTemplate((template) => ({ ...template, zones: (template.zones || []).map((item) => item.id === zone.id ? { ...item, minDeliveryDays: Number(event.target.value) || 1 } : item) }))} /> 至 <input type="number" min="1" max="90" value={zone.maxDeliveryDays} onChange={(event) => updateShippingTemplate((template) => ({ ...template, zones: (template.zones || []).map((item) => item.id === zone.id ? { ...item, maxDeliveryDays: Number(event.target.value) || 1 } : item) }))} /></span></label>
                    </div>
                    <div className="shipping-country-picker">
                      <span>目的国家 / 地区</span>
                      <details>
                        <summary>
                          {zone.countries.length
                            ? zone.countries
                                .map(
                                  (countryCode) =>
                                    SELLER_SHIPPING_COUNTRY_OPTIONS.find(
                                      ([code]) => code === countryCode,
                                    )?.[1] || countryCode,
                                )
                                .join("、")
                            : "请选择配送国家 / 地区"}
                        </summary>
                        <div>
                          {SELLER_SHIPPING_COUNTRY_OPTIONS.map(([code, name]) => (
                            <label key={code}>
                              <input
                                type="checkbox"
                                checked={zone.countries.includes(code)}
                                onChange={(event) =>
                                  updateShippingTemplate((template) => ({
                                    ...template,
                                    zones: (template.zones || []).map((item) =>
                                      item.id === zone.id
                                        ? {
                                            ...item,
                                            countries: event.target.checked
                                              ? Array.from(
                                                  new Set([
                                                    ...item.countries,
                                                    code,
                                                  ]),
                                                )
                                              : item.countries.filter(
                                                  (country) => country !== code,
                                                ),
                                          }
                                        : item,
                                    ),
                                  }))
                                }
                              />
                              {name}
                            </label>
                          ))}
                        </div>
                      </details>
                    </div>
                  </div>
                ))}
                <button type="button" className="secondary shipping-zone-add" disabled={(shippingTemplate?.zones?.length || 0) >= 8} onClick={() => updateShippingTemplate((template) => ({
                  ...template,
                  zones: [...(template.zones || []), { id: `zone-${Date.now()}`, name: "自定义区域", countries: ["US"], carrier: "顺丰国际", firstFee: 0, additionalFee: 0, freeShippingThreshold: 0, minDeliveryDays: 7, maxDeliveryDays: 14, enabled: true }],
                }))}>添加配送区域</button>
              </div>
              <section className="operation-settings featured-selector">
                <div>
                  <b>店铺作品推荐标签</b>
                  <small>
                    最多标记 2 件作品；带推荐标签的作品将优先展示（已选{" "}
                    {(data.shop.featuredProductIds || []).length}/2）
                  </small>
                </div>
                {listedSellerProducts.map((product) => (
                  <label
                    className="featured-product-option"
                    key={product.catalogId || product.id}
                  >
                    <input
                      type="checkbox"
                      checked={
                        data.shop.featuredProductIds?.includes(
                          product.catalogId || String(product.id),
                        ) || false
                      }
                      disabled={
                        !(data.shop.featuredProductIds || []).includes(
                          product.catalogId || String(product.id),
                        ) && (data.shop.featuredProductIds || []).length >= 2
                      }
                      onChange={(event) =>
                        setData((value) => {
                          const featured = value.shop.featuredProductIds || [];
                          const productKey =
                            product.catalogId || String(product.id);
                          const next = event.target.checked
                            ? [...featured, productKey].slice(0, 2)
                            : featured.filter((id) => id !== productKey);
                          return {
                            ...value,
                            shop: { ...value.shop, featuredProductIds: next },
                          };
                        })
                      }
                    />
                    <img
                      src={productListImageUrl(
                        product.images?.[0] || product.image,
                        160,
                      )}
                      alt=""
                    />
                    <span>{product.title}</span>
                  </label>
                ))}
              </section>
              <button className="primary" onClick={() => void saveShop()}>
                保存更改
              </button>
            </section>
    </>
  );
}

