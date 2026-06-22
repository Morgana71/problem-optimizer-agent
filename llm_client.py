"""
llm_client.py

大模型 API 调用封装。
默认采用 OpenAI-compatible Chat Completions 接口，便于接入：
- 通义千问 / 阿里云百炼 compatible-mode
- 豆包 / 火山方舟 OpenAI-compatible 接口
- OpenAI API
- 其他兼容 /chat/completions 的模型服务

重要：不要把 API Key 写死在代码里。请使用 Streamlit Secrets 或环境变量。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import requests


@dataclass
class LLMConfig:
    provider: str
    api_key: str
    base_url: str
    model: str
    temperature: float = 0.3
    max_tokens: int = 5000
    timeout: int = 120
    enable_thinking: bool = True


def normalize_base_url(base_url: str) -> str:
    """确保最终请求地址为 {base_url}/chat/completions。"""
    cleaned = (base_url or "").strip().rstrip("/")
    if cleaned.endswith("/chat/completions"):
        return cleaned
    return f"{cleaned}/chat/completions"


def call_openai_compatible(messages: list[dict[str, str]], config: LLMConfig) -> str:
    """调用 OpenAI-compatible Chat Completions API，返回模型文本。"""
    if not config.api_key or "REPLACE" in config.api_key.upper():
        raise ValueError("API Key 为空或仍是占位符。请在 Streamlit Secrets 或侧边栏中配置真实 API Key。")
    if not config.base_url:
        raise ValueError("Base URL 为空。请配置 OpenAI-compatible API Base URL。")
    if not config.model:
        raise ValueError("模型名为空。请配置模型名称。")

    url = normalize_base_url(config.base_url)
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "enable_thinking": config.enable_thinking,
        "stream": False,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=config.timeout)
    except requests.RequestException as exc:
        raise RuntimeError(f"请求大模型 API 失败：{exc}") from exc

    if response.status_code >= 400:
        # 截断过长错误，避免页面过乱
        text = response.text[:1500]
        raise RuntimeError(f"API 返回错误状态码 {response.status_code}：{text}")

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError(f"API 返回内容不是合法 JSON：{response.text[:1000]}") from exc

    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"无法从 API 响应中解析模型输出：{data}") from exc


PROVIDER_DEFAULTS = {
    "阿里云百炼 / Qwen": {
        "base_url": "https://llm-dks5jdo39k1dk6wb.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-flash",
        "api_key_env": "DASHSCOPE_API_KEY",
    },
    "豆包 / 火山方舟": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "REPLACE_WITH_YOUR_DOUBAO_MODEL_NAME",
        "api_key_env": "ARK_API_KEY",
    },
    "OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
    },
    "自定义 OpenAI-compatible": {
        "base_url": "https://YOUR_BASE_URL/v1",
        "model": "YOUR_MODEL_NAME",
        "api_key_env": "API_KEY",
    },
}
