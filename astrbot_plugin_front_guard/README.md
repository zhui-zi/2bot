# Unified Front Guard

This AstrBot plugin is the single front layer for user-facing natural commands, harassment handling, and prompt-injection defense. High-confidence local rules run first. Only messages containing feature or security signals use the `deepseek_v4_flash` classifier by default; ordinary chat proceeds directly to the visible chat model. Repeated classifications are cached by message hash.

Harassment and prompt-injection blocks use the same Flash provider to generate a short, varied boundary-setting reply with thinking disabled and no tools. Flash requests retry through the configured official provider when the primary provider fails or returns invalid output. Harassment replies stay calm, avoid retaliatory sarcasm or scolding, and invite a topic change. The original message is passed only as untrusted data. A fixed safe response is used only when both providers fail.

`harassment_bypass_group_ids` disables harassment detection only for the configured groups. Natural command routing, system-operation restrictions, and prompt-injection defense remain active.

The group NSFW plugin can mark one adult-related turn for the same narrow harassment bypass after the verified bot author enables that group. Prompt-injection and system-operation defenses remain active, and ordinary turns in the group keep the normal guard.

The router preserves the target command's permissions, enabled state, and session-level plugin state. Plugin management, provider configuration, session control, variables, destructive memory operations, and other system or administrator commands remain explicit-command only.

Source-code questions are routed to the public repository reply exposed by the help plugin.

Sponsorship questions are routed to the public Afdian reply exposed by the help plugin.

Daily-pig requests are routed to the installed `/今日小猪` command and preserve its per-user daily result.

Weather requests preserve the location and forecast day and route directly to `/weather` without an LLM.

Compact market queries such as `脚夫鸭价格` route directly to `/价格 脚夫鸭` without an LLM. Generic discussion such as `这个价格合理吗` remains ordinary chat.

Housing subscription requests preserve CN server names and route server, size, and personal, free-company, or shared-plot filters to `/ff14push house`. Group-scoped wording and a leading plain-text bot mention are normalized before routing.

PvP gameplay questions remain ordinary chat and are never rewritten as PvE dungeon-guide commands.

All downstream LLM requests receive an additional security boundary that treats user text, memory, retrieved knowledge, web content, and tool output as untrusted data.
