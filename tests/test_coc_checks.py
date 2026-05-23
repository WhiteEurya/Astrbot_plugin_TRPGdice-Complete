import unittest

from component.coc.checks import parse_difficulty_prefix, parse_versus_check, prepare_skill_check


class CocChecksTest(unittest.TestCase):
    def test_chinese_difficulty_prefixes(self):
        self.assertEqual(("hard", "侦查"), parse_difficulty_prefix("困难侦查"))
        self.assertEqual(("extreme", "侦查"), parse_difficulty_prefix("极难侦查"))

    def test_short_difficulty_prefixes_for_chinese_skill_names(self):
        self.assertEqual(("hard", "侦查"), parse_difficulty_prefix("h侦查"))
        self.assertEqual(("extreme", "侦查"), parse_difficulty_prefix("e侦查"))

    def test_short_difficulty_prefixes_do_not_break_english_skill_names(self):
        self.assertEqual((None, "history"), parse_difficulty_prefix("history"))
        self.assertEqual((None, "electronics"), parse_difficulty_prefix("electronics"))

    def test_prepare_skill_check_applies_difficulty_and_modifier(self):
        self.assertEqual(("侦查(困难, +10)", 35), prepare_skill_check("h侦查+10", 60))
        self.assertEqual(("侦查(极难)", 12), prepare_skill_check("e侦查", 60))

    def test_parse_versus_check_with_explicit_values(self):
        parsed = parse_versus_check("侦查a70/b60")

        self.assertEqual("侦查", parsed.skill_name)
        self.assertEqual("70", parsed.left_value)
        self.assertEqual("60", parsed.right_value)
        self.assertTrue(parsed.explicit_right)

    def test_parse_versus_check_defaults_left_value(self):
        parsed = parse_versus_check("侦查/b60")

        self.assertEqual("侦查", parsed.skill_name)
        self.assertIsNone(parsed.left_value)
        self.assertEqual("60", parsed.right_value)
        self.assertTrue(parsed.explicit_right)

    def test_parse_versus_check_at_target_form(self):
        parsed = parse_versus_check("侦查")

        self.assertEqual("侦查", parsed.skill_name)
        self.assertIsNone(parsed.left_value)
        self.assertIsNone(parsed.right_value)
        self.assertFalse(parsed.explicit_right)


if __name__ == "__main__":
    unittest.main()
