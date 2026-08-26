import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path


DATABASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DATABASE_DIR))
import server  # noqa: E402
import backup  # noqa: E402
import init_db  # noqa: E402
import sqlite_config  # noqa: E402


class ServerDataTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = server.DB_PATH
        self.original_database = server.database
        self.original_init_db_path = init_db.DB_PATH
        server.DB_PATH = Path(self.temp_dir.name) / "handicrafts-test.db"
        # Never copy the developer's operational database: it can contain
        # browsing events and date-dependent records that make CI non-repeatable.
        init_db.DB_PATH = server.DB_PATH
        init_db.main(verbose=False)

        @contextmanager
        def isolated_database():
            connection = sqlite_config.connect(server.DB_PATH)
            try:
                yield connection
                connection.commit()
            finally:
                connection.close()

        server.database = isolated_database

    def tearDown(self):
        server.database = self.original_database
        server.DB_PATH = self.original_db_path
        init_db.DB_PATH = self.original_init_db_path
        self.temp_dir.cleanup()

    @contextmanager
    def connection(self):
        connection = sqlite_config.connect(server.DB_PATH)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def test_all_migrations_and_operational_tables_are_present(self):
        with self.connection() as connection:
            migrations = {row[0] for row in connection.execute("SELECT name FROM schema_migrations")}
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            default_sku = connection.execute("SELECT stock FROM product_skus WHERE product_id = 'product-demo-cup' AND id = 'product-demo-cup-default-sku'").fetchone()
            event_columns = {row[1] for row in connection.execute("PRAGMA table_info(analytics_events)")}
            event_indexes = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'analytics_events'")}
        self.assertIn("046_web_push_subscriptions.sql", migrations)
        self.assertIn("047_product_customization.sql", migrations)
        self.assertIn("066_product_buyer_english_copy.sql", migrations)
        self.assertIn("067_marketplace_risk_controls.sql", migrations)
        self.assertIn("069_seller_settlement_schedule.sql", migrations)
        self.assertIn("070_usd_currency_and_rate_locks.sql", migrations)
        self.assertIn("071_preproduction_transaction_foundation.sql", migrations)
        self.assertIn("072_international_shipping_zones.sql", migrations)
        self.assertIn("073_business_advisor_analytics.sql", migrations)
        self.assertIn("075_product_sku_codes.sql", migrations)
        self.assertIn("076_session_csrf_tokens.sql", migrations)
        self.assertIn("077_product_media_asset_workflow.sql", migrations)
        self.assertIn("078_ai_rate_limit_events.sql", migrations)
        self.assertIn("079_seller_message_automation.sql", migrations)
        self.assertTrue({"platform_campaign_redemptions", "platform_campaign_claims", "analytics_events", "search_history", "user_profiles", "account_deletions", "seller_quick_replies", "governance_rules", "enforcement_templates", "governance_tasks", "support_tickets", "support_ticket_messages", "seller_verification_applications", "shop_staff", "database_backup_runs", "governance_rule_versions", "governance_rule_hits", "governance_task_transfers", "governance_task_notes", "governance_case_events", "seller_verification_documents", "shop_staff_audit_logs", "campaign_audiences", "campaign_coupon_codes", "campaign_coupon_issuances", "campaign_coupon_reminders", "platform_activities", "activity_applications", "activity_products", "activity_order_allocations", "order_inventory_allocations", "order_resource_events", "customer_service_conversations", "customer_service_message_links", "customer_service_webhook_events", "search_synonyms", "search_corrections", "search_recommendations", "search_zero_result_rules", "search_query_metrics", "service_automation_rules", "support_ticket_events"}.issubset(tables))
        self.assertIn("push_subscriptions", tables)
        self.assertTrue({"seller_message_settings", "seller_message_attention", "seller_message_notifications"}.issubset(tables))
        self.assertIsNotNone(default_sku)
        self.assertIn("placement", event_columns)
        self.assertTrue({"idx_analytics_events_type_date", "idx_analytics_events_channel_date", "idx_analytics_events_user_date", "idx_analytics_events_actor_funnel", "idx_analytics_events_shop_product_type_date"}.issubset(event_indexes))

    def test_product_media_stays_quarantined_until_promoted(self):
        original_quarantine = server.QUARANTINE_MEDIA_DIR
        original_media = server.MEDIA_DIR
        original_cos_settings = server.public_cos_settings
        server.QUARANTINE_MEDIA_DIR = Path(self.temp_dir.name) / "quarantine"
        server.MEDIA_DIR = Path(self.temp_dir.name) / "public"
        server.public_cos_settings = lambda: None
        try:
            asset = server.create_quarantined_product_media(
                "user-demo-seller",
                "image",
                "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC",
            )
            with self.connection() as connection:
                row = connection.execute(
                    "SELECT status, verified_at, moderation_status, storage_key FROM media_assets WHERE id = ?",
                    (asset["id"],),
                ).fetchone()
                self.assertEqual(row["status"], "temporary")
                self.assertIsNotNone(row["verified_at"])
                self.assertEqual(row["moderation_status"], "approved")
                promoted = server.promote_product_media_assets(
                    connection, "user-demo-seller", [asset["id"]], activate=True
                )[0]
                self.assertEqual(promoted["status"], "active")
                self.assertTrue((server.MEDIA_DIR / Path(promoted["storage_key"]).name).is_file())
                self.assertFalse((server.QUARANTINE_MEDIA_DIR / Path(row["storage_key"]).name).exists())
        finally:
            server.QUARANTINE_MEDIA_DIR = original_quarantine
            server.MEDIA_DIR = original_media
            server.public_cos_settings = original_cos_settings

    def test_seller_ai_rate_limit_is_persisted_and_enforced(self):
        for _ in range(3):
            self.assertTrue(server.seller_ai_assistant_rate_allowed("user-demo-seller", limit=3, window_seconds=600))
        self.assertFalse(server.seller_ai_assistant_rate_allowed("user-demo-seller", limit=3, window_seconds=600))
        with self.connection() as connection:
            event_count = connection.execute(
                "SELECT COUNT(*) FROM ai_rate_limit_events WHERE user_id = ? AND scope = 'seller_ai'",
                ("user-demo-seller",),
            ).fetchone()[0]
        self.assertEqual(event_count, 3)

    def test_product_skus_receive_unique_codes_and_reject_duplicates(self):
        product = {
            "title": "SKU 编号测试作品",
            "category": "陈艺",
            "price": 10,
            "stock": 2,
            "craftsmanship": "纯手工制作",
            "variants": [{"name": "Color", "values": ["Red", "Blue"]}],
            "skus": [
                {"optionValues": {"Color": "Red"}, "price": 10, "stock": 1},
                {"optionValues": {"Color": "Blue"}, "price": 10, "stock": 1},
            ],
        }
        with self.connection() as connection:
            server.upsert_product(connection, "test-sku-codes", "shop-demo-taoran", product, "draft")
            codes = [row[0] for row in connection.execute("SELECT sku_code FROM product_skus WHERE product_id = ? ORDER BY id", ("test-sku-codes",))]
            self.assertEqual(len(codes), 2)
            self.assertTrue(all(code.startswith("SKU-") for code in codes))
            self.assertEqual(len({code.casefold() for code in codes}), 2)
            self.assertTrue(connection.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_product_skus_sku_code_unique'").fetchone())

            duplicate = {**product, "skus": [{"price": 10, "stock": 1, "code": codes[0]}]}
            with self.assertRaisesRegex(ValueError, "已被使用"):
                server.upsert_product(connection, "test-sku-duplicate", "shop-demo-taoran", duplicate, "draft")

    def test_international_shipping_zone_quote_validates_destination_and_snapshots_rule(self):
        template = {
            "name": "Test international shipping",
            "currency": "USD",
            "zones": [
                {"id": "north-america", "name": "North America", "countries": ["US", "CA"], "carrier": "SF International", "firstFee": 12, "additionalFee": 3, "freeShippingThreshold": 1000, "minDeliveryDays": 7, "maxDeliveryDays": 12, "enabled": True},
            ],
        }
        with self.connection() as connection:
            connection.execute("UPDATE shops SET shipping_template_json = ? WHERE id = 'shop-demo-taoran'", (server.json.dumps(template),))
            connection.execute(
                "INSERT INTO buyer_addresses (id, buyer_user_id, recipient_name, recipient_phone, province, city, district, detail, country_code, country_name, is_default) VALUES ('test-shipping-address', 'user-demo-buyer', 'Buyer', '13800000000', 'California', 'Los Angeles', 'Central', 'Test street', 'US', 'United States', 1)"
            )

        item = {"catalogId": "product-demo-cup", "quantity": 2, "variants": {}}
        quote = server.checkout_quote("user-demo-buyer", {"addressId": "test-shipping-address", "items": [item]})
        self.assertEqual(quote["shippingAmount"], 15)
        self.assertEqual(quote["shops"][0]["shippingRule"]["carrier"], "SF International")
        self.assertEqual(quote["shops"][0]["shippingRule"]["maxDeliveryDays"], 12)

        order = server.create_orders("user-demo-buyer", {"addressId": "test-shipping-address", "items": [item]})[0]
        self.assertEqual(order["shippingRule"]["zoneId"], "north-america")
        with self.connection() as connection:
            connection.execute("UPDATE buyer_addresses SET country_code = 'GB', country_name = 'United Kingdom' WHERE id = 'test-shipping-address'")
        with self.assertRaisesRegex(ValueError, "暂不配送"):
            server.checkout_quote("user-demo-buyer", {"addressId": "test-shipping-address", "items": [item]})

    def test_product_weight_is_persisted_and_returned_by_catalog(self):
        with self.connection() as connection:
            server.upsert_product(
                connection,
                "test-weight-product",
                "shop-demo-taoran",
                {"title": "Weight test", "category": "陶艺", "price": 10, "stock": 2, "weightGrams": 350, "dimensions": "10 × 8 × 6 cm"},
                "draft",
            )
        product = next(item for item in server.catalog(statuses=("draft",)) if item["catalogId"] == "test-weight-product")
        self.assertEqual(product["weightGrams"], 350)
        self.assertEqual(product["dimensions"], "10 × 8 × 6 cm")

    def test_buyer_english_listing_copy_is_persisted_and_searchable(self):
        with self.connection() as connection:
            with self.assertRaisesRegex(ValueError, "English listing copy is too long"):
                server.upsert_product(
                    connection,
                    "test-missing-english-listing",
                    "shop-demo-taoran",
                    {"title": "中文陶杯", "category": "陶艺", "price": 24, "stock": 2, "buyerTitle": "x" * 141},
                    "draft",
                )
        with self.connection() as connection:
            server.upsert_product(
                connection,
                "test-english-listing",
                "shop-demo-taoran",
                {
                    "title": "中文陶杯",
                    "category": "陶艺",
                    "price": 24,
                    "stock": 2,
                    "buyerTitle": "Handmade Celadon Tea Cup",
                    "buyerDescription": "A small stoneware cup for everyday tea rituals.",
                    "buyerMaterial": "Stoneware clay and celadon glaze",
                    "buyerSeoTags": ["celadon cup", "tea gift"],
                },
                "draft",
            )
            connection.execute(
                "UPDATE products SET status = 'published', published_at = CURRENT_TIMESTAMP WHERE id = 'test-english-listing'"
            )
        product = next(item for item in server.catalog(statuses=("published",)) if item["catalogId"] == "test-english-listing")
        self.assertEqual(product["title"], "中文陶杯")
        self.assertEqual(product["buyerTitle"], "Handmade Celadon Tea Cup")
        self.assertEqual(product["buyerSeoTags"], ["celadon cup", "tea gift"])
        results = server.search_catalog("celadon", "", "price_asc")
        self.assertTrue(any(item["catalogId"] == "test-english-listing" for item in results))

    def test_marketplace_risk_controls_record_and_deduplicate_cases(self):
        with self.connection() as connection:
            server.record_risk_case(
                connection,
                "coupon_abuse",
                "medium",
                "rapid_coupon_claims",
                subject_user_id="user-demo-buyer",
                detail={"claims10m": 5},
            )
            server.record_risk_case(
                connection,
                "coupon_abuse",
                "high",
                "rapid_coupon_claims",
                subject_user_id="user-demo-buyer",
                detail={"claims10m": 6},
            )
            cases = server.risk_cases_payload(connection)
            coupon_case = next(item for item in cases if item["reasonCode"] == "rapid_coupon_claims")
            self.assertEqual(coupon_case["occurrences"], 2)
            self.assertEqual(coupon_case["severity"], "high")

            connection.execute(
                "INSERT INTO media_assets (id, uploader_user_id, media_type, mime_type, storage_key, public_url, byte_size, content_hash) VALUES (?, ?, 'image', 'image/jpeg', ?, ?, 4, ?)",
                ("risk-image-one", "user-demo-seller", "risk-one.jpg", "/media/risk-one.jpg", "a" * 64),
            )
            connection.execute(
                "INSERT INTO media_assets (id, uploader_user_id, media_type, mime_type, storage_key, public_url, byte_size, content_hash) VALUES (?, ?, 'image', 'image/jpeg', ?, ?, 4, ?)",
                ("risk-image-two", "user-demo-seller", "risk-two.jpg", "/media/risk-two.jpg", "a" * 64),
            )
            server.record_product_image_fingerprints(connection, "product-demo-cup", ["/media/risk-one.jpg"])
            server.upsert_product(
                connection,
                "test-risk-image-product",
                "shop-demo-taoran",
                {"title": "Risk image product", "category": "陶艺", "price": 20, "stock": 1},
                "draft",
            )
            server.record_product_image_fingerprints(connection, "test-risk-image-product", ["/media/risk-two.jpg"])
            duplicate_case = next(item for item in server.risk_cases_payload(connection) if item["category"] == "image_duplicate")
        self.assertEqual(duplicate_case["detail"]["matchedProductId"], "product-demo-cup")

    def test_sqlite_connections_enable_wal_and_busy_timeout(self):
        with self.connection() as connection:
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
            busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
        self.assertEqual(journal_mode.lower(), "wal")
        self.assertGreaterEqual(busy_timeout, sqlite_config.BUSY_TIMEOUT_MS)

    def test_login_cookie_persists_for_the_session_lifetime(self):
        cookie = server.session_cookie("test-token")
        self.assertIn("Max-Age=1209600", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)

    def test_state_changes_require_trusted_origin_and_session_csrf_token(self):
        class FakeHandler:
            browser_origin_is_allowed = server.Handler.browser_origin_is_allowed
            enforce_state_change_protection = server.Handler.enforce_state_change_protection

            def __init__(self, headers: dict[str, str], path: str = "/api/cart") -> None:
                self.headers = headers
                self.path = path
                self.responses: list[tuple[int, dict]] = []

            def send_json(self, status: int, payload: dict, **_kwargs) -> None:
                self.responses.append((status, payload))

        session, csrf = server.create_session("user-demo-buyer")
        protected_headers = {
            "Origin": "http://127.0.0.1:5173",
            "Cookie": f"handicrafts_session={session}",
            "X-CSRF-Token": csrf,
        }
        self.assertTrue(FakeHandler(protected_headers).enforce_state_change_protection())

        missing_csrf = FakeHandler({key: value for key, value in protected_headers.items() if key != "X-CSRF-Token"})
        self.assertFalse(missing_csrf.enforce_state_change_protection())
        self.assertEqual(missing_csrf.responses[0][0], 403)

        foreign_origin = FakeHandler({"Origin": "https://attacker.example"})
        self.assertFalse(foreign_origin.enforce_state_change_protection())
        self.assertEqual(foreign_origin.responses[0][0], 403)

    def test_sensitive_request_rate_limiter_blocks_after_its_window_quota(self):
        limiter = server.SlidingWindowRateLimiter()
        self.assertEqual(limiter.allow("message", "user:one", 2, 60), (True, 0))
        self.assertEqual(limiter.allow("message", "user:one", 2, 60), (True, 0))
        allowed, retry_after = limiter.allow("message", "user:one", 2, 60)
        self.assertFalse(allowed)
        self.assertGreaterEqual(retry_after, 1)
        self.assertLessEqual(retry_after, 60)
        self.assertEqual(limiter.allow("message", "user:two", 2, 60), (True, 0))

    def test_client_ip_uses_proxy_header_only_for_local_reverse_proxy(self):
        class LocalProxyRequest:
            client_address = ("127.0.0.1", 12345)
            headers = {"X-Real-IP": "203.0.113.12"}

        class DirectRequest:
            client_address = ("198.51.100.30", 12345)
            headers = {"X-Real-IP": "203.0.113.12"}

        self.assertEqual(server.client_ip(LocalProxyRequest()), "203.0.113.12")
        self.assertEqual(server.client_ip(DirectRequest()), "198.51.100.30")

    def test_handler_rate_limit_returns_429_and_retry_after(self):
        class FakeHandler:
            enforce_rate_limit = server.Handler.enforce_rate_limit

            def __init__(self) -> None:
                self.client_address = ("198.51.100.30", 12345)
                self.headers = {}
                self.responses: list[tuple[int, dict, dict | None]] = []

            def send_json(self, status: int, payload: dict, cookie=None, extra_headers=None) -> None:
                self.responses.append((status, payload, extra_headers))

        original_limiter = server.REQUEST_RATE_LIMITER
        server.REQUEST_RATE_LIMITER = server.SlidingWindowRateLimiter()
        try:
            handler = FakeHandler()
            self.assertTrue(handler.enforce_rate_limit("message", "user-one", per_ip=2, per_user=2, window_seconds=60))
            self.assertTrue(handler.enforce_rate_limit("message", "user-one", per_ip=2, per_user=2, window_seconds=60))
            self.assertFalse(handler.enforce_rate_limit("message", "user-one", per_ip=2, per_user=2, window_seconds=60))
        finally:
            server.REQUEST_RATE_LIMITER = original_limiter
        self.assertEqual(handler.responses[0][0], 429)
        self.assertIn("retryAfter", handler.responses[0][1])
        self.assertIn("Retry-After", handler.responses[0][2] or {})

    def test_request_body_length_rejects_invalid_and_oversized_put_bodies(self):
        class FakeHandler:
            request_body_length = server.Handler.request_body_length

            def __init__(self, content_length: str) -> None:
                self.headers = {"Content-Length": content_length}
                self.responses: list[tuple[int, dict]] = []

            def send_json(self, status: int, payload: dict, **_kwargs) -> None:
                self.responses.append((status, payload))

        valid = FakeHandler("1024")
        self.assertEqual(valid.request_body_length(), 1024)
        self.assertEqual(valid.responses, [])

        malformed = FakeHandler("invalid")
        self.assertIsNone(malformed.request_body_length())
        self.assertEqual(malformed.responses[0][0], 400)

        oversized = FakeHandler(str(server.MAX_REQUEST_BODY_BYTES + 1))
        self.assertIsNone(oversized.request_body_length())
        self.assertEqual(oversized.responses[0][0], 413)

    def test_live_message_hub_fans_out_websocket_events_to_target_users(self):
        class FakeSocket:
            def __init__(self):
                self.frames: list[bytes] = []

            def sendall(self, frame: bytes) -> None:
                self.frames.append(frame)

        hub = server.LiveMessageHub()
        seller_one_socket, seller_two_socket, unrelated_socket = FakeSocket(), FakeSocket(), FakeSocket()
        hub.add("seller-1", seller_one_socket)
        hub.add("seller-2", seller_two_socket)
        hub.add("other-user", unrelated_socket)
        event = {"type": "message.new", "audience": "seller", "shopId": "shop-1"}
        hub.publish(["seller-1", "seller-2"], event)
        self.assertEqual(seller_one_socket.frames, [server.websocket_text_frame(event)])
        self.assertEqual(seller_two_socket.frames, [server.websocket_text_frame(event)])
        self.assertEqual(unrelated_socket.frames, [])

    def test_search_operations_expand_synonyms_and_corrections(self):
        with self.connection() as connection:
            connection.execute("INSERT INTO search_corrections (id, typo, corrected_term, created_by_user_id) VALUES ('test-search-correction', 'cupp', 'cup', 'user-platform-admin')")
            connection.execute("INSERT INTO search_synonyms (id, source_term, target_terms_json, created_by_user_id) VALUES ('test-search-synonym', 'cup', '[\"mug\"]', 'user-platform-admin')")
            connection.execute("INSERT INTO search_recommendations (id, keyword, recommendation, created_by_user_id) VALUES ('test-search-recommendation', 'cup', '陶艺杯', 'user-platform-admin')")
            operations = server.search_operations(connection, "cupp")
            self.assertEqual(operations["corrected"], "cup")
            self.assertEqual(operations["terms"], ["cup", "mug"])
            self.assertIn("陶艺杯", operations["recommendations"])

    def test_search_intelligence_auto_corrects_and_returns_personalized_suggestions(self):
        with self.connection() as connection:
            connection.execute("INSERT INTO product_seo_tags (product_id, tag, weight, sort_order) VALUES ('product-demo-cup', 'teacup', 1, 99)")
            connection.execute("INSERT INTO search_history (id, user_id, keyword) VALUES ('test-search-history', 'user-demo-buyer', 'tea collection')")
            connection.execute("INSERT INTO search_query_metrics (id, keyword, result_count) VALUES ('test-search-trending', 'tea gift', 2)")
            operations = server.search_operations(connection, "teacuup")
            suggestions = server.search_suggestions(connection, "tea", "user-demo-buyer")
        self.assertEqual(operations["corrected"], "teacup")
        self.assertEqual(operations["correctionSource"], "automatic")
        self.assertIn("teacup", operations["terms"])
        self.assertTrue(any(item["value"] == "tea collection" and item["type"] == "history" for item in suggestions))
        self.assertTrue(any(item["value"] == "tea gift" and item["type"] == "trending" for item in suggestions))

    def test_search_operations_payload_aggregates_rules_and_zero_results(self):
        with self.connection() as connection:
            baseline = connection.execute("SELECT COUNT(*) FROM search_query_metrics WHERE created_at >= datetime('now', '-30 days')").fetchone()[0]
            connection.execute("INSERT INTO search_synonyms (id, source_term, target_terms_json, created_by_user_id) VALUES ('test-search-payload-synonym', 'cup', '[\"mug\"]', 'user-platform-admin')")
            connection.execute("INSERT INTO search_zero_result_rules (id, keyword, message, created_by_user_id) VALUES ('test-search-payload-zero', 'rare', 'Try our new collection', 'user-platform-admin')")
            connection.execute("INSERT INTO search_query_metrics (id, keyword, corrected_keyword, result_count) VALUES ('test-search-metric-1', 'rare', NULL, 0)")
            connection.execute("INSERT INTO search_query_metrics (id, keyword, corrected_keyword, result_count) VALUES ('test-search-metric-2', 'cupp', 'cup', 3)")
            payload = server.search_operations_payload(connection, 30)
        self.assertEqual(payload["summary"]["searches"], baseline + 2)
        self.assertGreaterEqual(payload["summary"]["zeroResults"], 1)
        self.assertGreaterEqual(payload["summary"]["corrections"], 1)
        self.assertTrue(any(item["source"] == "cup" for item in payload["rules"]["synonyms"]))
        self.assertTrue(any(item["keyword"] == "rare" for item in payload["zeroTerms"]))

    def test_versioned_combined_rules_hits_and_task_sla(self):
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO governance_rules (id, name, keyword, action, priority, conditions_json, condition_logic, rollout_percent, release_status, version, created_by_user_id) VALUES (?, ?, '', 'manual_review', 10, ?, 'all', 100, 'active', 2, ?)",
                ("test-deep-rule", "Combined", '[{"field":"title","operator":"contains","value":"demo"},{"field":"category","operator":"equals","value":"陶艺"}]', "user-platform-admin"),
            )
            connection.execute("INSERT INTO governance_rule_versions (id, rule_id, version, snapshot_json, created_by_user_id) VALUES ('test-deep-rule-v2', 'test-deep-rule', 2, '{}', 'user-platform-admin')")
            rule = server.matched_governance_rule(connection, "product-demo-cup", {"category": "陶艺", "description": ""}, "Demo cup", [], "demo cup")
            self.assertEqual(rule["id"], "test-deep-rule")
            server.record_governance_rule_hit(connection, rule, "product-demo-cup", "demo cup")
            self.assertEqual(connection.execute("SELECT rule_version FROM governance_rule_hits WHERE rule_id = 'test-deep-rule'").fetchone()[0], 2)
            server.ensure_governance_tasks(connection)
            task = connection.execute("SELECT * FROM governance_tasks WHERE task_type = 'product_moderation' AND target_id = 'product-demo-cup'").fetchone()
            self.assertIsNone(task)
            self.assertEqual(connection.execute("SELECT moderation_status FROM products WHERE id = 'product-demo-cup'").fetchone()[0], "approved")

    def test_service_ticket_staff_permissions_and_verification_queue(self):
        with self.connection() as connection:
            connection.execute("INSERT INTO shop_staff (id, shop_id, user_id, role, invited_by_user_id) VALUES ('test-staff', 'shop-demo-taoran', 'user-demo-buyer', 'customer_service', 'user-demo-seller')")
            permissions = server.seller_shop_permissions(connection, "user-demo-buyer")
            self.assertIn("messages", permissions["shop-demo-taoran"])
            self.assertNotIn("inventory", permissions["shop-demo-taoran"])
            connection.execute("INSERT INTO support_tickets (id, buyer_user_id, shop_id, subject, priority) VALUES ('test-ticket', 'user-demo-buyer', 'shop-demo-taoran', 'Need help', 'high')")
            ticket = connection.execute("SELECT * FROM support_tickets WHERE id = 'test-ticket'").fetchone()
            self.assertEqual(server.support_ticket_access(connection, ticket, "user-demo-buyer", "buyer"), "buyer")
            self.assertEqual(server.support_ticket_access(connection, ticket, "user-demo-buyer", "seller"), "seller")
            connection.execute("INSERT INTO seller_verification_applications (id, seller_user_id, legal_name, identity_number, contact_phone) VALUES ('test-verification', 'user-demo-seller', 'Demo Seller', '1234567890', '13800138000')")
            self.assertEqual(connection.execute("SELECT status FROM seller_verification_applications WHERE id = 'test-verification'").fetchone()[0], "pending")

    def test_governance_and_support_automation_routes_assigns_and_escalates(self):
        with self.connection() as connection:
            connection.execute("INSERT INTO service_automation_rules (id, name, keywords_json, priority, route, reply_template, created_by_user_id) VALUES ('test-service-rule', 'Fraud escalation', '[\"fraud\"]', 'high', 'platform', 'We received {subject}', 'user-platform-admin')")
            connection.execute("INSERT INTO support_tickets (id, buyer_user_id, shop_id, subject, priority) VALUES ('test-automated-ticket', 'user-demo-buyer', 'shop-demo-taoran', 'Possible fraud', 'normal')")
            server.apply_support_automation(connection, 'test-automated-ticket', 'I suspect fraud in this order')
            ticket = connection.execute("SELECT * FROM support_tickets WHERE id = 'test-automated-ticket'").fetchone()
            self.assertEqual(ticket['priority'], 'high')
            self.assertEqual(ticket['assigned_user_id'], 'user-platform-admin')
            self.assertIsNotNone(ticket['first_response_due_at'])
            self.assertIsNotNone(ticket['resolution_due_at'])
            self.assertEqual(connection.execute("SELECT sender_role FROM support_ticket_messages WHERE ticket_id = 'test-automated-ticket'").fetchone()[0], 'admin')
            connection.execute("UPDATE support_tickets SET first_response_due_at = datetime('now', '-1 hour') WHERE id = 'test-automated-ticket'")
            self.assertEqual(server.run_support_automation(connection), 1)
            self.assertEqual(connection.execute("SELECT priority FROM support_tickets WHERE id = 'test-automated-ticket'").fetchone()[0], 'urgent')
            event_types = {row[0] for row in connection.execute("SELECT event_type FROM support_ticket_events WHERE ticket_id = 'test-automated-ticket'")}
            self.assertTrue({'automation_applied', 'auto_replied', 'sla_escalated'}.issubset(event_types))

            server.ensure_governance_tasks(connection)
            task = connection.execute("SELECT * FROM governance_tasks WHERE task_type = 'product_moderation' AND target_id = 'product-demo-cup'").fetchone()
            self.assertIsNone(task)

    def test_verification_expiry_and_delegated_staff_permissions_are_enforced(self):
        with self.connection() as connection:
            connection.execute("UPDATE seller_profiles SET verification_status = 'approved', verification_expires_at = datetime('now', '-1 day') WHERE user_id = 'user-demo-seller'")
            self.assertFalse(server.seller_is_verified(connection, "user-demo-seller"))
            connection.execute("INSERT INTO shop_staff (id, shop_id, user_id, role, permissions_json, invited_by_user_id) VALUES ('test-delegated-staff', 'shop-demo-taoran', 'user-demo-buyer', 'customer_service', '[\"orders\", \"staff\"]', 'user-demo-seller')")
            permissions = server.seller_shop_permissions(connection, "user-demo-buyer")["shop-demo-taoran"]
            self.assertIn("orders", permissions)
            self.assertNotIn("staff", permissions)
            server.audit_delegated_shop_operation(connection, "user-demo-buyer", "shop-demo-taoran", "buyer_message_sent", {"messageType": "text"})
            audit = connection.execute("SELECT action, staff_user_id FROM shop_staff_audit_logs WHERE action = 'buyer_message_sent'").fetchone()
            self.assertEqual(tuple(audit), ("buyer_message_sent", "user-demo-buyer"))

    def test_governance_case_notes_and_backup_integrity(self):
        with self.connection() as connection:
            connection.execute("INSERT INTO content_reports (id, reporter_user_id, target_type, target_id, reason, detail, evidence_json) VALUES ('test-case-report', 'user-demo-buyer', 'product', 'product-demo-cup', 'test', 'details', '[]')")
            connection.execute("INSERT INTO governance_case_notes (id, case_type, case_id, author_user_id, content) VALUES ('test-case-note', 'report', 'test-case-report', 'user-platform-admin', 'Investigating')")
            payload = server.governance_case_payload(connection, "report", "test-case-report")
            self.assertEqual(payload["case"]["status"], "pending")
            self.assertTrue(any(item["content"] == "Investigating" for item in payload["timeline"]))
        backup_dir = Path(self.temp_dir.name) / "backups"
        metadata = backup.create_backup(backup_dir, server.DB_PATH)
        self.assertEqual(metadata["integrity"], "ok")
        self.assertEqual(backup.verify_backup(backup_dir / metadata["file"])["sha256"], metadata["sha256"])

    def test_restore_rehearsal_preserves_source_and_restores_contents(self):
        with self.connection() as connection:
            connection.execute("INSERT INTO content_reports (id, reporter_user_id, target_type, target_id, reason, detail, evidence_json) VALUES ('test-restore-drill-report', 'user-demo-buyer', 'product', 'product-demo-cup', 'test', 'restore rehearsal', '[]')")
        expected = backup.database_summary(server.DB_PATH)
        result = backup.rehearse_restore(Path(self.temp_dir.name) / "restore-drill", server.DB_PATH)
        restored_path = Path(result["target"])
        self.assertEqual(result["restored"]["integrity"], "ok")
        self.assertTrue(restored_path.is_file())
        self.assertEqual(backup.database_summary(server.DB_PATH), expected)
        self.assertEqual(backup.database_summary(restored_path), expected)

    def test_governance_operations_create_and_complete_review_tasks(self):
        with self.connection() as connection:
            connection.execute("INSERT INTO governance_rules (id, name, keyword, action, created_by_user_id) VALUES ('test-governance-rule', 'Keyword review', 'sample', 'manual_review', 'user-platform-admin')")
            connection.execute("INSERT INTO enforcement_templates (id, name, target_type, action_type, reason, created_by_user_id) VALUES ('test-enforcement-template', 'Unlist template', 'product', 'unlist_product', 'Violation', 'user-platform-admin')")
            payload = server.governance_operation_data(connection)
            self.assertFalse(any(item["type"] == "product_moderation" and item["targetId"] == "product-demo-cup" for item in payload["tasks"]))
            self.assertTrue(any(item["id"] == "test-governance-rule" for item in payload["rules"]))
            self.assertTrue(any(item["id"] == "test-enforcement-template" for item in payload["templates"]))

    def test_message_conversations_include_unread_summary_and_order_card(self):
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO orders (id, order_no, buyer_user_id, shop_id, address_snapshot, item_amount_cents, shipping_amount_cents, discount_amount_cents, paid_amount_cents, status) VALUES ('test-message-order', 'TEST-MESSAGE-ORDER', 'user-demo-buyer', 'shop-demo-taoran', '{}', 2000, 0, 0, 2000, 'completed')"
            )
            connection.execute(
                "INSERT INTO shop_messages (id, shop_id, buyer_user_id, sender_role, content, message_type, order_id) VALUES ('test-message-order-card', 'shop-demo-taoran', 'user-demo-buyer', 'seller', '', 'order', 'test-message-order')"
            )
            connection.execute(
                "INSERT INTO seller_quick_replies (id, seller_user_id, content) VALUES ('test-quick-reply', 'user-demo-seller', '感谢咨询，正在为您核对。')"
            )
            payload = server.buyer_messages_payload(connection, "user-demo-buyer")
            self.assertEqual(payload["conversations"][0]["unread"], 1)
            self.assertIn("订单卡片", payload["conversations"][0]["preview"])
            detail = server.buyer_messages_payload(connection, "user-demo-buyer", "shop-demo-taoran")
            self.assertEqual(detail["messages"][0]["type"], "order")
            self.assertEqual(detail["messages"][0]["order"]["orderNo"], "TEST-MESSAGE-ORDER")
            self.assertTrue(detail["messages"][0]["read"])
            seller = server.seller_messages_payload(connection, "user-demo-seller", "shop-demo-taoran", "user-demo-buyer")
            self.assertEqual(seller["messages"][0]["buyer"], "林知夏")
            self.assertEqual(connection.execute("SELECT content FROM seller_quick_replies WHERE id = 'test-quick-reply'").fetchone()[0], "感谢咨询，正在为您核对。")

    def test_message_updates_return_only_new_rows_and_enforce_conversation_access(self):
        with self.connection() as connection:
            connection.execute("INSERT INTO shop_messages (id, shop_id, buyer_user_id, sender_role, content) VALUES ('test-sync-first', 'shop-demo-taoran', 'user-demo-buyer', 'buyer', 'first')")
            first = server.message_updates_payload(connection, "user-demo-seller", "seller", "shop-demo-taoran", "user-demo-buyer", 0)
            self.assertEqual([message["id"] for message in first["messages"]], ["test-sync-first"])
            self.assertGreater(first["cursor"], 0)
            connection.execute("INSERT INTO shop_messages (id, shop_id, buyer_user_id, sender_role, content) VALUES ('test-sync-second', 'shop-demo-taoran', 'user-demo-buyer', 'buyer', 'second')")
            second = server.message_updates_payload(connection, "user-demo-seller", "seller", "shop-demo-taoran", "user-demo-buyer", first["cursor"])
            self.assertEqual([message["id"] for message in second["messages"]], ["test-sync-second"])
            self.assertEqual(server.message_updates_payload(connection, "user-demo-seller", "seller", "shop-demo-taoran", "user-demo-buyer", second["cursor"])["messages"], [])
            connection.execute("INSERT INTO users (id, display_name, phone, password_hash) VALUES ('test-other-buyer', 'Other buyer', '13900000000', 'hash')")
            with self.assertRaises(ValueError):
                server.message_updates_payload(connection, "test-other-buyer", "buyer", "shop-demo-taoran", None, 0)
            connection.execute("INSERT INTO users (id, display_name, email, password_hash) VALUES ('test-other-seller', 'Other seller', 'other-seller@example.test', 'hash')")
            connection.execute("INSERT INTO user_roles (user_id, role) VALUES ('test-other-seller', 'seller')")
            with self.assertRaises(ValueError):
                server.message_updates_payload(connection, "test-other-seller", "seller", "shop-demo-taoran", "user-demo-buyer", 0)

    def test_seller_message_automation_classifies_urgent_and_skips_reminder_after_reply(self):
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO seller_message_settings (shop_id, weekly_hours_json, off_hours_auto_reply_enabled, urgent_sms_enabled) VALUES ('shop-demo-taoran', ?, 0, 0)",
                ('{"mon":[{"start":"00:00","end":"23:59"}],"tue":[{"start":"00:00","end":"23:59"}],"wed":[{"start":"00:00","end":"23:59"}],"thu":[{"start":"00:00","end":"23:59"}],"fri":[{"start":"00:00","end":"23:59"}],"sat":[{"start":"00:00","end":"23:59"}],"sun":[{"start":"00:00","end":"23:59"}]}',)
            )
            connection.execute(
                "INSERT INTO shop_messages (id, shop_id, buyer_user_id, sender_role, sender_user_id, content) VALUES ('test-urgent-buyer-message', 'shop-demo-taoran', 'user-demo-buyer', 'buyer', 'user-demo-buyer', 'Please cancel order and refund immediately')"
            )
            outcome = server.apply_buyer_message_automation(
                connection, "test-urgent-buyer-message", "shop-demo-taoran", "user-demo-buyer", "Please cancel order and refund immediately"
            )
            attention = connection.execute("SELECT priority, status FROM seller_message_attention WHERE message_id = 'test-urgent-buyer-message'").fetchone()
            queued = connection.execute("SELECT notification_type, channel FROM seller_message_notifications WHERE message_id = 'test-urgent-buyer-message'").fetchall()
            self.assertEqual(outcome["priority"], "urgent")
            self.assertEqual(attention["priority"], "urgent")
            self.assertEqual(attention["status"], "open")
            self.assertIn(("urgent", "email"), {(row[0], row[1]) for row in queued})

            connection.execute("UPDATE shop_messages SET created_at = datetime('now', '-5 minutes') WHERE id = 'test-urgent-buyer-message'")
            connection.execute("INSERT INTO shop_messages (id, shop_id, buyer_user_id, sender_role, sender_user_id, content) VALUES ('test-urgent-seller-reply', 'shop-demo-taoran', 'user-demo-buyer', 'seller', 'user-demo-seller', 'We are checking this now.')")
            connection.execute("UPDATE seller_message_notifications SET due_at = CURRENT_TIMESTAMP WHERE message_id = 'test-urgent-buyer-message' AND notification_type = 'unanswered'")
        server.run_seller_message_automation()
        with self.connection() as connection:
            status = connection.execute("SELECT status FROM seller_message_notifications WHERE message_id = 'test-urgent-buyer-message' AND notification_type = 'unanswered'").fetchone()
            self.assertEqual(status[0], "skipped")

    def test_customer_service_mappings_record_sender_delivery_and_deduplicate_webhooks(self):
        with self.connection() as connection:
            connection.execute("INSERT INTO shop_messages (id, shop_id, buyer_user_id, sender_role, sender_user_id, content) VALUES ('test-customer-service-message', 'shop-demo-taoran', 'user-demo-buyer', 'seller', 'user-demo-seller', 'Hello')")
            connection.execute("INSERT INTO customer_service_conversations (id, provider, external_conversation_id, shop_id, buyer_user_id) VALUES ('test-customer-service-conversation', 'chaskiq', 'external-conversation-1', 'shop-demo-taoran', 'user-demo-buyer')")
            connection.execute("INSERT INTO customer_service_message_links (id, conversation_id, local_message_id, provider, external_message_id, direction, sync_status, attempts) VALUES ('test-customer-service-link', 'test-customer-service-conversation', 'test-customer-service-message', 'chaskiq', 'external-message-1', 'outbound', 'synced', 1)")
            first = server.record_customer_service_webhook_event(connection, "chaskiq", "external-event-1", "message.created", {"provider": "chaskiq", "eventId": "external-event-1"})
            duplicate = server.record_customer_service_webhook_event(connection, "chaskiq", "external-event-1", "message.created", {"provider": "chaskiq", "eventId": "external-event-1"})
            message = server.message_rows(connection, "shop_messages.id = ?", ("test-customer-service-message",))[0]
            self.assertEqual(message["sender_user_id"], "user-demo-seller")
            self.assertTrue(first)
            self.assertFalse(duplicate)
            self.assertEqual(connection.execute("SELECT sync_status FROM customer_service_message_links WHERE id = 'test-customer-service-link'").fetchone()[0], "synced")

    def test_profile_is_persisted_and_disabled_accounts_lose_session_access(self):
        class Handler:
            headers = {"Cookie": "handicrafts_session=test-disabled-session"}

        with self.connection() as connection:
            connection.execute("INSERT INTO user_profiles (user_id, bio) VALUES ('user-demo-buyer', 'Handmade collector')")
            profile = server.profile_for_user(connection, "user-demo-buyer")
            self.assertEqual(profile["name"], "林知夏")
            self.assertEqual(profile["bio"], "Handmade collector")
            connection.execute("INSERT INTO web_sessions (token, id, user_id, expires_at, last_seen_at) VALUES ('test-disabled-session', 'test-disabled-session-id', 'user-demo-buyer', datetime('now', '+1 day'), CURRENT_TIMESTAMP)")

        self.assertEqual(server.session_user(Handler()), "user-demo-buyer")
        with self.connection() as connection:
            connection.execute("UPDATE users SET status = 'disabled' WHERE id = 'user-demo-buyer'")
            self.assertIsNone(server.profile_for_user(connection, "user-demo-buyer"))
        self.assertIsNone(server.session_user(Handler()))

    def test_search_matches_title_and_honors_price_sorting(self):
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO products (id, shop_id, category, title, description, material, price_cents, stock, status, published_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'published', CURRENT_TIMESTAMP)",
                ("test-search-product", "shop-demo-taoran", "织物", "Needle Search Sample", "Searchable handmade textile", "linen", 1234, 3),
            )
        results = server.search_catalog("needle", "", "price_asc")
        self.assertTrue(any(item["catalogId"] == "test-search-product" for item in results))

    def test_search_personalization_uses_persisted_buyer_activity(self):
        with self.connection() as connection:
            server.record_analytics_event(
                connection,
                "add_cart",
                user_id="user-demo-buyer",
                shop_id="shop-demo-taoran",
                product_id="product-demo-cup",
            )
            personalized = server.personal_recommendations(connection, "user-demo-buyer")
        self.assertTrue(any(item["catalogId"] == "product-demo-cup" for item in personalized))
        ranked = server.search_catalog("ceramic coffee", "", "relevance", ["ceramic coffee"], "user-demo-buyer")
        self.assertTrue(any(item["catalogId"] == "product-demo-cup" for item in ranked))

    def test_business_advisor_events_are_idempotent_and_aggregate_paid_products(self):
        events = [
            {"eventId": "business-event-0001", "type": "product_impression", "productId": "product-demo-cup", "visitorKey": "business-visitor-a", "placement": "home_featured"},
            {"eventId": "business-event-0002", "type": "product_impression", "productId": "product-demo-cup", "visitorKey": "business-visitor-b", "placement": "search_results"},
            {"eventId": "business-event-0003", "type": "product_click", "productId": "product-demo-cup", "visitorKey": "business-visitor-a", "placement": "home_featured"},
        ]
        with self.connection() as connection:
            accepted, duplicates = server.record_public_analytics_events(connection, events)
            repeated, repeated_duplicates = server.record_public_analytics_events(connection, [events[0]])
            self.assertEqual((accepted, duplicates), (3, 0))
            self.assertEqual((repeated, repeated_duplicates), (0, 1))
            server.record_analytics_event(
                connection, "favorite_added", user_id="user-demo-buyer", shop_id="shop-demo-taoran",
                product_id="product-demo-cup", placement="product_detail",
            )
            server.record_analytics_event(
                connection, "add_cart", user_id="user-demo-buyer", shop_id="shop-demo-taoran",
                product_id="product-demo-cup", placement="product_detail",
            )
            connection.execute(
                "INSERT INTO orders (id, order_no, buyer_user_id, shop_id, address_snapshot, item_amount_cents, shipping_amount_cents, paid_amount_cents, status, paid_at, placed_at) VALUES ('business-order', 'BUSINESS-ORDER', 'user-demo-buyer', 'shop-demo-taoran', '{}', 16800, 0, 16800, 'completed', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
            connection.execute(
                "INSERT INTO order_items (id, order_id, product_id, title_snapshot, specifications_snapshot, unit_price_cents, quantity, subtotal_cents) VALUES ('business-order-item', 'business-order', 'product-demo-cup', 'Cup', '{}', 16800, 1, 16800)"
            )

        analytics = server.seller_business_analytics("user-demo-seller", 30)
        self.assertEqual(analytics["overview"]["impressions"], 2)
        self.assertEqual(analytics["overview"]["exposureUv"], 2)
        self.assertEqual(analytics["overview"]["clickUv"], 1)
        self.assertEqual(analytics["overview"]["favoriteAdds"], 1)
        self.assertEqual(analytics["overview"]["orders"], 1)
        self.assertEqual(analytics["overview"]["revenue"], 168)
        self.assertEqual(analytics["funnel"]["paidOrders"], 1)
        self.assertEqual(analytics["current"]["overview"]["impressions"], 2)
        self.assertEqual(analytics["current"]["funnel"]["exposureUv"], 2)
        self.assertTrue(any(item["id"] == "product-demo-cup" for item in analytics["current"]["products"]))
        self.assertIn("startDate", analytics["previous"])
        product = next(row for row in analytics["products"] if row["id"] == "product-demo-cup")
        self.assertEqual(product["clickToOrderRate"], 100)
        self.assertEqual(product["favoriteAdds"], 1)

    def test_business_advisor_event_validation_requires_published_product_and_valid_visitor(self):
        with self.connection() as connection:
            with self.assertRaisesRegex(ValueError, "visitor"):
                server.record_public_analytics_events(connection, [{"eventId": "business-invalid-001", "type": "product_click", "productId": "product-demo-cup", "visitorKey": "bad", "placement": "product_detail"}])
            with self.assertRaisesRegex(ValueError, "Product not found"):
                server.record_public_analytics_events(connection, [{"eventId": "business-invalid-002", "type": "product_impression", "productId": "missing-product", "visitorKey": "business-visitor", "placement": "product_detail"}])
            with self.assertRaisesRegex(ValueError, "Favorite events"):
                server.record_public_analytics_events(connection, [{"eventId": "business-invalid-003", "type": "favorite_added", "productId": "product-demo-cup", "visitorKey": "business-visitor", "placement": "product_detail"}])

    def test_claimed_coupon_is_selectable_and_release_restores_wallet(self):
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO platform_campaigns (id, name, campaign_type, rule_json, status, budget_cents, total_usage_limit, per_user_usage_limit, per_user_claim_limit, created_by_user_id) VALUES (?, ?, 'coupon', ?, 'active', 1000, 5, 1, 1, ?)",
                ("test-campaign", "Test coupon", '{"threshold": 10, "discount": 2}', "user-platform-admin"),
            )
            connection.execute(
                "INSERT INTO platform_campaign_claims (id, campaign_id, buyer_user_id, claimed_quantity, used_quantity) VALUES (?, ?, ?, 1, 0)",
                ("test-claim", "test-campaign", "user-demo-buyer"),
            )
            candidate = server.platform_campaign_for_charge(connection, "user-demo-buyer", 2000)
            self.assertEqual(candidate["claimId"], "test-claim")
            connection.execute("INSERT INTO orders (id, order_no, buyer_user_id, shop_id, address_snapshot, item_amount_cents, shipping_amount_cents, discount_amount_cents, paid_amount_cents, status) VALUES ('test-order', 'TEST-ORDER', 'user-demo-buyer', 'shop-demo-taoran', '{}', 2000, 0, 200, 1800, 'pending_payment')")
            connection.execute("INSERT INTO platform_campaign_redemptions (id, campaign_id, order_id, buyer_user_id, item_amount_cents, discount_amount_cents, claim_id) VALUES ('test-redemption', 'test-campaign', 'test-order', 'user-demo-buyer', 2000, 200, 'test-claim')")
            connection.execute("UPDATE platform_campaign_claims SET used_quantity = 1 WHERE id = 'test-claim'")
            server.set_campaign_redemption_status(connection, "test-order", "released")
            remaining = connection.execute("SELECT claimed_quantity - used_quantity FROM platform_campaign_claims WHERE id = 'test-claim'").fetchone()[0]
        self.assertEqual(remaining, 1)

    def test_direct_coupon_issuance_updates_wallet_and_operations_statistics(self):
        with self.connection() as connection:
            connection.execute("INSERT INTO platform_campaigns (id, name, campaign_type, rule_json, status, per_user_claim_limit, per_user_usage_limit, created_by_user_id) VALUES ('test-direct-coupon', 'Direct coupon', 'coupon', '{\"threshold\": 10, \"discount\": 2}', 'active', 2, 2, 'user-platform-admin')")
            issued = server.issue_campaign_coupons(connection, "test-direct-coupon", ["user-demo-buyer", "user-demo-seller"], 2, "direct", "user-platform-admin")
            self.assertEqual(issued, {"users": 1, "quantity": 2, "skipped": 1})
            wallet = connection.execute("SELECT claimed_quantity, used_quantity FROM platform_campaign_claims WHERE campaign_id = 'test-direct-coupon' AND buyer_user_id = 'user-demo-buyer'").fetchone()
            self.assertEqual(tuple(wallet), (2, 0))
            self.assertEqual(connection.execute("SELECT source, issued_quantity FROM campaign_coupon_issuances WHERE campaign_id = 'test-direct-coupon'").fetchone()[0], "direct")
            metrics = next(item for item in server.campaign_performance(connection) if item["id"] == "test-direct-coupon")
            self.assertEqual(metrics["claimUsers"], 1)
            self.assertEqual(metrics["directIssuedQuantity"], 2)
            self.assertEqual(metrics["claimToRedeemRate"], 0)

    def test_expired_pending_order_releases_inventory_coupon_and_payment_once(self):
        with self.connection() as connection:
            product = connection.execute("SELECT id FROM products WHERE id = 'product-demo-cup'").fetchone()
            sku = connection.execute("SELECT id FROM product_skus WHERE product_id = ? LIMIT 1", (product["id"],)).fetchone()
            self.assertIsNotNone(sku)
            connection.execute("UPDATE products SET stock = 0 WHERE id = ?", (product["id"],))
            connection.execute("UPDATE product_skus SET stock = 0 WHERE id = ?", (sku["id"],))
            connection.execute(
                "INSERT INTO platform_campaigns (id, name, campaign_type, rule_json, status, budget_cents, total_usage_limit, per_user_usage_limit, per_user_claim_limit, created_by_user_id) VALUES (?, ?, 'coupon', ?, 'active', 1000, 5, 1, 1, ?)",
                ("test-expiry-campaign", "Expiry coupon", '{\"threshold\": 10, \"discount\": 2}', "user-platform-admin"),
            )
            connection.execute(
                "INSERT INTO platform_campaign_claims (id, campaign_id, buyer_user_id, claimed_quantity, used_quantity) VALUES (?, ?, ?, 1, 1)",
                ("test-expiry-claim", "test-expiry-campaign", "user-demo-buyer"),
            )
            connection.execute(
                "INSERT INTO orders (id, order_no, buyer_user_id, shop_id, address_snapshot, item_amount_cents, shipping_amount_cents, discount_amount_cents, paid_amount_cents, status, expires_at) VALUES (?, ?, ?, ?, '{}', 2000, 0, 200, 1800, 'pending_payment', datetime('now', '-1 minute'))",
                ("test-expiry-order", "TEST-EXPIRY-ORDER", "user-demo-buyer", "shop-demo-taoran"),
            )
            connection.execute(
                "INSERT INTO order_items (id, order_id, product_id, sku_id, title_snapshot, specifications_snapshot, unit_price_cents, quantity, subtotal_cents) VALUES (?, ?, ?, ?, 'Expiry product', '{}', 2000, 1, 2000)",
                ("test-expiry-item", "test-expiry-order", product["id"], sku["id"]),
            )
            connection.execute(
                "INSERT INTO platform_campaign_redemptions (id, campaign_id, order_id, buyer_user_id, item_amount_cents, discount_amount_cents, claim_id) VALUES (?, ?, ?, ?, 2000, 200, ?)",
                ("test-expiry-redemption", "test-expiry-campaign", "test-expiry-order", "user-demo-buyer", "test-expiry-claim"),
            )
            connection.execute(
                "INSERT INTO payment_transactions (id, order_id, payment_method, amount_cents, payment_token) VALUES (?, ?, 'alipay', 1800, 'test-expiry-payment')",
                ("test-expiry-payment", "test-expiry-order"),
            )

            self.assertEqual(server.expire_pending_orders(connection), 1)
            self.assertEqual(server.expire_pending_orders(connection), 0)
            order = connection.execute("SELECT status FROM orders WHERE id = 'test-expiry-order'").fetchone()
            product_stock = connection.execute("SELECT stock FROM products WHERE id = ?", (product["id"],)).fetchone()[0]
            sku_stock = connection.execute("SELECT stock FROM product_skus WHERE id = ?", (sku["id"],)).fetchone()[0]
            used_quantity = connection.execute("SELECT used_quantity FROM platform_campaign_claims WHERE id = 'test-expiry-claim'").fetchone()[0]
            redemption = connection.execute("SELECT status FROM platform_campaign_redemptions WHERE id = 'test-expiry-redemption'").fetchone()
            payment = connection.execute("SELECT status, failure_reason FROM payment_transactions WHERE id = 'test-expiry-payment'").fetchone()

        self.assertEqual(order["status"], "cancelled")
        self.assertEqual(product_stock, 1)
        self.assertEqual(sku_stock, 1)
        self.assertEqual(used_quantity, 0)
        self.assertEqual(redemption["status"], "released")
        self.assertEqual(payment["status"], "cancelled")
        self.assertEqual(payment["failure_reason"], "payment_timeout")

    def test_activity_quota_is_reserved_redeemed_and_released_once(self):
        with self.connection() as connection:
            sku = connection.execute("SELECT id FROM product_skus WHERE product_id = 'product-demo-cup' LIMIT 1").fetchone()
            self.assertIsNotNone(sku)
            connection.execute("UPDATE products SET stock = 5 WHERE id = 'product-demo-cup'")
            connection.execute("UPDATE product_skus SET stock = 5 WHERE id = ?", (sku["id"],))
            connection.execute("INSERT INTO buyer_addresses (id, buyer_user_id, recipient_name, recipient_phone, province, city, district, detail, is_default) VALUES ('test-activity-address', 'user-demo-buyer', 'Buyer', '13800000000', 'Zhejiang', 'Hangzhou', 'Xihu', 'Test street', 1)")
            connection.execute("INSERT INTO platform_activities (id, name, status, created_by_user_id) VALUES ('test-activity', 'Summer activity', 'active', 'user-platform-admin')")
            connection.execute("INSERT INTO activity_applications (id, activity_id, shop_id, applicant_user_id, status) VALUES ('test-activity-application', 'test-activity', 'shop-demo-taoran', 'user-demo-seller', 'approved')")
            connection.execute("INSERT INTO activity_products (id, activity_id, application_id, product_id, quota_stock, status) VALUES ('test-activity-product', 'test-activity', 'test-activity-application', 'product-demo-cup', 2, 'active')")
            connection.execute("INSERT INTO platform_campaigns (id, name, campaign_type, rule_json, status, budget_cents, total_usage_limit, per_user_usage_limit, per_user_claim_limit, created_by_user_id) VALUES ('test-activity-campaign', 'Activity coupon', 'coupon', '{\"threshold\": 10, \"discount\": 2}', 'active', 1000, 5, 1, 1, 'user-platform-admin')")
            connection.execute("INSERT INTO platform_campaign_claims (id, campaign_id, buyer_user_id) VALUES ('test-activity-claim', 'test-activity-campaign', 'user-demo-buyer')")

        orders = server.create_orders("user-demo-buyer", {"addressId": "test-activity-address", "items": [{"catalogId": "product-demo-cup", "quantity": 2, "variants": {}, "activityId": "test-activity"}]})
        self.assertEqual(orders[0]["currency"], "USD")
        self.assertEqual(orders[0]["paymentCurrency"], "USD")
        self.assertEqual(orders[0]["settlementCurrency"], "USD")
        self.assertEqual(orders[0]["paymentExchangeRate"], "1.00000000")
        order_id = orders[0]["orderId"]
        with self.connection() as connection:
            allocation = connection.execute("SELECT status FROM activity_order_allocations WHERE order_id = ?", (order_id,)).fetchone()
            self.assertEqual(allocation["status"], "reserved")
            self.assertEqual(connection.execute("SELECT reserved_stock FROM activity_products WHERE id = 'test-activity-product'").fetchone()[0], 2)
            server.set_activity_allocation_status(connection, order_id, "redeemed")
            server.set_campaign_redemption_status(connection, order_id, "redeemed")
            connection.execute("UPDATE orders SET status = 'pending_fulfillment' WHERE id = ?", (order_id,))
            server.restore_order_inventory(connection, order_id, status="reversed")
            connection.execute("UPDATE orders SET status = 'refunded' WHERE id = ?", (order_id,))
            server.set_activity_allocation_status(connection, order_id, "reversed")
            server.set_campaign_redemption_status(connection, order_id, "reversed")
            server.set_activity_allocation_status(connection, order_id, "reversed")
            allocation = connection.execute("SELECT status FROM activity_order_allocations WHERE order_id = ?", (order_id,)).fetchone()
            self.assertEqual(allocation["status"], "reversed")
            self.assertEqual(connection.execute("SELECT reserved_stock FROM activity_products WHERE id = 'test-activity-product'").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT stock FROM products WHERE id = 'product-demo-cup'").fetchone()[0], 5)
            self.assertEqual(connection.execute("SELECT stock FROM product_skus WHERE id = ?", (sku["id"],)).fetchone()[0], 5)
            events = {(row[0], row[1]) for row in connection.execute("SELECT resource_type, action FROM order_resource_events WHERE order_id = ?", (order_id,))}
            self.assertTrue({("sku_inventory", "reserved"), ("sku_inventory", "reversed"), ("campaign_coupon", "reserved"), ("campaign_coupon", "redeemed"), ("campaign_coupon", "reversed"), ("activity_quota", "reserved"), ("activity_quota", "redeemed"), ("activity_quota", "reversed")}.issubset(events))

    def test_activity_page_queue_and_expiry_disable_products(self):
        with self.connection() as connection:
            connection.execute("INSERT INTO platform_activities (id, name, status, ends_at, created_by_user_id) VALUES ('test-ended-activity', 'Ended activity', 'active', datetime('now', '-1 minute'), 'user-platform-admin')")
            connection.execute("INSERT INTO activity_applications (id, activity_id, shop_id, applicant_user_id, status) VALUES ('test-ended-application', 'test-ended-activity', 'shop-demo-taoran', 'user-demo-seller', 'approved')")
            connection.execute("INSERT INTO activity_products (id, activity_id, application_id, product_id, quota_stock, status) VALUES ('test-ended-product', 'test-ended-activity', 'test-ended-application', 'product-demo-cup', 3, 'active')")
            self.assertEqual(server.expire_ended_activities(connection), 1)
            activity = connection.execute("SELECT * FROM platform_activities WHERE id = 'test-ended-activity'").fetchone()
            payload = server.activity_response(connection, activity, include_review_queue=True)
            self.assertEqual(activity["status"], "ended")
            self.assertEqual(payload["products"][0]["status"], "disabled")
            self.assertEqual(payload["applications"][0]["status"], "approved")

    def test_platform_analytics_exposes_quality_customer_and_product_dimensions(self):
        with self.connection() as connection:
            server.record_analytics_event(connection, "product_view", visitor_key="test-visitor", user_id="user-demo-buyer", shop_id="shop-demo-taoran", product_id="product-demo-cup", channel="test")
            server.record_analytics_event(connection, "add_cart", user_id="user-demo-buyer", shop_id="shop-demo-taoran", product_id="product-demo-cup", channel="test")
            server.record_analytics_event(connection, "checkout_started", user_id="user-demo-buyer", channel="test")
            server.record_analytics_event(connection, "order_paid", user_id="user-demo-buyer", shop_id="shop-demo-taoran", channel="test")
        analytics = server.platform_analytics(30)
        self.assertEqual(set(analytics["quality"]), {"paidOrders", "averageOrderValue", "averageItemValue", "refundOrders", "refundAmount", "refundRate", "afterSaleRate", "fulfillmentHours"})
        self.assertIn("new", analytics["customers"])
        self.assertIn("repeatRevenue", analytics["customers"])
        self.assertIn("paymentDropOff", analytics["funnel"])
        self.assertTrue(any(item["channel"] == "test" and "visitorToCartRate" in item for item in analytics["channels"]))
        self.assertEqual(len(server.analytics_export_sections(analytics)), 5)
        self.assertTrue(any(item["id"] == "product-demo-cup" for item in analytics["productPerformance"]))

    def test_governance_and_support_insights_include_sla_and_rule_effectiveness(self):
        with self.connection() as connection:
            connection.execute("INSERT INTO support_tickets (id, buyer_user_id, shop_id, subject, priority) VALUES ('test-insight-ticket', 'user-demo-buyer', 'shop-demo-taoran', 'Insight ticket', 'high')")
            connection.execute("INSERT INTO support_ticket_messages (id, ticket_id, sender_user_id, sender_role, content) VALUES ('test-insight-ticket-message', 'test-insight-ticket', 'user-demo-seller', 'seller', 'We are reviewing this')")
            insights = server.governance_service_insights(connection)
        self.assertIn("sla", insights["governance"])
        self.assertIn("rules", insights["governance"])
        self.assertGreaterEqual(insights["support"]["total"], 1)
        self.assertGreaterEqual(insights["support"]["averageFirstResponseHours"], 0)

    def test_concurrent_stock_reservations_never_oversell(self):
        with self.connection() as connection:
            sku = connection.execute("SELECT id FROM product_skus WHERE product_id = 'product-demo-cup' LIMIT 1").fetchone()
            self.assertIsNotNone(sku)
            connection.execute("UPDATE product_skus SET stock = 5 WHERE id = ?", (sku["id"],))
        accepted: list[bool] = []
        guard = threading.Lock()
        barrier = threading.Barrier(10)

        def reserve_one():
            barrier.wait()
            for _ in range(20):
                connection = sqlite3.connect(server.DB_PATH, timeout=0.05)
                try:
                    connection.execute("BEGIN IMMEDIATE")
                    changed = connection.execute("UPDATE product_skus SET stock = stock - 1 WHERE id = ? AND stock >= 1", (sku["id"],)).rowcount
                    connection.commit()
                    with guard:
                        accepted.append(changed == 1)
                    return
                except sqlite3.OperationalError:
                    connection.rollback()
                    time.sleep(0.01)
                finally:
                    connection.close()
            self.fail("inventory reservation remained locked")

        workers = [threading.Thread(target=reserve_one) for _ in range(10)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        with self.connection() as connection:
            final_stock = connection.execute("SELECT stock FROM product_skus WHERE id = ?", (sku["id"],)).fetchone()[0]
        self.assertEqual(sum(accepted), 5)
        self.assertEqual(final_stock, 0)

    def test_seller_finance_settlement_holds_before_release_and_refund_is_idempotent(self):
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO orders
                  (id, order_no, buyer_user_id, shop_id, address_snapshot, item_amount_cents,
                   shipping_amount_cents, discount_amount_cents, paid_amount_cents, status, paid_at)
                VALUES ('test-finance-order', 'TEST-FINANCE-ORDER', 'user-demo-buyer',
                        'shop-demo-taoran', '{}', 10000, 0, 0, 10000, 'pending_fulfillment', CURRENT_TIMESTAMP)
                """
            )
            self.assertTrue(server.create_order_settlement(connection, 'test-finance-order'))
            self.assertFalse(server.create_order_settlement(connection, 'test-finance-order'))
            settlement = connection.execute("SELECT net_cents, platform_fee_cents, status, settlement_currency, settlement_exchange_rate FROM shop_settlements WHERE order_id = 'test-finance-order'").fetchone()
            self.assertEqual(tuple(settlement), (9500, 500, 'pending', 'USD', '1.00000000'))
            self.assertEqual(connection.execute("SELECT pending_cents FROM shop_wallets WHERE shop_id = 'shop-demo-taoran'").fetchone()[0], 9500)
            connection.execute("UPDATE orders SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = 'test-finance-order'")
            self.assertTrue(server.schedule_order_settlement_hold(connection, 'test-finance-order'))
            settlement = connection.execute("SELECT hold_until FROM shop_settlements WHERE order_id = 'test-finance-order'").fetchone()
            self.assertGreater(settlement[0], connection.execute("SELECT CURRENT_TIMESTAMP").fetchone()[0])
            self.assertFalse(server.release_order_settlement(connection, 'test-finance-order'))
            connection.execute("UPDATE shop_settlements SET hold_until = '2020-01-01 00:00:00' WHERE order_id = 'test-finance-order'")
            self.assertTrue(server.release_order_settlement(connection, 'test-finance-order'))
            self.assertFalse(server.release_order_settlement(connection, 'test-finance-order'))
            wallet = connection.execute("SELECT available_cents, pending_cents FROM shop_wallets WHERE shop_id = 'shop-demo-taoran'").fetchone()
            self.assertEqual(tuple(wallet), (9500, 0))
            self.assertTrue(server.reverse_order_settlement(connection, 'test-finance-order'))
            self.assertFalse(server.reverse_order_settlement(connection, 'test-finance-order'))
            wallet = connection.execute("SELECT available_cents, pending_cents FROM shop_wallets WHERE shop_id = 'shop-demo-taoran'").fetchone()
            self.assertEqual(tuple(wallet), (0, 0))
            ledger_types = [row[0] for row in connection.execute("SELECT entry_type FROM shop_wallet_ledger WHERE settlement_id = (SELECT id FROM shop_settlements WHERE order_id = 'test-finance-order') ORDER BY created_at")]
            self.assertEqual(set(ledger_types), {'order_pending', 'order_available', 'refund_reversal'})

    def test_settlement_schedule_defaults_and_business_day_calculation(self):
        self.assertEqual(
            server.add_business_days(server.database_datetime('2026-08-14 12:00:00'), 3).strftime('%Y-%m-%d %H:%M:%S'),
            '2026-08-19 12:00:00',
        )
        with self.connection() as connection:
            finance = server.seller_finance_payload(connection, 'user-demo-seller')
            self.assertEqual(finance['payoutSchedule'], 'weekly')
            self.assertEqual(finance['minimumPayout'], 25)
            self.assertEqual(finance['holdBusinessDays'], 3)

    def test_partial_refund_locks_usd_rate_and_reverses_only_the_refund_amount(self):
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO orders
                  (id, order_no, buyer_user_id, shop_id, address_snapshot, item_amount_cents,
                   shipping_amount_cents, discount_amount_cents, paid_amount_cents, status, paid_at)
                VALUES ('test-partial-refund-order', 'TEST-PARTIAL-REFUND', 'user-demo-buyer',
                        'shop-demo-taoran', '{}', 10000, 0, 0, 10000, 'completed', CURRENT_TIMESTAMP)
                """
            )
            self.assertTrue(server.create_order_settlement(connection, 'test-partial-refund-order'))
            connection.execute(
                """
                INSERT INTO after_sale_requests
                  (id, order_id, buyer_user_id, request_type, reason, requested_amount_cents,
                   refund_currency, refund_exchange_rate, status)
                VALUES ('test-partial-refund', 'test-partial-refund-order', 'user-demo-buyer',
                        'refund', 'Partial refund', 2500, 'USD', '1.00000000', 'completed')
                """
            )
            refund = server.record_after_sale_refund(connection, 'test-partial-refund')
            self.assertEqual(refund['platformFeeReversalCents'], 125)
            self.assertEqual(refund['sellerNetReversalCents'], 2375)
            self.assertFalse(refund['fullyRefunded'])
            settlement = connection.execute("SELECT status, refunded_gross_cents, refunded_fee_cents, refunded_net_cents FROM shop_settlements WHERE order_id = 'test-partial-refund-order'").fetchone()
            self.assertEqual(tuple(settlement), ('pending', 2500, 125, 2375))
            wallet = connection.execute("SELECT pending_cents, refund_debt_cents FROM shop_wallets WHERE shop_id = 'shop-demo-taoran'").fetchone()
            self.assertEqual(tuple(wallet), (7125, 0))
            connection.execute("UPDATE shop_settlements SET hold_until = '2020-01-01 00:00:00' WHERE order_id = 'test-partial-refund-order'")
            self.assertTrue(server.release_order_settlement(connection, 'test-partial-refund-order'))
            wallet = connection.execute("SELECT available_cents, pending_cents FROM shop_wallets WHERE shop_id = 'shop-demo-taoran'").fetchone()
            self.assertEqual(tuple(wallet), (7125, 0))
            locked = connection.execute("SELECT currency, exchange_rate FROM order_refunds WHERE after_sale_id = 'test-partial-refund'").fetchone()
            self.assertEqual(tuple(locked), ('USD', '1.00000000'))

    def test_logistics_callback_is_idempotent_and_completes_only_delivered_shipments(self):
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO orders
                  (id, order_no, buyer_user_id, shop_id, address_snapshot, item_amount_cents,
                   shipping_amount_cents, discount_amount_cents, paid_amount_cents, status, paid_at)
                VALUES ('test-logistics-order', 'TEST-LOGISTICS-ORDER', 'user-demo-buyer',
                        'shop-demo-taoran', '{}', 5000, 0, 0, 5000, 'shipped', CURRENT_TIMESTAMP)
                """
            )
            connection.execute("INSERT INTO shipments (id, order_id, carrier, tracking_no, logistics_provider, provider_tracking_id, status) VALUES ('test-logistics-shipment', 'test-logistics-order', 'SF International', 'SF999', 'sf', 'SF999', 'in_transit')")
            event = {"provider": "sf", "eventId": "event-999", "trackingNo": "SF999", "status": "delivered", "label": "Delivered"}
            first = server.record_logistics_webhook_event(connection, event)
            second = server.record_logistics_webhook_event(connection, event)
            self.assertTrue(first['completed'])
            self.assertTrue(second['duplicate'])
            order = connection.execute("SELECT status FROM orders WHERE id = 'test-logistics-order'").fetchone()
            self.assertEqual(order[0], 'completed')

    def test_delivered_order_completion_starts_hold_once(self):
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO orders
                  (id, order_no, buyer_user_id, shop_id, address_snapshot, item_amount_cents,
                   shipping_amount_cents, discount_amount_cents, paid_amount_cents, status, paid_at)
                VALUES ('test-delivered-order', 'TEST-DELIVERED-ORDER', 'user-demo-buyer',
                        'shop-demo-taoran', '{}', 10000, 0, 0, 10000, 'shipped', CURRENT_TIMESTAMP)
                """
            )
            connection.execute(
                "INSERT INTO shipments (id, order_id, carrier, tracking_no, status) VALUES ('test-delivered-shipment', 'test-delivered-order', 'SF International', 'SF123', 'in_transit')"
            )
            self.assertTrue(server.complete_order_and_start_settlement_hold(connection, 'test-delivered-order'))
            self.assertFalse(server.complete_order_and_start_settlement_hold(connection, 'test-delivered-order'))
            order = connection.execute("SELECT status, completed_at FROM orders WHERE id = 'test-delivered-order'").fetchone()
            shipment = connection.execute("SELECT status, delivered_at FROM shipments WHERE order_id = 'test-delivered-order'").fetchone()
            settlement = connection.execute("SELECT status, hold_until FROM shop_settlements WHERE order_id = 'test-delivered-order'").fetchone()
            self.assertEqual(order['status'], 'completed')
            self.assertIsNotNone(order['completed_at'])
            self.assertEqual(shipment['status'], 'delivered')
            self.assertIsNotNone(shipment['delivered_at'])
            self.assertEqual(settlement['status'], 'pending')
            self.assertIsNotNone(settlement['hold_until'])


if __name__ == "__main__":
    unittest.main()
