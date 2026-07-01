"""
Streamlit 主程序：软件需求工程分析智能体

运行方式：
streamlit run app.py
"""

from __future__ import annotations

import html
import os
import re
import time
import traceback
from datetime import datetime

import streamlit as st

from llm_client import LLMConfig, PROVIDER_DEFAULTS, call_openai_compatible
from pdf_generator import markdown_to_pdf_bytes, safe_filename_from_report
try:
    from prompt_templates import build_chat_messages, build_document_messages
except ImportError:
    # 兼容保护：如果线上 prompt_templates.py 还停留在旧版本，
    # 不让应用在启动阶段崩溃；后续仍建议同步更新 prompt_templates.py。
    from prompt_templates import build_chat_messages

    def _format_history_for_document_fallback(
        chat_history: list[dict[str, str]],
        max_history: int = 30,
    ) -> str:
        selected = chat_history[-max_history:]
        lines = []
        for index, message in enumerate(selected, start=1):
            role = message.get("role", "").strip()
            content = str(message.get("content", "")).strip()
            if not content:
                continue
            label = "用户" if role == "user" else "智能体" if role == "assistant" else role or "未知"
            if len(content) > 3500:
                content = content[:3500] + "\n……（该轮内容过长，已截断）"
            lines.append(f"【{index}. {label}】\n{content}")
        return "\n\n".join(lines) if lines else "暂无历史对话。"

    def build_document_messages(
        chat_history: list[dict[str, str]],
        domain: str,
        tool_analysis: str,
        agent_context: str = "暂无",
        previous_document: str = "",
        document_version: int = 1,
        max_history: int = 30,
    ) -> list[dict[str, str]]:
        previous = previous_document.strip() or "暂无上一版完整文档。"
        if len(previous) > 9000:
            previous = previous[:9000] + "\n……（上一版文档过长，已截断；请保留其核心结构并融合最新修改。）"
        history_text = _format_history_for_document_fallback(chat_history, max_history=max_history)
        system_prompt = f"""
你是一个资深软件需求工程文档生成专家，当前固定领域为：{domain}。

你的任务是基于完整历史对话、会话记忆、系统轻量分析结果和上一版文档，生成“当前最新版完整正式软件需求工程分析文档”。

重要要求：
1. 不要只总结最近一条回复。
2. 不要只回复“已完成”“已确认”“请下载”等短句。
3. 必须综合全部历史对话，尤其以用户最新确认和修改意见为准。
4. 如果存在上一版完整文档，请在其基础上融合最新修改，输出完整新版文档。
5. 文档必须完整、正式、可直接转换为 PDF 并用于课程/正式展示场合。
6. PDF 下载由系统页面下方“下载 PDF 文档”按钮提供，正文中严禁生成 Markdown 下载链接、虚假文件链接或“点击此处下载”文案。
7. 输出语言必须为中文，使用 Markdown。

输出必须包含以下结构：
# 软件需求工程分析文档

## 文档信息
项目名称、文档版本、生成时间、文档状态、适用范围。

## 1. 愿景和范围
业务背景、业务机遇、业务目标、成功指标、愿景陈述、范围、限制、业务风险、假设与依赖。

## 2. 干系人与用户分析
干系人、目标用户、用户类别、主要价值、约束和关注点。

## 3. 用例分析
主要操作者、用例列表、核心用例详情、正常流程、异常流程、后置条件和业务规则。

## 4. 软件需求规范
功能需求、非功能需求、数据需求、外部接口需求、操作环境、设计与实现约束。

## 5. 分析模型
业务流程、领域对象、数据模型、状态流转、权限模型。

## 6. 业务规则
使用 BR-编号 描述关键业务规则。

## 7. 界面原型说明
主要页面、字段、操作入口、交互流程和页面跳转关系。

## 8. 验收标准
功能验收、性能验收、安全验收、文档验收和演示验收。

## 9. 风险与改进方向
技术风险、业务风险、实施风险和后续改进方向。

## 10. 版本变更记录
说明本版文档吸收了哪些历史对话中的确认项、修改项和默认假设。
""".strip()
        user_prompt = f"""
请生成第 V{document_version} 版完整正式软件需求工程分析文档。

【系统轻量分析结果】
{tool_analysis}

【智能体能力与会话记忆】
{agent_context or '暂无'}

【上一版完整文档】
{previous}

【完整历史对话】
{history_text}

请务必输出完整正式文档，不要只输出最近一轮回复，不要输出下载链接。
""".strip()
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

