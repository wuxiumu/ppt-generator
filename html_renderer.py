"""HTML slide renderer — produces a single self-contained HTML file with
   modern CSS (gradients, glassmorphism, animations, scroll-snap navigation)."""

import html as html_lib
import json

# ── Color Palettes (same as PPTX renderer) ────────────────
PALETTES = {
    "tech": {
        "bg": "#FAFBFC", "surface": "#EEF0F5",
        "text": "#1A1A2E", "text2": "#4A4A6A", "text3": "#8888AA",
        "accent1": "#6C63FF", "accent2": "#00D2FF", "accent3": "#FF6B6B", "accent4": "#2ED573",
        "on_accent": "#FFFFFF", "divider": "#E2E8F0", "code_bg": "#1E1E2E",
        "grad1": "linear-gradient(135deg, #6C63FF 0%, #00D2FF 100%)",
        "grad2": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    },
    "warm": {
        "bg": "#FFF8F0", "surface": "#FFF0E0",
        "text": "#2D1B00", "text2": "#6B4E37", "text3": "#A08B7A",
        "accent1": "#C67B5C", "accent2": "#E87461", "accent3": "#4A7C59", "accent4": "#F4C542",
        "on_accent": "#FFFFFF", "divider": "#E8D5C4", "code_bg": "#2D1B00",
        "grad1": "linear-gradient(135deg, #C67B5C 0%, #F4C542 100%)",
        "grad2": "linear-gradient(135deg, #E87461 0%, #C67B5C 100%)",
    },
    "corporate": {
        "bg": "#FFFFFF", "surface": "#F7FAFC",
        "text": "#1A202C", "text2": "#4A5568", "text3": "#A0AEC0",
        "accent1": "#2B6CB0", "accent2": "#ED8936", "accent3": "#38A169", "accent4": "#E53E3E",
        "on_accent": "#FFFFFF", "divider": "#E2E8F0", "code_bg": "#1A202C",
        "grad1": "linear-gradient(135deg, #2B6CB0 0%, #38A169 100%)",
        "grad2": "linear-gradient(135deg, #2B6CB0 0%, #ED8936 100%)",
    },
    "personal": {
        "bg": "#FFFDF7", "surface": "#FAF5FF",
        "text": "#2D3748", "text2": "#718096", "text3": "#A0AEC0",
        "accent1": "#9F7AEA", "accent2": "#F687B3", "accent3": "#68D391", "accent4": "#FBD38D",
        "on_accent": "#FFFFFF", "divider": "#E9D8FD", "code_bg": "#2D3748",
        "grad1": "linear-gradient(135deg, #9F7AEA 0%, #F687B3 100%)",
        "grad2": "linear-gradient(135deg, #667eea 0%, #9F7AEA 100%)",
    },
    "dark": {
        "bg": "#0F172A", "surface": "#1E293B",
        "text": "#F8FAFC", "text2": "#CBD5E1", "text3": "#64748B",
        "accent1": "#818CF8", "accent2": "#34D399", "accent3": "#FB923C", "accent4": "#F472B6",
        "on_accent": "#0F172A", "divider": "#334155", "code_bg": "#020617",
        "grad1": "linear-gradient(135deg, #818CF8 0%, #34D399 100%)",
        "grad2": "linear-gradient(135deg, #818CF8 0%, #F472B6 100%)",
    },
}


