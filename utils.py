"""
utils.py

轻量工具函数：
1. 原始问题质量评分
2. 缺失要素分析
3. 示例报告生成，用于无 API Key 时演示页面效果
"""

from __future__ import annotations

import re
from datetime import datetime


REQUIRED_DIMENSIONS = {
    "目标": ["目标", "希望", "想要", "实现", "解决", "提升", "降低", "完成"],
    "对象": ["用户", "学生", "教师", "企业", "客户", "管理员", "对象", "人群"],
    "场景": ["场景", "使用", "应用", "校园", "课堂", "线上", "线下", "平台"],
    "功能": ["功能", "模块", "系统", "页面", "流程", "管理", "分析", "推荐"],
    "约束": ["限制", "约束", "时间", "成本", "预算", "技术", "数据", "要求"],
    "产出": ["报告", "方案", "原型", "文档", "系统", "代码", "PDF", "设计"],
    "评价": ["评价", "指标", "效果", "标准", "准确率", "效率", "满意度", "验收"],
}


def _contains_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def extract_keywords(question: str, max_keywords: int = 8) -> list[str]:
    """非常轻量的关键词提取，避免引入复杂 NLP 依赖。"""
    text = re.sub(r"[，。！？、；：,.!?;:\n\t()（）\[\]【】]", " ", question)
    candidates = [w.strip() for w in text.split() if len(w.strip()) >= 2]

    # 中文场景下，如果用户没有空格，做一个简单短语匹配兜底
    fallback_terms = [
        "校园", "二手", "交易", "在线学习", "学生", "成绩", "分析", "系统", "平台", "App",
        "需求", "设计", "智能体", "科研", "项目", "课程", "推荐", "管理", "报告",
    ]
    for term in fallback_terms:
        if term in question and term not in candidates:
            candidates.append(term)

    seen = set()
    keywords = []
    for word in candidates:
        if word not in seen:
            seen.add(word)
            keywords.append(word)
        if len(keywords) >= max_keywords:
            break
    return keywords


def score_question_quality(question: str) -> dict:
    """对原始问题做一个可解释的轻量评分。"""
    normalized = question.strip()
    length = len(normalized)

    dimension_hits = {}
    for dim, words in REQUIRED_DIMENSIONS.items():
        dimension_hits[dim] = _contains_any(normalized, words)

    dimension_score = sum(1 for v in dimension_hits.values() if v) / len(REQUIRED_DIMENSIONS) * 70

    if length >= 80:
        length_score = 20
    elif length >= 40:
        length_score = 15
    elif length >= 20:
        length_score = 10
    else:
        length_score = 5

    question_mark_score = 10 if any(mark in normalized for mark in ["？", "?", "如何", "怎么", "怎样", "帮我"]) else 5
    total = round(min(100, dimension_score + length_score + question_mark_score), 1)

    missing = [dim for dim, hit in dimension_hits.items() if not hit]
    present = [dim for dim, hit in dimension_hits.items() if hit]
    keywords = extract_keywords(normalized)

    if total >= 80:
        level = "较清晰"
    elif total >= 60:
        level = "基本清晰但仍需优化"
    elif total >= 40:
        level = "较模糊"
    else:
        level = "非常模糊"

    return {
        "score": total,
        "level": level,
        "present_dimensions": present,
        "missing_dimensions": missing,
        "keywords": keywords,
        "length": length,
    }


def score_requirement_context(messages: list[dict[str, str]]) -> dict:
    """基于历史对话综合评估需求清晰度，避免只看最近一条短回复。"""
    user_texts = [m.get("content", "") for m in messages if m.get("role") == "user"]
    combined_user_text = "\n".join(user_texts).strip()

    if not combined_user_text:
        return {
            "score": 0.0,
            "level": "",
            "present_dimensions": [],
            "missing_dimensions": [],
            "keywords": [],
            "length": 0,
            "turn_count": 0,
            "basis": "等待用户输入",
        }

    # 评分主体只看用户已经提供/确认的信息，避免助手自动补全导致首轮模糊需求被误判为满分。
    result = score_question_quality(combined_user_text)

    turn_count = len(user_texts)
    progress_bonus = min(12, max(0, turn_count - 1) * 4)

    option_detail_patterns = [
        r"\b[ABCD]\b",
        r"\b\d+[A-D]\b",
        "默认",
        "确认",
        "MVP",
        "发布",
        "优先",
        "角色",
        "页面",
        "流程",
        "验收",
        "约束",
    ]
    detail_hits = sum(1 for pattern in option_detail_patterns if re.search(pattern, combined_user_text, re.IGNORECASE))
    detail_bonus = min(10, detail_hits * 2)

    first_turn_cap = 65 if turn_count <= 1 else 100
    accumulated_score = min(first_turn_cap, result["score"] + progress_bonus + detail_bonus)
    result["score"] = round(accumulated_score, 1)
    result["turn_count"] = turn_count
    result["basis"] = "历史对话综合诊断"

    if result["score"] >= 80:
        result["level"] = "较清晰"
    elif result["score"] >= 60:
        result["level"] = "基本清晰但仍需优化"
    elif result["score"] >= 40:
        result["level"] = "较模糊"
    else:
        result["level"] = "非常模糊"

    return result


