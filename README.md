# 软件需求工程分析智能体

本项目是一个基于 **Streamlit + 公开大模型 API + 提示词工程 + 轻量工具调用 + PDF 生成** 的软件需求工程分析智能体系统。

系统固定面向：**软件需求工程分析**。用户可以像使用大模型智能体一样进行多轮对话，逐步完成需求澄清、问题优化、功能需求分析、非功能需求分析、业务流程梳理、验收标准设计，并在需要时生成可预览和下载的 PDF 文档。

## 1. 项目功能

- 多轮对话式需求工程分析；
- 轻量工具自动分析需求问题质量；
- 大模型进行需求澄清、问题诊断、需求优化、功能拆解和方案生成；
- 用户要求生成 PDF / 文档 / 报告时，自动生成 Markdown 文档和 PDF；
- 当智能体输出内容较多时，自动生成可下载 PDF；
- 支持在网页中预览 PDF；
- 支持公开部署到 Streamlit Community Cloud；
- 支持阿里云百炼、豆包、OpenAI 以及其他 OpenAI-compatible API。

## 2. 项目结构

```text
problem-optimizer-agent/
├── app.py                         # Streamlit 主程序
├── llm_client.py                  # 大模型 API 调用封装
├── prompt_templates.py            # 提示词工程模板
├── pdf_generator.py               # PDF 生成工具
├── utils.py                       # 轻量问题评分工具、示例对话
├── requirements.txt               # Python 依赖
├── README.md                      # 项目说明
├── .gitignore                     # Git 忽略文件
├── .streamlit/
│   ├── config.toml                # Streamlit 页面配置
│   └── secrets.example.toml       # API Key 配置示例，不是真实密钥
└── examples/
    ├── test_cases.md              # 测试样例
    └── training_log.md            # 提示词工程训练记录
```

## 3. 本地运行

### 3.1 安装依赖

```bash
pip install -r requirements.txt
```

### 3.2 配置 API Key

复制示例文件：

```bash
cp .streamlit/secrets.example.toml .streamlit/secrets.toml
```

然后把 `.streamlit/secrets.toml` 中的占位内容替换为你的真实配置：

```toml
[api]
provider = "阿里云百炼 / Qwen"
base_url = "https://llm-dks5jdo39k1dk6wb.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
model = "qwen-flash"
api_key = "REPLACE_WITH_YOUR_REAL_API_KEY"
```

> 注意：`.streamlit/secrets.toml` 已经写入 `.gitignore`，不要上传 GitHub。

### 3.3 启动应用

```bash
streamlit run app.py
```

## 4. 无 API Key 测试

如果还没有配置 API Key，可以在侧边栏勾选：

```text
示例模式（不调用 API）
```

示例模式不会调用真实大模型，但可以测试聊天式交互、需求评分、PDF 预览和 PDF 下载功能。

## 5. PDF 生成逻辑

系统会在以下情况下生成 PDF：

- 用户明确要求生成 PDF、文档、报告、需求规格说明或详细方案；
- 智能体输出内容较多，适合整理为文档；
- 用户点击“基于最近回答生成 PDF”按钮。

生成后可以在“文档预览与下载”页中预览 PDF，并下载 Markdown 或 PDF 文件。

## 6. 推荐演示问题

```text
我想做一个校园二手交易平台，请帮我分析需求。
```

```text
请基于刚才的分析，生成一份需求规格说明文档 PDF。
```

## 7. 部署到 Streamlit Community Cloud

1. 将本项目上传到 GitHub；
2. 确认 `.streamlit/secrets.toml` 没有上传；
3. 登录 Streamlit Community Cloud；
4. 选择 GitHub 仓库；
5. 入口文件选择 `app.py`；
6. 在 App 的 Secrets 中填写 API Key、Base URL 和模型名；
7. 点击 Deploy；
8. 部署完成后获得公开访问链接。

## 8. 作业提交建议

最终提交：

```text
1. Streamlit 公开访问链接
2. 智能体需求分析对话过程 MP4 视频
3. 智能体生成的 PDF 需求分析文档
```

录屏建议流程：

1. 打开公开访问链接；
2. 输入演示需求；
3. 展示智能体如何追问、澄清和分析需求；
4. 要求智能体生成需求规格说明文档 PDF；
5. 在网页中预览 PDF；
6. 下载并打开 PDF 展示内容。

## 9. 说明：什么是“训练”

本项目中的“训练”不是训练或微调大模型参数，而是：

```text
提示词工程训练 = 角色提示词 + 流程提示词 + 输出模板 + 测试样例 + 迭代优化
```

系统通过多轮测试不断改进提示词，使智能体稳定执行：

```text
需求理解 → 缺失信息识别 → 澄清追问 → 需求建模 → 方案输出 → PDF 文档生成
```