from agent_capabilities import extract_agent_memory, format_agent_context
try:
    from utils import build_mock_chat_response, build_mock_full_document, format_tool_analysis, score_requirement_context
except ImportError:
    from utils import build_mock_chat_response, format_tool_analysis, score_requirement_context

    def build_mock_full_document(
        messages: list[dict[str, str]],
        domain: str,
        tool_analysis: str,
        previous_document: str = "",
        document_version: int = 1,
    ) -> str:
        user_texts = [m.get("content", "") for m in messages if m.get("role") == "user"]
        topic = user_texts[0] if user_texts else "软件项目"
        latest = user_texts[-1] if user_texts else "暂无"
        return f"""# 软件需求工程分析文档

## 文档信息

- 文档版本：V{document_version}
- 当前领域：{domain}
- 文档状态：示例模式下生成的完整正式文档

## 1. 愿景和范围

本项目围绕“{topic}”开展需求工程分析，目标是将用户的多轮对话和确认信息整合为一份完整、可审阅、可导出的软件需求工程文档。

## 2. 干系人与用户分析

主要干系人包括普通用户、管理员、项目负责人、开发人员和测试人员。

## 3. 用例分析

- UC-01 用户登录与身份识别
- UC-02 核心业务信息提交
- UC-03 信息查询与筛选
- UC-04 管理员审核与维护

## 4. 软件需求规范

### 功能需求

- FR-01 系统应支持用户注册、登录和权限管理。
- FR-02 系统应支持核心业务信息的新增、查询、修改和删除。
- FR-03 系统应支持管理员审核、统计和配置。

### 非功能需求

- NFR-01 易用性：页面流程清晰。
- NFR-02 安全性：区分角色权限并保护用户数据。
- NFR-03 性能：常用查询需要在可接受时间内响应。

## 5. 分析模型

系统可划分为用户端、管理端、业务服务层、数据存储层和文档输出模块。

## 6. 业务规则

- BR-01 不同角色只能访问授权范围内的数据。
- BR-02 关键业务操作需要进行数据校验。
- BR-03 管理端应保留审核和操作记录。

## 7. 界面原型说明

主要页面包括登录页、首页、业务列表页、详情页、管理审核页和统计报表页。

## 8. 验收标准

核心业务流程可完整走通；主要数据能正确保存和查询；权限控制正确；PDF 文档可正常导出。

## 9. 风险与改进方向

风险包括需求范围扩大、用户角色不清、数据字段遗漏和验收标准过泛。后续可通过原型评审和测试用例反推继续完善。

## 10. 版本变更记录

本版文档基于历史对话生成，最新用户输入为：{latest}
"""


APP_TITLE = "软件需求工程分析智能体"
APP_SUBTITLE = "面向软件需求工程分析的对话式智能体，支持需求澄清、问题优化、方案生成和 PDF 文档导出"
FIXED_DOMAIN = "软件需求工程分析"
PDF_TRIGGER_KEYWORDS = [
    "pdf",
    "PDF",
    "文档",
    "报告",
    "下载",
    "导出",
    "需求规格",
    "需求说明",
    "详细方案",
    "详细文档",
]
TYPEWRITER_MAX_CHARS = 900
TYPEWRITER_DELAY_SECONDS = 0.012

DOWNLOAD_NOTICE = "PDF 文档已由系统生成，请使用页面下方的“下载 PDF 文档”按钮下载。"
DOWNLOAD_LINK_LABEL_KEYWORDS = [
    "下载", "PDF", "pdf", "文档", "报告", "需求规格", "需求说明", "说明书", "导出"
]