def format_tool_analysis(question: str) -> str:
    """格式化工具分析结果，作为上下文传给大模型。"""
    result = score_question_quality(question)
    return (
        f"问题质量评分：{result['score']} / 100\n"
        f"问题清晰度等级：{result['level']}\n"
        f"已包含要素：{', '.join(result['present_dimensions']) if result['present_dimensions'] else '暂无明显要素'}\n"
        f"缺失要素：{', '.join(result['missing_dimensions']) if result['missing_dimensions'] else '未发现明显缺失'}\n"
        f"关键词：{', '.join(result['keywords']) if result['keywords'] else '未提取到明显关键词'}\n"
        f"原始问题长度：{result['length']} 字"
    )


def build_mock_report(question: str, domain: str, tool_analysis: str) -> str:
    """无 API Key 时使用的示例报告。真实运行时会由大模型生成。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""# 问题优化智能体求解报告

> 生成时间：{now}  
> 当前领域：{domain}  
> 说明：当前为示例模式。接入真实 API Key 后，本报告会由大模型自动生成。PDF 下载由页面下方系统按钮提供，正文不生成虚假下载链接。

## 1. 原始问题

{question}

## 2. 原始问题诊断

该问题表达了一个初步需求，但仍然偏模糊。主要问题包括：目标用户不够明确、核心功能未细化、项目边界不清晰、缺少验收指标，也没有说明技术、时间、成本等约束。

## 3. 轻量工具分析结果

{tool_analysis}

## 4. 缺失信息分析

从问题优化角度看，当前问题至少需要补充以下信息：

- 目标用户：系统主要服务哪些人群；
- 使用场景：用户在什么情况下使用该系统；
- 核心功能：系统必须具备哪些关键能力；
- 约束条件：是否有技术、时间、数据或成本限制；
- 评价标准：如何判断方案是否成功。

## 5. 优化后的高质量问题

请设计一个面向校园用户的软件项目方案，明确目标用户、主要使用场景、核心功能模块、技术实现方式、数据管理方案、系统风险以及评价指标，并形成一份适合课程作业提交的需求分析报告。

## 6. 子问题拆解

1. 项目的目标用户是谁？
2. 用户在什么场景下会使用该系统？
3. 系统应该包含哪些核心功能？
4. 系统前端、后端和数据库如何设计？
5. 如何保证系统可用性、安全性和可扩展性？
6. 项目最终如何验收？

## 7. 解决方案

### 7.1 项目背景

该项目面向校园场景，目标是将用户的模糊想法转化为可执行的软件需求方案。

### 7.2 目标用户

主要用户包括普通学生、管理员以及潜在的教师或运营人员。

### 7.3 功能需求

- 用户注册与登录；
- 信息发布与管理；
- 搜索与筛选；
- 消息通知；
- 后台审核；
- 数据统计。

### 7.4 非功能需求

- 易用性：界面简洁，操作步骤少；
- 安全性：保护用户数据；
- 稳定性：支持多人同时访问；
- 可扩展性：后续可增加 AI 推荐、数据分析等能力。

## 8. 实施步骤

1. 明确需求范围；
2. 设计页面原型；
3. 搭建前后端基础框架；
4. 实现核心业务功能；
5. 完成测试与优化；
6. 生成项目报告并进行展示。

## 9. 风险与改进方向

风险包括需求范围扩大、数据质量不足、用户使用意愿不强、系统安全机制不足等。后续可以通过用户调研、权限控制、数据分析和智能推荐机制进行改进。

## 10. 智能体自我检查

- 原始问题诊断完整性：16 / 20
- 优化后问题清晰度：17 / 20
- 子问题拆解合理性：17 / 20
- 方案可执行性：16 / 20
- 报告规范性：18 / 20

总分：84 / 100。整体方案结构完整，但真实 API 模式下可以生成更贴合原始问题的细化内容。

## 11. 可复用提示词模板

请围绕【项目名称】设计一份软件需求分析方案，要求明确目标用户、使用场景、核心功能、页面模块、数据模块、技术架构、风险分析和评价指标，并输出适合课程作业提交的结构化报告。

## 12. 总结

本次问题优化过程将一个较模糊的项目想法转化为结构化、可执行的问题，并进一步生成了需求分析方案。该流程体现了问题诊断、问题优化、子问题拆解和方案生成的完整智能体能力。
"""


