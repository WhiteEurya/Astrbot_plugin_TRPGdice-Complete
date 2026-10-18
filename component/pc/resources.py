"""Versioned DnD resource balances, without resolving feature effects."""

from copy import deepcopy
from functools import lru_cache
from itertools import product
import json
from pathlib import Path
import re

from .catalog import load_catalog, find_subclasses
from .classes import CLASS_NAMES
from ..common.output import get_output


RULES_PATH = Path(__file__).resolve().parents[2] / "data" / "dnd" / "resources.json"
RESOURCE_HELP = (
    "资源上限自动读取职业、子职、等级与属性，不需要整张卡选择版本。\n"
    ".res 查看；.res 一环 扣一个普通法术位；.res 契约 扣一个契约法术位。\n"
    ".res 术法点-2 扣两点；.res 术法点+2 补回两点（兼容原空格写法）。\n"
    ".res add 灵能点 5 [短休|长休|皆有|手动] 添加自定义资源，默认手动；重复登记修改设置，保留已消耗数量。\n"
    "上限可填整数、=总等级 或 =totallvl、=<职业>等级 或 =<class>lvl（如 =牧师等级 或 =clericlvl）、=<属性>、=熟练加值、=熟练 或 =pb。\n"
    "属性支持：力量/str、敏捷/dex、体质/con、智力/int、感知/wis、魅力/cha；属性调整值至少为 1。\n"
    "动态上限跟随人物卡变化；总等级取职业等级之和（无职业时取卡上等级），职业等级取对应职业记录，未拥有该职业时为 0，熟练加值取卡上的熟练值。\n"
    "动态上限支持正整数倍，如 =5*totallvl、=2*clericlvl、=2*int、=2*pb；属性先取至少为 1 的调整值，再乘倍数。\n"
    "皆有（both）：长休回满，短休回 1。\n"
    ".res del 灵能点 删除自定义资源；短休资源也会在长休时恢复。\n"
    ".res 短休 / 长休：仅恢复资源，不改 HP。\n"
    "默认本地最新规则；旧版直接加后缀，例如 .pc class 战士2014:5/法师(剑咏塔莎):3。\n"
    "职业资源的短休和长休恢复方式按规则库自动确定。\n"
    "只记录资源余额；触发恢复、资源转换及特性效果由玩家自行处理。"
)
RINGS = "一二三四五六七八九"
REST_NAMES = {"short": "短休/长休", "long": "长休", "manual": "手动", "both": "皆有"}

CAPACITY_ALIASES = {
    "总等级": "总等级", "totallvl": "总等级",
    **{key: name + "等级" for class_id, name in CLASS_NAMES.items()
       for key in (name + "等级", class_id + "lvl")},
    "魔契师等级": "邪术师等级", "熟练加值": "熟练加值", "熟练": "熟练加值", "pb": "熟练加值",
    **{key: name for name, alias in (("力量", "str"), ("敏捷", "dex"), ("体质", "con"),
                                     ("智力", "int"), ("感知", "wis"), ("魅力", "cha"))
       for key in (name, alias)},
}
CAPACITY_HELP = "上限为 1 到 10000 的整数、=总等级 或 =totallvl、=<职业>等级 或 =<class>lvl（如 =牧师等级 或 =clericlvl）、=<属性>（力量/str、敏捷/dex、体质/con、智力/int、感知/wis、魅力/cha）、=熟练加值、=熟练 或 =pb；支持正整数倍，如 =5*totallvl 或 =2*int。"


def _parse_capacity(text):
    if text.startswith("="):
        match = re.fullmatch(r"(?:([0-9]+)\*)?([^*]+)", text[1:].lower())
        if match:
            multiplier, target = match.groups()
            name = CAPACITY_ALIASES.get(target)
            if name and (multiplier is None or any(char != "0" for char in multiplier)):
                prefix = multiplier.lstrip("0") + "*" if multiplier is not None else ""
                return "=" + prefix + name
        raise ValueError(CAPACITY_HELP)
    try:
        return _amount(text)
    except ValueError:
        raise ValueError(CAPACITY_HELP) from None


