"""
# 好感度系统 (Affection System)

基于用户交互频率、触发词和记忆系统记录/增减好感度，并影响 Agent 的回复态度或状态。

## 主要功能

- **交互追踪**: 记录用户每条消息，自动增加好感度
- **关键词检测**: 检测正/负向关键词，触发额外好感度变化
- **时间衰减**: 无互动时好感度自动衰减
- **Prompt 注入**: 将好感度信息注入 AI 上下文，影响回复态度
- **里程碑系统**: 达到特定好感度阈值时解锁不同互动级别

## 配置说明

- `MAX_AFFECTION`: 好感度上限，默认 100
- `MIN_AFFECTION`: 好感度下限，默认 0
- `DEFAULT_AFFECTION`: 新用户初始好感度，默认 50
- `DECAY_PER_HOUR`: 无互动时每小时衰减，默认 0.5
- `POSITIVE_TRIGGERS`: 正向关键词列表
- `NEGATIVE_TRIGGERS`: 负向关键词列表
- `INTERACTION_BASE_POINTS`: 每条消息基础好感度，默认 1
- `POSITIVE_KEYWORD_BONUS`: 正向关键词奖励，默认 3
- `NEGATIVE_KEYWORD_PENALTY`: 负向关键词惩罚，默认 2
"""

import json
import time
from typing import Any, Dict, List, Optional

from pydantic import Field

from nekro_agent.api import core, i18n
from nekro_agent.api.core import logger
from nekro_agent.api.plugin import (
    ConfigBase,
    ExtraField,
    NekroPlugin,
)
from nekro_agent.api.schemas import AgentCtx
from nekro_agent.api.message import ChatMessage


plugin = NekroPlugin(
    name="好感度系统",
    module_name="affection",
    description="基于用户交互追踪和关键词检测的好感度系统",
    version="0.1.0",
    author="KroMiose",
    url="https://github.com/KroMiose/nekro-agent",
    i18n_name=i18n.i18n_text(
        zh_CN="好感度系统",
        en_US="Affection System",
    ),
    i18n_description=i18n.i18n_text(
        zh_CN="基于用户交互追踪和关键词检测的好感度系统",
        en_US="Affection system based on user interaction tracking and keyword detection",
    ),
    support_adapter=["*"],
    allow_sleep=True,
    sleep_brief="好感度系统被动追踪用户状态，平时不需要主动服务。",
)


class AffectionConfig(ConfigBase):
    """好感度系统配置"""

    MAX_AFFECTION: int = Field(
        default=100,
        title="最大好感度",
        description="好感度上限",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="最大好感度",
                en_US="Max Affection",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="好感度上限",
                en_US="Maximum affection value",
            ),
        ).model_dump(),
    )

    MIN_AFFECTION: int = Field(
        default=0,
        title="最小好感度",
        description="好感度下限",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="最小好感度",
                en_US="Min Affection",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="好感度下限",
                en_US="Minimum affection value",
            ),
        ).model_dump(),
    )

    DEFAULT_AFFECTION: int = Field(
        default=50,
        title="默认好感度",
        description="新用户初始好感度",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="默认好感度",
                en_US="Default Affection",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="新用户初始好感度",
                en_US="Initial affection for new users",
            ),
        ).model_dump(),
    )

    DECAY_PER_HOUR: float = Field(
        default=0.5,
        title="每小时衰减",
        description="无互动时的好感度衰减速度",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="每小时衰减",
                en_US="Decay Per Hour",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="无互动时的好感度衰减速度",
                en_US="Affection decay rate when there's no interaction",
            ),
        ).model_dump(),
    )

    POSITIVE_TRIGGERS: List[str] = Field(
        default=[
            "谢谢",
            "喜欢",
            "太棒了",
            "好用",
            "厉害",
            "可爱",
            "夸夸",
            "支持",
            "真不错",
            "打卡",
            "投喂",
            "摸摸头",
            "好棒",
            "爱你",
            "棒棒",
            "点赞",
            "比心",
        ],
        title="正向触发词",
        description="触发好感度增加的正向关键词",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="正向触发词",
                en_US="Positive Triggers",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="触发好感度增加的正向关键词",
                en_US="Positive keywords that trigger affection increase",
            ),
        ).model_dump(),
    )

    NEGATIVE_TRIGGERS: List[str] = Field(
        default=[
            "无聊",
            "差评",
            "垃圾",
            "滚",
            "烦",
            "讨厌",
            "别来",
            "不要",
            "没用",
            "讨厌",
            "哼",
            "切",
            "懒得理",
        ],
        title="负向触发词",
        description="触发好感度减少的负向关键词",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="负向触发词",
                en_US="Negative Triggers",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="触发好感度减少的负向关键词",
                en_US="Negative keywords that trigger affection decrease",
            ),
        ).model_dump(),
    )

    INTERACTION_BASE_POINTS: int = Field(
        default=1,
        title="每次交互基础好感度",
        description="每条消息带来的基础好感度增加",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="每次交互基础好感度",
                en_US="Base Points Per Interaction",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="每条消息带来的基础好感度增加",
                en_US="Base affection points for each message interaction",
            ),
        ).model_dump(),
    )

    POSITIVE_KEYWORD_BONUS: int = Field(
        default=3,
        title="正向关键词奖励",
        description="检测到正向关键词时的好感度奖励",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="正向关键词奖励",
                en_US="Positive Keyword Bonus",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="检测到正向关键词时的好感度奖励",
                en_US="Affection bonus when positive keyword is detected",
            ),
        ).model_dump(),
    )

    NEGATIVE_KEYWORD_PENALTY: int = Field(
        default=2,
        title="负向关键词惩罚",
        description="检测到负向关键词时的好感度扣除",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="负向关键词惩罚",
                en_US="Negative Keyword Penalty",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="检测到负向关键词时的好感度扣除",
                en_US="Affection penalty when negative keyword is detected",
            ),
        ).model_dump(),
    )


