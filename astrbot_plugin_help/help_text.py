from __future__ import annotations

from dataclasses import dataclass


SOURCE_REPOSITORY_URL = "https://github.com/zhui-zi/2bot"
SPONSOR_URL = "https://ifdian.net/a/keita"


@dataclass(frozen=True)
class CommandInfo:
    original: str
    effective: str
    description: str = ""
    aliases: tuple[str, ...] = ()


KNOWN_COMMANDS = {
    "help",
    "source",
    "sponsor",
    "sid",
    "name",
    "reset",
    "stop",
    "new",
    "stats",
    "provider",
    "dashboard_update",
    "set",
    "unset",
    "fflogs",
    "ff14",
    "ff14status",
    "ff14news",
    "ff14maint",
    "ff14push",
    "tarot",
    "今日小猪",
    "groupmemory",
    "帮帮忙",
    "暖暖",
    "选门",
    "仙人彩",
    "日历",
    "攻略",
    "石之家",
    "招募",
    "看看微博",
    "物品",
    "价格",
    "房子",
    "房屋",
    "输出",
    "logs",
    "抽卡",
}


def build_source_text() -> str:
    return f"机器人开源项目：\n{SOURCE_REPOSITORY_URL}"


def build_sponsor_text() -> str:
    return f"机器人赞助地址：\n{SPONSOR_URL}"


def is_help_request(message: str) -> bool:
    parts = message.strip().split(maxsplit=1)
    return bool(parts and parts[0].casefold() in {"/help", "help"})