def _custom_capacity(card, capacity):
    if type(capacity) is int:
        return capacity
    # Keep previously saved total-level bindings readable.
    capacity = "=总等级" if capacity in {"=等级", "=lvl"} else capacity
    name = _parse_capacity(capacity)[1:]
    if "*" in name:
        multiplier, target = name.split("*", 1)
        try:
            factor = int(multiplier)
        except ValueError:
            raise ValueError(CAPACITY_HELP) from None
        return factor * _custom_capacity(card, "=" + target)
    attrs = card.get("attributes", {})
    if name == "总等级":
        classes = _classes(card)
        value = sum(level for _, level, _ in classes) if classes else attrs.get("等级")
        if type(value) is not int or not 1 <= value <= 20:
            raise MissingAttribute("请先用 .pc class 录入职业等级，或用 .st 等级:数值 录入 1 到 20 的等级。")
        return value
    if name.endswith("等级") and name[:-2] in CLASS_NAMES.values():
        return next((level for class_id, level, _ in _classes(card)
                     if CLASS_NAMES[class_id] == name[:-2]), 0)
    if name == "熟练加值":
        value = attrs.get("熟练")
        if type(value) is not int or not 1 <= value <= 10000:
            raise MissingAttribute("请先用 .st 熟练:数值 录入 1 到 10000 的熟练加值。")
        return value
    return max(1, _evaluate({"mod": name}, 0, 0, attrs))


@lru_cache(maxsize=1)
def load_rules():
    with RULES_PATH.open(encoding="utf-8") as stream:
        rules = json.load(stream)
    if rules["schema_version"] != 1:
        raise ValueError("不支持的资源规则版本。")
    with RULES_PATH.with_name("resource-pools.json").open(encoding="utf-8") as stream:
        counters = json.load(stream)
    existing = {(r["owner"], r["name"]) for r in rules["pools"]}
    rules["pools"].extend(r for r in counters["pools"] if (r["owner"], r["name"]) not in existing)
    rules["sources"]["audited_resources"] = {"description": "resource-research-*.json 已核对资源，resource-pools.json 为可执行计数规则"}
    return rules


def _resource_state(card):
    state = deepcopy(card.get("dnd_resources", {}))
    used = state.setdefault("used", {})
    for rule in load_rules()["pools"]:
        old_key = f"{rule['owner']}:{rule['key']}"
        key = rule.get("pool_id", old_key)
        if rule.get("equivalent_key") and key != old_key and old_key in used:
            used.setdefault(key, used.pop(old_key))
    return state


def _step(steps, level):
    return next(value for minimum, value in reversed(steps) if level >= minimum)


class MissingAttribute(ValueError):
    pass


