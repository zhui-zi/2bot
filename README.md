# 2bot

Public AstrBot plugins used by a personal QQ bot.

## Included plugins

- `astrbot_plugin_ardbert_worldbook`: contextual FF14 Ardbert lore retrieval.
- `astrbot_plugin_ff14_cn`: FF14 CN news and Frontline notifications.
- `astrbot_plugin_ff14_novice`: local FF14 beginner knowledge retrieval.
- `astrbot_plugin_front_guard`: natural-command routing and safety checks.
- `astrbot_plugin_group_memory`: bounded, group-isolated conversation memory.
- `astrbot_plugin_help`: consolidated live command help.
- `astrbot_plugin_mention_only`: mention-gated and controlled active chat.
- `astrbot_plugin_tarot`: deterministic daily tarot and multi-card readings.

Each plugin contains its own metadata, configuration schema, documentation, and tests where applicable.

Runtime credentials, deployment-specific configuration, generated caches, private persona configuration, and independently maintained plugin worktrees are intentionally excluded.
