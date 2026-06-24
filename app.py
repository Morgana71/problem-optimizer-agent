"""
Streamlit 主程序：软件需求工程分析智能体

运行方式：
streamlit run app.py
"""

from __future__ import annotations

import base64
import html
import os
import time
import traceback
from datetime import datetime

import streamlit as st

from llm_client import LLMConfig, PROVIDER_DEFAULTS, call_openai_compatible
from pdf_generator import markdown_to_pdf_bytes, safe_filename_from_report
from prompt_templates import build_chat_messages
from agent_capabilities import extract_agent_memory, format_agent_context
from utils import build_mock_chat_response, format_tool_analysis, score_requirement_context


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
.pdf-preview {
    width: 100%;
    height: 620px;
    border: 1px solid #dddddd;
    border-radius: 8px;
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
                    "我会帮你澄清需求、分析问题、拆解功能、设计业务流程，并在需要时生成可预览和下载的 PDF 文档。"
                ),
            }
        ],
        "last_report": "",
        "last_question": "",
        "last_tool_analysis": "",
        "last_pdf": b"",
        "last_run_time": "",
        "pdf_ready": False,
        "pending_user_input": "",
        "is_generating": False,
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


def render_pdf_preview(pdf_bytes: bytes) -> None:
    """在页面中预览 PDF。"""
    encoded = base64.b64encode(pdf_bytes).decode("ascii")
    st.markdown(
        f'<iframe class="pdf-preview" src="data:application/pdf;base64,{encoded}"></iframe>',
        unsafe_allow_html=True,
    )


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

    st.session_state.last_report = assistant_text

    if should_generate_pdf(user_input, assistant_text):
        st.session_state.last_pdf = markdown_to_pdf_bytes(
            assistant_text,
            title="软件需求工程分析智能体文档",
        )
        st.session_state.pdf_ready = True
    else:
        st.session_state.pdf_ready = False
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
    model_options = ["qwen-flash"]
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
    enable_thinking = st.checkbox(
        "启用模型思考 enable_thinking",
        value=True,
        help='对应阿里云百炼 OpenAI-compatible 示例中的 extra_body={"enable_thinking": True}。',
    )
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
            "pending_user_input",
            "is_generating",
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

        if st.session_state.pdf_ready and st.session_state.last_pdf:
            st.success("已生成可下载的 PDF 文档。")
            pdf_filename = safe_filename_from_report(st.session_state.last_report, suffix="pdf")
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
                show_pdf_preview = st.toggle("预览", value=False)
            if show_pdf_preview:
                render_pdf_preview(st.session_state.last_pdf)
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
        if st.button("基于最近回答生成 PDF", use_container_width=True, disabled=not bool(st.session_state.last_report)):
            st.session_state.last_pdf = markdown_to_pdf_bytes(
                st.session_state.last_report,
                title="软件需求工程分析智能体文档",
            )
            st.session_state.pdf_ready = True
            st.success("PDF 已生成，可在对话区下方下载或预览。")
