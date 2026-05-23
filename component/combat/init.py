import random
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class InitiativeItem:
    name: str
    init_value: int
    player_id: int


class InitiativeManager:
    """Group-scoped initiative tracker."""

    def __init__(self):
        self._items: Dict[str, List[InitiativeItem]] = {}
        self._current_index: Dict[str, int] = {}

    def _ensure_group(self, group_id: str) -> None:
        self._items.setdefault(str(group_id), [])
        self._current_index.setdefault(str(group_id), -1)

    def add_item(self, group_id: str, item: InitiativeItem) -> None:
        group_id = str(group_id)
        self._ensure_group(group_id)
        self._items[group_id].append(item)
        self.sort_list(group_id)

    def remove_by_name(self, group_id: str, name: str) -> None:
        group_id = str(group_id)
        self._ensure_group(group_id)
        self._items[group_id] = [item for item in self._items[group_id] if item.name != name]
        if not self._items[group_id]:
            self._current_index[group_id] = -1
        elif self._current_index[group_id] >= len(self._items[group_id]):
            self._current_index[group_id] = 0

    def remove_by_player(self, group_id: str, player_id: int) -> None:
        group_id = str(group_id)
        self._ensure_group(group_id)
        self._items[group_id] = [item for item in self._items[group_id] if item.player_id != player_id]
        if not self._items[group_id]:
            self._current_index[group_id] = -1

    def clear(self, group_id: str) -> None:
        group_id = str(group_id)
        self._items[group_id] = []
        self._current_index[group_id] = -1

    def sort_list(self, group_id: str) -> None:
        group_id = str(group_id)
        self._ensure_group(group_id)
        self._items[group_id].sort(key=lambda x: x.init_value, reverse=True)

    def next_turn(self, group_id: str) -> Optional[InitiativeItem]:
        group_id = str(group_id)
        self._ensure_group(group_id)
        if not self._items[group_id]:
            return None

        if self._current_index[group_id] < 0:
            self._current_index[group_id] = 0
        else:
            self._current_index[group_id] = (self._current_index[group_id] + 1) % len(self._items[group_id])

        return self._items[group_id][self._current_index[group_id]]

    def current_turn(self, group_id: str) -> Optional[InitiativeItem]:
        group_id = str(group_id)
        self._ensure_group(group_id)
        if not self._items[group_id]:
            return None
        index = self._current_index[group_id]
        if index < 0 or index >= len(self._items[group_id]):
            return None
        return self._items[group_id][index]

    def format_list(self, group_id: str) -> str:
        group_id = str(group_id)
        self._ensure_group(group_id)
        if not self._items[group_id]:
            return "先攻列表为空"

        lines = []
        for i, item in enumerate(self._items[group_id]):
            prefix = "-> " if i == self._current_index[group_id] else "   "
            lines.append(f"{prefix}{item.name}: {item.init_value}")
        return "\n".join(lines)

    def parse_roll(self, expr: Optional[str], default_name: str) -> Tuple[int, str]:
        if not expr:
            return random.randint(1, 20), default_name

        if expr[0] == "+":
            match = re.match(r"\+(\d+)", expr)
            return random.randint(1, 20) + int(match.group(1)), default_name

        if expr[0] == "-":
            match = re.match(r"\-(\d+)", expr)
            return random.randint(1, 20) - int(match.group(1)), default_name

        match = re.match(r"(\d+)", expr)
        init_value = int(match.group(1))
        player_name = expr[match.end():] or default_name
        return init_value, player_name