def clean_fake_download_links(text: str) -> str:
    """清理大模型可能生成的“假下载链接”。

    真实 PDF 下载由 Streamlit 的 st.download_button 提供。
    这里把模型正文里的 Markdown 下载链接或“点击此处下载”文案替换为稳定提示，
    避免用户误以为正文中的蓝色下划线文字可以触发文件下载。
    """
    if not text:
        return text

    cleaned = text

    # 1) 将 Markdown 文件/下载类链接改为普通文字说明。
    #    例如：[PDF版需求规格说明书](#)、[点击下载](xxx)。
    def replace_markdown_link(match: re.Match) -> str:
        label = match.group(1).strip()
        url = match.group(2).strip()
        if any(keyword in label for keyword in DOWNLOAD_LINK_LABEL_KEYWORDS):
            return f"{label}（{DOWNLOAD_NOTICE}）"
        # 明显的空链接也不保留，避免出现不可点击假链接。
        if url in {"", "#"} or url.lower().startswith(("javascript:", "about:blank")):
            return label
        return match.group(0)

    cleaned = re.sub(r"\[([^\]]+)\]\(([^)]*)\)", replace_markdown_link, cleaned)

    # 2) 清理常见“点击此处下载/点此下载/下载链接”等无真实绑定的文案。
    phrase_patterns = [
        r"点击此处下载\s*[:：]?\s*",
        r"点此下载\s*[:：]?\s*",
        r"点击下载\s*[:：]?\s*",
        r"下载链接\s*[:：]?\s*",
        r"PDF\s*下载链接\s*[:：]?\s*",
        r"请点击(?:上方|下方|此处)?\s*下载\s*[:：]?\s*",
    ]
    for pattern in phrase_patterns:
        cleaned = re.sub(pattern, f"{DOWNLOAD_NOTICE} ", cleaned, flags=re.IGNORECASE)

    # 3) 合并连续重复的下载提示。
    duplicate_notice_pattern = rf"(?:{re.escape(DOWNLOAD_NOTICE)}\s*){{2,}}"
    cleaned = re.sub(duplicate_notice_pattern, DOWNLOAD_NOTICE + " ", cleaned)

    return cleaned.strip()



st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)


