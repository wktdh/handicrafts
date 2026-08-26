// @ts-nocheck
import { lazy, Suspense, useState } from "react";
import {
  ArrowDown,
  ArrowDownLeft,
  ArrowDownRight,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  ArrowUpLeft,
  ArrowUpRight,
  ChevronDown,
  ChevronUp,
  Crosshair,
  Pipette,
} from "lucide-react";
import BrandSitePreview from "./BrandSitePreview";

const LazyHexAlphaColorPicker = lazy(
  () => import("../../components/HexAlphaColorPicker"),
);

function BrandSiteSectionColorControl({
  label,
  value,
  fallback,
  onChange,
  open,
  onOpenChange,
}: {
  label: string;
  value?: string;
  fallback: string;
  onChange: (color: string) => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const color = value || fallback;
  const presetColors = ["#ffffff", "#000000", "#343434", "#dedede"];
  const pickScreenColor = async () => {
    const EyeDropper = (
      window as Window & {
        EyeDropper?: new () => { open: () => Promise<{ sRGBHex: string }> };
      }
    ).EyeDropper;
    if (!EyeDropper) return;
    try {
      const result = await new EyeDropper().open();
      onChange(result.sRGBHex);
    } catch {
      // The user closed the system picker; retain the current colour.
    }
  };
  return (
    <div className="brand-site-section-color-item">
      <span>{label}</span>
      <span className="brand-site-section-color-control">
        <button
          type="button"
          className="brand-site-section-color-swatch"
          aria-label={`选择${label}`}
          style={{ backgroundColor: color }}
          onClick={() => onOpenChange(!open)}
        />
        {open && (
          <span className="brand-site-section-color-popover">
            <Suspense fallback={<span className="brand-site-color-picker-loading" aria-busy="true" />}>
              <LazyHexAlphaColorPicker color={color} onChange={onChange} />
            </Suspense>
            <span className="brand-site-color-value">
              <i aria-hidden="true" style={{ backgroundColor: color }} />
              <input
                value={color.toUpperCase()}
                maxLength={9}
                aria-label={`${label}颜色值`}
                onChange={(event) => {
                  const next = event.target.value.trim();
                  if (/^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$/.test(next))
                    onChange(next);
                }}
              />
              <button
                type="button"
                className="brand-site-color-eyedropper"
                aria-label="从屏幕取色"
                title="从屏幕取色"
                onClick={() => void pickScreenColor()}
              >
                <Pipette size={16} />
              </button>
            </span>
            <span className="brand-site-color-presets">
              <b>调色板</b>
              <span>
                {presetColors.map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    aria-label={`使用${preset}颜色`}
                    style={{ backgroundColor: preset }}
                    onClick={() => onChange(preset)}
                  />
                ))}
              </span>
            </span>
          </span>
        )}
      </span>
    </div>
  );
}

