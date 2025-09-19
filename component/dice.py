import random
import re
import datetime
import hashlib

from .output import get_output
from .rules import great_success_range, great_failure_range, get_great_sf_rule, set_great_sf_rule, GREAT_SF_RULE_DEFAULT, GREAT_SF_RULE_STR

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

def parse_dice_expression(expression):
    """
    解析骰子表达式，并格式化输出。
    支持普通骰、奖励/惩罚骰、吸血鬼骰等。
    返回 (总和, 格式化字符串)
    """
    expression = expression.replace("x", "*").replace("X", "*")

    match_repeat = re.match(r"(\d+)?#(.+)", expression) # Match 3#2d20
    roll_times = 1
    bonus_dice = 0
    penalty_dice = 0

    if match_repeat:    # Matched: roll group(2) for group(1) times
        roll_times = int(match_repeat.group(1)) if match_repeat.group(1) else 1
        expression = match_repeat.group(2)

        if expression in ["p", "b"]:
            penalty_dice = 1 if expression == "p" else 0
            bonus_dice = 1 if expression == "b" else 0
            expression = "1d100"

    results = []
    total = None
    for _ in range(roll_times):
        parts = re.split(r"([+\-*])", expression)
        subtotal = None
        formatted_parts = []

        for i in range(0, len(parts), 2):
            expr = parts[i].strip()
            operator = parts[i - 1] if i > 0 else "+"

            if expr.isdigit():
                subtotal = int(expr)
                roll_result = f"{subtotal}"
            else:
                match = re.match(r"(\d*)d(\d+)(k\d+)?([+\-*]\d+)?(v(\d+)?)?", expr)
                if not match:
                    return None, f"⚠️ 格式错误 `{expr}`"

                dice_count = int(match.group(1)) if match.group(1) else 1
                dice_faces = int(match.group(2))
                keep_highest = int(match.group(3)[1:]) if match.group(3) else dice_count
                modifier = match.group(4)
                vampire_difficulty = (int(match.group(6)) if match.group(5) and match.group(5).strip() != "v" else 6) if match.group(5) else None

                if not (1 <= dice_count <= 100 and 1 <= dice_faces <= 1000):
                    return None, "⚠️ 骰子个数 1-100，面数 1-1000，否则非法！"

                # COC 奖励/惩罚骰
                if dice_count == 1 and dice_faces == 100 and (bonus_dice > 0 or penalty_dice > 0):
                    base_tens = random.randint(0, 9)
                    unit = random.randint(0, 9)
                    rolls = [random.randint(0, 9) for _ in range(1 + max(bonus_dice, penalty_dice))]
                    if bonus_dice > 0:
                        final_tens = min(rolls[:1 + bonus_dice])
                        roll_type = "奖励骰"
                    else:
                        final_tens = max(rolls[:1 + penalty_dice])
                        roll_type = "惩罚骰"
                    subtotal = final_tens * 10 + unit
                    roll_result = f"{expr} = [D100: {base_tens * 10 + unit}, {roll_type}: {', '.join(map(str, rolls))}] → {subtotal}"

                elif vampire_difficulty:
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

                    roll_result = f"难度为{vampire_difficulty}的{dice_count}次掷骰 = [{', '.join(map(str, sorted_rolls))}]"
                    if success_num > 0:
                        roll_result += f"，成功！成功数为{success_num}"
                    elif super_failure:
                        roll_result += "，大失败！"
                    else:
                        roll_result += "，失败！"
                    subtotal = None  # 吸血鬼骰不返回总和

                else:
                    # 普通骰子
                    rolls = [random.randint(1, dice_faces) for _ in range(dice_count)]
                    sorted_rolls = sorted(rolls, reverse=True)
                    selected_rolls = sorted_rolls[:keep_highest]
                    subtotal_before_mod = sum(selected_rolls)

                    if keep_highest < dice_count:
                        kept = " ".join(map(str, sorted_rolls[:keep_highest]))
                        dropped = " ".join(map(str, sorted_rolls[keep_highest:]))
                        roll_result = f"{dice_count}d{dice_faces}k{keep_highest}={subtotal_before_mod} [{kept} | {dropped}]"
                    else:
                        roll_result = f"{dice_count}d{dice_faces}={subtotal_before_mod} [{' + '.join(map(str, rolls))}]"

                    if modifier:
                        try:
                            subtotal = eval(f"{subtotal_before_mod}{modifier}")
                            roll_result = f"{dice_count}d{dice_faces}{modifier}={subtotal_before_mod} [{' + '.join(map(str, rolls))}] {modifier} = {subtotal}"
                        except:
                            return None, f"⚠️ 修正值 `{modifier}` 无效！"
                    else:
                        subtotal = subtotal_before_mod

            # 计算表达式
            if not vampire_difficulty:
                if total is None:
                    total = subtotal
                else:
                    if operator == "+":
                        total += subtotal
                    elif operator == "-":
                        total -= subtotal
                    elif operator == "*":
                        total *= subtotal

            # 存储格式化骰子结果
            if i == 0:
                formatted_parts.append(f"{roll_result}")
            else:
                formatted_parts.append(f"{operator} {roll_result}")

        # 最终格式化输出
        if not vampire_difficulty:
            final_result = f"{'  '.join(formatted_parts)} = {total}"
            results.append(f"{final_result}")
        else:
            final_result = f"{'  '.join(formatted_parts)}"
            results.append(f"{final_result}")

    return total, "\n".join(results)

