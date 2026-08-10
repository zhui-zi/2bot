# Unified Permissions

Shared permission hierarchy for user-facing AstrBot plugins:

```text
Bot author > AstrBot administrator > current-group owner/administrator > member
```

Bot authors are configured once through `bot_author_ids`. AstrBot administrators continue to use AstrBot's administrator configuration. Group owners and administrators are recognized from QQ platform role fields and are restricted to the current group. When a platform omits group roles, `group_manager_overrides` accepts scoped `group_id:sender_id` entries.

`/permission` or `/权限` shows the caller's effective level. Permission changes remain configuration-only; natural-language requests cannot grant or modify permissions.
