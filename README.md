# PPT Generator — 一套生成器

> 输入一个 JSON，输出一套 25-30 张风格统一、叙事连贯的 .pptx / .html 演示文稿。

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/wuxiumu/ppt-generator.git
cd ppt-generator

# 2. 安装依赖（推荐 uv）
uv venv .venv && source .venv/bin/activate
uv pip install -r requirements.txt
# 或: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# 3. 配置 API Key（.env 不会被提交）
cp .env.example .env
# 编辑 .env，填入 DeepSeek API Key
# 复制后的后台密码是 change-me-before-demo，对外演示前请修改
# 只有不设置 ADMIN_PASS 时才会回退到 admin / admin888

# 4. 先做离线检查（不需要 API Key，写出 4 张预览）
python main.py samples/client-brief.json --dry-run
# 预览文件: output/sample-preview.pptx

# 5a. CLI 正式生成（约 25–30 张，需要上一步填好的 Key）
python main.py samples/client-brief.json
# 开发集示例: python main.py inputs/01-python-beginner.json

# 5b. Web 管理后台 — 可视化编辑 + 生成 + 扫码分享
python app.py
# 浏览器打开 http://localhost:8080
```

## 买家演示

给客户看路径时，用咨询入职培训这套简报，不必先讲开发集：

```bash
python main.py samples/client-brief.json --dry-run   # 检查输入，写出 4 张预览
python main.py samples/client-brief.json             # 正式生成 25–30 张
```

| 步骤 | 路径 |
|------|------|
| 输入 | `samples/client-brief.json`（`topic` / `brief` / `audience`） |
| 离线预览 | `output/sample-preview.pptx`（4 张，不调用模型） |
| 正式输出 | `output/<主题>_<模型>_<月日_时分>.pptx` 与同名 `.html` |

输入缺字段、文件不是 JSON，或 `.env` 里仍是空的 / 模板占位符时，命令会说明缺什么，并给出下一条可复制的命令。Web 后台在同样情况下会把进度停在「还不能生成」或「生成没有完成」，而不是只丢一段栈信息。

对外打开后台前，把 `.env` 里的 `ADMIN_USER` / `ADMIN_PASS` 改掉。未配置时内置账号是 `admin` / `admin888`。

## 架构

```
JSON 输入 (topic + brief + audience)
  │
  ▼
┌─────────────────────────────┐
│  Stage 1: Planner           │  ← 强模型（DeepSeek / GPT-4o / Claude）
│  叙事规划：三幕结构 + 布局    │     只调用 1 次，~3000 tokens
│  分配 + 配色选择             │
└────────────┬────────────────┘
             ▼
┌─────────────────────────────┐
│  Stage 2: Writer (×N 并行)   │  ← 同一模型，每张 slide 一次调用
│  逐张生成内容，带上下文       │     5 并发，共 25-30 次
└────────────┬────────────────┘
             ▼
┌─────────────────────────────┐
│  Stage 3: Renderer           │  ← 纯代码，0 LLM 调用
│  结构化数据 → PPTX / HTML    │     确定性渲染，8 种布局
└────────────┬────────────────┘
             ▼
     .pptx / .html