CUSTOM_CSS = """
<style>
.block-container {
    padding-top: 1.4rem;
    padding-bottom: 1rem;
}
.main-header {
    padding: 1rem 0 0.2rem 0;
}
.small-note {
    color: #666;
    font-size: 0.92rem;
}
.markdown-preview {
    max-height: 620px;
    overflow-y: auto;
    padding: 1rem 1.1rem;
    border: 1px solid #dddddd;
    border-radius: 8px;
    background: #ffffff;
}
.preview-note {
    color: #666;
    font-size: 0.92rem;
    margin-bottom: 0.6rem;
}
.chat-panel {
    border: 1px solid #e6e6e6;
    border-radius: 8px;
    background: #ffffff;
}
section[data-testid="stChatInput"] {
    padding-top: 0.25rem;
}
.user-message-row {
    display: flex;
    justify-content: flex-end;
    align-items: flex-start;
    gap: 0.75rem;
    margin: 0.6rem 0 1.2rem 0;
}
.user-message-bubble {
    max-width: min(86%, 900px);
    padding: 1rem 1.15rem;
    border-radius: 8px;
    background: #f7f7f8;
    color: #2f3340;
    font-size: 1rem;
    line-height: 1.75;
    overflow-wrap: anywhere;
}
.user-message-avatar {
    width: 2.6rem;
    height: 2.6rem;
    min-width: 2.6rem;
    border-radius: 8px;
    background: #f25555;
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.35rem;
    line-height: 1;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def get_secret_value(key: str, default: str = "", env_key: str | None = None) -> str:
    """优先读取 Streamlit secrets，其次读取环境变量。"""
    try:
        if "api" in st.secrets and key in st.secrets["api"]:
            return str(st.secrets["api"][key])
    except Exception:
        pass
    if env_key:
        value = os.getenv(env_key)
        if value:
            return value
    return os.getenv(key.upper(), default)


def init_session_state() -> None:
    defaults = {
        "messages": [
            {
                "role": "assistant",
                "content": (
                    "你好，我是软件需求工程分析智能体。你可以直接和我对话，例如描述一个想做的软件项目，"
                    "我会帮你澄清需求、分析问题、拆解功能、设计业务流程，并在需要时生成可预览报告正文和可下载的 PDF 文档。PDF 请使用页面下方的“下载 PDF 文档”按钮获取。"
                ),
            }
        ],
        "last_report": "",
        "last_question": "",
        "last_tool_analysis": "",
        "last_pdf": b"",
        "last_run_time": "",
        "pdf_ready": False,
        "current_document": "",
        "document_version": 0,
        "document_updated_at": "",
        "pending_user_input": "",
        "is_generating": False,
        "is_document_generating": False,
        "last_error_trace": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def should_generate_pdf(user_text: str, assistant_text: str) -> bool:
    """用户主动要求文档/PDF，或回答较长时自动生成 PDF。"""
    if any(keyword in user_text for keyword in PDF_TRIGGER_KEYWORDS):
        return True
    return len(assistant_text) >= 1200


def is_document_request(user_text: str) -> bool:
    """判断用户是否在要求生成长文档或 PDF。"""
    return any(keyword in user_text for keyword in PDF_TRIGGER_KEYWORDS)


def should_typewriter(user_text: str, assistant_text: str) -> bool:
    """短问答使用逐字呈现，长文档一次性展示。"""
    if is_document_request(user_text):
        return False
    return 0 < len(assistant_text) <= TYPEWRITER_MAX_CHARS


def render_markdown_preview(report_markdown: str) -> None:
    """稳定预览报告正文：不再内嵌 PDF，避免 Edge / Streamlit iframe 拦截。"""
    report_markdown = clean_fake_download_links(report_markdown)
    if not report_markdown:
        st.info("暂无可预览的报告内容。")
        return

    st.markdown("### 报告内容预览")
    st.caption("这里预览的是智能体生成的 Markdown 报告正文；正式 PDF 请点击上方按钮下载。")
    st.markdown('<div class="markdown-preview">', unsafe_allow_html=True)
    st.markdown(report_markdown)
    st.markdown("</div>", unsafe_allow_html=True)


def build_config(
    provider: str,
    api_key: str,
    base_url: str,
    model: str,
    temperature: float,
    max_tokens: int,
    enable_thinking: bool,
) -> LLMConfig:
    return LLMConfig(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        enable_thinking=enable_thinking,
    )



def has_user_requirement(messages: list[dict[str, str]]) -> bool:
    """判断当前会话中是否已有用户需求输入。"""
    return any(m.get("role") == "user" and str(m.get("content", "")).strip() for m in messages)


def build_overall_tool_analysis(messages: list[dict[str, str]]) -> str:
    """基于完整历史用户输入生成文档级轻量分析。"""
    quality = score_requirement_context(messages)
    return (
        f"综合需求质量评分：{quality.get('score', 0)} / 100\n"
        f"综合清晰度等级：{quality.get('level', '暂无')}\n"
        f"诊断依据：{quality.get('basis', '历史对话综合诊断')}\n"
        f"累计用户轮次：{quality.get('turn_count', 0)}\n"
        f"已包含要素：{'、'.join(quality.get('present_dimensions', [])) if quality.get('present_dimensions') else '暂无明显要素'}\n"
        f"缺失要素：{'、'.join(quality.get('missing_dimensions', [])) if quality.get('missing_dimensions') else '未发现明显缺失'}\n"
        f"关键词：{'、'.join(quality.get('keywords', [])) if quality.get('keywords') else '未提取到明显关键词'}"
    )


def generate_full_document_from_history(
    provider: str,
    api_key: str,
    base_url: str,
    model: str,
    temperature: float,
    max_tokens: int,
    enable_thinking: bool,
    use_mock_mode: bool,
    history_messages: list[dict[str, str]] | None = None,
) -> str:
    """基于完整历史对话生成/刷新当前最新版正式文档，并同步生成 PDF。

    注意：PDF 永远由 current_document 转换得到，不再直接使用最近一条聊天回复。
    """
    history = history_messages or st.session_state.messages
    if not has_user_requirement(history):
        raise ValueError("当前还没有用户需求输入，无法生成完整正式文档。")

    next_version = int(st.session_state.get("document_version", 0) or 0) + 1
    document_updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tool_analysis = build_overall_tool_analysis(history)
    previous_document = st.session_state.get("current_document", "")

    if use_mock_mode:
        document_text = build_mock_full_document(
            messages=history,
            domain=FIXED_DOMAIN,
            tool_analysis=tool_analysis,
            previous_document=previous_document,
            document_version=next_version,
        )
    else:
        document_max_tokens = min(12000, max(max_tokens, 8000))
        config = build_config(
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
            max_tokens=document_max_tokens,
            enable_thinking=enable_thinking,
        )
        document_messages = build_document_messages(
            chat_history=history,
            domain=FIXED_DOMAIN,
            tool_analysis=tool_analysis,
            agent_context=format_agent_context(history),
            previous_document=previous_document,
            document_version=next_version,
        )
        document_text = call_openai_compatible(document_messages, config)

    document_text = clean_fake_download_links(document_text)
    st.session_state.current_document = document_text
    st.session_state.document_version = next_version
    st.session_state.document_updated_at = document_updated_at
    st.session_state.last_pdf = markdown_to_pdf_bytes(
        document_text,
        title="软件需求工程分析正式文档",
    )
    st.session_state.pdf_ready = True
    st.session_state.last_run_time = document_updated_at
    return document_text


def generate_assistant_response(
    user_input: str,
    provider: str,
    api_key: str,
    base_url: str,
    model: str,
    temperature: float,
    max_tokens: int,
    enable_thinking: bool,
    use_mock_mode: bool,
) -> str:
    """生成一轮助手回复，并更新报告/PDF状态。"""
    st.session_state.last_question = user_input
    st.session_state.last_tool_analysis = format_tool_analysis(user_input)
    st.session_state.last_run_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if use_mock_mode:
        assistant_text = build_mock_chat_response(
            user_input,
            FIXED_DOMAIN,
            st.session_state.last_tool_analysis,
        )
    else:
        messages = build_chat_messages(
            chat_history=st.session_state.messages[:-1],
            user_input=user_input,
            domain=FIXED_DOMAIN,
            tool_analysis=st.session_state.last_tool_analysis,
            agent_context=format_agent_context(st.session_state.messages),
        )
        config = build_config(
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            enable_thinking=enable_thinking,
        )
        assistant_text = call_openai_compatible(messages, config)

    assistant_text = clean_fake_download_links(assistant_text)
    st.session_state.last_report = assistant_text

    # 如果用户明确要求 PDF / 文档 / 报告，则自动基于完整历史对话刷新正式文档。
    # 这里不会把“最近一条聊天回复”直接转成 PDF，而是单独生成 current_document。
    if is_document_request(user_input):
        history_for_document = st.session_state.messages + [{"role": "assistant", "content": assistant_text}]
        generate_full_document_from_history(
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            enable_thinking=enable_thinking,
            use_mock_mode=use_mock_mode,
            history_messages=history_for_document,
        )

    return assistant_text


def render_typewriter(text: str, placeholder: st.delta_generator.DeltaGenerator) -> None:
    """在助手消息气泡内模拟逐字输出。"""
    rendered = ""
    for char in text:
        rendered += char
        placeholder.markdown(rendered + "▌")
        time.sleep(TYPEWRITER_DELAY_SECONDS)
    placeholder.markdown(text)


def render_user_message(content: str) -> None:
    """右侧渲染用户消息，与左侧智能体头像区分。"""
    safe_content = html.escape(content).replace("\n", "<br>")
    st.markdown(
        f"""
        <div class="user-message-row">
            <div class="user-message-bubble">{safe_content}</div>
            <div class="user-message-avatar">☺</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


