# AI亲子故事漫画生成器 — 设计文档

## 产品定位

在现有 PPT Generator 基础上，扩展一个"AI亲子故事漫画生成器"模块。输入主题和孩子名字，3 分钟生成一本 8-12 页的专属亲子漫画。

**目标场景**：睡前故事、行为引导、生日/节日礼物、知识科普

**技术策略**：复用现有 Flask 后台 / 登录系统 / LLM 客户端，新增漫画专属管线和渲染器。

---

## 1. 架构总览

```
                    ┌─────────────────────────────┐
                    │     现有 PPT Generator       │
                    │  main.py / renderer.py       │
                    │  html_renderer.py            │
                    └──────────────┬──────────────┘
                                   │
           共享层: llm.py / auth / gen_status / PROVIDERS / projects/
                                   │
                    ┌──────────────┴──────────────┐
                    │    新增 Comic Generator      │
                    │  comic_main.py (2-stage)     │
                    │  comic_renderer.py (HTML)    │
                    │  comic_pdf.py (PDF)          │
                    │  comic-admin/ (前端tab)      │
                    └─────────────────────────────┘
```

### 与现有系统的关系

| 组件 | PPT Generator | Comic Generator | 共享方式 |
|------|--------------|-----------------|---------|
| LLM 客户端 | `llm.py` | 同 | 直接引用 |
| 认证 | `app.py` auth | 同 | `before_request` 自动保护 |
| 项目存储 | `projects/<pid>/` | `projects/<cid>/` | 同结构，`type` 字段区分 |
| 生成状态 | `gen_status` | `comic_gen_status` | 同模式，独立 dict |
| Provider | `PROVIDERS` | 同 | 直接引用 |
| 前端 | `admin-html/` | `comic-admin/` | 独立 SPA，共享登录 |
| API 前缀 | `/api/projects/` | `/api/comics/` | Flask Blueprint |

---

## 2. 两阶段管线 (comic_main.py)

### 数据流

```
输入 JSON                        Stage 1                 Stage 2                  Stage 3
{topic, child_name,          →  story_plan()  →  plan  →  write_pages()  →  pages  →  ComicRenderer
 age, template}                    (1 LLM call)           (8-12 parallel       (0 LLM,
                                    ~2000 tokens           LLM calls, 3         纯渲染)
                                                         concurrent)
```

### 输入 Schema

```json
{
  "topic": "小明的牙齿王国冒险",
  "child_name": "小明",
  "age": 5,
  "template": "behavior_guide",
  "extra": "不爱刷牙，喜欢吃糖"
}
```

### Stage 1: 故事规划 (story_plan)

**系统提示词**：
```
你是一位儿童故事作家。你擅长为3-8岁的孩子创作有趣、温暖、有教育意义的短篇漫画故事。
故事要有明确的起承转合，语言简单活泼，适合亲子共读。
输出纯JSON，不要markdown包裹。
```

**用户提示词模板**：
```
为以下孩子创作一本8-12页的亲子漫画故事。

## 基本信息
- 主题: {topic}
- 主角名字: {child_name}
- 年龄: {age}岁
- 故事类型: {template}
- 补充: {extra}

## 故事类型说明
- bedtime: 睡前故事，节奏舒缓，温暖结尾
- behavior_guide: 行为引导，通过冒险让孩子理解道理
- birthday: 生日庆祝，充满惊喜和祝福
- science: 知识科普，用故事解释科学现象
- fairy_tale: 奇幻冒险，充满想象力

## 叙事结构 (三幕式)
- 开场 (1-2页): 介绍主角和日常世界
- 冒险 (5-7页): 遇到问题/进入新世界/经历挑战
- 收尾 (2-3页): 解决/回家/获得成长

## 页面类型 (7种)
cover / intro / scene / dialogue / action / discovery / ending

## 配色方案 (4种)
warm_pastel(暖粉) / bright_fun(明亮) / soft_edu(柔和教育) / festive(节日金)

## 输出JSON
{
  "title": "漫画标题",
  "palette": "配色方案",
  "moral": "故事寓意(一句话)",
  "style": "画风描述",
  "characters": [
    {"name": "角色名", "emoji": "🧒", "desc": "角色描述"}
  ],
  "page_plan": [
    {
      "n": 1,
      "act": 1,
      "page_type": "cover",
      "brief": "80字以内的画面描述",
      "scene_emoji": "🏠",
      "mood": "情绪关键词"
    }
  ]
}
```

