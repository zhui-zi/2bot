# Mention Only Chat and Active Group Reply

AstrBot request gate and optional active participation for QQ Official and SnowLuma group conversations.

The plugin allows direct LLM requests when a QQ Official group message contains a real `At` component targeting the bot or directly replies to a message sent by the bot. Normal plugin and built-in commands remain available. Trusted tarot, active group reply, and matched FF14 knowledge requests may explicitly allow their own model calls. This lets relevant FF14 questions work in an allowlisted QQ Official private session without opening unrelated private chat.

For ordinary QQ group messages, `active_reply_percent` controls the independent chance that the bot joins the conversation. The value is clamped to 0-30 percent and defaults to 5 percent. Direct mentions, replies to the bot, slash commands, empty messages, and messages sent by the bot are excluded from random participation.

Enable AstrBot group context awareness so an active response can include recent group messages. The plugin reuses or creates the current group conversation and uses its configured provider and persona.
