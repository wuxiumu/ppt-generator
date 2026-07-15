#!/usr/bin/env python3
"""
PPT Generator — Web Admin Backend
Flask API for project management, prompt editing, and generation.
"""

import asyncio
import json
import os
import re
import uuid
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, send_file, send_from_directory
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder=".", static_url_path="")

# ── Config ────────────────────────────────────────────────
PROJECTS_DIR = Path("projects")
OUTPUT_DIR = Path("output")
PROJECTS_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Generation state (for polling)
gen_status = {}  # {project_id: {"status": "running|done|error", "progress": "", "outputs": []}}

# ── Default Prompts (extracted from main.py) ─────────────

DEFAULT_PLANNER_SYSTEM = "你是PPT叙事架构师。你为25-30张幻灯片的演示文稿设计完整的叙事结构。输出纯JSON，不要markdown包裹。"

DEFAULT_PLANNER_PROMPT = """为以下主题设计一套25-30张幻灯片的PPT叙事规划。

## 输入
- 主题: {topic}
- 简介: {brief}
- 受众: {audience}

## 三幕结构要求
- Act 1 开场 (4-5张, ~15%): 封面(title)、钩子(statement)、共鸣(bullets)、路线图(bullets)
- Act 2 主体 (17-20张, ~65%): 3-4个子章节，每个: section → 展开 → 细节
- Act 3 收尾 (4-5张, ~15%): 回顾(bullets)、行动(bullets)、金句(statement)、结束(end)

## 布局类型 (8种)
title / section / bullets / statement / comparison / big_number / code / end

## 调色板 (5种)
tech(紫蓝) / warm(暖棕) / corporate(商务蓝) / personal(薰衣草紫) / dark(深色)

## 布局节奏规则
- 连续不超过2张相同布局
- 每3-4张出现一次视觉重的布局（statement/comparison/big_number）

## 输出JSON
{{
  "palette": "调色板名",
  "tone": "语气描述",
  "slide_plan": [
    {{"n": 1, "act": 1, "role": "角色", "layout": "布局", "brief": "50-100字内容要求", "transition": "过渡说明"}}
  ]
}}"""

DEFAULT_WRITER_SYSTEM = "你是PPT内容撰稿人。为单张幻灯片撰写精炼的内容。输出纯JSON，不要markdown包裹。"

DEFAULT_WRITER_PROMPT = """为第 {num} 张幻灯片撰写内容。

## 当前slide
- 编号: {num} / {total}
- 叙事角色: {role}
- 布局类型: {layout}
- 内容要求: {brief}
- 过渡: {transition}

## 上下文
- 前一张: {prev}
- 后一张: {next}

## 风格
- 语气: {tone}

## 输出JSON
{{
  "title": "标题(≤15字)",
  "subtitle": "副标题(可选)",
  "bullets": ["要点1", ...],
  "body_text": "正文(≤80字)",
  "highlight": "关键数字(仅big_number)",
  "left_title": "左栏标题(仅comparison)",
  "right_title": "右栏标题(仅comparison)",
  "left_bullets": ["左栏要点", ...],
  "right_bullets": ["右栏要点", ...],
  "code": "代码(仅code布局)",
  "annotations": ["注释", ...],
  "act": {act},
  "speaker_notes": "演讲备注"
}}"""

# ── Provider Config ───────────────────────────────────────
PROVIDERS = {
    "deepseek": {"sdk": "openai", "default_url": "https://api.deepseek.com", "default_model": "deepseek-chat", "env_prefix": "DEEPSEEK"},
    "qwen": {"sdk": "anthropic", "default_url": "https://coding.dashscope.aliyuncs.com/apps/anthropic", "default_model": "qwen3.7-plus", "env_prefix": "QWEN"},
    "openai": {"sdk": "openai", "default_url": "https://api.openai.com/v1", "default_model": "gpt-4o", "env_prefix": "OPENAI"},
}


# ── Helper Functions ──────────────────────────────────────

def load_project(pid: str) -> dict | None:
    path = PROJECTS_DIR / pid / "project.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_project(pid: str, data: dict):
    path = PROJECTS_DIR / pid / "project.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def list_projects() -> list[dict]:
    results = []
    for d in sorted(PROJECTS_DIR.iterdir()):
        if d.is_dir():
            pj = load_project(d.name)
            if pj:
                results.append({"id": d.name, **{k: pj[k] for k in ["topic", "brief", "audience", "created_at", "updated_at"] if k in pj}})
    return results