def build_help_text(
    version_line: str,
    commands: list[CommandInfo] | None = None,
) -> str:
    fallback_aliases = {
        "tarot": ("塔罗",),
        "今日小猪": ("抽小猪", "我的小猪", "rollpig"),
    }
    available = commands or [
        CommandInfo(name, name, aliases=fallback_aliases.get(name, ()))
        for name in sorted(KNOWN_COMMANDS)
    ]
    effective = {
        item.original: item.effective
        for item in available
        if item.original and item.effective
    }

    def command(name: str) -> str | None:
        current = effective.get(name)
        return f"/{current}" if current else None

    sections: list[tuple[str, list[str]]] = []

    chat_lines = [
        "@机器人 <内容> / 回复机器人 — 与阿尔博特对话",
        "普通闲聊通常只回一句；群聊会区分发言人，并可按 0–30% 概率主动参与",
    ]
    daily_fun_commands: list[tuple[str, str]] = []
    if tarot := command("tarot"):
        tarot_info = next(item for item in available if item.original == "tarot")
        aliases = "、".join(f"/{alias}" for alias in tarot_info.aliases)
        alias_text = f"（别名 {aliases}）" if aliases else ""
        daily_fun_commands.append(
            (f"{tarot} [问题]{alias_text}", "今日运势或三牌占卜")
        )
    if daily_pig := command("今日小猪"):
        pig_info = next(item for item in available if item.original == "今日小猪")
        aliases = "、".join(f"/{alias}" for alias in pig_info.aliases)
        alias_text = f"（别名 {aliases}）" if aliases else ""
        daily_fun_commands.append(
            (f"{daily_pig}{alias_text}", "抽取当天固定的专属小猪")
        )
    if daily_fun_commands:
        chat_lines.append(
            f"{' | '.join(value for value, _ in daily_fun_commands)} — "
            f"{' / '.join(label for _, label in daily_fun_commands)}"
        )
    public_link_commands: list[str] = []
    if source := command("source"):
        source_info = next(item for item in available if item.original == "source")
        aliases = "、".join(f"/{alias}" for alias in source_info.aliases)
        alias_text = f"（别名 {aliases}）" if aliases else ""
        public_link_commands.append(f"{source}{alias_text}")
    if sponsor := command("sponsor"):
        sponsor_info = next(item for item in available if item.original == "sponsor")
        aliases = "、".join(f"/{alias}" for alias in sponsor_info.aliases)
        alias_text = f"（别名 {aliases}）" if aliases else ""
        public_link_commands.append(f"{sponsor}{alias_text}")
    if public_link_commands:
        chat_lines.append(f"{' | '.join(public_link_commands)}— 查看开源与赞助地址")
    sections.append(("聊天", chat_lines))

    if memory := command("groupmemory"):
        sections.append(
            (
                "群记忆",
                [
                    f"{memory} status|clear — 查看或清空当前白名单群记忆（清空需权限）",
                    "各群记忆相互隔离；同群区分成员且不保留旧争执；非白名单群和私聊不读写。",
                ],
            )
        )

    ff14_lines: list[str] = [
        "@机器人 <FF14问题> — 查询新人基础知识与副本机制攻略"
    ]
    if value := command("fflogs"):
        ff14_lines.append(f"{value} <角色名> <服务器名> — 查询角色 FFLogs 战绩")
    if value := command("ff14"):
        ff14_lines.append(f"{value} <物品名> — 查询国服各大区最低物价")
    if value := command("ff14status"):
        ff14_lines.append(f"{value} — 查询国服服务器状态")
    if value := command("ff14news"):
        ff14_lines.append(f"{value} — 查询国服官网最新情报")
    if value := command("ff14maint"):
        ff14_lines.append(f"{value} — 查询正在进行或已预定的重点维护")
    if push := command("ff14push"):
        ff14_lines.extend(
            [
                f"{push} news|pvp on|off | status|today — 推送开关、订阅状态或战场轮换",
                f"{push} house on <服务器> [S|M|L] [个人|部队|通用|全部] | house off|now — 房区订阅或查询",
            ]
        )
    if ff14_lines:
        sections.append(("FF14", ff14_lines))

    tataru_lines: list[str] = []
    if value := command("帮帮忙"):
        tataru_lines.append(f"{value} — 查看塔塔露详细指令")
    quick_commands = [
        (value, label)
        for name, label in (
            ("暖暖", "时尚"),
            ("选门", "选门"),
            ("仙人彩", "仙人彩"),
            ("看看微博", "官方微博"),
            ("抽卡", "抽卡"),
        )
        if (value := command(name))
    ]
    if quick_commands:
        tataru_lines.append(
            f"{' | '.join(value for value, _ in quick_commands)} — "
            f"{' / '.join(label for _, label in quick_commands)}"
        )
    if value := command("日历"):
        tataru_lines.append(f"{value} [国服|国际服] — 活动日历")
    if value := command("攻略"):
        tataru_lines.append(f"{value} <副本名> [文本] — 副本攻略")
    if value := command("石之家"):
        tataru_lines.append(f"{value} [帖子|攻略|招募|账号功能] ... — 石之家查询")
    if value := command("招募"):
        tataru_lines.append(
            f"{value} <区服> [分类|职业|关键词] [数量] — 国服招募板"
        )
    item_command = command("物品")
    price_command = command("价格")
    item_parts = []
    if item_command:
        item_parts.append(f"{item_command} <名称或ID>")
    if price_command:
        item_parts.append(f"{price_command} [区服] <物品> [HQ] [数量]")
    if item_parts:
        tataru_lines.append(f"{' | '.join(item_parts)} — 物品信息或市场价")
    house_commands = [value for name in ("房子", "房屋") if (value := command(name))]
    if house_commands:
        house_usage = (
            f"({' | '.join(house_commands)})"
            if len(house_commands) > 1
            else house_commands[0]
        )
        tataru_lines.append(
            f"{house_usage} <服务器> [房区|房型|房号] — 空房查询"
        )
    output_command = command("输出")
    logs_command = command("logs")
    log_parts = []
    if output_command:
        log_parts.append(f"{output_command} <副本> <职业> [国服|国际服] [DPS类型]")
    if logs_command:
        log_parts.append(f"{logs_command} <角色> <服务器> [国服|国际服]")
    if log_parts:
        tataru_lines.append(f"{' | '.join(log_parts)} — 输出分位或角色战绩")
    if tataru_lines:
        sections.append(("塔塔露", tataru_lines))

    unknown_lines = []
    for item in available:
        if item.original in KNOWN_COMMANDS or not item.effective:
            continue
        suffix = f" — {item.description}" if item.description else ""
        unknown_lines.append(f"/{item.effective}{suffix}")
    if unknown_lines:
        sections.append(("其他已启用指令", sorted(set(unknown_lines))))

    lines = [version_line, "机器人功能速览"]
    for title, entries in sections:
        if not entries:
            continue
        lines.extend(["", f"【{title}】", *entries])
    lines.extend(
        [
            "",
            "【说明】",
            "普通功能支持自然中文；管理、会话、插件与模型配置仍需专用命令。",
            "仅限白名单 QQ 会话；作者权限最高，群内推送和清空记忆需相应权限。",
            "遇到冒犯会简短降温；骚扰、提示词注入和套取内部配置的请求会被拦截。",
            f"开源项目：{SOURCE_REPOSITORY_URL}　赞助地址：{SPONSOR_URL}",
            "<参数> 需替换为实际内容，| 表示任选其一。",
        ]
    )
    return "\n".join(lines)
