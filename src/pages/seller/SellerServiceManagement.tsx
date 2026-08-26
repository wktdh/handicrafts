import { useEffect, useState } from "react";

// @ts-nocheck
export default function SellerServiceManagement({
  shopId,
  section,
  apiBase,
  imageCompressor,
  operatingCategories,
}: {
  shopId: string;
  section: "verification" | "members" | "support";
  apiBase: string;
  imageCompressor: (file: File) => Promise<string>;
  operatingCategories: readonly string[];
}) {
  type DocumentType =
    | "identity_front"
    | "identity_back"
    | "business_license"
    | "authorization"
    | "other";
  type DocumentUploadKind =
    "identity_card" | "business_license" | "authorization" | "other";
  type VerificationDocument = {
    id?: string;
    type: DocumentType;
    url: string;
    status?: string;
    reviewNote?: string;
  };
  type Verification = {
    status: string;
    legalName: string;
    identityNumber: string;
    contactPhone: string;
    businessAddress?: string;
    operatingCategories?: string[];
    expiresAt?: string | null;
    application?: {
      status: string;
      reviewNote?: string;
      rejectionCode?: string;
      supplementDueAt?: string | null;
      businessType?: "individual" | "enterprise";
      legalRepresentative?: string;
      businessLicenseNo?: string;
      businessAddress?: string;
      evidence?: string[];
      documents?: VerificationDocument[];
    } | null;
  };
  type Staff = {
    id: string;
    name: string;
    role: "operator" | "fulfillment" | "customer_service";
    status: "active" | "disabled";
    permissions: string[];
  };
  type Audit = {
    id: string;
    action: string;
    actor: string;
    createdAt: string;
    detail: Record<string, unknown>;
  };
  type Ticket = {
    id: string;
    subject: string;
    status: string;
    priority: string;
    buyer: string;
  };
  const permissionOptions = [
    "products",
    "inventory",
    "orders",
    "shipping",
    "messages",
    "after_sales",
    "reviews",
    "settings",
  ];
  const [draft, setDraft] = useState({
    legalName: "",
    identityNumber: "",
    contactPhone: "",
    businessType: "individual" as "individual" | "enterprise",
    legalRepresentative: "",
    businessLicenseNo: "",
    businessAddress: "",
    operatingCategories: [] as string[],
    evidence: [] as string[],
    documents: [] as VerificationDocument[],
  });
  const [documentType, setDocumentType] =
    useState<DocumentUploadKind>("identity_card");
  const [staff, setStaff] = useState<Staff[]>([]);
  const [member, setMember] = useState({
    userId: "",
    role: "customer_service" as Staff["role"],
    permissions: [] as string[],
  });
  const [audits, setAudits] = useState<Audit[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [ticketReply, setTicketReply] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const load = async () => {
    const [verificationResponse, staffResponse, auditResponse, ticketResponse] =
      await Promise.all([
        fetch(`${apiBase}/api/seller/verification`, {
          credentials: "include",
        }),
        fetch(`${apiBase}/api/seller/staff`, { credentials: "include" }),
        fetch(`${apiBase}/api/seller/staff/audit`, { credentials: "include" }),
        fetch(`${apiBase}/api/seller/support/tickets`, {
          credentials: "include",
        }),
      ]);
    if (verificationResponse.ok) {
      const next = (
        (await verificationResponse.json()) as { verification: Verification }
      ).verification;
      setDraft((value) => ({
        ...value,
        legalName: next.legalName || value.legalName,
        identityNumber: next.identityNumber || value.identityNumber,
        contactPhone: next.contactPhone || value.contactPhone,
        businessAddress: next.businessAddress || value.businessAddress,
        operatingCategories: next.operatingCategories?.length
          ? next.operatingCategories
          : value.operatingCategories,
      }));
    }
    if (staffResponse.ok)
      setStaff(
        ((await staffResponse.json()) as { staff: Staff[] }).staff || [],
      );
    if (auditResponse.ok)
      setAudits(((await auditResponse.json()) as { logs: Audit[] }).logs || []);
    if (ticketResponse.ok)
      setTickets(
        ((await ticketResponse.json()) as { tickets: Ticket[] }).tickets || [],
      );
  };
  useEffect(() => {
    void load();
  }, []);
  const uploadDocument = async (file: File | undefined, type: DocumentType) => {
    if (!file) return;
    const data = await imageCompressor(file);
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
    setDraft((value) => {
      const replaced = value.documents.filter((item) => item.type !== type);
      const replacedUrls = new Set(
        value.documents
          .filter((item) => item.type === type)
          .map((item) => item.url),
      );
      return {
        ...value,
        evidence: [
          ...value.evidence.filter((url) => !replacedUrls.has(url)),
          payload.url!,
        ].slice(0, 6),
        documents: [...replaced, { type, url: payload.url! }].slice(0, 8),
      };
    });
  };
  const togglePermission = (permissions: string[], permission: string) =>
    permissions.includes(permission)
      ? permissions.filter((item) => item !== permission)
      : [...permissions, permission];
  const saveStaff = async (item: Staff, patch: Partial<Staff>) => {
    const response = await fetch(
      `${apiBase}/api/seller/staff/${encodeURIComponent(item.id)}`,
      {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role: patch.role || item.role,
          status: patch.status || item.status,
          permissions: patch.permissions || item.permissions,
        }),
      },
    );
    const payload = (await response.json().catch(() => ({}))) as {
      error?: string;
    };
    if (!response.ok) return setNotice(payload.error || "成员设置保存失败");
    void load();
  };
  const documentLabels: Record<DocumentType, string> = {
    identity_front: "身份证人像面",
    identity_back: "身份证国徽面",
    business_license: "营业执照",
    authorization: "授权书",
    other: "其他材料",
  };
  const removeDocument = (url: string) =>
    setDraft((value) => ({
      ...value,
      documents: value.documents.filter((item) => item.url !== url),
      evidence: value.evidence.filter((item) => item !== url),
    }));
  return (
    <section
      className={`studio-panel operation-settings seller-service-management seller-service-${section}`}
    >
      {notice && <p className="auth-error">{notice}</p>}
      {section !== "support" && (
        <div className="seller-service-grid">
          <form
            className="seller-service-section seller-verification-section"
            onSubmit={async (event) => {
              event.preventDefault();
              const response = await fetch(
                `${apiBase}/api/seller/verification`,
                {
                  method: "POST",
                  credentials: "include",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify(draft),
                },
              );
              const payload = (await response.json().catch(() => ({}))) as {
                error?: string;
                status?: string;
              };
              if (!response.ok)
                return setNotice(payload.error || "认证提交失败");
              setNotice(
                payload.status === "approved"
                  ? "认证已通过，可以发布作品"
                  : "认证资料已提交",
              );
              setDraft((value) => ({ ...value, evidence: [], documents: [] }));
              void load();
            }}
          >
            <div className="seller-service-section-head">
              <div>
                <h3>卖家认证</h3>
                <p>提交主体资料与凭证。</p>
              </div>
            </div>
            <div className="seller-form-grid">
              <label>
                <span>主体类型</span>
                <select
                  value={draft.businessType}
                  onChange={(event) =>
                    setDraft((value) => ({
                      ...value,
                      businessType: event.target
                        .value as typeof value.businessType,
                    }))
                  }
                >
                  <option value="individual">个人主体</option>
                  <option value="enterprise">企业主体</option>
                </select>
              </label>
              <label>
                <span>主体名称</span>
                <input
                  required
                  minLength={2}
                  maxLength={80}
                  value={draft.legalName}
                  onChange={(event) =>
                    setDraft((value) => ({
                      ...value,
                      legalName: event.target.value,
                    }))
                  }
                  placeholder="请输入 2-80 个字的姓名或主体名称"
                  title="主体名称需为 2-80 个字"
                />
              </label>
              <label>
                <span>证件号码</span>
                <input
                  required
                  pattern="[A-Za-z0-9]{6,32}"
                  minLength={6}
                  maxLength={32}
                  value={draft.identityNumber}
                  onChange={(event) =>
                    setDraft((value) => ({
                      ...value,
                      identityNumber: event.target.value,
                    }))
                  }
                  onInput={(event) => event.currentTarget.setCustomValidity("")}
                  onInvalid={(event) =>
                    event.currentTarget.setCustomValidity(
                      "证件号码需为 6-32 位字母或数字",
                    )
                  }
                  placeholder="请输入 6-32 位字母或数字的证件号码"
                  title="证件号码需为 6-32 位字母或数字"
                />
              </label>
              <label>
                <span>联系电话</span>
                <input
                  required
                  inputMode="numeric"
                  pattern="[0-9]{6,20}"
                  maxLength={20}
                  value={draft.contactPhone}
                  onChange={(event) =>
                    setDraft((value) => ({
                      ...value,
                      contactPhone: event.target.value,
                    }))
                  }
                  placeholder="请输入 6-20 位数字联系电话"
                  title="联系电话需为 6-20 位数字"
                />
              </label>
              <label className="seller-form-wide">
                <span>经营地址</span>
                <input
                  required
                  minLength={5}
                  maxLength={300}
                  value={draft.businessAddress}
                  onChange={(event) =>
                    setDraft((value) => ({
                      ...value,
                      businessAddress: event.target.value,
                    }))
                  }
                  placeholder="请输入 5-300 个字的常用经营地址"
                  title="经营地址需为 5-300 个字"
                />
              </label>
              <div className="seller-form-wide seller-form-field">
                <span>经营类目</span>
                <select
                  required
                  aria-label="经营类目"
                  value={draft.operatingCategories[0] || ""}
                  onChange={(event) =>
                    setDraft((value) => ({
                      ...value,
                      operatingCategories: event.target.value
                        ? [event.target.value]
                        : [],
                    }))
                  }
                >
                  <option value="">请选择经营类目</option>
                  {operatingCategories.map((category) => (
                    <option key={category} value={category}>
                      {category}
                    </option>
                  ))}
                </select>
              </div>
              {draft.businessType === "enterprise" && (
                <>
                  <label>
                    <span>法定代表人</span>
                    <input
                      required
                      value={draft.legalRepresentative}
                      onChange={(event) =>
                        setDraft((value) => ({
                          ...value,
                          legalRepresentative: event.target.value,
                        }))
                      }
                      placeholder="请输入法定代表人姓名"
                    />
                  </label>
                  <label>
                    <span>营业执照编号</span>
                    <input
                      required
                      value={draft.businessLicenseNo}
                      onChange={(event) =>
                        setDraft((value) => ({
                          ...value,
                          businessLicenseNo: event.target.value,
                        }))
                      }
                      placeholder="请输入营业执照编号"
                    />
                  </label>
                </>
              )}
            </div>
            <div className="seller-document-section">
              <div>
                <h3>认证材料</h3>
                <small>
                  支持 JPG、PNG、WebP 格式。身份证请分别上传人像面和国徽面。
                </small>
              </div>
              <div className="seller-document-controls">
                <select
                  value={documentType}
                  onChange={(event) =>
                    setDocumentType(event.target.value as DocumentUploadKind)
                  }
                >
                  <option value="identity_card">身份证</option>
                  <option value="business_license">营业执照</option>
                  <option value="authorization">授权书</option>
                  <option value="other">其他材料</option>
                </select>
                {documentType !== "identity_card" && (
                  <label className="icon-upload">
                    上传
                    {documentType === "business_license"
                      ? "营业执照"
                      : documentType === "authorization"
                        ? "授权书"
                        : "材料"}
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        event.currentTarget.value = "";
                        void uploadDocument(file, documentType).catch(
                          (error: Error) => setNotice(error.message),
                        );
                      }}
                    />
                  </label>
                )}
              </div>
              {documentType === "identity_card" ? (
                <div className="seller-identity-upload-grid">
                  {(["identity_front", "identity_back"] as DocumentType[]).map(
                    (type) => {
                      const item = draft.documents.find(
                        (document) => document.type === type,
                      );
                      return (
                        <div
                          className={`seller-identity-upload-card${item ? " uploaded" : ""}`}
                          key={type}
                        >
                          {item ? (
                            <>
                              <img src={item.url} alt={documentLabels[type]} />
                              <div className="seller-identity-upload-caption">
                                <span>{documentLabels[type]}</span>
                                <button
                                  type="button"
                                  className="remove"
                                  onClick={() => removeDocument(item.url)}
                                >
                                  删除
                                </button>
                              </div>
                            </>
                          ) : (
                            <label>
                              <span className="seller-identity-upload-plus">
                                +
                              </span>
                              <b>上传{documentLabels[type]}</b>
                              <small>点击选择图片</small>
                              <input
                                type="file"
                                accept="image/jpeg,image/png,image/webp"
                                onChange={(event) => {
                                  const file = event.target.files?.[0];
                                  event.currentTarget.value = "";
                                  void uploadDocument(file, type).catch(
                                    (error: Error) => setNotice(error.message),
                                  );
                                }}
                              />
                            </label>
                          )}
                        </div>
                      );
                    },
                  )}
                </div>
              ) : (
                <div className="media-preview-grid seller-document-previews">
                  {draft.documents
                    .filter((item) => item.type === documentType)
                    .map((item, index) => (
                      <figure key={`${item.url}-${index}`}>
                        <img src={item.url} alt={documentLabels[item.type]} />
                        <figcaption>
                          {documentLabels[item.type]}
                          <button
                            type="button"
                            className="remove"
                            onClick={() => removeDocument(item.url)}
                          >
                            删除
                          </button>
                        </figcaption>
                      </figure>
                    ))}
                </div>
              )}
            </div>
            <div className="seller-section-actions">
              <button className="primary">提交认证</button>
            </div>
          </form>
          <section className="seller-service-section seller-members-section">
            <div className="seller-service-section-head">
              <div>
                <h3>店铺成员与权限</h3>
                <p>按岗位分配可访问的工作台功能。</p>
              </div>
              <span className="seller-member-count">{staff.length} 位成员</span>
            </div>
            <div className="seller-member-create">
              <input
                value={member.userId}
                onChange={(event) =>
                  setMember({ ...member, userId: event.target.value })
                }
                placeholder="已注册账号 ID"
              />
              <select
                value={member.role}
                onChange={(event) =>
                  setMember({
                    ...member,
                    role: event.target.value as Staff["role"],
                  })
                }
              >
                <option value="operator">运营</option>
                <option value="fulfillment">发货</option>
                <option value="customer_service">客服</option>
              </select>
              <button
                className="secondary"
                type="button"
                onClick={async () => {
                  const response = await fetch(`${apiBase}/api/seller/staff`, {
                    method: "POST",
                    credentials: "include",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ shopId, ...member }),
                  });
                  const payload = (await response.json().catch(() => ({}))) as {
                    error?: string;
                  };
                  if (!response.ok)
                    return setNotice(payload.error || "成员保存失败");
                  setMember({
                    userId: "",
                    role: "customer_service",
                    permissions: [],
                  });
                  void load();
                }}
              >
                添加成员
              </button>
            </div>
            <fieldset className="seller-permission-picker">
              <legend>新成员权限</legend>
              <div className="staff-permissions">
                {permissionOptions.map((permission) => (
                  <label key={permission}>
                    <input
                      type="checkbox"
                      checked={member.permissions.includes(permission)}
                      onChange={() =>
                        setMember((value) => ({
                          ...value,
                          permissions: togglePermission(
                            value.permissions,
                            permission,
                          ),
                        }))
                      }
                    />
                    {permission}
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="seller-member-list">
              {staff.map((item) => (
                <article key={item.id} className="seller-member-item">
                  <header>
                    <div>
                      <b>{item.name}</b>
                      <small>{item.id}</small>
                    </div>
                    <span className={`seller-member-status ${item.status}`}>
                      {item.status === "active" ? "使用中" : "已停用"}
                    </span>
                  </header>
                  <div className="seller-member-role">
                    <label>
                      岗位
                      <select
                        value={item.role}
                        onChange={(event) =>
                          void saveStaff(item, {
                            role: event.target.value as Staff["role"],
                          })
                        }
                      >
                        <option value="operator">运营</option>
                        <option value="fulfillment">发货</option>
                        <option value="customer_service">客服</option>
                      </select>
                    </label>
                  </div>
                  <fieldset className="seller-permission-picker">
                    <legend>可用权限</legend>
                    <div className="staff-permissions">
                      {permissionOptions.map((permission) => (
                        <label key={permission}>
                          <input
                            type="checkbox"
                            checked={item.permissions.includes(permission)}
                            onChange={() =>
                              void saveStaff(item, {
                                permissions: togglePermission(
                                  item.permissions,
                                  permission,
                                ),
                              })
                            }
                          />
                          {permission}
                        </label>
                      ))}
                    </div>
                  </fieldset>
                  <footer>
                    <button
                      type="button"
                      className="secondary"
                      onClick={() =>
                        void saveStaff(item, {
                          status:
                            item.status === "active" ? "disabled" : "active",
                        })
                      }
                    >
                      {item.status === "active" ? "停用" : "启用"}
                    </button>
                    <button
                      type="button"
                      className="danger"
                      onClick={async () => {
                        if (!window.confirm(`移除成员 ${item.name}？`)) return;
                        const response = await fetch(
                          `${apiBase}/api/seller/staff/${encodeURIComponent(item.id)}`,
                          { method: "DELETE", credentials: "include" },
                        );
                        if (!response.ok) return setNotice("成员移除失败");
                        void load();
                      }}
                    >
                      移除
                    </button>
                  </footer>
                </article>
              ))}
              {!staff.length && (
                <p className="seller-empty-state">
                  暂无成员，可通过上方账号 ID 添加店铺协作者。
                </p>
              )}
            </div>
          </section>
        </div>
      )}
      {section === "members" && (
        <section className="seller-service-section seller-audit-section">
          <div className="seller-service-section-head">
            <div>
              <h3>成员操作审计</h3>
              <p>保留最近 30 条成员操作记录。</p>
            </div>
          </div>
          <div className="seller-audit-list">
            {audits.slice(0, 30).map((item) => (
              <article key={item.id}>
                <div>
                  <b>{item.action}</b>
                  <small>
                    {item.actor} · {item.createdAt}
                  </small>
                </div>
                <p>
                  {Object.entries(item.detail || {})
                    .map(([key, value]) => `${key}: ${String(value)}`)
                    .join(" · ") || "无附加信息"}
                </p>
              </article>
            ))}
            {!audits.length && (
              <p className="seller-empty-state">暂无成员操作记录</p>
            )}
          </div>
        </section>
      )}
      {section === "support" && (
        <section className="seller-service-section seller-tickets-section">
          <div className="seller-service-section-head">
            <div>
              <h3>客服工单</h3>
              <p>及时回复买家咨询，保持服务进度清晰。</p>
            </div>
            <span className="seller-member-count">{tickets.length} 条工单</span>
          </div>
          <div className="seller-ticket-list">
            {tickets.map((ticket) => (
              <article key={ticket.id}>
                <header>
                  <div>
                    <b>{ticket.subject}</b>
                    <small>
                      {ticket.buyer} · {ticket.priority} · {ticket.status}
                    </small>
                  </div>
                  <span className="seller-ticket-status">{ticket.status}</span>
                </header>
                <div className="seller-ticket-reply">
                  <input
                    value={ticketReply[ticket.id] || ""}
                    onChange={(event) =>
                      setTicketReply((value) => ({
                        ...value,
                        [ticket.id]: event.target.value,
                      }))
                    }
                    placeholder="回复买家"
                  />
                  <button
                    className="secondary"
                    onClick={async () => {
                      const content = ticketReply[ticket.id]?.trim();
                      if (!content) return;
                      const response = await fetch(
                        `${apiBase}/api/seller/support/tickets/${encodeURIComponent(ticket.id)}/messages`,
                        {
                          method: "POST",
                          credentials: "include",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({ content }),
                        },
                      );
                      if (!response.ok) return setNotice("工单回复失败");
                      setTicketReply((value) => ({
                        ...value,
                        [ticket.id]: "",
                      }));
                      void load();
                    }}
                  >
                    发送回复
                  </button>
                </div>
              </article>
            ))}
            {!tickets.length && (
              <p className="seller-empty-state">暂无店铺工单</p>
            )}
          </div>
        </section>
      )}
    </section>
  );
}
