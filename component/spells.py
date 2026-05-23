import json
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


DND5E_API_BASE = "https://www.dnd5eapi.co/api"
PLUGIN_DIR = Path(__file__).resolve().parents[1]
SEALDICE_HELPDOC_DIR = PLUGIN_DIR / "data" / "sealdice-builtins" / "data" / "helpdoc"
XLSX_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
XLSX_REL_NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
SEALDICE_DND_SOURCE = "资料源：SeaDice sealdice-builtins DND 查询资料；D&D 系列资料整理者主要为 DicePP 项目组成员。"
SEALDICE_COC_SOURCE = "资料源：SeaDice sealdice-builtins CoC 魔法大典；整理者：魔骨、NULL、Dr.Amber。"
_SEALDICE_DND_CACHE = None
_SEALDICE_COC_CACHE = None

DND_SPELL_ALIASES = {
    "acidarrow": "acid-arrow",
    "艾伽酸箭": "acid-arrow",
    "酸箭": "acid-arrow",
    "aid": "aid",
    "援助术": "aid",
    "alarm": "alarm",
    "警报术": "alarm",
    "animateobjects": "animate-objects",
    "活化物件": "animate-objects",
    "反魔法力场": "antimagic-field",
    "antimagicfield": "antimagic-field",
    "antipathysympathy": "antipathy-sympathy",
    "厌恶/共鸣": "antipathy-sympathy",
    "奥术眼": "arcane-eye",
    "arcaneeye": "arcane-eye",
    "魔法手": "mage-hand",
    "magehand": "mage-hand",
    "法师护甲": "mage-armor",
    "magearmor": "mage-armor",
    "魔法飞弹": "magic-missile",
    "magicmissile": "magic-missile",
    "火球术": "fireball",
    "fireball": "fireball",
    "护盾术": "shield",
    "shield": "shield",
    "法术反制": "counterspell",
    "反制法术": "counterspell",
    "counterspell": "counterspell",
    "闪电束": "lightning-bolt",
    "lightningbolt": "lightning-bolt",
    "疗伤术": "cure-wounds",
    "治愈伤口": "cure-wounds",
    "curewounds": "cure-wounds",
    "治疗真言": "healing-word",
    "healingword": "healing-word",
    "复活术": "raise-dead",
    "raisedead": "raise-dead",
    "死者复活": "raise-dead",
    "祝福术": "bless",
    "bless": "bless",
    "灾祸术": "bane",
    "bane": "bane",
    "黑暗术": "darkness",
    "darkness": "darkness",
    "隐形术": "invisibility",
    "invisibility": "invisibility",
    "高等隐形术": "greater-invisibility",
    "greaterinvisibility": "greater-invisibility",
    "飞行术": "fly",
    "fly": "fly",
    "加速术": "haste",
    "haste": "haste",
    "减速术": "slow",
    "slow": "slow",
    "睡眠术": "sleep",
    "sleep": "sleep",
    "魅惑人类": "charm-person",
    "charmperson": "charm-person",
    "侦测魔法": "detect-magic",
    "detectmagic": "detect-magic",
    "解除魔法": "dispel-magic",
    "dispelmagic": "dispel-magic",
    "羽落术": "feather-fall",
    "featherfall": "feather-fall",
    "识破隐形": "see-invisibility",
    "seeinvisibility": "see-invisibility",
    "传送术": "teleport",
    "teleport": "teleport",
    "许愿术": "wish",
    "wish": "wish",
}

DND_SPELL_CN_NAMES = {
    "acid-arrow": "艾伽酸箭",
    "aid": "援助术",
    "alarm": "警报术",
    "animate-objects": "活化物件",
    "antimagic-field": "反魔法力场",
    "arcane-eye": "奥术眼",
    "bane": "灾祸术",
    "bless": "祝福术",
    "charm-person": "魅惑人类",
    "counterspell": "法术反制",
    "cure-wounds": "疗伤术",
    "darkness": "黑暗术",
    "detect-magic": "侦测魔法",
    "dispel-magic": "解除魔法",
    "feather-fall": "羽落术",
    "fireball": "火球术",
    "fly": "飞行术",
    "greater-invisibility": "高等隐形术",
    "haste": "加速术",
    "healing-word": "治疗真言",
    "invisibility": "隐形术",
    "lightning-bolt": "闪电束",
    "mage-armor": "法师护甲",
    "mage-hand": "魔法手",
    "magic-missile": "魔法飞弹",
    "raise-dead": "复活术",
    "see-invisibility": "识破隐形",
    "shield": "护盾术",
    "sleep": "睡眠术",
    "slow": "减速术",
    "teleport": "传送术",
    "wish": "许愿术",
}

