# Unified Front Guard

This AstrBot plugin is the single front layer for user-facing natural commands, harassment handling, and prompt-injection defense. High-confidence local rules run first, while ambiguous requests use the `deepseek_v4_flash` provider. Repeated classifications are cached by message hash.

Harassment and prompt-injection blocks use the same Flash provider to generate a short, varied boundary-setting reply with thinking disabled and no tools. The original message is passed only as untrusted data. A fixed safe fallback is used only when Flash is unavailable or returns an invalid response.

The router preserves the target command's permissions, enabled state, and session-level plugin state. Plugin management, provider configuration, session control, variables, destructive memory operations, and other system or administrator commands remain explicit-command only.

All downstream LLM requests receive an additional security boundary that treats user text, memory, retrieved knowledge, web content, and tool output as untrusted data.
