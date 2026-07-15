#!/usr/bin/env python3
"""
AI Comic Generator — 亲子故事漫画生成器
JSON in, comic HTML/PDF out.
Single command: python comic_main.py input.json [-o output.html]
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

# ── Provider configurations (shared with main.py) ────────

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

# ── Story Templates ──────────────────────────────────────

TEMPLATES = {
    "bedtime": {
        "name": "睡前故事",
        "pages": 8,
        "desc": "节奏舒缓，温暖结尾，适合睡前朗读",
        "structure": "开场(2页) → 小冒险(4页) → 温暖回家(2页)",
    },
    "behavior_guide": {
        "name": "行为引导",
        "pages": 10,
        "desc": "通过冒险故事让孩子理解道理",
        "structure": "日常问题(2页) → 奇幻冒险(5页) → 领悟改变(3页)",
    },
    "birthday": {
        "name": "生日庆祝",
        "pages": 8,
        "desc": "充满惊喜和祝福的生日故事",
        "structure": "期待(2页) → 准备惊喜(3页) → 庆祝(3页)",
    },
    "science": {
        "name": "知识科普",
        "pages": 10,
        "desc": "用故事解释科学现象",
        "structure": "提出问题(2页) → 探索发现(5页) → 原来如此(3页)",
    },
    "fairy_tale": {
        "name": "奇幻冒险",
        "pages": 12,
        "desc": "完整的英雄旅程",
        "structure": "日常世界(2页) → 进入奇幻(6页) → 胜利归来(4页)",
    },
    "custom": {
        "name": "自定义",
        "pages": 10,
        "desc": "通用模板，自由发挥",
        "structure": "开场(2页) → 主体(6页) → 结尾(2页)",
    },
}

# ── JSON parsing ─────────────────────────────────────────

def parse_json(text: str) -> dict:
    """Parse JSON from LLM output, handling markdown wrappers."""
    text = text.strip()
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    return json.loads(text)


# ── Stage 1: Story Planner ───────────────────────────────

STORY_PLANNER_SYSTEM = """你是一位儿童故事作家。你擅长为3-8岁的孩子创作有趣、温暖、有教育意义的短篇漫画故事。
故事要有明确的起承转合，语言简单活泼，适合亲子共读。
输出纯JSON，不要markdown包裹。"""

STORY_PLANNER_PROMPT = """为以下孩子创作一本亲子漫画故事规划。

## 基本信息
- 主题: {topic}
- 主角名字: {child_name}
- 年龄: {age}岁
- 故事类型: {template}
- 补充: {extra}

## 故事类型说明
{template_desc}
- 叙事结构: {template_structure}
- 目标页数: {target_pages}页

## 三幕叙事结构
- Act 1 开场 (1-2页): 介绍主角和日常世界，让孩子产生代入感
- Act 2 冒险 (主体部分): 遇到问题/进入新世界/经历挑战，这是故事的核心
- Act 3 收尾 (2-3页): 解决问题/温暖回家/获得成长，给孩子安全感

## 页面类型 (7种)
- cover: 封面页（大标题 + 主角登场 + 装饰）
- intro: 角色介绍页（展示主角和日常）
- scene: 场景叙述页（旁白推进故事 + 场景描写）
- dialogue: 对话互动页（角色之间的有趣对话）
- action: 动作场景页（冒险、追逐、变化，拟声词）
- discovery: 发现转折页（惊喜时刻、重要领悟）
- ending: 结尾页（温暖总结 + 故事寓意 + "晚安"或"故事结束"）

## 配色方案 (4种，根据主题自动选择)
- warm_pastel: 暖粉色调 → 睡前故事、温馨主题
- bright_fun: 明亮活泼 → 冒险故事、行为引导
- soft_edu: 柔和教育 → 知识科普、探索主题
- festive: 节日金色 → 生日、庆祝主题

