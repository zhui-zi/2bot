from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from help_text import (
    SOURCE_REPOSITORY_URL,
    SPONSOR_URL,
    CommandInfo,
    build_help_text,
    build_source_text,
    build_sponsor_text,
    is_help_request,
)


class HelpTextTests(unittest.TestCase):
    def test_fallback_help_contains_public_command_set(self) -> None:
        text = build_help_text("AstrBot v4.27.2")

        for command in (
            "/fflogs",
            "/ff14 ",
            "/ff14status",
            "/ff14news",
            "/ff14maint",
            "/ff14push",
            "/tarot",
            "/今日小猪",
            "/groupmemory",
            "/source",
            "/sponsor",
            "/weather",
            "/帮帮忙",
            "/暖暖",
            "/选门",
            "/仙人彩",
            "/日历",
            "/攻略",
            "/石之家",
            "/招募",
            "/看看微博",
            "/物品",
            "/价格",
            "(/房子 | /房屋)",
            "/输出",
            "/logs",
            "/抽卡",
        ):
            self.assertIn(command, text)

        for hidden in (
            "【会话】",
            "【工具】",
            "【管理员指令】",
            "/help",
            "/sid",
            "/name",
            "/reset",
            "/stop",
            "/new",
            "/stats",
            "/provider",
            "/dashboard_update",
            "/set",
            "/unset",
        ):
            self.assertNotIn(hidden, text)

        self.assertIn("机器人功能速览", text)
        self.assertLessEqual(len(text.splitlines()), 40)
        self.assertIn("@机器人 <内容> / 回复机器人", text)
        self.assertIn(
            "/weather <城市或地区> [今天|明天|后天] — 查询实时天气与短期预报",
            text,
        )
        self.assertIn("@机器人 <FF14问题> — 查询新人基础知识与副本机制攻略", text)
        self.assertIn("别名 /塔罗", text)
        self.assertIn("今日运势或三牌占卜", text)
        self.assertIn("别名 /抽小猪、/我的小猪、/rollpig", text)
        self.assertIn("抽取当天固定的专属小猪", text)
        self.assertIn("/ff14push news|pvp on|off | status|today", text)
        self.assertIn("/ff14push house on <服务器>", text)
        self.assertIn("house off|now", text)
        self.assertIn("战场轮换", text)
        self.assertIn("【说明】", text)
        self.assertIn("普通功能支持自然中文", text)
        self.assertIn("管理、会话、插件与模型配置仍需专用命令", text)
        self.assertIn("骚扰、提示词注入和套取内部配置", text)
        self.assertIn(SOURCE_REPOSITORY_URL, text)
        self.assertIn(SPONSOR_URL, text)
        self.assertIn("普通闲聊通常只回一句", text)
        self.assertIn("群聊会区分发言人", text)
        self.assertIn("0–30% 概率主动参与", text)
        self.assertIn("仅限白名单 QQ 会话", text)
        self.assertIn(
            "机器人作者 > AstrBot 管理员 > 当前群群主/管理员 > 普通成员",
            text,
        )
        self.assertIn("/permission 可查看", text)
        self.assertIn("【群记忆】", text)
        self.assertIn("短期对话会遗忘", text)
        self.assertIn("长期只学习稳定偏好和习惯", text)
        self.assertIn("同群区分成员且不保留旧争执", text)
        self.assertIn("遇到冒犯会简短降温", text)
        self.assertNotIn("好感", text)
        self.assertNotIn("恋爱", text)
        self.assertIn("【塔塔露】", text)
        self.assertIn("/暖暖 | /选门 | /仙人彩 | /看看微博 | /抽卡", text)
        self.assertIn("/日历 [国服|国际服] — 活动日历", text)
        self.assertIn("/攻略 <副本名> [文本] — 副本攻略", text)
        self.assertIn("/石之家 [帖子|攻略|招募|账号功能]", text)
        self.assertIn("/价格 [区服] <物品> [HQ] [数量]", text)
        self.assertIn("/logs <角色> <服务器> [国服|国际服]", text)

    def test_source_reply_contains_public_repository(self) -> None:
        self.assertEqual(
            build_source_text(),
            "机器人开源项目：\nhttps://github.com/zhui-zi/2bot",
        )

    def test_sponsor_reply_contains_public_address(self) -> None:
        self.assertEqual(
            build_sponsor_text(),
            "机器人赞助地址：\nhttps://ifdian.net/a/keita",
        )

    def test_live_state_applies_renames_and_omits_disabled_commands(self) -> None:
        text = build_help_text(
            "AstrBot v4.27.2",
            [
                CommandInfo("help", "帮助"),
                CommandInfo("tarot", "占卜", aliases=("塔罗",)),
            ],
        )

        self.assertNotIn("/帮助", text)
        self.assertIn("/占卜 [问题]", text)
        self.assertNotIn("/fflogs", text)

    def test_unknown_enabled_command_uses_registered_description(self) -> None:
        text = build_help_text(
            "AstrBot v4.27.2",
            [CommandInfo("ping", "延迟", "查询延迟")],
        )

        self.assertIn("【其他已启用指令】", text)
        self.assertIn("/延迟 — 查询延迟", text)

    def test_tataru_commands_follow_live_command_state(self) -> None:
        text = build_help_text(
            "AstrBot v4.27.2",
            [
                CommandInfo("攻略", "副本攻略"),
                CommandInfo("房屋", "找房"),
                CommandInfo("logs", "战绩"),
            ],
        )

        self.assertIn("【塔塔露】", text)
        self.assertIn("/副本攻略 <副本名> [文本]", text)
        self.assertIn("/找房 <服务器> [房区|房型|房号]", text)
        self.assertIn("/战绩 <角色> <服务器>", text)
        self.assertNotIn("/暖暖", text)
        self.assertNotIn("【其他已启用指令】", text)

    def test_help_request_detection(self) -> None:
        for message in (
            "/help",
            " /HELP details",
            "help",
        ):
            with self.subTest(message=message):
                self.assertTrue(is_help_request(message))

        for message in (
            "/helpful",
            "请 help 我",
            "你有什么功能？",
            "请问机器人都有哪些指令",
            "你能做什么",
            "功能列表",
            "使用帮助",
            "这个功能怎么用",
            "塔塔露有什么功能",
            "你知道塔塔露有什么功能吗",
            "你能帮我查物价吗",
            "攻略命令怎么用",
            "介绍一下插件功能",
        ):
            with self.subTest(message=message):
                self.assertFalse(is_help_request(message))


if __name__ == "__main__":
    unittest.main()
