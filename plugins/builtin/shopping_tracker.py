"""
# 购物防杀熟比价工具 (Shopping Safety Tracker)

帮助用户查询商品历史价格，检测大数据杀熟行为。

## 主要功能

- **历史价格查询**: 支持淘宝、京东、拼多多等主流电商平台的商品历史价格查询
- **杀熟检测**: 自动分析价格走势，判断是否存在"先涨价后降价"等杀熟行为
- **价格提醒**: 提示用户当前价格是否处于低位

## 使用方法

用户发送商品链接后，AI 将自动调用此工具查询历史价格并给出分析结果。

## 数据来源

本插件使用公开的第三方价格数据接口，包括：
- FreeApis.cn (免费接口，每日10000次调用额度)
- 什么值得买官方 API

## 安全声明

⚠️ **本插件绝对不包含任何以下内容**：
- 推广链接或返利链接
- 广告植入
- 用户隐私数据收集
- 账号密码请求

本插件仅提供纯粹的价格查询和比价功能。
"""

import re
import time
from typing import Optional
from dataclasses import dataclass
from enum import Enum

from httpx import AsyncClient
from pydantic import Field

from nekro_agent.api import core, i18n
from nekro_agent.api.plugin import (
    ConfigBase,
    ExtraField,
    NekroPlugin,
    SandboxMethodType,
)
from nekro_agent.api.schemas import AgentCtx

plugin = NekroPlugin(
    name="购物防杀熟比价工具",
    module_name="shopping_tracker",
    description="查询商品历史价格，检测大数据杀熟行为",
    version="0.1.0",
    author="KroMiose",
    url="https://github.com/KroMiose/nekro-agent",
    i18n_name=i18n.i18n_text(
        zh_CN="购物防杀熟比价工具",
        en_US="Shopping Safety Tracker",
    ),
    i18n_description=i18n.i18n_text(
        zh_CN="查询商品历史价格，检测大数据杀熟行为",
        en_US="Query product price history and detect price manipulation",
    ),
    allow_sleep=True,
    sleep_brief="用于查询商品历史价格和检测杀熟行为。当用户发送购物链接或询问商品价格时激活。",
)


@plugin.mount_config()
class ShoppingTrackerConfig(ConfigBase):
    """购物比价工具配置"""

    API_PROVIDER: str = Field(
        default="freeapi",
        title="API 提供商",
        description="选择价格查询 API 提供商",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="API 提供商",
                en_US="API Provider",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="选择价格查询 API 提供商 (freeapi | smzdm)",
                en_US="Choose price query API provider (freeapi | smzdm)",
            ),
        ).model_dump(),
    )
    FREEAPI_API_KEY: str = Field(
        default="",
        title="FreeAPI API Key",
        description="FreeAPI API Key (免费注册: https://freeapi.ai)",
        json_schema_extra=ExtraField(
            is_secret=True,
            i18n_title=i18n.i18n_text(
                zh_CN="FreeAPI API Key",
                en_US="FreeAPI API Key",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="FreeAPI API Key <a href='https://freeapi.ai' target='_blank' rel='noopener noreferrer'>免费注册</a>",
                en_US="FreeAPI API Key <a href='https://freeapi.ai' target='_blank' rel='noopener noreferrer'>Register Free</a>",
            ),
        ).model_dump(),
    )
    SMZDM_API_KEY: str = Field(
        default="",
        title="什么值得买 API Key",
        description="什么值得买官方 API Key",
        json_schema_extra=ExtraField(
            is_secret=True,
            i18n_title=i18n.i18n_text(
                zh_CN="什么值得买 API Key",
                en_US="SMZDM API Key",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="什么值得买官方 API Key",
                en_US="SMZDM Official API Key",
            ),
        ).model_dump(),
    )
    THROTTLE_TIME: int = Field(
        default=5,
        title="查询冷却时间(秒)",
        description="同一商品链接在此时间内重复查询将被阻止",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="查询冷却时间(秒)",
                en_US="Query Cooldown (seconds)",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="同一商品链接在此时间内重复查询将被阻止",
                en_US="Repeated queries for the same product within this time will be blocked",
            ),
        ).model_dump(),
    )
    REQUEST_TIMEOUT: int = Field(
        default=15,
        title="请求超时(秒)",
        description="API 请求超时时间",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="请求超时(秒)",
                en_US="Request Timeout (seconds)",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="API 请求超时时间",
                en_US="API request timeout in seconds",
            ),
        ).model_dump(),
    )


