import { useEffect, useState, type FormEvent } from "react";
import { ArrowLeft, ChevronRight, CreditCard, Heart, Package, Settings2, Store } from "lucide-react";

const API_BASE =
  (import.meta as ImportMeta & { env?: { VITE_API_BASE?: string } }).env
    ?.VITE_API_BASE ?? "";

type Account = {
  name: string;
  phone?: string;
  email?: string;
  role: "buyer" | "seller" | "admin";
};

export function AccountSecurity({
  account,
  onBack,
}: {
  account: Account;
  onBack: () => void;
}) {
  const [security, setSecurity] = useState<{
    phone?: string;
    email?: string;
    phoneVerified: boolean;
    emailVerified: boolean;
    passwordChangedAt?: string;
    lastLoginAt?: string;
  } | null>(null);
  const [sessions, setSessions] = useState<
    {
      id: string;
      current: boolean;
      createdAt: string;
      lastSeenAt?: string;
      expiresAt: string;
      userAgent?: string;
      ipAddress?: string;
    }[]
  >([]);
  const [events, setEvents] = useState<
    {
      success: boolean;
      reason?: string;
      ipAddress?: string;
      createdAt: string;
    }[]
  >([]);
  const [destination, setDestination] = useState("");
  const [code, setCode] = useState("");
  const [developmentCode, setDevelopmentCode] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [notice, setNotice] = useState("");
  const load = async () => {
    const response = await fetch(`${API_BASE}/api/auth/security`, {
      credentials: "include",
    });
    const payload = (await response.json().catch(() => null)) as {
      security?: typeof security;
      sessions?: typeof sessions;
      loginEvents?: typeof events;
    } | null;
    if (response.ok && payload?.security) {
      setSecurity(payload.security);
      setSessions(payload.sessions || []);
      setEvents(payload.loginEvents || []);
    }
  };
  useEffect(() => {
    void load();
  }, []);
  const requestCode = async (value: string) => {
    setNotice("");
    const response = await fetch(`${API_BASE}/api/auth/request-verification`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ destination: value, purpose: "contact_verify" }),
    });
    const payload = (await response.json().catch(() => ({}))) as {
      error?: string;
      developmentCode?: string;
    };
    if (!response.ok) return setNotice(payload.error || "验证码发送失败");
    setDestination(value);
    setDevelopmentCode(payload.developmentCode || "");
    setNotice("验证码已发送");
  };
  const verifyContact = async () => {
    const response = await fetch(`${API_BASE}/api/auth/verify-contact`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ destination, code }),
    });
    const payload = (await response.json().catch(() => ({}))) as {
      error?: string;
    };
    if (!response.ok) return setNotice(payload.error || "验证失败");
    setCode("");
    setDevelopmentCode("");
    setNotice("联系方式已验证");
    void load();
  };
  const changePassword = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const response = await fetch(`${API_BASE}/api/auth/change-password`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ currentPassword, password: newPassword }),
    });
    const payload = (await response.json().catch(() => ({}))) as {
      error?: string;
    };
    if (!response.ok) return setNotice(payload.error || "密码修改失败");
    setCurrentPassword("");
    setNewPassword("");
    setNotice("密码已修改，其他设备已退出登录");
    void load();
  };
  const revokeSession = async (sessionId: string) => {
    const response = await fetch(`${API_BASE}/api/auth/sessions/revoke`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId }),
    });
    const payload = (await response.json().catch(() => ({}))) as {
      error?: string;
    };
    if (!response.ok) return setNotice(payload.error || "会话移除失败");
    setNotice("设备已退出登录");
    void load();
  };
  return (
    <main className="container page section security-page">
      <button className="back" onClick={onBack}>
        <ArrowLeft size={18} />
        Back
      </button>
      <div className="page-title">
        <div>
          <h1>Account & security</h1>
          <p>Manage security settings for {account.name}.</p>
        </div>
      </div>
      {notice && <p className="auth-error">{notice}</p>}
      <section className="security-card">
        <h2>Contact verification</h2>
        {security?.phone && (
          <div className="security-contact">
            <span>Phone: {security.phone}</span>
            <b>{security.phoneVerified ? "Verified" : "Not verified"}</b>
            {!security.phoneVerified && (
              <button
                className="secondary"
                onClick={() => void requestCode(security.phone!)}
              >
                Send code
              </button>
            )}
          </div>
        )}
        {security?.email && (
          <div className="security-contact">
            <span>Email: {security.email}</span>
            <b>{security.emailVerified ? "Verified" : "Not verified"}</b>
            {!security.emailVerified && (
              <button
                className="secondary"
                onClick={() => void requestCode(security.email!)}
              >
                Send code
              </button>
            )}
          </div>
        )}
        {destination && (
          <div className="security-verification">
            <input
              inputMode="numeric"
              maxLength={6}
              value={code}
              onChange={(event) =>
                setCode(event.target.value.replace(/\D/g, ""))
              }
              placeholder="Enter the 6-digit code"
            />{" "}
            <button className="primary" onClick={() => void verifyContact()}>
              Verify
            </button>
          </div>
        )}
        {developmentCode && (
          <small className="security-dev-code">
            Development code: {developmentCode}
          </small>
        )}
      </section>
      <section className="security-card">
        <h2>Change password</h2>
        <form className="security-password" onSubmit={changePassword}>
          <input
            type="password"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            placeholder="Current password"
            autoComplete="current-password"
            required
          />
          <input
            type="password"
            minLength={8}
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            placeholder="New password, at least 8 characters"
            autoComplete="new-password"
            required
          />
          <button className="primary">Update password</button>
        </form>
      </section>
      <section className="security-card">
        <div className="panel-head">
        <h2>Signed-in devices</h2>
        <span>{sessions.length} sessions</span>
        </div>
        {sessions.map((item) => (
          <div className="security-session" key={item.id}>
            <span>
              <b>{item.current ? "Current device" : "Signed-in device"}</b>
              <small>
                {item.ipAddress || "Unknown address"} · Last active{" "}
                {item.lastSeenAt || item.createdAt}
              </small>
            </span>
            {!item.current && (
              <button
                className="secondary"
                onClick={() => void revokeSession(item.id)}
              >
                Sign out device
              </button>
            )}
          </div>
        ))}
      </section>
      <section className="security-card">
        <div className="panel-head">
        <h2>Recent sign-ins</h2>
        </div>
        {events.length ? (
          events.map((item, index) => (
            <div
              className="security-session"
              key={`${item.createdAt}-${index}`}
            >
              <span>
                <b>{item.success ? "Successful sign-in" : "Failed sign-in"}</b>
                <small>
                  {item.ipAddress || "Unknown address"} · {item.createdAt}
                  {item.reason ? ` · ${item.reason}` : ""}
                </small>
              </span>
            </div>
          ))
        ) : (
          <p>No sign-in activity yet.</p>
        )}
      </section>
    </main>
  );
}