DND_LOCAL_SPELLS = {
    "fireball": {
        "name": "火球术",
        "en_name": "Fireball",
        "level": "3环",
        "school": "塑能",
        "casting_time": "1动作",
        "range": "150尺",
        "components": "V、S、M",
        "duration": "立即",
        "summary": "指定距离内一点爆发火焰，范围内生物进行敏捷豁免；失败承受火焰伤害，成功减半。升环时伤害提高。",
    },
    "magic-missile": {
        "name": "魔法飞弹",
        "en_name": "Magic Missile",
        "level": "1环",
        "school": "塑能",
        "casting_time": "1动作",
        "range": "120尺",
        "components": "V、S",
        "duration": "立即",
        "summary": "创造数枚自动命中的力场飞弹，可分配给一个或多个可见目标。升环时飞弹数量增加。",
    },
    "shield": {
        "name": "护盾术",
        "en_name": "Shield",
        "level": "1环",
        "school": "防护",
        "casting_time": "1反应",
        "range": "自身",
        "components": "V、S",
        "duration": "1轮",
        "summary": "在被攻击命中或成为魔法飞弹目标时触发，短暂提高 AC，并免疫魔法飞弹。",
    },
    "counterspell": {
        "name": "法术反制",
        "en_name": "Counterspell",
        "level": "3环",
        "school": "防护",
        "casting_time": "1反应",
        "range": "60尺",
        "components": "S",
        "duration": "立即",
        "summary": "尝试中断一个正在施放的法术。目标法术环阶较高时，可能需要施法属性检定。",
    },
    "cure-wounds": {
        "name": "疗伤术",
        "en_name": "Cure Wounds",
        "level": "1环",
        "school": "塑能",
        "casting_time": "1动作",
        "range": "触及",
        "components": "V、S",
        "duration": "立即",
        "summary": "触碰一个生物并恢复生命值；对不死生物和构装体通常无效。升环时治疗量提高。",
    },
    "healing-word": {
        "name": "治疗真言",
        "en_name": "Healing Word",
        "level": "1环",
        "school": "塑能",
        "casting_time": "1附赠动作",
        "range": "60尺",
        "components": "V",
        "duration": "立即",
        "summary": "以短促圣言治疗一个可见生物；治疗量较低但施法很快。升环时治疗量提高。",
    },
    "bless": {
        "name": "祝福术",
        "en_name": "Bless",
        "level": "1环",
        "school": "附魔",
        "casting_time": "1动作",
        "range": "30尺",
        "components": "V、S、M",
        "duration": "专注，至多1分钟",
        "summary": "让若干目标在攻击检定和豁免检定上获得额外加值。升环时可影响更多目标。",
    },
    "detect-magic": {
        "name": "侦测魔法",
        "en_name": "Detect Magic",
        "level": "1环",
        "school": "预言",
        "casting_time": "1动作",
        "range": "自身",
        "components": "V、S",
        "duration": "专注，至多10分钟",
        "summary": "感知附近魔法灵光，并可辨认其魔法学派。本法术可作为仪式施放。",
    },
    "dispel-magic": {
        "name": "解除魔法",
        "en_name": "Dispel Magic",
        "level": "3环",
        "school": "防护",
        "casting_time": "1动作",
        "range": "120尺",
        "components": "V、S",
        "duration": "立即",
        "summary": "终止目标身上的法术效果。目标效果环阶较高时，可能需要施法属性检定。",
    },
    "invisibility": {
        "name": "隐形术",
        "en_name": "Invisibility",
        "level": "2环",
        "school": "幻术",
        "casting_time": "1动作",
        "range": "触及",
        "components": "V、S、M",
        "duration": "专注，至多1小时",
        "summary": "使一个生物隐形，直到法术结束，或目标攻击、施法。升环时可影响更多目标。",
    },
}

