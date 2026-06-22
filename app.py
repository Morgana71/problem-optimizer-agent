"""
Streamlit 主程序：通用问题优化智能体

运行方式：
streamlit run app.py
"""

from __future__ import annotations

import os
import traceback
from datetime import datetime

import streamlit as st

from llm_client import LLMConfig, PROVIDER_DEFAULTS, call_openai_compatible
from pdf_generator import markdown_to_pdf_bytes, safe_filename_from_question
from prompt_templates import build_messages
from utils import build_mock_report, format_tool_analysis, score_question_quality


APP_TITLE = "通用问题优化智能体"
APP_SUBTITLE = "基于公开大模型 API + 提示词工程 + 轻量工具调用的领域问题优化系统"


st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)


CUSTOM_CSS = """
<style>
.main-header {
    padding: 1rem 0 0.2rem 0;
}
.small-note {
    color: #666;
    font-size: 0.92rem;
}
.result-box {
    border: 1px solid #e6e6e6;
    border-radius: 12px;
    padding: 1rem;
    background: #fafafa;
}
.metric-card {
    border: 1px solid #eee;
    border-radius: 12px;
    padding: 0.75rem;
    background: #fff;
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
        "last_report": "",
        "last_question": "",
        "last_tool_analysis": "",
        "last_pdf": b"",
        "last_run_time": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


init_session_state()


# =========================
# Sidebar: API 配置
# =========================
with st.sidebar:
    st.header("⚙️ 模型与运行配置")

    provider_options = list(PROVIDER_DEFAULTS.keys())
    default_provider = get_secret_value("provider", "阿里云百炼 / Qwen")
    if default_provider not in provider_options:
        default_provider = "阿里云百炼 / Qwen"

    provider = st.selectbox("模型服务商", provider_options, index=provider_options.index(default_provider))
    provider_default = PROVIDER_DEFAULTS[provider]

    secret_api_key = get_secret_value("api_key", "", provider_default.get("api_key_env"))
    secret_base_url = get_secret_value("base_url", provider_default["base_url"])
    secret_model = get_secret_value("model", provider_default["model"])

    base_url = st.text_input(
        "Base URL",
        value=secret_base_url,
        help="OpenAI-compatible 接口地址。一般填写到 /v1 或 /api/v3 即可，程序会自动拼接 /chat/completions。",
    )
    model = st.text_input("模型名称", value=secret_model)
    api_key = st.text_input(
        "API Key",
        value=secret_api_key,
        type="password",
        help=f"建议部署时放到 Streamlit Secrets；本服务商也支持环境变量 {provider_default.get('api_key_env', 'API_KEY')}。",
    )

    temperature = st.slider("生成随机性 temperature", 0.0, 1.0, 0.3, 0.05)
    max_tokens = st.slider("最大输出 tokens", 1000, 12000, 5000, 500)
    enable_thinking = st.checkbox(
        "启用模型思考 enable_thinking",
        value=True,
        help="对应阿里云百炼 OpenAI-compatible 示例中的 extra_body={\"enable_thinking\": True}。",
    )
    use_mock_mode = st.checkbox(
        "示例模式（不调用 API）",
        value=not bool(api_key) or "REPLACE" in api_key.upper(),
        help="没有 API Key 时可以先用示例模式测试页面和 PDF 下载功能。",
    )

    st.divider()
    st.subheader("🛡️ 公开访问建议")
    st.caption("公开部署后建议限制输入长度、控制最大输出 tokens，并避免泄露 API Key。")


# =========================
# Main UI
# =========================
st.markdown(f"<div class='main-header'><h1>🧠 {APP_TITLE}</h1></div>", unsafe_allow_html=True)
st.caption(APP_SUBTITLE)

main_tab, prompt_tab, training_tab, deploy_tab = st.tabs([
    "🚀 智能体运行",
    "🧩 提示词工程",
    "🧪 训练记录模板",
    "🌐 部署说明",
])


with main_tab:
    left_col, right_col = st.columns([0.66, 0.34], gap="large")

    with left_col:
        st.subheader("1. 输入原始问题")

        domain_options = [
            "软件项目需求分析",
            "科研选题与项目申请",
            "课程学习与考试复习",
            "产品设计与商业策划",
            "自定义领域",
        ]
        domain_choice = st.selectbox("选择问题领域", domain_options)
        if domain_choice == "自定义领域":
            domain = st.text_input("请输入自定义领域", value="软件项目需求分析")
        else:
            domain = domain_choice

        default_question = "我想做一个校园二手交易平台，应该怎么做？"
        question = st.text_area(
            "请输入一个较模糊或需要优化的问题",
            value=default_question,
            height=140,
            max_chars=1200,
            help="建议输入 20～1000 字。系统会先诊断问题，再优化问题并生成报告。",
        )

        report_style = st.radio(
            "报告风格",
            ["课程作业版", "简洁汇报版", "详细报告版"],
            horizontal=True,
        )

        extra_constraints = st.text_area(
            "额外约束（可选）",
            value="输出适合录制 MP4 演示和导出 PDF 提交，语言正式，结构完整。",
            height=90,
        )

        run_button = st.button("开始优化并生成报告", type="primary", use_container_width=True)

    with right_col:
        st.subheader("2. 轻量工具分析")
        if question.strip():
            quality = score_question_quality(question)
            st.metric("原始问题质量评分", f"{quality['score']} / 100")
            st.write(f"**清晰度等级：** {quality['level']}")
            st.write("**已包含要素：**")
            st.write("、".join(quality["present_dimensions"]) if quality["present_dimensions"] else "暂无明显要素")
            st.write("**缺失要素：**")
            st.write("、".join(quality["missing_dimensions"]) if quality["missing_dimensions"] else "未发现明显缺失")
            st.write("**关键词：**")
            st.write("、".join(quality["keywords"]) if quality["keywords"] else "未提取到明显关键词")
        else:
            st.info("输入问题后，这里会显示轻量工具分析结果。")

    if run_button:
        if not question.strip():
            st.error("请先输入原始问题。")
        else:
            tool_analysis = format_tool_analysis(question)
            st.session_state.last_question = question
            st.session_state.last_tool_analysis = tool_analysis
            st.session_state.last_run_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with st.spinner("智能体正在进行问题诊断、问题优化、方案生成和 PDF 报告准备……"):
                try:
                    if use_mock_mode:
                        report_markdown = build_mock_report(question, domain, tool_analysis)
                    else:
                        messages = build_messages(
                            question=question,
                            domain=domain,
                            tool_analysis=tool_analysis,
                            extra_constraints=extra_constraints,
                            report_style=report_style,
                            report_title="问题优化智能体求解报告",
                        )
                        config = LLMConfig(
                            provider=provider,
                            api_key=api_key,
                            base_url=base_url,
                            model=model,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            enable_thinking=enable_thinking,
                        )
                        report_markdown = call_openai_compatible(messages, config)

                    pdf_bytes = markdown_to_pdf_bytes(report_markdown, title="问题优化智能体求解报告")
                    st.session_state.last_report = report_markdown
                    st.session_state.last_pdf = pdf_bytes
                    st.success("生成完成。")
                except Exception as exc:
                    st.error(f"生成失败：{exc}")
                    with st.expander("查看错误详情"):
                        st.code(traceback.format_exc())

    if st.session_state.last_report:
        st.divider()
        st.subheader("3. 智能体输出结果")
        st.caption(f"最近生成时间：{st.session_state.last_run_time}")
        st.markdown(st.session_state.last_report)

        md_filename = safe_filename_from_question(st.session_state.last_question, suffix="md")
        pdf_filename = safe_filename_from_question(st.session_state.last_question, suffix="pdf")

        download_col1, download_col2 = st.columns(2)
        with download_col1:
            st.download_button(
                "下载 Markdown 报告",
                data=st.session_state.last_report.encode("utf-8"),
                file_name=md_filename,
                mime="text/markdown",
                use_container_width=True,
            )
        with download_col2:
            st.download_button(
                "下载 PDF 报告",
                data=st.session_state.last_pdf,
                file_name=pdf_filename,
                mime="application/pdf",
                use_container_width=True,
            )


with prompt_tab:
    st.subheader("提示词工程说明")
    st.markdown(
        """