export function ProfileSettings({
  account,
  onBack,
  onSecurity,
  onFavorites,
  onOrders,
  onCoupons,
  onFollowing,
  onAccountUpdated,
  onAccountDeleted,
}: {
  account: Account;
  onBack: () => void;
  onSecurity: () => void;
  onFavorites: () => void;
  onOrders: () => void;
  onCoupons: () => void;
  onFollowing: () => void;
  onAccountUpdated: (changes: Partial<Account>) => void;
  onAccountDeleted: () => void;
}) {
  const [name, setName] = useState(account.name);
  const [bio, setBio] = useState("");
  const [phone, setPhone] = useState(account.phone || "");
  const [email, setEmail] = useState(account.email || "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [reason, setReason] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/api/profile`, { credentials: "include" })
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then(
        (payload: {
          profile?: {
            name: string;
            bio: string;
            phone?: string;
            email?: string;
          };
        }) => {
          if (!payload.profile) return;
          setName(payload.profile.name);
          setBio(payload.profile.bio || "");
          setPhone(payload.profile.phone || "");
          setEmail(payload.profile.email || "");
        },
      )
      .catch(() => setNotice("个人资料加载失败"));
  }, []);

  const saveProfile = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setNotice("");
    try {
      const response = await fetch(`${API_BASE}/api/profile`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, bio, phone, email, currentPassword }),
      });
      const payload = (await response.json().catch(() => ({}))) as {
        error?: string;
        profile?: { name: string; phone?: string; email?: string };
      };
      if (!response.ok || !payload.profile) {
        setNotice(payload.error || "个人资料保存失败");
        return;
      }
      setCurrentPassword("");
      onAccountUpdated({
        name: payload.profile.name,
        phone: payload.profile.phone,
        email: payload.profile.email,
      });
      setNotice("个人资料已保存");
    } catch {
      setNotice("个人资料保存失败");
    } finally {
      setSaving(false);
    }
  };

  const deleteAccount = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setCancelling(true);
    setNotice("");
    try {
      const response = await fetch(`${API_BASE}/api/auth/delete-account`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ currentPassword, confirmation, reason }),
      });
      const payload = (await response.json().catch(() => ({}))) as {
        error?: string;
      };
      if (!response.ok) {
        setNotice(payload.error || "账号注销失败");
        return;
      }
      onAccountDeleted();
    } catch {
      setNotice("账号注销失败");
    } finally {
      setCancelling(false);
    }
  };

  return (
    <main className="container page section security-page profile-page">
      <button className="back" onClick={onBack}>
        <ArrowLeft size={18} />
        Back
      </button>
      <div className="page-title">
        <div>
          <h1>Profile</h1>
          <p>Manage your public profile and sign-in contact details.</p>
        </div>
      </div>
      {notice && <p className="auth-error">{notice}</p>}
      {account.role === "buyer" && (
        <section className="profile-services" aria-label="My account services">
          <button type="button" onClick={onSecurity}>
            <Settings2 size={20} />
            <span>
              <b>Account & security</b>
              <small>Manage your password, verification, and signed-in devices.</small>
            </span>
            <ChevronRight size={18} />
          </button>
          <button type="button" onClick={onOrders}>
            <Package size={20} />
            <span>
              <b>My orders</b>
              <small>View orders, tracking, and support progress.</small>
            </span>
            <ChevronRight size={18} />
          </button>
          <button type="button" onClick={onFavorites}>
            <Heart size={20} />
            <span>
              <b>Saved items</b>
              <small>View handmade pieces you have saved.</small>
            </span>
            <ChevronRight size={18} />
          </button>
          <button type="button" onClick={onCoupons}>
            <CreditCard size={20} />
            <span>
              <b>Coupons</b>
              <small>View available offers and claim history.</small>
            </span>
            <ChevronRight size={18} />
          </button>
          <button type="button" onClick={onFollowing}>
            <Store size={20} />
            <span>
              <b>Following</b>
              <small>View and manage makers you follow.</small>
            </span>
            <ChevronRight size={18} />
          </button>
        </section>
      )}
      <section className="security-card">
        <h2>Basic information</h2>
        <form className="profile-form" onSubmit={saveProfile}>
          <label>
            Display name
            <input
              value={name}
              maxLength={30}
              onChange={(event) => setName(event.target.value)}
              required
            />
          </label>
          <label className="profile-form-wide">
            About you
            <textarea
              value={bio}
              maxLength={300}
              onChange={(event) => setBio(event.target.value)}
              placeholder="Tell us about your handmade interests"
            />
          </label>
          <label>
            Phone number
            <input
              inputMode="numeric"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              placeholder="Keep at least one contact method"
            />
          </label>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="Keep at least one contact method"
            />
          </label>
          <label className="profile-form-wide">
            Current password (required only when changing phone or email)
            <input
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
            />
          </label>
          <div className="profile-form-wide">
            <button className="primary" disabled={saving}>
              {saving ? "Saving..." : "Save profile"}
            </button>
          </div>
        </form>
      </section>
      <section className="security-card danger-zone">
        <h2>Close account</h2>
        <p>
          Closing your account signs you out everywhere and removes your profile and addresses. Past orders are retained for transaction records. You cannot close the account while orders or support requests are active.
        </p>
        <form className="profile-form" onSubmit={deleteAccount}>
          <label>
            Current password
            <input
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              required
            />
          </label>
          <label>
            Confirmation text
            <input
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
              placeholder="Type: CLOSE ACCOUNT"
              required
            />
          </label>
          <label className="profile-form-wide">
            Why are you leaving? (optional)
            <textarea
              value={reason}
              maxLength={300}
              onChange={(event) => setReason(event.target.value)}
              placeholder="Help us improve"
            />
          </label>
          <div className="profile-form-wide">
            <button className="danger-button" disabled={cancelling}>
              {cancelling ? "Closing..." : "Close account"}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}