MYTHOS_RITUALS = {
    "驱逐实体": {
        "name": "驱逐实体",
        "en_name": "Banish Entity",
        "source": "Cthulhu Eternal / Open Mythos Rituals",
        "summary": "用于将被召唤或进入现实的神话实体逐出当前场景。具体代价、时长和检定应按主持人采用的规则处理。",
    },
    "召唤实体": {
        "name": "召唤实体",
        "en_name": "Summon Entities",
        "source": "Cthulhu Eternal / Open Mythos Rituals",
        "summary": "用于联系或召来神话存在。该类仪式通常需要罕见材料、漫长准备和明显风险。",
    },
    "伊本加齐粉": {
        "name": "伊本-加齐粉",
        "en_name": "Powder of Ibn-Ghazi",
        "source": "Cthulhu Eternal / Open Mythos Rituals",
        "summary": "一种令不可见事物短暂显现的神秘粉末。适合用于揭示隐形实体、痕迹或超自然现象。",
    },
    "沃瑞什印记": {
        "name": "沃瑞什印记",
        "en_name": "Voorish Sign",
        "source": "Cthulhu Eternal / Open Mythos Rituals",
        "summary": "一种辅助仪式的神秘手势或符号，常用于强化感知、开启仪式流程或接触超自然存在。",
    },
    "加速愈合": {
        "name": "加速愈合",
        "en_name": "Accelerated Healing",
        "source": "Cthulhu Eternal / Open Mythos Rituals",
        "summary": "用于推动伤口以不自然速度恢复。主持人应同时处理仪式代价和可能的副作用。",
    },
}

MYTHOS_ALIASES = {
    "banishentity": "驱逐实体",
    "驱逐": "驱逐实体",
    "summonentities": "召唤实体",
    "召唤": "召唤实体",
    "powderofibnghazi": "伊本加齐粉",
    "powderofibn-ghazi": "伊本加齐粉",
    "伊本加齐": "伊本加齐粉",
    "voorishsign": "沃瑞什印记",
    "沃瑞什": "沃瑞什印记",
    "acceleratedhealing": "加速愈合",
    "愈合": "加速愈合",
}


def _normalize_name(value: str) -> str:
    value = (value or "").strip().lower()
    return re.sub(r"[\s_.'’`·\-]+", "", value)


def _normalize_lookup(value: str) -> str:
    return re.sub(r"[\s_.'’`·\-:：/／（）()【】\[\]]+", "", (value or "").strip().lower())


