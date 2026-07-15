#!/usr/bin/env python3
"""
Comic HTML Renderer — 漫画HTML渲染器
将结构化页面数据渲染为自包含的竖屏滚动漫画HTML。
"""

import html
import os


# ── Color Palettes ───────────────────────────────────────

PALETTES = {
    "warm_pastel": {
        "name": "暖粉色调",
        "bg": "#FFF5F7",
        "surface": "#FFFFFF",
        "text": "#4A3728",
        "text2": "#7A6558",
        "accent": "#E8A0BF",
        "accent2": "#FFD1DC",
        "bubble": "#FFFFFF",
        "bubble_border": "#E8A0BF",
        "narration": "#6B4F3A",
        "sfx": "#E85D75",
        "footer": "#D4A89A",
        "grad1": "linear-gradient(180deg, #FFE8F0 0%, #FFF5F7 100%)",
        "grad2": "linear-gradient(135deg, #FFD1DC 0%, #E8A0BF 100%)",
        "cover_bg": "linear-gradient(160deg, #FFE0EC 0%, #FFF0F5 40%, #FFF8E7 100%)",
        "ending_bg": "linear-gradient(180deg, #FFF5F7 0%, #FFE0EC 50%, #FFD1DC 100%)",
    },
    "bright_fun": {
        "name": "明亮活泼",
        "bg": "#F0F8FF",
        "surface": "#FFFFFF",
        "text": "#2C3E50",
        "text2": "#5D6D7E",
        "accent": "#FF9F43",
        "accent2": "#54A0FF",
        "bubble": "#FFFFFF",
        "bubble_border": "#FF9F43",
        "narration": "#34495E",
        "sfx": "#E74C3C",
        "footer": "#95A5A6",
        "grad1": "linear-gradient(180deg, #E8F8FF 0%, #F0F8FF 100%)",
        "grad2": "linear-gradient(135deg, #FF9F43 0%, #54A0FF 100%)",
        "cover_bg": "linear-gradient(160deg, #FFECD2 0%, #FCB69F 50%, #FF9A9E 100%)",
        "ending_bg": "linear-gradient(180deg, #A1C4FD 0%, #C2E9FB 50%, #F0F8FF 100%)",
    },
    "soft_edu": {
        "name": "柔和教育",
        "bg": "#F8FBF8",
        "surface": "#FFFFFF",
        "text": "#2C3E50",
        "text2": "#5D6D7E",
        "accent": "#74B9FF",
        "accent2": "#00B894",
        "bubble": "#FFFFFF",
        "bubble_border": "#74B9FF",
        "narration": "#2D3436",
        "sfx": "#6C5CE7",
        "footer": "#B2BEC3",
        "grad1": "linear-gradient(180deg, #E8F4FD 0%, #F8FBF8 100%)",
        "grad2": "linear-gradient(135deg, #74B9FF 0%, #00B894 100%)",
        "cover_bg": "linear-gradient(160deg, #A1C4FD 0%, #C2E9FB 50%, #E8F8F5 100%)",
        "ending_bg": "linear-gradient(180deg, #F8FBF8 0%, #DFE6E9 50%, #B2BEC3 100%)",
    },
    "festive": {
        "name": "节日金色",
        "bg": "#FFF9F0",
        "surface": "#FFFFFF",
        "text": "#4A3728",
        "text2": "#7A6558",
        "accent": "#FDCB6E",
        "accent2": "#E17055",
        "bubble": "#FFFFFF",
        "bubble_border": "#FDCB6E",
        "narration": "#5D4037",
        "sfx": "#E17055",
        "footer": "#D4A89A",
        "grad1": "linear-gradient(180deg, #FFF3E0 0%, #FFF9F0 100%)",
        "grad2": "linear-gradient(135deg, #FDCB6E 0%, #E17055 100%)",
        "cover_bg": "linear-gradient(160deg, #FDCB6E 0%, #F8A5C2 50%, #F7D794 100%)",
        "ending_bg": "linear-gradient(180deg, #FFF9F0 0%, #FDCB6E 50%, #F8A5C2 100%)",
    },
}

# ── Emotion → emoji mapping ─────────────────────────────

