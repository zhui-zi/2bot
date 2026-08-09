# FF14 CN Push

AstrBot plugin for QQ Official and SnowLuma FF14 CN notifications.

## Features

- Polls the RSSHub `/ff14/zh/all` route and sends unseen entries.
- Sends the current and next-day CN Frontline maps every day at 23:00 Asia/Shanghai.
- Stores switches and delivery state independently per group or private chat.
- Gives configured bot author IDs the highest permission tier, above AstrBot administrators, configured managers, and platform owner/admin roles.
- Restricts group switch changes to the bot author, AstrBot admins, configured manager OpenIDs, or explicit platform owner/admin roles.
- Allows each private user to manage only their own private subscription.
- Seeds current RSS entries when enabled to avoid sending historical news.

## Commands

```text
/ff14push news on
/ff14push news off
/ff14push pvp on
/ff14push pvp off
/ff14push status
/ff14push today
```

The same commands work in QQ Official and SnowLuma group and private chats. QQ Official group messages may omit the sender's group role. Add trusted group owner and admin `/sid` values to `manager_openids` or the AstrBot administrator list. Group permission checks fail closed when no trusted role or ID is available.

Permission order is configured bot author, AstrBot administrator or configured manager, platform owner or administrator, then regular member. Add the same trusted IDs to AstrBot `admins_id` when built-in administrator commands should use the same authority.

Private scheduled delivery depends on the QQ Official bot's private-message permissions and messaging limits. The user must first open a private conversation with the bot.

The Frontline rotation uses the factual eight-day CN sequence and the 2026-04-28 23:00 Asia/Shanghai anchor documented by the reference implementation. No reference code or assets are included.
