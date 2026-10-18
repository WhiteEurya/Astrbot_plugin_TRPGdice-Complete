"""DnD class records, independent of spell-slot and hit-point calculations."""

from copy import deepcopy
import re
from .catalog import (format_catalog, resolve_subclass, source_id, split_source_suffix,
                      latest_class_edition, load_catalog, find_subclasses, SOURCE_ORDER, SOURCE_SUFFIX)


CLASS_NAMES = {
    "barbarian": "野蛮人", "bard": "吟游诗人", "cleric": "牧师", "druid": "德鲁伊",
    "fighter": "战士", "monk": "武僧", "paladin": "圣武士", "ranger": "游侠",
    "rogue": "游荡者", "sorcerer": "术士", "warlock": "邪术师", "wizard": "法师",
    "artificer": "奇械师",
}
CLASS_ALIASES = {**CLASS_NAMES, **{name: name for name in CLASS_NAMES.values()},
                 "盗贼": "游荡者", "魔契师": "邪术师", "野蛮": "野蛮人", "工匠": "奇械师"}
SPECIAL_SUBCLASSES = {
    "奥法骑士": ("战士", "奥法骑士"), "eldritch knight": ("战士", "奥法骑士"),
    "诡术师": ("游荡者", "诡术师"), "arcane trickster": ("游荡者", "诡术师"),
}
CLASS_HELP = (
    "用法：.pc class 战士:3/法师:2；第一项为起始职业，总等级自动求和。\n"
    "子职：.pc class 战士(奥法骑士):3/法师:2，也可直接写 奥法骑士:3/法师:2。\n"
    "自定义子职：.pc class 战士(自定义):5；只计算主职业公共资源，额外资源用 .res add 资源名 上限 登记。\n"
    "无参数查看；list [职业] [来源] 查看子职目录；clear 清除职业记录并保留总等级。\n"
    "默认使用本地目录最新规则；旧版：战士2014(战斗大师2014):5 / 法师(剑咏剑湾):5。\n"
    "主职业：" + "、".join(CLASS_NAMES.values()) + "。\n"
    "普通施法职业：吟游诗人、牧师、德鲁伊、术士、法师；半施法职业：圣武士、游侠、奇械师。\n"
    "特殊法术位子职：战士(奥法骑士)、游荡者(诡术师)；邪术师使用契约魔法。\n"
    "有限施法示例：战士(奥术射手)、武僧(暗影宗)、武僧(四象宗)、野蛮人(图腾武者)。\n"
    "这些子职不提供普通法术位；括号内一次只能填一个子职，不用 / 分隔子职。\n"
    "主职业版本直接写在名称后：术士2014:5；子职也可写 魂刃2014、剑咏塔莎。旧@写法兼容。\n"
    "资源按职业和属性自动计算，用 .res 查看；无差异的资源不要求标来源。\n"
    "职业命令不修改 HP、熟练，也不校验兼职前提。"
)