EMOTION_EMOJI = {
    "happy": "😊", "surprised": "😲", "thinking": "🤔",
    "sad": "😢", "brave": "💪", "excited": "🤩",
    "sleepy": "😴", "scared": "😨", "love": "🥰",
    "default": "😊",
}


class ComicRenderer:
    """HTML Comic Renderer with CSS illustrations."""

    def render(self, pages: list[dict], palette_name: str,
               plan_data: dict = None, out: str = "comic.html") -> str:
        pal = PALETTES.get(palette_name, PALETTES["warm_pastel"])
        plan = plan_data or {}
        title = plan.get("title", pages[0].get("title", "故事")) if pages else "故事"

        page_htmls = []
        for i, page in enumerate(pages):
            page_htmls.append(self._render_page(page, pal, i, len(pages)))

        full_html = self._wrap(page_htmls, pal, title, plan, len(pages))

        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(full_html)
        return out

    def render_to_string(self, pages, palette_name, plan_data=None) -> str:
        pal = PALETTES.get(palette_name, PALETTES["warm_pastel"])
        plan = plan_data or {}
        title = plan.get("title", "故事")
        page_htmls = []
        for i, page in enumerate(pages):
            page_htmls.append(self._render_page(page, pal, i, len(pages)))
        return self._wrap(page_htmls, pal, title, plan, len(pages))

    # ── Page Rendering ───────────────────────────────────

    def _render_page(self, page: dict, pal: dict, index: int, total: int) -> str:
        ptype = page.get("page_type", "scene")
        dispatch = {
            "cover": self._page_cover,
            "intro": self._page_intro,
            "scene": self._page_scene,
            "dialogue": self._page_dialogue,
            "action": self._page_action,
            "discovery": self._page_discovery,
            "ending": self._page_ending,
        }
        handler = dispatch.get(ptype, self._page_scene)
        inner = handler(page, pal)

        # Decorations layer
        emojis = page.get("scene_emojis", [page.get("scene_emoji", "🌟")])
        deco_html = self._render_decorations(emojis, ptype)

        # Page footer (except cover and ending)
        footer = ""
        if ptype not in ("cover", "ending"):
            footer = f'<div class="page-footer">── 第 {index + 1} 页 / 共 {total} 页 ──</div>'

        return f'''<section class="comic-page page-{ptype}" data-page="{index + 1}">
  <div class="page-bg"></div>
  <div class="page-decorations">{deco_html}</div>
  <div class="page-content">{inner}</div>
  {footer}
</section>'''

    def _render_decorations(self, emojis: list, ptype: str) -> str:
        import random
        positions = [
            ("8%", "5%"), ("12%", "85%"), ("75%", "8%"),
            ("80%", "88%"), ("45%", "3%"), ("30%", "90%"),
        ]
        html_parts = []
        for i, em in enumerate(emojis[:5]):
            top, left = positions[i % len(positions)]
            size = random.choice(["28px", "32px", "36px", "24px"])
            delay = f"{i * 0.3}s"
            html_parts.append(
                f'<span class="deco" style="top:{top};left:{left};'
                f'font-size:{size};animation-delay:{delay}">{html.escape(em)}</span>'
            )
        return "\n".join(html_parts)

    # ── Page Type Renderers ──────────────────────────────

    def _page_cover(self, page: dict, pal: dict) -> str:
        title = html.escape(page.get("title", ""))
        scene_emoji = html.escape(page.get("scene_emoji", "📖"))
        mood = html.escape(page.get("mood", ""))
        characters = page.get("characters", [])
        char_emojis = "".join(html.escape(c.get("emoji", "")) for c in characters[:3]) if characters else ""

        return f'''
    <div class="cover-content">
      <div class="cover-emoji">{scene_emoji}</div>
      <h1 class="cover-title">{title}</h1>
      {f'<div class="cover-mood">{mood}</div>' if mood else ''}
      {f'<div class="cover-chars">{char_emojis}</div>' if char_emojis else ''}
      <div class="cover-badge">亲子漫画</div>
    </div>'''

    def _page_intro(self, page: dict, pal: dict) -> str:
        return self._story_page(page, pal, "intro")

    def _page_scene(self, page: dict, pal: dict) -> str:
        return self._story_page(page, pal, "scene")

    def _page_dialogue(self, page: dict, pal: dict) -> str:
        title = html.escape(page.get("title", ""))
        story = html.escape(page.get("story_text", ""))
        dialogues = page.get("dialogue", [])
        scene_emoji = html.escape(page.get("scene_emoji", "💬"))

        bubbles_html = ""
        for d in dialogues[:3]:
            emotion = d.get("emotion", "happy")
            emo = EMOTION_EMOJI.get(emotion, "😊")
            char = html.escape(d.get("character", ""))
            text = html.escape(d.get("text", ""))
            bubbles_html += f'''
        <div class="bubble bubble-{emotion}">
          <div class="bubble-header">
            <span class="bubble-avatar">{emo}</span>
            <span class="bubble-name">{char}</span>
          </div>
          <div class="bubble-text">{text}</div>
        </div>'''

        return f'''
    <div class="page-title">{title}</div>
    <div class="page-scene-emoji">{scene_emoji}</div>
    {f'<div class="page-narration">{story}</div>' if story else ''}
    <div class="dialogues-container">{bubbles_html}</div>'''

    def _page_action(self, page: dict, pal: dict) -> str:
        title = html.escape(page.get("title", ""))
        story = html.escape(page.get("story_text", ""))
        sfx = html.escape(page.get("sound_effect", ""))
        scene_emoji = html.escape(page.get("scene_emoji", "⚡"))
        dialogues = page.get("dialogue", [])

        bubbles_html = ""
        for d in dialogues[:2]:
            emotion = d.get("emotion", "brave")
            emo = EMOTION_EMOJI.get(emotion, "💪")
            char = html.escape(d.get("character", ""))
            text = html.escape(d.get("text", ""))
            bubbles_html += f'''
        <div class="bubble bubble-{emotion} bubble-compact">
          <span class="bubble-avatar">{emo}</span>
          <span class="bubble-text-compact"><b>{char}</b>: {text}</span>
        </div>'''

        return f'''
    <div class="page-title">{title}</div>
    <div class="page-scene-emoji action-emoji">{scene_emoji}</div>
    {f'<div class="page-sfx">{sfx}</div>' if sfx else ''}
    {f'<div class="page-narration">{story}</div>' if story else ''}
    {f'<div class="dialogues-container">{bubbles_html}</div>' if bubbles_html else ''}'''

    def _page_discovery(self, page: dict, pal: dict) -> str:
        title = html.escape(page.get("title", ""))
        story = html.escape(page.get("story_text", ""))
        scene_emoji = html.escape(page.get("scene_emoji", "✨"))
        dialogues = page.get("dialogue", [])

        bubbles_html = ""
        for d in dialogues[:2]:
            emotion = d.get("emotion", "surprised")
            emo = EMOTION_EMOJI.get(emotion, "😲")
            char = html.escape(d.get("character", ""))
            text = html.escape(d.get("text", ""))
            bubbles_html += f'''
        <div class="bubble bubble-{emotion}">
          <div class="bubble-header">
            <span class="bubble-avatar">{emo}</span>
            <span class="bubble-name">{char}</span>
          </div>
          <div class="bubble-text">{text}</div>
        </div>'''

        return f'''
    <div class="discovery-glow">{scene_emoji}</div>
    <div class="page-title discovery-title">{title}</div>
    {f'<div class="page-narration discovery-narration">{story}</div>' if story else ''}
    {f'<div class="dialogues-container">{bubbles_html}</div>' if bubbles_html else ''}'''

    def _page_ending(self, page: dict, pal: dict) -> str:
        title = html.escape(page.get("title", ""))
        story = html.escape(page.get("story_text", ""))
        scene_emoji = html.escape(page.get("scene_emoji", "🌙"))
        moral = html.escape(page.get("moral", ""))

        return f'''
    <div class="ending-content">
      <div class="ending-emoji">{scene_emoji}</div>
      <h2 class="ending-title">{title}</h2>
      {f'<div class="ending-story">{story}</div>' if story else ''}
      {f'<div class="ending-moral">{moral}</div>' if moral else ''}
      <div class="ending-mark">── 故事结束 ──</div>
    </div>'''

    def _story_page(self, page: dict, pal: dict, variant: str) -> str:
        """Generic story page with narration + optional dialogue."""
        title = html.escape(page.get("title", ""))
        story = html.escape(page.get("story_text", ""))
        scene_emoji = html.escape(page.get("scene_emoji", "🌟"))
        dialogues = page.get("dialogue", [])

        bubbles_html = ""
        for d in dialogues[:3]:
            emotion = d.get("emotion", "happy")
            emo = EMOTION_EMOJI.get(emotion, "😊")
            char = html.escape(d.get("character", ""))
            text = html.escape(d.get("text", ""))
            bubbles_html += f'''
        <div class="bubble bubble-{emotion}">
          <div class="bubble-header">
            <span class="bubble-avatar">{emo}</span>
            <span class="bubble-name">{char}</span>
          </div>
          <div class="bubble-text">{text}</div>
        </div>'''

        return f'''
    <div class="page-title">{title}</div>
    <div class="page-scene-emoji">{scene_emoji}</div>
    {f'<div class="page-narration">{story}</div>' if story else ''}
    {f'<div class="dialogues-container">{bubbles_html}</div>' if bubbles_html else ''}'''

    # ── HTML Wrapper ─────────────────────────────────────

    def _wrap(self, page_htmls: list[str], pal: dict,
              title: str, plan: dict, total: int) -> str:
        moral = html.escape(plan.get("moral", ""))
        characters = plan.get("characters", [])
        chars_text = " ".join(
            f"{html.escape(c.get('emoji', ''))} {html.escape(c.get('name', ''))}"
            for c in characters
        )

        pages_joined = "\n".join(page_htmls)

        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)} — 亲子漫画</title>
