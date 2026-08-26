import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


DATABASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DATABASE_DIR))
from business_advisor import build_insights  # noqa: E402


class BusinessAdvisorTestCase(unittest.TestCase):
    def test_builds_all_actionable_rules_with_stable_contract(self):
        old_date = (datetime.now(timezone.utc) - timedelta(days=8)).date().isoformat()
        payload = {
            "products": [
                {"id": "hidden", "title": "无曝光杯", "publishedAt": old_date, "impressions": 0},
                {"id": "weak-ctr", "title": "弱点击", "impressions": 100, "clicks": 2, "addCarts": 0},
                {"id": "normal-a", "title": "正常 A", "impressions": 100, "clicks": 10, "addCarts": 3},
                {"id": "normal-b", "title": "正常 B", "impressions": 100, "clicks": 20, "addCarts": 6},
                {"id": "weak-cart", "title": "弱加购", "impressions": 100, "clicks": 20, "addCarts": 1},
                {"id": "intent", "title": "高意向", "impressions": 20, "clicks": 10, "addCarts": 5, "favorites": 5, "paidOrders": 0, "stock": 2, "lowStockThreshold": 3},
            ]
        }

        insights = build_insights(payload)
        ids = {item["id"] for item in insights}
        self.assertTrue({"no-exposure:hidden", "low-ctr:weak-ctr", "low-cart-rate:weak-cart", "cart-no-order:intent", "favorite-no-order:intent", "low-stock-interest:intent"}.issubset(ids))
        self.assertEqual(insights[0]["id"], "cart-no-order:intent")
        self.assertEqual(set(insights[0]), {"id", "priority", "title", "reason", "recommendation", "actionLabel", "actionTarget", "metrics"})
        self.assertTrue(insights[0]["recommendation"])
        self.assertNotEqual(insights[0]["recommendation"], insights[0]["reason"])
        inventory = next(item for item in insights if item["id"] == "low-stock-interest:intent")
        self.assertEqual(inventory["actionTarget"], "inventory")
        self.assertEqual(inventory["metrics"]["productId"], "intent")

    def test_small_benchmark_does_not_create_rate_diagnostics(self):
        payload = {"productPerformance": [
            {"catalogId": "a", "impressions": 100, "clicks": 1, "addCarts": 0},
            {"catalogId": "b", "impressions": 100, "clicks": 20, "addCarts": 5},
        ]}
        ids = [item["id"] for item in build_insights(payload)]
        self.assertNotIn("low-ctr:a", ids)
        self.assertNotIn("low-cart-rate:b", ids)

    def test_malformed_or_partial_payload_never_raises_or_overdiagnoses(self):
        self.assertEqual(build_insights({}), [])
        self.assertEqual(build_insights({"products": [None, {"id": "missing-metrics"}, {"id": "bad", "impressions": "nope"}]}), [])
        self.assertEqual(build_insights("not-a-dict"), [])

    def test_nested_metrics_and_decimal_rates_are_supported(self):
        payload = {"items": [
            {"id": "low", "metrics": {"impressions": 100, "clicks": 2, "addCarts": 0}, "ctr": 0.02},
            {"id": "one", "metrics": {"impressions": 100, "clicks": 10, "addCarts": 3}, "ctr": 0.1},
            {"id": "two", "metrics": {"impressions": 100, "clicks": 20, "addCarts": 5}, "ctr": 0.2},
        ]}
        insight = next(item for item in build_insights(payload) if item["id"] == "low-ctr:low")
        self.assertEqual(insight["metrics"]["ctr"], 2)


if __name__ == "__main__":
    unittest.main()
