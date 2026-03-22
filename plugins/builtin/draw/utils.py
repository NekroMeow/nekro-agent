import re

from nekro_agent.core import logger
from nekro_agent.tools.common_util import limited_text_output


def extract_image_from_content(content: str) -> str:
    """从 content 中提取图片 URL 或 base64 数据

    Args:
        content: 响应内容

    Returns:
        str: 图片 URL 或 base64 数据

    Raises:
        Exception: 当无法找到图片内容时
    """
    if not content:
        raise Exception("内容为空，无法提取图片")

    # 清理 content 中的转义字符
    content = content.strip()

    # 尝试 markdown 语法匹配，例如 ![alt](url)
    m = re.search(r"!\[[^\]]*\]\(([^)]+)\)", content)
    if m:
        url = m.group(1).strip()
        logger.info(f"从 markdown 提取到图片: {url[:50]}...")
        return url

    # 尝试 HTML <img> 标签匹配，例如 <img src="url" />
    m = re.search(r'<img\s+src=["\']([^"\']+)["\']', content)
    if m:
        url = m.group(1).strip()
        logger.info(f"从 HTML img 标签提取到图片: {url[:50]}...")
        return url

    # 尝试 base64 数据匹配 (带完整 data URI)
    m = re.search(r"(data:image/[^;]+;base64,[A-Za-z0-9+/=]+)", content)
    if m:
        logger.info(f"从 content 提取到 base64 图片")
        return m.group(1)

    # 尝试纯 base64 数据匹配（需要手动添加前缀）
    m = re.search(r"base64,([A-Za-z0-9+/=]+)", content)
    if m:
        logger.info(f"从 content 提取到纯 base64，添加前缀")
        return f"data:image/png;base64,{m.group(1)}"

    # 尝试裸 URL 匹配，例如 http://... 或 https://...
    m = re.search(r"(https?://[^\s<>\"]+)", content)
    if m:
        url = m.group(1).strip()
        # 排除明显不是图片的 URL
        if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', 'image', 'img', 'photo', 'picture', 'photo']):
            logger.info(f"从 content 提取到图片 URL: {url[:50]}...")
            return url

    logger.error(f"从内容中未找到图片信息: {limited_text_output(str(content))}")
    raise Exception("未找到图片内容，请检查模型响应或调整提示词")
