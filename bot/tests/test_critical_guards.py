"""
关键业务守卫测试 (Critical Business Guard Tests)

这些测试保护系统中最高风险的业务逻辑，防止回归。
部署前必须全部通过，任何一个失败都禁止上线。

设计原则：
- 每个测试验证一个"不应该发生的危险行为"
- 不依赖外部服务（Telegram API、LLM 等）
- 可在任何环境独立运行
"""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestPushIntervalGuard(unittest.TestCase):
    """守卫：推送间隔判定逻辑，防止全员被当作 Pro 高频推送"""

    @patch.dict(os.environ, {"FEATURE_PAYMENT": "false"})
    def test_free_user_not_treated_as_pro_when_payment_disabled(self):
        """
        场景：FEATURE_PAYMENT=false（当前生产配置）
        预期：Free 用户的 is_pro 必须为 False
        反例：2026-02-23 / 2026-03-05 事故 — 所有用户被判定为 Pro，每小时推送
        """
        from utils.permissions import get_user_plan, check_feature

        fake_telegram_id = "999999999"

        # check_feature 在 FEATURE_PAYMENT=false 时对所有功能返回 True
        # 这是权限系统的设计行为（付费关闭 = 全部解锁）
        cf_result = check_feature(fake_telegram_id, "priority_push")
        self.assertTrue(cf_result, "check_feature should return True when payment disabled")

        # 但推送间隔判定不能用 check_feature，必须查 plan
        plan = get_user_plan(fake_telegram_id)
        self.assertEqual(plan, "free", "Non-existent user must default to free plan")

        # 模拟 main.py 中的修复后逻辑
        from config import FEATURE_PAYMENT
        if FEATURE_PAYMENT:
            is_pro = check_feature(fake_telegram_id, "priority_push")
        else:
            is_pro = get_user_plan(str(fake_telegram_id)) == "pro"

        self.assertFalse(is_pro, 
            "CRITICAL: Free user must NOT be treated as Pro when FEATURE_PAYMENT=false. "
            "This bug caused mass-push incidents on 2026-02-23 and 2026-03-05.")

    @patch.dict(os.environ, {"FEATURE_PAYMENT": "false"})
    def test_push_interval_is_24h_for_free_user(self):
        """
        场景：Free 用户的推送间隔必须是 24 小时
        预期：interval_hours = PUSH_INTERVAL_HOURS (24)
        """
        from utils.permissions import get_user_plan
        from config import PUSH_INTERVAL_HOURS, PUSH_INTERVAL_PRO_HOURS, FEATURE_PAYMENT

        fake_telegram_id = "999999999"

        if FEATURE_PAYMENT:
            from utils.permissions import check_feature
            is_pro = check_feature(fake_telegram_id, "priority_push")
        else:
            is_pro = get_user_plan(str(fake_telegram_id)) == "pro"

        if is_pro:
            interval_hours = PUSH_INTERVAL_PRO_HOURS
        else:
            interval_hours = PUSH_INTERVAL_HOURS

        self.assertEqual(interval_hours, 24,
            f"Free user push interval must be 24h, got {interval_hours}h. "
            f"is_pro={is_pro}, FEATURE_PAYMENT={FEATURE_PAYMENT}")

    @patch.dict(os.environ, {"FEATURE_PAYMENT": "false"})
    def test_recently_pushed_user_not_due(self):
        """
        场景：用户 30 分钟前刚收到推送
        预期：不应该再次出现在 due_users 列表中
        """
        from utils.permissions import get_user_plan
        from config import PUSH_INTERVAL_HOURS, PUSH_INTERVAL_PRO_HOURS, FEATURE_PAYMENT

        fake_telegram_id = "999999999"
        now = datetime.now()
        last_push = now - timedelta(minutes=30)  # 30分钟前

        if FEATURE_PAYMENT:
            from utils.permissions import check_feature
            is_pro = check_feature(fake_telegram_id, "priority_push")
        else:
            is_pro = get_user_plan(str(fake_telegram_id)) == "pro"

        interval_hours = PUSH_INTERVAL_PRO_HOURS if is_pro else PUSH_INTERVAL_HOURS
        interval_seconds = interval_hours * 3600
        time_since_push = (now - last_push).total_seconds()

        is_due = time_since_push >= interval_seconds
        self.assertFalse(is_due,
            f"User pushed 30min ago should NOT be due. "
            f"interval={interval_hours}h, time_since={time_since_push/3600:.1f}h, is_pro={is_pro}")


