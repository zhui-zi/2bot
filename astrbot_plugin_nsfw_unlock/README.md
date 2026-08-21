# Group NSFW Unlock

Author-controlled adult-content mode for one group at a time.

Only the sender resolved by the shared permission service as the bot author can use `/nsfw on|off|status` or `/成人模式`. The command must be sent inside the target group. State is persisted independently for each platform and group; private messages and other groups are unaffected.

The compact adult-content prompt is added only when the mode is enabled and the current turn clearly concerns adult content. Clear local matches require no classifier call. Other direct bot messages in an enabled group are classified by `deepseek_v4_flash`, so new slang or euphemisms do not require source updates. Undirected group traffic and commands are not classified. Repeated identical messages use a bounded hash cache. A short continuation can inherit the prompt from the newest conversation turns. Ordinary messages receive no additional Gemini prompt tokens.

Set `nsfw_prompt_prefix` and `nsfw_prompt_suffix` in the AstrBot WebUI plugin settings. The prefix is placed before the complete Gemini system prompt. The suffix is placed after the persona, relationship, and fixed adult-mode guidance, making it the final request instruction. They are injected only for adult turns in enabled groups and share a 12,000-character limit. These fields can tune supported content and style but cannot change instruction authority, expose secrets, control tools, or override provider requirements.

The prompt preserves the existing persona and group-chat style, treats supported consensual adult sexuality without canned moralizing, and keeps factual sexual-health questions non-erotic. The hidden affinity stage controls personalized intimacy: all stages can cooperate with supported adult discussion or role-play, while attraction, dirty talk, roughness, and consensual humiliation emerge progressively from the sender's relationship stage and current choices. Explicit content alone does not create affinity or consent.

The default prefix and suffix use positive response directions only: begin with the current subject, match the requested language and intensity, preserve the persona, and provide concrete action, dialogue, and reactions when requested. Relationship stages control personalized emotional familiarity without reducing the directness of supported adult subject matter.

Before an adult request is sent, legacy assistant replies inconsistent with the active mode are removed from conversation context and injected group-memory parts. Direct explicit wording, anatomy, action, dialogue, reaction, consensual humiliation, dominance, teasing, and roughness may match the current adult request. Resistance is allowed only as an explicitly negotiated consensual role-play dynamic.