def build_mock_chat_response(user_input: str, domain: str, tool_analysis: str) -> str:
    """无 API Key 时使用的对话式示例回复。"""
    wants_document = any(
        keyword in user_input
        for keyword in ["pdf", "PDF", "文档", "报告", "需求规格", "详细方案", "导出", "下载"]
    )
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if wants_document:
        return f"""# 软件需求工程分析文档

> 生成时间：{now}  
> 当前领域：{domain}  
> 说明：当前为示例模式。接入真实 API Key 后，文档会由大模型根据对话上下文生成。PDF 下载由页面下方系统按钮提供，正文不生成虚假下载链接。

## 1. 用户原始需求

{user_input}

## 2. 需求问题诊断

当前需求已经表达出一个软件项目意图，但仍需要进一步明确目标用户、核心业务场景、功能边界、数据对象、权限角色、非功能需求和验收标准。

## 3. 轻量工具分析结果

{tool_analysis}

## 4. 利益相关者分析

- 普通用户：完成主要业务操作；
- 管理员：进行数据审核、用户管理和运营维护；
- 项目负责人：关注范围、进度、质量和验收；
- 开发与测试人员：依据需求说明完成设计、实现和测试。

## 5. 功能需求

1. 用户注册、登录与权限管理；
2. 核心业务信息的新增、查询、修改和删除；
3. 搜索、筛选、排序和详情查看；
4. 管理端审核、统计和配置；
5. 消息提醒与状态流转。

## 6. 非功能需求

- 易用性：页面流程清晰，关键操作步骤少；
- 安全性：保护用户数据，区分不同角色权限；
- 性能：常用查询需要在可接受时间内响应；
- 可维护性：模块边界清晰，便于后续扩展。

## 7. 业务流程

1. 用户进入系统并登录；
2. 用户提交或查询业务信息；
3. 系统进行数据校验和状态更新；
4. 管理员处理异常或审核事项；
5. 系统生成统计结果或通知用户。

## 8. 验收标准

- 核心功能能够按角色正常完成；
- 主要业务流程无阻塞；
- 数据保存、查询和权限控制正确；
- 需求文档、测试用例和演示材料完整。

## 9. 风险与改进建议

主要风险包括需求边界扩大、用户角色不清、数据字段遗漏和验收标准过泛。建议后续通过访谈、原型评审和测试用例反推继续完善需求。
"""

    return f"""我已按 **{domain}** 的方式理解你的问题。下面先做一轮需求工程分析：

**1. 初步判断**

你的输入已经说明了一个软件项目方向，但还需要进一步明确用户、场景、功能边界、数据对象和验收标准。

**2. 轻量诊断**

{tool_analysis}

**3. 我先给你 3 个可选设计方向**

A. **课程学习管理型**：重点解决课程资料、学习计划、任务提醒、进度追踪问题。适合课程作业和学习效率场景。  
B. **题库练习与测评型**：重点解决刷题、错题、测评、学习反馈问题。适合考试复习和能力提升场景。  
C. **AI 学习助手型**：重点解决答疑、知识总结、个性化推荐问题。适合突出智能体特色。

**推荐默认方案：A + C 的组合。**  
理由：既能体现真实软件需求工程中的业务流程和功能模块，又能体现智能体或 AI 能力，适合生成完整需求文档。

**4. 基于默认方案，我可以先做如下假设**

- 目标用户：大学生；
- 核心场景：课程学习、资料整理、学习计划、AI 辅助答疑；
- MVP 功能：用户登录、课程管理、学习任务、资料上传、AI 问答、学习进度；
- 后续功能：智能推荐、错题分析、教师端管理、学习数据报表；
- 验收标准：核心流程可用、响应及时、权限清晰、文档完整。

**5. 你只需要选择或确认以下选项**

1. 产品定位选哪个？A 课程学习管理 / B 题库练习测评 / C AI 学习助手 / D A+C 综合型；
2. 用户角色选哪些？A 学生 / B 教师 / C 管理员 / D 多角色；
3. 文档深度选哪个？A 简版 / B 课程作业版 / C 完整需求规格说明书；

**6. 下一步**

如果你还不确定，可以直接说“按推荐默认方案生成需求规格说明文档 PDF”，我会先生成一版可审阅文档，并由页面下方的系统按钮提供 PDF 下载，文档中会标注默认假设和待确认项。
"""