<style>
{self._get_css(pal)}
</style>
</head>
<body>
<div class="comic-container">
{pages_joined}
</div>
<script>
// Keyboard navigation
document.addEventListener('keydown', function(e) {{
  const pages = document.querySelectorAll('.comic-page');
  const current = Math.round(window.scrollY / window.innerHeight);
  if (e.key === 'ArrowDown' || e.key === 'PageDown' || e.key === ' ') {{
    e.preventDefault();
    if (current < pages.length - 1) pages[current + 1].scrollIntoView({{behavior:'smooth'}});
  }} else if (e.key === 'ArrowUp' || e.key === 'PageUp') {{
    e.preventDefault();
    if (current > 0) pages[current - 1].scrollIntoView({{behavior:'smooth'}});
  }} else if (e.key === 'Home') {{
    pages[0].scrollIntoView({{behavior:'smooth'}});
  }} else if (e.key === 'End') {{
    pages[pages.length - 1].scrollIntoView({{behavior:'smooth'}});
  }}
}});

// Intersection observer for fade-in animations
const observer = new IntersectionObserver((entries) => {{
  entries.forEach(entry => {{
    if (entry.isIntersecting) {{
      entry.target.classList.add('visible');
    }}
  }});
}}, {{threshold: 0.3}});
document.querySelectorAll('.comic-page').forEach(p => observer.observe(p));
</script>
</body>
</html>'''

    def _get_css(self, pal: dict) -> str:
        return f'''
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

