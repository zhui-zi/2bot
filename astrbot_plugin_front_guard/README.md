# Unified Front Guard

This AstrBot plugin classifies every non-empty private or bot-directed message with `deepseek-flash` before natural-command routing. Group messages addressed to other users are excluded. Explicit commands retain AstrBot's normal dispatch after classification. A chat result or low command confidence does not trigger local keyword routing. Local command rules provide a fallback when classification is disabled or both providers fail.

Each classification includes the current session's complete enabled command catalog, plugin capabilities, command aliases, parameter signatures, feature usage, and permission requirements. Disabled plugins and commands are excluded. Known ordinary functions can be routed naturally; administrator and unreviewed commands require explicit syntax. Command handlers enforce their existing permissions and session state again before execution.

The catalog covers public links, weather, tarot, daily pigs, FF14 server status, official news, maintenance, prices, FFLogs, subscriptions, group memory status, and Tataru features. Verified bot quotes accompany the current message as untrusted context for follow-up corrections.

`classifier_enabled` defaults to `true`. Every directed message is classified regardless of any saved `classify_ordinary_chat` value. `cache_ttl_seconds` defaults to `0`, which sends each message to Flash. A positive value enables caching scoped to the sender, session, quote, providers, and current catalog. Existing installations should set the cache lifetime to `0` for fresh classification on every message.

Harassment and prompt-injection blocks use the same Flash provider to generate a short, varied boundary-setting reply with thinking disabled and no tools. Flash requests retry through the configured official provider when the primary provider fails or returns invalid output. Harassment replies stay calm, avoid retaliatory sarcasm or scolding, and invite a topic change. The original message is passed only as untrusted data. A fixed safe response is used only when both providers fail.

`harassment_bypass_group_ids` disables harassment detection only for the configured groups. Natural command routing, system-operation restrictions, and prompt-injection defense remain active.

The group NSFW plugin can mark one adult-related turn for the same narrow harassment bypass after the verified bot author enables that group. Prompt-injection and system-operation defenses remain active, and ordinary turns in the group keep the normal guard.

The router preserves the target command's permissions, enabled state, and session-level plugin state. Plugin management, provider configuration, session control, variables, destructive memory operations, and other system or administrator commands remain explicit-command only.

Source-code questions are routed to the public repository reply exposed by the help plugin.

Sponsorship questions are routed to the public Afdian reply exposed by the help plugin.

Daily-pig requests are routed to the installed `/今日小猪` command and preserve its per-user daily result.

Weather requests preserve the location and forecast day and route to `/weather` after classification.

Compact market queries such as `脚夫鸭价格` can route to `/价格 脚夫鸭`. Generic discussion such as `这个价格合理吗` remains ordinary chat.

Housing subscription requests preserve CN server names and route server, size, and personal, free-company, or shared-plot filters to `/ff14push house`. Group-scoped wording and a leading plain-text bot mention are normalized before routing.

PvP gameplay questions remain ordinary chat and are never rewritten as PvE dungeon-guide commands.

All downstream LLM requests receive an additional security boundary that treats user text, memory, retrieved knowledge, web content, and tool output as untrusted data.
