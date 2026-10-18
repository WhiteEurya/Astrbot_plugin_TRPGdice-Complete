"""DnD simplified sheets: raw scores, extra modifiers, and proficiency metadata."""

from copy import deepcopy
import math
import re

from ..roll.dice import parse_dice_expression
from ..common.output import get_output
from .classes import CLASS_HELP, format_classes, format_subclass_catalog, update_classes
from .resources import format_resources


ABILITIES = ("力量", "敏捷", "体质", "智力", "感知", "魅力")
SKILLS = {
    "运动": "力量", "特技": "敏捷", "巧手": "敏捷", "隐匿": "敏捷",
    "调查": "智力", "奥秘": "智力", "历史": "智力", "自然": "智力", "宗教": "智力",
    "察觉": "感知", "洞悉": "感知", "驯兽": "感知", "医疗": "感知", "求生": "感知",
    "游说": "魅力", "欺瞒": "魅力", "威吓": "魅力", "表演": "魅力",
}
ALIASES = {
    "level": "等级", "lvl": "等级", "lv": "等级",
    "力": "力量", "敏": "敏捷", "体": "体质", "智": "智力", "感": "感知", "魅": "魅力",
    "str": "力量", "dex": "敏捷", "con": "体质", "int": "智力", "wis": "感知", "cha": "魅力",
    "体操": "特技", "潜行": "隐匿", "侦察": "察觉", "生存": "求生",
    "说服": "游说", "欺诈": "欺瞒", "驯养": "驯兽", "驯服动物": "驯兽", "医学": "医疗",
    "生命": "hp", "生命值": "hp", "max_hp": "hpmax", "最大生命": "hpmax", "生命上限": "hpmax",
    "临时hp": "thp", "临时生命": "thp", "临时生命值": "thp", "temp_hp": "thp",
    "熟练加值": "熟练", "pb": "熟练", "护甲等级": "ac", "法术dc": "dc", "被动察觉": "pp",
    "initiative": "先攻", "athletics": "运动", "acrobatics": "特技", "sleight_of_hand": "巧手",
    "stealth": "隐匿", "investigation": "调查", "arcana": "奥秘", "history": "历史",
    "nature": "自然", "religion": "宗教", "perception": "察觉", "insight": "洞悉",
    "animal_handling": "驯兽", "medicine": "医疗", "survival": "求生", "persuasion": "游说",
    "deception": "欺瞒", "intimidation": "威吓", "performance": "表演",
}
PROTECTED = set(ABILITIES) | {"hp", "hpmax", "thp", "熟练", "等级"}
HEADER = re.compile(r"(?<![A-Za-z0-9_.])([\u4e00-\u9fffA-Za-z_][\u4e00-\u9fffA-Za-z_]*)(?:\*(0\.5|0|1|2)?)?\s*([:=+\-])")


def canonical(name):
    name = name.strip().lower()
    if name.endswith("豁"):
        name += "免"
    if name.endswith("豁免"):
        base = ALIASES.get(name[:-2], name[:-2])
        if base not in ABILITIES:
            raise ValueError("豁免必须使用六项基础属性。")
        return base + "豁免"
    return ALIASES.get(name, name)


def _attributes(card):
    if card.get("rule_system") != "dnd":
        raise ValueError("此人物卡不是 DnD 规则。")
    return card.get("attributes", {})


def modifier(score):
    return (int(score) - 10) // 2


def _proficiency(card, name):
    return math.floor(card.get("dnd_proficiency", {}).get(name, 0) * _attributes(card).get("熟练", 0))


def check_bonus(card, name):
    attrs = _attributes(card)
    name = canonical(name)
    if name in ABILITIES:
        if name not in attrs:
            raise ValueError(f"尚未录入属性：{name}")
        return modifier(attrs[name]), f"{name}调整值 {modifier(attrs[name]):+d}"
    if name in SKILLS or name.endswith("豁免"):
        ability = SKILLS[name] if name in SKILLS else name[:-2]
        if ability not in attrs:
            raise ValueError(f"尚未录入属性：{ability}")
        extra = attrs.get(name, 0)
        proficiency_name = name if name in SKILLS else ability
        trained = _proficiency(card, proficiency_name)
        value = modifier(attrs[ability]) + trained + extra
        return value, f"{ability}调整值 {modifier(attrs[ability]):+d}，熟练 {trained:+d}，额外修正 {extra:+d}"
    if name == "先攻":
        if name in attrs:
            return attrs[name], f"先攻 {attrs[name]:+d}"
        return check_bonus(card, "敏捷")
    if name in attrs:
        return attrs[name], f"{name} {attrs[name]:+d}"
    raise ValueError(f"未找到属性或技能：{name}")


