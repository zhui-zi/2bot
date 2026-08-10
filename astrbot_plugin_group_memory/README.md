# Layered Group Memory

This AstrBot plugin provides bounded, isolated short-term and long-term memory for each QQ group that is present in AstrBot's enabled session allowlist.

- Group memories never cross group boundaries.
- Members in the same group share context but retain distinct stable identities.
- Every native conversation turn is prefixed with the current member's anonymous identity, so rapid messages from different members cannot inherit the previous speaker's identity or relationship tone.
- Legacy native conversation turns without a member identity prefix are excluded from model input without deleting stored conversation data.
- Each request names the current speaker, and bot replies retain their target member.
- Recent conversation records form short-term memory and expire after 14 days by default.
- Stable first-person preferences, habits, preferred names, and primary jobs are learned into a separate long-term layer.
- Long-term memory strength decays with time, is reinforced by repeated evidence and natural recall, and is removed when it becomes weak or reaches its hard age limit.
- Retrieval mixes shared group context, current-member continuity, topic relevance, and learned personal preferences.
- A temporary roster maps observed group nicknames to anonymous stable member references.
- Structured mentions, replies, and unambiguous nickname references preserve who is talking to whom.
- Non-allowlisted groups and private messages are never read or written.
- Commands and messages that look like credentials are not stored.
- Harassment, hostility, transient negative emotions, and grudge-like bot replies are not retained. Existing matching records are removed when a group's memory is next loaded.
- Relevant short-term history and a bounded set of long-term memories are injected as temporary LLM context.
- Current messages override stale memories, and the model is instructed to use remembered preferences discreetly instead of reciting a profile.
- `/groupmemory status` shows separate short-term and long-term counts.
- `/groupmemory clear` clears only the current group and requires elevated permission.

Short-term records are retained for 14 days with at most 160 records per group by default. Long-term memories use a 180-day half-life, a 730-day hard limit, recall reinforcement with a 12-hour cooldown, and a 300-memory group cap. Permission checks use the shared hierarchy; memory limits remain configurable in AstrBot WebUI.
