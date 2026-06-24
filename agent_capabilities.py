"""
agent_capabilities.py

轻量智能体能力层：
- 知识：软件需求工程文档结构与规则
- 技能：当前智能体可执行的分析/生成能力
- 记忆：从会话历史中提取用户已表达或确认的信息
"""

from __future__ import annotations

import re


DOMAIN_KNOWLEDGE = {
    "需求文档结构": [
        "愿景和范围：背景、业务机遇、业务目标、成功指标、风险、假设与依赖、范围与限制。",
        "用例：操作者、触发器、前置条件、后置条件、正常流程、扩展流程、异常、优先级、业务规则。",
        "软件需求规范：产品视角、用户类别、运行环境、约束、系统特性、数据需求、接口需求、质量属性。",
        "分析模型：业务流程、领域对象、数据模型、状态流转、权限模型。",
        "业务规则：用 BR-编号 描述必须遵守的业务约束。",
        "界面原型：描述页面、字段、操作入口、跳转关系和关键交互。",
    ],
    "编号规范": [
        "BO：业务目标；SM：成功指标；RI：风险；AS：假设；DE：依赖。",
        "FE：系统特性；LI：限制；UC：用例；FR：功能需求；NFR：非功能需求；BR：业务规则。",
    ],
    "质量属性": [
        "易用性、性能、安全/防护、可用性、健壮性、兼容性、可维护性。",
    ],
}


AGENT_SKILLS = [
    {
        "name": "需求澄清",
        "description": "识别目标、对象、场景、功能、约束、产出和评价标准的缺口。",
    },
    {
        "name": "专家引导",
        "description": "在信息不足时给出备选方案、默认假设和少量选项式确认问题。",
    },
    {
        "name": "需求建模",
        "description": "组织用户角色、用例、业务流程、功能需求、非功能需求和数据需求。",
    },
    {
        "name": "文档生成",
        "description": "按需求工程文档结构生成可审阅的 Markdown，并触发 PDF 导出。",
    },
    {
        "name": "轻量工具分析",
        "description": "使用本地函数进行需求质量评分、关键词提取和缺失要素分析。",
    },
    {
        "name": "会话记忆",
        "description": "综合历史对话，记住用户已确认的产品方向、角色、约束和输出偏好。",
    },
]


MEMORY_PATTERNS = {
    "产品主题": ["平台", "系统", "APP", "App", "小程序", "网站", "工具"],
    "用户角色": ["学生", "教师", "管理员", "商家", "买家", "卖家", "用户", "游客"],
    "核心功能": ["发布", "搜索", "交易", "审核", "登录", "注册", "支付", "评价", "推荐", "管理", "统计"],
    "约束偏好": ["校园", "校内", "本校", "跨校", "人工审核", "排除", "食品", "预算", "时间", "隐私", "安全"],
    "交易方式": ["在线支付", "线下交易", "面交", "担保", "支付", "退款", "信用", "评价"],
    "范围约束": ["本校", "校内", "跨校", "限定", "不限", "仅限", "范围"],
    "文档偏好": ["PDF", "文档", "报告", "需求规格", "说明书", "课程作业", "正式", "详细", "最终版"],
}


def _user_messages(messages: list[dict[str, str]]) -> list[str]:
    return [m.get("content", "").strip() for m in messages if m.get("role") == "user" and m.get("content", "").strip()]


def extract_agent_memory(messages: list[dict[str, str]]) -> dict[str, list[str] | int]:
    """从用户历史输入中提取轻量记忆。"""
    user_texts = _user_messages(messages)
    joined = "\n".join(user_texts)
    memory: dict[str, list[str] | int] = {"turn_count": len(user_texts)}

    for label, terms in MEMORY_PATTERNS.items():
        hits = []
        for term in terms:
            if term in joined and term not in hits:
                hits.append(term)
        memory[label] = hits[:8]

    option_hits = re.findall(r"(?<![A-Za-z0-9])(?:\d+[A-D]|[ABCD])(?![A-Za-z0-9])", joined, flags=re.IGNORECASE)
    memory["选项确认"] = option_hits[-12:]
    memory["最近用户输入"] = user_texts[-3:]
    return memory


def format_agent_context(messages: list[dict[str, str]]) -> str:
    """把知识、技能、记忆压缩成可注入模型的上下文。"""
    memory = extract_agent_memory(messages)
    knowledge_lines = []
    for title, items in DOMAIN_KNOWLEDGE.items():
        knowledge_lines.append(f"{title}：{'；'.join(items)}")

    skill_lines = [f"{skill['name']}：{skill['description']}" for skill in AGENT_SKILLS]

    memory_lines = []
    for key, value in memory.items():
        if key == "turn_count":
            memory_lines.append(f"累计用户轮次：{value}")
        elif value:
            if isinstance(value, list):
                memory_lines.append(f"{key}：{'、'.join(str(item) for item in value)}")

    return (
        "【智能体知识】\n"
        + "\n".join(f"- {line}" for line in knowledge_lines)
        + "\n\n【智能体技能】\n"
        + "\n".join(f"- {line}" for line in skill_lines)
        + "\n\n【当前会话记忆】\n"
        + ("\n".join(f"- {line}" for line in memory_lines) if memory_lines else "- 暂无用户需求记忆")
    )