本系统中的“训练”不是微调大模型参数，而是通过提示词工程和轻量工具调用，对智能体的行为进行约束和迭代优化。

核心机制包括：

1. **角色提示词**：规定智能体是“问题优化智能体”，不是普通问答助手。  
2. **流程提示词**：要求它必须按照“诊断 → 优化 → 拆解 → 求解 → 自检”的顺序工作。  
3. **输出模板**：固定 12 个报告章节，保证 PDF 文档结构稳定。  
4. **轻量工具调用**：先用 Python 函数对原始问题进行评分和缺失要素分析，再把结果提供给大模型。  
5. **PDF 生成工具**：将智能体输出的 Markdown 报告转换为 PDF 文件，供用户下载。  

你后续主要修改 `prompt_templates.py` 文件，就可以完成提示词工程训练。
        """
    )

    with st.expander("查看当前提示词结构"):
        st.code(
            """
System Prompt：
- 角色：通用问题优化智能体
- 当前领域：由用户选择
- 工作原则：先优化问题，再解决问题
- 输出结构：固定 12 个章节

User Prompt：
- 当前领域
- 用户原始问题
- 轻量工具分析结果
- 用户额外约束
- 报告风格要求
            """.strip(),
            language="text",
        )


with training_tab:
    st.subheader("提示词工程训练记录模板")
    st.markdown(
        """
建议你在最终提交材料中保留一份训练记录，证明你做过多轮提示词优化。
可以直接使用项目中的 `examples/training_log.md`。
        """
    )
    st.code(
        """
第 1 轮：基础提示词
测试问题：我想做一个校园二手交易平台，应该怎么做？
发现问题：模型直接给方案，问题诊断不足。
修改策略：加入“必须先诊断，再优化，再求解”的流程约束。

第 2 轮：输出模板约束
测试问题：我想做一个在线学习 App，帮我设计一下。
发现问题：报告结构不稳定。
修改策略：固定 12 个 Markdown 章节。

第 3 轮：加入轻量工具分析
测试问题：我想做一个学生成绩分析系统，帮我规划一下。
发现问题：缺少量化分析和自检。
修改策略：加入问题质量评分、缺失要素分析和 100 分自评。
        """.strip(),
        language="text",
    )


with deploy_tab:
    st.subheader("公开部署流程")
    st.markdown(
        """
推荐部署到 Streamlit Community Cloud：

1. 将本项目上传到 GitHub；
2. 确认 `.gitignore` 中已经忽略 `.streamlit/secrets.toml`；
3. 在 Streamlit Cloud 中选择 GitHub 仓库和 `app.py`；
4. 在 Secrets 中配置 API Key、Base URL 和模型名；
5. 点击 Deploy，获得公开访问链接；
6. 打开链接，输入演示问题，生成报告并下载 PDF；
7. 录制 MP4：展示访问链接、输入问题、智能体求解过程、PDF 下载和打开过程。

Secrets 示例：
        """
    )
    st.code(
        """
[api]
provider = "阿里云百炼 / Qwen"
base_url = "https://llm-dks5jdo39k1dk6wb.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
model = "qwen-flash"
api_key = "REPLACE_WITH_YOUR_REAL_API_KEY"
        """.strip(),
        language="toml",
    )