### Stage 2: 内容生成 (write_pages)

**系统提示词**：
```
你是儿童漫画内容撰稿人。为单页漫画撰写温暖有趣的文字内容。
语言要适合3-8岁孩子理解，活泼可爱，多用拟声词和感叹句。
输出纯JSON，不要markdown包裹。
```

**用户提示词模板**：
```
为漫画第 {num} 页撰写内容。

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

## 风格
- 画风: {style}

## 输出JSON
{
  "title": "页面标题(≤8字)",
  "story_text": "旁白文字(≤60字，适合朗读)",
  "dialogue": [
    {"character": "角色名", "text": "对白", "emotion": "happy/surprised/thinking"}
  ],
  "sound_effect": "拟声词(可选, 如：咔嚓！噗通！)",
  "scene_emojis": ["场景装饰emoji1", "emoji2", "emoji3"],
  "page_num": {num},
  "page_type": "{page_type}"
}
```

### Stage 3: 渲染 (comic_renderer.py / comic_pdf.py)

纯代码，不调用 LLM。

---

## 3. 页面类型系统 (7 种)

| 类型 | 用途 | 视觉特征 |
|------|------|---------|
| `cover` | 封面 | 大标题 + 主角emoji + 装饰背景 + 作者信息 |
| `intro` | 介绍主角 | 角色展示 + 日常描述 + 暖色调 |
| `scene` | 场景叙述 | 旁白为主 + 场景emoji装饰 + 氛围背景 |
| `dialogue` | 对话互动 | 气泡对话框 + 角色emoji + 表情标签 |
| `action` | 动作场景 | 拟声词大字 + 动态emoji + 渐变背景 |
| `discovery` | 发现/转折 | 高亮重点 + 惊喜emoji + 对比色 |
| `ending` | 结尾 | 温暖总结 + 寓意 + "故事结束"标记 |

---

## 4. 配色方案 (4 种)

| 名称 | 适用场景 | 主色 |
|------|---------|------|
| `warm_pastel` | 睡前故事 | 淡粉 #FFE0EC / 暖黄 #FFF3CD / 淡蓝 #D4E6F1 |
| `bright_fun` | 冒险故事 | 亮橙 #FF9F43 / 天蓝 #54A0FF / 草绿 #5CD859 |
| `soft_edu` | 知识科普 | 柔蓝 #74B9FF / 淡绿 #00B894 / 米白 #FFF8E7 |
| `festive` | 生日/节日 | 金 #FDCB6E / 红 #E17055 / 紫 #A29BFE |

每个配色包含：背景色、面板色、文字色、强调色、气泡色、渐变方向。

---

## 5. 叙事模板 (6 种)

| 模板 | 默认页数 | 叙事重点 |
|------|---------|---------|
| `bedtime` | 8 | 舒缓节奏，温暖收尾，"晚安"结尾 |
| `behavior_guide` | 10 | 问题→冒险→理解道理→改变 |
| `birthday` | 8 | 惊喜层层递进，祝福结尾 |
| `science` | 10 | 提问→探索→发现→原来如此 |
| `fairy_tale` | 12 | 完整英雄旅程 |
| `custom` | 10 | 通用模板 |

---

## 6. CSS 插画系统 (Phase 1)

### 设计理念

"零图片、纯 CSS"的漫画风格，类似现代 Webtoon 的极简风：

```
┌──────────────────────────────────┐
│  🌙  🌟        🌟    ✨         │  ← 场景emoji装饰层
│                                  │
│  ┌─────────────────────────────┐ │
│  │  🧒 小明                    │ │  ← 角色展示区
│  │                             │ │
│  │  ╭──────────────╮          │ │
│  │  │ "哇！好大    │          │ │  ← 对话气泡
│  │  │  的月亮！"   │          │ │
│  │  ╰──────────────╯          │ │
│  │                             │ │
│  │  小明抬头望着天空...         │ │  ← 旁白文字
│  └─────────────────────────────┘ │
│                                  │
│  ── 第 3 页 / 共 10 页 ──       │  ← 页码
└──────────────────────────────────┘
```

### 每页结构

