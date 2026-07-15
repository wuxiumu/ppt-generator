#!/usr/bin/env python3
"""
Comic Image Generator — Generate cartoon illustrations for comic pages.

Supports multiple image providers:
  - pollinations: Free, no API key needed (default for testing)
  - dashscope: Alibaba Wanx API (uses QWEN_API_KEY)
  - siliconflow: SiliconFlow Stable Diffusion API (uses SILICONFLOW_API_KEY)
"""

import hashlib
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

# ── Style presets ──────────────────────────────────────

STYLE_PREFIX = (
    "Cute kawaii cartoon illustration for children's comic book, "
    "warm pastel colors, soft rounded lines, adorable characters with big expressive eyes, "
    "children's book illustration style, no text, no watermark. "
)

PALETTE_DESC = {
    "warm_pastel": "warm pink and peach pastel tones, cozy atmosphere",
    "bright_fun": "bright cheerful colors, yellow and blue accents, playful",
    "soft_edu": "soft educational tones, green and blue, gentle and clear",
    "festive": "festive golden and warm tones, celebration atmosphere, sparkles",
}


def build_image_prompt(page_spec: dict, plan_data: dict) -> str:
    """Build a detailed English image prompt from page plan data."""
    brief = page_spec.get("brief", "")
    mood = page_spec.get("mood", "")
    page_type = page_spec.get("page_type", "scene")
    scene_emoji = page_spec.get("scene_emoji", "")
    palette = plan_data.get("palette", "warm_pastel")

    # Character descriptions
    characters = plan_data.get("characters", [])
    char_desc = []
    for c in characters:
        char_desc.append(f"{c['name']} ({c.get('desc', '')})")

    # Build prompt
    parts = [STYLE_PREFIX]

    # Scene description (translate brief to more visual description)
    if brief:
        parts.append(f"Scene: {brief}.")

    # Mood
    if mood:
        parts.append(f"Mood: {mood}.")

    # Characters present
    if char_desc:
        parts.append(f"Characters: {'; '.join(char_desc)}.")

    # Page type hints
    type_hints = {
        "cover": "Full page cover illustration, main character prominently centered, title-worthy composition",
        "intro": "Character introduction scene, showing daily life, warm and relatable",
        "scene": "Story scene with environmental details, showing action and interaction",
        "dialogue": "Two or more characters interacting, expressive faces and body language",
        "action": "Dynamic action scene, movement and energy, exciting moment",
        "discovery": "Surprise or discovery moment, character with amazed expression, magical feeling",
        "ending": "Warm concluding scene, peaceful and heartwarming, gentle lighting",
    }
    if page_type in type_hints:
        parts.append(type_hints[page_type] + ".")

    # Palette
    parts.append(PALETTE_DESC.get(palette, PALETTE_DESC["warm_pastel"]) + ".")

    return " ".join(parts)


# ── Providers ──────────────────────────────────────────

def generate_pollinations(prompt: str, out_path: str, width=1024, height=768, seed=None) -> bool:
    """Generate image via Pollinations.ai (free, no API key)."""
    if seed is None:
        seed = int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16) % 100000

    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&seed={seed}&nologo=true"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ComicGen/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
            if len(data) < 1000:
                print(f"    ⚠️  Image too small ({len(data)} bytes), likely error")
                return False
            with open(out_path, "wb") as f:
                f.write(data)
            print(f"    ✅ {out_path} ({len(data)//1024}KB)")
            return True
    except Exception as e:
        print(f"    ❌ Pollinations error: {e}")
        return False


