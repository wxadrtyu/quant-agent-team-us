---
type: data-decision
summary: 已按当前仓库代码编写覆盖 A 股日频主流程及美股研究扩展的离线单页 HTML 二次开发说明书；明确旧文档与实现边界、状态改变入口和人工审核要求。
stage: documentation-implementation
kpi_version: n/a
tags:
  - project:quant-agent-team
  - market:cn_a
  - freq:daily
  - stage:documentation-implementation
  - status:verified
next_step: 后续代码或数据契约变化时同步更新说明书，并在 codex-mcp-memory 恢复后补写此记录。
memory_sync: codex-mcp-memory memory_search/memory_create 本轮不可用；待可用时补写。
---

2026-10-16：产物为 `docs/secondary-development-guide.html`。本轮核查 `pyproject.toml`、CLI/工作流、数据库、摄取、回测/评估、美股主要脚本和测试。HTML 用标准库 `html.parser` 解析，8 个段落锚点及 69 个本地链接均可解析，未引入外部资源，且包含窄屏与打印 CSS；`pytest --collect-only` 收集 226 项，完整单测为 217 通过、9 跳过、6 条 pandas FutureWarning，定向测试 6 项通过。本地 `file://` 浏览器预览被安全策略阻止，未做视觉确认。未运行真实数据摄取或研究回测、订单或监控池写入；未恢复自动轮训。
