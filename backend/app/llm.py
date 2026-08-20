"""智谱 GLM 大模型调用封装（AI 库存管理员）

通过 HTTP 调用智谱开放平台的 chat/completions 接口，
GLM-4-Flash 模型免费，接口格式与 OpenAI 兼容。
"""
import requests

from .config import ZHIPU_API_KEY

# 智谱开放平台接口地址
API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

# 使用的模型：glm-4-flash 免费
MODEL = "glm-4-flash"

# 请求超时（秒）：大模型生成需要时间，设宽松一些
TIMEOUT = 60

# 单次回答的最大 token 数（约 500 汉字）
MAX_TOKENS = 1024


class LLMError(Exception):
    """大模型调用失败的统一异常"""
    pass


def is_configured() -> bool:
    """判断 API Key 是否已配置"""
    return bool(ZHIPU_API_KEY)


def chat(messages: list[dict]) -> str:
    """调用大模型，返回回答文本

    参数：
        messages: OpenAI 格式的消息列表，例如：
            [
                {"role": "system", "content": "系统设定"},
                {"role": "user", "content": "用户问题"},
                {"role": "assistant", "content": "AI上一轮回答"},
                {"role": "user", "content": "用户本轮问题"},
            ]

    返回：大模型生成的回答文本

    异常：LLMError（Key 未配置 / 网络失败 / 接口报错）
    """
    if not is_configured():
        raise LLMError(
            "AI 功能尚未配置：请在 backend/app/config.py 中填写 ZHIPU_API_KEY"
        )

    headers = {
        "Authorization": f"Bearer {ZHIPU_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.7,      # 0~1，越高越有创造性，库存建议要稳重取 0.7
        "max_tokens": MAX_TOKENS,
    }

    try:
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise LLMError(f"连接大模型失败：{e}")

    if resp.status_code != 200:
        # 常见错误：401 Key 错误、429 触发限流
        detail = ""
        try:
            data = resp.json()
            detail = data.get("error", {}).get("message", "")
        except Exception:
            detail = resp.text[:200]
        raise LLMError(f"大模型接口返回 {resp.status_code}：{detail}")

    try:
        data = resp.json()
        answer = data["choices"][0]["message"]["content"]
        return answer.strip()
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError(f"解析大模型回答失败：{e}")