```html
<div class="comic-page page-{type}" data-page="3">
  <div class="page-bg"></div>                    <!-- 渐变背景 -->
  <div class="page-decorations">                 <!-- emoji装饰层 -->
    <span class="deco" style="top:10%;left:5%">🌙</span>
    <span class="deco" style="top:15%;right:10%">⭐</span>
  </div>
  <div class="page-content">                     <!-- 主内容区 -->
    <div class="page-title">月光下的约定</div>
    <div class="page-illustration">              <!-- emoji角色展示 -->
      <div class="character">🧒</div>
    </div>
    <div class="page-dialogues">                 <!-- 对话气泡 -->
      <div class="bubble bubble-happy">
        <span class="bubble-name">小明</span>
        <span class="bubble-text">哇！好大的月亮！</span>
      </div>
    </div>
    <div class="page-narration">                 <!-- 旁白 -->
      小明抬头望着天空，心里许下了一个愿望...
    </div>
    <div class="page-sfx">咔嚓！</div>          <!-- 拟声词 -->
  </div>
  <div class="page-footer">                      <!-- 页码 -->
    <span>── 第 3 页 ──</span>
  </div>
</div>
```

### AI 图片预留接口

```python
class ComicRenderer:
    def __init__(self, image_provider: str = "css"):
        """
        image_provider:
          - "css": 纯 CSS 插画 (默认, 零成本)
          - "dalle": OpenAI DALL-E 3 (高质量, ~$0.04/张)
          - "stable": Stable Diffusion (本地/远程)
        """
        self.image_provider = image_provider

    async def generate_illustration(self, prompt: str, style: str) -> str:
        """为单页生成插画，返回图片 URL/base64"""
        if self.image_provider == "css":
            return None  # 使用 CSS 插画
        elif self.image_provider == "dalle":
            return await self._call_dalle(prompt, style)
        # ... 其他 provider
```

Phase 1 使用纯 CSS，后续升级时只需实现 `generate_illustration()` 并在 HTML 中插入 `<img>` 标签。

---

## 7. HTML 渲染器 (comic_renderer.py)

### 输出格式

单文件自包含 HTML，竖向长卷滚动阅读：

```
封面 (全屏) → 故事页×10 (竖屏比例) → 结尾 (全屏)
```

### 技术选型

- 竖屏滑动阅读，适合手机/平板
- CSS scroll-snap（每页一屏）
- 动画效果：页面淡入 + emoji 微动画
- 触摸滑动 + 键盘导航
- 响应式：手机竖屏 / 平板 / 桌面横屏均适配

### 关键 CSS 特性

```css
/* 每页占满视口 */
.comic-page {
  width: 100vw;
  min-height: 100vh;
  scroll-snap-align: start;
}

/* 角色emoji动画 */
.character {
  font-size: 80px;
  animation: bounce 2s ease-in-out infinite;
}

/* 对话气泡 */
.bubble {
  position: relative;
  background: white;
  border-radius: 20px;
  padding: 12px 18px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

/* 拟声词 */
.page-sfx {
  font-size: 48px;
  font-weight: 900;
  transform: rotate(-5deg);
  text-shadow: 3px 3px 0 rgba(0,0,0,0.1);
}
```

---

## 8. PDF 渲染器 (comic_pdf.py)

### 方案

使用 `weasyprint` 将 HTML 漫画转换为 PDF：

```python
class ComicPDFRenderer:
    def render(self, pages, palette, title, out="comic.pdf"):
        # 1. 用 ComicRenderer 生成 HTML
        html_content = ComicRenderer().render_to_string(pages, palette, title)
        # 2. 转换为 PDF (A4竖版, 适合打印)
        weasyprint.HTML(string=html_content).write_pdf(out)
        return out
```

### 备选方案

如果 `weasyprint` 依赖过重，可退到 `reportlab` 或 `pdfkit`（wkhtmltopdf）。

---

## 9. 后端 API 设计

### Flask Blueprint: `comic_bp`

```python
comic_bp = Blueprint('comic', __name__)
```

### 路由

| Method | Path | 功能 |
|--------|------|------|
| GET | `/api/comics` | 列出所有漫画项目 |
| POST | `/api/comics` | 创建漫画项目 |
| GET | `/api/comics/<cid>` | 获取项目详情 |
| PUT | `/api/comics/<cid>` | 更新项目信息 |
| DELETE | `/api/comics/<cid>` | 删除项目 |
| POST | `/api/comics/<cid>/generate` | 启动生成 |
| GET | `/api/comics/<cid>/status` | 查询生成状态 |
| GET | `/api/comics/templates` | 获取叙事模板列表 |
| GET | `/api/comics/prompts/default` | 获取默认提示词 |

### 项目 JSON 结构

