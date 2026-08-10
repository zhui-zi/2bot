from pathlib import Path
from types import SimpleNamespace
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from astrbot_plugin_permissions.permission_core import (
    PERMISSION_ASTRBOT_ADMIN,
    PERMISSION_BOT_AUTHOR,
    PERMISSION_GROUP_MANAGER,
    PERMISSION_MEMBER,
    configure_permission_policy,
    extract_platform_roles,
    permission_management_scope,
    resolve_event_permission,
    resolve_permission,
)


class PermissionCoreTests(unittest.TestCase):
    def tearDown(self) -> None:
        configure_permission_policy()

    def test_exact_hierarchy_order(self) -> None:
        author = resolve_permission(
            "author",
            is_astrbot_admin=True,
            bot_author_ids=["author"],
            is_group_chat=True,
            group_id="group",
            platform_roles=["owner"],
        )
        admin = resolve_permission("admin", is_astrbot_admin=True)
        group_manager = resolve_permission(
            "manager",
            is_group_chat=True,
            group_id="group",
            platform_roles=["admin"],
        )
        member = resolve_permission("member")

        self.assertEqual(author.level, PERMISSION_BOT_AUTHOR)
        self.assertEqual(admin.level, PERMISSION_ASTRBOT_ADMIN)
        self.assertEqual(group_manager.level, PERMISSION_GROUP_MANAGER)
        self.assertEqual(member.level, PERMISSION_MEMBER)
        self.assertGreater(author.level, admin.level)
        self.assertGreater(admin.level, group_manager.level)
        self.assertGreater(group_manager.level, member.level)

    def test_group_roles_are_scoped_to_group_events(self) -> None:
        private = resolve_permission(
            "manager",
            is_group_chat=False,
            platform_roles=["owner"],
        )
        group = resolve_permission(
            "manager",
            is_group_chat=True,
            group_id="group-a",
            platform_roles=["owner"],
        )
        self.assertEqual(private.level, PERMISSION_MEMBER)
        self.assertEqual(group.level, PERMISSION_GROUP_MANAGER)
        self.assertEqual(permission_management_scope(group), "group")

    def test_group_override_never_crosses_groups(self) -> None:
        overrides = [("group-a", "manager")]
        allowed = resolve_permission(
            "manager",
            is_group_chat=True,
            group_id="group-a",
            group_manager_overrides=overrides,
        )
        denied = resolve_permission(
            "manager",
            is_group_chat=True,
            group_id="group-b",
            group_manager_overrides=overrides,
        )
        self.assertEqual(allowed.level, PERMISSION_GROUP_MANAGER)
        self.assertEqual(denied.level, PERMISSION_MEMBER)

    def test_extracts_onebot_and_official_role_shapes(self) -> None:
        self.assertEqual(
            extract_platform_roles({"sender": {"role": "admin"}}),
            {"admin"},
        )
        self.assertEqual(
            extract_platform_roles({"author": {"roles": ["Member", "Owner"]}}),
            {"member", "owner"},
        )

    def test_event_resolution_uses_central_policy(self) -> None:
        configure_permission_policy(
            bot_author_ids=["author"],
            group_manager_overrides=["group-a:manager"],
        )

        def event(sender: str, group: str, is_admin: bool = False):
            raw = SimpleNamespace(raw_data={"group_id": group})
            return SimpleNamespace(
                get_sender_id=lambda: sender,
                get_group_id=lambda: group,
                is_private_chat=lambda: not bool(group),
                is_admin=lambda: is_admin,
                message_obj=SimpleNamespace(raw_message=raw),
            )

        self.assertEqual(
            resolve_event_permission(event("author", "group-a")).level,
            PERMISSION_BOT_AUTHOR,
        )
        self.assertEqual(
            resolve_event_permission(event("manager", "group-a")).level,
            PERMISSION_GROUP_MANAGER,
        )


if __name__ == "__main__":
    unittest.main()
