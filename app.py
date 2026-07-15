#!/usr/bin/env python3
"""
PPT Generator — Web Admin Backend
Flask API for project management, prompt editing, and generation.
"""

import asyncio
import hashlib
import json
import os
import random
import re
import secrets
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

# Auth config
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin888")
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
TOKEN_EXPIRE = 86400  # 24 hours

# In-memory stores
gen_status = {}       # {project_id: {"status": "running|done|error", ...}}
auth_tokens = {}      # {token: {"user": str, "created": float}}
captcha_store = {}    # {captcha_id: {"answer": str, "created": float}}

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


def create_history_snapshot(pid: str, project: dict, note: str = ""):
    """Create a history snapshot of current slides."""
    if "history" not in project:
        project["history"] = []

    version = len(project["history"]) + 1
    snapshot = {
        "version": version,
        "timestamp": datetime.now().isoformat(),
        "slides": project.get("slides", []),
        "note": note
    }
    project["history"].append(snapshot)


def list_projects() -> list[dict]:
    results = []
    for d in sorted(PROJECTS_DIR.iterdir()):
        if d.is_dir():
            pj = load_project(d.name)
            if pj:
                results.append({
                    "id": d.name,
                    **{k: pj[k] for k in ["topic", "brief", "audience", "created_at", "updated_at"] if k in pj},
                    "slides_count": len(pj.get("slides", []))
                })
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


# ── Auth: Captcha + Login + Middleware ────────────────────

def _generate_captcha_image():
    """Generate a math captcha image, return (captcha_id, image_bytes)."""
    from PIL import Image, ImageDraw, ImageFont
    import io, string

    # Math expression
    ops = ["+", "-", "×"]
    op = random.choice(ops)
    if op == "×":
        a, b = random.randint(2, 9), random.randint(2, 9)
        answer = a * b
    elif op == "-":
        a, b = random.randint(10, 50), random.randint(1, 9)
        answer = a - b
    else:
        a, b = random.randint(5, 40), random.randint(5, 40)
        answer = a + b

    text = f"{a} {op} {b} = ?"

    # Draw image
    w, h = 140, 46
    img = Image.new("RGB", (w, h), "#f0f0f5")
    draw = ImageDraw.Draw(img)

    # Noise lines
    for _ in range(4):
        x1, y1 = random.randint(0, w), random.randint(0, h)
        x2, y2 = random.randint(0, w), random.randint(0, h)
        color = f"#{random.randint(0xa0,0xcc):02x}{random.randint(0xa0,0xcc):02x}{random.randint(0xa0,0xcc):02x}"
        draw.line([(x1, y1), (x2, y2)], fill=color, width=1)

    # Noise dots
    for _ in range(30):
        draw.point((random.randint(0, w), random.randint(0, h)),
                   fill=f"#{random.randint(0x80,0xbb):02x}{random.randint(0x80,0xbb):02x}{random.randint(0x80,0xbb):02x}")

    # Text
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
    except Exception:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        except Exception:
            font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (w - tw) // 2 + random.randint(-3, 3)
    y = (h - th) // 2 + random.randint(-2, 2)

    # Draw each char with slight color variation
    cx = x
    for ch in text:
        r = random.randint(0x20, 0x50)
        g = random.randint(0x20, 0x50)
        b = random.randint(0x60, 0x90)
        draw.text((cx, y), ch, fill=f"#{r:02x}{g:02x}{b:02x}", font=font)
        cx += random.randint(14, 19)

    buf = io.BytesIO()
    img.save(buf, format="PNG")

    captcha_id = secrets.token_hex(8)
    captcha_store[captcha_id] = {"answer": str(answer), "created": time.time()}

    # Cleanup old captchas (>10min)
    expired = [k for k, v in captcha_store.items() if time.time() - v["created"] > 600]
    for k in expired:
        del captcha_store[k]

    return captcha_id, buf.getvalue()


