# ppt-generator · 深优化建议（文档先行）

> 与父仓 `docs/OPTIMIZATION-NEXT.md` Top5 对齐。  
> 轻量加固：✅ C1 PR（钉依赖 / `.env.example` / dry-run / README 对齐）。**下列留给下一轮代码。**

## 现状对照

| 项 | 现状 |
|---|---|
| CLI | `python main.py inputs/*.json`；Web：`python app.py` |
| Demo | README 有 5 套 Demo 实测；C1 引入 `--dry-run` / samples 路径需与远端 PR 对齐本地 |
| 配置 | `config/footer.json`、`modals.json`；缺主题 profile YAML |
| 卫生 | 输出 pptx 易误提交，需 `.gitignore` 加固 |

## 建议（可执行）

| # | 建议 | 类型 | 验收 |
|---|---|---|---|
| 1 | 固化 `samples/client-brief.json` + `--dry-run` 为默认 Demo（无 Key 出结构预览） | Demo | README 第一路径即此命令 |
| 2 | 主题/字体/页数做成 profile YAML（如 `config/profiles/training.yaml`） | 定制 | 换 profile 即换皮 |
| 3 | Web `app.py` 与 CLI 共用同一生成管线，避免双份逻辑；单测覆盖入口 | 可运行 | 改一处两端生效 |
| 4 | 输出目录清理规则 + 大文件 `.gitignore`（`*.pptx` / `out/`） | 安全/卫生 | 不误提交产物 |
| 5 | 客户交付：`docs/HANDOFF.md`（钉死 `requirements` + 操作录屏脚本清单） | 文档 | 交付可交接 |
| 6 | README 第一屏改「结果句」（培训/咨询一天出 N 套） | 文档 | 标题可转化 |

## 建议落地顺序

1 → 4 → 6 → 2 → 3 → 5。

## 定制联系

微信 **qingbao199101**（备注：PPT生成）· [wuxiumu@163.com](mailto:wuxiumu@163.com)