export default function BrandSiteBuilder({ context }: { context: Record<string, any> }) {
  const {
    brandSite,
    shop,
    products,
    onChange,
    onSectionChange,
    onSectionMove,
    onSave,
    apiBase,
    compressImageForUpload,
    brandSiteAdditionalSections,
    previewDependencies,
  } = context;
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewDevice, setPreviewDevice] = useState<"desktop" | "mobile">(
    "desktop",
  );
  const [selectedEditorItem, setSelectedEditorItem] = useState<
    BrandSiteSectionId | "brand-logo"
  >(brandSite.sections?.[0]?.id || "hero");
  const setSelectedSectionId = (id: BrandSiteSectionId) =>
    setSelectedEditorItem(id);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [uploadingSectionId, setUploadingSectionId] =
    useState<BrandSiteSectionId | null>(null);
  const [openColorControl, setOpenColorControl] = useState<string | null>(null);
  const [draggedSectionId, setDraggedSectionId] =
    useState<BrandSiteSectionId | null>(null);
  const selectedSection =
    selectedEditorItem === "brand-logo"
      ? undefined
      : brandSite.sections?.find(
          (section) => section.id === selectedEditorItem,
        ) || brandSite.sections?.[0];
  const navigationLabels =
    selectedSection?.id === "header" && selectedSection.navLabels?.length
      ? selectedSection.navLabels
      : ["作品", "关于", "联系"];
  const navigationPageOptions = (brandSite.sections || [])
    .filter(
      (section) =>
        section.enabled &&
        section.id !== "announcement" &&
        section.id !== "header",
    )
    .map((section) => ({
      value: `#brand-site-${section.id}`,
      label: section.label,
    }));
  const defaultNavigationLinkFor = (index: number) => {
    if (index === 0) return "#brand-site-collection";
    if (index === 1)
      return navigationPageOptions.some(
        (option) => option.value === "#brand-site-story",
      )
        ? "#brand-site-story"
        : navigationPageOptions.some(
              (option) => option.value === "#brand-site-maker",
            )
          ? "#brand-site-maker"
          : "#brand-site-columns";
    return "#brand-site-footer";
  };
  const uploadLogo = async (file?: File) => {
    if (!file) return;
    setUploadingLogo(true);
    try {
      const data = await compressImageForUpload(file);
      const response = await fetch(`${apiBase}/api/media`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data, mediaType: "image" }),
      });
      const payload = (await response.json().catch(() => ({}))) as {
        url?: string;
        error?: string;
      };
      if (!response.ok || !payload.url)
        throw new Error(payload.error || "Logo 上传失败");
      onChange({ logoUrl: payload.url });
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Logo 上传失败");
    } finally {
      setUploadingLogo(false);
    }
  };
  const uploadSectionImage = async (
    sectionId: BrandSiteSectionId,
    file?: File,
  ) => {
    if (!file) return;
    setUploadingSectionId(sectionId);
    try {
      const data = await compressImageForUpload(file);
      const response = await fetch(`${apiBase}/api/media`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data, mediaType: "image" }),
      });
      const payload = (await response.json().catch(() => ({}))) as {
        url?: string;
        error?: string;
      };
      if (!response.ok || !payload.url)
        throw new Error(payload.error || "图片上传失败");
      onSectionChange(sectionId, { imageUrl: payload.url });
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "图片上传失败");
    } finally {
      setUploadingSectionId(null);
    }
  };
  const addModule = (sectionId: keyof typeof brandSiteAdditionalSections) => {
    if (brandSite.sections?.some((section) => section.id === sectionId)) return;
    onChange({
      sections: [
        ...(brandSite.sections || []),
        { ...brandSiteAdditionalSections[sectionId] },
      ],
    });
  };
  const moveSectionBefore = (
    sourceId: BrandSiteSectionId,
    targetId: BrandSiteSectionId,
  ) => {
    if (sourceId === targetId) return;
    const sections = [...(brandSite.sections || [])];
    const sourceIndex = sections.findIndex(
      (section) => section.id === sourceId,
    );
    const targetIndex = sections.findIndex(
      (section) => section.id === targetId,
    );
    if (sourceIndex < 0 || targetIndex < 0) return;
    const [source] = sections.splice(sourceIndex, 1);
    sections.splice(
      sourceIndex < targetIndex ? targetIndex - 1 : targetIndex,
      0,
      source,
    );
    onChange({ sections });
  };
  const toggleCollectionProduct = (
    section: BrandSiteSection,
    productId: string,
  ) => {
    const selected = section.productIds || [];
    if (selected.includes(productId))
      return onSectionChange(section.id, {
        productIds: selected.filter((id) => id !== productId),
      });
    if (selected.length >= 3) return window.alert("首页精选作品最多选择 3 件");
    onSectionChange(section.id, { productIds: [...selected, productId] });
  };
  return (
    <main className="brand-site-builder">
      <header className="brand-site-editor-toolbar">
        <div>
          <b>独立站编辑器</b>
          <span>草稿</span>
        </div>
        <div>
          <span>首页</span>
          <button
            className="secondary"
            type="button"
            onClick={() => setPreviewOpen(true)}
          >
            预览
          </button>
          <button
            className="primary"
            type="button"
            onClick={() => void onSave()}
          >
            保存
          </button>
        </div>
      </header>
      <div
        className={`brand-site-builder-layout ${selectedEditorItem === "brand-logo" ? "brand-site-panel-logo" : "brand-site-panel-section"}`}
      >
        <aside className="brand-site-builder-controls">
          <section className="brand-site-builder-brand-nav">
            {brandSite.sections?.some(
              (section) => section.id === "announcement",
            ) && (
              <button
                type="button"
                className={
                  selectedSection?.id === "announcement" ? "active" : ""
                }
                onClick={() => setSelectedSectionId("announcement")}
              >
                <span>公告栏</span>
                <small>公共区域</small>
              </button>
            )}
            <button
              type="button"
              className={selectedEditorItem === "brand-logo" ? "active" : ""}
              onClick={() => setSelectedEditorItem("brand-logo")}
            >
              <span>品牌标识</span>
              <small>全站设置</small>
            </button>
            <button
              type="button"
              className={selectedSection?.id === "header" ? "active" : ""}
              onClick={() => setSelectedSectionId("header")}
            >
              <span>导航栏</span>
              <small>全站设置</small>
            </button>
          </section>
          <section className="brand-site-builder-navigator">
            <small>点击区块可在右侧编辑，也可直接在画布中选择。</small>
            <div>
              {brandSite.sections
                ?.filter(
                  (section) =>
                    section.id !== "header" && section.id !== "announcement",
                )
                .map((section) => (
                  <button
                    type="button"
                    className={
                      selectedSection?.id === section.id ? "active" : ""
                    }
                    key={section.id}
                    draggable
                    onDragStart={(event) => {
                      event.dataTransfer.effectAllowed = "move";
                      setDraggedSectionId(section.id);
                    }}
                    onDragOver={(event) => {
                      event.preventDefault();
                      event.dataTransfer.dropEffect = "move";
                    }}
                    onDrop={(event) => {
                      event.preventDefault();
                      if (draggedSectionId)
                        moveSectionBefore(draggedSectionId, section.id);
                      setDraggedSectionId(null);
                    }}
                    onDragEnd={() => setDraggedSectionId(null)}
                    onClick={() => setSelectedSectionId(section.id)}
                  >
                    <span>{section.label}</span>
                    <small>{section.enabled ? "显示" : "隐藏"}</small>
                  </button>
                ))}
            </div>
            <b>添加区块</b>
            <span className="brand-site-navigator-add">
              {(
                Object.keys(
                  brandSiteAdditionalSections,
                ) as (keyof typeof brandSiteAdditionalSections)[]
              ).map((id) => {
                const item = brandSiteAdditionalSections[id];
                const added = brandSite.sections?.some(
                  (section) => section.id === id,
                );
                return (
                  <button
                    key={id}
                    type="button"
                    disabled={added}
                    onClick={() => {
                      addModule(id);
                      setSelectedSectionId(id);
                    }}
                  >
                    {added ? `${item.label}已添加` : `+ ${item.label}`}
                  </button>
                );
              })}
            </span>
          </section>
        </aside>
        <section
          className={`brand-site-builder-preview brand-site-preview-device-${previewDevice}`}
        >
          <div className="brand-site-builder-preview-head">
            <b>实时预览</b>
            <span className="brand-site-device-switch">
              <button
                type="button"
                className={previewDevice === "desktop" ? "active" : ""}
                onClick={() => setPreviewDevice("desktop")}
              >
                桌面端
              </button>
              <button
                type="button"
                className={previewDevice === "mobile" ? "active" : ""}
                onClick={() => setPreviewDevice("mobile")}
              >
                手机端
              </button>
            </span>
          </div>
          <div className="brand-site-preview-frame">
            <BrandSitePreview
              context={{
                brandSite,
                shop,
                products,
                selectedSectionId: selectedSection?.id,
                selectedBrandLogo: selectedEditorItem === "brand-logo",
                onSelectSection: setSelectedSectionId,
                ...previewDependencies,
              }}
            />
          </div>
        </section>
        <aside className="brand-site-builder-inspector">
          {selectedEditorItem === "brand-logo" ? (
            <>
              <header>
                <b>品牌标识</b>
                <small>全站设置</small>
              </header>
              <div className="brand-site-logo-editor">
                <span>站点标识</span>
                <label className="secondary">
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/avif"
                    disabled={uploadingLogo}
                    onChange={(event) => {
                      void uploadLogo(event.target.files?.[0]);
                      event.currentTarget.value = "";
                    }}
                  />
                  {uploadingLogo
                    ? "上传中…"
                    : brandSite.logoUrl
                      ? "更换 Logo"
                      : "上传 Logo"}
                </label>
                {brandSite.logoUrl && (
                  <>
                    <img src={brandSite.logoUrl} alt="Logo 预览" />
                    <button
                      type="button"
                      onClick={() => onChange({ logoUrl: "" })}
                    >
                      移除
                    </button>
                  </>
                )}
              </div>
              <label>
                站点名称
                <input
                  value={brandSite.siteName}
                  maxLength={60}
                  placeholder={shop.name}
                  onChange={(event) =>
                    onChange({ siteName: event.target.value })
                  }
                />
              </label>
              <label>
                品牌标语
                <input
                  value={brandSite.tagline}
                  maxLength={120}
                  placeholder="例如：把日常做成值得收藏的作品"
                  onChange={(event) =>
                    onChange({ tagline: event.target.value })
                  }
                />
              </label>
              <label className="brand-site-builder-color">
                主题色
                <input
                  type="color"
                  value={brandSite.themeColor}
                  onChange={(event) =>
                    onChange({ themeColor: event.target.value })
                  }
                />
              </label>
            </>
          ) : selectedSection ? (
            <>
              <header>
                <b>{selectedSection.label}</b>
                <small>区块设置</small>
              </header>
              <div className="brand-site-inspector-toggle">
                <input
                  type="checkbox"
                  id={`brand-site-section-visible-${selectedSection.id}`}
                  checked={selectedSection.enabled}
                  onChange={(event) =>
                    onSectionChange(selectedSection.id, {
                      enabled: event.target.checked,
                    })
                  }
                />
                <label
                  htmlFor={`brand-site-section-visible-${selectedSection.id}`}
                >
                  显示此区块
                </label>
              </div>
              {selectedSection.id !== "announcement" && (
                <div className="brand-site-inspector-order">
                  {
                    <>
                      <button
                        type="button"
                        onClick={() => onSectionMove(selectedSection.id, "up")}
                      >
                        <ChevronUp size={15} />
                        上移
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          onSectionMove(selectedSection.id, "down")
                        }
                      >
                        <ChevronDown size={15} />
                        下移
                      </button>
                    </>
                  }
                </div>
              )}
              {selectedSection.id === "announcement" ? (
                <label>
                  公告内容
                  <input
                    value={selectedSection.content}
                    maxLength={160}
                    onChange={(event) =>
                      onSectionChange(selectedSection.id, {
                        content: event.target.value,
                      })
                    }
                  />
                </label>
              ) : (
                selectedSection.id !== "header" && (
                  <>
                    <label>
                      标题
                      <input
                        value={selectedSection.title}
                        maxLength={80}
                        onChange={(event) =>
                          onSectionChange(selectedSection.id, {
                            title: event.target.value,
                          })
                        }
                      />
                    </label>
                    <label>
                      正文
                      <textarea
                        value={selectedSection.content}
                        maxLength={300}
                        onChange={(event) =>
                          onSectionChange(selectedSection.id, {
                            content: event.target.value,
                          })
                        }
                      />
                    </label>
                  </>
                )
              )}
              {selectedSection.id === "header" && (
                <fieldset className="brand-site-navigation-labels">
                  <legend>导航链接</legend>
                  {navigationLabels.map((label, index) => (
                    <div key={`${label}-${index}`}>
                      <div>
                        <input
                          value={label}
                          maxLength={16}
                          aria-label={`导航文字 ${index + 1}`}
                          placeholder="链接名称"
                          onChange={(event) => {
                            const labels = [...navigationLabels];
                            labels[index] = event.target.value;
                            onSectionChange(selectedSection.id, {
                              navLabels: labels,
                            });
                          }}
                        />
                        {(() => {
                          const savedLink =
                            selectedSection.navLinks?.[index] || "";
                          const selectedLink =
                            savedLink || defaultNavigationLinkFor(index);
                          const isCustom =
                            Boolean(savedLink) &&
                            !navigationPageOptions.some(
                              (option) => option.value === savedLink,
                            );
                          return (
                            <>
                              <select
                                value={isCustom ? "__custom__" : selectedLink}
                                aria-label={`跳转页面 ${index + 1}`}
                                onChange={(event) => {
                                  const links = [
                                    ...(selectedSection.navLinks || []),
                                  ];
                                  links[index] =
                                    event.target.value === "__custom__"
                                      ? "https://"
                                      : event.target.value;
                                  onSectionChange(selectedSection.id, {
                                    navLinks: links,
                                  });
                                }}
                              >
                                {navigationPageOptions.map((option) => (
                                  <option
                                    key={option.value}
                                    value={option.value}
                                  >
                                    {option.label}
                                  </option>
                                ))}
                                <option value="__custom__">自定义链接</option>
                              </select>
                              {isCustom && (
                                <input
                                  value={savedLink}
                                  maxLength={240}
                                  aria-label={`自定义链接地址 ${index + 1}`}
                                  placeholder="输入完整网址或锚点"
                                  onChange={(event) => {
                                    const links = [
                                      ...(selectedSection.navLinks || []),
                                    ];
                                    links[index] = event.target.value;
                                    onSectionChange(selectedSection.id, {
                                      navLinks: links,
                                    });
                                  }}
                                />
                              )}
                            </>
                          );
                        })()}
                      </div>
                      <button
                        type="button"
                        disabled={navigationLabels.length <= 1}
                        onClick={() => {
                          const labels = [...navigationLabels];
                          const links = [...(selectedSection.navLinks || [])];
                          labels.splice(index, 1);
                          links.splice(index, 1);
                          onSectionChange(selectedSection.id, {
                            navLabels: labels,
                            navLinks: links,
                          });
                        }}
                      >
                        删除
                      </button>
                    </div>
                  ))}
                  <button
                    type="button"
                    onClick={() => {
                      onSectionChange(selectedSection.id, {
                        navLabels: [...navigationLabels, "新链接"],
                        navLinks: [...(selectedSection.navLinks || []), ""],
                      });
                    }}
                  >
                    添加链接
                  </button>
                </fieldset>
              )}
              {selectedSection.id === "hero" && (
                <fieldset className="brand-site-hero-position">
                  <legend>内容位置</legend>
                  {(
                    [
                      ["top-left", "左上", ArrowUpLeft],
                      ["top-center", "上方居中", ArrowUp],
                      ["top-right", "右上", ArrowUpRight],
                      ["center-left", "左侧居中", ArrowLeft],
                      ["center", "居中", Crosshair],
                      ["center-right", "右侧居中", ArrowRight],
                      ["bottom-left", "左下", ArrowDownLeft],
                      ["bottom-center", "下方居中", ArrowDown],
                      ["bottom-right", "右下", ArrowDownRight],
                    ] as [
                      NonNullable<BrandSiteSection["heroContentPosition"]>,
                      string,
                      LucideIcon,
                    ][]
                  ).map(([value, label, Icon]) => (
                    <button
                      key={value}
                      type="button"
                      title={label}
                      aria-label={label}
                      className={
                        (selectedSection.heroContentPosition || "center") ===
                        value
                          ? "active"
                          : ""
                      }
                      onClick={() =>
                        onSectionChange(selectedSection.id, {
                          heroContentPosition:
                            value as BrandSiteSection["heroContentPosition"],
                        })
                      }
                    >
                      <Icon size={15} strokeWidth={1.7} aria-hidden="true" />
                    </button>
                  ))}
                </fieldset>
              )}
              <fieldset className="brand-site-section-colors">
                <legend>区块配色</legend>
                <BrandSiteSectionColorControl
                  label="背景色"
                  value={selectedSection.backgroundColor}
                  fallback="#ffffff"
                  open={openColorControl === "background"}
                  onOpenChange={(open) =>
                    setOpenColorControl(open ? "background" : null)
                  }
                  onChange={(backgroundColor) =>
                    onSectionChange(selectedSection.id, { backgroundColor })
                  }
                />
                <BrandSiteSectionColorControl
                  label="文字色"
                  value={selectedSection.textColor}
                  fallback="#292825"
                  open={openColorControl === "text"}
                  onOpenChange={(open) =>
                    setOpenColorControl(open ? "text" : null)
                  }
                  onChange={(textColor) =>
                    onSectionChange(selectedSection.id, { textColor })
                  }
                />
                {selectedSection.buttonLabel !== undefined && (
                  <BrandSiteSectionColorControl
                    label="按钮色"
                    value={selectedSection.buttonColor}
                    fallback={brandSite.themeColor}
                    open={openColorControl === "button"}
                    onOpenChange={(open) =>
                      setOpenColorControl(open ? "button" : null)
                    }
                    onChange={(buttonColor) =>
                      onSectionChange(selectedSection.id, { buttonColor })
                    }
                  />
                )}
              </fieldset>
              {(selectedSection.id === "hero" ||
                selectedSection.id === "image-text") && (
                <div className="brand-site-module-image">
                  <span>
                    {selectedSection.id === "hero" ? "横幅图片" : "模块图片"}
                  </span>
                  <label className="secondary">
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp,image/avif"
                      disabled={uploadingSectionId === selectedSection.id}
                      onChange={(event) => {
                        void uploadSectionImage(
                          selectedSection.id,
                          event.target.files?.[0],
                        );
                        event.currentTarget.value = "";
                      }}
                    />
                    {uploadingSectionId === selectedSection.id
                      ? "上传中…"
                      : selectedSection.imageUrl
                        ? "更换图片"
                        : "上传图片"}
                  </label>
                  {selectedSection.imageUrl && (
                    <>
                      <img src={selectedSection.imageUrl} alt="模块图片预览" />
                      <button
                        type="button"
                        onClick={() =>
                          onSectionChange(selectedSection.id, { imageUrl: "" })
                        }
                      >
                        移除
                      </button>
                    </>
                  )}
                </div>
              )}
              {selectedSection.id === "collection" && (
                <fieldset className="brand-site-product-picker">
                  <legend>精选作品（最多 3 件）</legend>
                  {products.slice(0, 9).map((product) => (
                    <label key={product.id}>
                      <input
                        type="checkbox"
                        checked={(selectedSection.productIds || []).includes(
                          String(product.id),
                        )}
                        onChange={() =>
                          toggleCollectionProduct(
                            selectedSection,
                            String(product.id),
                          )
                        }
                      />
                      {product.title}
                    </label>
                  ))}
                  {!products.length && <small>请先发布作品。</small>}
                </fieldset>
              )}
              {selectedSection.buttonLabel !== undefined && (
                <label>
                  按钮文字
                  <input
                    value={selectedSection.buttonLabel}
                    maxLength={30}
                    onChange={(event) =>
                      onSectionChange(selectedSection.id, {
                        buttonLabel: event.target.value,
                      })
                    }
                  />
                </label>
              )}
            </>
          ) : (
            <p>从左侧或页面画布选择一个区块开始编辑。</p>
          )}
        </aside>
      </div>
      {previewOpen && (
        <div
          className={`brand-site-preview-dialog brand-site-preview-device-${previewDevice}`}
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setPreviewOpen(false);
          }}
        >
          <section role="dialog" aria-modal="true" aria-label="网站预览">
            <header>
              <b>网站预览</b>
              <span className="brand-site-device-switch">
                <button
                  type="button"
                  className={previewDevice === "desktop" ? "active" : ""}
                  onClick={() => setPreviewDevice("desktop")}
                >
                  桌面端
                </button>
                <button
                  type="button"
                  className={previewDevice === "mobile" ? "active" : ""}
                  onClick={() => setPreviewDevice("mobile")}
                >
                  手机端
                </button>
                <button
                  className="secondary"
                  type="button"
                  onClick={() => setPreviewOpen(false)}
                >
                  关闭预览
                </button>
              </span>
            </header>
            <div className="brand-site-preview-frame">
              <BrandSitePreview
                context={{ brandSite, shop, products, ...previewDependencies }}
              />
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