def _split_aliases(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[/／,，;；|｜\n]+", value or "") if part.strip()]


def _english_aliases(value: str) -> list[str]:
    return [item.strip() for item in re.findall(r"[A-Za-z][A-Za-z '()\\-]+", value or "") if item.strip()]


def _xlsx_col(cell_ref: str) -> str:
    match = re.match(r"[A-Z]+", cell_ref or "")
    return match.group(0) if match else ""


def _xlsx_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    values = []
    for item in root.findall("m:si", XLSX_NS):
        parts = []
        for text in item.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"):
            parts.append(text.text or "")
        values.append("".join(parts))
    return values


def _xlsx_cell_text(cell, shared: list[str]) -> str:
    value_node = cell.find("m:v", XLSX_NS)
    if value_node is None:
        return ""
    value = value_node.text or ""
    if cell.attrib.get("t") == "s":
        try:
            return shared[int(value)]
        except (IndexError, ValueError):
            return ""
    return value


def _xlsx_sheet_targets(zf: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
    targets = []
    for sheet in workbook.find("m:sheets", XLSX_REL_NS):
        sheet_name = sheet.attrib.get("name", "")
        rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        target = rel_map.get(rel_id)
        if target:
            targets.append((sheet_name, "xl/" + target.lstrip("/")))
    return targets


def _load_sealdice_dnd_entries() -> list[dict]:
    entries = []
    dnd_dir = SEALDICE_HELPDOC_DIR / "DND"
    if not dnd_dir.exists():
        return entries

    for path in sorted(dnd_dir.glob("*.xlsx")):
        try:
            with zipfile.ZipFile(path) as zf:
                shared = _xlsx_shared_strings(zf)
                for sheet_name, target in _xlsx_sheet_targets(zf):
                    if "法术" not in sheet_name:
                        continue
                    root = ET.fromstring(zf.read(target))
                    for row in root.findall(".//m:row", XLSX_NS):
                        if row.attrib.get("r") == "1":
                            continue
                        values = {
                            _xlsx_col(cell.attrib.get("r", "")): _xlsx_cell_text(cell, shared)
                            for cell in row.findall("m:c", XLSX_NS)
                        }
                        key = values.get("A", "").strip()
                        content = values.get("C", "").strip()
                        if key and content:
                            entries.append(
                                {
                                    "key": key,
                                    "synonym": values.get("B", "").strip(),
                                    "content": content,
                                    "book": path.stem,
                                    "sheet": sheet_name,
                                }
                            )
        except Exception:
            continue
    return entries


def _load_sealdice_coc_entries() -> dict:
    path = SEALDICE_HELPDOC_DIR / "COC" / "魔法大典.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    helpdoc = data.get("helpdoc", {})
    return helpdoc if isinstance(helpdoc, dict) else {}


def _sealdice_dnd_entries() -> list[dict]:
    global _SEALDICE_DND_CACHE
    if _SEALDICE_DND_CACHE is None:
        _SEALDICE_DND_CACHE = _load_sealdice_dnd_entries()
    return _SEALDICE_DND_CACHE


def _sealdice_coc_entries() -> dict:
    global _SEALDICE_COC_CACHE
    if _SEALDICE_COC_CACHE is None:
        _SEALDICE_COC_CACHE = _load_sealdice_coc_entries()
    return _SEALDICE_COC_CACHE


def _lookup_sealdice_dnd_spell(name: str) -> str | None:
    query = _normalize_lookup(name)
    if not query:
        return None
    entries = _sealdice_dnd_entries()
    exact_matches = []
    fuzzy_matches = []
    for entry in entries:
        first_content_line = entry.get("content", "").splitlines()[0] if entry.get("content") else ""
        names = [
            entry["key"],
            first_content_line,
            *_english_aliases(first_content_line),
            *_split_aliases(entry.get("synonym", "")),
        ]
        normalized_names = [_normalize_lookup(item) for item in names if item]
        if query in normalized_names:
            exact_matches.append(entry)
        elif any(query in item or item in query for item in normalized_names):
            fuzzy_matches.append(entry)

    match = exact_matches[0] if exact_matches else (fuzzy_matches[0] if fuzzy_matches else None)
    if not match:
        return None
    return (
        f"【DND法术】{match['key']}\n"
        f"{match['content']}\n"
        f"出处分组：{match['book']} / {match['sheet']}\n"
        f"{SEALDICE_DND_SOURCE}"
    )


def _lookup_sealdice_coc_spell(name: str) -> str | None:
    query = _normalize_lookup(name)
    if not query:
        return None
    entries = _sealdice_coc_entries()
    exact_key = None
    fuzzy_key = None
    for key in entries:
        names = [key, *_split_aliases(key)]
        normalized_names = [_normalize_lookup(item) for item in names]
        if query in normalized_names:
            exact_key = key
            break
        if fuzzy_key is None and any(query in item or item in query for item in normalized_names):
            fuzzy_key = key
    key = exact_key or fuzzy_key
    if key is None:
        return None
    display_key = re.sub(r"^coc\s+", "", key, flags=re.I).strip() or key
    return f"【COC法术】{display_key}\n{entries[key]}\n{SEALDICE_COC_SOURCE}"


def _slugify_dnd_name(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def _join_api_values(values) -> str:
    if not values:
        return "无"
    if isinstance(values, list):
        return "、".join(str(item) for item in values)
    return str(values)


def _api_get_json(path: str) -> dict:
    url = f"{DND5E_API_BASE}{path}"
    request = urllib.request.Request(url, headers={"User-Agent": "AstrBot-TRPGdice/1.0"})
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))


def _resolve_dnd_slug(name: str) -> str:
    normalized = _normalize_name(name)
    if normalized in DND_SPELL_ALIASES:
        return DND_SPELL_ALIASES[normalized]
    return _slugify_dnd_name(name)


def _format_dnd_spell(data: dict, slug: str) -> str:
    cn_name = DND_SPELL_CN_NAMES.get(slug)
    title = f"{cn_name} / {data.get('name', slug)}" if cn_name else data.get("name", slug)
    level = data.get("level", 0)
    level_text = "戏法" if level == 0 else f"{level}环"
    school = data.get("school", {}).get("name", "未知")
    components = _join_api_values(data.get("components", []))
    material = data.get("material")
    concentration = "是" if data.get("concentration") else "否"
    ritual = "是" if data.get("ritual") else "否"
    desc = "\n".join(data.get("desc", [])) or "暂无描述。"
    higher_level = "\n".join(data.get("higher_level", []))

    lines = [
        f"【DND法术】{title}",
        f"等级：{level_text}；学派：{school}",
        f"施法时间：{data.get('casting_time', '未知')}；距离：{data.get('range', '未知')}",
        f"成分：{components}；专注：{concentration}；仪式：{ritual}",
        f"持续时间：{data.get('duration', '未知')}",
    ]
    if material:
        lines.append(f"材料：{material}")
    lines.append(f"效果：{desc}")
    if higher_level:
        lines.append(f"升环：{higher_level}")
    lines.append("资料源：D&D 5e SRD API（SRD/CC-BY-4.0）；英文描述来自 SRD。")
    return "\n".join(lines)


def _format_local_dnd_spell(slug: str, reason: str = "") -> str:
    spell = DND_LOCAL_SPELLS[slug]
    lines = [
        f"【DND法术】{spell['name']} / {spell['en_name']}",
        f"等级：{spell['level']}；学派：{spell['school']}",
        f"施法时间：{spell['casting_time']}；距离：{spell['range']}",
        f"成分：{spell['components']}；持续时间：{spell['duration']}",
        f"效果摘要：{spell['summary']}",
        "资料源：D&D 5e SRD；当前为插件内置中文摘要。",
    ]
    if reason:
        lines.append(f"联网查询未使用：{reason}")
    return "\n".join(lines)


def _lookup_dnd_spell(name: str) -> str:
    slug = _resolve_dnd_slug(name)
    try:
        data = _api_get_json(f"/spells/{urllib.parse.quote(slug)}")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            if slug in DND_LOCAL_SPELLS:
                return _format_local_dnd_spell(slug)
            return f"没有找到 DND SRD 法术：{name}\n可以试试英文名，如 .查询法术 dnd fireball。"
        return f"DND 法术查询失败：HTTP {exc.code}"
    except Exception as exc:
        if slug in DND_LOCAL_SPELLS:
            return _format_local_dnd_spell(slug, str(exc))
        return f"DND 法术查询失败：{exc}"
    return _format_dnd_spell(data, slug)


def _lookup_mythos_ritual(name: str) -> str:
    normalized = _normalize_name(name)
    key = MYTHOS_ALIASES.get(normalized, name.strip())
    ritual = MYTHOS_RITUALS.get(key)
    if ritual is None:
        return (
            f"没有找到神话仪式：{name}\n"
            "当前内置：驱逐实体、召唤实体、伊本加齐粉、沃瑞什印记、加速愈合。"
        )
    return (
        f"【神话仪式】{ritual['name']} / {ritual['en_name']}\n"
        f"简介：{ritual['summary']}\n"
        f"资料源：{ritual['source']}。此处不是 Chaosium 官方 CoC 法术全文。"
    )


def query_spell(raw_query: str) -> str:
    query = (raw_query or "").strip()
    if not query:
        return (
            "法术查询用法：\n"
            ".查询法术 火球术\n"
            ".查询法术 dnd fireball\n"
            ".查询法术 神话 驱逐实体\n"
            "DND 查询基于 SRD；CoC 相关仅提供开放神话仪式摘要。"
        )

    parts = query.split(maxsplit=1)
    first = parts[0].lower()
    rest = parts[1].strip() if len(parts) > 1 else ""

    if first in {"dnd", "5e", "d&d"}:
        sealdice_result = _lookup_sealdice_dnd_spell(rest or query)
        if sealdice_result:
            return sealdice_result
        return _lookup_dnd_spell(rest or query)
    if first in {"coc", "克苏鲁", "神话", "仪式"}:
        sealdice_result = _lookup_sealdice_coc_spell(rest or query)
        if sealdice_result:
            return sealdice_result
        return _lookup_mythos_ritual(rest or query)

    normalized = _normalize_name(query)
    if normalized in MYTHOS_ALIASES or query in MYTHOS_RITUALS:
        return _lookup_mythos_ritual(query)
    sealdice_result = _lookup_sealdice_dnd_spell(query) or _lookup_sealdice_coc_spell(query)
    if sealdice_result:
        return sealdice_result
    return _lookup_dnd_spell(query)