:root {{
  --bg: {pal['bg']};
  --surface: {pal['surface']};
  --text: {pal['text']};
  --text2: {pal['text2']};
  --accent: {pal['accent']};
  --accent2: {pal['accent2']};
  --bubble: {pal['bubble']};
  --bubble-border: {pal['bubble_border']};
  --narration: {pal['narration']};
  --sfx: {pal['sfx']};
  --footer: {pal['footer']};
  --cover-bg: {pal['cover_bg']};
  --ending-bg: {pal['ending_bg']};
}}

html {{ scroll-behavior: smooth; }}

body {{
  font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", -apple-system, sans-serif;
  background: var(--bg);
  color: var(--text);
  overflow-x: hidden;
  -webkit-font-smoothing: antialiased;
}}

.comic-container {{
  scroll-snap-type: y mandatory;
  overflow-y: scroll;
  height: 100vh;
}}

/* ── Comic Page ─────────────────────────────── */
.comic-page {{
  width: 100vw;
  min-height: 100vh;
  scroll-snap-align: start;
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
  overflow: hidden;
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 0.6s ease, transform 0.6s ease;
}}

.comic-page.visible {{
  opacity: 1;
  transform: translateY(0);
}}

.page-bg {{
  position: absolute;
  inset: 0;
  background: var(--bg);
  z-index: 0;
}}

