import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedInlineCommand:
    cmd: str
    expr: str = ""
    remark: Optional[str] = None
    skill_value: Optional[str] = ""
    dice_count: str = "1"
    roll_times: str = "1"


def strip_command_prefix(message: str, prefixes: list[str]) -> Optional[str]:
    if not any(message.startswith(prefix) for prefix in prefixes):
        return None
    return re.sub(r"\s+", "", message[1:])


def _split_skill_and_value(expr: str) -> tuple[str, Optional[str]]:
    expr = expr.strip()
    if not expr:
        return "", None

    explicit_with_modifier = re.match(r"^(.+?)(\d+)([+-]\d+)$", expr)
    if explicit_with_modifier:
        name = explicit_with_modifier.group(1) + explicit_with_modifier.group(3)
        return name.strip(), explicit_with_modifier.group(2)

    if re.match(r"^.+[+-]\d+$", expr):
        return expr, None

    value_match = re.search(r"(\d+)$", expr)
    if value_match:
        value = value_match.group(1)
        name = expr[:-len(value)].strip()
        return (name or value), value

    return expr, None


def _parse_check_command(message: str, prefix: str) -> ParsedInlineCommand:
    body = message[len(prefix):]
    roll_times = "1"
    dice_count = "0"
    cmd = prefix

    hash_match = re.match(r"^(\d+)#(.+)", body)
    if hash_match:
        roll_times = hash_match.group(1)
        body = hash_match.group(2)

    if prefix in {"ra", "rc"}:
        if body.startswith("b"):
            cmd = "rab"
            body = body[1:]
        elif body.startswith("p"):
            cmd = "rap"
            body = body[1:]

    if prefix in {"rav", "rcv"}:
        return ParsedInlineCommand(cmd=cmd, expr=body.strip(), roll_times=roll_times)

    pure_number = False
    if cmd in {"rab", "rap"}:
        body = body.strip()
        if "c" in body:
            parts = body.split("c", 1)
            dice_count = parts[0].strip() or "1"
            body = parts[1].strip()
            pure_number = body.isdigit()
        elif body.isdigit():
            dice_count = "1"
            pure_number = True
        else:
            dice_match = re.match(r"^(\d+)", body)
            if dice_match:
                matched_num = dice_match.group(1)
                remaining = body[len(matched_num):].strip()
                if not remaining:
                    dice_count = "1"
                    pure_number = True
                    body = matched_num
                else:
                    dice_count = matched_num
                    body = remaining
            else:
                dice_count = "1"

    skill_name, skill_value = _split_skill_and_value(body)
    if pure_number:
        skill_value = skill_value or body
        skill_name = skill_name or str(skill_value)

    return ParsedInlineCommand(
        cmd=cmd,
        expr=skill_name.strip(),
        skill_value=skill_value,
        dice_count=dice_count,
        roll_times=roll_times,
    )


def parse_inline_command(message: str) -> Optional[ParsedInlineCommand]:
    """Parse dot-style inline commands handled by identify_command."""
    m = re.match(r"^([a-z]+)", message, re.I)
    if not m:
        return None

    cmd = m.group(1).lower()
    expr = message[m.end():].strip()
    remark = None
    skill_value: Optional[str] = ""
    dice_count = "1"
    roll_times = "1"

    if cmd[0:2] == "en":
        sv_match = re.search(r"\d+$", message)
        if sv_match:
            skill_value = sv_match.group()
            expr = message[2:len(message) - len(skill_value)]
        else:
            skill_value = None
            expr = message[2:]
        cmd = "en"

    if cmd == "rau":
        return _parse_check_command(message, "rau")

    if cmd == "rb":
        return _parse_check_command(f"rab{message[2:]}", "ra")

    if cmd == "rp":
        return _parse_check_command(f"rap{message[2:]}", "ra")

    if cmd == "hl":
        return _parse_check_command(f"rah{message[2:]}", "rah")

    if cmd in {"rah", "rch", "rav", "rcv"}:
        return _parse_check_command(message, cmd)

    if cmd[0:2] in {"ra", "rc"}:
        return _parse_check_command(message, cmd[0:2])

    elif cmd == "ri":
        expr = message[2:].strip()

    elif cmd[0:2] == "rd":
        raw = message[2:].strip()
        dice_match = re.match(r"(\d+)", raw)
        if dice_match:
            dice_size = dice_match.group(1)
            expr = f"1d{dice_size}"
            remark = raw[len(dice_size):].strip()
        else:
            expr = "1d100"
            remark = raw.strip()
        cmd = "rd"

    elif cmd[0] == "r":
        is_hidden_roll = cmd == "rh"
        command_len = 2 if is_hidden_roll else 1
        content = message[command_len:].strip()
        if not content:
            expr = "1d100"
            remark = ""
        else:
            match = re.match(r"([\d#+\-*/().xXdkvbpBP]+)", content, re.IGNORECASE)
            if match:
                expr = match.group(1)
                remark = content[match.end():].strip()
            else:
                expr = "1d100"
                remark = content.strip()
        cmd = "rh" if is_hidden_roll else "r"

    return ParsedInlineCommand(
        cmd=cmd,
        expr=expr,
        remark=remark,
        skill_value=skill_value,
        dice_count=dice_count,
        roll_times=roll_times,
    )