```

**核心设计**：LLM 只负责内容，不碰视觉参数。所有样式由渲染引擎硬编码，保证 100% 视觉一致性。

## 特性

**叙事连贯性** — 25-30 张幻灯片遵循三幕结构（开场 15% / 主体 65% / 收尾 15%），Planner 自动从 5 种叙事模板（教程 / 时间线 / 指南 / 提案 / 行程）中选择最匹配的类型。

**8 种布局 × 5 套调色板** — title / section / bullets / statement / comparison / big_number / code / end，配合 tech / warm / corporate / personal / dark 五套调色板，由 Planner 根据主题自动选择。

**双输出格式** — PPTX（PowerPoint/Keynote 兼容）和 HTML（CSS 渐变 + 毛玻璃 + 滚动吸附翻页 + 键盘导航 + 二维码分享）。

**Web 管理后台** — 小白友好的可视化管理界面：项目管理 / 提示词编辑 / 幻灯片编辑 / 一键生成 / 输出预览 / 扫码分享。

**多模型** — 通过 `--provider` 切换 DeepSeek / 千问 / OpenAI，同一套代码零改动。

## 5 套 Demo 实测数据

| # | 主题 | 张数 | 调色板 | 耗时 | 成本 |
|---|------|------|--------|------|------|
| 1 | Python 入门 30 分钟 | 29 | tech | 30.6s | $0.012 |
| 2 | 2025 我的年度复盘 | 28 | personal | 29.2s | $0.012 |
| 3 | 如何挑选咖啡豆 | 26 | warm | 25.7s | $0.011 |
| 4 | Rust 重写订单系统 | 27 | corporate | 30.4s | $0.012 |
| 5 | 周末两天玩遍京都 | 25 | warm | 33.3s | $0.012 |

> **5 套总成本 $0.059**，平均 30 秒一套。

## CLI 用法

```bash
python main.py samples/client-brief.json --dry-run          # 离线检查 + 4 张预览
python main.py samples/client-brief.json                    # 默认 DeepSeek + PPTX+HTML
python main.py samples/client-brief.json --provider qwen -f html   # 千问 + 仅 HTML
python main.py samples/client-brief.json --provider openai -f pptx # OpenAI + 仅 PPTX
python main.py samples/client-brief.json -p corporate       # 强制商务蓝调色板
python main.py samples/client-brief.json -c 10              # 10 并发
```

## Web 管理后台

```bash
python app.py  # → http://localhost:8080
```

- **📝 基本信息**：编辑主题、简介、受众
- **🤖 提示词**：自定义 Planner/Writer prompt，一键恢复默认
- **🎴 幻灯片**：逐张查看和编辑生成的内容
- **🚀 生成**：选模型 + 格式，实时进度，~30秒完成
- **📁 输出文件**：HTML 预览 + PPTX 下载 + 📤 扫码分享

## 项目结构

```
ppt-generator/
├── main.py              # CLI 入口（含 --dry-run）
├── app.py               # Web 管理后台 (Flask API)
├── admin-html/          # 管理面板
├── llm.py               # LLM 客户端 (OpenAI + Anthropic)
├── renderer.py          # PPTX 渲染引擎
├── html_renderer.py     # HTML 渲染引擎
├── init_demos.py        # 初始化 5 个 demo
├── requirements.txt     # 已钉死的直接依赖
├── .env.example         # API Key 模板（不含真实密钥）
├── DESIGN.md            # 决策日志
├── samples/             # 买家演示简报
│   └── client-brief.json
├── inputs/              # 5 个开发集 JSON
├── doc/                 # 设计文档 + Demo 输出
├── output/              # 生成结果（不入库）
└── projects/            # Web 后台数据（不入库）
```

## 部署

### 本地

```bash
git clone https://github.com/wuxiumu/ppt-generator.git && cd ppt-generator
uv venv .venv && source .venv/bin/activate && uv pip install -r requirements.txt
cp .env.example .env && vim .env  # 填入 API Key，并修改 ADMIN_PASS
python main.py samples/client-brief.json --dry-run
python app.py
```

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["python", "app.py"]
```

```bash
docker build -t ppt-generator .
docker run -p 8080:8080 --env-file .env ppt-generator
```

## 环境变量

复制 `.env.example` 后填写。仓库里只有占位模板，不要提交 `.env`。

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek Key | 正式生成必填；空值或模板占位符视为未配置 |
| `DEEPSEEK_BASE_URL` | 端点 | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 模型名 | `deepseek-chat` |
| `QWEN_API_KEY` | 千问 Key | 可选，`--provider qwen` |
| `QWEN_BASE_URL` | 千问端点 | DashScope Anthropic 兼容 |
| `QWEN_MODEL` | 千问模型 | `qwen3.7-plus` |
| `OPENAI_API_KEY` | OpenAI Key | 可选，`--provider openai` |
| `OPENAI_BASE_URL` | OpenAI 端点 | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | OpenAI 模型 | `gpt-4o` |
| `ADMIN_USER` | Web 后台账号 | `admin` |
| `ADMIN_PASS` | Web 后台密码 | `admin888`（对外演示前请修改） |
| `SECRET_KEY` | 会话签名 | 未设置时每次启动随机生成 |

## License

MIT
