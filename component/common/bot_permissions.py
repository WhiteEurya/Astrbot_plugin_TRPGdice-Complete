"""Group-scoped delegates for bot control commands."""


def parse_bot_operators(value: str) -> set[tuple[str, str, str]]:
    if not isinstance(value, str):
        raise ValueError("授权名单须为文本。")
    operators = set()
    for number, line in enumerate(value.splitlines(), 1):
        parts = line.split()
        if not parts:
            continue
        if len(parts) != 3:
            raise ValueError(f"授权名单第 {number} 行须填写：适配器 群ID 用户ID。")
        platform, group_id, user_id = parts
        operators.add((platform, group_id, user_id))
    return operators