def _evaluate(expression, level, total, attrs, depth=0):
    """Evaluate the small numeric rule vocabulary; never execute rule text."""
    if depth > 12:
        raise ValueError("资源公式嵌套过深。")
    if type(expression) is int:
        return expression
    if not isinstance(expression, dict):
        raise ValueError("资源公式格式无效。")
    if set(expression) == {"var"}:
        variables = {"level": level, "total_level": total, "pb": 2 + (max(1, total) - 1) // 4}
        if expression["var"] not in variables:
            raise ValueError("资源公式使用了未知变量。")
        return variables[expression["var"]]
    if set(expression) == {"mod"}:
        name = expression["mod"]
        value = attrs.get(name)
        if type(value) is not int or not 1 <= value <= 30:
            raise MissingAttribute(f"请先用 .st {name}:数值 录入{name}，资源上限会自动计算。")
        return (value - 10) // 2
    if set(expression) != {"op", "args"} or not isinstance(expression["args"], list):
        raise ValueError("资源公式格式无效。")
    values = [_evaluate(arg, level, total, attrs, depth + 1) for arg in expression["args"]]
    op = expression["op"]
    if len(values) == 2:
        left, right = values
        if op == "add":
            return left + right
        if op == "mul":
            return left * right
        if op == "floor_div" and right > 0:
            return left // right
        if op == "ceil_div" and right > 0:
            return -(-left // right)
    if values and op == "max":
        return max(values)
    if values and op == "min":
        return min(values)
    raise ValueError("资源公式运算无效。")


def card_edition(card):
    edition = card.get("dnd_edition", card.get("dnd_resources", {}).get("edition"))
    if edition not in {"2014", "2024"}:
        raise ValueError("请先用 .pc version 2014 或 .pc version 2024 选择这张卡的规则版本（兼容 .pc res init）。")
    return edition


def set_version(card, edition):
    if card.get("rule_system") != "dnd":
        raise ValueError("版本设置只适用于 DnD 人物卡。")
    if edition not in {"2014", "2024"}:
        raise ValueError("用法：.pc version 2014 或 .pc version 2024。")
    updated = deepcopy(card)
    updated["dnd_edition"] = edition
    state = updated.setdefault("dnd_resources", {"used": {}, "custom": {}})
    state["edition"] = edition
    definitions(updated)
    return updated


def _classes(card):
    result = []
    names = {name: key for key, name in CLASS_NAMES.items()}
    for record in card.get("dnd_classes", []):
        name, level = record.get("class"), record.get("level")
        if name not in names or type(level) is not int or not 1 <= level <= 20:
            raise ValueError("职业记录无效，请用 .pc class 重新设置。")
        result.append((names[name], level, record))
    if sum(level for _, level, _ in result) > 20 or len({name for name, _, _ in result}) != len(result):
        raise ValueError("职业记录重复或总等级超过 20。")
    return result


def _slots(classes, entries):
    casters = []
    for name, level, record in classes:
        edition = record.get("edition")
        subclass = entries.get(record.get("subclass_id"))
        candidates = find_subclasses(record.get("subclass", ""), name) if not subclass else (subclass,)
        if name in {"bard", "cleric", "druid", "sorcerer", "wizard"}:
            casters.append(("full", level, edition))
        elif name in {"paladin", "ranger"} and (level >= 2 or edition == "2024"):
            casters.append(("half", level, edition))
        elif name == "artificer":
            if edition == "2024":
                raise ValueError("尚未核实新版奇械师法术位；不能按旧版职业表计算 2024 奇械师。")
            casters.append(("artificer", level, edition))
        elif (candidates and all(item.english in {"Eldritch Knight", "Arcane Trickster"} for item in candidates)
              and level >= 3):
            casters.append(("third", level, edition))
    if not casters:
        return []
    rules = load_rules()
    if len(casters) == 1:
        kind, level, _ = casters[0]
        if kind == "full":
            return rules["full_slots"][level]
        if kind == "third":
            return rules["third_slots"][level]
        return [2] if level == 1 else rules["half_slots"][level]
    caster_level = 0
    for kind, level, edition in casters:
        if kind == "full":
            caster_level += level
        elif kind == "third":
            caster_level += level // 3
        else:
            rounded_up = kind == "artificer" or edition == "2024"
            caster_level += (level + int(rounded_up)) // 2
    return rules["full_slots"][caster_level]


def _slot_definitions(classes, entries, warnings):
    uncertain = [name for name, _, record in classes
                 if name in {"paladin", "ranger", "artificer"} and not record.get("edition")]
    results = []
    for editions in product(("2014", "2024"), repeat=len(uncertain)):
        choices = dict(zip(uncertain, editions))
        selected = [(name, level, {**record, "edition": record.get("edition") or choices.get(name)})
                    for name, level, record in classes]
        try:
            result = _slots(selected, entries)
        except ValueError as exc:
            warnings.append(str(exc) if not uncertain else "法术位：奇械师来源未明确，请标 @2014；新版数据尚未核实。")
            return []
        results.append(result)
    if any(result != results[0] for result in results[1:]):
        names = "、".join(CLASS_NAMES[name] for name in uncertain)
        warnings.append(f"法术位：{names}的版本会影响计算，请在职业名后标 @2014 或 @2024；其他资源照常可用。")
        return []
    return results[0]


def _selected_rules(owners, editions, warnings):
    selected = []
    groups = {}
    for rule in load_rules()["pools"]:
        if owners.get(rule["owner"], 0) < rule["minimum"]:
            continue
        if rule["edition"] == "both" or ":" in rule["owner"]:
            selected.append(rule)
        elif editions.get(rule["owner"]):
            if rule["edition"] == editions[rule["owner"]]:
                selected.append(rule)
        else:
            groups.setdefault((rule["owner"], rule.get("equivalent_key", rule["key"])), []).append(rule)
    for (owner, _), rules in groups.items():
        # Compare only resource behavior; publication labels are not rules.
        normalized = []
        for rule in rules:
            value = {key: val for key, val in rule.items()
                     if key not in {"edition", "source", "name", "aliases", "key", "equivalent_key", "pool_id"}}
            if value.get("short_recovery", {}).get("minimum", 0) > owners[owner]:
                value.pop("short_recovery")
            normalized.append(value)
        if {rule["edition"] for rule in rules} == {"2014", "2024"} and all(value == normalized[0] for value in normalized):
            aliases = list(dict.fromkeys(alias for rule in rules for alias in [rule["name"], *rule.get("aliases", [])]))
            selected.append({**rules[0], "aliases": aliases})
        else:
            label = "／".join(dict.fromkeys(rule["name"] for rule in rules))
            warnings.append(f"{label}：存在版本差异，请用 .pc class 为{CLASS_NAMES[owner]}标 @2014 或 @2024；其他资源照常可用。")
    return selected


def definitions(card):
    """Derive capacities without touching expenditure, including dormant history."""
    state = card.get("dnd_resources", {})
    legacy_edition = card.get("dnd_edition", state.get("edition"))
    classes = _classes(card)
    classes = [(name, level, {**record, "edition": record.get("edition", legacy_edition)})
               for name, level, record in classes]
    entries = {entry.id: entry for entry in load_catalog()[1]}
    warnings = []
    owners = {}
    editions = {}
    for name, level, record in classes:
        owners[name] = level
        edition = record.get("edition")
        if edition is not None and edition not in {"2014", "2024"}:
            raise ValueError("职业来源记录无效，请用 .pc class 重新录入。")
        editions[name] = edition
        if record.get("subclass_status") == "needs_source":
            warnings.append(f"{record['subclass']}是未确定来源的旧记录，请重新用 .pc class 录入以选择最新版；其他资源照常可用。")
        subclass_id = record.get("subclass_id")
        subclass = entries.get(subclass_id)
        if record.get("subclass") and not subclass and record.get("subclass_status") not in {"custom", "needs_source"}:
            raise ValueError("子职来源记录无效或过旧，请用 .pc class 重新录入并指定 @来源。")
        if subclass:
            owners[subclass_id] = level
        if subclass_id == "scag:wizard:bladesinging":
            warnings.append("剑湾剑歌有原印本与勘误差异，暂不自动计算；勘误后的资源模型可选剑咏@塔莎。")
    pools = {}
    for ring, maximum in enumerate(_slot_definitions(classes, entries, warnings), 1):
        pools[f"slot:{ring}"] = {
            "name": f"{RINGS[ring - 1]}环", "max": maximum, "rest": load_rules()["spell_slots_rest"],
            "aliases": [str(ring), f"{ring}环", f"{ring}环法术位", f"{RINGS[ring - 1]}环法术位"],
        }
    total = sum(level for _, level, _ in classes)
    attrs = card.get("attributes", {})
    for rule in _selected_rules(owners, editions, warnings):
        level = owners.get(rule["owner"], 0)
        maximum = rule.get("max")
        if "steps" in rule:
            maximum = _step(rule["steps"], level)
        elif "formula" in rule:
            try:
                maximum = _evaluate(rule["formula"], level, total, attrs)
            except MissingAttribute as exc:
                warnings.append(f"{rule['name']}：{exc}")
                continue
        pool = {"name": rule["name"], "max": maximum, "rest": rule["rest"], "aliases": rule.get("aliases", []),
                "source": rule["source"], "short_restore": rule.get("short_restore", 0)}
        if level >= rule.get("short_rest_from", 21):
            pool["rest"] = "short"
        if "die_steps" in rule:
            pool["die"] = _step(rule["die_steps"], level)
        if "ring_steps" in rule:
            pool["ring"] = _step(rule["ring_steps"], level)
        recovery = rule.get("short_recovery")
        if recovery and level >= recovery.get("minimum", 1):
            pool["short_recovery"] = {**recovery, "amount": _evaluate(recovery["amount"], level, total, attrs)}
        for field in ("initial_used", "initial_remaining", "rest_set", "short_if_empty"):
            if field in rule:
                pool[field] = rule[field]
        key = rule.get("pool_id", f"{rule['owner']}:{rule['key']}")
        if key in pools:
            if rule.get("merge") != "max":
                raise ValueError("资源数据库包含重复资源池。")
            pool["max"] = max(pool["max"], pools[key]["max"])
        pools[key] = pool
    for name, pool in state.get("custom", {}).items():
        try:
            maximum = _custom_capacity(card, pool["max"])
        except MissingAttribute as exc:
            warnings.append(f"{name}：{exc}")
            continue
        custom_pool = {"max": maximum, "name": name, "aliases": [], "rest": pool.get("rest", "manual")}
        if custom_pool["rest"] == "both":
            custom_pool.update(rest="long", short_restore=1)
        if isinstance(pool["max"], str):
            custom_pool["capacity_binding"] = "=总等级" if pool["max"] in {"=等级", "=lvl"} else pool["max"]
        pools[f"custom:{name}"] = custom_pool
    warnings.append(get_output("dnd.resource.note"))
    return pools, warnings


def _remaining(pool, used):
    return None if pool["max"] is None else max(0, pool["max"] - used)


def _balance(key, pool, state):
    remaining = _remaining(pool, state.get("used", {}).get(key, _initial_spent(pool)))
    balance = "不限" if remaining is None else f"{remaining}/{pool['max']}"
    extra = f"，{pool['ring']}环" if "ring" in pool else ""
    extra += f"，d{pool['die']}" if "die" in pool else ""
    rest = REST_NAMES[pool["rest"]]
    if pool.get("short_restore"):
        rest += f"；短休回 {pool['short_restore']}"
    if pool.get("short_recovery"):
        rest += f"；短休可回 {pool['short_recovery']['amount']}，受恢复次数限制"
    binding = f" [上限{pool['capacity_binding']}]" if "capacity_binding" in pool else ""
    return f"{pool['name']}: {balance}（{rest}{extra}）{binding}"


def _initial_spent(pool):
    if pool.get("initial_used") == "all":
        return pool["max"]
    if "initial_remaining" in pool:
        return max(0, pool["max"] - pool["initial_remaining"])
    return 0


def format_resources(card):
    pools, warnings = definitions(card)
    state = _resource_state(card)
    lines = [get_output("dnd.resource.header")]
    lines.extend(_balance(key, pool, state) for key, pool in pools.items())
    if not pools:
        lines.append("当前职业暂无已支持资源。" if card.get("dnd_classes") else "请用 .pc class 录入职业，资源将自动计算。")
    lines.extend(warnings)
    return "\n".join(lines)


def custom_subclass_notices(card):
    """Return a card with pending notices marked, plus separate message texts."""
    updated = deepcopy(card)
    messages = []
    for record in updated.get("dnd_classes", []):
        if record.get("subclass_status") != "custom" or record.get("resource_notice_sent"):
            continue
        if record.get("subclass") == "自定义":
            messages.append(f"{record['class']}(自定义)：仅计算主职业公共资源；其他资源用 .res add 资源名 上限 手动登记。")
        else:
            messages.append(f"{record['subclass']}：自定义子职的自动资源暂未支持，主职业资源照常计算；可用 .res add 资源名 上限 手动登记。")
        record["resource_notice_sent"] = True
    return (updated if messages else None), messages


def _find(pools, name):
    matches = [(key, pool) for key, pool in pools.items()
               if name.casefold() in {key.casefold(), pool["name"].casefold(),
                                      *(alias.casefold() for alias in pool["aliases"])}]
    if not matches:
        raise ValueError("没有这个资源，请用 .res 查看；未定来源或数据库未收录的资源暂未支持。")
    if len(matches) != 1:
        raise ValueError("资源名称重复，请用完整资源 ID：" + "、".join(key for key, _ in matches))
    return matches[0]


def _amount(text):
    if not re.fullmatch(r"[0-9]{1,5}", text) or not 1 <= int(text) <= 10000:
        raise ValueError("数量必须是 1 到 10000 的整数。")
    return int(text)


def resource_command(card, args):
    """Return (new card or None for reads, response); failed edits are atomic."""
    if card.get("rule_system") != "dnd":
        raise ValueError("资源操作只适用于 DnD 人物卡。")
    words = args.strip().split()
    if len(words) == 1:
        change = re.fullmatch(r"(.+?)([+-])([0-9]+)", words[0])
        if change:
            name, sign, amount = change.groups()
            words = (["recover"] if sign == "+" else ["use"]) + [name, amount]
    if words and words[0].lower() in {"help", "帮助"}:
        return None, RESOURCE_HELP
    if words and words[0].lower() in {"init", "初始化"}:
        if len(words) != 2 or words[1] not in {"2014", "2024"}:
            raise ValueError("用法：.pc res init 2014 或 .pc res init 2024。")
        previous = card.get("dnd_edition", card.get("dnd_resources", {}).get("edition"))
        if previous and previous != words[1]:
            raise ValueError("资源账本已指定其他版本，不能通过重复初始化切换版本或重置消耗。")
        updated = set_version(card, words[1])
        return updated, format_resources(updated)
    if not words or words[0].lower() in {"show", "查看"}:
        if len(words) > 1:
            raise ValueError("用 .res 查看全部资源。")
        return None, format_resources(card)
    updated = deepcopy(card)
    pools, _ = definitions(updated)
    state = _resource_state(updated)
    updated["dnd_resources"] = state
    used = state.setdefault("used", {})
    for key, pool in pools.items():
        if key not in used and _initial_spent(pool):
            used[key] = _initial_spent(pool)
    custom = state.setdefault("custom", {})
    action = words[0].lower()
    if action in {"add", "登记"}:
        if len(words) not in {3, 4}:
            raise ValueError("用法：.res add 资源名 上限 [短休|长休|皆有|手动]，例如 .res add 灵能点 5 长休；默认手动恢复。" + CAPACITY_HELP)
        _, name, maximum = words[:3]
        if len(name) > 30 or not re.fullmatch(r"[\w\u4e00-\u9fff-]+", name):
            raise ValueError("资源名限 30 字内的文字、数字、下划线或连字符。")
        maximum = _parse_capacity(maximum)
        _custom_capacity(updated, maximum)
        rest = words[3].lower() if len(words) == 4 else "manual"
        rest = {"短休": "short", "长休": "long", "手动": "manual", "皆有": "both"}.get(rest, rest)
        if rest not in REST_NAMES:
            raise ValueError("恢复方式为短休、长休、皆有、手动（或 short、long、both、manual）。")
        if name.casefold() in {"help", "帮助", "init", "初始化", "show", "查看", "add", "登记",
                              "del", "删除", "rest", "休息", "短休", "长休", "recover", "恢复", "补回", "use", "消耗"}:
            raise ValueError("资源名不能与资源指令相同，请换一个名称。")
        if name not in custom and len(custom) >= 50:
            raise ValueError("自定义资源最多登记 50 项。")
        if any(key != f"custom:{name}" and name.casefold() in
               {key.casefold(), pool["name"].casefold(), *(alias.casefold() for alias in pool["aliases"])}
               for key, pool in pools.items()):
            raise ValueError("名称与现有资源重复，请换一个资源名。")
        custom[name] = {"max": maximum, "rest": rest}
        return updated, format_resources(updated)
    if action in {"del", "删除"}:
        if len(words) != 2 or words[1] not in custom:
            raise ValueError("只能删除已登记的自定义资源：.res del 资源名。")
        del custom[words[1]]
        return updated, "已移除自定义资源，历史消耗保留。"
    rest = None
    if action in {"短休", "长休"} and len(words) == 1:
        rest = "short" if action == "短休" else "long"
    elif action in {"rest", "休息"} and len(words) == 2:
        rest = {"短休": "short", "长休": "long"}.get(words[1], words[1].lower())
        if rest not in {"short", "long"}:
            raise ValueError("用法：.pc res rest short|long。")
    if rest:
        for key, pool in pools.items():
            if rest in pool.get("rest_set", {}):
                used[key] = max(0, pool["max"] - pool["rest_set"][rest])
            elif rest == "short" and pool.get("short_if_empty") and not _remaining(pool, used.get(key, 0)):
                used[key] = max(0, pool["max"] - pool["short_if_empty"])
            elif pool["rest"] == "short" or (rest == "long" and pool["rest"] == "long"):
                used[key] = 0
            elif rest == "short" and pool.get("short_restore"):
                spent = min(used.get(key, 0), pool["max"])
                used[key] = max(0, spent - pool["short_restore"])
        if rest == "short":
            for key, pool in pools.items():
                if key.startswith("custom:"):
                    continue
                recovery = pool.get("short_recovery")
                if not recovery or not used.get(key, 0):
                    continue
                limiter = recovery["limit_pool"]
                limit_pool = pools.get(limiter)
                if not limit_pool or not _remaining(limit_pool, used.get(limiter, 0)):
                    continue
                spent = min(used[key], pool["max"])
                used[key] = max(0, spent - recovery["amount"])
                used[limiter] = used.get(limiter, 0) + 1
        return updated, get_output("dnd.resource.restored", rest="短休" if rest == "short" else "长休", resources=format_resources(updated))
    if action in {"rest", "休息", "短休", "长休"}:
        raise ValueError("用法：.pc res 短休 / .pc res 长休。")
    recovering = action in {"recover", "恢复", "补回"}
    if action in {"use", "消耗"} or recovering:
        words = words[1:]
    if len(words) not in {1, 2}:
        raise ValueError(RESOURCE_HELP)
    key, pool = _find(pools, words[0])
    amount = _amount(words[1]) if len(words) == 2 else 1
    spent = used.get(key, 0)
    remaining = _remaining(pool, spent)
    if remaining is None:
        return None, _balance(key, pool, state) + "；无需扣除。"
    if recovering:
        used[key] = max(0, min(spent, pool["max"]) - amount)
    else:
        if amount > remaining:
            raise ValueError(f"{pool['name']}不足：剩余 {remaining}，需要 {amount}；未扣除。")
        used[key] = spent + amount
    return updated, get_output("dnd.resource.changed", balance=_balance(key, pool, state))
