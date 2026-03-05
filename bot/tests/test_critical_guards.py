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


if __name__ == "__main__":
    print("=" * 60)
    print("CRITICAL BUSINESS GUARD TESTS")
    print("All tests must pass before deployment")
    print("=" * 60)
    unittest.main(verbosity=2)
