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

# 3. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 DeepSeek API Key

# 4a. CLI 模式 — 一条命令生成
python main.py inputs/01-python-intro.json

# 4b. Web 管理后台 — 可视化编辑 + 生成 + 扫码分享
python app.py
# 浏览器打开 http://localhost:8080
```

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
python main.py input.json                          # 默认 DeepSeek + PPTX+HTML
python main.py input.json --provider qwen -f html  # 千问 + 仅HTML
python main.py input.json --provider openai -f pptx # OpenAI + 仅PPTX
python main.py input.json -p corporate              # 强制商务蓝调色板
python main.py input.json -c 10                     # 10并发
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
├── main.py              # CLI 入口
├── app.py               # Web 管理后台 (Flask API)
├── admin.html           # 管理面板 (单文件 SPA)
├── llm.py               # LLM 客户端 (OpenAI + Anthropic)
├── renderer.py          # PPTX 渲染引擎
├── html_renderer.py     # HTML 渲染引擎
├── init_demos.py        # 初始化 5 个 demo
├── requirements.txt
├── .env.example         # API Key 模板
├── DESIGN.md            # 决策日志
├── inputs/              # 5 个开发集 JSON
├── doc/                 # 设计文档 + Demo 输出
└── projects/            # Web 后台数据
```

## 部署

### 本地

```bash
git clone https://github.com/wuxiumu/ppt-generator.git && cd ppt-generator
uv venv .venv && source .venv/bin/activate && uv pip install -r requirements.txt
cp .env.example .env && vim .env  # 填入 API Key
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

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek Key | 必填 |
| `DEEPSEEK_BASE_URL` | 端点 | `https://api.deepseek.com` |
| `QWEN_API_KEY` | 千问 Key | 可选 |
| `QWEN_BASE_URL` | 千问端点 | DashScope Anthropic 兼容 |
| `OPENAI_API_KEY` | OpenAI Key | 可选 |

## License

MIT