def parse_entries(text):
    text = text.strip().replace("\\*", "*").replace("：", ":").replace("＝", "=")
    text = re.sub(r"^\.st\s+", "", text, flags=re.I)
    if len(text) > 10000:
        raise ValueError("录入内容过长。")
    matches = list(HEADER.finditer(text))
    if not matches or text[:matches[0].start()].strip() or len(matches) > 100:
        raise ValueError("请使用 .st 力量:8 敏捷:18 察觉*:0 熟练:3。")
    entries = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        expression = re.sub(r"\s+", "", text[match.end():end])
        if not expression or len(expression) > 200 or not re.fullmatch(r"[\d.dDkKmMiInNaAxXrRhHbBuUsStT,+*/()\->=!]+", expression):
            raise ValueError(f"无效数值或骰式：{expression}")
        factor = None
        if "*" in match.group(0):
            factor = float(match.group(2)) if match.group(2) is not None else 1
        name = canonical(match.group(1))
        if factor is not None and name not in ABILITIES and name not in SKILLS:
            raise ValueError("熟练星号只适用于六项属性的豁免或技能。")
        entries.append((name, factor, match.group(3), expression))
    return entries


class ProficiencyMismatch(ValueError):
    """A valid import whose explicit PB differs from the level-derived value."""

    def __init__(self, card, detail, expected):
        super().__init__(f"导入的熟练加值 {card['attributes']['熟练']} 与总等级计算值 {expected} 不符；已保留导入值。")
        self.card = card
        self.detail = detail


def update_card(card, text):
    _attributes(card)
    entries = parse_entries(text)
    result = deepcopy(card)
    attrs = result.setdefault("attributes", {})
    proficiency = result.setdefault("dnd_proficiency", {})
    changes = []
    for name, factor, operator, expression in entries:
        value, detail = parse_dice_expression(expression)
        if value is None or abs(value) > 1000000 or not math.isfinite(value) or value != int(value):
            raise ValueError(f"{name} 的数值必须是有效整数：{detail}")
        value = int(value)
        old = attrs.get(name, 0)
        if operator == "+":
            value = old + value
        elif operator == "-":
            value = old - value
        if name in ABILITIES and not 1 <= value <= 30:
            raise ValueError(f"{name} 必须在 1 到 30 之间。")
        if name == "等级" and not 1 <= value <= 20:
            raise ValueError("等级必须在 1 到 20 之间。")
        if name in {"hpmax", "thp", "熟练", "ac", "dc", "pp"}:
            value = max(0, value)
        if name == "hp" and operator == "-" and value < old:
            damage = max(0, old - value)
            absorbed = min(attrs.get("thp", 0), damage)
            attrs["thp"] = attrs.get("thp", 0) - absorbed
            value = max(0, old - damage + absorbed)
        if name == "hp":
            value = max(0, value)
            if operator in {"+", "-"} and "hpmax" in attrs:
                value = min(value, attrs["hpmax"])
        attrs[name] = value
        if factor is not None:
            proficiency[name] = factor
        changes.append(f"{name}: {old} -> {value}")
    if "hp" in attrs and "hpmax" in attrs:
        attrs["hp"] = min(attrs["hp"], attrs["hpmax"])
    if result.get("dnd_classes") and attrs.get("等级") != sum(item["level"] for item in result["dnd_classes"]):
        raise ValueError("已有职业记录，总等级须等于各职业等级之和；请用 .pc class 更新职业等级。")
    explicit_pb = any(name == "熟练" for name, _, _, _ in entries)
    total = sum(item["level"] for item in result["dnd_classes"]) if result.get("dnd_classes") else attrs.get("等级")
    expected_pb = (7 + total) // 4 if type(total) is int and 1 <= total <= 20 else None
    if expected_pb is not None and attrs.get("等级") != card.get("attributes", {}).get("等级") and not explicit_pb:
        old_pb = attrs.get("熟练", 0)
        attrs["熟练"] = expected_pb
        changes.append(f"熟练: {old_pb} -> {expected_pb}（随总等级更新）")
    # Display derived values only after all six scores and PB have been imported.
    for name, _, _, _ in entries:
        if name in SKILLS and SKILLS[name] in attrs:
            bonus, detail = check_bonus(result, name)
            changes.append(f"{name}检定 {bonus:+d}（{detail}）")
    if "hp" in attrs:
        changes.append(f"HP {attrs['hp']}/{attrs.get('hpmax', '?')}，临时 HP {attrs.get('thp', 0)}")
    detail = "\n".join(changes)
    if explicit_pb and expected_pb is not None and attrs["熟练"] != expected_pb:
        raise ProficiencyMismatch(result, detail, expected_pb)
    return result, detail


