# FF14 CN Push

AstrBot plugin for QQ Official and SnowLuma FF14 CN notifications.

## Features

- Polls the RSSHub `/ff14/zh/all` route and sends unseen entries.
- Sends the current and next-day CN Frontline maps every day at 23:00 Asia/Shanghai.
- Polls the public CN housing API and sends one deduplicated update when each five-day lottery application period starts.
- Filters housing subscriptions by server, S/M/L size, and personal, free-company, or shared eligibility.
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
/ff14push house on <server> [S|M|L] [personal|fc|shared|all]
/ff14push house off
/ff14push house now
/ff14push status
/ff14push today
```

The same commands work in QQ Official and SnowLuma group and private chats. QQ Official group messages may omit the sender's group role. Add trusted group owner and admin `/sid` values to `manager_openids` or the AstrBot administrator list. Group permission checks fail closed when no trusted role or ID is available.

Multiple server names and sizes may be supplied in one subscription. A `personal` filter includes personal-only and shared plots. An `fc` filter includes free-company-only and shared plots. Use `shared` to receive shared plots only, or `all` to receive every eligibility type. Enabling or changing a subscription seeds the current cycle and starts automatic delivery with the next application period; `house now` performs an immediate query.

Housing records older than the configured freshness limit are excluded. Automatic delivery also waits until the API reports a complete server refresh after the new application period begins. Records without complete lottery details use the same nine-day cycle model documented by the data source: five application days followed by four result days. Inferred entries are marked in the message. Delivery state is persisted per server and updated only after a successful send, so restarts and temporary API failures do not duplicate completed updates or discard pending ones.

Permission order is configured bot author, AstrBot administrator or configured manager, platform owner or administrator, then regular member. Add the same trusted IDs to AstrBot `admins_id` when built-in administrator commands should use the same authority.

Private scheduled delivery depends on the QQ Official bot's private-message permissions and messaging limits. The user must first open a private conversation with the bot.

The Frontline rotation uses the factual eight-day CN sequence and the 2026-04-28 23:00 Asia/Shanghai anchor documented by the reference implementation. No reference code or assets are included.

Housing data and API field definitions: <https://house.ffxiv.cyou/#/about>. Lottery behavior reference: <https://ff14.huijiwiki.com/wiki/%E5%8D%9A%E5%AE%A2:%E6%88%BF%E5%B1%8B%E6%8A%BD%E7%AD%BE#%E6%96%B0%E7%9A%84%E6%88%BF%E5%B1%8B%E6%8A%BD%E9%80%89%E7%B3%BB%E7%BB%9F>.