## 输出JSON格式（严格遵守）
{{
  "title": "漫画标题(10字以内，有趣吸引人)",
  "palette": "配色方案名称",
  "moral": "故事寓意(一句话，20字以内)",
  "style": "画风描述(如：温暖可爱，线条柔和)",
  "characters": [
    {{"name": "{child_name}", "emoji": "🧒", "desc": "主角，{age}岁的小朋友"}},
    {{"name": "角色名", "emoji": "对应emoji", "desc": "角色描述"}}
  ],
  "page_plan": [
    {{
      "n": 1,
      "act": 1,
      "page_type": "cover",
      "brief": "80字以内的画面描述，包括场景、角色动作、情绪",
      "scene_emoji": "🌙",
      "mood": "温暖期待"
    }}
  ]
}}

## 约束
- 总页数: {target_pages}页
- 第1页必须是cover
- 最后一页必须是ending
- 中间页的page_type要多样化，避免连续3页相同类型
- 每页brief要具体描述画面内容，不要抽象
- scene_emoji选择最能代表该页场景的emoji
- 直接输出JSON，不要任何其他文字"""


async def story_plan(llm: LLMClient, data: dict) -> dict:
    """Stage 1: Generate story plan."""
    template = data.get("template", "custom")
    tpl = TEMPLATES.get(template, TEMPLATES["custom"])
    target_pages = tpl["pages"]

    prompt = STORY_PLANNER_PROMPT.format(
        topic=data["topic"],
        child_name=data["child_name"],
        age=data.get("age", 5),
        template=template,
        extra=data.get("extra", ""),
        template_desc=tpl["desc"],
        template_structure=tpl["structure"],
        target_pages=target_pages,
    )

    raw = await llm.call(
        prompt, system=STORY_PLANNER_SYSTEM,
        temperature=0.85, max_tokens=4096, json_mode=True,
    )
    plan = parse_json(raw)

    # Validate page count
    pages = plan.get("page_plan", [])
    n = len(pages)
    if n < target_pages - 2:
        print(f"  ⚠️  规划只有{n}页，要求补充到{target_pages}页...")
        supplement = (
            f"当前规划只有{n}页，请补充到{target_pages}页。"
            f"保持三幕结构比例，第1页cover，最后一页ending。"
            f"现有规划：{json.dumps(pages, ensure_ascii=False)}\n"
            f"请输出完整的page_plan数组（{target_pages}页），JSON格式。"
        )
        raw2 = await llm.call(
            supplement, system=STORY_PLANNER_SYSTEM,
            temperature=0.7, max_tokens=4096, json_mode=True,
        )
        extra = parse_json(raw2)
        if isinstance(extra, dict) and "page_plan" in extra:
            plan["page_plan"] = extra["page_plan"]
        elif isinstance(extra, list):
            plan["page_plan"] = extra

    return plan


# ── Stage 2: Page Writer ─────────────────────────────────

PAGE_WRITER_SYSTEM = """你是儿童漫画内容撰稿人。为单页漫画撰写温暖有趣的文字内容。
语言要适合3-8岁孩子理解，活泼可爱，多用拟声词和感叹句。
输出纯JSON，不要markdown包裹。"""

PAGE_WRITER_PROMPT = """为漫画第 {num} 页撰写内容。

## 当前页
- 页码: {num} / {total}
- 页面类型: {page_type}
- 画面描述: {brief}
- 场景元素: {scene_emoji}
- 情绪: {mood}

## 上下文
- 前一页: {prev}
- 后一页: {next}

## 角色
{characters}

## 故事信息
- 标题: {title}
- 寓意: {moral}
- 画风: {style}

## 输出JSON
{{
  "title": "页面标题(≤8字)",
  "story_text": "旁白文字(≤60字，适合朗读，温暖有趣)",
  "dialogue": [
    {{"character": "角色名", "text": "对白(≤20字)", "emotion": "happy/surprised/thinking/sad/brave"}}
  ],
  "sound_effect": "拟声词(可选, 如：咔嚓！噗通！嗖～，无则空字符串)",
  "scene_emojis": ["场景装饰emoji1", "emoji2", "emoji3"],
  "page_num": {num},
  "page_type": "{page_type}"
}}

