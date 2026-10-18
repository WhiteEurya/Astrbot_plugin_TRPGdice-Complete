"""Versioned subclass identities; unverified resource rules are never inferred."""

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import re


CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "dnd" / "subclasses.json"
SOURCE_ORDER = {"phb2014": 2014, "scag": 2015, "xgte": 2017, "tcoe": 2020, "phb2024": 2024}
SOURCE_SUFFIX = {"phb2014": "2014", "scag": "剑湾", "xgte": "珊娜萨", "tcoe": "塔莎", "phb2024": "2024"}
CUSTOM_SUBCLASS = "自定义"


@dataclass(frozen=True)
class Subclass:
    id: str
    class_id: str
    name: str
    english: str
    aliases: tuple
    source: str
    edition: str
    resource_rules_status: str = "pending_verification"
    resource_definitions: tuple = ()


def normalize(name):
    return " ".join(name.strip().casefold().split())


@lru_cache(maxsize=1)
def load_catalog():
    with CATALOG_PATH.open(encoding="utf-8") as stream:
        data = json.load(stream)
    if data["schema_version"] != 1:
        raise ValueError("不支持的子职目录版本。")
    entries = []
    for source, classes in data["books"].items():
        for class_id, rows in classes.items():
            for row in rows:
                english, name = row[:2]
                slug = re.sub(r"[^a-z0-9]+", "-", english.casefold()).strip("-")
                entries.append(Subclass(
                    id=f"{source}:{class_id}:{slug}", class_id=class_id,
                    name=name, english=english, aliases=tuple(row[2] if len(row) > 2 else []),
                    source=source, edition=data["sources"][source]["edition"],
                    resource_rules_status=data["resource_rules_status"],
                ))
    if len({entry.id for entry in entries}) != len(entries):
        raise ValueError("子职目录存在重复 ID。")
    return data["sources"], tuple(entries)


def source_id(name):
    sources, _ = load_catalog()
    name = normalize(name)
    for key, source in sources.items():
        if name in {normalize(key), normalize(source["name"]), *(normalize(alias) for alias in source["aliases"])}:
            return key
    raise ValueError("来源无效，可用 phb2014、剑湾、珊娜萨、塔莎、2024。")


def find_subclasses(name, class_id=None, source=None):
    _, entries = load_catalog()
    name = normalize(name)
    return tuple(entry for entry in entries
                 if (class_id is None or entry.class_id == class_id)
                 and (source is None or entry.source == source)
                 and name in {normalize(entry.name), normalize(entry.english),
                              *(normalize(alias) for alias in entry.aliases)})


def split_source_suffix(name):
    sources, _ = load_catalog()
    choices = [(alias, key) for key, source in sources.items()
               for alias in [key, source["name"], *source["aliases"]]]
    for alias, key in sorted(choices, key=lambda item: len(item[0]), reverse=True):
        if normalize(name).endswith(normalize(alias)):
            prefix = name[:-len(alias)].strip()
            if prefix:
                return prefix, key, normalize(alias) in {"2014", "2024"}
    return name, None, False


def latest_class_edition(class_id):
    return max((entry.edition for entry in load_catalog()[1] if entry.class_id == class_id), default="2024")


def resolve_subclass(name, class_id, edition=None):
    """Select the latest local publication unless a suffix requests older rules."""
    if normalize(name) in {CUSTOM_SUBCLASS, "custom"}:
        return CUSTOM_SUBCLASS, None, "custom"
    source = None
    selected_edition = None
    if "@" in name:
        name, source_name = name.rsplit("@", 1)
        source = source_id(source_name)
    else:
        name, source, edition_suffix = split_source_suffix(name)
        if edition_suffix:
            selected_edition = "2024" if source == "phb2024" else "2014"
            source = None
    matches = find_subclasses(name, class_id, source)
    if selected_edition or (edition == "2014" and source is None):
        matches = tuple(entry for entry in matches if entry.edition == (selected_edition or edition))
    if not matches:
        if source is not None or selected_edition is not None:
            raise ValueError("该来源中没有此职业的这个子职；请用 .pc class list 查询。")
        if find_subclasses(name):
            raise ValueError("这个子职不属于当前主职业；请用 .pc class list 查询。")
        return name, None, "custom"
    entry = max(matches, key=lambda item: SOURCE_ORDER[item.source])
    label = entry.name + SOURCE_SUFFIX[entry.source]
    return label, entry.id, "catalogued"


def format_catalog(class_names, class_id=None, source=None):
    sources, entries = load_catalog()
    lines = [f"DnD 子职目录：{len(entries)} 条出版记录（同名重印、不同版本分开）。"]
    if class_id is None and source is None:
        for key, book in sources.items():
            lines.append(f"{book['name']}: {sum(entry.source == key for entry in entries)}")
        lines.append("查询：.pc class list 战士 / .pc class list 塔莎 / .pc class list 武僧 2024")
    else:
        for key, label in class_names.items():
            if class_id is not None and key != class_id:
                continue
            selected = [entry for entry in entries if entry.class_id == key
                        and (source is None or entry.source == source)]
            if selected:
                lines.append(label + ": " + "、".join(entry.name + SOURCE_SUFFIX[entry.source] for entry in selected))
        if len(lines) == 1:
            lines.append("该来源下没有此职业的子职记录。")
    custom_classes = [label for key, label in class_names.items() if class_id is None or key == class_id]
    lines.append("自定义选项（不属于上述出版记录）：" + "、".join(f"{label}(自定义)" for label in custom_classes))
    lines.append("自定义子职只计算主职业公共资源；子职资源用 .res add 资源名 上限 手动添加，不随休息恢复。")
    lines.append("录入：.pc class 战士(战斗大师):5；默认本地目录最新版，旧版用 战士2014(战斗大师2014):5。")
    lines.append("目录收录不代表全部特性均自动处理；中文名为便捷译名。")
    return "\n".join(lines)