```json
{
  "type": "comic",
  "topic": "小明的牙齿王国冒险",
  "child_name": "小明",
  "age": 5,
  "template": "behavior_guide",
  "extra": "不爱刷牙",
  "story_plan": { ... },
  "pages": [ ... ],
  "plan": { "palette": "bright_fun", ... },
  "created_at": "...",
  "updated_at": "..."
}
```

### 与 PPT 项目的区分

项目列表中通过 `type` 字段区分。admin 前端按 type 过滤显示。
也可独立为两套 admin 前端：PPT 管理后台 + 漫画管理后台。

---

## 10. 前端设计 (comic-admin/)

### 方案：独立 SPA

创建 `comic-admin/` 目录，独立的前端页面。好处：
- 漫画项目有独特的交互需求（页面预览、角色编辑、故事线编辑）
- 不污染现有 PPT admin 的代码
- 共享同一个 Flask 后端和登录系统

### Tab 结构

| Tab | 功能 |
|-----|------|
| 故事信息 | 主题、孩子名字、年龄、模板选择、补充信息 |
| 提示词 | 故事规划/内容生成的系统/用户提示词编辑 |
| 故事预览 | 页面卡片列表，可视化预览每一页 |
| 生成 | 模型选择、格式选择(HTML/PDF)、生成按钮、进度 |
| 输出文件 | 生成的文件列表，预览/分享/下载 |

### 故事预览卡片

```
┌─────────────┐
│ 🌙 封面      │  ← 页码 + 类型
│             │
│ 小明和      │  ← 标题
│ 月亮朋友    │
│             │
│ 🧒  🌙  ⭐  │  ← emoji装饰
│             │
│ "哇！好大   │  ← 对白预览
│  的月亮！"  │
│             │
│ [编辑]      │
└─────────────┘
```

### 移动端适配

- 复用现有 CSS 响应式策略
- 故事预览卡片单列竖排
- 底部固定"生成"按钮（移动端常见模式）
- 分享：生成二维码，手机扫码阅读

---

## 11. 5 个 Demo 主题

| # | 主题 | 孩子名字 | 年龄 | 模板 | 配色 |
|---|------|---------|------|------|------|
| 1 | 小明和月亮做朋友 | 小明 | 4 | bedtime | warm_pastel |
| 2 | 牙齿王国大冒险 | 朵朵 | 5 | behavior_guide | bright_fun |
| 3 | 小星的生日蛋糕 | 小星 | 6 | birthday | festive |
| 4 | 为什么天空是蓝色的 | 乐乐 | 7 | science | soft_edu |
| 5 | 魔法森林的秘密 | 悠悠 | 5 | fairy_tale | bright_fun |

---

## 12. 成本与性能预估

| 阶段 | LLM 调用 | Token 估算 | 耗时 |
|------|---------|-----------|------|
| Stage 1: 故事规划 | 1 次 | ~2000 in / ~1500 out | ~5s |
| Stage 2: 内容生成 | 10 次(并发3) | ~500×10 in / ~300×10 out | ~15s |
| Stage 3: 渲染 | 0 | 0 | ~2s |
| **总计** | **11 次** | **~10K tokens** | **~22s** |

DeepSeek 成本：约 $0.005/本 (0.27×10K/1M + 1.1×6K/1M)

---

## 13. 文件清单

```
新增文件:
├── comic_main.py              # 漫画管线 (2-stage pipeline)
├── comic_renderer.py          # HTML 漫画渲染器 (CSS插画)
├── comic_pdf.py               # PDF 渲染器 (weasyprint)
├── comic-admin/
│   ├── index.html             # 漫画管理前端
│   ├── css/style.css          # 漫画前端样式
│   └── js/app.js              # 漫画前端逻辑
├── comic-inputs/
│   ├── 01-moon-friend.json
│   ├── 02-tooth-kingdom.json
│   ├── 03-birthday-cake.json
│   ├── 04-blue-sky.json
│   └── 05-magic-forest.json
└── doc/comic-design.md        # 本文件

修改文件:
├── app.py                     # 添加 comic Blueprint 路由
└── requirements.txt           # 添加 weasyprint (可选)
```

---

## 14. 实施顺序

1. **comic_main.py** — 管线核心，先跑通 CLI 生成
2. **comic_renderer.py** — HTML 渲染，CSS 插画系统
3. **app.py 路由** — Blueprint + 生成状态
4. **comic-admin/** — 前端管理页面
5. **comic_pdf.py** — PDF 输出
6. **5 个 Demo** — 生成示例漫画
7. **AI 图片接口** — (Phase 2) DALL-E 集成
