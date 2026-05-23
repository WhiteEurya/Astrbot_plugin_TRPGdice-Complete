import random
import sys
import types
import unittest


output_module = types.ModuleType("component.common.output")
output_module.get_output = lambda key, **kwargs: key
sys.modules.setdefault("component.common.output", output_module)

from component.roll import dice
from component.roll.dice import choose_option, parse_choice_options, parse_dice_expression, roll_d66


class RollDiceExpressionTest(unittest.TestCase):
    def test_arithmetic_precedence_without_dice(self):
        total, detail = parse_dice_expression("2+3*4")

        self.assertEqual(14, total)
        self.assertEqual("2 + 3 * 4 = 14", detail)

    def test_parentheses_and_division(self):
        total, detail = parse_dice_expression("8/(2+2)")

        self.assertEqual(2, total)
        self.assertEqual("8 / (2 + 2) = 2", detail)

    def test_dice_can_be_used_inside_parentheses(self):
        random.seed(1)

        total, detail = parse_dice_expression("(1d6+2)*3/2")

        self.assertIsNotNone(total)
        self.assertIn("(", detail)
        self.assertIn("* 3 / 2", detail)

    def test_keep_highest_and_lowest_still_work(self):
        random.seed(2)

        high_total, high_detail = parse_dice_expression("4d6k3")
        low_total, low_detail = parse_dice_expression("4d6k-2")

        self.assertIsInstance(high_total, int)
        self.assertIsInstance(low_total, int)
        self.assertIn("丢弃", high_detail)
        self.assertIn("丢弃", low_detail)

    def test_repeat_roll_keeps_last_total_and_all_result_lines(self):
        random.seed(3)

        total, detail = parse_dice_expression("3#1d1")

        self.assertEqual(1, total)
        self.assertEqual(3, len(detail.splitlines()))

    def test_vampire_roll_has_no_numeric_total(self):
        random.seed(4)

        total, detail = parse_dice_expression("5d10v7")

        self.assertIsNone(total)
        self.assertIn("难度7", detail)

    def test_division_by_zero_reports_error(self):
        total, detail = parse_dice_expression("1d6/0")

        self.assertIsNone(total)
        self.assertIn("除数不能为 0", detail)

    def test_roll_d66_single_and_multiple_results(self):
        random.seed(5)

        single = roll_d66()
        multiple = roll_d66(3)

        self.assertRegex(single, r"^D66 = [1-6][1-6]$")
        self.assertRegex(multiple, r"^D66 = [1-6][1-6], [1-6][1-6], [1-6][1-6]$")

    def test_roll_d66_limits_count(self):
        random.seed(6)

        result = roll_d66(100)

        self.assertEqual(20, len(result.replace("D66 = ", "").split(", ")))

    def test_parse_choice_options_supports_common_separators(self):
        self.assertEqual(["调查", "潜入", "跑路"], parse_choice_options("调查/潜入/跑路"))
        self.assertEqual(["苹果", "香蕉", "梨"], parse_choice_options("苹果 香蕉 梨"))
        self.assertEqual(["红", "蓝"], parse_choice_options("红|蓝"))

    def test_choose_option_requires_at_least_two_options(self):
        self.assertIn("选择项不足", choose_option("只有一个"))

    def test_choose_option_picks_one_of_options(self):
        random.seed(7)

        result = choose_option("调查/潜入/跑路")

        self.assertIn(result.replace("我选：", ""), ["调查", "潜入", "跑路"])

    def test_roll_attribute_until_success_reports_attempts_and_first_ten(self):
        original_get_roll_result = dice.get_roll_result
        original_get_success_rank = dice.get_success_rank
        ranks = [1] * 12 + [2]

        try:
            dice.get_roll_result = lambda roll, value, group: "成功" if ranks[0] >= 2 else "失败"

            def fake_rank(_roll, _value, _group):
                return ranks.pop(0)

            dice.get_success_rank = fake_rank
            random.seed(8)

            result = dice.roll_attribute_until_success("侦查", 70, "group", "Alice")

            self.assertIn("第 13 次成功", result)
            self.assertIn("前10次结果", result)
            self.assertIn("10.", result)
            self.assertNotIn("11.", result)
        finally:
            dice.get_roll_result = original_get_roll_result
            dice.get_success_rank = original_get_success_rank

    def test_opposed_check_both_fail_has_no_winner_even_if_one_fumbles(self):
        original_randint = random.randint
        rolls = [80, 100]

        try:
            random.randint = lambda _low, _high: rolls.pop(0)
            result = dice.roll_opposed_check("Alice的侦查", 50, "Bob的侦查", 50, "group")

            self.assertIn("双方均失败，无胜者", result)
        finally:
            random.randint = original_randint


if __name__ == "__main__":
    unittest.main()