config: ShoppingTrackerConfig = plugin.get_config(ShoppingTrackerConfig)

_last_url: Optional[str] = None
_last_call_time: float = 0


class PriceTrend(Enum):
    UP = "up"
    DOWN = "down"
    STABLE = "stable"
    UNKNOWN = "unknown"


@dataclass
class PriceInfo:
    platform: str
    item_name: str
    current_price: float
    lowest_price: float
    highest_price: float
    lowest_price_date: str
    trend: PriceTrend
    is_lowest: bool
    is_highest: bool
    item_url: str


@dataclass
class PoisoningCheckResult:
    is_poisoned: bool
    reason: str
    suggestion: str


PLATFORM_PATTERNS = {
    "京东": [r"jd\.com", r"jdstore"],
    "淘宝": [r"taobao\.com"],
    "天猫": [r"tmall\.com"],
    "拼多多": [r"pinduoduo\.com"],
}


def detect_platform(url: str) -> str:
    for platform, patterns in PLATFORM_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return platform
    return "未知平台"


async def fetch_price_from_api(url: str, api_key: str, timeout: int) -> Optional[PriceInfo]:
    """从 API 获取价格信息（实际对接时替换为真实接口）"""
    platform = detect_platform(url)

    if config.API_PROVIDER == "freeapi":
        api_url = "https://api.freeapi.ai/api/v1/price/query"
    else:
        api_url = "https://api.zhidemai.com/v1/price/query"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}" if api_key else "",
    }

    payload = {"url": url, "platform": platform}

    try:
        async with AsyncClient(timeout=timeout) as client:
            response = await client.post(api_url, json=payload, headers=headers)
            if response.status_code == 200:
                data = response.json()
                return _parse_response(data, url)
    except Exception as e:
        core.logger.warning(f"价格查询 API 调用失败: {e}")

    return None


def _parse_response(data: dict, original_url: str) -> PriceInfo:
    """解析 API 响应"""
    platform = data.get("platform", detect_platform(original_url))
    current = float(data.get("currentPrice", 0))
    lowest = float(data.get("lowestPrice", current))
    highest = float(data.get("highestPrice", current))
    change = data.get("priceChange", 0)

    trend = PriceTrend.UP if change > 0 else PriceTrend.DOWN if change < 0 else PriceTrend.STABLE

    return PriceInfo(
        platform=platform,
        item_name=data.get("itemName", "未知商品"),
        current_price=current,
        lowest_price=lowest,
        highest_price=highest,
        lowest_price_date=data.get("lowestPriceDate", ""),
        trend=trend,
        is_lowest=current <= lowest * 1.01,
        is_highest=current >= highest * 0.99,
        item_url=original_url,
    )


def check_poisoning(info: PriceInfo) -> PoisoningCheckResult:
    """检测大数据杀熟"""
    result = PoisoningCheckResult(is_poisoned=False, reason="", suggestion="")

    if info.lowest_price > 0:
        ratio = info.current_price / info.lowest_price
    else:
        ratio = 1.0

    if ratio >= 1.3:
        result.is_poisoned = True
        result.reason = f"当前价(¥{info.current_price})比历史最低(¥{info.lowest_price})高 {(ratio - 1) * 100:.0f}%"
        result.suggestion = "建议等待降价或寻找其他渠道"
    elif not info.is_lowest and info.trend == PriceTrend.UP:
        result.is_poisoned = True
        result.reason = "价格正在上涨，可能是促销前先涨后降"
        result.suggestion = "建议观望一段时间后再决定"
    elif info.highest_price > 0 and info.current_price / info.highest_price >= 0.95:
        result.is_poisoned = True
        result.reason = f"当前价格接近历史最高(¥{info.highest_price})"
        result.suggestion = "此时购买不划算，建议等降价"

    return result