@app.route("/api/captcha")
def api_captcha():
    captcha_id, img_bytes = _generate_captcha_image()
    from flask import Response
    return Response(
        json.dumps({"captcha_id": captcha_id}),
        mimetype="application/json",
        headers={"X-Captcha-Image": __import__('base64').b64encode(img_bytes).decode()}
    )


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.json or {}
    username = data.get("username", "")
    password = data.get("password", "")
    captcha_id = data.get("captcha_id", "")
    captcha_code = data.get("captcha_code", "")

    # Validate captcha
    cap = captcha_store.pop(captcha_id, None)
    if not cap:
        return jsonify({"error": "验证码已过期，请刷新"}), 400
    if cap["answer"] != captcha_code.strip():
        return jsonify({"error": "验证码错误"}), 400

    # Validate credentials
    if username != ADMIN_USER or password != ADMIN_PASS:
        return jsonify({"error": "用户名或密码错误"}), 401

    # Generate token
    token = secrets.token_hex(32)
    auth_tokens[token] = {"user": username, "created": time.time()}

    # Cleanup expired tokens
    expired = [k for k, v in auth_tokens.items() if time.time() - v["created"] > TOKEN_EXPIRE]
    for k in expired:
        del auth_tokens[k]

    return jsonify({"token": token, "user": username})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    auth_tokens.pop(token, None)
    return jsonify({"ok": True})


@app.route("/api/check-auth")
def api_check_auth():
    """Check if current token is valid (for frontend init)."""
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    if token in auth_tokens:
        info = auth_tokens[token]
        if time.time() - info["created"] < TOKEN_EXPIRE:
            return jsonify({"ok": True, "user": info["user"]})
    return jsonify({"ok": False}), 401


# Routes that don't require auth
PUBLIC_ROUTES = {
    "/", "/api/login", "/api/captcha", "/api/check-auth",
    "/api/share-info",
}
PUBLIC_PREFIXES = ("/css/", "/js/", "/share/", "/api/temp/")


@app.before_request
def require_auth():
    path = request.path

    # Allow public routes
    if path in PUBLIC_ROUTES:
        return None
    for prefix in PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return None

    # Allow output file downloads (for sharing)
    if path.startswith("/api/projects/") and "/output/" in path:
        return None

    # OPTIONS preflight
    if request.method == "OPTIONS":
        return None

    # Check token
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    if token in auth_tokens:
        info = auth_tokens[token]
        if time.time() - info["created"] < TOKEN_EXPIRE:
            return None

    return jsonify({"error": "未登录", "code": "AUTH_REQUIRED"}), 401


# ── API Routes ────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("admin-html", "index.html")


@app.route("/css/<path:filename>")
def serve_css(filename):
    return send_from_directory("admin-html/css", filename)


@app.route("/js/<path:filename>")
def serve_js(filename):
    return send_from_directory("admin-html/js", filename)


@app.route("/api/temp/<temp_dir>/<path:filename>")
def serve_temp_file(temp_dir, filename):
    """Serve temporary preview files."""
    import tempfile
    temp_base = Path(tempfile.gettempdir())
    temp_path = temp_base / temp_dir / filename

    # Security check: ensure path is within temp directory
    if not str(temp_path.resolve()).startswith(str(temp_base.resolve())):
        return jsonify({"error": "invalid path"}), 403

    if not temp_path.exists():
        return jsonify({"error": "not found"}), 404

    return send_from_directory(str(temp_path.parent), temp_path.name)


@app.route("/share/<pid>/<filename>")
def share_output(pid, filename):
    """Clean URL for sharing presentations."""
    out_dir = PROJECTS_DIR / pid / "output"
    if not (out_dir / filename).exists():
        return "File not found", 404
    return send_from_directory(str(out_dir), filename)


