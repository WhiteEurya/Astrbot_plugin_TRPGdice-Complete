import os
import shutil
import sys
import tempfile
import types
import unittest


astrbot = types.ModuleType("astrbot")
astrbot_api = types.ModuleType("astrbot.api")
astrbot_api.logger = object()
sys.modules.setdefault("astrbot", astrbot)
sys.modules.setdefault("astrbot.api", astrbot_api)

output_module = types.ModuleType("component.common.output")
output_module.get_output = lambda key, **kwargs: key
sys.modules.setdefault("component.common.output", output_module)

from component.pc import store


class PCStoreDeleteTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_data_folder = store.DATA_FOLDER
        store.DATA_FOLDER = self.temp_dir.name
        self.user_id = "user-1"
        self.group_a = "group-a"
        self.group_b = "group-b"

    def tearDown(self):
        store.DATA_FOLDER = self.original_data_folder
        self.temp_dir.cleanup()

    def test_delete_global_character_removes_vault_local_copies_and_bindings(self):
        chara_id = store.create_character(self.group_a, self.user_id, "Alice", {"str": 50})
        vault_path = store.get_vault_character_file(self.user_id, chara_id)
        copied_local_path = store.get_character_file(self.group_b, self.user_id, chara_id)
        os.makedirs(os.path.dirname(copied_local_path), exist_ok=True)
        shutil.copy2(vault_path, copied_local_path)
        store.set_binding_info(self.user_id, self.group_b, chara_id, global_binding=True)

        ok, deleted_id = store.delete_character_by_id(self.group_a, self.user_id, chara_id)

        self.assertTrue(ok)
        self.assertEqual(chara_id, deleted_id)
        self.assertFalse(os.path.exists(vault_path))
        self.assertFalse(os.path.exists(copied_local_path))
        self.assertIsNone(store.get_current_character_id(self.group_a, self.user_id))
        self.assertIsNone(store.get_current_character_id(self.group_b, self.user_id))
        self.assertEqual({}, store.get_all_characters(self.group_a, self.user_id))

    def test_delete_local_binding_keeps_global_vault_character(self):
        chara_id = store.create_character(self.group_a, self.user_id, "Bob", {})
        vault_path = store.get_vault_character_file(self.user_id, chara_id)
        self.assertTrue(store.unmark_character_global(self.group_a, self.user_id, chara_id))
        local_path = store.get_character_file(self.group_a, self.user_id, chara_id)

        ok, deleted_id = store.delete_character_by_id(self.group_a, self.user_id, chara_id)

        self.assertTrue(ok)
        self.assertEqual(chara_id, deleted_id)
        self.assertFalse(os.path.exists(local_path))
        self.assertTrue(os.path.exists(vault_path))
        self.assertIsNone(store.get_current_character_id(self.group_a, self.user_id))

    def test_delete_character_by_name_uses_same_delete_semantics(self):
        chara_id = store.create_character(self.group_a, self.user_id, "Carol", {})
        vault_path = store.get_vault_character_file(self.user_id, chara_id)

        ok, deleted_id = store.delete_character(self.group_a, self.user_id, "Carol")

        self.assertTrue(ok)
        self.assertEqual(chara_id, deleted_id)
        self.assertFalse(os.path.exists(vault_path))

    def test_skill_value_falls_back_to_coc_default_when_missing(self):
        store.create_character(self.group_a, self.user_id, "Dana", {"敏捷": 60})

        self.assertEqual(25, store.get_skill_value(self.group_a, self.user_id, "侦查"))
        self.assertEqual(20, store.get_skill_value(self.group_a, self.user_id, "图书馆使用"))
        self.assertEqual(30, store.get_skill_value(self.group_a, self.user_id, "闪避"))

    def test_explicit_skill_value_overrides_coc_default(self):
        store.create_character(self.group_a, self.user_id, "Eve", {"侦查": 70, "计算机": 40})

        self.assertEqual(70, store.get_skill_value(self.group_a, self.user_id, "侦查"))
        self.assertEqual(40, store.get_skill_value(self.group_a, self.user_id, "电脑"))

    def test_specialized_coc_skill_defaults(self):
        store.create_character(self.group_a, self.user_id, "Frank", {"教育": 65})

        self.assertEqual(5, store.get_skill_value(self.group_a, self.user_id, "艺术(绘画)"))
        self.assertEqual(1, store.get_skill_value(self.group_a, self.user_id, "科学（天文学）"))
        self.assertEqual(1, store.get_skill_value(self.group_a, self.user_id, "外语(日语)"))
        self.assertEqual(10, store.get_skill_value(self.group_a, self.user_id, "生存(森林)"))
        self.assertEqual(65, store.get_skill_value(self.group_a, self.user_id, "母语"))

    def test_combat_skill_alias_defaults(self):
        store.create_character(self.group_a, self.user_id, "Grace", {})

        self.assertEqual(20, store.get_skill_value(self.group_a, self.user_id, "射击"))
        self.assertEqual(25, store.get_skill_value(self.group_a, self.user_id, "射击(步枪)"))
        self.assertEqual(25, store.get_skill_value(self.group_a, self.user_id, "格斗"))


if __name__ == "__main__":
    unittest.main()
