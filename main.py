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
from dotenv import load_dotenv

from llm import LLMClient
from renderer import Renderer
from html_renderer import HTMLRenderer

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
            print(f"  ⚠️  S{spec['n']} JSON解析失败，使用备选内容")
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


# ── Main ──────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="PPT Generator")
    parser.add_argument("input", help="Input JSON file")
    parser.add_argument("-o", "--output", help="Output .pptx path (overrides auto-naming)")
    parser.add_argument("-p", "--palette", help="Force palette name")
    parser.add_argument("--provider", default="deepseek",
                        choices=list(PROVIDERS.keys()),
                        help="LLM provider: deepseek / qwen / openai")
    parser.add_argument("-c", "--concurrency", type=int, default=5, help="Parallel LLM calls")
    parser.add_argument("-f", "--format", default="both",
                        choices=["pptx", "html", "both"],
                        help="Output format: pptx / html / both")
    args = parser.parse_args()

    load_dotenv()

    # Resolve provider config from env vars
    prov = PROVIDERS[args.provider]
    prefix = prov["env_prefix"]
    api_key = os.getenv(f"{prefix}_API_KEY") or os.getenv("DEEPSEEK_API_KEY", "")
    base_url = os.getenv(f"{prefix}_BASE_URL", prov["default_url"])
    model = os.getenv(f"{prefix}_MODEL", prov["default_model"])

    if not api_key:
        print(f"❌ 请设置 {prefix}_API_KEY（在 .env 文件或环境变量中）")
        sys.exit(1)

    # Sanitize model name for filename (remove slashes, dots)
    model_tag = re.sub(r'[/\\.]', '-', model).split('-')[-1]  # e.g. "chat" from "deepseek-chat"
    if len(model_tag) > 12:
        model_tag = model_tag[:12]
    ts = datetime.now().strftime("%m%d_%H%M")

    llm = LLMClient(provider=prov["sdk"], api_key=api_key, base_url=base_url, model=model)
    t0 = time.time()

    # Load input
    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)

    topic = data["topic"]
    topic_tag = topic.replace(" ", "_").replace("/", "-")[:20]
    base_name = args.output or f"output/{topic_tag}_{model_tag}_{ts}"
    os.makedirs(os.path.dirname(base_name) or "output", exist_ok=True)

    # ── Stage 1: Plan ──
    print(f"\n{'─' * 50}")
    print(f"📋 主题: {topic}")
    print(f"👥 受众: {data.get('audience', '通用')}")
    print(f"🤖 模型: {args.provider} / {model}")
    print(f"{'─' * 50}")

    print("\n🎬 Stage 1: 叙事规划 ...")
    plan_data = await plan(llm, data)
    palette = args.palette or plan_data.get("palette", "tech")
    n_slides = len(plan_data.get("slide_plan", []))
    rhythm_fixes = fix_layout_rhythm(plan_data["slide_plan"])
    if rhythm_fixes:
        print(f"  🔧 自动修复了 {rhythm_fixes} 处连续相同布局")
    print(f"  ✅ 规划完成: {n_slides} 张, 调色板={palette}, 语气={plan_data.get('tone', '')}")

    # Save plan for debugging
    os.makedirs("debug", exist_ok=True)
    with open("debug/plan.json", "w", encoding="utf-8") as f:
        json.dump(plan_data, f, ensure_ascii=False, indent=2)

    # ── Stage 2: Write ──
    print(f"\n✍️  Stage 2: 内容生成 (并发={args.concurrency}) ...")
    t1 = time.time()
    contents = await write_all(llm, plan_data, args.concurrency)
    t_write = time.time() - t1
    print(f"  ✅ {len(contents)} 张内容生成完成 ({t_write:.1f}s)")

    # Save contents for debugging
    with open("debug/contents.json", "w", encoding="utf-8") as f:
        json.dump(contents, f, ensure_ascii=False, indent=2)

    # Validate
    issues = validate(contents)
    if issues:
        print(f"  ⚠️  发现 {len(issues)} 个问题:")
        for iss in issues[:5]:
            print(f"     - {iss}")

    # ── Stage 3: Render ──
    fmt = args.format
    output_files = []

    if fmt in ("pptx", "both"):
        pptx_out = f"{base_name}.pptx"
        print("\n🎨 Stage 3: PPTX渲染 ...")
        renderer = Renderer()
        renderer.render(contents, palette, topic=topic, out=pptx_out)
        output_files.append(pptx_out)

    if fmt in ("html", "both"):
        html_out = f"{base_name}.html"
        print("\n🌐 Stage 3: HTML渲染 ...")
        html_renderer = HTMLRenderer()
        html_renderer.render(contents, palette, topic=topic, out=html_out)
        output_files.append(html_out)

    total_time = time.time() - t0
    cost = llm.get_cost_estimate()

    print(f"\n{'═' * 50}")
    for f in output_files:
        print(f"✅ {f}")
    print(f"   📊 {len(contents)} 张幻灯片")
    print(f"   ⏱  总耗时: {total_time:.1f}s")
    print(f"   💰 预估成本: ${cost:.4f}")
    print(f"   📝 Tokens: {llm.total_input_tokens:,} in + {llm.total_output_tokens:,} out")
    print(f"{'═' * 50}")


if __name__ == "__main__":
    asyncio.run(main())
