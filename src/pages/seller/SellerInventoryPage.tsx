// @ts-nocheck
import { Search } from "lucide-react";

function Empty({
  title,
  text,
  action,
  onAction,
}: {
  title: string;
  text: string;
  action: string;
  onAction: () => void;
}) {
  return (
    <div className="empty">
      <h2>{title}</h2>
      <p>{text}</p>
      <button className="primary" onClick={onAction}>{action}</button>
    </div>
  );
}

export default function SellerInventoryPage({ context }: { context: Record<string, any> }) {
  const {
    studioText,
    exportInventory,
    inventoryProduct,
    inventoryListRows,
    inventorySearch,
    setInventorySearch,
    inventoryListReason,
    setInventoryListReason,
    inventorySelectedSkuIds,
    setInventorySelectedSkuIds,
    saveInventoryList,
    allVisibleInventorySelected,
    productListImageUrl,
    selectInventorySku,
    inventoryRowValues,
    setInventoryRowValues,
    saveInventoryRow,
    money,
    inventorySku,
    setInventorySkuId,
    setInventorySkuStatus,
    inventoryAdjustmentType,
    setInventoryAdjustmentType,
    inventoryQuantity,
    setInventoryQuantity,
    inventoryReason,
    setInventoryReason,
    adjustInventory,
    inventoryAdjustments,
    openStudioTab,
    setShowForm,
  } = context;
  return (
    <>
            <div className="studio-title">
              <div>
                <h1>{studioText("库存管理", "Inventory")}</h1>
                <p>{studioText("按 SKU 调整可售库存，并保留每一次变更记录", "Adjust available stock by SKU and keep an audit trail")}</p>
              </div>
              <button className="secondary" onClick={exportInventory}>
                导出库存
              </button>
            </div>
            {inventoryProduct ? (
              <>
                <section className="studio-panel inventory-list-panel">
                  <div className="panel-head">
                    <div>
                      <h3>SKU 库存列表</h3>
                      <p>
                        直接编辑库存，光标移出输入框后会自动保存；也可勾选多条后批量盘点。
                      </p>
                    </div>
                    <span>{inventoryListRows.length} 个 SKU</span>
                  </div>
                  <div className="inventory-list-toolbar">
                    <label className="inventory-list-search">
                      <Search size={16} />
                      <input
                        value={inventorySearch}
                        onChange={(event) =>
                          setInventorySearch(event.target.value)
                        }
                        placeholder="搜索作品、SKU 或规格"
                      />
                    </label>
                    <input
                      value={inventoryListReason}
                      maxLength={120}
                      onChange={(event) =>
                        setInventoryListReason(event.target.value)
                      }
                      placeholder="批量盘点原因（必填）"
                    />
                    <button
                      className="secondary"
                      disabled={!inventorySelectedSkuIds.length}
                      onClick={() => void saveInventoryList()}
                    >
                      保存已选 {inventorySelectedSkuIds.length || ""}
                    </button>
                  </div>
                  <div className="inventory-list-head">
                    <label>
                      <input
                        type="checkbox"
                        checked={allVisibleInventorySelected}
                        onChange={() =>
                          setInventorySelectedSkuIds((current) =>
                            allVisibleInventorySelected
                              ? current.filter(
                                  (id) =>
                                    !inventoryListRows.some(
                                      ({ sku }) => sku.id === id,
                                    ),
                                )
                              : Array.from(
                                  new Set([
                                    ...current,
                                    ...inventoryListRows.map(
                                      ({ sku }) => sku.id,
                                    ),
                                  ]),
                                ),
                          )
                        }
                      />
                    </label>
                    <span>图片</span>
                    <span>作品</span>
                    <span>规格 / SKU</span>
                    <span>售价</span>
                    <span>库存</span>
                    <span>状态</span>
                  </div>
                  <div className="inventory-list">
                    {inventoryListRows.map(({ product, sku }) => {
                      const spec = Object.keys(sku.optionValues).length
                        ? Object.entries(sku.optionValues)
                            .map(([name, value]) => `${name}: ${value}`)
                            .join(" · ")
                        : "默认规格";
                      const skuImage =
                        (product.variants || [])
                          .map(
                            (variant) =>
                              variant.valueImages?.[
                                sku.optionValues[variant.name]
                              ],
                          )
                          .find(Boolean) || product.image;
                      const inventoryStatus =
                        sku.stock === 0
                          ? "售罄"
                          : sku.stock < 10
                            ? "紧张"
                            : "可售";
                      return (
                        <article key={sku.id} className="">
                          <label className="inventory-row-check">
                            <input
                              type="checkbox"
                              checked={inventorySelectedSkuIds.includes(sku.id)}
                              onChange={() =>
                                setInventorySelectedSkuIds((current) =>
                                  current.includes(sku.id)
                                    ? current.filter((id) => id !== sku.id)
                                    : [...current, sku.id],
                                )
                              }
                            />
                            <span className="sr-only">
                              选择 {product.title}
                            </span>
                          </label>
                          <span className="inventory-row-image">
                            <img
                              src={productListImageUrl(skuImage, 160)}
                              alt={`${spec} 图片`}
                            />
                          </span>
                          <button
                            type="button"
                            className="inventory-row-product"
                            onClick={() => selectInventorySku(product, sku)}
                          >
                            <span>
                              <b>{product.title}</b>
                            </span>
                          </button>
                          <span className="inventory-row-sku">
                            <b>{spec}</b>
                            <small>{sku.code || "未编码"}</small>
                          </span>
                          <span className="inventory-row-price">
                            {money(sku.price ?? product.price)}
                          </span>
                          <label className="inventory-row-stock">
                            <input
                              type="number"
                              min="0"
                              step="1"
                              value={
                                inventoryRowValues[sku.id] ?? String(sku.stock)
                              }
                              onChange={(event) =>
                                setInventoryRowValues((current) => ({
                                  ...current,
                                  [sku.id]: event.target.value,
                                }))
                              }
                              onBlur={() => void saveInventoryRow(product, sku)}
                            />
                          </label>
                          <span
                            className={`inventory-row-status ${inventoryStatus === "售罄" ? "sold-out" : inventoryStatus === "紧张" ? "tight" : "available"}`}
                          >
                            {inventoryStatus}
                          </span>
                        </article>
                      );
                    })}
                    {!inventoryListRows.length && (
                      <p className="inventory-list-empty">没有匹配的 SKU。</p>
                    )}
                  </div>
                </section>
                <div className="inventory-layout inventory-detail-layout">
                  <section className="studio-panel inventory-adjustment-panel">
                    <div className="panel-head">
                      <h3>单个 SKU 调整</h3>
                    </div>
                    <div className="inventory-selected-product">
                      <img
                        src={productListImageUrl(inventoryProduct.image, 160)}
                        alt=""
                      />
                      <span>
                        <small>当前作品</small>
                        <b>{inventoryProduct.title}</b>
                      </span>
                    </div>
                    <div className="inventory-summary">
                      <span>作品可售库存</span>
                      <b>{inventoryProduct.stock}</b>
                      <small>
                        预警阈值：{inventoryProduct.lowStockThreshold ?? 3}
                      </small>
                      {inventorySku && (
                        <small>
                          当前 SKU：{inventorySku.code || "未编码"} ·{" "}
                          {money(inventorySku.price ?? inventoryProduct.price)}{" "}
                          ·{" "}
                          {inventorySku.status === "disabled"
                            ? "已停用"
                            : "可售"}
                        </small>
                      )}
                    </div>
                    <label>
                      SKU
                      <select
                        value={inventorySku?.id || ""}
                        onChange={(event) =>
                          setInventorySkuId(event.target.value)
                        }
                      >
                        {(inventoryProduct.skus || []).map((sku) => (
                          <option key={sku.id} value={sku.id}>
                            {Object.keys(sku.optionValues).length
                              ? Object.entries(sku.optionValues)
                                  .map(([name, value]) => `${name}: ${value}`)
                                  .join(" · ")
                              : "默认规格"}
                            （
                            {sku.status === "disabled"
                              ? "已停用"
                              : `现货 ${sku.stock}`}
                            ）
                          </option>
                        ))}
                      </select>
                    </label>
                    {inventorySku && (
                      <button
                        className="secondary"
                        onClick={() =>
                          void setInventorySkuStatus(
                            inventorySku,
                            inventorySku.status === "disabled"
                              ? "active"
                              : "disabled",
                          )
                        }
                      >
                        {inventorySku.status === "disabled"
                          ? "启用当前 SKU"
                          : "停用当前 SKU"}
                      </button>
                    )}
                    <div className="inventory-form-row">
                      <label>
                        操作
                        <select
                          value={inventoryAdjustmentType}
                          onChange={(event) =>
                            setInventoryAdjustmentType(
                              event.target
                                .value as typeof inventoryAdjustmentType,
                            )
                          }
                        >
                          <option value="increase">入库增加</option>
                          <option value="decrease">出库减少</option>
                          <option value="set">盘点设定</option>
                        </select>
                      </label>
                      <label>
                        数量
                        <input
                          type="number"
                          min="0"
                          step="1"
                          value={inventoryQuantity}
                          onChange={(event) =>
                            setInventoryQuantity(event.target.value)
                          }
                        />
                      </label>
                    </div>
                    <label>
                      调整原因
                      <input
                        maxLength={120}
                        value={inventoryReason}
                        onChange={(event) =>
                          setInventoryReason(event.target.value)
                        }
                        placeholder="如：到货补充、盘点修正"
                      />
                    </label>
                    <button
                      className="primary"
                      onClick={() => void adjustInventory()}
                    >
                      确认调整
                    </button>
                  </section>
                  <section className="studio-panel inventory-history-panel">
                    <div className="panel-head">
                      <h3>库存调整记录</h3>
                      <span>{inventoryAdjustments.length} 条</span>
                    </div>
                    {inventoryAdjustments.length ? (
                      <div className="inventory-history-list">
                        {inventoryAdjustments.map((item) => {
                          const sku = inventoryProduct.skus?.find(
                            (value) => value.id === item.skuId,
                          );
                          const label =
                            sku && Object.keys(sku.optionValues).length
                              ? Object.entries(sku.optionValues)
                                  .map(([name, value]) => `${name}: ${value}`)
                                  .join(" · ")
                              : "默认规格";
                          return (
                            <article key={item.id}>
                              <div>
                                <b>{label}</b>
                                <small>
                                  {item.reason || "未填写原因"} ·{" "}
                                  {item.createdAt}
                                </small>
                              </div>
                              <span>
                                {item.type === "increase"
                                  ? "+"
                                  : item.type === "decrease"
                                    ? "-"
                                    : "="}
                                {item.type === "decrease"
                                  ? item.before - item.after
                                  : item.type === "increase"
                                    ? item.after - item.before
                                    : item.after}{" "}
                                <em>
                                  {item.before} → {item.after}
                                </em>
                              </span>
                            </article>
                          );
                        })}
                      </div>
                    ) : (
                      <p>暂无该作品的库存调整记录。</p>
                    )}
                  </section>
                </div>
              </>
            ) : (
              <Empty
                title="暂无作品"
                text="发布作品后即可管理 SKU 库存。"
                action="发布作品"
                onAction={() => {
                  openStudioTab("products");
                  setShowForm(true);
                }}
              />
            )}
    </>
  );
}

