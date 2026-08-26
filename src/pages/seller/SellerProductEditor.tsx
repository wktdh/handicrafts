// This component receives its editor state from Studio while the gradual
// migration keeps those mutations centralized. The state shape is intentionally
// untyped here; the public editor contract will be narrowed in the next split.
// @ts-nocheck
import { ImagePlus, LoaderCircle, Plus, Video, X, type LucideIcon } from "lucide-react";

const DIMENSION_LABELS = ["长", "宽", "高"] as const;

function IconButton({
  icon: Icon,
  label,
  onClick,
  disabled,
}: {
  icon: LucideIcon;
  label: string;
  onClick?: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      className="icon-button"
      type="button"
      title={label}
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
    >
      <Icon size={20} />
    </button>
  );
}

export default function SellerProductEditor({
  context,
}: {
  context: Record<string, any>;
}) {
  const { editingProductId,
    form,
    setForm,
    isGeneratingProductTitle,
    generatedChineseTitle,
    chooseVideo,
    productImageLoadStates,
    setProductImageLoadStates,
    dragOverImageIndex,
    draggedImageIndex,
    setDraggedImageIndex,
    setDragOverImageIndex,
    moveImage,
    pendingProductImageIds,
    pendingProductImageProgress,
    chooseImages,
    settlementEstimatorExpanded,
    setSettlementEstimatorExpanded,
    estimatedGatewayFeeRate,
    setEstimatedGatewayFeeRate,
    shippingTemplate,
    freeShippingApplies,
    productSaleAmount,
    estimatedShippingAmount,
    estimatedOrderTotal,
    gatewayFeeRate,
    estimatedGatewayFee,
    estimatedPlatformCommission,
    estimatedLogisticsCost,
    estimatedSettlementAmount,
    productDimensionValues,
    updateProductDimension,
    variantDrafts,
    setVariantDrafts,
    skuStocks,
    setSkuStocks,
    skuPrices,
    setSkuPrices,
    skuCodes,
    setSkuCodes,
    defaultSkuCode,
    setDefaultSkuCode,
    skuStatuses,
    setSkuStatuses,
    seoTagInput,
    setSeoTagInput,
    addSeoTag,
    pendingVariantImageKeys,
    variantImageLoadStates,
    setVariantImageLoadStates,
    chooseVariantImage,
    variantImageBusy,
    hasCompleteVariants,
    variantStockCombinations,
    variantCombinationKey,
    saveDraft,
    addProduct,
    money,
    productListImageUrl } = context;
  return (
              <section className="studio-panel publish-form">
                {editingProductId && <h3>编辑作品</h3>}
                <label>
                  <span className="product-title-label">
                    作品名称
                    <small className="product-title-hint">
                      上传图片后将自动生成英文 SEO 标题，可继续修改。
                    </small>
                  </span>
                  <input
                    value={form.title}
                    onChange={(e) =>
                      setForm({ ...form, title: e.target.value })
                    }
                    placeholder="例如：手作陶瓷香插"
                    maxLength={125}
                  />
                  {!isGeneratingProductTitle && generatedChineseTitle && (
                    <small className="generated-title-translation">
                      中文参考：{generatedChineseTitle}
                    </small>
                  )}
                </label>
                <section className="media-upload-section product-media-upload">
                  <div className="media-upload-heading">
                    <h4>上传视频/图片</h4>
                    <small>最多可上传 10 张图片</small>
                  </div>
                  <div className="upload-grid">
                    {form.video ? (
                      <div className="upload-preview video-preview">
                        <video src={form.video} muted controls />
                        <button
                          type="button"
                          title="移除视频"
                          aria-label="移除视频"
                          onClick={() =>
                            setForm((value) => ({ ...value, video: "" }))
                          }
                        >
                          <X size={15} />
                        </button>
                        <span>视频</span>
                      </div>
                    ) : (
                      <label className="image-upload video-upload">
                        <input
                          type="file"
                          accept="video/*"
                          onChange={(event) => {
                            chooseVideo(event.target.files?.[0]);
                            event.currentTarget.value = "";
                          }}
                        />
                        <span>
                          <Video size={24} />
                          添加视频
                          <small>MP4/WebM/MOV，不超过 50MB</small>
                        </span>
                      </label>
                    )}
                    {form.images.map((image, index) => {
                      const imageLoadState =
                        productImageLoadStates[image] || "loading";
                      return (
                        <div
                          className={`upload-preview image-${imageLoadState} ${dragOverImageIndex === index ? "drag-over" : ""} ${draggedImageIndex === index ? "dragging" : ""}`}
                          key={image}
                          draggable
                          onDragStart={() => setDraggedImageIndex(index)}
                          onDragOver={(event) => {
                            event.preventDefault();
                            setDragOverImageIndex(index);
                          }}
                          onDrop={(event) => {
                            event.preventDefault();
                            if (draggedImageIndex !== null)
                              moveImage(draggedImageIndex, index);
                            setDraggedImageIndex(null);
                            setDragOverImageIndex(null);
                          }}
                          onDragEnd={() => {
                            setDraggedImageIndex(null);
                            setDragOverImageIndex(null);
                          }}
                        >
                          {imageLoadState !== "loaded" && (
                            <div
                              className="upload-preview-image-status"
                              aria-live="polite"
                            >
                              <div className="uploading-image-placeholder">
                                <ImagePlus size={25} />
                              </div>
                              <span className="uploading-image-status">
                                <LoaderCircle size={18} />
                                {imageLoadState === "error"
                                  ? "图片加载失败"
                                  : "图片加载中"}
                              </span>
                            </div>
                          )}
                          <img
                            src={image}
                            alt={`作品图片 ${index + 1}`}
                            onLoad={() =>
                              setProductImageLoadStates((current) => ({
                                ...current,
                                [image]: "loaded",
                              }))
                            }
                            onError={() =>
                              setProductImageLoadStates((current) => ({
                                ...current,
                                [image]: "error",
                              }))
                            }
                          />
                          <button
                            type="button"
                            title="移除图片"
                            aria-label="移除图片"
                            onClick={() =>
                              setForm((value) => ({
                                ...value,
                                images: value.images.filter(
                                  (_, imageIndex) => imageIndex !== index,
                                ),
                                imageAssetIds: value.imageAssetIds.filter(
                                  (_, imageIndex) => imageIndex !== index,
                                ),
                              }))
                            }
                          >
                            <X size={15} />
                          </button>
                          {index === 0 && <span>主图</span>}
                        </div>
                      );
                    })}
                    {pendingProductImageIds.map((id) => (
                      <div
                        className="upload-preview uploading"
                        key={id}
                        aria-live="polite"
                        aria-label="图片上传中"
                      >
                        <div className="uploading-image-placeholder">
                          <ImagePlus size={25} />
                        </div>
                        <span className="uploading-image-status">
                          <LoaderCircle size={18} />
                          {(pendingProductImageProgress[id] || 0) < 3
                            ? "图片处理中"
                            : `上传 ${pendingProductImageProgress[id]}%`}
                        </span>
                      </div>
                    ))}
                    {form.images.length + pendingProductImageIds.length <
                      10 && (
                      <label className="image-upload">
                        <input
                          type="file"
                          accept="image/*"
                          multiple
                          onChange={(event) => {
                            chooseImages(event.target.files);
                            event.currentTarget.value = "";
                          }}
                        />
                        <span>
                          <ImagePlus size={24} />
                          添加图片
                          <small>JPG/PNG/WebP，单张不超过 3MB</small>
                        </span>
                      </label>
                    )}
                  </div>
                </section>
                <label className="product-price-field">
                  价格（USD）
                  <input
                    type="number"
                    value={form.price}
                    onChange={(e) =>
                      setForm({ ...form, price: e.target.value })
                    }
                    placeholder="0.00"
                  />
                </label>
                <section
                  className={`settlement-estimator${settlementEstimatorExpanded ? "" : " is-collapsed"}`}
                  aria-label="预计结算金额计算"
                >
                  <header>
                    <div>
                          <b>预计净结算金额</b>
                      {settlementEstimatorExpanded && (
                        <small>按单件订单及当前店铺运费模板估算</small>
                      )}
                    </div>
                    {settlementEstimatorExpanded ? (
                      <label>
                        支付网关预估费率
                        <span>
                          <input
                            type="number"
                            min="0"
                            max="100"
                            step="0.01"
                            value={estimatedGatewayFeeRate}
                            onChange={(event) =>
                              setEstimatedGatewayFeeRate(event.target.value)
                            }
                          />
                          <i>%</i>
                        </span>
                      </label>
                    ) : (
                      <button
                        type="button"
                        className="settlement-estimator-toggle"
                        aria-expanded={false}
                        onClick={() => setSettlementEstimatorExpanded(true)}
                      >
                        查看详细
                      </button>
                    )}
                  </header>
                  {settlementEstimatorExpanded && (
                    <>
                      <div className="settlement-estimator-rows">
                        <p>
                          <span>销售额</span>
                          <b>{money(productSaleAmount)}</b>
                        </p>
                        <p>
                          <span>
                            买家支付运费（{shippingTemplate?.name || "店铺运费模板"}
                            {freeShippingApplies ? " · 满额包邮" : ""}）
                          </span>
                          <b>{money(estimatedShippingAmount)}</b>
                        </p>
                        <p>
                          <span>总金额（销售额 + 运费）</span>
                          <b>{money(estimatedOrderTotal)}</b>
                        </p>
                        <p>
                          <span>支付网关手续费（{gatewayFeeRate * 100}%）</span>
                          <b>-{money(estimatedGatewayFee)}</b>
                        </p>
                        <p>
                          <span>平台佣金（5%）</span>
                          <b>-{money(estimatedPlatformCommission)}</b>
                        </p>
                        <p>
                          <span>预计物流成本</span>
                          <b>-{money(estimatedLogisticsCost)}</b>
                        </p>
                        <p className="settlement-estimator-total">
                          <span>预计净结算金额</span>
                          <b>{money(estimatedSettlementAmount)}</b>
                        </p>
                      </div>
                      <small className="settlement-estimator-note">
                        计算公式：买家实付总额（销售额 +
                        运费）－支付网关手续费－平台佣金－预计物流成本。物流成本暂按当前运费模板估算；实际净收入以买家实际支付金额、支付通道账单、物流账单、退款及拒付结果为准。
                      </small>
                      <button
                        type="button"
                        className="settlement-estimator-toggle settlement-estimator-collapse"
                        aria-expanded={true}
                        onClick={() => setSettlementEstimatorExpanded(false)}
                      >
                        收起
                      </button>
                    </>
                  )}
                </section>
                <div className="form-split product-detail-fields">
                  <label>
                    库存
                    <input
                      type="number"
                      min="0"
                      value={form.stock}
                      onChange={(e) =>
                        setForm({ ...form, stock: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    低库存预警
                    <input
                      type="number"
                      min="0"
                      value={form.lowStockThreshold}
                      onChange={(e) =>
                        setForm({ ...form, lowStockThreshold: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    重量（g）
                    <input
                      type="number"
                      min="1"
                      max="100000"
                      step="1"
                      value={form.weightGrams}
                      onChange={(e) =>
                        setForm({ ...form, weightGrams: e.target.value })
                      }
                      placeholder="如：350"
                    />
                  </label>
                  <div className="product-dimensions-field">
                    <span>尺寸（cm）</span>
                    <div className="product-dimensions-inputs">
                      {DIMENSION_LABELS.map((label, index) => (
                        <div className="product-dimension-input" key={label}>
                          <input
                            type="number"
                            min="0"
                            step="0.1"
                            value={productDimensionValues[index]}
                            onChange={(event) =>
                              updateProductDimension(index, event.target.value)
                            }
                            placeholder="0"
                            aria-label={`${label}（cm）`}
                          />
                          <span>{label}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="seo-tag-editor">
                  <div>
                    <b>搜索标签</b>
                    <small>最多 12 个，每个最多 10 个字</small>
                  </div>
                  <div className="seo-tag-input">
                    <input
                      value={seoTagInput}
                      onChange={(event) => setSeoTagInput(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key !== "Enter") return;
                        event.preventDefault();
                        addSeoTag();
                      }}
                      placeholder="输入标签后按回车"
                      maxLength={10}
                    />
                    <IconButton
                      icon={Plus}
                      label="添加搜索标签"
                      onClick={addSeoTag}
                      disabled={form.seoTags.length >= 12}
                    />
                  </div>
                  {!!form.seoTags.length && (
                    <div className="seo-tag-list">
                      {form.seoTags.map((tag) => (
                        <span key={tag}>
                          {tag}
                          <button
                            type="button"
                            title={`移除标签 ${tag}`}
                            aria-label={`移除标签 ${tag}`}
                            onClick={() =>
                              setForm((value) => ({
                                ...value,
                                seoTags: value.seoTags.filter(
                                  (item) => item !== tag,
                                ),
                              }))
                            }
                          >
                            <X size={14} />
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="variant-editor">
                  <div>
                    <b>商品规格</b>
                    <small>每个规格值可以上传一张对应图片</small>
                  </div>
                  {variantDrafts.map((variant) => (
                    <div className="variant-draft-wrap" key={variant.id}>
                      <div className="variant-heading">
                        <select
                          value={variant.name}
                          onChange={(event) =>
                            setVariantDrafts((items) =>
                              items.map((item) =>
                                item.id === variant.id
                                  ? { ...item, name: event.target.value }
                                  : item,
                              ),
                            )
                          }
                        >
                          <option value="">选择规格类型</option>
                          <option value="颜色">颜色</option>
                          <option value="尺寸">尺寸</option>
                          <option value="型号">型号</option>
                          <option value="组合">组合</option>
                        </select>
                        <IconButton
                          icon={X}
                          label="删除规格"
                          onClick={() =>
                            setVariantDrafts((items) =>
                              items.filter((item) => item.id !== variant.id),
                            )
                          }
                        />
                        {variant.name && (
                          <button
                            type="button"
                            className="continue-add"
                            onClick={() =>
                              setVariantDrafts((items) =>
                                items.map((draft) =>
                                  draft.id === variant.id
                                    ? {
                                        ...draft,
                                        values: [
                                          ...draft.values,
                                          { id: Date.now(), value: "" },
                                        ],
                                      }
                                    : draft,
                                ),
                              )
                            }
                          >
                            继续添加
                          </button>
                        )}
                      </div>
                      {variant.name && (
                        <div className="variant-value-list">
                          {variant.values.map((item, index) => {
                            const variantImageKey = `${variant.id}:${item.id}`;
                            const variantImageUploading =
                              pendingVariantImageKeys.includes(
                                variantImageKey,
                              );
                            const variantImageLoading =
                              variantImageLoadStates[variantImageKey] ===
                              "loading";
                            const variantImageBusy =
                              variantImageUploading || variantImageLoading;
                            return (
                              <div className="variant-value-row" key={item.id}>
                                <input
                                  value={item.value}
                                  onChange={(event) =>
                                    setVariantDrafts((items) =>
                                      items.map((draft) =>
                                        draft.id === variant.id
                                          ? {
                                              ...draft,
                                              values: draft.values.map(
                                                (value) =>
                                                  value.id === item.id
                                                    ? {
                                                        ...value,
                                                        value:
                                                          event.target.value,
                                                      }
                                                    : value,
                                              ),
                                            }
                                          : draft,
                                      ),
                                    )
                                  }
                                  placeholder={`规格值 ${index + 1}`}
                                />
                                <label
                                  className={`variant-image-upload${variantImageBusy ? " uploading" : ""}`}
                                  title={
                                    variantImageUploading
                                      ? "图片上传中"
                                      : variantImageLoading
                                        ? "图片加载中"
                                      : "上传对应图片"
                                  }
                                >
                                  <input
                                    type="file"
                                    accept="image/jpeg,image/png,image/webp"
                                    disabled={variantImageBusy}
                                    onChange={(event) => {
                                      chooseVariantImage(
                                        variant.id,
                                        item.id,
                                        event.target.files?.[0],
                                      );
                                      event.currentTarget.value = "";
                                    }}
                                  />
                                  {item.image && (
                                    <img
                                      src={productListImageUrl(item.image, 160)}
                                      alt="规格值对应图片"
                                      onLoad={() =>
                                        setVariantImageLoadStates((states) => ({
                                          ...states,
                                          [variantImageKey]: "loaded",
                                        }))
                                      }
                                      onError={() =>
                                        setVariantImageLoadStates((states) => ({
                                          ...states,
                                          [variantImageKey]: "error",
                                        }))
                                      }
                                    />
                                  )}
                                  {variantImageBusy ? (
                                    <span className="variant-image-uploading">
                                      <LoaderCircle size={16} />
                                      <small>
                                        {variantImageUploading ? "上传中" : "加载中"}
                                      </small>
                                    </span>
                                  ) : !item.image ||
                                    variantImageLoadStates[variantImageKey] ===
                                      "error" ? (
                                    <ImagePlus size={20} />
                                  ) : null}
                                </label>
                                {variant.values.length > 1 && (
                                  <button
                                    type="button"
                                    className="remove-value"
                                    onClick={() =>
                                      setVariantDrafts((items) =>
                                        items.map((draft) =>
                                          draft.id === variant.id
                                            ? {
                                                ...draft,
                                                values: draft.values.filter(
                                                  (value) =>
                                                    value.id !== item.id,
                                                ),
                                              }
                                            : draft,
                                        ),
                                      )
                                    }
                                    aria-label="删除规格值"
                                    title="删除规格值"
                                  >
                                    <X size={16} />
                                  </button>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  ))}
                  {variantDrafts.length < 3 && (
                    <button
                      type="button"
                      className="add-variant"
                      onClick={() =>
                        setVariantDrafts((items) => [
                          ...items,
                          {
                            id: Date.now(),
                            name: "",
                            values: [{ id: Date.now() + 1, value: "" }],
                          },
                        ])
                      }
                    >
                      <Plus size={16} />
                      添加规格
                    </button>
                  )}
                </div>
                <div className="product-custom-toggle product-custom-option">
                  <input
                    id="product-custom-toggle"
                    type="checkbox"
                    checked={form.custom}
                    onChange={(event) =>
                      setForm({ ...form, custom: event.target.checked })
                    }
                  />
                  <label htmlFor="product-custom-toggle">支持定制</label>
                  <small>买家需先咨询确认方案与报价</small>
                </div>
                {variantDrafts.length === 0 && (
                  <section className="sku-stock-editor default-sku-editor">
                    <div>
                      <b>SKU 编号</b>
                      <small>未填写时，保存后将自动生成唯一编号</small>
                    </div>
                    <label>
                      SKU 编号
                      <input
                        value={defaultSkuCode}
                        maxLength={40}
                        onChange={(event) => setDefaultSkuCode(event.target.value)}
                        placeholder="SKU 编号（可选）"
                        aria-label="作品 SKU 编号"
                      />
                    </label>
                  </section>
                )}
                {hasCompleteVariants && (
                  <section className="sku-stock-editor">
                    <div>
                      <b>规格组合库存</b>
                      <small>未填写时使用上方默认库存</small>
                    </div>
                    <div className="sku-stock-list sku-detail-list">
                      {variantStockCombinations.map((optionValues) => {
                        const key = variantCombinationKey(optionValues);
                        return (
                          <div className="sku-detail-row" key={key}>
                            <span>
                              {Object.entries(optionValues)
                                .map(([name, value]) => `${name}: ${value}`)
                                .join(" · ")}
                            </span>
                            <input
                              value={skuCodes[key] ?? ""}
                              maxLength={40}
                              onChange={(event) =>
                                setSkuCodes((value) => ({
                                  ...value,
                                  [key]: event.target.value,
                                }))
                              }
                              placeholder="SKU 编码"
                              aria-label={`${key} SKU 编码`}
                            />
                            <input
                              type="number"
                              min="0"
                              step="0.01"
                              value={skuPrices[key] ?? form.price}
                              onChange={(event) =>
                                setSkuPrices((value) => ({
                                  ...value,
                                  [key]: event.target.value,
                                }))
                              }
                              placeholder="售价（USD）"
                              aria-label={`${key} 售价（USD）`}
                            />
                            <input
                              type="number"
                              min="0"
                              value={skuStocks[key] ?? form.stock}
                              onChange={(event) =>
                                setSkuStocks((stocks) => ({
                                  ...stocks,
                                  [key]: event.target.value,
                                }))
                              }
                              aria-label={`${key}库存`}
                            />
                            <label className="sku-status-toggle">
                              <input
                                type="checkbox"
                                checked={
                                  (skuStatuses[key] ?? "active") === "active"
                                }
                                onChange={(event) =>
                                  setSkuStatuses((value) => ({
                                    ...value,
                                    [key]: event.target.checked
                                      ? "active"
                                      : "disabled",
                                  }))
                                }
                              />
                              可售
                            </label>
                          </div>
                        );
                      })}
                    </div>
                  </section>
                )}
                <label>
                  作品描述
                  <textarea
                    value={form.description}
                    onChange={(event) =>
                      setForm({ ...form, description: event.target.value })
                    }
                    placeholder="介绍作品的灵感、工艺、尺寸或适用场景..."
                    maxLength={300}
                  />
                </label>
                <label>
                  材质
                  <input
                    value={form.material}
                    onChange={(event) =>
                      setForm({ ...form, material: event.target.value })
                    }
                    placeholder="例如：陶瓷、黄铜、棉麻、天然羊毛"
                    maxLength={300}
                  />
                </label>
                <label>
                  制作工艺
                  <textarea
                    value={form.craftsmanship}
                    onChange={(event) =>
                      setForm({ ...form, craftsmanship: event.target.value })
                    }
                    placeholder="例如：手工拉坯、自然晾干、两次施釉后高温烧制"
                    maxLength={300}
                  />
                </label>
                <div className="publish-actions">
                  <button
                    className="secondary"
                    type="button"
                    disabled={pendingProductImageIds.length > 0}
                    onClick={saveDraft}
                  >
                    保存草稿
                  </button>
                  <button
                    className="primary"
                    disabled={pendingProductImageIds.length > 0}
                    onClick={addProduct}
                  >
                    {editingProductId ? "保存修改" : "确认发布"}
                  </button>
                </div>
              </section>
  );
}
