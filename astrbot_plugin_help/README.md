# Complete Help

AstrBot plugin that replaces the built-in `/help` response with a concise Chinese feature overview for all currently deployed user commands.

The plugin reads live command-management state so disabled commands are omitted and renamed commands use their effective names. Known commands receive concise usage details, while newly installed commands are appended with their registered descriptions.

Natural-language capability questions, such as `你有什么功能` and `你能做什么`, return the same output as `/help`.

`/source`, `/开源`, `/源码`, and natural-language source requests return the public repository URL. The same URL is included in `/help`.

`/sponsor`, `/赞助`, `/爱发电`, and natural-language sponsorship requests return the public sponsorship URL. The same URL is included in `/help`.

Direct requests such as `占卜一下 <问题>` are documented as natural-language aliases of `/tarot <问题>`.

`/weather <location> [day]` is listed with current and short-forecast natural-language usage.

`/今日小猪` and its registered aliases are included in help. Direct requests such as `看看我的小猪` are routed to the same daily draw.

All enabled user-facing feature commands accept explicit natural Chinese requests through the unified Flash front layer. The same layer handles harassment and prompt-injection defense before normal chat. Plugin management, session control, providers, variables, and other system or administrator commands remain command-only.

The FF14 section documents housing subscriptions with server, size, and purchase-eligibility filters, plus immediate housing queries.

The compact output groups chat, group memory, FF14, and Tataru functions, combines closely related commands, and keeps only essential permission and parameter notes. It explains short casual replies, member-aware group chat, layered forgetting and preference learning, expired disputes, and calm handling of abuse without exposing private relationship state. Internal session, tool, and administrator command sections remain hidden.

Permission guidance uses the shared bot-author, AstrBot-administrator, current-group-manager, and member hierarchy. `/permission` shows the caller's effective level.
