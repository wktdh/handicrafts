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
import sqlite_config  # noqa: E402


class ServerDataTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = server.DB_PATH
        self.original_database = server.database
        server.DB_PATH = Path(self.temp_dir.name) / "handicrafts-test.db"
        source = sqlite_config.connect(self.original_db_path, writable=False)
        target = sqlite_config.connect(server.DB_PATH)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()

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
        self.assertIn("046_web_push_subscriptions.sql", migrations)
        self.assertIn("047_product_customization.sql", migrations)
        self.assertTrue({"platform_campaign_redemptions", "platform_campaign_claims", "analytics_events", "search_history", "user_profiles", "account_deletions", "seller_quick_replies", "governance_rules", "enforcement_templates", "governance_tasks", "support_tickets", "support_ticket_messages", "seller_verification_applications", "shop_staff", "database_backup_runs", "governance_rule_versions", "governance_rule_hits", "governance_task_transfers", "governance_task_notes", "governance_case_events", "seller_verification_documents", "shop_staff_audit_logs", "campaign_audiences", "campaign_coupon_codes", "campaign_coupon_issuances", "campaign_coupon_reminders", "platform_activities", "activity_applications", "activity_products", "activity_order_allocations", "order_inventory_allocations", "order_resource_events", "customer_service_conversations", "customer_service_message_links", "customer_service_webhook_events", "search_synonyms", "search_corrections", "search_recommendations", "search_zero_result_rules", "search_query_metrics", "service_automation_rules", "support_ticket_events"}.issubset(tables))
        self.assertIn("push_subscriptions", tables)
        self.assertIsNotNone(default_sku)

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
            connection.execute("UPDATE products SET moderation_status = 'pending' WHERE id = 'product-demo-cup'")
            server.ensure_governance_tasks(connection)
            task = connection.execute("SELECT * FROM governance_tasks WHERE task_type = 'product_moderation' AND target_id = 'product-demo-cup'").fetchone()
            connection.execute("UPDATE governance_tasks SET priority = 'urgent', due_at = datetime('now', '-1 hour') WHERE id = ?", (task["id"],))
            overdue = server.governance_task_rows(connection, {"sla": "overdue"})
            self.assertTrue(any(item["id"] == task["id"] and item["sla"] == "overdue" for item in overdue))
            connection.execute("INSERT INTO governance_task_notes (id, task_id, author_user_id, content) VALUES ('test-deep-task-note', ?, 'user-platform-admin', 'Escalated')", (task["id"],))
            connection.execute("INSERT INTO governance_case_events (id, case_type, case_id, event_type, actor_user_id) VALUES ('test-deep-case-event', 'product', 'product-demo-cup', 'task_sla_updated', 'user-platform-admin')")
            case = server.governance_case_payload(connection, "product", "product-demo-cup")
            self.assertTrue(any(item["type"] == "task_note" for item in case["timeline"]))
            self.assertTrue(any(item["type"] == "event" for item in case["timeline"]))

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

            connection.execute("UPDATE products SET moderation_status = 'pending' WHERE id = 'product-demo-cup'")
            server.ensure_governance_tasks(connection)
            task = connection.execute("SELECT * FROM governance_tasks WHERE task_type = 'product_moderation' AND target_id = 'product-demo-cup'").fetchone()
            self.assertEqual(task['status'], 'in_progress')
            self.assertEqual(task['assigned_user_id'], 'user-platform-admin')

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
            connection.execute("UPDATE products SET moderation_status = 'pending' WHERE id = 'product-demo-cup'")
            connection.execute("INSERT INTO governance_rules (id, name, keyword, action, created_by_user_id) VALUES ('test-governance-rule', 'Keyword review', 'sample', 'manual_review', 'user-platform-admin')")
            connection.execute("INSERT INTO enforcement_templates (id, name, target_type, action_type, reason, created_by_user_id) VALUES ('test-enforcement-template', 'Unlist template', 'product', 'unlist_product', 'Violation', 'user-platform-admin')")
            payload = server.governance_operation_data(connection)
            task = next(item for item in payload["tasks"] if item["type"] == "product_moderation" and item["targetId"] == "product-demo-cup")
            self.assertEqual(task["status"], "in_progress")
            self.assertEqual(task["assigneeId"], "user-platform-admin")
            self.assertTrue(any(item["id"] == "test-governance-rule" for item in payload["rules"]))
            self.assertTrue(any(item["id"] == "test-enforcement-template" for item in payload["templates"]))
            server.complete_governance_task(connection, "product_moderation", "product-demo-cup")
            self.assertEqual(connection.execute("SELECT status FROM governance_tasks WHERE id = ?", (task["id"],)).fetchone()[0], "completed")

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

    def test_seller_finance_settlement_release_and_refund_are_idempotent(self):
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
            settlement = connection.execute("SELECT net_cents, platform_fee_cents, status FROM shop_settlements WHERE order_id = 'test-finance-order'").fetchone()
            self.assertEqual(tuple(settlement), (9500, 500, 'pending'))
            self.assertEqual(connection.execute("SELECT pending_cents FROM shop_wallets WHERE shop_id = 'shop-demo-taoran'").fetchone()[0], 9500)
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


if __name__ == "__main__":
    unittest.main()