init_session_state()


# =========================
# Sidebar: API 配置
# =========================
with st.sidebar:
    st.header("⚙️ 模型与运行配置")

    provider = get_secret_value("provider", "阿里云百炼 / Qwen")
    if provider not in PROVIDER_DEFAULTS:
        provider = "阿里云百炼 / Qwen"
    provider_default = PROVIDER_DEFAULTS[provider]

    secret_api_key = get_secret_value("api_key", "", provider_default.get("api_key_env"))
    secret_base_url = get_secret_value("base_url", provider_default["base_url"])
    secret_model = get_secret_value("model", provider_default["model"])
    model_options = ["deepseek-v4-flash"]
    if secret_model not in model_options:
        model_options.append(secret_model)
    model = st.selectbox("模型选择", model_options, index=model_options.index(secret_model))
    base_url = secret_base_url
    api_key = secret_api_key

    if api_key and "REPLACE" not in api_key.upper():
        st.success("模型已就绪")
    else:
        st.warning("模型暂不可用，将进入示例模式")

    temperature = st.slider("生成随机性 temperature", 0.0, 1.0, 0.3, 0.05)
    max_tokens = st.slider("最大输出 tokens", 1000, 12000, 5000, 500)
    if any(name in provider for name in ["阿里云", "百炼", "Qwen", "通义"]):
        enable_thinking = st.checkbox(
            "启用模型思考 enable_thinking",
            value=True,
            help='该参数主要用于阿里云百炼 / Qwen OpenAI-compatible 接口。',
        )
    else:
        enable_thinking = False
    st.caption("当前模型不使用 enable_thinking 参数；DeepSeek 请通过模型名选择 flash / pro。")
    api_key_available = bool(api_key) and "REPLACE" not in api_key.upper()
    use_mock_mode = not api_key_available
    if use_mock_mode:
        st.info("当前为示例模式。管理员完成模型配置后会自动启用真实模型。")

    st.divider()
    st.subheader("🎯 当前领域")
    st.info(FIXED_DOMAIN)

    if st.button("清空对话", use_container_width=True):
        for key in [
            "messages",
            "last_report",
            "last_question",
            "last_tool_analysis",
            "last_pdf",
            "last_run_time",
            "pdf_ready",
            "current_document",
            "document_version",
            "document_updated_at",
            "pending_user_input",
            "is_generating",
            "is_document_generating",
            "last_error_trace",
        ]:
            st.session_state.pop(key, None)
        init_session_state()
        st.rerun()

    st.divider()
    st.subheader("🛡️ 公开访问建议")
    st.caption("公开部署后建议限制输入长度和最大输出 tokens。")


