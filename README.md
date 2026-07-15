# PPT Generator

输入一个 JSON，输出一套 25-30 张的 .pptx 文件。

## 快速开始

```bash
# 1. 安装依赖
uv venv .venv && source .venv/bin/activate
uv pip install -r requirements.txt

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 3. 运行
python main.py test_input.json
# 输出: output/Python_入门_30_分钟.pptx
```

## 用法

```bash
# 基本用法
python main.py input.json

# 指定输出路径
python main.py input.json -o my_presentation.pptx

# 强制指定调色板
python main.py input.json -p corporate

# 调整并发数（默认5）
python main.py input.json -c 10
```

## 输入格式

```json
{
  "topic": "主题",
  "brief": "简介（≤500字）",
  "audience": "目标受众"
}
```

## 架构

三阶段流水线：

1. **Planner** (DeepSeek) — 生成25-30张的叙事规划（三幕结构、布局分配、配色选择）
2. **Writer** (DeepSeek × N 并行) — 逐张生成slide内容，每张知道前后上下文
3. **Renderer** (纯代码) — 结构化数据 → python-pptx，应用设计系统

## 模型切换

在 `.env` 中修改：

```bash
# DeepSeek（默认）
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# 千问（DashScope OpenAI兼容接口）
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DEEPSEEK_MODEL=qwen-plus

# OpenAI
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.openai.com/v1
DEEPSEEK_MODEL=gpt-4o
```

## 设计系统

- **8种布局**: title / section / bullets / statement / comparison / big_number / code / end
- **5套调色板**: tech / warm / corporate / personal / dark
- **字体**: Microsoft YaHei（中文）/ Impact（大数字）/ Consolas（代码）

## 项目结构

```
ppt-generator/
├── main.py          # CLI入口 + 叙事规划 + 内容生成
├── llm.py           # DeepSeek异步客户端
├── renderer.py      # PPTX渲染引擎
├── requirements.txt
├── .env.example
└── test_input.json
```
