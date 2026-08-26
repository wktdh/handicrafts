"""Deterministic, explainable seller-business diagnostic rules.

``build_insights`` deliberately has no database or web dependencies.  The API
layer supplies an analytics payload and can therefore reuse the same rules for
the seller dashboard, scheduled reports, and future AI tools.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from statistics import median
from typing import Any


_PRODUCT_LIST_KEYS = ("products", "productPerformance", "productRows", "items")
_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _number(value: Any, default: float = 0) -> float:
    """Parse a possibly malformed JSON metric without allowing exceptions out."""
    try:
        if value is None or isinstance(value, bool):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _first(mapping: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def _metric(row: dict[str, Any], *keys: str) -> float:
    nested = row.get("metrics")
    source = nested if isinstance(nested, dict) else {}
    value = _first(row, *keys, default=_first(source, *keys, default=0))
    return max(0, _number(value))


def _percent(value: Any) -> float:
    """Normalize a decimal (0.03) or percentage (3) to percentage points."""
    result = max(0, _number(value))
    return result * 100 if result <= 1 else result


def _rate(row: dict[str, Any], rate_keys: tuple[str, ...], numerator: float, denominator: float) -> float:
    explicit = _first(row, *rate_keys, default=None)
    if explicit is not None:
        return _percent(explicit)
    return round(numerator / denominator * 100, 4) if denominator else 0


def _published_days(value: Any) -> int | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text).date()
    except (TypeError, ValueError):
        try:
            parsed = date.fromisoformat(str(value)[:10])
        except (TypeError, ValueError):
            return None
    return max(0, (datetime.now(timezone.utc).date() - parsed).days)


def _clean_number(value: float) -> int | float:
    return int(value) if value.is_integer() else round(value, 2)


def _products(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: Any = None
    for key in _PRODUCT_LIST_KEYS:
        if isinstance(payload.get(key), list):
            rows = payload[key]
            break
    if not isinstance(rows, list):
        return []

    normalised: list[dict[str, Any]] = []
    for index, raw in enumerate(rows):
        if not isinstance(raw, dict):
            continue
        product_id = _first(raw, "id", "productId", "catalogId", "product_id", default=None)
        # Stable identities are required for a task item to be dismissible later.
        if product_id is None or not str(product_id).strip():
            continue
        impressions = _metric(raw, "impressions", "impression", "exposures", "exposure")
        clicks = _metric(raw, "clicks", "productClicks")
        favorites = _metric(raw, "favorites", "favoriteAdded", "favoriteAdds", "saves")
        carts = _metric(raw, "addCarts", "addCart", "carts", "cartAdds")
        orders = _metric(raw, "paidOrders", "orders", "orderCount", "sales")
        ctr = _rate(raw, ("ctr", "clickThroughRate", "clickRate"), clicks, impressions)
        cart_rate = _rate(raw, ("cartRate", "addCartRate", "clickToCartRate"), carts, clicks)
        normalised.append(
            {
                "id": str(product_id),
                "title": str(_first(raw, "title", "name", "productTitle", default="未命名作品")),
                "position": index,
                "impressions": impressions,
                "clicks": clicks,
                "favorites": favorites,
                "carts": carts,
                "orders": orders,
                "ctr": ctr,
                "cart_rate": cart_rate,
                "published_days": _published_days(_first(raw, "publishedAt", "published_at", "listedAt", "createdAt", default=None)),
                "stock": _first(raw, "stock", "inventory", "availableStock", default=None),
                "low_stock_threshold": _first(raw, "lowStockThreshold", "low_stock_threshold", "stockWarningThreshold", default=None),
            }
        )
    return normalised


def _insight(
    rule: str,
    product: dict[str, Any],
    priority: str,
    title: str,
    reason: str,
    action_label: str,
    action_target: str,
    recommendation: str,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": f"{rule}:{product['id']}",
        "priority": priority,
        "title": title,
        "reason": reason,
        "recommendation": recommendation,
        "actionLabel": action_label,
        "actionTarget": action_target,
        "metrics": {"productId": product["id"], "productTitle": product["title"], **metrics},
    }


def build_insights(analytics_payload: dict) -> list[dict]:
    """Build actionable diagnostics from a seller analytics payload.

    Accepted input uses ``products`` (or ``productPerformance``) containing
    product-level metrics.  Each rule requires its own minimum sample; rate
    benchmark rules additionally require three comparable products, so small
    stores do not receive statistically misleading alerts.
    """
    if not isinstance(analytics_payload, dict):
        return []
    try:
        products = _products(analytics_payload)
        insights: list[dict[str, Any]] = []

        comparable_ctr = [item["ctr"] for item in products if item["impressions"] >= 20]
        comparable_cart = [item["cart_rate"] for item in products if item["clicks"] >= 10]
        ctr_median = float(median(comparable_ctr)) if len(comparable_ctr) >= 3 else None
        cart_median = float(median(comparable_cart)) if len(comparable_cart) >= 3 else None

        for product in products:
            name = product["title"]
            impressions = product["impressions"]
            clicks = product["clicks"]
            favorites = product["favorites"]
            carts = product["carts"]
            orders = product["orders"]

            if product["published_days"] is not None and product["published_days"] >= 7 and impressions == 0:
                insights.append(_insight(
                    "no-exposure", product, "medium", f"《{name}》上架后仍未获得曝光",
                    f"作品已上架 {product['published_days']} 天，近统计周期曝光为 0。",
                    "完善作品", "products",
                    "补齐首图、标题、类目、搜索标签和至少 3 张作品图片；更新后 48 小时复查曝光变化。",
                    {"publishedDays": product["published_days"], "impressions": 0},
                ))

            if ctr_median is not None and impressions >= 20 and product["ctr"] < ctr_median * 0.7:
                insights.append(_insight(
                    "low-ctr", product, "medium", f"《{name}》点击率偏低",
                    f"曝光 { _clean_number(impressions) } 次，点击率 {product['ctr']:.2f}% ，低于店铺有效作品中位数 {ctr_median:.2f}% 的 70%。",
                    "优化作品", "products",
                    "替换更清晰、有使用场景的首图；标题开头采用“材质 + 作品类型 + 使用场景”，保留核心搜索词，7 天后观察点击率。",
                    {"impressions": _clean_number(impressions), "clicks": _clean_number(clicks), "ctr": round(product["ctr"], 2), "benchmarkCtr": round(ctr_median, 2)},
                ))

            if cart_median is not None and clicks >= 10 and product["cart_rate"] < cart_median * 0.7:
                insights.append(_insight(
                    "low-cart-rate", product, "medium", f"《{name}》加购转化偏低",
                    f"已有 { _clean_number(clicks) } 次点击，加购率 {product['cart_rate']:.2f}% ，低于店铺有效作品中位数 {cart_median:.2f}% 的 70%。",
                    "优化作品", "products",
                    "在详情首屏明确尺寸、材质、制作周期、运费和退换说明，并补充规格与细节图片，降低买家的决策顾虑。",
                    {"clicks": _clean_number(clicks), "addCarts": _clean_number(carts), "cartRate": round(product["cart_rate"], 2), "benchmarkCartRate": round(cart_median, 2)},
                ))

            if carts >= 5 and orders == 0:
                insights.append(_insight(
                    "cart-no-order", product, "high", f"《{name}》有加购但未成交",
                    f"近统计周期有 { _clean_number(carts) } 位买家加购，但尚未产生支付订单。",
                    "创建优惠", "promotions",
                    "创建限时满减或优惠券，并检查运费、预计到货时间和库存状态是否清晰展示，优先促成已加购买家下单。",
                    {"addCarts": _clean_number(carts), "paidOrders": 0},
                ))

            if favorites >= 5 and orders == 0:
                insights.append(_insight(
                    "favorite-no-order", product, "medium", f"《{name}》收藏意向尚未转化",
                    f"近统计周期新增收藏 { _clean_number(favorites) } 次，但尚未产生支付订单。",
                    "创建优惠", "promotions",
                    "设置收藏后可用的专属优惠；同时补充制作周期、库存数量和细节图，推动有意向的买家完成购买。",
                    {"favorites": _clean_number(favorites), "paidOrders": 0},
                ))

            raw_stock = product["stock"]
            raw_threshold = product["low_stock_threshold"]
            if raw_stock is not None and raw_threshold is not None and (carts > 0 or favorites > 0):
                stock = max(0, _number(raw_stock))
                threshold = max(0, _number(raw_threshold))
                if stock <= threshold:
                    priority = "high" if stock == 0 else "medium"
                    insights.append(_insight(
                        "low-stock-interest", product, priority, f"《{name}》有购买意向且库存偏低",
                        f"近统计周期有 { _clean_number(carts) } 次加购、{ _clean_number(favorites) } 次收藏，当前库存 { _clean_number(stock) } 件（预警阈值 { _clean_number(threshold) } 件）。",
                        "管理库存", "inventory",
                        "优先补货；若暂时无法补货，请设置为售罄并暂停促销，避免有购买意向的买家无法下单。",
                        {"addCarts": _clean_number(carts), "favorites": _clean_number(favorites), "stock": _clean_number(stock), "lowStockThreshold": _clean_number(threshold)},
                    ))

        return sorted(insights, key=lambda item: (_PRIORITY_ORDER[item["priority"]], item["id"]))
    except Exception:
        # The dashboard must remain available even when legacy or partial input
        # is encountered.  Malformed individual products are skipped above.
        return []