def list_outputs(pid: str) -> list[dict]:
    out_dir = PROJECTS_DIR / pid / "output"
    if not out_dir.exists():
        return []
    files = []
    for f in sorted(out_dir.iterdir(), reverse=True):
        if f.suffix in (".html", ".pptx"):
            files.append({"name": f.name, "ext": f.suffix, "size_kb": round(f.stat().st_size / 1024, 1), "created": datetime.fromtimestamp(f.stat().st_mtime).strftime("%m-%d %H:%M")})
    return files


# ── API Routes ────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(".", "admin.html")


@app.route("/api/projects", methods=["GET"])
def api_list_projects():
    return jsonify(list_projects())


@app.route("/api/projects", methods=["POST"])
def api_create_project():
    data = request.json or {}
    pid = uuid.uuid4().hex[:8]
    project = {
        "topic": data.get("topic", "新主题"),
        "brief": data.get("brief", ""),
        "audience": data.get("audience", "通用"),
        "planner_system": DEFAULT_PLANNER_SYSTEM,
        "planner_prompt": DEFAULT_PLANNER_PROMPT,
        "writer_system": DEFAULT_WRITER_SYSTEM,
        "writer_prompt": DEFAULT_WRITER_PROMPT,
        "slides": [],
        "plan": {},
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    save_project(pid, project)
    return jsonify({"id": pid, **project})


@app.route("/api/projects/<pid>", methods=["GET"])
def api_get_project(pid):
    project = load_project(pid)
    if not project:
        return jsonify({"error": "not found"}), 404
    project["id"] = pid
    project["outputs"] = list_outputs(pid)
    return jsonify(project)


@app.route("/api/projects/<pid>", methods=["PUT"])
def api_update_project(pid):
    project = load_project(pid)
    if not project:
        return jsonify({"error": "not found"}), 404
    data = request.json or {}
    for key in ["topic", "brief", "audience", "planner_system", "planner_prompt", "writer_system", "writer_prompt"]:
        if key in data:
            project[key] = data[key]
    project["updated_at"] = datetime.now().isoformat()
    save_project(pid, project)
    return jsonify({"ok": True})


@app.route("/api/projects/<pid>/slides", methods=["PUT"])
def api_update_slides(pid):
    project = load_project(pid)
    if not project:
        return jsonify({"error": "not found"}), 404
    slides = request.json
    if isinstance(slides, list):
        project["slides"] = slides
        project["updated_at"] = datetime.now().isoformat()
        save_project(pid, project)
        return jsonify({"ok": True, "count": len(slides)})
    return jsonify({"error": "expected array"}), 400


@app.route("/api/projects/<pid>/generate", methods=["POST"])
def api_generate(pid):
    project = load_project(pid)
    if not project:
        return jsonify({"error": "not found"}), 404

    params = request.json or {}
    provider = params.get("provider", "deepseek")
    fmt = params.get("format", "both")

    # Start generation in background thread
    gen_status[pid] = {"status": "running", "progress": "初始化...", "outputs": [], "started": time.time()}
    thread = threading.Thread(target=_run_generate, args=(pid, project.copy(), provider, fmt))
    thread.daemon = True
    thread.start()

    return jsonify({"ok": True, "status": "started"})


@app.route("/api/projects/<pid>/status", methods=["GET"])
def api_status(pid):
    status = gen_status.get(pid, {"status": "idle", "progress": "", "outputs": []})
    return jsonify(status)


@app.route("/api/projects/<pid>/output/<filename>")
def api_serve_output(pid, filename):
    out_dir = PROJECTS_DIR / pid / "output"
    if not (out_dir / filename).exists():
        return jsonify({"error": "not found"}), 404
    return send_from_directory(str(out_dir), filename)


@app.route("/api/projects/<pid>/plan", methods=["PUT"])
def api_update_plan(pid):
    project = load_project(pid)
    if not project:
        return jsonify({"error": "not found"}), 404
    project["plan"] = request.json or {}
    project["updated_at"] = datetime.now().isoformat()
    save_project(pid, project)
    return jsonify({"ok": True})


@app.route("/api/prompts/default")
def api_default_prompts():
    return jsonify({
        "planner_system": DEFAULT_PLANNER_SYSTEM,
        "planner_prompt": DEFAULT_PLANNER_PROMPT,
        "writer_system": DEFAULT_WRITER_SYSTEM,
        "writer_prompt": DEFAULT_WRITER_PROMPT,
    })


@app.route("/api/providers")
def api_providers():
    result = {}
    for name, cfg in PROVIDERS.items():
        prefix = cfg["env_prefix"]
        has_key = bool(os.getenv(f"{prefix}_API_KEY") or os.getenv("DEEPSEEK_API_KEY"))
        result[name] = {"model": os.getenv(f"{prefix}_MODEL", cfg["default_model"]), "available": has_key}
    return jsonify(result)


# ── Generation Logic ──────────────────────────────────────

def _run_generate(pid: str, project: dict, provider: str, fmt: str):
    """Run generation in background thread."""
    try:
        from llm import LLMClient
        from renderer import Renderer
        from html_renderer import HTMLRenderer

        s = gen_status[pid]

        # Setup LLM
        prov = PROVIDERS.get(provider, PROVIDERS["deepseek"])
        prefix = prov["env_prefix"]
        api_key = os.getenv(f"{prefix}_API_KEY") or os.getenv("DEEPSEEK_API_KEY", "")
        base_url = os.getenv(f"{prefix}_BASE_URL", prov["default_url"])
        model = os.getenv(f"{prefix}_MODEL", prov["default_model"])

        if not api_key:
            s["status"] = "error"
            s["progress"] = f"未配置 {prefix}_API_KEY"
            return

        llm = LLMClient(provider=prov["sdk"], api_key=api_key, base_url=base_url, model=model)

        # Use asyncio in thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        s["progress"] = "Stage 1: 叙事规划中..."

        # Stage 1: Plan
        from main import plan as plan_fn, fix_layout_rhythm, parse_json
        plan_data = loop.run_until_complete(plan_fn(llm, project))
        palette = plan_data.get("palette", "tech")
        fixes = fix_layout_rhythm(plan_data.get("slide_plan", []))
        if fixes:
            s["progress"] = f"规划完成({len(plan_data['slide_plan'])}张), 修复了{fixes}处布局..."
        else:
            s["progress"] = f"规划完成({len(plan_data['slide_plan'])}张)..."

        # Save plan
        project["plan"] = plan_data
        save_project(pid, project)

        # Stage 2: Write
        s["progress"] = "Stage 2: 内容生成中..."
        from main import write_all
        contents = loop.run_until_complete(write_all(llm, plan_data, concurrency=5))

        # Save slides
        project["slides"] = contents
        save_project(pid, project)

        s["progress"] = f"内容完成({len(contents)}张), 渲染中..."

        # Stage 3: Render
        out_dir = PROJECTS_DIR / pid / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%m%d_%H%M")
        model_tag = re.sub(r'[/\\.]', '-', model).split('-')[-1][:12]
        base = str(out_dir / f"slides_{model_tag}_{ts}")
        outputs = []

        if fmt in ("pptx", "both"):
            pptx_path = f"{base}.pptx"
            Renderer().render(contents, palette, topic=project["topic"], out=pptx_path)
            outputs.append(os.path.basename(pptx_path))

        if fmt in ("html", "both"):
            html_path = f"{base}.html"
            HTMLRenderer().render(contents, palette, topic=project["topic"], out=html_path)
            outputs.append(os.path.basename(html_path))

        elapsed = time.time() - s["started"]
        cost = llm.get_cost_estimate()

        s["status"] = "done"
        s["progress"] = f"完成! {len(contents)}张, {elapsed:.1f}s, ${cost:.4f}"
        s["outputs"] = outputs
        s["elapsed"] = round(elapsed, 1)
        s["cost"] = round(cost, 4)
        s["slide_count"] = len(contents)
        s["tokens"] = {"in": llm.total_input_tokens, "out": llm.total_output_tokens}

    except Exception as e:
        gen_status[pid]["status"] = "error"
        gen_status[pid]["progress"] = f"错误: {str(e)[:200]}"


# ── Run ───────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n🖥️  PPT Generator Admin")
    print(f"📂 项目目录: {PROJECTS_DIR.resolve()}")
    print(f"🌐 访问: http://localhost:8080\n")
    app.run(host="0.0.0.0", port=8080, debug=False)
