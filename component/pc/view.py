import re
from typing import Iterable, List

from ..common.output import get_output
from ..common.utils import SYNONYMS


def get_primary_attributes(attributes: dict) -> dict:
    primary_attributes = {}
    for attr, value in attributes.items():
        primary_name = SYNONYMS.SYNONYM_MAP.get(attr, attr)
        if primary_name not in primary_attributes:
            primary_attributes[primary_name] = (attr, value)
        else:
            current_attr = primary_attributes[primary_name][0]
            if current_attr != primary_name and attr == primary_name:
                primary_attributes[primary_name] = (attr, value)
    return primary_attributes


def format_all_attributes(chara_data: dict) -> str:
    output_list = []
    for primary_name, (_original_attr, value) in sorted(get_primary_attributes(chara_data.get("attributes", {})).items()):
        output_list.append(f"{primary_name}: {value}")
    return get_output(
        "pc.show.all",
        name=chara_data["name"],
        attributes="\n".join(output_list)
    )


def format_threshold_attributes(attributes: dict, threshold: int, header_prefix: str = "") -> str:
    output_parts = []
    for attr, value in attributes.items():
        try:
            if value > threshold:
                output_parts.append(f"路 {attr}: {value}")
        except TypeError:
            continue

    if not output_parts:
        return get_output("pc.show.none_above", num=threshold)

    header = get_output("pc.show.above_threshold_header", num=threshold)
    return header_prefix + header + "\n" + "\n".join(output_parts)


def format_named_attributes(chara_data: dict, keys: Iterable[str], header_prefix: str = "") -> str:
    attributes = chara_data.get("attributes", {})
    found_attrs: List[str] = []
    not_found_attrs: List[str] = []

    for key in keys:
        if key in attributes:
            found_attrs.append(get_output("pc.show.attr", attr=key, value=attributes[key]))
        elif key not in chara_data.get("name", ""):
            not_found_attrs.append(key)

    output_parts = []
    if header_prefix:
        output_parts.append(header_prefix.rstrip("\n"))
    if found_attrs:
        output_parts.append("\n".join(found_attrs))
    if not_found_attrs:
        output_parts.append(get_output("pc.show.attr_missing", attribute=", ".join(not_found_attrs)))

    return "\n".join(output_parts)


def clean_st_show_words(args_str: str, chara_name: str) -> List[str]:
    base_str = args_str.split("@")[0] if "@" in args_str else args_str
    clean_text = re.sub(r"\[CQ:at.*?\]", " ", base_str)
    valid_words = []

    for word in clean_text.split():
        upper_word = word.upper()
        if word.startswith("@"):
            continue
        if "HP:" in upper_word or "SAN:" in upper_word or "DEX:" in upper_word:
            continue
        if re.match(r"^\d+/\d+$", word):
            continue
        if word == chara_name:
            continue
        valid_words.append(word)

    return valid_words