.page-cover .page-bg {{ background: var(--cover-bg); }}
.page-ending .page-bg {{ background: var(--ending-bg); }}

.page-content {{
  position: relative;
  z-index: 2;
  max-width: 480px;
  width: 100%;
  text-align: center;
}}

/* ── Decorations ────────────────────────────── */
.page-decorations {{
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
}}

.deco {{
  position: absolute;
  animation: float 3s ease-in-out infinite;
  opacity: 0.6;
}}

@keyframes float {{
  0%, 100% {{ transform: translateY(0) rotate(0deg); }}
  50% {{ transform: translateY(-10px) rotate(5deg); }}
}}

/* ── Page Title ─────────────────────────────── */
.page-title {{
  font-size: clamp(22px, 5vw, 32px);
  font-weight: 800;
  color: var(--text);
  margin-bottom: 16px;
  line-height: 1.3;
}}

.page-scene-emoji {{
  font-size: clamp(60px, 15vw, 100px);
  margin: 16px 0;
  line-height: 1;
  animation: bounce 2s ease-in-out infinite;
}}

.action-emoji {{
  animation: shake 0.5s ease-in-out infinite;
}}

@keyframes bounce {{
  0%, 100% {{ transform: translateY(0); }}
  50% {{ transform: translateY(-12px); }}
}}

@keyframes shake {{
  0%, 100% {{ transform: rotate(0deg); }}
  25% {{ transform: rotate(-8deg); }}
  75% {{ transform: rotate(8deg); }}
}}

/* ── Narration ──────────────────────────────── */
.page-narration {{
  font-size: clamp(16px, 3.5vw, 20px);
  color: var(--narration);
  line-height: 1.8;
  margin: 16px 0;
  padding: 16px 20px;
  background: rgba(255,255,255,0.7);
  border-radius: 16px;
  backdrop-filter: blur(10px);
  text-align: left;
}}

.discovery-narration {{
  background: rgba(255,255,255,0.9);
  border: 2px solid var(--accent);
  font-size: clamp(18px, 4vw, 22px);
  text-align: center;
}}

/* ── Sound Effect ───────────────────────────── */
.page-sfx {{
  font-size: clamp(36px, 10vw, 64px);
  font-weight: 900;
  color: var(--sfx);
  margin: 12px 0;
  transform: rotate(-3deg);
  text-shadow: 3px 3px 0 rgba(0,0,0,0.08);
  animation: sfxPop 0.6s ease-out;
}}

@keyframes sfxPop {{
  0% {{ transform: scale(0.5) rotate(-3deg); opacity: 0; }}
  60% {{ transform: scale(1.1) rotate(-3deg); }}
  100% {{ transform: scale(1) rotate(-3deg); opacity: 1; }}
}}

/* ── Dialogue Bubbles ───────────────────────── */
.dialogues-container {{
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 16px 0;
  text-align: left;
}}

.bubble {{
  background: var(--bubble);
  border-radius: 18px;
  padding: 14px 18px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.06);
  border: 2px solid transparent;
  animation: bubbleIn 0.4s ease-out;
}}

