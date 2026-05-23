import unittest
from component.spells import query_spell


class SpellLookupTests(unittest.TestCase):
    def test_dnd_spell_prefers_sealdice_builtin_data(self):
        result = query_spell("火球术")

        self.assertIn("【DND法术】火球术", result)
        self.assertIn("火球术 Fireball", result)
        self.assertIn("SeaDice sealdice-builtins", result)

    def test_coc_spell_uses_sealdice_magic_compendium(self):
        result = query_spell("coc 动物魅惑法")

        self.assertIn("【COC法术】动物魅惑法", result)
        self.assertIn("SeaDice sealdice-builtins CoC 魔法大典", result)

    def test_mythos_ritual_query(self):
        result = query_spell("神话 驱逐实体")

        self.assertIn("【神话仪式】驱逐实体 / Banish Entity", result)
        self.assertIn("不是 Chaosium 官方 CoC 法术全文", result)

    def test_empty_query_returns_usage(self):
        result = query_spell("")

        self.assertIn(".查询法术 火球术", result)


if __name__ == "__main__":
    unittest.main()