def _format_recent_user_inputs_for_mock(messages: list[dict[str, str]], max_items: int = 8) -> str:
    """示例模式下格式化最近用户输入。"""
    user_texts = [m.get("content", "").strip() for m in messages if m.get("role") == "user" and m.get("content", "").strip()]
    if not user_texts:
        return "暂无明确用户输入。"
    return "\n".join(f"- {item}" for item in user_texts[-max_items:])


def build_mock_full_document(
    messages: list[dict[str, str]],
    domain: str,
    tool_analysis: str,
    previous_document: str = "",
    document_version: int = 1,
) -> str:
    """无 API Key 时生成一份“基于完整对话的正式文档”示例。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    recent_inputs = _format_recent_user_inputs_for_mock(messages)
    previous_note = "已有上一版文档，本版在上一版基础上融合最新对话。" if previous_document.strip() else "暂无上一版文档，本版为基于当前对话生成的初版。"

    return f"""# 软件需求工程分析文档

> 文档版本：V{document_version}  
> 文档状态：当前最新版  
> 生成时间：{now}  
> 当前领域：{domain}  
> 说明：当前为示例模式。接入真实 API Key 后，系统会基于完整历史对话生成更贴合项目的正式文档。PDF 下载由页面下方系统按钮提供，正文不生成虚假下载链接。

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 项目名称 | 示例软件项目需求工程分析 |
| 文档版本 | V{document_version} |
| 文档状态 | 当前最新版 |
| 生成方式 | 基于完整历史对话与会话记忆生成 |
| 版本说明 | {previous_note} |

### 1.1 最近用户需求输入

{recent_inputs}

## 2. 愿景和范围

### 2.1 业务背景

用户希望围绕一个软件项目想法形成正式需求工程分析文档。系统需要把模糊描述转化为可审阅、可开发、可验收的需求说明。

### 2.2 业务目标

- BO-1：明确项目目标用户、核心场景和主要业务流程。
- BO-2：形成覆盖功能需求、非功能需求、数据需求和业务规则的正式文档。
- BO-3：为后续原型设计、开发实现和验收测试提供依据。

### 2.3 成功指标

- SM-1：文档覆盖核心业务流程不少于 3 个。
- SM-2：功能需求、非功能需求和业务规则均有编号化描述。
- SM-3：主要用户角色、核心用例和验收标准清晰可验证。

### 2.4 范围与限制

- 范围：需求澄清、用例分析、功能建模、数据建模、业务规则和验收标准。
- 限制：示例模式不会调用真实大模型，内容用于演示工作流。

## 3. 干系人与用户分析

| 干系人 | 主要价值 | 态度 | 主要兴趣 | 约束 |
|---|---|---|---|---|
| 普通用户 | 完成核心业务操作 | 支持 | 操作便捷、结果可靠 | 需要低学习成本 |
| 管理员 | 管理用户与数据 | 支持 | 审核、统计、配置 | 需要权限控制 |
| 项目负责人 | 控制范围和进度 | 支持 | 质量、风险、验收 | 受时间与资源限制 |
| 开发与测试人员 | 依据需求实现系统 | 中立 | 需求明确、可测试 | 需要清晰接口与规则 |

## 4. 用例分析

### 4.1 用例列表

| 用例编号 | 用例名称 | 主要操作者 | 优先级 |
|---|---|---|---|
| UC-1 | 用户登录与身份识别 | 普通用户 | 高 |
| UC-2 | 核心业务信息提交 | 普通用户 | 高 |
| UC-3 | 信息查询与筛选 | 普通用户 | 高 |
| UC-4 | 后台审核与管理 | 管理员 | 中 |

