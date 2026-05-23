import unittest

from component.roll.parser import parse_inline_command, strip_command_prefix


class RollParserTest(unittest.TestCase):
    def test_strip_command_prefix_removes_whitespace_after_prefix(self):
        prefixes = [".", "/", "。", "!", "！"]
        self.assertEqual("ra侦查50", strip_command_prefix(".ra 侦查 50", prefixes))
        self.assertEqual("r1d20+5", strip_command_prefix("/r 1d20 + 5", prefixes))
        self.assertEqual("r1d100", strip_command_prefix("!r 1d100", prefixes))
        self.assertEqual("ra侦查50", strip_command_prefix("！ra 侦查 50", prefixes))
        self.assertIsNone(strip_command_prefix("r1d100", prefixes))

    def test_parse_normal_roll_with_remark(self):
        parsed = parse_inline_command("r2d6+3攻击")

        self.assertEqual("r", parsed.cmd)
        self.assertEqual("2d6+3", parsed.expr)
        self.assertEqual("攻击", parsed.remark)

    def test_parse_empty_roll_uses_default_d100(self):
        parsed = parse_inline_command("r")

        self.assertEqual("r", parsed.cmd)
        self.assertEqual("1d100", parsed.expr)
        self.assertEqual("", parsed.remark)

    def test_parse_normal_roll_with_parentheses_and_division(self):
        parsed = parse_inline_command("r(1d6+2)*3/2伤害")

        self.assertEqual("r", parsed.cmd)
        self.assertEqual("(1d6+2)*3/2", parsed.expr)
        self.assertEqual("伤害", parsed.remark)

    def test_parse_hidden_roll_keeps_expression_and_remark(self):
        parsed = parse_inline_command("rh1d6秘密")

        self.assertEqual("rh", parsed.cmd)
        self.assertEqual("1d6", parsed.expr)
        self.assertEqual("秘密", parsed.remark)

    def test_parse_rd_shortcut(self):
        parsed = parse_inline_command("rd20先攻")

        self.assertEqual("rd", parsed.cmd)
        self.assertEqual("1d20", parsed.expr)
        self.assertEqual("先攻", parsed.remark)

    def test_parse_coc_check_bonus_penalty_and_repeat(self):
        bonus = parse_inline_command("ra3#b2射击50")
        self.assertEqual("rab", bonus.cmd)
        self.assertEqual("射击", bonus.expr)
        self.assertEqual("50", bonus.skill_value)
        self.assertEqual("2", bonus.dice_count)
        self.assertEqual("3", bonus.roll_times)

        penalty = parse_inline_command("rap侦查70")
        self.assertEqual("rap", penalty.cmd)
        self.assertEqual("侦查", penalty.expr)
        self.assertEqual("70", penalty.skill_value)
        self.assertEqual("1", penalty.dice_count)

    def test_parse_dice_compat_bonus_penalty_shortcuts(self):
        bonus = parse_inline_command("rb2射击50")
        self.assertEqual("rab", bonus.cmd)
        self.assertEqual("射击", bonus.expr)
        self.assertEqual("50", bonus.skill_value)
        self.assertEqual("2", bonus.dice_count)

        penalty = parse_inline_command("rp侦查70")
        self.assertEqual("rap", penalty.cmd)
        self.assertEqual("侦查", penalty.expr)
        self.assertEqual("70", penalty.skill_value)
        self.assertEqual("1", penalty.dice_count)

    def test_parse_dice_compat_hidden_check_shortcut(self):
        parsed = parse_inline_command("hl侦查50")

        self.assertEqual("rah", parsed.cmd)
        self.assertEqual("侦查", parsed.expr)
        self.assertEqual("50", parsed.skill_value)

    def test_parse_until_success_check(self):
        parsed = parse_inline_command("rau侦查70")

        self.assertEqual("rau", parsed.cmd)
        self.assertEqual("侦查", parsed.expr)
        self.assertEqual("70", parsed.skill_value)

    def test_parse_growth_sanity_and_initiative(self):
        growth = parse_inline_command("en侦查70")
        self.assertEqual("en", growth.cmd)
        self.assertEqual("侦查", growth.expr)
        self.assertEqual("70", growth.skill_value)

        sanity = parse_inline_command("sc1/1d6")
        self.assertEqual("sc", sanity.cmd)
        self.assertEqual("1/1d6", sanity.expr)

        initiative = parse_inline_command("ri+3Alice")
        self.assertEqual("ri", initiative.cmd)
        self.assertEqual("+3Alice", initiative.expr)


if __name__ == "__main__":
    unittest.main()