def parse_classes(expression):
    expression = expression.strip().replace("：", ":").replace("／", "/")
    expression = expression.replace("（", "(").replace("）", ")")
    if not expression or len(expression) > 1000:
        raise ValueError("请使用 主职:等级/兼职:等级，例如 战士:3/法师:2。")
    records = []
    seen = set()
    for part in expression.split("/"):
        match = re.fullmatch(r"\s*([^:()]+?)(?:\(([^:()]+)\))?\s*:\s*([0-9]{1,2})\s*", part)
        if not match:
            raise ValueError("职业格式错误，请使用 战士:3/法师:2 或 战士(奥法骑士):3/法师:2。")
        name, subclass, level = match.groups()
        name = name.strip().lower()
        edition = None
        if "@" in name:
            name, source = name.rsplit("@", 1)
            name = name.strip()
            source = source_id(source)
            if source not in {"phb2014", "phb2024"}:
                raise ValueError("主职业来源请写 @2014 或 @2024；扩展书来源写在子职后。")
            edition = "2024" if source == "phb2024" else "2014"
        else:
            name, source, _ = split_source_suffix(name)
            if source:
                if source not in {"phb2014", "phb2024"}:
                    raise ValueError("主职业版本请写2014或2024；书名来源写在子职后。")
                edition = "2024" if source == "phb2024" else "2014"
        requested_edition = edition
        special = SPECIAL_SUBCLASSES.get(name)
        if special:
            if subclass:
                raise ValueError("直接填写特殊子职时不能再附加其他子职。")
            name, subclass = special
        name = CLASS_ALIASES.get(name, name)
        if name not in CLASS_NAMES.values():
            raise ValueError(f"不支持的职业：{name}。用 .pc class list 查看支持列表。")
        if name in seen:
            raise ValueError(f"职业重复：{name}，同一职业请合并等级，不能选择两个子职。")
        level = int(level)
        if not 1 <= level <= 20:
            raise ValueError("每个职业的等级必须在 1 到 20 之间。")
        class_id = next(key for key, value in CLASS_NAMES.items() if value == name)
        record = {"class": name, "level": level, "edition": edition or latest_class_edition(class_id)}
        if subclass:
            subclass = subclass.strip()
            if not subclass or len(subclass) > 60 or any(c in subclass for c in "\n\r"):
                raise ValueError("子职名称无效。")
            special = SPECIAL_SUBCLASSES.get(subclass.lower())
            if special:
                if special[0] != name:
                    raise ValueError(f"{special[1]}属于{special[0]}，不能挂在{name}下面。")
                subclass = special[1]
            subclass, catalog_id, status = resolve_subclass(subclass, class_id, requested_edition)
            record["subclass"] = subclass
            record["subclass_status"] = status
            if catalog_id:
                record["subclass_id"] = catalog_id
        records.append(record)
        seen.add(name)
    if sum(record["level"] for record in records) > 20:
        raise ValueError("职业等级之和不能超过 20。")
    return records


def format_subclass_catalog(query=""):
    class_id = None
    source = None
    for word in query.split():
        name = CLASS_ALIASES.get(word.lower())
        if name:
            if class_id is not None:
                raise ValueError("一次只查询一个主职业。")
            class_id = next(key for key, value in CLASS_NAMES.items() if value == name)
        else:
            if source is not None:
                raise ValueError("一次只查询一个来源。")
            source = source_id(word)
    return format_catalog(CLASS_NAMES, class_id, source)


def format_classes(card):
    parts = []
    entries = {entry.id: entry for entry in load_catalog()[1]}
    for record in card.get("dnd_classes", []):
        name = record["class"]
        class_id = next(key for key, value in CLASS_NAMES.items() if value == name)
        edition = record.get("edition", card.get("dnd_edition", card.get("dnd_resources", {}).get("edition")))
        if edition in {"2014", "2024"} and edition != latest_class_edition(class_id):
            name += edition
        if record.get("subclass"):
            entry = entries.get(record.get("subclass_id"))
            label = record["subclass"]
            if entry:
                candidates = find_subclasses(entry.name, class_id)
                latest = max(candidates, key=lambda item: SOURCE_ORDER[item.source])
                label = entry.name
                if entry.id != latest.id or (edition and edition != entry.edition):
                    label += SOURCE_SUFFIX[entry.source]
            name += f"({label})"
        parts.append(f"{name}:{record['level']}")
    return "/".join(parts)


def update_classes(card, expression):
    if card.get("rule_system") != "dnd":
        raise ValueError("职业设置只适用于 DnD 人物卡。")
    records = parse_classes(expression)
    notified = {
        (record["class"], record.get("subclass"))
        for record in card.get("dnd_classes", [])
        if record.get("subclass_status") == "custom" and record.get("resource_notice_sent")
    }
    for record in records:
        if (record.get("subclass_status") == "custom"
                and (record["class"], record.get("subclass")) in notified):
            record["resource_notice_sent"] = True
    updated = deepcopy(card)
    updated["dnd_classes"] = records
    attrs = updated.setdefault("attributes", {})
    total = sum(record["level"] for record in records)
    if attrs.get("等级") != total:
        attrs["熟练"] = (7 + total) // 4
    attrs["等级"] = total
    return updated