class HTMLRenderer:
    """Renders slide data into a single self-contained HTML file."""

    def render(self, slides: list[dict], palette_name: str,
               topic: str = "", out: str = "output.html") -> str:
        pal = PALETTES.get(palette_name, PALETTES["tech"])
        total = len(slides)
        slides_html = "\n".join(
            self._render_slide(s, pal, i + 1, total) for i, s in enumerate(slides)
        )

        doc = self._wrap(topic, pal, slides_html, total)
        with open(out, "w", encoding="utf-8") as f:
            f.write(doc)
        return out

    # ── Slide dispatcher ────────────────────────────────────

    def _render_slide(self, s: dict, pal: dict, num: int, total: int) -> str:
        layout = s.get("layout", "bullets")
        fn = {
            "title": self._slide_title,
            "section": self._slide_section,
            "bullets": self._slide_bullets,
            "statement": self._slide_statement,
            "comparison": self._slide_comparison,
            "big_number": self._slide_big_number,
            "code": self._slide_code,
            "end": self._slide_end,
        }.get(layout, self._slide_bullets)
        inner = fn(s, pal)
        page_num = f'<div class="page-num">{num} / {total}</div>' if layout not in ("title", "end") else ""
        return f'<section class="slide slide-{layout}" data-slide="{num}">\n{inner}\n{page_num}\n</section>'

    # ── Helpers ─────────────────────────────────────────────

    def _esc(self, text: str) -> str:
        return html_lib.escape(str(text)) if text else ""

    def _nl2br(self, text: str) -> str:
        return self._esc(text).replace("\n", "<br>") if text else ""

    # ── Layout renderers ────────────────────────────────────

    def _slide_title(self, s: dict, pal: dict) -> str:
        title = self._esc(s.get("title", ""))
        subtitle = self._esc(s.get("subtitle", s.get("body_text", "")))
        return f"""
        <div class="title-content">
            <div class="accent-bar"></div>
            <h1 class="title-text">{title}</h1>
            <p class="subtitle-text">{subtitle}</p>
            <div class="deco-circle c1"></div>
            <div class="deco-circle c2"></div>
        </div>"""

    def _slide_section(self, s: dict, pal: dict) -> str:
        act = s.get("act", s.get("slide_num", ""))
        num = f"{act:02d}" if isinstance(act, int) else str(act)
        title = self._esc(s.get("title", ""))
        subtitle = self._esc(s.get("subtitle", s.get("body_text", "")))
        return f"""
        <div class="section-content">
            <div class="section-number">{num}</div>
            <h2 class="section-title">{title}</h2>
            <p class="section-subtitle">{subtitle}</p>
            <div class="deco-circle c3"></div>
        </div>"""

    def _slide_bullets(self, s: dict, pal: dict) -> str:
        title = self._esc(s.get("title", ""))
        bullets = s.get("bullets", [])
        body = self._esc(s.get("body_text", ""))
        items = "\n".join(
            f'<li><span class="bullet-dot"></span><span class="bullet-text">{self._esc(b)}</span></li>'
            for b in bullets
        )
        body_html = f'<p class="body-text">{body}</p>' if body else ""
        return f"""
        <div class="bullets-content">
            <div class="accent-bar"></div>
            <h2 class="slide-title">{title}</h2>
            <ul class="bullet-list">{items}</ul>
            {body_html}
        </div>"""

    def _slide_statement(self, s: dict, pal: dict) -> str:
        text = self._esc(s.get("title", s.get("body_text", "")))
        attr = self._esc(s.get("subtitle", ""))
        attr_html = f'<p class="attr-text">— {attr}</p>' if attr else ""
        return f"""
        <div class="statement-content">
            <div class="quote-mark">\u201c</div>
            <blockquote class="statement-text">{text}</blockquote>
            {attr_html}
        </div>"""

    def _slide_comparison(self, s: dict, pal: dict) -> str:
        title = self._esc(s.get("title", ""))
        lt = self._esc(s.get("left_title", ""))
        rt = self._esc(s.get("right_title", ""))
        left = s.get("left_bullets", s.get("bullets", []))
        right = s.get("right_bullets", [])
        left_items = "\n".join(f"<li>{self._esc(b)}</li>" for b in left)
        right_items = "\n".join(f"<li>{self._esc(b)}</li>" for b in right)
        return f"""
        <div class="comparison-content">
            <h2 class="slide-title">{title}</h2>
            <div class="compare-grid">
                <div class="compare-col col-left">
                    <h3>{lt}</h3>
                    <ul>{left_items}</ul>
                </div>
                <div class="compare-divider"></div>
                <div class="compare-col col-right">
                    <h3>{rt}</h3>
                    <ul>{right_items}</ul>
                </div>
            </div>
        </div>"""

    def _slide_big_number(self, s: dict, pal: dict) -> str:
        number = self._esc(s.get("highlight", s.get("title", "")))
        label = self._esc(s.get("title", ""))
        ctx = self._esc(s.get("body_text", s.get("subtitle", "")))
        ctx_html = f'<p class="bn-context">{ctx}</p>' if ctx else ""
        return f"""
        <div class="big-number-content">
            <div class="bn-number">{number}</div>
            <h3 class="bn-label">{label}</h3>
            {ctx_html}
        </div>"""

    def _slide_code(self, s: dict, pal: dict) -> str:
        title = self._esc(s.get("title", ""))
        code = self._esc(s.get("code", s.get("body_text", "")))
        notes = s.get("annotations", s.get("bullets", []))
        note_items = "\n".join(
            f'<div class="note-item"><span class="note-arrow">→</span>{self._esc(n)}</div>'
            for n in notes
        )
        return f"""
        <div class="code-content">
            <h2 class="slide-title">{title}</h2>
            <div class="code-grid">
                <pre class="code-block"><code>{code}</code></pre>
                <div class="code-notes">{note_items}</div>
            </div>
        </div>"""

    def _slide_end(self, s: dict, pal: dict) -> str:
        thanks = self._esc(s.get("title", "谢谢"))
        contact = self._esc(s.get("body_text", s.get("subtitle", "")))
        contact_html = f'<p class="end-contact">{contact}</p>' if contact else ""
        return f"""
        <div class="end-content">
            <h1 class="end-thanks">{thanks}</h1>
            {contact_html}
            <div class="deco-circle c4"></div>
            <div class="deco-circle c5"></div>
        </div>"""

    # ── HTML wrapper with CSS + JS ──────────────────────────

    def _wrap(self, topic: str, pal: dict, slides_html: str, total: int) -> str:
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{self._esc(topic)}</title>
<style>
/* ── Reset & Base ─────────────────────────────── */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