def roll_attribute(skill_name, skill_value, group_id, name):
    """
    普通技能判定
    """
    try:
        skill_value = int(skill_value)
    except ValueError:
        return get_output("skill_check.error.normal", skill_name=skill_name)

    tens_digit = random.randint(0, 9)
    ones_digit = random.randint(0, 9)
    roll_result = 100 if (tens_digit == 0 and ones_digit == 0) else (tens_digit * 10 + ones_digit)

    # 这里建议 get_roll_result 也迁移到 dice.py 或 rules.py
    result = get_roll_result(roll_result, skill_value, str(group_id))

    return get_output(
        "skill_check.normal",
        skill_name=skill_name,
        roll_result=roll_result,
        skill_value=skill_value,
        result=result,
        name = name
    )

def roll_attribute_penalty(dice_count, skill_name, skill_value, group_id, name):
    """
    技能判定（惩罚骰）
    """
    try:
        dice_count = int(dice_count)
        skill_value = int(skill_value)
    except ValueError:
        return get_output("skill_check.error.penalty", skill_name=skill_name)

    ones_digit = random.randint(0, 9)
    new_tens_digits = [random.randint(0, 9) for _ in range(dice_count)]
    new_tens_digits.append(random.randint(0, 9))

    if 0 in new_tens_digits and ones_digit == 0:
        final_y = 100
    else:
        final_tens = max(new_tens_digits)
        final_y = final_tens * 10 + ones_digit

    result = get_roll_result(final_y, skill_value, str(group_id))

    return get_output(
        "skill_check.penalty",
        skill_name=skill_name,
        new_tens_digits=new_tens_digits,
        final_y=final_y,
        skill_value=skill_value,
        result=result,
        name = name
    )

def roll_attribute_bonus(dice_count, skill_name, skill_value, group_id, name):
    """
    技能判定（奖励骰）
    """
    try:
        dice_count = int(dice_count)
        skill_value = int(skill_value)
    except ValueError:
        return get_output("skill_check.error.bonus", skill_name=skill_name)

    ones_digit = random.randint(0, 9)
    new_tens_digits = [random.randint(0, 9) for _ in range(dice_count)]
    new_tens_digits.append(random.randint(0, 9))

    filtered_tens = [tens for tens in new_tens_digits if not (tens == 0 and ones_digit == 0)]
    if not filtered_tens:
        final_tens = 0
    else:
        final_tens = min(filtered_tens)

    final_y = final_tens * 10 + ones_digit

    result = get_roll_result(final_y, skill_value, str(group_id))

    return get_output(
        "skill_check.bonus",
        skill_name=skill_name,
        new_tens_digits=new_tens_digits,
        final_y=final_y,
        skill_value=skill_value,
        result=result,
        name = name
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
        if remark is None :
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

