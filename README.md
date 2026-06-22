# 通用问题优化智能体

本项目是一个基于 **Streamlit + 公开大模型 API + 提示词工程 + 轻量工具调用 + PDF 生成** 的 Web 智能体系统。

默认示例领域为：**软件项目需求分析**。系统可以将用户输入的模糊问题转化为清晰、完整、可执行的问题，并进一步生成结构化解决方案和 PDF 报告。

## 1. 项目功能

- 输入原始问题；
- 轻量工具自动分析问题质量；
- 大模型进行问题诊断、问题优化、子问题拆解和方案生成；
- 自动生成 Markdown 报告；
- 自动生成 PDF 报告；
- 支持公开部署到 Streamlit Community Cloud；
- 支持通义千问、豆包、OpenAI 以及其他 OpenAI-compatible API。

## 2. 项目结构

```text
problem-optimizer-agent/
├── app.py                         # Streamlit 主程序
├── llm_client.py                  # 大模型 API 调用封装
├── prompt_templates.py            # 提示词工程模板
├── pdf_generator.py               # PDF 生成工具
├── utils.py                       # 轻量问题评分工具、示例报告
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

浏览器会自动打开本地页面。

## 4. 无 API Key 测试

如果还没有配置 API Key，可以在侧边栏勾选：

```text
示例模式（不调用 API）
```

示例模式不会调用真实大模型，但可以测试网页交互、问题评分和 PDF 下载功能。

## 5. 部署到 Streamlit Community Cloud

1. 将本项目上传到 GitHub；
2. 确认 `.streamlit/secrets.toml` 没有上传；
3. 登录 Streamlit Community Cloud；
4. 选择 GitHub 仓库；
5. 入口文件选择 `app.py`；
6. 在 App 的 Secrets 中填写：

```toml
[api]
provider = "阿里云百炼 / Qwen"
base_url = "https://llm-dks5jdo39k1dk6wb.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
model = "qwen-flash"
api_key = "你的真实 API Key"
```

7. 点击 Deploy；
8. 部署完成后获得公开访问链接。

## 6. 推荐演示问题

```text
我想做一个校园二手交易平台，应该怎么做？
```

或：

```text
我想做一个在线学习 App，帮我设计一下。
```

## 7. 作业提交建议

最终提交：

```text
1. Streamlit 公开访问链接
2. 智能体求解过程 MP4 视频
3. 智能体生成的 PDF 报告
```

录屏建议流程：

1. 打开公开访问链接；
2. 输入演示问题；
3. 点击“开始优化并生成报告”；
4. 展示问题诊断、优化后的问题、子问题拆解和解决方案；
5. 下载 PDF；
6. 打开 PDF 展示内容。

## 8. 说明：什么是“训练”

本项目中的“训练”不是训练或微调大模型参数，而是：

```text
提示词工程训练 = 角色提示词 + 流程提示词 + 输出模板 + 测试样例 + 迭代优化
```

系统通过多轮测试不断改进提示词，使智能体稳定执行：

```text
问题诊断 → 问题优化 → 子问题拆解 → 方案生成 → 自我检查 → PDF 报告生成
```

## 9. 可以继续扩展的功能

- 加入联网搜索工具；
- 加入用户登录和调用次数限制；
- 加入历史报告保存；
- 加入不同领域的专用提示词模板；
- 接入数据库保存训练记录；
- 支持 DOCX 导出。