@plugin.mount_sandbox_method(
    SandboxMethodType.AGENT,
    name="查询历史价格",
    description="查询商品历史价格，判断是否存在大数据杀熟",
)
async def query_price_history(_ctx: AgentCtx, item_url: str) -> str:
    """查询商品历史价格"""
    global _last_url, _last_call_time

    if not item_url:
        return "[错误] 请提供有效的商品链接"

    if not re.match(r"https?://", item_url):
        return "[错误] 请提供完整的商品链接（以 http:// 或 https:// 开头）"

    platform = detect_platform(item_url)
    if platform == "未知平台":
        return "[错误] 暂不支持此平台，支持：京东、淘宝、天猫、拼多多"

    if item_url == _last_url and time.time() - _last_call_time < config.THROTTLE_TIME:
        return f"[提示] 请勿频繁查询同一商品，{config.THROTTLE_TIME}秒后再试"

    _last_url = item_url
    _last_call_time = time.time()

    api_key = config.FREEAPI_API_KEY if config.API_PROVIDER == "freeapi" else config.SMZDM_API_KEY
    price_info = await fetch_price_from_api(item_url, api_key, config.REQUEST_TIMEOUT)

    if price_info is None:
        return _build_help(platform)

    poisoning = check_poisoning(price_info)
    return _format_reply(price_info, poisoning)


def _format_reply(info: PriceInfo, poisoning: PoisoningCheckResult) -> str:
    """格式化回复"""
    emoji_map = {"京东": "📦", "淘宝": "🛒", "天猫": "🎯", "拼多多": "💰", "未知平台": "❓"}
    trend_map = {PriceTrend.UP: "↑", PriceTrend.DOWN: "↓", PriceTrend.STABLE: "→", PriceTrend.UNKNOWN: "?"}

    status = "🎉 近期最低价！" if info.is_lowest else "⚠️ 接近最高价" if info.is_highest else f"📈 趋势{trend_map[info.trend]}"

    lines = [
        f"{emoji_map.get(info.platform, '🏪')} **{info.item_name}**",
        f"📍 平台: {info.platform}",
        f"💰 当前价: ¥{info.current_price:.2f}",
        f"📊 状态: {status}",
        f"📈 历史最低: ¥{info.lowest_price:.2f}",
        f"📉 历史最高: ¥{info.highest_price:.2f}",
    ]

    if poisoning.is_poisoned:
        lines.extend(["─" * 30, f"⚠️ 杀熟提醒: {poisoning.reason}", f"💡 建议: {poisoning.suggestion}"])

    if info.is_lowest:
        lines.append("✅ 购买建议: 当前是好价格，可以入手！")
    elif poisoning.is_poisoned:
        lines.append("❌ 购买建议: 建议等降价后再入手")
    else:
        lines.append("🤔 购买建议: 价格一般，可观望")

    return "\n".join(lines)


def _build_help(platform: str) -> str:
    """构建帮助信息"""
    return f"""📍 检测到平台: {platform}

⚠️ **尚未配置价格查询 API**

配置步骤：
1. 访问 https://freeapi.ai 注册免费账号
2. 获取 API Key
3. 在 NA 插件配置中填入 API Key

配置后即可查询历史价格和检测杀熟行为。

💡 临时方案: 手动到比价网站查询
   • 慢慢买: https://www.manmanbuy.com
   • 什么值得买: https://www.smzdm.com"""


@plugin.mount_cleanup_method()
async def clean_up():
    global _last_url, _last_call_time
    _last_url = None
    _last_call_time = 0
