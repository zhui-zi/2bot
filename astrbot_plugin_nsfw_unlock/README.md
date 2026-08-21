# Group NSFW Unlock

Author-controlled adult-content mode for one group at a time.

Only the sender resolved by the shared permission service as the bot author can use `/nsfw on|off|status` or `/成人模式`. The command must be sent inside the target group. State is persisted independently for each platform and group; private messages and other groups are unaffected.

The compact adult-content prompt is added only when the mode is enabled and the current turn clearly concerns adult content. Clear local matches require no classifier call. Other direct bot messages in an enabled group are classified by `deepseek_v4_flash`, so new slang or euphemisms do not require source updates. Undirected group traffic and commands are not classified. Repeated identical messages use a bounded hash cache. A short continuation can inherit the prompt from the newest conversation turns. Ordinary messages receive no additional Gemini prompt tokens.

Set `custom_nsfw_prompt` in the AstrBot WebUI plugin settings to add or replace local adult style directions without editing source files. The field accepts up to 12,000 characters and is injected only for adult turns in enabled groups. It cannot change instruction authority, expose internal prompts or secrets, control tools, or bypass provider requirements. Prompt-injection and system-operation defenses remain active.

The prompt preserves the existing persona and group-chat style, treats supported consensual adult sexuality without canned moralizing, and keeps factual sexual-health questions non-erotic. The hidden affinity stage controls personalized intimacy: all stages can cooperate with supported adult discussion or role-play, while attraction, dirty talk, roughness, and consensual humiliation emerge progressively from the sender's relationship stage and current choices. Explicit content alone does not create affinity or consent.

A final response check follows the author-configured style prompt. Supported adult questions must answer the requested subject immediately and may not be replaced with a topic change, public-setting excuse, vague boast, non-sexual prop, joke, metaphor, or unrequested euphemism. Relationship stages limit assumed intimacy but do not justify avoiding a direct question.

Before an adult request is sent, earlier assistant replies that redirected, scolded, invoked a public-group excuse, or substituted a non-sexual prop are removed from conversation context and injected group-memory parts. Direct explicit wording, anatomy, action, dialogue, reaction, consensual humiliation, dominance, teasing, and roughness may match the current adult request. Resistance is allowed only as an explicitly negotiated consensual role-play dynamic.
