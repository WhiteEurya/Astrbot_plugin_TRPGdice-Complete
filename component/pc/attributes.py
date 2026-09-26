"""Shared attribute names and strict .st expression parsing."""
import re
import unicodedata

class SYNONYMS:
    SYNONYM = [
        ["力量", "str"],
        ["敏捷", "dex"],
        ["意志", "pow"],
        ["体质", "con"],
        ["外貌", "app"],
        ["教育", "知识", "edu"],
        ["体型", "siz"],
        ["智力", "灵感", "int"],
        ["san", "san值", "理智", "理智值"],
        ["幸运", "运气"],
        ["mp", "魔法"],
        ["hp", "体力"],
        ["max_hp"],
        ["max_san"],

        # 技能/替代名（根据你给出的列表合并）
        ["计算机", "计算机使用", "电脑"],
        ["会计"],
        ["人类学"],
        ["估价"],
        ["考古学"],
        ["取悦"],
        ["攀爬"],
        ["电脑", "计算机"],  # 重复安全
        ["信用", "信誉", "信用评级"],
        ["克苏鲁", "克苏鲁神话", "cm"],
        ["乔装"],
        ["闪避"],
        ["汽车", "驾驶", "汽车驾驶"],
        ["电气维修"],
        ["电子学"],
        ["话术"],
        ["斗殴"],
        ["手枪"],
        ["急救"],
        ["历史"],
        ["恐吓"],
        ["跳跃"],
        ["拉丁语"],
        ["母语"],
        ["法律"],
        ["图书馆", "图书馆使用"],
        ["聆听"],
        ["开锁", "撬锁", "锁匠"],
        ["机械维修"],
        ["医学"],
        ["博物学", "自然学"],
        ["领航", "导航"],
        ["神秘学"],
        ["重型操作", "重型机械", "操作重型机械", "重型"],
        ["说服"],
        ["精神分析"],
        ["心理学"],
        ["骑术"],
        ["妙手"],
        ["侦查", "侦察"],
        ["潜行"],
        ["生存"],
        ["游泳"],
        ["投掷"],
        ["追踪"],
        ["驯兽"],
        ["潜水"],
        ["爆破"],
        ["读唇"],
        ["催眠"],
        ["炮术"],
    ]

    SYNONYM_MAP = {}
    for group in SYNONYM:
        primary_name = group[0]
        for synonym in group:
            if synonym not in SYNONYM_MAP:
                SYNONYM_MAP[synonym] = primary_name

    PROTECTED_SYNONYM_GROUPS = [
        ["力量", "str"],
        ["敏捷", "dex"],
        ["意志", "pow"],
        ["体质", "con"],
        ["外貌", "app"],
        ["教育", "知识", "edu"],
        ["体型", "siz"],
        ["智力", "灵感", "int"],
        ["san", "san值", "理智", "理智值"],
        ["幸运", "运气"],
        ["mp", "魔法"],
        ["hp", "体力"],
        ["max_hp"],
        ["max_san"],
    ]

    PRIMARY_TO_ALL_MAP = {group[0]: set(group) for group in SYNONYM}

    PROTECTED_ATTRIBUTES = set()
    for group in PROTECTED_SYNONYM_GROUPS:
        PROTECTED_ATTRIBUTES.update(group)

BRACKETS = {"(": ")", "[": "]", "{": "}", "【": "】", "〔": "〕", "〈": "〉", "《": "》", "「": "」", "『": "』", "〖": "〗", "〘": "〙", "〚": "〛"}
WORD = r"[a-zA-Z\u3400-\u9fff/_]+"
def bracket_pattern(content):
    return "(?:" + "|".join(
        re.escape(a) + content + re.escape(b) for a, b in BRACKETS.items()
    ) + ")"


# A colon can introduce a specialization or separate the name from its value.
SPECIALIZATION = bracket_pattern(rf"(?:{WORD})?")
BASE_NAME = rf"{WORD}(?::{WORD}|:?{SPECIALIZATION})?"
NAME = rf"(?:{BASE_NAME}|{bracket_pattern(BASE_NAME + ':?')})"
ENTRY = re.compile(rf"(?P<name>{NAME}):?(?P<op>[+*-]?)(?P<value>\d+[dD]\d+|\d+)")


def clean_text(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def normalize_attribute_name(name):
    name = clean_text(name)
    while name:
        previous = name
        name = name.rstrip(":")
        for opening, closing in BRACKETS.items():
            if opening in name and name.endswith(closing):
                prefix, content = name.split(opening, 1)
                content = content[:-len(closing)]
                # Empty specialization retains the parent skill.
                name = content or prefix
                break
        else:
            if ":" in name:
                name = name.rsplit(":", 1)[1]
        if name == previous:
            break
    return SYNONYMS.SYNONYM_MAP.get(name.lower(), name)


def find_attribute_key(attributes, name):
    canonical = normalize_attribute_name(name)
    if canonical in attributes:
        return canonical
    return next((key for key in attributes if normalize_attribute_name(key) == canonical), None)


def set_attribute_value(attributes, name, value):
    canonical = normalize_attribute_name(name)
    # Update existing aliases before save_character synchronizes them.
    for key in list(attributes):
        if normalize_attribute_name(key) == canonical:
            attributes[key] = value
    attributes[canonical] = value


def parse_st_expression(text):
    text = clean_text(text)
    entries = []
    position = 0
    while position < len(text):
        match = ENTRY.match(text, position)
        if not match:
            raise ValueError("Invalid .st expression")
        entries.append((normalize_attribute_name(match['name']), match['op'], match['value']))
        position = match.end()
        separator = re.match(r"[,;、]+", text[position:])
        if separator:
            position += separator.end()
    if not entries or (len(entries) > 1 and any(op or not value.isdecimal() for _, op, value in entries)):
        raise ValueError("Expected assignments or a single operation")
    return entries
