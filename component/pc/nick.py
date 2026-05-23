from typing import Any, Dict


def format_coc_card(name: str, hp: int, max_hp: int, san: int, dex: int) -> str:
    return f"{name} HP:{hp}/{max_hp} SAN:{san} DEX:{dex}"


def build_coc_card(chara_data: Dict[str, Any]) -> str:
    attributes = chara_data.get("attributes", {})
    max_hp = (attributes.get("con", 0) + attributes.get("siz", 0)) // 10
    return format_coc_card(
        name=chara_data.get("name", ""),
        hp=attributes.get("hp", 0),
        max_hp=max_hp,
        san=attributes.get("san", 0),
        dex=attributes.get("dex", 0),
    )


def build_coc_long_card(chara_data: Dict[str, Any]) -> str:
    attributes = chara_data.get("attributes", {})
    max_hp = (attributes.get("con", 0) + attributes.get("siz", 0)) // 10
    return (
        f"{chara_data.get('name', '')} "
        f"HP:{attributes.get('hp', 0)}/{max_hp} "
        f"SAN:{attributes.get('san', 0)} "
        f"MP:{attributes.get('mp', 0)} "
        f"DEX:{attributes.get('dex', 0)}"
    )


def build_card_by_mode(chara_data: Dict[str, Any], mode: str = "coc") -> str:
    mode = (mode or "coc").lower()
    if mode == "cocl":
        return build_coc_long_card(chara_data)
    if mode == "none":
        return chara_data.get("name", "")
    if mode == "off":
        return ""
    return build_coc_card(chara_data)