.bubble-happy {{ border-color: #FFD93D; }}
.bubble-surprised {{ border-color: #FF6B6B; }}
.bubble-thinking {{ border-color: #74B9FF; }}
.bubble-sad {{ border-color: #A29BFE; }}
.bubble-brave {{ border-color: #FF9F43; }}
.bubble-excited {{ border-color: #FD79A8; }}
.bubble-scared {{ border-color: #DFE6E9; }}
.bubble-love {{ border-color: #FD79A8; }}

@keyframes bubbleIn {{
  0% {{ opacity: 0; transform: scale(0.9) translateY(10px); }}
  100% {{ opacity: 1; transform: scale(1) translateY(0); }}
}}

.bubble-header {{
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}}

.bubble-avatar {{
  font-size: 24px;
  line-height: 1;
}}

.bubble-name {{
  font-size: 13px;
  font-weight: 700;
  color: var(--text2);
}}

.bubble-text {{
  font-size: clamp(16px, 3.5vw, 20px);
  color: var(--text);
  line-height: 1.5;
}}

.bubble-compact {{
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
}}

.bubble-text-compact {{
  font-size: clamp(14px, 3vw, 18px);
  color: var(--text);
}}

/* ── Cover Page ─────────────────────────────── */
.cover-content {{
  text-align: center;
}}

.cover-emoji {{
  font-size: clamp(80px, 20vw, 140px);
  margin-bottom: 20px;
  animation: bounce 2.5s ease-in-out infinite;
  line-height: 1;
}}

.cover-title {{
  font-size: clamp(28px, 7vw, 48px);
  font-weight: 900;
  color: var(--text);
  line-height: 1.2;
  margin-bottom: 12px;
  text-shadow: 0 2px 4px rgba(0,0,0,0.06);
}}

.cover-mood {{
  font-size: clamp(14px, 3vw, 18px);
  color: var(--text2);
  margin-bottom: 8px;
}}

.cover-chars {{
  font-size: 40px;
  margin: 16px 0;
  letter-spacing: 8px;
}}

.cover-badge {{
  display: inline-block;
  padding: 6px 20px;
  background: var(--accent);
  color: white;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
  margin-top: 20px;
}}

/* ── Discovery Page ─────────────────────────── */
.discovery-glow {{
  font-size: clamp(70px, 18vw, 120px);
  margin-bottom: 16px;
  animation: glow 1.5s ease-in-out infinite alternate;
  line-height: 1;
}}

@keyframes glow {{
  0% {{ transform: scale(1); filter: brightness(1); }}
  100% {{ transform: scale(1.1); filter: brightness(1.2); }}
}}

.discovery-title {{
  color: var(--accent) !important;
  font-size: clamp(24px, 6vw, 36px) !important;
}}

/* ── Ending Page ────────────────────────────── */
.ending-content {{
  text-align: center;
}}

.ending-emoji {{
  font-size: clamp(60px, 15vw, 100px);
  margin-bottom: 16px;
  animation: float 3s ease-in-out infinite;
  line-height: 1;
}}

.ending-title {{
  font-size: clamp(24px, 6vw, 36px);
  font-weight: 800;
  color: var(--text);
  margin-bottom: 16px;
}}

.ending-story {{
  font-size: clamp(16px, 3.5vw, 20px);
  color: var(--narration);
  line-height: 1.8;
  margin: 16px 0;
  padding: 16px 24px;
  background: rgba(255,255,255,0.8);
  border-radius: 16px;
}}

.ending-moral {{
  font-size: clamp(14px, 3vw, 18px);
  color: var(--accent);
  font-weight: 600;
  margin: 20px 0;
  padding: 12px 20px;
  background: rgba(255,255,255,0.6);
  border-radius: 12px;
  border: 2px dashed var(--accent);
}}

.ending-mark {{
  font-size: 14px;
  color: var(--footer);
  margin-top: 32px;
  letter-spacing: 4px;
}}

/* ── Page Footer ────────────────────────────── */
.page-footer {{
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 12px;
  color: var(--footer);
  letter-spacing: 2px;
  z-index: 3;
  white-space: nowrap;
}}

/* ── Responsive ─────────────────────────────── */
@media (max-width: 480px) {{
  .comic-page {{ padding: 32px 16px; }}
  .page-narration {{ padding: 12px 16px; }}
  .bubble {{ padding: 10px 14px; }}
  .cover-chars {{ font-size: 32px; }}
}}

@media (min-width: 768px) {{
  .page-content {{ max-width: 560px; }}
  .comic-page {{ padding: 60px 40px; }}
}}

/* Print / PDF friendly */
@media print {{
  .comic-page {{
    page-break-after: always;
    min-height: 100vh;
    opacity: 1 !important;
    transform: none !important;
  }}
  .comic-container {{ overflow: visible; height: auto; }}
}}
'''
