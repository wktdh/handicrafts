// @ts-nocheck
import { Globe2 } from "lucide-react";

export default function SellerBrandSitePage({ context }: { context: Record<string, any> }) {
  const { studioText, brandSite, openPublicBrandSite, openBrandSiteEditor, updateBrandSite, saveBrandSite } = context;
  return <>
            <div className="studio-title">
              <div>
                <h1>{studioText("我的独立站", "Brand site")}</h1>
                <p>
                  选择建站模板并绑定自己购买的域名；页面设计请在建站编辑器完成。
                </p>
              </div>
              <div className="brand-site-title-actions">
                <span
                  className={`status status-${brandSite.status === "published" ? "active" : "pending"}`}
                >
                  {brandSite.status === "published" ? "已启用" : "草稿"}
                </span>
                {brandSite.status === "published" && (
                  <button
                    className="secondary"
                    type="button"
                    onClick={openPublicBrandSite}
                  >
                    查看独立站
                  </button>
                )}
                <button
                  className="secondary"
                  type="button"
                  onClick={openBrandSiteEditor}
                >
                  打开建站编辑器
                </button>
              </div>
            </div>
            <section className="studio-panel settings-form brand-site-settings">
              <div className="operation-settings brand-site-theme-market">
                <div>
                  <b>探索模板</b>
                  <small>
                    选择一个平台主题作为店铺独立站的基础；切换主题会重置为该主题的默认模块与文案。
                  </small>
                </div>
                <div className="brand-site-market-grid">
                  {(
                    Object.keys(brandSiteTemplateInfo) as BrandSiteTemplate[]
                  ).map((id) => {
                    const info = brandSiteTemplateInfo[id];
                    const selected = brandSite.template === id;
                    return (
                      <article
                        className={`brand-site-market-card brand-site-market-${id}${selected ? " active" : ""}`}
                        key={id}
                      >
                        <div
                          className="brand-site-market-thumb"
                          aria-label={`${info.title}主题缩略图`}
                        >
                          <span>手作集</span>
                          <img
                            src={brandSiteTemplatePreviewImages[id]}
                            alt=""
                          />
                          <i />
                          <i />
                          <i />
                          <i />
                        </div>
                        <div>
                          <b>{info.title}</b>
                          <small>{info.description}</small>
                          <span>
                            {info.tags.map((tag) => (
                              <em key={tag}>{tag}</em>
                            ))}
                          </span>
                        </div>
                        <button
                          type="button"
                          className={selected ? "secondary" : "primary"}
                          onClick={() =>
                            updateBrandSite({
                              template: id,
                              sections: createBrandSiteSections(id),
                            })
                          }
                        >
                          {selected ? "正在使用" : "使用此模板"}
                        </button>
                      </article>
                    );
                  })}
                  <article className="brand-site-market-more">
                    <b>更多主题即将上线</b>
                    <p>平台会持续提供适合手作、工作室与品牌商店的新主题。</p>
                  </article>
                </div>
              </div>
              <div className="operation-settings">
                <div>
                  <b>绑定自有域名</b>
                  <small>域名需由卖家自行购买；平台不代售域名。</small>
                </div>
                <label>
                  域名
                  <input
                    value={brandSite.domain}
                    inputMode="url"
                    placeholder="www.yourbrand.com"
                    onChange={(event) =>
                      updateBrandSite({
                        domain: event.target.value.trim().toLowerCase(),
                      })
                    }
                  />
                </label>
                <p className="brand-site-domain-hint">
                  保存后，请在域名服务商处将域名 CNAME
                  解析至平台提供的接入地址。域名验证与 SSL
                  证书将在正式发布服务接入后完成。
                </p>
              </div>
              <div className="seller-section-actions brand-site-actions">
                <button
                  className="secondary"
                  type="button"
                  onClick={() => void saveBrandSite()}
                >
                  保存草稿
                </button>
                <button
                  className="primary"
                  type="button"
                  onClick={() => {
                    if (!brandSite.domain.trim())
                      return toast("请先填写已购买的独立站域名");
                    void saveBrandSite(true);
                  }}
                >
                  <Globe2 size={17} />
                  启用我的独立站
                </button>
              </div>
            </section>
  </>;
}

