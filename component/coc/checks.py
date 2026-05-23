import re
from dataclasses import dataclass
from typing import Optional


STANDARD_CHECK_COMMANDS = {"ra", "rc"}
HIDDEN_CHECK_COMMANDS = {"rah", "rch"}
VERSUS_CHECK_COMMANDS = {"rav", "rcv"}

DIFFICULTY_PREFIXES = {
    "困难": "hard",
    "困難": "hard",
    "极难": "extreme",
    "極難": "extreme",
    "h": "hard",
    "H": "hard",
    "e": "extreme",
    "E": "extreme",
}


@dataclass(frozen=True)
class CheckIntent:
    command: str
    hidden: bool = False
    versus: bool = False
    rulebook: bool = False


def classify_check_command(command: str) -> Optional[CheckIntent]:
    command = command.lower().strip()
    if command in STANDARD_CHECK_COMMANDS:
        return CheckIntent(command=command, rulebook=command == "rc")
    if command in HIDDEN_CHECK_COMMANDS:
        return CheckIntent(command=command, hidden=True, rulebook=command == "rch")
    if command in VERSUS_CHECK_COMMANDS:
        return CheckIntent(command=command, versus=True, rulebook=command == "rcv")
    return None


def parse_difficulty_prefix(text: str) -> tuple[Optional[str], str]:
    text = text.strip()
    for prefix, difficulty in DIFFICULTY_PREFIXES.items():
        if text.startswith(prefix):
            if len(prefix) == 1 and len(text) > 1 and text[1].isascii() and text[1].isalpha():
                continue
            return difficulty, text[len(prefix):].strip()
    return None, text


def split_skill_modifier(skill_name: str) -> tuple[str, int]:
    match = re.match(r"^(.+?)([+-]\d+)$", skill_name.strip())
    if not match:
        return skill_name.strip(), 0
    return match.group(1).strip(), int(match.group(2))


def apply_difficulty(skill_value: int, difficulty: Optional[str]) -> int:
    if difficulty == "hard":
        return skill_value // 2
    if difficulty == "extreme":
        return skill_value // 5
    return skill_value


def difficulty_label(difficulty: Optional[str]) -> str:
    if difficulty == "hard":
        return "困难"
    if difficulty == "extreme":
        return "极难"
    return ""


def prepare_skill_check(skill_name: str, skill_value: int) -> tuple[str, int]:
    difficulty, clean_name = parse_difficulty_prefix(skill_name)
    clean_name, modifier = split_skill_modifier(clean_name)
    adjusted_value = max(0, skill_value + modifier)
    target_value = apply_difficulty(adjusted_value, difficulty)

    labels = []
    if difficulty:
        labels.append(difficulty_label(difficulty))
    if modifier:
        labels.append(f"{modifier:+d}")
    display_name = clean_name
    if labels:
        display_name = f"{clean_name}({', '.join(labels)})"
    return display_name, target_value


@dataclass(frozen=True)
class VersusCheckSpec:
    skill_name: str
    left_value: Optional[str] = None
    right_value: Optional[str] = None
    explicit_right: bool = False


def parse_versus_check(text: str) -> Optional[VersusCheckSpec]:
    """Parse .rav/.rcv body.

    Supported forms:
    - 技能名a70/b60
    - 技能名/b60
    - 技能名@对抗者 (the @ text is stripped before parsing; target comes from event)
    """
    text = re.sub(r"\[CQ:at.*?\]", "", text or "").strip()
    if not text:
        return None

    if "/" in text:
        left_part, right_part = text.split("/", 1)
        left_part = left_part.strip()
        right_part = right_part.strip()

        right_match = re.fullmatch(r"b?(\d+)", right_part, re.I)
        if not right_match:
            return None

        left_match = re.fullmatch(r"(.+?)(?:a(\d+))?", left_part, re.I)
        if not left_match:
            return None

        skill_name = left_match.group(1).strip()
        if not skill_name:
            return None
        return VersusCheckSpec(
            skill_name=skill_name,
            left_value=left_match.group(2),
            right_value=right_match.group(1),
            explicit_right=True,
        )

    skill_name = text.split("@", 1)[0].strip()
    return VersusCheckSpec(skill_name=skill_name) if skill_name else None
