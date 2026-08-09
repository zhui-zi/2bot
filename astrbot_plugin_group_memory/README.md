# Group Persistent Memory

This AstrBot plugin stores bounded, isolated conversation memory for each QQ group that is present in AstrBot's enabled session allowlist.

- Group memories never cross group boundaries.
- Members in the same group share context but retain distinct stable identities.
- Each request names the current speaker, and bot replies retain their target member.
- Retrieval mixes shared group context with recent records involving the current member.
- A temporary roster maps observed group nicknames to anonymous stable member references.
- Structured mentions, replies, and unambiguous nickname references preserve who is talking to whom.
- Non-allowlisted groups and private messages are never read or written.
- Commands and messages that look like credentials are not stored.
- Relevant history and a small recent window are injected as temporary LLM context.
- `/groupmemory status` shows the current group record count.
- `/groupmemory clear` clears only the current group and requires elevated permission.

Memory is retained for 180 days by default, with at most 500 records per group. Both limits and additional trusted manager IDs are configurable in AstrBot WebUI.