# 获取配置
config: AffectionConfig = plugin.get_config(AffectionConfig)


def _get_user_key(ctx: AgentCtx) -> str:
    """生成用户唯一标识"""
    return f"{ctx.adapter_key}:{ctx.from_platform_userid}"


def _clamp(value: int, min_val: int, max_val: int) -> int:
    """将值限制在指定范围内"""
    return max(min_val, min(max_val, value))


async def get_affection_data(user_key: str) -> Dict[str, Any]:
    """获取用户好感度数据"""
    raw = await plugin.store.get(user_key=user_key, store_key="affection_data")
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

    return {
        "affection_level": config.DEFAULT_AFFECTION,
        "total_interactions": 0,
        "last_interaction": 0.0,
        "positive_keywords": [],
        "negative_keywords": [],
        "milestone_reached": [],
    }


async def save_affection_data(user_key: str, data: Dict[str, Any]) -> None:
    """保存用户好感度数据"""
    await plugin.store.set(user_key=user_key, store_key="affection_data", value=json.dumps(data))


async def get_affection_level(ctx: AgentCtx) -> int:
    """获取当前用户好感度等级（0-100）"""
    user_key = _get_user_key(ctx)
    data = await get_affection_data(user_key)
    return data["affection_level"]


def _check_triggers(text: str, triggers: List[str]) -> List[str]:
    """检测文本中包含的触发词"""
    found = []
    for trigger in triggers:
        if trigger in text:
            found.append(trigger)
    return found


MILESTONES = [
    (1, "初识"),
    (10, "熟人"),
    (50, "挚友"),
    (100, "灵魂伴侣"),
]


def _check_milestones(total_interactions: int, current_level: int, reached: List[str]) -> tuple[int, List[str]]:
    """检查并处理里程碑触发"""
    new_reached = list(reached)
    new_level = current_level

    for threshold, title in MILESTONES:
        if total_interactions >= threshold and title not in reached:
            new_reached.append(title)
            # 里程碑奖励
            new_level = _clamp(new_level + 10, config.MIN_AFFECTION, config.MAX_AFFECTION)

    return new_level, new_reached