def generate_dashscope(prompt: str, out_path: str, width=1024, height=768, **kwargs) -> bool:
    """Generate image via Alibaba DashScope Wanx API."""
    import json

    api_key = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        print("    ❌ 未配置 QWEN_API_KEY / DASHSCOPE_API_KEY")
        return False

    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
    payload = json.dumps({
        "model": "wanx-v1",
        "input": {"prompt": prompt},
        "parameters": {"size": f"{width}*{height}", "n": 1}
    }).encode()

    try:
        req = urllib.request.Request(url, data=payload, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "X-DashScope-Async": "enable",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())

        task_id = result.get("output", {}).get("task_id")
        if not task_id:
            print(f"    ❌ No task_id: {result}")
            return False

        # Poll for result
        check_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
        for _ in range(60):
            time.sleep(3)
            check_req = urllib.request.Request(check_url, headers={
                "Authorization": f"Bearer {api_key}",
            })
            with urllib.request.urlopen(check_req, timeout=30) as resp:
                status = json.loads(resp.read())

            task_status = status.get("output", {}).get("task_status")
            if task_status == "SUCCEEDED":
                img_url = status["output"]["results"][0]["url"]
                urllib.request.urlretrieve(img_url, out_path)
                print(f"    ✅ {out_path}")
                return True
            elif task_status == "FAILED":
                print(f"    ❌ Task failed: {status}")
                return False
            # else PENDING/RUNNING, continue polling

        print("    ❌ Timeout waiting for image")
        return False

    except Exception as e:
        print(f"    ❌ DashScope error: {e}")
        return False


def generate_siliconflow(prompt: str, out_path: str, width=1024, height=768, **kwargs) -> bool:
    """Generate image via SiliconFlow Stable Diffusion API."""
    import json

    api_key = os.getenv("SILICONFLOW_API_KEY", "")
    if not api_key:
        print("    ❌ 未配置 SILICONFLOW_API_KEY")
        return False

    url = "https://api.siliconflow.cn/v1/images/generations"
    payload = json.dumps({
        "model": "stabilityai/stable-diffusion-3-5-large",
        "prompt": prompt,
        "image_size": f"{width}x{height}",
        "num_inference_steps": 30,
    }).encode()

    try:
        req = urllib.request.Request(url, data=payload, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        })
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())

        img_url = result.get("images", [{}])[0].get("url")
        if not img_url:
            print(f"    ❌ No image URL: {result}")
            return False

        urllib.request.urlretrieve(img_url, out_path)
        print(f"    ✅ {out_path}")
        return True

    except Exception as e:
        print(f"    ❌ SiliconFlow error: {e}")
        return False


# Provider registry
PROVIDERS = {
    "pollinations": generate_pollinations,
    "dashscope": generate_dashscope,
    "siliconflow": generate_siliconflow,
}


def get_default_provider() -> str:
    """Determine the best available image provider.
    Note: DASHSCOPE_API_KEY is for image gen (wanx), QWEN_API_KEY is for LLM only.
    """
    # Only use dashscope if DASHSCOPE_API_KEY is explicitly set
    if os.getenv("DASHSCOPE_API_KEY"):
        return "dashscope"
    if os.getenv("SILICONFLOW_API_KEY"):
        return "siliconflow"
    # Fallback to free provider
    return "pollinations"


# ── Batch generation ──────────────────────────────────

def generate_page_images(
    pages: list[dict],
    plan_data: dict,
    out_dir: str,
    provider: str = None,
    width: int = 1024,
    height: int = 768,
) -> list[str]:
    """
    Generate images for all comic pages.
    Returns list of image file paths (empty string for failed pages).
    """
    if provider is None:
        provider = get_default_provider()

    gen_func = PROVIDERS.get(provider, generate_pollinations)
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n🎨 Image Generation ({provider})")
    print(f"   {len(pages)} pages to generate...")

    paths = []
    for i, page in enumerate(pages):
        page_num = page.get("page_num", i + 1)
        img_file = os.path.join(out_dir, f"page_{page_num:02d}.png")

        # Skip if already exists
        if os.path.exists(img_file) and os.path.getsize(img_file) > 1000:
            print(f"  [{page_num}/{len(pages)}] Cached: {img_file}")
            paths.append(img_file)
            continue

        prompt = build_image_prompt(page, plan_data)
        print(f"  [{page_num}/{len(pages)}] Generating: {page.get('title', '?')}...")

        ok = gen_func(prompt, img_file, width=width, height=height)

        # Fallback to pollinations if primary provider fails
        if not ok and provider != "pollinations":
            print(f"    ↪ Falling back to pollinations.ai...")
            ok = generate_pollinations(prompt, img_file, width=width, height=height)

        paths.append(img_file if ok else "")

        # Rate limit: small delay between requests
        if provider == "pollinations":
            time.sleep(1)

    generated = sum(1 for p in paths if p)
    print(f"\n   ✅ {generated}/{len(pages)} images generated")

    return paths
