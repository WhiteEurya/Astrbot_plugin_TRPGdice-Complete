"""Compile audited, finite resource counters into the runtime rule vocabulary."""

import ast
from copy import deepcopy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ATTRS = dict(zip(("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"),
                 ("力量", "敏捷", "体质", "智力", "感知", "魅力")))
KINDS = {"use_pool", "dice_pool", "die_pool", "rolled_value_list", "rolled_mode_pool",
         "free_spell_pool", "selected_free_spell", "selected_slot_recovery", "conditional_use_pool",
         "success_consumed_pool", "summon_pool", "per_selection_pool", "per_activation_pool",
         "conditional_life_pool", "conditional_pool", "rest_count_cooldown"}
INHERIT = {
    "scag:rogue:swashbuckler": "xgte:rogue:swashbuckler",
    "scag:sorcerer:storm-sorcery": "xgte:sorcerer:storm-sorcery",
    "phb2024:rogue:arcane-trickster": "phb2014:rogue:arcane-trickster",
    "phb2024:rogue:soulknife": "tcoe:rogue:soulknife",
    "phb2024:fighter:psi-warrior": "tcoe:fighter:psi-warrior",
    "phb2024:sorcerer:aberrant-sorcery": "tcoe:sorcerer:aberrant-mind",
    "phb2024:sorcerer:clockwork-sorcery": "tcoe:sorcerer:clockwork-soul",
    "phb2024:warlock:celestial-patron": "xgte:warlock:the-celestial",
    "phb2024:ranger:fey-wanderer": "tcoe:ranger:fey-wanderer",
    "phb2024:bard:college-of-glamour": "xgte:bard:college-of-glamour",
    "phb2024:monk:warrior-of-mercy": "tcoe:monk:way-of-mercy",
    "phb2024:paladin:oath-of-glory": "tcoe:paladin:oath-of-glory",
    "phb2024:paladin:oath-of-the-ancients": "phb2014:paladin:oath-of-the-ancients",
    "phb2024:wizard:diviner": "phb2014:wizard:school-of-divination",
}
# Only these counters retain identical capacity/recovery across publications.
SHARED_KEYS = {"spell_thief", "free_powers", "implosion", "trance", "cavalcade",
               "healing_light", "searing_vengeance", "fey", "misty", "unbreakable_majesty",
               "ultimate_mercy", "glorious_defense", "sentinel", "portent", "third_eye",
               "master_duelist", "wind_soul"}
POWER_NAMES = {"psychic_whispers": "心灵低语", "psychic_veil": "灵能面纱", "rend_mind": "撕裂心智",
               "telekinetic_movement": "念力控物", "psi_powered_leap": "灵力跃动",
               "bulwark_force": "力场壁垒", "telekinetic_master": "念力大师"}


def formula(value):
    if type(value) is int:
        return value
    def convert(node):
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return node.value
        if isinstance(node, ast.Name):
            name = node.id
            if name in {"proficiency_bonus", "total_character_level"}:
                return {"var": {"proficiency_bonus": "pb", "total_character_level": "total_level"}[name]}
            if name.endswith("_level"):
                return {"var": "level"}
            if name.endswith("_modifier") and name[:-9] in ATTRS:
                return {"mod": ATTRS[name[:-9]]}
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult)):
            left, right = convert(node.left), convert(node.right)
            if isinstance(node.op, ast.Sub):
                right = {"op": "mul", "args": [-1, right]}
            return {"op": "mul" if isinstance(node.op, ast.Mult) else "add", "args": [left, right]}
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            if node.func.id in {"min", "max"}:
                return {"op": node.func.id, "args": [convert(n) for n in node.args]}
            if node.func.id in {"floor", "ceil"} and len(node.args) == 1:
                arg = node.args[0]
                if isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Div):
                    return {"op": node.func.id + "_div", "args": [convert(arg.left), convert(arg.right)]}
        raise ValueError(f"Unsupported numeric formula: {value}")
    return convert(ast.parse(value, mode="eval").body)