### 4.2 核心用例 UC-2：核心业务信息提交

- 触发器：用户进入系统并点击新增或发布入口。
- 前置条件：用户已完成登录，具备对应操作权限。
- 后置条件：业务信息被保存并进入待处理或已发布状态。
- 正常流程：填写信息、系统校验、提交保存、返回结果。
- 异常流程：字段缺失、权限不足、网络失败或数据重复。
- 业务规则：BR-1 用户提交内容必须满足必填字段和合法性校验。

## 5. 软件需求规范

### 5.1 产品视角

系统作为面向课程作业或项目实践的需求分析对象，应支持用户操作、数据管理、状态流转和后台维护。

### 5.2 功能需求

- FR-1：系统应支持用户注册、登录和权限识别。
- FR-2：系统应支持核心业务信息的新增、查询、修改和删除。
- FR-3：系统应支持搜索、筛选、排序和详情查看。
- FR-4：系统应支持后台审核、统计和配置管理。
- FR-5：系统应支持必要的消息提示和状态更新。

### 5.3 非功能需求

- NFR-1 易用性：主要操作路径应清晰，关键任务可在较少步骤内完成。
- NFR-2 性能：常用查询应在可接受时间内返回。
- NFR-3 安全性：系统应保护用户数据并区分角色权限。
- NFR-4 可维护性：模块划分清晰，便于后续扩展。
- NFR-5 健壮性：异常输入和网络错误应有友好提示。

### 5.4 数据需求

| 数据对象 | 关键字段 | 说明 |
|---|---|---|
| 用户 | 用户ID、角色、联系方式、状态 | 支撑身份识别和权限控制 |
| 业务记录 | 记录ID、标题、内容、状态、创建时间 | 支撑核心业务流程 |
| 操作日志 | 日志ID、操作人、操作类型、时间 | 支撑审计和问题追踪 |

## 6. 系统特性与功能模块

- FE-1 用户与权限模块：支持登录、角色识别、权限控制。
- FE-2 核心业务模块：支持业务信息维护和状态流转。
- FE-3 查询检索模块：支持关键词搜索、筛选和详情查看。
- FE-4 管理后台模块：支持审核、统计、配置和用户管理。

## 7. 数据需求与分析模型

### 7.1 业务流程

用户登录后进入系统，完成核心业务信息提交、查询或管理；系统进行数据校验、保存和状态更新；管理员根据规则进行审核或维护。

### 7.2 状态流转

业务记录可包含：草稿、待审核、已通过、已驳回、已归档等状态。

### 7.3 权限模型

普通用户可维护自身数据；管理员可进行审核、统计和配置；系统保留操作日志用于追踪。

## 8. 业务规则

- BR-1：用户必须登录后才能执行需要身份识别的操作。
- BR-2：关键业务字段不能为空，且必须满足格式校验。
- BR-3：管理员审核操作必须记录操作人和操作时间。
- BR-4：普通用户不得访问超出自身权限范围的数据。

## 9. 界面原型说明

- 登录页：输入账号、密码，完成身份认证。
- 首页：展示核心功能入口、最新记录和操作提示。
- 列表页：支持搜索、筛选、排序和分页。
- 详情页：展示完整业务信息和状态。
- 管理页：提供审核、统计和配置功能。

## 10. 验收标准

- 功能验收：核心流程可按角色正常完成。
- 性能验收：常用查询和提交操作响应及时。
- 安全验收：权限控制、数据校验和日志记录有效。
- 易用性验收：页面入口清晰，操作提示明确。
- 文档验收：需求、用例、规则、模型和验收标准完整。

## 11. 风险与改进方向

主要风险包括需求边界扩大、用户角色不清、数据字段遗漏和验收标准过泛。后续应通过用户访谈、原型评审、测试用例反推和迭代更新继续完善需求。

## 12. 版本变更记录

| 版本 | 变更说明 |
|---|---|
| V{document_version} | 基于当前完整历史对话生成或刷新最新版正式文档。 |

## 13. 总结

本版本文档把对话中的项目想法、确认项和默认假设转化为结构化的软件需求工程分析文档。正式 API 模式下，系统会进一步结合全部历史对话和上一版文档，生成更贴合具体项目的可提交版本。
"""