:root {{
    --bg: {pal['bg']};
    --surface: {pal['surface']};
    --text: {pal['text']};
    --text2: {pal['text2']};
    --text3: {pal['text3']};
    --accent1: {pal['accent1']};
    --accent2: {pal['accent2']};
    --accent3: {pal['accent3']};
    --accent4: {pal['accent4']};
    --on-accent: {pal['on_accent']};
    --divider: {pal['divider']};
    --code-bg: {pal['code_bg']};
    --grad1: {pal['grad1']};
    --grad2: {pal['grad2']};
    --slide-w: min(100vw, 177.78vh);
    --slide-h: min(56.25vw, 100vh);
}}

html {{
    scroll-snap-type: y mandatory;
    scroll-behavior: smooth;
    overflow-y: scroll;
    overflow-x: hidden;
}}

body {{
    font-family: "PingFang SC", "Microsoft YaHei", -apple-system, "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--text);
    -webkit-font-smoothing: antialiased;
}}

/* ── Slide Base ───────────────────────────────── */
.slide {{
    width: var(--slide-w);
    height: var(--slide-h);
    scroll-snap-align: start;
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 5vh 6vw;
    overflow: hidden;
    background: var(--bg);
}}

.slide > div:first-child {{
    width: 100%;
    max-width: 1100px;
    animation: fadeUp 0.5s ease-out;
}}