# =========================
# Main UI
# =========================
st.markdown(f"<div class='main-header'><h1>🧠 {APP_TITLE}</h1></div>", unsafe_allow_html=True)
st.caption(APP_SUBTITLE)

st.divider()

with st.container():
    left_col, right_col = st.columns([0.68, 0.32], gap="large")

    with left_col:
        st.subheader("对话式需求分析")

        with st.container(height=640, border=True):
            for message in st.session_state.messages:
                if message["role"] == "user":
                    render_user_message(message["content"])
                else:
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])

            if st.session_state.pending_user_input:
                pending_input = st.session_state.pending_user_input
                with st.chat_message("assistant"):
                    placeholder = st.empty()
                    status_text = "正在生成内容，请稍候……" if is_document_request(pending_input) else "正在思考……"
                    placeholder.markdown(status_text)
                    try:
                        assistant_text = generate_assistant_response(
                            user_input=pending_input,
                            provider=provider,
                            api_key=api_key,
                            base_url=base_url,
                            model=model,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            enable_thinking=enable_thinking,
                            use_mock_mode=use_mock_mode,
                        )
                        if should_typewriter(pending_input, assistant_text):
                            render_typewriter(assistant_text, placeholder)
                        else:
                            placeholder.markdown(assistant_text)
                        st.session_state.messages.append({"role": "assistant", "content": assistant_text})
                    except Exception as exc:
                        error_text = f"生成失败：{exc}"
                        placeholder.error(error_text)
                        st.session_state.messages.append({"role": "assistant", "content": error_text})
                        st.session_state.last_report = error_text
                        st.session_state.last_error_trace = traceback.format_exc()
                    finally:
                        st.session_state.pending_user_input = ""
                        st.session_state.is_generating = False

        user_input = st.chat_input(
            "描述你的软件项目需求，或要求我生成 PDF / 需求规格说明文档",
            key="software_requirements_chat_input",
            disabled=st.session_state.is_generating,
        )

        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            st.session_state.pending_user_input = user_input
            st.session_state.is_generating = True
            st.session_state.last_error_trace = ""
            st.rerun()

        if st.session_state.current_document and st.session_state.pdf_ready and st.session_state.last_pdf:
            version = st.session_state.get("document_version", 0)
            updated_at = st.session_state.get("document_updated_at", "")
            st.success(f"已生成当前最新版正式文档 V{version}。PDF 内容来自完整历史对话整合结果，而不是最近一条回复。")
            if updated_at:
                st.caption(f"文档更新时间：{updated_at}")
            pdf_filename = safe_filename_from_report(st.session_state.current_document, suffix="pdf")
            pdf_col, preview_col = st.columns([0.72, 0.28])
            with pdf_col:
                st.download_button(
                    "下载 PDF 文档",
                    data=st.session_state.last_pdf,
                    file_name=pdf_filename,
                    mime="application/pdf",
                    use_container_width=True,
                )
            with preview_col:
                show_report_preview = st.toggle("预览正式文档", value=False)
            if show_report_preview:
                render_markdown_preview(st.session_state.current_document)
        elif has_user_requirement(st.session_state.messages):
            st.info("尚未生成完整正式文档。请点击右侧“生成 / 刷新完整正式文档”按钮，系统会基于全部历史对话生成最新版 PDF。")
        if st.session_state.get("last_error_trace"):
            with st.expander("查看最近错误详情"):
                st.code(st.session_state.last_error_trace)

    with right_col:
        st.subheader("实时需求诊断")
        quality = score_requirement_context(st.session_state.messages)
        st.metric("需求问题质量评分", f"{quality['score']} / 100")
        if quality.get("turn_count", 0) == 0:
            st.caption("请输入需求后，这里会显示实时诊断结果。")
        else:
            st.write(f"**清晰度等级：** {quality['level']}")
            st.write(f"**诊断依据：** {quality.get('basis', '历史对话综合诊断')}")
            st.write(f"**累计用户轮次：** {quality['turn_count']}")
            st.write("**已包含要素：**")
            st.write("、".join(quality["present_dimensions"]) if quality["present_dimensions"] else "暂无明显要素")
            st.write("**缺失要素：**")
            st.write("、".join(quality["missing_dimensions"]) if quality["missing_dimensions"] else "未发现明显缺失")
            st.write("**关键词：**")
            st.write("、".join(quality["keywords"]) if quality["keywords"] else "未提取到明显关键词")
            st.caption("该诊断会综合历史用户输入和已沉淀的需求分析内容，避免只按最近一条短回复评分。")

            memory = extract_agent_memory(st.session_state.messages)
            with st.expander("会话记忆"):
                st.caption("智能体会把这些信息作为后续需求分析上下文。")
                for key in ["产品主题", "用户角色", "核心功能", "约束偏好", "文档偏好", "选项确认"]:
                    values = memory.get(key, [])
                    if values:
                        st.write(f"**{key}：** {'、'.join(str(item) for item in values)}")
                recent_inputs = memory.get("最近用户输入", [])
                if recent_inputs:
                    st.write("**最近输入：**")
                    for item in recent_inputs:
                        st.caption(item)

        st.divider()
        st.subheader("正式文档生成")
        if st.session_state.current_document:
            st.caption(
                f"当前文档：V{st.session_state.get('document_version', 0)}"
                + (f"，更新时间：{st.session_state.get('document_updated_at')}" if st.session_state.get('document_updated_at') else "")
            )
        else:
            st.caption("当前还没有完整正式文档。")

        generate_disabled = (not has_user_requirement(st.session_state.messages)) or st.session_state.is_generating
        if st.button("生成 / 刷新完整正式文档", use_container_width=True, disabled=generate_disabled):
            with st.spinner("正在基于全部历史对话生成最新版正式文档……"):
                try:
                    generate_full_document_from_history(
                        provider=provider,
                        api_key=api_key,
                        base_url=base_url,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        enable_thinking=enable_thinking,
                        use_mock_mode=use_mock_mode,
                        history_messages=st.session_state.messages,
                    )
                    st.success("最新版正式文档已生成。请在左侧对话区下方下载 PDF 或预览正式文档。")
                except Exception as exc:
                    st.session_state.last_error_trace = traceback.format_exc()
                    st.error(f"正式文档生成失败：{exc}")
