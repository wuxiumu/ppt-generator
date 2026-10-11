#!/usr/bin/env python3
"""
PPT Generator — JSON in, .pptx out.
Single command: python main.py input.json [-o output.pptx]
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime

try:
    from dotenv import load_dotenv
    from llm import LLMClient
    from renderer import PALETTES, Renderer
    from html_renderer import HTMLRenderer
except ImportError as exc:
    missing = getattr(exc, "name", None) or exc
    print("依赖还没装好，生成器无法启动。")
    print("  请在项目目录执行：")
    print("    python3 -m venv .venv && source .venv/bin/activate")
    print("    pip install -r requirements.txt")
    print(f"  缺少模块: {missing}")
    sys.exit(1)

SAMPLE_INPUT = "samples/client-brief.json"
SAMPLE_PREVIEW = "output/sample-preview.pptx"
REQUIRED_FIELDS = ("topic", "brief", "audience")
_PLACEHOLDER_MARKERS = ("your-key", "changeme", "replace-me", "sk-xxx")

# ── Provider configurations ───────────────────────────────

PROVIDERS = {
    "deepseek": {
        "sdk": "openai",
        "default_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "env_prefix": "DEEPSEEK",
    },
    "qwen": {
        "sdk": "anthropic",
        "default_url": "https://coding.dashscope.aliyuncs.com/apps/anthropic",
        "default_model": "qwen3.7-plus",
        "env_prefix": "QWEN",
    },
    "openai": {
        "sdk": "openai",
        "default_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "env_prefix": "OPENAI",
    },
}

# ── JSON parsing helper ───────────────────────────────────

def parse_json(text: str) -> dict:
    """Parse JSON from LLM output, handling markdown wrappers."""
    text = text.strip()
    # Strip ```json ... ```
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    return json.loads(text)


# ── Stage 1: Planner ──────────────────────────────────────

PLANNER_SYSTEM = """你是PPT叙事架构师。你为25-30张幻灯片的演示文稿设计完整的叙事结构。
输出纯JSON，不要markdown包裹。"""

PLANNER_PROMPT = """为以下主题设计一套25-30张幻灯片的PPT叙事规划。

## 输入
- 主题: {topic}
- 简介: {brief}
- 受众: {audience}

## 三幕结构要求
- **Act 1 开场 (4-5张, ~15%)**: 建立共鸣、抛出问题、预告方向
  - 必须包含: 封面(title)、钩子(statement/引发思考)、共鸣(bullets/场景代入)、路线图(bullets/概览)
- **Act 2 主体 (17-20张, ~65%)**: 核心内容，分3-4个子章节
  - 每个子章节: 章节分隔(section) → 展开(bullets/statement) → 细节(bullets/comparison/big_number)
  - 子章节之间有逻辑递进关系，难度递增
- **Act 3 收尾 (4-5张, ~15%)**: 总结升华、行动号召
  - 必须包含: 回顾(bullets)、进阶/行动(bullets)、金句(statement)、结束(end)

## 布局类型 (8种)
- title: 封面页（大标题+副标题）
- section: 章节分隔页（大色块背景+章节名+序号）
- bullets: 要点列表页（3-5个要点，最常用的布局）
- statement: 声明页（一句话居中，大字，用于金句/提问/观点）
- comparison: 对比页（左右两栏对比，需要left_title/right_title/left_bullets/right_bullets）
- big_number: 大数字页（关键数据突出显示，需要highlight字段）
- code: 代码展示页（代码+注释，技术主题使用）
- end: 结束页（感谢+联系方式）

## 调色板 (5种，根据主题选择)
- tech: 紫蓝调 → 技术/编程主题
- warm: 暖棕调 → 生活/咖啡/旅行
- corporate: 商务蓝 → 商务提案/工作汇报
- personal: 薰衣草紫 → 个人分享/年度复盘
- dark: 深色科技 → 前沿技术/深度分析

## 布局节奏规则
- 连续不超过2张相同布局
- 每3-4张出现一次视觉上"重"的布局（statement/comparison/big_number）
- section页间距不超过6张
- 前3张用不同布局（title → statement → bullets）

## 输出JSON格式（严格遵守）
{{
  "palette": "tech/warm/corporate/personal/dark",
  "tone": "描述整体语气，如：友好鼓励/专业严谨/轻松幽默",
  "slide_plan": [
    {{
      "n": 1,
      "act": 1,
      "role": "封面",
      "layout": "title",
      "brief": "50-100字的内容要求和方向描述",
      "transition": "从封面自然引向一个引发思考的问题"
    }},
    ...
  ]
}}

