# OpenCode 文档

`` 收录 OpenCode 官方文档的本地存档(英文原文),便于离线查阅与 Agent 按需引用;内容以 [opencode.ai/docs](https://opencode.ai/docs) 为准。项目自定义的 Agent、技能与规则见 `AGENTS.md` 与 `.opencode/`。

# 文档目录

| 文档 | 主题 |
| --- | --- |
| [platform.md](platform.md) | 平台总览:CLI / 桌面 / Web 下载安装、Docker、接入 Provider |
| [cli.md](cli.md) | CLI 使用(命令与 TUI) |
| [console.md](console.md) | OpenCode Console 云端服务:工作区、模型推理、预算与团队策略 |
| [config.md](config.md) | `opencode.jsonc` 配置(全局/系统级位置与常用选项) |
| [providers.md](providers.md) | LLM Provider 接入与自定义配置 |
| [models.md](models.md) | 模型列表、切换与 variant 参数 |
| [mcp-servers.md](mcp-servers.md) | MCP 服务器接入配置 |
| [agents.md](agents.md) | 自定义 Agent:system prompt、模式、模型、权限、步骤数 |
| [skills.md](skills.md) | 技能:`SKILL.md` 编写、发现位置与触发机制 |
| [commands.md](commands.md) | 自定义斜杠命令(`/review` 等) |
| [plugins.md](plugins.md) | 插件开发与加载 |
| [formatters.md](formatters.md) | 代码格式化工具集成 |
| [tools.md](tools.md) | 内置工具总览与工具级配置 |
| [permissions.md](permissions.md) | 工具权限规则:`allow` / `ask` / `deny` |
| [policies.md](policies.md) | 策略:二元强制规则,只收紧权限、从不提示 |
| [network.md](network.md) | 代理(`HTTP_PROXY` / `NO_PROXY`)等网络设置 |
| [websearch.md](websearch.md) | 联网搜索:Provider 选择与用法 |
| [instructions.md](instructions.md) | `AGENTS.md` 项目级持久化指引 |
| [references.md](references.md) | 引用(别名挂载)项目外目录 |
| [attachments.md](attachments.md) | 向 prompt 附加本地文件(截图、CSV 等) |
| [compaction.md](compaction.md) | 长会话上下文压缩(摘要 + 保留近期对话) |
| [warming.md](warming.md) | 会话保温:暂停期间维持 Provider 侧 prompt 缓存 |
| [snapshots.md](snapshots.md) | 快照:`/undo` 一并回滚对话与文件改动 |
| [themes.md](themes.md) | 界面主题定制 |