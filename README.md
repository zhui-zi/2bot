# 2bot

Public AstrBot plugins used by a personal QQ bot.

## Included plugins

- `astrbot_plugin_ardbert_worldbook`: contextual FF14 Ardbert lore retrieval.
- `astrbot_plugin_ff14_cn`: FF14 CN news, Frontline, and housing notifications.
- `astrbot_plugin_ff14_novice`: local FF14 beginner knowledge retrieval.
- `astrbot_plugin_front_guard`: natural-command routing and safety checks.
- `astrbot_plugin_group_memory`: bounded, group-isolated conversation memory.
- `astrbot_plugin_help`: consolidated live command help.
- `astrbot_plugin_mention_only`: mention-gated and controlled active chat.
- `astrbot_plugin_nsfw_unlock`: author-controlled group adult-content mode.
- `astrbot_plugin_permissions`: shared permission hierarchy for administrative features.
- `astrbot_plugin_tarot`: deterministic daily tarot and multi-card readings.
- `astrbot_plugin_weather`: compact current weather and short forecasts.

Each plugin contains its own metadata, configuration schema, documentation, and tests where applicable.

Runtime credentials, deployment-specific configuration, generated caches, private persona configuration, and independently maintained plugin worktrees are intentionally excluded.

## License

Project code is licensed under the [MIT License](LICENSE). Bundled third-party knowledge data remains subject to its source terms.
