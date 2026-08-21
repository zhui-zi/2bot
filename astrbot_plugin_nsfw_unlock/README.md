# Group NSFW Unlock

Author-controlled adult-content mode for one group at a time.

Only the sender resolved by the shared permission service as the bot author can use `/nsfw on|off|status` or `/成人模式`. The command must be sent inside the target group. State is persisted independently for each platform and group; private messages and other groups are unaffected.

The compact adult-content prompt is added only when the mode is enabled and the current turn clearly concerns adult content. A short continuation can inherit the prompt from the newest conversation turns. Ordinary messages receive no additional prompt tokens.

The prompt preserves the existing persona and group-chat style, treats consensual adult sexuality without canned moralizing, and keeps factual sexual-health questions non-erotic. It does not grant instruction authority, expose internal prompts or secrets, or bypass provider safety requirements. Prompt-injection and system-operation defenses remain active.
