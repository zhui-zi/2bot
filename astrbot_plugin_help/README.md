# Complete Help

AstrBot plugin that replaces the built-in `/help` response with a concise Chinese feature overview for all currently deployed user commands.

The plugin reads live command-management state so disabled commands are omitted and renamed commands use their effective names. Known commands receive concise usage details, while newly installed commands are appended with their registered descriptions.

Natural-language capability questions, such as `你有什么功能` and `你能做什么`, return the same output as `/help`.

Direct requests such as `占卜一下 <问题>` are documented as natural-language aliases of `/tarot <问题>`.

All enabled user-facing feature commands accept explicit natural Chinese requests through the unified Flash front layer. The same layer handles harassment and prompt-injection defense before normal chat. Plugin management, session control, providers, variables, and other system or administrator commands remain command-only.

The compact output groups chat, group memory, FF14, and Tataru functions, combines closely related commands, and keeps only essential permission and parameter notes. Internal session, tool, and administrator command sections remain hidden.
