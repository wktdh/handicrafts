// @ts-nocheck
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

export default function SellerProductList({ context }: { context: Record<string, any> }) {
  const {
    showForm,
    productListMode,
    setProductListMode,
    listedSellerProducts,
    recycledSellerProducts,
    selectedProductIds,
    setSelectedProductIds,
    sellerProductSelectionId,
    bulkPrice,
    setBulkPrice,
    bulkStock,
    setBulkStock,
    applyBulkChanges,
    displayedSellerProducts,
    onOpen,
    productListImageUrl,
    lowStockCount,
    money,
    editProduct,
    changeProductStatus,
    removeProduct,
    appealProduct,
    data,
    setEditingProductId,
    setEditingProductCatalogId,
    setEditingDraftId,
    setEditingDraftCatalogId,
    loadProductForm,
  } = context;
  return (
    <>
            {!showForm && (
              <div
                className="product-list-tabs"
                role="tablist"
                aria-label="作品状态"
              >
                <button
                  className={productListMode === "listed" ? "active" : ""}
                  onClick={() => setProductListMode("listed")}
                >
                  已上架 {listedSellerProducts.length}
                </button>
                <button
                  className={productListMode === "trash" ? "active" : ""}
                  onClick={() => setProductListMode("trash")}
                >
                  回收站 {recycledSellerProducts.length}
                </button>
              </div>
            )}
            {showForm && (
              <Suspense fallback={<section className="studio-panel publish-form" aria-busy="true"><span className="app-loading"><span /></span></section>}>
                <LazySellerProductEditor context={{
                  editingProductId,
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
                  variantImageBusy: pendingVariantImageKeys.length > 0,
                  hasCompleteVariants,
                  variantStockCombinations,
                  variantCombinationKey,
                  saveDraft,
                  addProduct,
                  money,
                  productListImageUrl,
                }} />
              </Suspense>
            )}
            {!showForm && (
              <>
                {productListMode === "listed" &&
                  !!listedSellerProducts.length && (
                    <section className="studio-panel bulk-editor">
                      <label className="select-all" aria-label="全选作品">
                        <input
                          type="checkbox"
                          checked={
                            selectedProductIds.length ===
                            listedSellerProducts.length
                          }
                          onChange={(event) =>
                            setSelectedProductIds(
                              event.target.checked
                                ? listedSellerProducts.map(
                                    sellerProductSelectionId,
                                  )
                                : [],
                            )
                          }
                        />
                      </label>
                      <div>
                        <span>已选 {selectedProductIds.length} 件作品</span>
                      </div>
                      <input
                        type="number"
                        value={bulkPrice}
                        onChange={(event) => setBulkPrice(event.target.value)}
                        placeholder="统一价格"
                      />
                      <input
                        type="number"
                        value={bulkStock}
                        onChange={(event) => setBulkStock(event.target.value)}
                        placeholder="统一库存"
                      />
                      <button
                        className="secondary"
                        disabled={
                          !selectedProductIds.length ||
                          (!bulkPrice && !bulkStock)
                        }
                        onClick={() => void applyBulkChanges()}
                      >
                        应用修改
                      </button>
                    </section>
                  )}
                <div className="studio-product-list">
                  {displayedSellerProducts.map((p) => (
                    <article
                      className="studio-product-row"
                      key={sellerProductSelectionId(p)}
                    >
                      {productListMode === "listed" ? (
                        <input
                          type="checkbox"
                          checked={selectedProductIds.includes(
                            sellerProductSelectionId(p),
                          )}
                          onChange={() =>
                            setSelectedProductIds((ids) =>
                              ids.includes(sellerProductSelectionId(p))
                                ? ids.filter(
                                    (id) => id !== sellerProductSelectionId(p),
                                  )
                                : [...ids, sellerProductSelectionId(p)],
                            )
                          }
                          aria-label={`选择${p.title}`}
                        />
                      ) : (
                        <span className="trash-marker">已下架</span>
                      )}
                      <div className="product-preview">
                        <button
                          className="product-preview-image"
                          onClick={() => onOpen(p.id)}
                          aria-label={`查看${p.title}`}
                        >
                          <img src={productListImageUrl(p.image, 160)} alt="" />
                        </button>
                        <div className="product-preview-info">
                          <a
                            className="product-title-link"
                            href={`#product-${p.catalogId || p.id}`}
                            onClick={(event) => {
                              event.preventDefault();
                              onOpen(p.id);
                            }}
                          >
                            {p.title}
                          </a>
                          {p.code && <small>作品编号：{p.code}</small>}
                          <small>
                            {productListMode === "trash" ? "已下架" : "已发布"}
                            {productListMode === "listed" &&
                              p.reviewStatus === "rejected" &&
                              " · 平台已下架"}
                            {productListMode === "listed" &&
                              lowStockCount(p) > 0 && (
                                <em className="stock-warning">
                                  · {lowStockCount(p)} 个低库存规格
                                </em>
                              )}
                          </small>
                        </div>
                        <span className="product-price-stock">
                          <strong>{money(p.price)}</strong>
                          <small>库存 {p.stock} 件</small>
                        </span>
                      </div>
                      <div className="product-row-actions">
                        {productListMode === "listed" ? (
                          <>
                            <button onClick={() => editProduct(p)}>编辑</button>
                            <button
                              onClick={() => {
                                void changeProductStatus(p, "unlisted");
                                setSelectedProductIds((ids) =>
                                  ids.filter(
                                    (id) => id !== sellerProductSelectionId(p),
                                  ),
                                );
                              }}
                            >
                              下架
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              onClick={() =>
                                void changeProductStatus(p, "published")
                              }
                            >
                              上架
                            </button>
                            {p.reviewStatus === "rejected" && (
                              <button onClick={() => void appealProduct(p)}>
                                申诉
                              </button>
                            )}
                            <button
                              className="danger"
                              onClick={() => void removeProduct(p)}
                            >
                              删除
                            </button>
                          </>
                        )}
                      </div>
                    </article>
                  ))}
                  {!displayedSellerProducts.length && (
                    <Empty
                      title={
                        productListMode === "trash"
                          ? "回收站还是空的"
                          : "还没有作品"
                      }
                      text={
                        productListMode === "trash"
                          ? "下架的作品会暂存在这里。"
                          : "发布你的第一件原创手作吧。"
                      }
                      action={
                        productListMode === "trash"
                          ? "查看已上架作品"
                          : "发布作品"
                      }
                      onAction={() =>
                        productListMode === "trash"
                          ? setProductListMode("listed")
                          : setShowForm(true)
                      }
                    />
                  )}
                </div>
                {!!data.drafts.length && (
                  <section className="studio-panel draft-list">
                    <div className="panel-head">
                      <h3>草稿箱</h3>
                      <span>{data.drafts.length} 份草稿</span>
                    </div>
                    {data.drafts.map((draft) => (
                      <button
                        key={draft.id}
                        onClick={() => {
                          setEditingProductId(null);
                          setEditingProductCatalogId(null);
                          setEditingDraftId(draft.id);
                          setEditingDraftCatalogId(draft.catalogId || null);
                          loadProductForm(draft);
                        }}
                      >
                        <span>
                          <b>{draft.title}</b>
                          <small>保存于 {draft.updatedAt}</small>
                        </span>
                        <span>继续编辑</span>
                      </button>
                    ))}
                  </section>
                )}
              </>
            )}

    </>
  );
}

