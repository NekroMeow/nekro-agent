"""
Shopping Tracker 单元测试

测试内容:
1. 平台检测
2. 杀熟检测逻辑
3. 格式化回复

运行: pytest tests/test_shopping_tracker.py -v
"""

import pytest
from plugins.builtin.shopping_tracker import (
    detect_platform,
    check_poisoning,
    PriceInfo,
    PriceTrend,
    PoisoningCheckResult,
    _format_reply,
)


class TestPlatformDetection:
    def test_jd(self):
        assert detect_platform("https://item.jd.com/100012043.html") == "京东"

    def test_taobao(self):
        assert detect_platform("https://item.taobao.com/item.htm?id=123") == "淘宝"

    def test_tmall(self):
        assert detect_platform("https://detail.tmall.com/item.htm?id=123") == "天猫"

    def test_pinduoduo(self):
        assert detect_platform("https://pinduoduo.com/goods.html?goods_id=123") == "拼多多"

    def test_unknown(self):
        assert detect_platform("https://example.com/product/123") == "未知平台"


class TestPoisoningDetection:
    def test_not_poisoned_lowest(self):
        info = PriceInfo(
            platform="京东", item_name="测试", current_price=99.0,
            lowest_price=99.0, highest_price=299.0, lowest_price_date="2026-03-15",
            trend=PriceTrend.STABLE, is_lowest=True, is_highest=False, item_url="",
        )
        result = check_poisoning(info)
        assert result.is_poisoned is False

    def test_poisoned_high_markup(self):
        info = PriceInfo(
            platform="京东", item_name="测试", current_price=299.0,
            lowest_price=99.0, highest_price=299.0, lowest_price_date="2026-03-15",
            trend=PriceTrend.STABLE, is_lowest=False, is_highest=True, item_url="",
        )
        result = check_poisoning(info)
        assert result.is_poisoned is True
        assert "比历史最低" in result.reason

    def test_poisoned_rising(self):
        info = PriceInfo(
            platform="淘宝", item_name="测试", current_price=150.0,
            lowest_price=99.0, highest_price=199.0, lowest_price_date="2026-03-10",
            trend=PriceTrend.UP, is_lowest=False, is_highest=False, item_url="",
        )
        result = check_poisoning(info)
        assert result.is_poisoned is True
        assert "上涨" in result.reason

    def test_normal_price(self):
        info = PriceInfo(
            platform="拼多多", item_name="测试", current_price=120.0,
            lowest_price=99.0, highest_price=199.0, lowest_price_date="2026-03-15",
            trend=PriceTrend.DOWN, is_lowest=False, is_highest=False, item_url="",
        )
        result = check_poisoning(info)
        assert result.is_poisoned is False


class TestFormatting:
    def test_lowest_price_format(self):
        info = PriceInfo(
            platform="京东", item_name="iPhone 15", current_price=7999.0,
            lowest_price=7999.0, highest_price=9999.0, lowest_price_date="2026-03-15",
            trend=PriceTrend.STABLE, is_lowest=True, is_highest=False, item_url="",
        )
        poisoning = PoisoningCheckResult(is_poisoned=False, reason="", suggestion="")
        reply = _format_reply(info, poisoning)
        assert "iPhone 15" in reply
        assert "¥7999.00" in reply
        assert "✅" in reply

    def test_high_price_format(self):
        info = PriceInfo(
            platform="天猫", item_name="戴森", current_price=3499.0,
            lowest_price=1999.0, highest_price=3499.0, lowest_price_date="2026-02-01",
            trend=PriceTrend.UP, is_lowest=False, is_highest=True, item_url="",
        )
        poisoning = PoisoningCheckResult(
            is_poisoned=True, reason="接近历史最高", suggestion="等降价"
        )
        reply = _format_reply(info, poisoning)
        assert "戴森" in reply
        assert "⚠️" in reply or "杀熟" in reply
        assert "❌" in reply


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
