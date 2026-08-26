// @ts-nocheck
import { useEffect, useState, type FormEvent } from "react";

function money(value: number) {
  return `$${value.toFixed(2)}`;
}

export default function FinanceCenter({
  toast,
  apiBase,
}: {
  toast: (message: string) => void;
  apiBase: string;
}) {
  type Finance = {
    currency: "USD";
    feeRateBps: number;
    payoutSchedule: "daily" | "weekly" | "biweekly" | "monthly";
    nextPayoutAt: string;
    minimumPayout: number;
    holdBusinessDays: number;
    newSellerRiskWindowDays: number;
    wallet: {
      available: number;
      pending: number;
      withdrawing: number;
      withdrawn: number;
      refundDebt: number;
    };
    shops: {
      id: string;
      name: string;
      available: number;
      pending: number;
      withdrawing: number;
      withdrawn: number;
    }[];
    settlements: {
      id: string;
      orderNo: string;
      gross: number;
      fee: number;
      net: number;
      refundedAmount: number;
      currency: "USD";
      exchangeRate: string;
      status: string;
      createdAt: string;
      holdUntil?: string | null;
      availableAt?: string;
    }[];
    ledger: {
      id: string;
      type: string;
      availableDelta: number;
      pendingDelta: number;
      withdrawingDelta: number;
      withdrawnDelta: number;
      note: string;
      createdAt: string;
    }[];
    withdrawals: {
      id: string;
      shopId: string;
      shop: string;
      amount: number;
      recipientType: string;
      recipient: string;
      status: string;
      note?: string;
      createdAt: string;
    }[];
  };
  const [finance, setFinance] = useState<Finance | null>(null);
  const [payoutAccount, setPayoutAccount] = useState<{
    provider: string;
    status: string;
    accountMask?: string | null;
    boundAt?: string | null;
    mode?: string;
  } | null>(null);
  const [amount, setAmount] = useState("");
  const [recipientType, setRecipientType] = useState<"bank" | "wallet">("bank");
  const [recipient, setRecipient] = useState("");
  const [selectedShopId, setSelectedShopId] = useState("");
  const load = async () => {
    const response = await fetch(`${apiBase}/api/seller/finance`, {
      credentials: "include",
    });
    const payload = (await response.json().catch(() => ({}))) as Finance & {
      error?: string;
    };
    if (!response.ok) return toast(payload.error || "资金数据加载失败");
    setFinance(payload);
  };
  useEffect(() => {
    void load();
  }, []);
  const loadPayoutAccount = async () => {
    const response = await fetch(`${apiBase}/api/seller/payout-account`, {
      credentials: "include",
    });
    if (response.ok)
      setPayoutAccount(
        ((await response.json()) as { payoutAccount: typeof payoutAccount })
          .payoutAccount,
      );
  };
  useEffect(() => {
    void loadPayoutAccount();
  }, []);
  useEffect(() => {
    if (!selectedShopId && finance?.shops[0])
      setSelectedShopId(finance.shops[0].id);
  }, [finance, selectedShopId]);
  const updatePayoutSchedule = async (schedule: Finance["payoutSchedule"]) => {
    const response = await fetch(`${apiBase}/api/seller/finance/schedule`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ schedule }),
    });
    const payload = (await response.json().catch(() => ({}))) as {
      error?: string;
      payoutSchedule?: Finance["payoutSchedule"];
      nextPayoutAt?: string;
    };
    if (!response.ok) return toast(payload.error || "结算周期保存失败");
    setFinance((current) =>
      current
        ? {
            ...current,
            payoutSchedule: payload.payoutSchedule || schedule,
            nextPayoutAt: payload.nextPayoutAt || current.nextPayoutAt,
          }
        : current,
    );
    toast("结算周期已保存");
  };
  const bindPayoutAccount = async () => {
    const accountName = window.prompt("请输入连连实名姓名");
    if (!accountName) return;
    const bankCard = window.prompt(
      "本地 mock 模式请输入银行卡号（生产环境将跳转连连安全页面）",
    );
    if (!bankCard) return;
    const response = await fetch(
      `${apiBase}/api/seller/payout-account/onboarding`,
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ accountName, bankCard }),
      },
    );
    const payload = (await response.json().catch(() => ({}))) as {
      error?: string;
      payoutAccount?: typeof payoutAccount;
    };
    if (!response.ok) return toast(payload.error || "连连账户绑定失败");
    if (payload.payoutAccount) setPayoutAccount(payload.payoutAccount);
    toast("连连收款账户已绑定");
  };
  const requestWithdrawal = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const shopId = selectedShopId || finance?.shops[0]?.id;
    if (!shopId) return toast("未找到可提现店铺");
    const response = await fetch(`${apiBase}/api/seller/withdrawals`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        shopId,
        amount: Number(amount),
        recipientType,
        recipient,
      }),
    });
    const payload = (await response.json().catch(() => ({}))) as {
      error?: string;
    };
    if (!response.ok) return toast(payload.error || "提现申请失败");
    setAmount("");
    setRecipient("");
    toast("提现申请已提交，等待平台审核");
    void load();
  };
  const settlementStatus: Record<string, string> = {
    pending: "冻结中",
    available: "可提现",
    reversed: "已冲回",
  };
  const withdrawalStatus: Record<string, string> = {
    pending: "待审核",
    approved: "待打款",
    rejected: "已驳回",
    paid: "已打款",
  };
  return (
    <>
      <div className="studio-title">
        <div>
          <h1>结算与资金</h1>
          <p>订单完成后冻结 {finance?.holdBusinessDays || 3} 个工作日，满足条件后进入可结算余额。</p>
        </div>
      </div>
      <div className="metric-grid finance-metrics">
        <Metric
          label="可提现"
          value={money(finance?.wallet.available || 0)}
          trend="可提交提现申请"
        />
        <Metric
          label="待结算"
          value={money(finance?.wallet.pending || 0)}
          trend="等待订单完成或冻结期结束"
        />
        <Metric
          label="提现中"
          value={money(finance?.wallet.withdrawing || 0)}
          trend="平台审核或打款中"
        />
        <Metric
          label="累计已提现"
          value={money(finance?.wallet.withdrawn || 0)}
          trend="已完成打款"
        />
        <Metric
          label="退款待抵扣"
          value={money(finance?.wallet.refundDebt || 0)}
          trend="将从后续可结算余额中自动抵扣"
        />
      </div>
      <section className="studio-panel payout-binding-panel">
        <div className="panel-head">
          <div>
            <h3>结算周期</h3>
            <small>
              默认每周一结算；可结算余额不足 {money(finance?.minimumPayout || 25)} 将自动累计至下一周期。
            </small>
          </div>
          <small>下一结算日：{finance?.nextPayoutAt || "-"}</small>
        </div>
        <label className="payout-schedule-field">
          <span>打款频率</span>
          <select
            value={finance?.payoutSchedule || "weekly"}
            onChange={(event) =>
              void updatePayoutSchedule(event.target.value as Finance["payoutSchedule"])
            }
          >
            <option value="daily">每日</option>
            <option value="weekly">每周（周一）</option>
            <option value="biweekly">双周（隔周周一）</option>
            <option value="monthly">每月</option>
          </select>
        </label>
        <small className="auth-hint">
          新卖家前 {finance?.newSellerRiskWindowDays || 90} 天可能触发额外风控冻结；具体天数由平台风控规则配置。
        </small>
      </section>
      <section className="studio-panel payout-binding-panel">
        <div className="panel-head">
          <div>
            <h3>连连收款账户</h3>
            <small>卖家收款需先完成连连实名和银行卡绑定。</small>
          </div>
          <span
            className={`seller-payout-status ${payoutAccount?.status || "unbound"}`}
          >
            {payoutAccount?.status === "bound"
              ? `已绑定 ${payoutAccount.accountMask || ""}`
              : "未绑定"}
          </span>
        </div>
        <button className="secondary" onClick={() => void bindPayoutAccount()}>
          {payoutAccount?.status === "bound" ? "重新绑定" : "绑定连连账户"}
        </button>
        {payoutAccount?.mode !== "mock" && (
          <small className="auth-hint">
            当前服务未配置连连商户参数，绑定按钮将在配置完成后启用。
          </small>
        )}
      </section>
      <div className="finance-layout">
        <section className="studio-panel settings-form">
          <div className="panel-head">
            <h3>申请提现</h3>
            <small>当前提现费率 1%</small>
          </div>
          <form onSubmit={requestWithdrawal} className="finance-form">
            {finance && finance.shops.length > 1 && (
              <label>
                结算店铺
                <select
                  value={selectedShopId}
                  onChange={(event) => setSelectedShopId(event.target.value)}
                >
                  {finance.shops.map((shop) => (
                    <option value={shop.id} key={shop.id}>
                      {shop.name} · 可提现 {money(shop.available)}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label>
              提现金额
              <input
                required
                type="number"
                min={finance?.minimumPayout || 25}
                step="0.01"
                max={
                  (finance?.shops.find((shop) => shop.id === selectedShopId)
                    ?.available ??
                    finance?.wallet.available) ||
                  0
                }
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
                placeholder="0.00"
              />
            </label>
            <label>
              收款方式
              <select
                value={recipientType}
                onChange={(event) =>
                  setRecipientType(event.target.value as "bank" | "wallet")
                }
              >
                <option value="bank">银行卡</option>
                <option value="wallet">电子钱包</option>
              </select>
            </label>
            <label>
              收款账户
              <input
                required
                maxLength={500}
                value={recipient}
                onChange={(event) => setRecipient(event.target.value)}
                placeholder={
                  recipientType === "bank" ? "开户名、开户行及账号" : "钱包账号"
                }
              />
            </label>
            <button
              className="primary"
              disabled={!finance?.wallet.available || finance.wallet.available < (finance.minimumPayout || 25)}
            >
              提交提现申请
            </button>
          </form>
        </section>
        <section className="studio-panel">
          <div className="panel-head">
            <h3>提现记录</h3>
            <button className="text-link" onClick={() => void load()}>
              刷新
            </button>
          </div>
          <div className="finance-list">
            {finance?.withdrawals.slice(0, 8).map((item) => (
              <div key={item.id}>
                <span>
                  <b>{money(item.amount)}</b>
                  <small>
                    {item.recipientType === "bank" ? "银行卡" : "电子钱包"} ·{" "}
                    {item.recipient}
                  </small>
                </span>
                <span>
                  <b>{withdrawalStatus[item.status] || item.status}</b>
                  <small>{item.createdAt}</small>
                </span>
              </div>
            )) || <p>暂无提现记录。</p>}
          </div>
        </section>
      </div>
      <section className="studio-panel finance-table">
        <div className="panel-head">
          <h3>订单结算单</h3>
          <small>服务费按订单支付时的费率固定</small>
        </div>
        <div className="finance-list">
          {finance?.settlements.map((item) => (
            <div key={item.id}>
              <span>
                <b>{item.orderNo}</b>
                <small>{item.createdAt}</small>
              </span>
              <span>
                <small>
                  交易额 {money(item.gross)} · 服务费 {money(item.fee)}
                </small>
                <b>
                  净额 {money(item.net)} ·{" "}
                  {settlementStatus[item.status] || item.status}
                </b>
                <small>
                  结算币种：{item.currency} · 锁定汇率：{item.exchangeRate} USD/USD
                </small>
                {item.refundedAmount > 0 && (
                  <small>已退款：{money(item.refundedAmount)}</small>
                )}
                {item.status === "pending" && item.holdUntil && (
                  <small>预计可结算：{item.holdUntil}</small>
                )}
              </span>
            </div>
          )) || <p>暂无已支付订单。</p>}
        </div>
      </section>
      <section className="studio-panel finance-table">
        <div className="panel-head">
          <h3>资金流水</h3>
        </div>
        <div className="finance-list">
          {finance?.ledger.map((item) => (
            <div key={item.id}>
              <span>
                <b>{item.note}</b>
                <small>{item.createdAt}</small>
              </span>
              <b>
                {[
                  item.availableDelta,
                  item.pendingDelta,
                  item.withdrawingDelta,
                  item.withdrawnDelta,
                ]
                  .filter(Boolean)
                  .map((value) => `${value > 0 ? "+" : ""}${money(value)}`)
                  .join(" · ") || "0.00"}
              </b>
            </div>
          )) || <p>暂无资金流水。</p>}
        </div>
      </section>
    </>
  );
}


