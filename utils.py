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
> 说明：当前为示例模式。接入真实 API Key 后，本报告会由大模型自动生成。

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
> 说明：当前为示例模式。接入真实 API Key 后，文档会由大模型根据对话上下文生成。

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

如果你还不确定，可以直接说“按推荐默认方案生成需求规格说明文档 PDF”，我会先生成一版可审阅文档，并在文档中标注默认假设和待确认项。
"""