直接输出JSON，不要任何其他文字。"""


async def plan(llm: LLMClient, data: dict) -> dict:
    """Stage 1: Generate narrative plan."""
    prompt = PLANNER_PROMPT.format(
        topic=data["topic"], brief=data["brief"], audience=data["audience"]
    )
    raw = await llm.call(prompt, system=PLANNER_SYSTEM, temperature=0.8,
                         max_tokens=4096, json_mode=True)
    plan = parse_json(raw)
    # Validate slide count
    n = len(plan.get("slide_plan", []))
    if n < 25:
        print(f"  ⚠️  规划只有{n}张，要求LLM补充到25张...")
        supplement = (
            f"当前规划只有{n}张幻灯片，请补充到25张。保持三幕结构比例。"
            f"现有规划：{json.dumps(plan['slide_plan'], ensure_ascii=False)}\n"
            f"请输出完整的slide_plan数组（25张），JSON格式。"
        )
        raw2 = await llm.call(supplement, system=PLANNER_SYSTEM, temperature=0.7,
                              max_tokens=4096, json_mode=True)
        extra = parse_json(raw2)
        if isinstance(extra, dict) and "slide_plan" in extra:
            plan["slide_plan"] = extra["slide_plan"]
        elif isinstance(extra, list):
            plan["slide_plan"] = extra
    return plan


def fix_layout_rhythm(slides: list[dict]) -> int:
    """Fix consecutive same-layout violations (3+ in a row).
    Picks a replacement layout that avoids creating new violations.
    Returns the number of fixes applied."""
    fixes = 0
    consec = 1
    alt_pool = ["statement", "big_number", "bullets", "comparison"]
    for i in range(1, len(slides)):
        if slides[i].get("layout") == slides[i - 1].get("layout"):
            consec += 1
            if consec >= 3:
                old = slides[i]["layout"]
                # Pick an alternative different from prev and next
                prev_l = slides[i - 1].get("layout", "")
                next_l = slides[i + 1].get("layout", "") if i + 1 < len(slides) else ""
                chosen = ""
                for alt in alt_pool:
                    if alt != prev_l and alt != next_l and alt != old:
                        chosen = alt
                        break
                if not chosen:
                    chosen = "bullets"
                slides[i]["layout"] = chosen
                slides[i]["brief"] = (
                    f"（布局已从{old}改为{chosen}以避免视觉单调，请用{chosen}布局呈现内容）"
                    + slides[i].get("brief", "")
                )
                fixes += 1
                consec = 1  # reset after fix
        else:
            consec = 1
    return fixes


# ── Stage 2: Writer ───────────────────────────────────────

WRITER_SYSTEM = """你是PPT内容撰稿人。为单张幻灯片撰写精炼的内容。
输出纯JSON，不要markdown包裹。严格遵守字数限制。"""

WRITER_PROMPT = """为第 {num} 张幻灯片撰写内容。

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
- 语言: 中文
- 不使用emoji

## 输出JSON
{{
  "title": "标题(≤15字)",
  "subtitle": "副标题(可选，≤20字，无则空字符串)",
  "bullets": ["要点1", "要点2", ...],
  "body_text": "正文(≤80字，无则空字符串)",
  "highlight": "关键数字或短语(≤10字，仅big_number布局使用)",
  "left_title": "左栏标题(仅comparison)",
  "right_title": "右栏标题(仅comparison)",
  "left_bullets": ["左栏要点1", ...],
  "right_bullets": ["右栏要点1", ...],
  "code": "代码文本(仅code布局)",
  "annotations": ["注释1", ...],
  "act": {act},
  "speaker_notes": "演讲备注(30-60字)"
}}