@plugin.mount_on_user_message()
async def on_user_message(ctx: AgentCtx, message: ChatMessage):
    """用户消息拦截，追踪好感度变化"""
    user_key = _get_user_key(ctx)
    data = await get_affection_data(user_key)

    # 更新时间戳
    now = time.time()
    last_interaction = data["last_interaction"]

    # 计算时间衰减（如果有）
    if last_interaction > 0 and config.DECAY_PER_HOUR > 0:
        elapsed_hours = (now - last_interaction) / 3600
        if elapsed_hours > 0:
            decay = elapsed_hours * config.DECAY_PER_HOUR
            data["affection_level"] = _clamp(
                data["affection_level"] - int(decay),
                config.MIN_AFFECTION,
                config.MAX_AFFECTION,
            )

    # 基础交互分数
    data["affection_level"] = _clamp(
        data["affection_level"] + config.INTERACTION_BASE_POINTS,
        config.MIN_AFFECTION,
        config.MAX_AFFECTION,
    )
    data["total_interactions"] += 1
    data["last_interaction"] = now

    # 检测正向关键词
    positive_found = _check_triggers(message.content, config.POSITIVE_TRIGGERS)
    if positive_found:
        data["affection_level"] = _clamp(
            data["affection_level"] + config.POSITIVE_KEYWORD_BONUS,
            config.MIN_AFFECTION,
            config.MAX_AFFECTION,
        )
        data["positive_keywords"].extend(positive_found)
        logger.info(f"[Affection] User {user_key} triggered positive keywords: {positive_found}")

    # 检测负向关键词
    negative_found = _check_triggers(message.content, config.NEGATIVE_TRIGGERS)
    if negative_found:
        data["affection_level"] = _clamp(
            data["affection_level"] - config.NEGATIVE_KEYWORD_PENALTY,
            config.MIN_AFFECTION,
            config.MAX_AFFECTION,
        )
        data["negative_keywords"].extend(negative_found)
        logger.info(f"[Affection] User {user_key} triggered negative keywords: {negative_found}")

    # 检查里程碑
    data["affection_level"], data["milestone_reached"] = _check_milestones(
        data["total_interactions"],
        data["affection_level"],
        data["milestone_reached"],
    )

    await save_affection_data(user_key, data)


@plugin.mount_prompt_inject_method("affection_context")
async def get_affection_context(ctx: AgentCtx) -> str:
    """将好感度信息注入到 AI Prompt 中"""
    level = await get_affection_level(ctx)

    if level >= 80:
        return "（当前用户对你好感度很高，态度热情，可以撒娇、主动示好）"
    elif level >= 60:
        return "（当前用户对你好感度良好，态度友善，乐于互动）"
    elif level >= 40:
        return "（当前用户对你好感度一般，保持中性平稳的互动）"
    elif level >= 20:
        return "（当前用户对你好感度较低，态度冷淡，注意保持适当距离）"
    else:
        return "（当前用户对你好感度很低，态度疏远，谨慎互动）"


@plugin.mount_sandbox_method(
    name="获取用户好感度",
    description="获取指定用户的好感度信息",
)
async def get_user_affection(ctx: AgentCtx, user_key: Optional[str] = None) -> Dict[str, Any]:
    """获取用户好感度详情

    Args:
        user_key: 用户标识，格式为 "adapter:user_id"，为空则获取当前用户

    Returns:
        包含好感度数据的字典
    """
    target_key = user_key or _get_user_key(ctx)
    data = await get_affection_data(target_key)

    # 计算状态描述
    level = data["affection_level"]
    if level >= 80:
        status = "热情"
    elif level >= 60:
        status = "友善"
    elif level >= 40:
        status = "一般"
    elif level >= 20:
        status = "冷淡"
    else:
        status = "疏远"

    return {
        "user_key": target_key,
        "affection_level": level,
        "total_interactions": data["total_interactions"],
        "status": status,
        "positive_keywords_count": len(data["positive_keywords"]),
        "negative_keywords_count": len(data["negative_keywords"]),
        "milestones": data["milestone_reached"],
    }




@plugin.mount_sandbox_method(
    name="手动调整好感度",
    description="手动增减用户好感度（管理员功能）",
)
async def adjust_affection(
    ctx: AgentCtx,
    user_key: str,
    delta: int,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """手动调整用户好感度

    Args:
        user_key: 用户标识
        delta: 调整值（正数增加，负数减少）
        reason: 调整原因（可选）

    Returns:
        调整后的好感度信息
    """
    data = await get_affection_data(user_key)

    old_level = data["affection_level"]
    data["affection_level"] = _clamp(
        data["affection_level"] + delta,
        config.MIN_AFFECTION,
        config.MAX_AFFECTION,
    )

    await save_affection_data(user_key, data)

    logger.info(f"[Affection] Manual adjustment for {user_key}: {old_level} -> {data['affection_level']}, reason: {reason}")

    return {
        "user_key": user_key,
        "old_level": old_level,
        "new_level": data["affection_level"],
        "delta": delta,
        "reason": reason,
    }


@plugin.mount_sandbox_method(
    name="重置用户好感度",
    description="重置指定用户的好感度数据",
)
async def reset_affection(ctx: AgentCtx, user_key: str) -> Dict[str, Any]:
    """重置用户好感度

    Args:
        user_key: 用户标识

    Returns:
        重置结果
    """
    await plugin.store.delete(user_key=user_key, store_key="affection_data")

    return {
        "user_key": user_key,
        "success": True,
        "message": "好感度已重置",
    }