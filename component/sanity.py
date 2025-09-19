import random
import re
import os
import json

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))

# 恐惧
with open(PLUGIN_DIR + "/../data/phobias.json", "r", encoding="utf-8") as f:
    phobias = json.load(f)["phobias"]

# 躁狂
with open(PLUGIN_DIR + "/../data/mania.json", "r", encoding="utf-8") as f:
    manias = json.load(f)["manias"]

def parse_san_loss_formula(formula: str):
    """
    解析 SAN 损失公式，返回成功和失败时的损失表达式。
    例如 "1d6/1d10" -> ("1d6", "1d10")
    """
    parts = formula.split("/")
    success_part = parts[0]
    failure_part = parts[1] if len(parts) > 1 else parts[0]
    return success_part, failure_part

def roll_loss(loss_expr: str):
    """
    根据损失表达式计算损失值。
    支持 "XdY" 或纯数字。
    """
    match = re.fullmatch(r"(\d+)d(\d+)", loss_expr)
    if match:
        num_dice, dice_size = map(int, match.groups())
        return sum(random.randint(1, dice_size) for _ in range(num_dice))
    elif loss_expr.isdigit():
        return int(loss_expr)
    return 0

def san_check(chara_data: dict, loss_formula: str):
    """
    进行一次理智检定，返回检定结果和损失值。
    chara_data: 当前人物卡数据（需包含'san'属性）
    loss_formula: 损失公式，如 "1d6/1d10"
    返回：(roll_result, san_value, result_msg, loss, new_san)
    """
    san_value = chara_data["attributes"].get("san", 0)
    roll_result = random.randint(1, 100)
    success_loss, failure_loss = parse_san_loss_formula(loss_formula)

    if roll_result <= san_value:
        loss = roll_loss(success_loss)
        result_msg = "成功！"
    else:
        loss = roll_loss(failure_loss)
        result_msg = "失败..."

    new_san = max(0, san_value - loss)
    return roll_result, san_value, result_msg, loss, new_san

def get_temporary_insanity(phobias: dict, manias: dict):
    """
    随机生成临时疯狂症状，返回症状文本。
    phobias, manias: 恐惧症和躁狂症字典
    """
    temporary_insanity = {
        1: "失忆：调查员只记得最后身处的安全地点，却没有任何来到这里的记忆。这将会持续 1D10 轮。",
        2: "假性残疾：调查员陷入心理性的失明、失聪或躯体缺失感，持续 1D10 轮。",
        3: "暴力倾向：调查员对周围所有人（敌人和同伴）展开攻击，持续 1D10 轮。",
        4: "偏执：调查员陷入严重的偏执妄想（所有人都想伤害他），持续 1D10 轮。",
        5: "人际依赖：调查员误认为某人是他的重要之人，并据此行动，持续 1D10 轮。",
        6: "昏厥：调查员当场昏倒，1D10 轮后苏醒。",
        7: "逃避行为：调查员试图用任何方式逃离当前场所，持续 1D10 轮。",
        8: "歇斯底里：调查员陷入极端情绪（大笑、哭泣、尖叫等），持续 1D10 轮。",
        9: "恐惧：骰 1D100 或由守秘人选择一个恐惧症，调查员会想象它存在，持续 1D10 轮。",
        10: "躁狂：骰 1D100 或由守秘人选择一个躁狂症，调查员会沉溺其中，持续 1D10 轮。"
    }
    roll = random.randint(1, 10)
    result = temporary_insanity[roll].replace("1D10", str(random.randint(1, 10)))
    if roll == 9:
        fear_roll = random.randint(1, 100)
        result += f"\n→ 具体恐惧症：{phobias[str(fear_roll)]}（骰值 {fear_roll}）"
    if roll == 10:
        mania_roll = random.randint(1, 100)
        result += f"\n→ 具体躁狂症：{manias[str(mania_roll)]}（骰值 {mania_roll}）"
    return result

def get_long_term_insanity(phobias: dict, manias: dict):
    """
    随机生成长期疯狂症状，返回症状文本。
    phobias, manias: 恐惧症和躁狂症字典
    """
    long_term_insanity = {
        1: "失忆：调查员发现自己身处陌生地方，并忘记自己是谁。记忆会缓慢恢复。",
        2: "被窃：调查员 1D10 小时后清醒，发现自己身上贵重物品丢失。",
        3: "遍体鳞伤：调查员 1D10 小时后清醒，身体有严重伤痕（生命值剩一半）。",
        4: "暴力倾向：调查员可能在疯狂期间杀人或造成重大破坏。",
        5: "极端信念：调查员疯狂地执行某个信仰（如宗教狂热、政治极端），并采取极端行动。",
        6: "重要之人：调查员疯狂追求某个他在意的人，不顾一切地接近该人。",
        7: "被收容：调查员在精神病院或警察局醒来，完全不记得发生了什么。",
        8: "逃避行为：调查员在远离原地点的地方醒来，可能在荒郊野外或陌生城市。",
        9: "恐惧：调查员患上一种新的恐惧症（骰 1D100 或由守秘人选择）。",
        10: "躁狂：调查员患上一种新的躁狂症（骰 1D100 或由守秘人选择）。"
    }
    roll = random.randint(1, 10)
    result = long_term_insanity[roll].replace("1D10", str(random.randint(1, 10)))
    if roll == 9:
        fear_roll = random.randint(1, 100)
        result += f"\n→ 具体恐惧症：{phobias[str(fear_roll)]}（骰值 {fear_roll}）"
    if roll == 10:
        mania_roll = random.randint(1, 100)
        result += f"\n→ 具体躁狂症：{manias[str(mania_roll)]}（骰值 {mania_roll}）"
    return result