## 约束
- 每张slide正文≤80字（标题+要点+正文的总和）
- 要点(bullets): 最多5个，每个≤25字
- comparison布局: 每侧最多4个要点
- statement布局: 只需title（那句核心话），bullets为空数组
- big_number布局: highlight必填，title是标签说明
- 要点之间要有逻辑递进，不要并列罗列同一层级的东西
- 直接输出JSON"""


async def write_slide(llm: LLMClient, spec: dict, ctx: dict, sem) -> dict:
    """Generate content for a single slide."""
    async with sem:
        prompt = WRITER_PROMPT.format(
            num=spec["n"],
            total=ctx["total"],
            role=spec.get("role", ""),
            layout=spec["layout"],
            brief=spec.get("brief", ""),
            transition=spec.get("transition", ""),
            prev=ctx.get("prev", "（无前一张）"),
            next=ctx.get("next", "（无后一张）"),
            tone=ctx["tone"],
            act=spec.get("act", 1),
        )
        raw = await llm.call(prompt, system=WRITER_SYSTEM, temperature=0.7,
                             max_tokens=1024, json_mode=True)
        try:
            content = parse_json(raw)
        except json.JSONDecodeError:
            print(f"  第 {spec['n']} 页返回的内容无法解析，已用简短占位继续。正式演示前建议重跑。")
            content = {
                "title": spec.get("brief", "")[:15],
                "bullets": ["内容生成中..."],
                "body_text": "",
                "act": spec.get("act", 1),
            }
        # Ensure layout is carried over
        content["layout"] = spec["layout"]
        content["slide_num"] = spec["n"]
        return content


async def write_all(llm: LLMClient, plan_data: dict, concurrency: int) -> list[dict]:
    """Stage 2: Generate all slide contents in parallel."""
    slides = plan_data["slide_plan"]
    tone = plan_data.get("tone", "专业且友好")
    sem = asyncio.Semaphore(concurrency)
    total = len(slides)

    tasks = []
    for i, spec in enumerate(slides):
        ctx = {
            "total": total,
            "tone": tone,
            "prev": slides[i - 1].get("brief", "") if i > 0 else "",
            "next": slides[i + 1].get("brief", "") if i < total - 1 else "",
        }
        tasks.append(write_slide(llm, spec, ctx, sem))

    return await asyncio.gather(*tasks)


# ── Validation ────────────────────────────────────────────

def validate(slides: list[dict]) -> list[str]:
    """Quick post-generation validation."""
    issues = []
    # Check consecutive same layouts
    consec = 0
    for i in range(1, len(slides)):
        if slides[i].get("layout") == slides[i - 1].get("layout"):
            consec += 1
            if consec >= 2:
                issues.append(
                    f"S{i + 1}: 连续{consec + 1}张 {slides[i].get('layout')} 布局"
                )
        else:
            consec = 0
    # Check empty titles
    for i, s in enumerate(slides):
        if not s.get("title", "").strip():
            issues.append(f"S{i + 1}: 标题为空")
    return issues


# ── Buyer-demo helpers ────────────────────────────────────

def fail(message: str, code: int = 1) -> None:
    """Print a short, actionable error and stop."""
    print(message)
    sys.exit(code)


def usable_api_key(*candidates: str | None) -> str:
    """Return the first real API key, ignoring blank and template placeholders."""
    for raw in candidates:
        key = (raw or "").strip()
        if not key:
            continue
        lowered = key.lower()
        if any(marker in lowered for marker in _PLACEHOLDER_MARKERS):
            continue
        return key
    return ""


def _short(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def load_brief(path: str) -> dict:
    """Load a buyer brief. Failures name the file and the next command to run."""
    if not os.path.isfile(path):
        fail(
            "找不到输入文件，这一轮还不能生成。\n"
            f"  路径: {path}\n"
            "  买家演示请用: python main.py samples/client-brief.json --dry-run\n"
            "  开发集示例: python main.py inputs/01-python-beginner.json"
        )
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        fail(
            "输入文件不是合法 JSON，这一轮还不能生成。\n"
            f"  文件: {path}\n"
            f"  位置: 第 {exc.lineno} 行，第 {exc.colno} 列\n"
            "  请对照 samples/client-brief.json，确认是一个包含 topic、brief、audience 的对象。"
        )
    except UnicodeDecodeError:
        fail(
            "输入文件编码无法读取。请保存为 UTF-8 JSON。\n"
            f"  文件: {path}\n"
            "  可参考: samples/client-brief.json"
        )
    if not isinstance(data, dict):
        fail(
            "输入 JSON 需要是对象，而不是数组或其他类型。\n"
            "  必填字段: topic、brief、audience\n"
            "  可参考: samples/client-brief.json"
        )
    missing = [key for key in REQUIRED_FIELDS if not str(data.get(key, "")).strip()]
    if missing:
        fail(
            "输入还不能用于生成，缺少必填字段: " + "、".join(missing) + "。\n"
            "  三个字段都需要非空文字。示例见 samples/client-brief.json"
        )
    return data


def preview_slides(data: dict) -> list[dict]:
    """Four local slides so a buyer can open a deck without an API key."""
    return [
        {
            "layout": "title",
            "title": _short(data["topic"], 18),
            "subtitle": "离线预览 · 正式生成会展开为 25–30 张",
        },
        {
            "layout": "bullets",
            "title": "这场培训要讲清什么",
            "bullets": [
                f"受众：{_short(data['audience'], 22)}",
                _short(data["brief"], 24),
                "正式生成会按三幕结构展开",
            ],
        },
        {
            "layout": "statement",
            "title": "这一页只证明版式可用",
            "subtitle": "不调用模型，也不消耗额度",
        },
        {
            "layout": "end",
            "title": "可以开始正式生成",
            "subtitle": "配置 API Key 后去掉 --dry-run",
        },
    ]


def render_preview(data: dict, palette: str, out: str) -> str:
    try:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        Renderer().render(preview_slides(data), palette, topic=data["topic"], out=out)
    except Exception as exc:
        fail(
            "离线预览没有写出来。请确认已执行 pip install -r requirements.txt。\n"
            f"  目标: {out}\n"
            f"  原因: {type(exc).__name__}: {exc}"
        )
    return out


async def _generate(llm, data, args, base_name, topic, model, t0):
    """Run plan, write, and render. Caller turns failures into a short message."""
    print(f"\n{'─' * 50}")
    print(f"主题: {topic}")
    print(f"受众: {data.get('audience', '通用')}")
    print(f"模型: {args.provider} / {model}")
    print(f"输入将生成约 25–30 张，输出目录: {os.path.dirname(base_name) or '.'}")
    print(f"{'─' * 50}")

    print("\n正在规划叙事结构...")
    plan_data = await plan(llm, data)
    palette = args.palette or plan_data.get("palette", "tech")
    if palette not in PALETTES:
        source = "指定的" if args.palette else "模型返回的"
        print(f"{source}调色板「{palette}」无法识别，已改用 tech。")
        palette = "tech"
    n_slides = len(plan_data.get("slide_plan", []))
    rhythm_fixes = fix_layout_rhythm(plan_data["slide_plan"])
    if rhythm_fixes:
        print(f"  已调整 {rhythm_fixes} 处连续相同的版式，避免看起来重复。")
    print(f"  规划完成: {n_slides} 张，调色板 {palette}，语气 {plan_data.get('tone', '')}")

    os.makedirs("debug", exist_ok=True)
    with open("debug/plan.json", "w", encoding="utf-8") as f:
        json.dump(plan_data, f, ensure_ascii=False, indent=2)

    print(f"\n正在撰写幻灯片内容（并发 {args.concurrency}）...")
    t1 = time.time()
    contents = await write_all(llm, plan_data, args.concurrency)
    t_write = time.time() - t1
    print(f"  内容完成: {len(contents)} 张（{t_write:.1f} 秒）")

    with open("debug/contents.json", "w", encoding="utf-8") as f:
        json.dump(contents, f, ensure_ascii=False, indent=2)

    issues = validate(contents)
    if issues:
        print(f"  有 {len(issues)} 处版式或标题需要留意，文件仍会写出：")
        for iss in issues[:5]:
            print(f"     - {iss}")

    fmt = args.format
    output_files = []

    if fmt in ("pptx", "both"):
        pptx_out = f"{base_name}.pptx"
        print("\n正在写出 PowerPoint...")
        Renderer().render(contents, palette, topic=topic, out=pptx_out)
        output_files.append(pptx_out)

    if fmt in ("html", "both"):
        html_out = f"{base_name}.html"
        print("\n正在写出 HTML...")
        HTMLRenderer().render(contents, palette, topic=topic, out=html_out)
        output_files.append(html_out)

    total_time = time.time() - t0
    cost = llm.get_cost_estimate()

    print(f"\n{'═' * 50}")
    for path in output_files:
        print(f"已写出: {path}")
    print(f"  幻灯片: {len(contents)} 张")
    print(f"  耗时: {total_time:.1f} 秒")
    print(f"  预估成本: ${cost:.4f}")
    print(f"  Tokens: {llm.total_input_tokens:,} in + {llm.total_output_tokens:,} out")
    print(f"{'═' * 50}")


# ── Main ──────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="PPT Generator")
    parser.add_argument("input", nargs="?", help="输入 JSON，需包含 topic、brief、audience")
    parser.add_argument("-o", "--output", help="Output .pptx path (overrides auto-naming)")
    parser.add_argument("-p", "--palette", help="Force palette name")
    parser.add_argument("--provider", default="deepseek",
                        choices=list(PROVIDERS.keys()),
                        help="LLM provider: deepseek / qwen / openai")
    parser.add_argument("-c", "--concurrency", type=int, default=5, help="Parallel LLM calls")
    parser.add_argument("-f", "--format", default="both",
                        choices=["pptx", "html", "both"],
                        help="Output format: pptx / html / both")
    parser.add_argument("--dry-run", action="store_true",
                        help="检查输入并写出 4 张离线预览，不调用模型")
    args = parser.parse_args()

    load_dotenv()

    input_path = args.input or (SAMPLE_INPUT if args.dry_run else "")
    if not input_path:
        fail(
            "还没有指定输入文件。\n"
            "  离线检查: python main.py samples/client-brief.json --dry-run\n"
            "  正式生成: python main.py samples/client-brief.json"
        )

    data = load_brief(input_path)

    # Resolve provider config from env vars
    prov = PROVIDERS[args.provider]
    prefix = prov["env_prefix"]
    api_key = usable_api_key(
        os.getenv(f"{prefix}_API_KEY"),
        os.getenv("DEEPSEEK_API_KEY"),
    )
    base_url = os.getenv(f"{prefix}_BASE_URL", prov["default_url"])
    model = os.getenv(f"{prefix}_MODEL", prov["default_model"])

    if args.dry_run:
        palette = args.palette or "corporate"
        if palette not in PALETTES:
            print(f"调色板「{palette}」不在可选范围，预览改用 corporate。")
            print("  可选: " + "、".join(PALETTES))
            palette = "corporate"
        preview_out = args.output or SAMPLE_PREVIEW
        if preview_out.endswith(".html"):
            preview_out = preview_out[:-5] + ".pptx"
        elif not preview_out.endswith(".pptx"):
            preview_out = preview_out + ".pptx"
        render_preview(data, palette, preview_out)
        key_state = "已配置，可以正式生成" if api_key else "尚未配置，正式生成前需要填写"
        print("离线检查通过。这一步没有调用模型。")
        print(f"  输入: {input_path}")
        print(f"  主题: {data['topic']}")
        print(f"  受众: {data['audience']}")
        print(f"  模型: {args.provider} / {model}（{key_state}）")
        print(f"  预览: {preview_out}（4 张）")
        print("下一步，生成完整的 25–30 张：")
        print(f"  python main.py {input_path}")
        return

    if not api_key:
        fail(
            f"还不能调用模型：没有可用的 {prefix}_API_KEY。\n"
            "  1. 复制模板: cp .env.example .env\n"
            "  2. 在 .env 里填入服务商发放的密钥，不要提交这个文件\n"
            "  3. 想先看版式: python main.py samples/client-brief.json --dry-run"
        )

    # Sanitize model name for filename (remove slashes, dots)
    model_tag = re.sub(r'[/\\.]', '-', model).split('-')[-1]  # e.g. "chat" from "deepseek-chat"
    if len(model_tag) > 12:
        model_tag = model_tag[:12]
    ts = datetime.now().strftime("%m%d_%H%M")

    llm = LLMClient(provider=prov["sdk"], api_key=api_key, base_url=base_url, model=model)
    t0 = time.time()

    topic = data["topic"]
    topic_tag = topic.replace(" ", "_").replace("/", "-")[:20]
    base_name = args.output or f"output/{topic_tag}_{model_tag}_{ts}"
    os.makedirs(os.path.dirname(base_name) or "output", exist_ok=True)

    try:
        await _generate(llm, data, args, base_name, topic, model, t0)
    except Exception as exc:
        reason = " ".join(str(exc).split())
        if len(reason) > 240:
            reason = reason[:240] + "…"
        fail(
            "生成中断，这一轮没有写出完整幻灯片。\n"
            f"  原因: {type(exc).__name__}: {reason}\n"
            "  请检查 API Key、网络和服务商额度。可以先跑通离线预览:\n"
            "  python main.py samples/client-brief.json --dry-run"
        )


if __name__ == "__main__":
    asyncio.run(main())