@app.route("/api/share-info")
def api_share_info():
    """Return local network IP and port for QR code."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"
    port = request.environ.get("SERVER_PORT", "8080")
    return jsonify({"ip": ip, "port": port, "base_url": f"http://{ip}:{port}"})


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


@app.route("/api/projects/<pid>", methods=["DELETE"])
def api_delete_project(pid):
    project_dir = PROJECTS_DIR / pid
    if not project_dir.exists():
        return jsonify({"error": "not found"}), 404

    # Delete project directory
    import shutil
    shutil.rmtree(project_dir)

    # Clean up gen_status if exists
    if pid in gen_status:
        del gen_status[pid]

    return jsonify({"ok": True})


@app.route("/api/projects/<pid>/slides", methods=["PUT"])
def api_update_slides(pid):
    project = load_project(pid)
    if not project:
        return jsonify({"error": "not found"}), 404
    slides = request.json
    if isinstance(slides, list):
        # Create history snapshot before updating
        create_history_snapshot(pid, project, "编辑幻灯片")

        project["slides"] = slides
        project["updated_at"] = datetime.now().isoformat()
        save_project(pid, project)
        return jsonify({"ok": True, "count": len(slides)})
    return jsonify({"error": "expected array"}), 400


@app.route("/api/projects/<pid>/history", methods=["GET"])
def api_get_history(pid):
    """Get version history for a project."""
    project = load_project(pid)
    if not project:
        return jsonify({"error": "not found"}), 404

    history = project.get("history", [])
    return jsonify(history)


@app.route("/api/projects/<pid>/rollback/<int:version>", methods=["POST"])
def api_rollback(pid, version):
    """Rollback to a specific version."""
    project = load_project(pid)
    if not project:
        return jsonify({"error": "not found"}), 404

    history = project.get("history", [])
    target = next((h for h in history if h["version"] == version), None)

    if not target:
        return jsonify({"error": "version not found"}), 404

    # Create snapshot of current state before rollback
    create_history_snapshot(pid, project, f"回滚到版本 {version}")

    # Restore slides from target version
    project["slides"] = target["slides"]
    project["updated_at"] = datetime.now().isoformat()
    save_project(pid, project)

    return jsonify({"ok": True, "restored_version": version})


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


@app.route("/api/projects/<pid>/preview", methods=["POST"])
def api_preview(pid):
    """Generate a preview HTML/PPTX from current slides data."""
    project = load_project(pid)
    if not project:
        return jsonify({"error": "not found"}), 404

    slides = project.get("slides", [])
    if not slides:
        return jsonify({"error": "no slides"}), 400

    # Get format from request
    params = request.json or {}
    fmt = params.get("format", "html")  # html, pptx, or both

    # Create temp directory for preview
    import tempfile
    import shutil
    temp_dir = Path(tempfile.mkdtemp(prefix=f"preview_{pid}_"))

    outputs = []

    try:
        # Generate HTML preview
        if fmt in ("html", "both"):
            from html_renderer import HTMLRenderer
            html_renderer = HTMLRenderer()
            palette = project.get("plan", {}).get("palette", "tech")
            html_file = temp_dir / "preview.html"
            html_renderer.render(slides, palette, project.get("topic", "Preview"), html_file)
            outputs.append({
                "type": "html",
                "name": "preview.html",
                "url": f"/api/temp/{temp_dir.name}/preview.html"
            })

        # Generate PPTX preview
        if fmt in ("pptx", "both"):
            from renderer import Renderer
            pptx_renderer = Renderer()
            palette = project.get("plan", {}).get("palette", "tech")
            pptx_file = temp_dir / "preview.pptx"
            pptx_renderer.render(slides, palette, project.get("topic", "Preview"), pptx_file)
            outputs.append({
                "type": "pptx",
                "name": "preview.pptx",
                "url": f"/api/temp/{temp_dir.name}/preview.pptx"
            })

        return jsonify({"ok": True, "outputs": outputs})

    except Exception as e:
        # Clean up on error
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({"error": str(e)}), 500


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


@app.route("/api/config/footer")
def api_footer_config():
    """Get footer configuration."""
    footer_path = Path("config/footer.json")
    if not footer_path.exists():
        return jsonify({"error": "not found"}), 404

    with open(footer_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    return jsonify(config)


@app.route("/api/config/modals")
def api_modals_config():
    """Get modals configuration."""
    modals_path = Path("config/modals.json")
    if not modals_path.exists():
        return jsonify({"error": "not found"}), 404

    with open(modals_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    return jsonify(config)


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
    import argparse
    parser = argparse.ArgumentParser(description="PPT Generator Admin")
    parser.add_argument("--port", type=int, default=int(os.environ.get("FLASK_PORT", 8080)))
    args = parser.parse_args()
    port = args.port

    print("\n🖥️  PPT Generator Admin")
    print(f"📂 项目目录: {PROJECTS_DIR.resolve()}")
    print(f"🌐 访问: http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