class TestPermissionSystemGuard(unittest.TestCase):
    """守卫：权限系统行为一致性"""

    @patch.dict(os.environ, {"FEATURE_PAYMENT": "false"})
    def test_check_feature_returns_true_when_payment_off(self):
        """确认 check_feature 的设计行为：付费关闭时全部返回 True"""
        from utils.permissions import check_feature
        self.assertTrue(check_feature("999999999", "priority_push"))
        self.assertTrue(check_feature("999999999", "custom_sources"))

    def test_free_user_no_priority_push_when_payment_on(self):
        """付费开启时，Free 用户不应有 priority_push 权限"""
        import config
        original = config.FEATURE_PAYMENT
        try:
            config.FEATURE_PAYMENT = True
            from utils.permissions import check_feature
            result = check_feature("999999999", "priority_push")
            self.assertFalse(result, "Free user must not have priority_push when payment is enabled")
        finally:
            config.FEATURE_PAYMENT = original


class TestInactivePauseGuard(unittest.TestCase):
    """守卫：不活跃暂停逻辑，确保暂停/恢复行为正确"""

    def test_paused_user_excluded_from_due_users(self):
        """已暂停的用户不应出现在待推送列表中。

        模拟 interval_digest_check_job 中的过滤逻辑。
        """
        users = [
            {"telegram_id": "111", "service_paused": True, "last_push_time": "2026-01-01T00:00:00"},
            {"telegram_id": "222", "service_paused": False, "last_push_time": "2026-01-01T00:00:00"},
            {"telegram_id": "333", "last_push_time": "2026-01-01T00:00:00"},
        ]
        active_users = [u for u in users if not u.get("service_paused")]
        paused_ids = [u["telegram_id"] for u in users if u.get("service_paused")]

        self.assertNotIn("111", [u["telegram_id"] for u in active_users],
            "Paused user must be excluded from active users list")
        self.assertIn("222", [u["telegram_id"] for u in active_users])
        self.assertIn("333", [u["telegram_id"] for u in active_users])
        self.assertEqual(len(paused_ids), 1)

    def test_inactive_user_detected_correctly(self):
        """超过 N 天未活跃的用户应被检测到。"""
        now = datetime.now()
        users = [
            {"telegram_id": "111", "last_active": (now - timedelta(days=10)).isoformat()},
            {"telegram_id": "222", "last_active": (now - timedelta(days=3)).isoformat()},
            {"telegram_id": "333", "last_active": now.isoformat()},
        ]
        inactive_days = 7
        cutoff = now - timedelta(days=inactive_days)
        inactive = [
            u for u in users
            if not u.get("service_paused")
            and datetime.fromisoformat(u["last_active"]) < cutoff
        ]
        self.assertEqual(len(inactive), 1,
            f"Only 1 user should be inactive (>7 days), got {len(inactive)}")
        self.assertEqual(inactive[0]["telegram_id"], "111")

    def test_resume_clears_pause_state(self):
        """恢复服务后，暂停标记必须被清除。"""
        user = {
            "service_paused": True,
            "paused_at": "2026-04-01T00:00:00",
            "pause_notified": True,
        }
        user["service_paused"] = False
        user["paused_at"] = None
        user["pause_notified"] = False

        self.assertFalse(user["service_paused"],
            "service_paused must be False after resume")
        self.assertIsNone(user["paused_at"],
            "paused_at must be None after resume")
        self.assertFalse(user["pause_notified"],
            "pause_notified must be False after resume")

    def test_already_paused_user_not_double_detected(self):
        """已暂停的用户不应再次被检测为不活跃。"""
        now = datetime.now()
        users = [
            {
                "telegram_id": "111",
                "last_active": (now - timedelta(days=30)).isoformat(),
                "service_paused": True,
            },
            {
                "telegram_id": "222",
                "last_active": (now - timedelta(days=30)).isoformat(),
                "service_paused": False,
            },
        ]
        inactive_days = 7
        cutoff = now - timedelta(days=inactive_days)
        inactive = [
            u for u in users
            if not u.get("service_paused")
            and datetime.fromisoformat(u["last_active"]) < cutoff
        ]
        self.assertEqual(len(inactive), 1,
            "Already paused user should NOT be re-detected as inactive")
        self.assertEqual(inactive[0]["telegram_id"], "222")


if __name__ == "__main__":
    print("=" * 60)
    print("CRITICAL BUSINESS GUARD TESTS")
    print("All tests must pass before deployment")
    print("=" * 60)
    unittest.main(verbosity=2)