def format_card(card, query=""):
    attrs = _attributes(card)
    query = query.strip()
    threshold = int(query) if re.fullmatch(r"-?\d+", query) else None
    names = query.split() if query and threshold is None else list(attrs)
    lines = [get_output("dnd.sheet.header", name=card["name"])]
    if query.lower() in {"资源", "res", "resource"}:
        try:
            lines.append(format_resources(card))
        except ValueError as exc:
            lines.append(str(exc))
        return "\n".join(lines)
    if not query or query.lower() in {"职业", "class"}:
        occupation = format_classes(card)
        if occupation or query:
            lines.append("职业: " + (occupation or "未录入"))
        if any(item.get("subclass_status") == "needs_source" for item in card.get("dnd_classes", [])):
            lines.append("旧子职记录尚未确定来源；重新用 .pc class 录入默认最新版，或用 子职2014 / 子职塔莎 指定旧版。")
        if query:
            return "\n".join(lines)
    for requested in names:
        try:
            name = canonical(requested)
            if name in ABILITIES:
                value = attrs[name]
                save, _ = check_bonus(card, name + "豁免")
                line = f"{name}: {value}（调整值 {modifier(value):+d}，豁免 {save:+d}）"
            elif name in SKILLS or name.endswith("豁免"):
                value, detail = check_bonus(card, name)
                line = f"{name}: {value:+d}（{detail}）"
            else:
                value = attrs[name]
                line = f"{name}: {value}"
            if threshold is None or value > threshold:
                lines.append(line)
        except (KeyError, ValueError):
            if query and threshold is None:
                lines.append(get_output("dnd.sheet.attribute_missing", attribute=requested))
    return "\n".join(lines)


def export_card(card):
    attrs = _attributes(card)
    proficiency = card.get("dnd_proficiency", {})
    parts = []
    for name, value in attrs.items():
        factor = proficiency.get(name, 0)
        suffix = ("*" if factor == 1 else f"*{factor:g}") if factor else ""
        parts.append(f"{name}{suffix}:{value}")
    exported = ".st " + " ".join(parts)
    occupation = format_classes(card)
    if occupation:
        exported += "\n.pc class " + occupation
    return exported


def delete_attributes(card, names, clear=False):
    attrs = _attributes(card)
    result = deepcopy(card)
    targets = list(attrs) if clear else [canonical(name) for name in names.split()]
    lines = []
    for name in targets:
        if name in PROTECTED:
            if not clear:
                lines.append(get_output("dnd.sheet.attribute_protected", attribute=name))
        elif name in result["attributes"]:
            del result["attributes"][name]
            result.get("dnd_proficiency", {}).pop(name, None)
            lines.append(get_output("dnd.sheet.attribute_deleted", attribute=name))
        elif not clear:
            lines.append(get_output("dnd.sheet.attribute_missing", attribute=name))
    return result, "\n".join(lines) or get_output("dnd.sheet.nothing_to_clear")


def roll_check(card, expression):
    expression = expression.strip()
    minimum = None
    if ">=" in expression:
        expression, bound = expression.rsplit(">=", 1)
        if not re.fullmatch(r"\s*[+-]?\d+\s*", bound) or ">=" in expression:
            raise ValueError("检定下限请写在末尾，例如 .rc 察觉>=15，且下限须为整数。")
        minimum = int(bound)
        expression = expression.strip()
    saving_throw = expression.startswith("*")
    if saving_throw:
        expression = expression[1:].strip()
    times = 1
    repeat = re.match(r"^(\d+)#\s*(.*)$", expression)
    if repeat:
        times, expression = int(repeat.group(1)), repeat.group(2)
    if not 1 <= times <= 20:
        raise ValueError("重复检定次数必须在 1 到 20 之间。")
    mode = re.match(r"^(优势|劣势|adv|dis)\s*", expression, re.I)
    dice = "1d20"
    if mode:
        dice = "2d20k1" if mode.group(1).lower() in {"优势", "adv"} else "2d20k-1"
        expression = expression[mode.end():]
    match = re.fullmatch(r"([^+\-]+?)\s*([+\-]\s*\d+)?", expression)
    if not match:
        raise ValueError("请使用 .rc 察觉 / .rc 智力豁免 / .rc 优势 隐匿+2。")
    name = canonical(match.group(1))
    if saving_throw:
        ability = name[:-2] if name.endswith("豁免") else name
        if ability not in ABILITIES:
            raise ValueError("豁免请使用 .rc*力量 / .rc*敏 / .rc*智力。")
        name = ability + "豁免"
    bonus, detail = check_bonus(card, name)
    extra = int(match.group(2).replace(" ", "")) if match.group(2) else 0
    lines = [get_output("dnd.check.head", name=card["name"], skill_name=name, detail=detail, extra=extra)]
    for _ in range(times):
        total, rolled = parse_dice_expression(f"{dice}{bonus + extra:+d}")
        natural = total - (bonus + extra)
        if minimum is not None:
            clamped = max(total, minimum)
            rolled += f"；取最大值 max({total}, {minimum}) = {clamped}"
        lines.append(get_output("dnd.check.roll", dice=dice, bonus=bonus + extra, result=rolled))
        if natural != 1:
            aside = get_output("dnd.check.aside", name=card["name"], skill_name=name)
            if aside:
                lines.append(aside)
        if natural in (1, 20):
            key = "natural_20" if natural == 20 else "natural_1"
            lines.append(get_output(f"dnd.check.{key}", name=card["name"], skill_name=name))
    return "\n".join(lines)


def template():
    attrs = {"等级": 1, **{name: 10 for name in ABILITIES}}
    attrs.update({"hp": 10, "hpmax": 10, "thp": 0, "先攻": 0, "ac": 10, "dc": 10, "pp": 10, "熟练": 2})
    attrs.update({name: 0 for name in SKILLS})
    return export_card({"rule_system": "dnd", "attributes": attrs})
