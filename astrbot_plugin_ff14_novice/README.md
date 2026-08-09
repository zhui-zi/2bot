# FF14 Novice Knowledge

This AstrBot plugin retrieves relevant FF14 beginner guidance and duty mechanics before an LLM response. It supports QQ Official Bot and OneBot conversations, including mention-triggered and active group chat. A matching QQ Official private query is explicitly allowed through the mention gate; unrelated private chat remains blocked.

The generated knowledge index is based on `thewakingsands/novice-network` commit `d80a1147d45e9dd299c67f4056e66aa05e85e516`. User-facing responses do not include repository URLs or document paths.

Curated supplemental entries are stored in `knowledge_extensions.json` and merged at runtime. Rebuilding `knowledge.json` does not overwrite these entries.

The source project can change with game updates. Rebuild and redeploy the index after reviewing upstream changes.
