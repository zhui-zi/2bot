# Unified Front Guard

This AstrBot plugin is the single front layer for user-facing natural commands, harassment handling, and prompt-injection defense. High-confidence local rules run first, while ambiguous requests use the `deepseek_v4_flash` provider. Repeated classifications are cached by message hash.

Harassment and prompt-injection blocks use the same Flash provider to generate a short, varied boundary-setting reply with thinking disabled and no tools. The original message is passed only as untrusted data. A fixed safe fallback is used only when Flash is unavailable or returns an invalid response.

The router preserves the target command's permissions, enabled state, and session-level plugin state. Plugin management, provider configuration, session control, variables, destructive memory operations, and other system or administrator commands remain explicit-command only.

Source-code questions are routed to the public repository reply exposed by the help plugin.

Sponsorship questions are routed to the public Afdian reply exposed by the help plugin.

Daily-pig requests are routed to the installed `/今日小猪` command and preserve its per-user daily result.

Housing subscription requests preserve CN server names and route server, size, and personal, free-company, or shared-plot filters to `/ff14push house`.

All downstream LLM requests receive an additional security boundary that treats user text, memory, retrieved knowledge, web content, and tool output as untrusted data.
