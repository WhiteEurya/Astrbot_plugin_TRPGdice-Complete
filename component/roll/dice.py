import random
import re
import datetime
import hashlib

from ..common.output import get_output
from ..coc.rules import great_success_range, great_failure_range, get_great_sf_rule, set_great_sf_rule, GREAT_SF_RULE_DEFAULT, GREAT_SF_RULE_STR

DEFAULT_DICE = 100

def roll_dice(dice_count, dice_faces):
    """掷 `dice_count` 个 `dice_faces` 面骰"""
    return [random.randint(1, dice_faces) for _ in range(dice_count)]

def roll_coc_bonus_penalty(base_roll, bonus_dice=0, penalty_dice=0):
    """奖励骰 / 惩罚骰"""
    tens_digit = base_roll // 10
    ones_digit = base_roll % 10
    if ones_digit == 0:
        ones_digit = 10

    alternatives = []
    for _ in range(max(bonus_dice, penalty_dice)):
        new_tens = random.randint(0, 9)
        alternatives.append(new_tens * 10 + ones_digit)

    if bonus_dice > 0:
        return min([base_roll] + alternatives)
    elif penalty_dice > 0:
        return max([base_roll] + alternatives)
    return base_roll

import re
import random

def _format_number(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(round(value, 2)) if isinstance(value, float) else str(value)

def _roll_dice_term(expr, bonus_dice=0, penalty_dice=0):
    match = re.fullmatch(r"(\d*)d(\d+)(k-?\d+)?(v(\d+)?)?", expr, re.IGNORECASE)
    if not match:
        return None, f"⚠️ 格式错误 `{expr}`", False

    dice_count = int(match.group(1)) if match.group(1) else 1
    dice_faces = int(match.group(2))
    keep_count = int(match.group(3)[1:]) if match.group(3) else dice_count
    vampire_difficulty = (int(match.group(5)) if match.group(5) and match.group(5).strip() != "v" else 6) if match.group(4) else None

    if not (1 <= dice_count <= 100 and 1 <= dice_faces <= 1000):
        return None, "⚠️ 骰子个数 1-100，面数 1-1000，否则非法！", False

    if dice_count == 1 and dice_faces == 100 and (bonus_dice > 0 or penalty_dice > 0):
        unit = random.randint(0, 9)
        num_tens_dice = 1 + max(bonus_dice, penalty_dice)
        rolls = [random.randint(0, 9) for _ in range(num_tens_dice)]
        final_tens = min(rolls) if bonus_dice > 0 else max(rolls)
        subtotal = final_tens * 10 + unit
        if subtotal == 0:
            subtotal = 100
        roll_type = f"{bonus_dice}B" if bonus_dice > 0 else f"{penalty_dice}P"
        return subtotal, f"[({roll_type}) 十:{','.join(map(str, rolls))} 个:{unit} -> {subtotal}]", False

    if vampire_difficulty:
        rolls = [random.randint(1, dice_faces) for _ in range(dice_count)]
        sorted_rolls = sorted(rolls, reverse=True)
        success_num = 0
        failure_flag = False
        success_flag = False
        super_failure = False

        for a_roll in sorted_rolls:
            if a_roll == 1:
                success_num -= 1
                failure_flag = True
            elif a_roll >= vampire_difficulty:
                success_num += 1
                success_flag = True
        if failure_flag and not success_flag:
            super_failure = True

        detail = f"[{','.join(map(str, sorted_rolls))}] 难度{vampire_difficulty}"
        if success_num > 0:
            detail += f" = 成功数 {success_num}"
        elif super_failure:
            detail += " = 大失败！"
        else:
            detail += " = 失败"
        return None, detail, True

    rolls = [random.randint(1, dice_faces) for _ in range(dice_count)]
    keep_lowest = keep_count < 0
    keep_amount = abs(keep_count)
    if keep_amount < 1 or keep_amount > dice_count:
        return None, f"⚠️ 保留骰数量必须在 1-{dice_count} 之间！", False

    sorted_rolls = sorted(rolls, reverse=not keep_lowest)
    selected_rolls = sorted_rolls[:keep_amount]
    subtotal = sum(selected_rolls)
    detail = f"[{' + '.join(map(str, selected_rolls))}]"

    if keep_amount < dice_count:
        dropped = " ".join(map(str, sorted_rolls[keep_amount:]))
        detail = f"[{' + '.join(map(str, selected_rolls))} | 丢弃: {dropped}]"

    return subtotal, detail, False

def _tokenize_dice_expression(expression, bonus_dice=0, penalty_dice=0):
    tokens = []
    i = 0

    while i < len(expression):
        char = expression[i]
        if char.isspace():
            i += 1
            continue

        if char in "+-*/()":
            tokens.append((char, char, char))
            i += 1
            continue

        dice_match = re.match(r"(\d*)d(\d+)(k-?\d+)?(v(\d+)?)?", expression[i:], re.IGNORECASE)
        if dice_match and dice_match.group(0):
            dice_expr = dice_match.group(0)
            value, detail, is_vampire_roll = _roll_dice_term(dice_expr, bonus_dice, penalty_dice)
            if value is None and not is_vampire_roll:
                return None, detail
            tokens.append(("VAMPIRE" if is_vampire_roll else "NUMBER", value, detail))
            i += len(dice_expr)
            continue

        number_match = re.match(r"\d+(?:\.\d+)?", expression[i:])
        if number_match:
            number_text = number_match.group(0)
            value = float(number_text) if "." in number_text else int(number_text)
            tokens.append(("NUMBER", value, number_text))
            i += len(number_text)
            continue

        return None, f"⚠️ 格式错误 `{expression[i:]}`"

    return tokens, None

class _DiceExpressionParser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def current(self):
        if self.pos >= len(self.tokens):
            return None
        return self.tokens[self.pos]

    def consume(self):
        token = self.current()
        self.pos += 1
        return token

    def parse(self):
        value, detail, is_vampire_roll = self.parse_expression()
        if is_vampire_roll and len(self.tokens) == 1:
            return None, detail, True, None
        if is_vampire_roll:
            return None, None, False, "⚠️ 吸血鬼骰不能参与四则运算。"
        if self.current() is not None:
            return None, None, False, f"⚠️ 格式错误 `{self.current()[2]}`"
        return value, detail, False, None

    def parse_expression(self):
        value, detail, is_vampire_roll = self.parse_term()
        while self.current() and self.current()[0] in {"+", "-"}:
            op = self.consume()[0]
            right_value, right_detail, right_vampire = self.parse_term()
            is_vampire_roll = is_vampire_roll or right_vampire
            if not is_vampire_roll:
                value = value + right_value if op == "+" else value - right_value
            detail = f"{detail} {op} {right_detail}"
        return value, detail, is_vampire_roll

    def parse_term(self):
        value, detail, is_vampire_roll = self.parse_factor()
        while self.current() and self.current()[0] in {"*", "/"}:
            op = self.consume()[0]
            right_value, right_detail, right_vampire = self.parse_factor()
            is_vampire_roll = is_vampire_roll or right_vampire
            if not is_vampire_roll:
                if op == "/" and right_value == 0:
                    raise ZeroDivisionError
                value = value * right_value if op == "*" else value / right_value
            detail = f"{detail} {op} {right_detail}"
        return value, detail, is_vampire_roll

    def parse_factor(self):
        token = self.current()
        if token is None:
            raise ValueError("表达式不完整")

        if token[0] in {"+", "-"}:
            op = self.consume()[0]
            value, detail, is_vampire_roll = self.parse_factor()
            if is_vampire_roll:
                return value, f"{op}{detail}", True
            return (value if op == "+" else -value), f"{op}{detail}", False

        if token[0] == "(":
            self.consume()
            value, detail, is_vampire_roll = self.parse_expression()
            if not self.current() or self.current()[0] != ")":
                raise ValueError("缺少右括号")
            self.consume()
            return value, f"({detail})", is_vampire_roll

        if token[0] in {"NUMBER", "VAMPIRE"}:
            self.consume()
            return token[1], token[2], token[0] == "VAMPIRE"

        raise ValueError(f"格式错误 `{token[2]}`")

def parse_dice_expression(expression):
    """
    解析骰子表达式，并格式化输出。
    支持普通骰、奖励/惩罚骰、吸血鬼骰等。
    返回 (总和, 格式化字符串)
    """
    expression_original = expression # 保留原始表达式用于显示
    expression = expression.replace("x", "*").replace("X", "*")

    match_repeat = re.match(r"(\d+)?#(.+)", expression)
    roll_times = 1
    bonus_dice = 0
    penalty_dice = 0

    if match_repeat:
        roll_times = int(match_repeat.group(1)) if match_repeat.group(1) else 1
        expression = match_repeat.group(2)
        expression_original = expression # 重复掷骰时，只显示单次表达式

        if expression in ["p", "b"]:
            penalty_dice = roll_times if expression == "p" else 0
            bonus_dice = roll_times if expression == "b" else 0
            expression = "1d100"
            expression_original = f"{roll_times}{expression}" # e.g. "3b"
            roll_times = 1

    final_results_list = []
    final_total = None # 存储最后一次掷骰的总和

    for _ in range(roll_times):
        tokens, error = _tokenize_dice_expression(expression, bonus_dice, penalty_dice)
        if error:
            return None, error

        try:
            total, detail, is_vampire_roll, error = _DiceExpressionParser(tokens).parse()
        except ZeroDivisionError:
            return None, "⚠️ 除数不能为 0！"
        except ValueError as exc:
            return None, f"⚠️ {exc}"

        if error:
            return None, error
        if is_vampire_roll:
            final_total = None
            final_results_list.append(f"{expression_original} = {detail}")
            continue

        final_total = total
        final_results_list.append(f"{detail} = {_format_number(total)}")
    return final_total, "\n".join(final_results_list)

def roll_attribute(roll_times, skill_name, skill_value, group_id, name):
    """
    普通技能判定 (支持多次, 适配 head/detail)
    """
    try:
        roll_times = int(roll_times)
        skill_value = int(skill_value)
    except ValueError:
        return get_output("skill_check.error.normal", skill_name=skill_name)

    # 1. 打印一次头部
    head_str = get_output(
        "skill_check.normal.head",
        skill_name=skill_name,
        name=name
    )
    
    results_list = [head_str] # 用头部初始化列表

    # 2. 循环 N 次, 仅生成 detail
    for _ in range(roll_times):
        tens_digit = random.randint(0, 9)
        ones_digit = random.randint(0, 9)
        roll_result = 100 if (tens_digit == 0 and ones_digit == 0) else (tens_digit * 10 + ones_digit)

        result = get_roll_result(roll_result, skill_value, str(group_id))

        detail_str = get_output(
            "skill_check.normal.detail",
            roll_result=roll_result,
            skill_value=skill_value,
            result=result
        )
        results_list.append(detail_str)
        
    return "".join(results_list) # 返回 "head\ndetail\ndetail..."

def roll_attribute_penalty(roll_times, dice_count, skill_name, skill_value, group_id, name):
    """
    技能判定（惩罚骰）(支持多次, 适配 head/detail)
    """
    try:
        roll_times = int(roll_times)
        dice_count = int(dice_count)
        skill_value = int(skill_value)
    except ValueError:
        return get_output("skill_check.error.penalty", skill_name=skill_name)

    # 1. 打印一次头部
    head_str = get_output(
        "skill_check.penalty.head",
        skill_name=skill_name,
        name=name
    )
    
    results_list = [head_str] # 用头部初始化列表

    # 2. 循环 N 次, 仅生成 detail
    for _ in range(roll_times):
        ones_digit = random.randint(0, 9)
        new_tens_digits = [random.randint(0, 9) for _ in range(dice_count)]
        new_tens_digits.append(random.randint(0, 9))

        if 0 in new_tens_digits and ones_digit == 0:
            final_y = 100
        else:
            final_tens = max(new_tens_digits)
            final_y = final_tens * 10 + ones_digit

        result = get_roll_result(final_y, skill_value, str(group_id))

        detail_str = get_output(
            "skill_check.penalty.detail",
            new_tens_digits=new_tens_digits,
            final_y=final_y,
            skill_value=skill_value,
            result=result
        )
        results_list.append(detail_str)
        
    return "".join(results_list)

def roll_attribute_bonus(roll_times, dice_count, skill_name, skill_value, group_id, name):
    """
    技能判定（奖励骰）(支持多次, 适配 head/detail)
    """
    try:
        roll_times = int(roll_times)
        dice_count = int(dice_count)
        skill_value = int(skill_value)
    except ValueError:
        return get_output("skill_check.error.bonus", skill_name=skill_name)

    # 1. 打印一次头部
    head_str = get_output(
        "skill_check.bonus.head",
        skill_name=skill_name,
        name=name
    )
    
    results_list = [head_str] # 用头部初始化列表

    # 2. 循环 N 次, 仅生成 detail
    for _ in range(roll_times):
        ones_digit = random.randint(0, 9)
        new_tens_digits = [random.randint(0, 9) for _ in range(dice_count)]
        new_tens_digits.append(random.randint(0, 9))

        filtered_tens = [tens for tens in new_tens_digits if not (tens == 0 and ones_digit == 0)]
        if not filtered_tens:
            final_tens = 0
        else:
            final_tens = min(filtered_tens)

        final_y = final_tens * 10 + ones_digit

        # --- BUG 修复：确保 00 = 100 ---
        if final_y == 0:
            final_y = 100
        # --- 修复结束 ---

        result = get_roll_result(final_y, skill_value, str(group_id))

        detail_str = get_output(
            "skill_check.bonus.detail",
            new_tens_digits=new_tens_digits,
            final_y=final_y,
            skill_value=skill_value,
            result=result
        )
        results_list.append(detail_str)
        
    return "".join(results_list)

def roll_attribute_until_success(skill_name, skill_value, group_id, name, max_attempts: int = 10000):
    try:
        skill_value = int(skill_value)
    except ValueError:
        return get_output("skill_check.error.normal", skill_name=skill_name)

    attempts = 0
    first_results = []

    while attempts < max_attempts:
        attempts += 1
        tens_digit = random.randint(0, 9)
        ones_digit = random.randint(0, 9)
        roll_result = 100 if (tens_digit == 0 and ones_digit == 0) else (tens_digit * 10 + ones_digit)
        result = get_roll_result(roll_result, skill_value, str(group_id))

        if attempts <= 10:
            first_results.append(f"{attempts}. {roll_result}/{skill_value} {result}")

        if get_success_rank(roll_result, skill_value, str(group_id)) >= 2:
            lines = [
                f"{name} 的【{skill_name}】连续检定直到成功：",
                f"第 {attempts} 次成功。",
                "前10次结果：",
                "\n".join(first_results),
            ]
            return "\n".join(lines)

    return (
        f"{name} 的【{skill_name}】连续检定直到成功：\n"
        f"已达到 {max_attempts} 次上限，仍未成功。\n"
        "前10次结果：\n"
        + "\n".join(first_results)
    )

def handle_roll_dice(expression: str, user_id: str = None, name : str = None, remark = None):
    """
    处理骰子表达式，返回格式化后的掷骰结果字符串。
    可根据需要扩展 user_id 用于个性化输出。
    """
    total, result_message = parse_dice_expression(expression)
    if total is None:
        return get_output("dice.normal.error", error=result_message)
    else:
        if not remark :
            return get_output("dice.normal.success", result=result_message, total=total, name = name)
        else :
            return get_output("dice.normal.success_remark", result=result_message, total=total, name = name, remark = remark)

def roll_dice_vampire(dice_count: int, difficulty: int):
    """
    吸血鬼规则掷骰，返回格式化字符串。
    """
    expr = f"{dice_count}d10v{difficulty}"
    _, result_message = parse_dice_expression(expr)
    return result_message

def roll_hidden(message: str = None):
    """
    私聊掷骰，返回格式化字符串。
    """
    message = message.strip() if message else f"1d{DEFAULT_DICE}"
    total, result_message = parse_dice_expression(message)
    if total is None:
        return get_output("dice.hidden.error", error=result_message)
    else:
        return get_output("dice.hidden.success", result=result_message)

def get_roll_result(roll_result: int, skill_value: int, group: str):
    """
    根据掷骰结果和技能值计算判定结果文本（COC规则）。
    所有输出建议通过 get_output 配置。
    """
    try:
        rule = get_great_sf_rule(group)
    except Exception:
        return get_output("coc_roll.results.error", error="Failed to fetch rule")

    validation_prefix = ""
    if great_success_range(50, rule)[0] <= 0:
        set_great_sf_rule(GREAT_SF_RULE_DEFAULT, group)
        validation_prefix += get_output("coc_roll.results.reset", rule=GREAT_SF_RULE_STR[GREAT_SF_RULE_DEFAULT])

    if roll_result in great_success_range(skill_value, rule):
        return validation_prefix + get_output("coc_roll.results.great_success")
    elif roll_result <= skill_value / 5:
        return validation_prefix + get_output("coc_roll.results.extreme_success")
    elif roll_result <= skill_value / 2:
        return validation_prefix + get_output("coc_roll.results.hard_success")
    elif roll_result <= skill_value:
        return validation_prefix + get_output("coc_roll.results.success")
    elif roll_result in great_failure_range(skill_value, rule):
        return validation_prefix + get_output("coc_roll.results.great_failure")
    else:
        return validation_prefix + get_output("coc_roll.results.failure")


def get_success_rank(roll_result: int, skill_value: int, group: str) -> int:
    try:
        rule = get_great_sf_rule(group)
    except Exception:
        rule = GREAT_SF_RULE_DEFAULT

    if roll_result in great_success_range(skill_value, rule):
        return 5
    if roll_result in great_failure_range(skill_value, rule):
        return 0
    if roll_result <= skill_value / 5:
        return 4
    if roll_result <= skill_value / 2:
        return 3
    if roll_result <= skill_value:
        return 2
    return 1


def roll_opposed_check(left_name: str, left_value: int, right_name: str, right_value: int, group_id: str) -> str:
    left_roll = random.randint(1, 100)
    right_roll = random.randint(1, 100)
    left_rank = get_success_rank(left_roll, left_value, group_id)
    right_rank = get_success_rank(right_roll, right_value, group_id)
    left_result = get_roll_result(left_roll, left_value, group_id)
    right_result = get_roll_result(right_roll, right_value, group_id)

    if left_rank <= 1 and right_rank <= 1:
        winner = "双方均失败，无胜者"
    elif left_rank > right_rank:
        winner = left_name
    elif right_rank > left_rank:
        winner = right_name
    elif left_value > right_value:
        winner = left_name
    elif right_value > left_value:
        winner = right_name
    else:
        winner = "平局"

    return (
        "来，让我听听这一次风会偏向哪一边。\n"
        "对抗检定结果：\n"
        f"{left_name}：{left_roll}/{left_value} —— {left_result}\n"
        f"{right_name}：{right_roll}/{right_value} —— {right_result}\n"
        f"嗯……我听清楚了，这次是：{winner}"
    )

def fireball(ring: int = 3):
    """
    施放 n 环火球术，返回伤害字符串。
    """
    if ring < 3:
        return get_output("fireball.low")
    rolls = [random.randint(1, 6) for _ in range(8 + (ring - 3))]
    total_sum = sum(rolls)
    damage_breakdown = " + ".join(map(str, rolls))
    return get_output(
        "fireball.result",
        ring=ring,
        breakdown=damage_breakdown,
        total=total_sum
    )

def roll_RP(user_id: str):
    """
    今日RP（运势），返回字符串。
    """
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    RP_str = f"{user_id}_{today}"
    hash = hashlib.sha256(RP_str.encode()).hexdigest()
    rp = int(hash, 16) % 100 + 1
    return get_output("rp.today", rp=rp)

def roll_d66(count: int = 1) -> str:
    count = max(1, min(int(count), 20))
    results = []
    for _ in range(count):
        tens = random.randint(1, 6)
        ones = random.randint(1, 6)
        results.append(f"{tens}{ones}")

    if count == 1:
        return f"D66 = {results[0]}"
    return "D66 = " + ", ".join(results)

def parse_choice_options(raw_options: str):
    raw_options = (raw_options or "").strip()
    if not raw_options:
        return []

    if any(separator in raw_options for separator in ["|", "/", "，", ","]):
        parts = re.split(r"[|/，,]", raw_options)
    else:
        parts = raw_options.split()

    return [part.strip() for part in parts if part.strip()]

def choose_option(raw_options: str) -> str:
    options = parse_choice_options(raw_options)
    if len(options) < 2:
        return "选择项不足：请使用 .choose 选项A 选项B，或用 /、|、逗号分隔。"

    choice = random.choice(options)
    return f"我选：{choice}"


def handle_pistol_fire(full_args: str, name: str, chara_data: dict = None) -> str:
    """
    手枪三连发后端逻辑 - 适配感性语词模板
    """
    # 1. 解析模式与惩罚规律
    penalty_pattern = [0, 0, 0]
    mode_label = "常规连射"
    if 'p2' in full_args:
        penalty_pattern = [0, 1, 2]
        mode_label = "后坐力递增"
    else :
        penalty_pattern = [1, 1, 1]
        mode_label = "精度下降"

    # 2. 确定技能值与名称
    skill_val_match = re.search(r'(?<!p)(\d{2,3})', full_args)
    if skill_val_match:
        skill_value = int(skill_val_match.group(1))
        skill_name = "手枪(指定)"
    elif chara_data:
        attrs = chara_data.get("attributes", {})
        # 依次查找：手枪、射击(手枪)、射击
        skill_value = attrs.get("手枪", attrs.get("射击(手枪)", attrs.get("射击", 20)))
        skill_name = "手枪"
    else:
        skill_value = 20
        skill_name = "手枪"

    # 3. 生成头部 (Head)
    head_str = get_output(
        "skill_check.pistol_check.head", 
        name=name, 
        skill_name=skill_name, 
        mode=mode_label
    )
    results_list = [head_str]

    # 4. 生成每一发的结果 (Detail)
    for i, p_count in enumerate(penalty_pattern):
        # 基础 1D100
        tens = random.randint(0, 9)
        ones = random.randint(0, 9)
        base_roll = 100 if (tens == 0 and ones == 0) else (tens * 10 + ones)
        
        final_roll = base_roll
        p_info = ""

        # 惩罚骰逻辑：十位取最高
        if p_count > 0:
            original_tens = tens if base_roll != 100 else 0
            p_tens_list = [random.randint(0, 9) for _ in range(p_count)]
            final_tens = max([original_tens] + p_tens_list)
            
            # 重新组合结果
            final_roll = 100 if (final_tens == 0 and ones == 0) else (final_tens * 10 + ones)
            p_info = f"[{tens}, {', '.join(map(str, p_tens_list))}]"

        # 判定成功等级 (调用你之前的 get_roll_result)
        # 这里的 group_id 传入空字符串或当前群ID
        result_level = get_roll_result(final_roll, skill_value, "")

        # 拼接详情
        detail_str = get_output(
            "skill_check.pistol_check.detail",
            i=i+1,
            p=p_count,
            roll=final_roll,
            p_info=p_info,
            skill_value=skill_value,
            result=result_level
        )
        results_list.append(detail_str)

    return "".join(results_list)
