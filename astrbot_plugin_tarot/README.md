# Tarot Reading

AstrBot plugin for text-based three-card Major Arcana readings.

## Commands

```text
/tarot
/塔罗
/tarot <question>
/塔罗 <question>
占卜一下 <question>
帮我用塔罗看看 <question>
```

With no question, the command creates a daily-fortune spread whose cards remain stable for the same user and China Standard Time date. With a question, the plugin draws three unique cards for past/root, present/core, and future/trend. Upright and reversed orientations are selected independently. The configured Flash provider creates a concise reading in the Ardbert persona without using the visible-chat provider. Failed or empty primary responses retry through the configured official provider.

The unified front layer routes direct natural-language tarot requests into the same command flow, cooldown, model prompt, and output formatter. Ordinary discussion that only mentions tarot or divination is not treated as a request.

Readings are for entertainment and self-reflection. They do not replace medical, legal, financial, or other professional advice.

The implementation was inspired by the interaction model of `uxiaohan/Tarot-Web`. No source code, prompt text, credentials, or card images from that unlicensed repository are included.