## 约束
- 旁白(story_text): ≤60字，像在给孩子讲故事一样
- 对白(dialogue): 最多3句，每句≤20字，活泼自然
- 拟声词: action类型页面必填，其他类型可选
- scene_emojis: 3-5个装饰用emoji，配合scene_emoji
- cover页: 不需要dialogue和story_text，只需大标题
- ending页: 必须包含温暖的结束语
- 直接输出JSON"""


async def write_page(llm: LLMClient, spec: dict, ctx: dict, sem) -> dict:
    """Generate content for a single comic page."""
    async with sem:
        chars_text = "\n".join(
            f"- {c['emoji']} {c['name']}: {c['desc']}"
            for c in ctx.get("characters", [])
        )

        prompt = PAGE_WRITER_PROMPT.format(
            num=spec["n"],
            total=ctx["total"],
            page_type=spec.get("page_type", "scene"),
            brief=spec.get("brief", ""),
            scene_emoji=spec.get("scene_emoji", "🌟"),
            mood=spec.get("mood", ""),
            prev=ctx.get("prev", "（故事开始）"),
            next=ctx.get("next", "（故事结束）"),
            characters=chars_text,
            title=ctx.get("title", ""),
            moral=ctx.get("moral", ""),
            style=ctx.get("style", ""),
        )

        raw = await llm.call(
            prompt, system=PAGE_WRITER_SYSTEM,
            temperature=0.8, max_tokens=1024, json_mode=True,
        )

        try:
            content = parse_json(raw)
        except json.JSONDecodeError:
            print(f"  ⚠️  P{spec['n']} JSON解析失败，使用备选内容")
            content = {
                "title": spec.get("brief", "")[:8],
                "story_text": spec.get("brief", ""),
                "dialogue": [],
                "sound_effect": "",
                "scene_emojis": [spec.get("scene_emoji", "🌟")],
                "page_num": spec["n"],
                "page_type": spec.get("page_type", "scene"),
            }

        # Carry over plan info
        content["page_type"] = spec.get("page_type", "scene")
        content["page_num"] = spec["n"]
        content["act"] = spec.get("act", 1)
        content["scene_emoji"] = spec.get("scene_emoji", "🌟")
        content["mood"] = spec.get("mood", "")
        return content


async def write_all_pages(llm: LLMClient, plan_data: dict, concurrency: int) -> list[dict]:
    """Stage 2: Generate all page contents in parallel."""
    pages = plan_data.get("page_plan", [])
    total = len(pages)
    sem = asyncio.Semaphore(concurrency)

    ctx_base = {
        "total": total,
        "characters": plan_data.get("characters", []),
        "title": plan_data.get("title", ""),
        "moral": plan_data.get("moral", ""),
        "style": plan_data.get("style", ""),
    }

    tasks = []
    for i, spec in enumerate(pages):
        ctx = {
            **ctx_base,
            "prev": pages[i - 1].get("brief", "") if i > 0 else "",
            "next": pages[i + 1].get("brief", "") if i < total - 1 else "",
        }
        tasks.append(write_page(llm, spec, ctx, sem))

    return list(await asyncio.gather(*tasks))


# ── Validation ───────────────────────────────────────────

def validate_pages(pages: list[dict]) -> list[str]:
    """Quick validation of generated pages."""
    issues = []
    for i, p in enumerate(pages):
        if not p.get("title", "").strip():
            issues.append(f"P{i + 1}: 标题为空")
        if p.get("page_type") == "cover" and i != 0:
            issues.append(f"P{i + 1}: cover不在第一页")
    return issues


# ── Main ─────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="AI Comic Generator")
    parser.add_argument("input", help="Input JSON file")
    parser.add_argument("-o", "--output", help="Output path (overrides auto-naming)")
    parser.add_argument("--provider", default="deepseek",
                        choices=list(PROVIDERS.keys()),
                        help="LLM provider")
    parser.add_argument("-c", "--concurrency", type=int, default=3,
                        help="Parallel LLM calls")
    parser.add_argument("-f", "--format", default="html",
                        choices=["html", "pdf", "both"],
                        help="Output format")
    args = parser.parse_args()

    load_dotenv()

    prov = PROVIDERS[args.provider]
    prefix = prov["env_prefix"]
    api_key = os.getenv(f"{prefix}_API_KEY") or os.getenv("DEEPSEEK_API_KEY", "")
    base_url = os.getenv(f"{prefix}_BASE_URL", prov["default_url"])
    model = os.getenv(f"{prefix}_MODEL", prov["default_model"])

    if not api_key:
        print(f"❌ 请设置 {prefix}_API_KEY")
        sys.exit(1)

    model_tag = re.sub(r'[/\\.]', '-', model).split('-')[-1][:12]
    ts = datetime.now().strftime("%m%d_%H%M")

    llm = LLMClient(provider=prov["sdk"], api_key=api_key, base_url=base_url, model=model)
    t0 = time.time()

    # Load input
    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)

    topic = data["topic"]
    child_name = data.get("child_name", "小朋友")
    topic_tag = topic.replace(" ", "_").replace("/", "-")[:20]
    base_name = args.output or f"comic-output/{topic_tag}_{model_tag}_{ts}"
    os.makedirs(os.path.dirname(base_name) or "comic-output", exist_ok=True)

    # ── Stage 1: Story Plan ──
    print(f"\n{'─' * 50}")
    print(f"📖 漫画: {topic}")
    print(f"👶 主角: {child_name} ({data.get('age', 5)}岁)")
    print(f"📝 模板: {TEMPLATES.get(data.get('template', 'custom'), {}).get('name', '自定义')}")
    print(f"🤖 模型: {args.provider} / {model}")
    print(f"{'─' * 50}")

    print("\n📖 Stage 1: 故事规划 ...")
    plan_data = await story_plan(llm, data)
    palette = plan_data.get("palette", "warm_pastel")
    n_pages = len(plan_data.get("page_plan", []))
    print(f"  ✅ 规划完成: {n_pages}页")
    print(f"     标题: {plan_data.get('title', '?')}")
    print(f"     配色: {palette}")
    print(f"     寓意: {plan_data.get('moral', '')}")
    print(f"     角色: {', '.join(c['name'] for c in plan_data.get('characters', []))}")

    # Save plan
    os.makedirs("debug", exist_ok=True)
    with open("debug/comic_plan.json", "w", encoding="utf-8") as f:
        json.dump(plan_data, f, ensure_ascii=False, indent=2)

    # ── Stage 2: Write Pages ──
    print(f"\n✍️  Stage 2: 内容生成 (并发={args.concurrency}) ...")
    t1 = time.time()
    pages = await write_all_pages(llm, plan_data, args.concurrency)
    t_write = time.time() - t1
    print(f"  ✅ {len(pages)}页内容完成 ({t_write:.1f}s)")

    with open("debug/comic_pages.json", "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False, indent=2)

    # Validate
    issues = validate_pages(pages)
    if issues:
        print(f"  ⚠️  发现 {len(issues)} 个问题:")
        for iss in issues[:5]:
            print(f"     - {iss}")

    # ── Stage 3: Render ──
    fmt = args.format
    output_files = []

    if fmt in ("html", "both"):
        html_out = f"{base_name}.html"
        print("\n🎨 Stage 3: HTML漫画渲染 ...")
        from comic_renderer import ComicRenderer
        ComicRenderer().render(pages, palette, plan_data, out=html_out)
        output_files.append(html_out)

    if fmt in ("pdf", "both"):
        pdf_out = f"{base_name}.pdf"
        print("\n📄 Stage 3: PDF渲染 ...")
        try:
            from comic_pdf import ComicPDFRenderer
            ComicPDFRenderer().render(pages, palette, plan_data, out=pdf_out)
            output_files.append(pdf_out)
        except ImportError:
            print("  ⚠️  PDF渲染需要 weasyprint，跳过。pip install weasyprint")

    total_time = time.time() - t0
    cost = llm.get_cost_estimate()

    print(f"\n{'═' * 50}")
    for f in output_files:
        print(f"✅ {f}")
    print(f"   📖 {len(pages)}页漫画")
    print(f"   ⏱  总耗时: {total_time:.1f}s")
    print(f"   💰 预估成本: ${cost:.4f}")
    print(f"   📝 Tokens: {llm.total_input_tokens:,} in + {llm.total_output_tokens:,} out")
    print(f"{'═' * 50}")


if __name__ == "__main__":
    asyncio.run(main())
