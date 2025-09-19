import random

class InitiativeItem:
    """
    先攻表中的一项，包含角色名、玩家ID、先攻值等信息。
    """
    def __init__(self, name, player_id, value):
        self.name = name
        self.player_id = player_id
        self.value = value

    def __repr__(self):
        return f"{self.name}({self.value})"

# 先攻表和当前轮次索引
init_list = []
current_index = 0

def add_item(name, player_id, value):
    """
    添加一个角色到先攻表。
    """
    global init_list
    item = InitiativeItem(name, player_id, value)
    init_list.append(item)

def remove_by_name(name):
    """
    按角色名移除先攻表中的角色。
    """
    global init_list
    init_list = [item for item in init_list if item.name != name]

def remove_by_player(player_id):
    """
    按玩家ID移除先攻表中的角色。
    """
    global init_list
    init_list = [item for item in init_list if item.player_id != player_id]

def init_clear():
    """
    清空先攻表和轮次索引。
    """
    global init_list, current_index
    init_list = []
    current_index = 0

def sort_list():
    """
    按先攻值降序排列先攻表。
    """
    global init_list
    init_list.sort(key=lambda x: x.value, reverse=True)

def next_turn():
    """
    轮到下一个角色，返回当前角色。
    """
    global current_index, init_list
    if not init_list:
        return None
    current_index = (current_index + 1) % len(init_list)
    return init_list[current_index]

def format_list():
    """
    返回格式化的先攻表字符串。
    """
    global init_list, current_index
    result = []
    for idx, item in enumerate(init_list):
        marker = "←当前" if idx == current_index else ""
        result.append(f"{item.name}({item.value}) {marker}")
    return "\n".join(result)

def initiative(characters):
    """
    根据角色列表生成先攻表（随机掷骰）。
    characters: [(name, player_id, base_value), ...]
    """
    init_clear()
    for name, player_id, base_value in characters:
        value = base_value + random.randint(1, 20)
        add_item(name, player_id, value)
    sort_list()

def roll_initiative(name, player_id, base_value):
    """
    单独为一个角色掷先攻并加入先攻表。
    """
    value = base_value + random.randint(1, 20)
    add_item(name, player_id, value)
    sort_list()

def end_current_round():
    """
    结束当前轮次，重置轮次索引。
    """
    global current_index
    current_index = 0