def compile_entry(entry, owner):
    kind = entry["kind"]
    if kind not in KINDS and not kind.startswith("use_pool_with_"):
        return []
    cap = entry["capacity"]
    cap = cap if isinstance(cap, dict) else {"uses": cap}
    if kind == "per_selection_pool":
        selections = cap.get("powers")
        if "known_runes" in cap:
            result = []
            for minimum, count in cap["known_runes"]:
                previous = max((n for level, n in cap["known_runes"] if level < minimum), default=0)
                for i in range(previous, count):
                    child = {**entry, "id": entry["id"] + f":{i + 1}", "name": f"符文{i + 1}",
                             "kind": "use_pool", "minimum_level": minimum,
                             "capacity": {"steps": cap["uses_per_rune"]}}
                    result.extend(compile_entry(child, owner))
            return result
        if not selections:
            names = cap.get("spells", [f"已选法术{i + 1}" for i in range(cap.get("selected_spells", 0))])
            selections = {name: {"uses": cap["free_uses_per_spell"]} for name in names}
        result = []
        for key, config in selections.items():
            child = {**entry, "id": entry["id"] + ":" + key,
                     "name": POWER_NAMES.get(key, key), "kind": "use_pool", "capacity": config,
                     "minimum_level": max(entry["minimum_level"], config.get("minimum_level", 1))}
            if "rest" in config:
                child["recovery"] = {"long_rest": "补满", **({"short_rest": "补满"} if config["rest"] == "short_or_long" else {})}
            result.extend(compile_entry(child, owner))
        return result
    value = next((cap[k] for k in ("uses", "free_uses", "successes", "dice", "steps", "count_by_rogue_level", "uses_per_rage", "hit_points") if k in cap), None)
    if value is None:
        return []
    recovery = entry["recovery"]
    # Special recovery text is not interpreted as a blanket refill.
    short = recovery.get("short_rest", "")
    rest = "short" if short.startswith("补满") else "long" if "long_rest" in recovery else "manual"
    if kind in {"per_activation_pool", "conditional_life_pool", "conditional_pool", "rest_count_cooldown"}:
        rest = "manual"
    rule = {"owner": owner, "edition": "both", "key": "research:" + entry["id"].split(":", 3)[-1],
            "name": entry["name"], "minimum": entry["minimum_level"], "rest": rest,
            "source": "audited_resources", "aliases": [entry["name"].split("：")[0]]}
    if isinstance(value, dict):
        value = sorted((int(k), v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        rule["steps"] = value
    else:
        rule["formula"] = formula(value)
    die = cap.get("die_faces", cap.get("die_steps", cap.get("faces_by_rogue_level")))
    if isinstance(die, dict):
        die = sorted((int(k), v) for k, v in die.items())
    if die is not None:
        rule["die_steps"] = die if isinstance(die, (list, tuple)) else [[entry["minimum_level"], die]]
    if owner in {"phb2024:fighter:psi-warrior", "phb2024:rogue:soulknife"} and kind == "dice_pool":
        rule["short_restore"] = 1
    if entry["id"] == "phb2024:cleric:light-domain:flare":
        rule["short_rest_from"] = 6
    if kind == "conditional_life_pool":
        rule["initial_used"] = "all"
        rule["rest_set"] = {"long": 0}
    if kind == "conditional_pool":
        rule["rest_set"] = {"long": 1}
        rule["short_if_empty"] = 1
        rule["initial_remaining"] = 1
    return [rule]


def build():
    entries = [e for path in sorted((ROOT / "data/dnd").glob("resource-research-*.json"))
               for e in json.loads(path.read_text())["entries"]]
    pools = []
    for entry in entries:
        for owner in entry["owners"]:
            if ":" in owner or entry["id"] in {"wizard:arcane_recovery:2014", "wizard:arcane_recovery:2024", "wizard:signature_spells"}:
                compiled = compile_entry(entry, owner)
                if entry["id"].startswith("wizard:arcane_recovery:"):
                    for pool in compiled:
                        pool["edition"] = entry["id"].rsplit(":", 1)[1]
                        pool["key"] = "arcane_recovery"
                pools.extend(compiled)
    original = deepcopy(pools)
    for target, source in INHERIT.items():
        for pool in original:
            if pool["owner"] == source and pool["key"].split(":")[1] in SHARED_KEYS:
                pools.append({**pool, "owner": target, "minimum": max(pool["minimum"], 3)})
    return {"schema_version": 1, "pools": pools}


if __name__ == "__main__":
    result = build()
    (ROOT / "data/dnd/resource-pools.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"Compiled {len(result['pools'])} resource counters")