@keyframes fadeUp {{
    from {{ opacity: 0; transform: translateY(20px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}

.page-num {{
    position: absolute;
    bottom: 3vh;
    right: 4vw;
    font-size: clamp(10px, 1.2vh, 14px);
    color: var(--text3);
    font-variant-numeric: tabular-nums;
}}

/* ── Title Slide ──────────────────────────────── */
.slide-title {{
    background: var(--bg);
    position: relative;
}}
.title-content {{
    position: relative;
    z-index: 1;
}}
.title-content .accent-bar {{
    width: 4px;
    height: 80px;
    background: var(--accent1);
    border-radius: 2px;
    margin-bottom: 2.5vh;
}}
.title-text {{
    font-size: clamp(28px, 5vh, 56px);
    font-weight: 800;
    line-height: 1.2;
    color: var(--text);
    margin-bottom: 2vh;
    letter-spacing: -0.02em;
}}
.subtitle-text {{
    font-size: clamp(16px, 2.5vh, 26px);
    color: var(--text2);
    font-weight: 400;
    line-height: 1.5;
}}
.deco-circle {{
    position: absolute;
    border-radius: 50%;
    opacity: 0.12;
    pointer-events: none;
}}
.title-content .c1 {{
    width: 220px; height: 220px;
    background: var(--accent1);
    right: -40px; bottom: -30px;
}}
.title-content .c2 {{
    width: 140px; height: 140px;
    background: var(--accent2);
    right: 60px; bottom: 80px;
}}

/* ── Section Slide ────────────────────────────── */
.slide-section {{
    background: var(--grad1);
}}
.section-content {{
    color: var(--on-accent);
    position: relative;
}}
.section-number {{
    font-size: clamp(60px, 12vh, 120px);
    font-weight: 900;
    opacity: 0.25;
    line-height: 1;
    margin-bottom: 1vh;
    font-family: "Impact", "Arial Black", sans-serif;
}}
.section-title {{
    font-size: clamp(24px, 4.5vh, 48px);
    font-weight: 700;
    margin-bottom: 1.5vh;
}}
.section-subtitle {{
    font-size: clamp(14px, 2vh, 22px);
    opacity: 0.8;
}}
.section-content .c3 {{
    width: 300px; height: 300px;
    background: var(--accent2);
    right: -80px; top: -60px;
    opacity: 0.08;
}}

/* ── Bullets Slide ────────────────────────────── */
.bullets-content {{
    position: relative;
}}
.bullets-content .accent-bar {{
    width: 4px;
    height: 36px;
    background: var(--accent1);
    border-radius: 2px;
    margin-bottom: 1.5vh;
}}
.slide-title {{
    font-size: clamp(20px, 3.5vh, 36px);
    font-weight: 700;
    margin-bottom: 3vh;
    color: var(--text);
}}
.bullet-list {{
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 1.8vh;
}}
.bullet-list li {{
    display: flex;
    align-items: flex-start;
    gap: 12px;
    font-size: clamp(14px, 2.2vh, 22px);
    line-height: 1.6;
    color: var(--text);
}}
.bullet-dot {{
    flex-shrink: 0;
    width: 8px; height: 8px;
    background: var(--accent1);
    border-radius: 50%;
    margin-top: 0.6em;
}}
.body-text {{
    margin-top: 3vh;
    font-size: clamp(13px, 1.8vh, 18px);
    color: var(--text2);
    line-height: 1.7;
}}

/* ── Statement Slide ──────────────────────────── */
.slide-statement {{
    background: var(--bg);
}}
.statement-content {{
    text-align: center;
    max-width: 85%;
    margin: 0 auto;
}}
.quote-mark {{
    font-size: clamp(50px, 10vh, 100px);
    color: var(--accent1);
    opacity: 0.3;
    line-height: 0.5;
    font-family: Georgia, serif;
    margin-bottom: 2vh;
}}
.statement-text {{
    font-size: clamp(20px, 3.5vh, 38px);
    font-weight: 600;
    line-height: 1.6;
    color: var(--text);
    border: none;
    padding: 0;
    margin: 0;
}}
.attr-text {{
    margin-top: 3vh;
    font-size: clamp(13px, 1.8vh, 18px);
    color: var(--text3);
    font-style: italic;
}}

/* ── Comparison Slide ─────────────────────────── */
.comparison-content .slide-title {{
    margin-bottom: 3vh;
}}
.compare-grid {{
    display: grid;
    grid-template-columns: 1fr 2px 1fr;
    gap: 0 3vw;
    align-items: start;
}}
.compare-divider {{
    background: var(--divider);
    height: 100%;
    min-height: 200px;
    border-radius: 1px;
}}
.compare-col h3 {{
    font-size: clamp(16px, 2.3vh, 24px);
    font-weight: 700;
    margin-bottom: 2vh;
    padding-bottom: 1vh;
}}
.col-left h3 {{ color: var(--accent1); border-bottom: 2px solid var(--accent1); }}
.col-right h3 {{ color: var(--accent2); border-bottom: 2px solid var(--accent2); }}
.compare-col ul {{
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 1.2vh;
}}
.compare-col li {{
    font-size: clamp(13px, 1.9vh, 19px);
    line-height: 1.5;
    color: var(--text);
    padding-left: 16px;
    position: relative;
}}
.compare-col li::before {{
    content: "●";
    position: absolute;
    left: 0;
    font-size: 8px;
    top: 0.4em;
}}
.col-left li::before {{ color: var(--accent1); }}
.col-right li::before {{ color: var(--accent2); }}

/* ── Big Number Slide ─────────────────────────── */
.big-number-content {{
    text-align: center;
}}
.bn-number {{
    font-size: clamp(60px, 14vh, 140px);
    font-weight: 900;
    background: var(--grad1);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1.1;
    font-family: "Impact", "Arial Black", sans-serif;
}}
.bn-label {{
    font-size: clamp(18px, 2.8vh, 30px);
    font-weight: 600;
    color: var(--text);
    margin-top: 2vh;
}}
.bn-context {{
    font-size: clamp(13px, 1.8vh, 18px);
    color: var(--text2);
    margin-top: 1.5vh;
}}

/* ── Code Slide ───────────────────────────────── */
.code-content .slide-title {{
    margin-bottom: 2.5vh;
}}
.code-grid {{
    display: grid;
    grid-template-columns: 1.2fr 0.8fr;
    gap: 3vw;
    align-items: start;
}}
.code-block {{
    background: var(--code-bg);
    border-radius: 12px;
    padding: 2.5vh 2vw;
    overflow-x: auto;
    box-shadow: 0 4px 24px rgba(0,0,0,0.12);
}}
.code-block code {{
    font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
    font-size: clamp(11px, 1.5vh, 16px);
    line-height: 1.7;
    color: #D4D4D4;
    white-space: pre;
}}
.code-notes {{
    display: flex;
    flex-direction: column;
    gap: 1.5vh;
    padding-top: 1vh;
}}
.note-item {{
    font-size: clamp(12px, 1.7vh, 17px);
    color: var(--text2);
    line-height: 1.5;
    display: flex;
    gap: 8px;
}}
.note-arrow {{
    color: var(--accent1);
    font-weight: 700;
    flex-shrink: 0;
}}

/* ── End Slide ────────────────────────────────── */
.slide-end {{
    background: var(--grad1);
}}
.end-content {{
    text-align: center;
    color: var(--on-accent);
    position: relative;
}}
.end-thanks {{
    font-size: clamp(32px, 6vh, 64px);
    font-weight: 800;
    letter-spacing: 0.05em;
}}
.end-contact {{
    margin-top: 3vh;
    font-size: clamp(14px, 2vh, 20px);
    opacity: 0.85;
}}
.end-content .c4 {{
    width: 160px; height: 160px;
    background: var(--accent2);
    left: -40px; top: -30px;
    opacity: 0.1;
}}
.end-content .c5 {{
    width: 120px; height: 120px;
    background: var(--accent2);
    right: -20px; bottom: -20px;
    opacity: 0.1;
}}

/* ── Navigation hint ──────────────────────────── */
.nav-hint {{
    position: fixed;
    bottom: 12px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 12px;
    color: var(--text3);
    opacity: 0.6;
    z-index: 100;
    pointer-events: none;
    transition: opacity 0.3s;
}}
</style>
</head>
<body>

{slides_html}

<div class="nav-hint">↑ ↓ 翻页 &nbsp;|&nbsp; 点击两侧区域翻页</div>

<script>
// Keyboard navigation
document.addEventListener('keydown', (e) => {{
    const h = window.innerHeight;
    if (e.key === 'ArrowDown' || e.key === ' ' || e.key === 'PageDown') {{
        e.preventDefault();
        window.scrollBy({{ top: h, behavior: 'smooth' }});
    }} else if (e.key === 'ArrowUp' || e.key === 'PageUp') {{
        e.preventDefault();
        window.scrollBy({{ top: -h, behavior: 'smooth' }});
    }} else if (e.key === 'Home') {{
        e.preventDefault();
        window.scrollTo({{ top: 0, behavior: 'smooth' }});
    }} else if (e.key === 'End') {{
        e.preventDefault();
        window.scrollTo({{ top: document.body.scrollHeight, behavior: 'smooth' }});
    }}
}});

// Click sides to navigate
document.addEventListener('click', (e) => {{
    const x = e.clientX / window.innerWidth;
    const y = e.clientY / window.innerHeight;
    // Only trigger on side areas (left/right 15%), not center
    if (y > 0.2 && y < 0.8) {{
        if (x < 0.15) {{
            window.scrollBy({{ top: -window.innerHeight, behavior: 'smooth' }});
        }} else if (x > 0.85) {{
            window.scrollBy({{ top: window.innerHeight, behavior: 'smooth' }});
        }}
    }}
}});

// Hide nav hint after 5s
setTimeout(() => {{
    document.querySelector('.nav-hint').style.opacity = '0';
}}, 5000);
</script>
</body>
</html>"""
