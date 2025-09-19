import os
import json
import uuid
import random

from .output import get_output

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(PLUGIN_DIR, "..", "chara_data")

def get_user_folder(user_id: str):
    """
    获取用户的人物卡存储文件夹路径，不存在则自动创建。
    """
    folder = os.path.join(DATA_FOLDER, str(user_id))
    os.makedirs(folder, exist_ok=True)
    return folder

def get_all_characters(user_id: str):
    """
    获取用户所有人物卡，返回 {人物卡名: 人物卡id} 字典。
    """
    folder = get_user_folder(user_id)
    characters = {}
    for filename in os.listdir(folder):
        if filename.endswith(".json"):
            path = os.path.join(folder, filename)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                characters[data["name"]] = data["id"]
    return characters

def get_character_file(user_id: str, chara_id: str):
    """
    获取指定人物卡的文件路径。
    """
    return os.path.join(get_user_folder(user_id), f"{chara_id}.json")

def get_current_character_file(user_id: str):
    """
    获取当前选中人物卡的记录文件路径。
    """
    return os.path.join(get_user_folder(user_id), "current.txt")

def get_current_character_id(user_id: str):
    """
    获取当前选中的人物卡ID。
    """
    path = get_current_character_file(user_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None

def get_current_character(user_id: str):
    """
    获取当前选中的人物卡数据（字典），没有则返回None。
    """
    chara_id = get_current_character_id(user_id)
    if not chara_id:
        return None
    return load_character(user_id, chara_id)

def set_current_character(user_id: str, chara_id: str):
    """
    设置当前选中的人物卡ID，写入current.txt。
    """
    with open(get_current_character_file(user_id), "w", encoding="utf-8") as f:
        f.write(chara_id if chara_id is not None else "")

def load_character(user_id: str, chara_id: str):
    """
    加载指定人物卡的数据（字典），不存在则返回None。
    """
    path = get_character_file(user_id, chara_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_character(user_id: str, chara_id: str, data: dict):
    """
    保存人物卡数据到文件，并在写回前把常见同义词组同步更新。
    同义词组中任意一个字段在某个容器（data 或其子 dict）存在时，
    将把该容器内所有同义词字段更新为该出现字段的值。
    """
    path = get_character_file(user_id, chara_id)

    # 同义词组（每组第一个为“代表/优先检查字段”，但最终会把组内所有字段设为同一值）
    SYNONYMS = [
        ["力量", "str"],
        ["敏捷", "dex"],
        ["意志", "pow"],
        ["体质", "con"],
        ["外貌", "app"],
        ["教育", "知识", "edu"],
        ["体型", "siz"],
        ["智力", "灵感", "int"],
        ["san", "san值", "理智", "理智值"],
        ["幸运", "运气"],
        ["mp", "魔法"],
        ["hp", "体力", "max_hp"],
        ["max_san"],

        # 技能/替代名（根据你给出的列表合并）
        ["计算机", "计算机使用", "电脑"],
        ["会计"],
        ["人类学"],
        ["估价"],
        ["考古学"],
        ["取悦"],
        ["攀爬"],
        ["电脑", "计算机"],  # 重复安全
        ["信用", "信誉", "信用评级"],
        ["克苏鲁", "克苏鲁神话", "cm"],
        ["乔装"],
        ["闪避"],
        ["汽车", "驾驶", "汽车驾驶"],
        ["电气维修"],
        ["电子学"],
        ["话术"],
        ["斗殴"],
        ["手枪"],
        ["急救"],
        ["历史"],
        ["恐吓"],
        ["跳跃"],
        ["拉丁语"],
        ["母语"],
        ["法律"],
        ["图书馆", "图书馆使用"],
        ["聆听"],
        ["开锁", "撬锁", "锁匠"],
        ["机械维修"],
        ["医学"],
        ["博物学", "自然学"],
        ["领航", "导航"],
        ["神秘学"],
        ["重型操作", "重型机械", "操作重型机械", "重型"],
        ["说服"],
        ["精神分析"],
        ["心理学"],
        ["骑术"],
        ["妙手"],
        ["侦查"],
        ["潜行"],
        ["生存"],
        ["游泳"],
        ["投掷"],
        ["追踪"],
        ["驯兽"],
        ["潜水"],
        ["爆破"],
        ["读唇"],
        ["催眠"],
        ["炮术"],
        ["max_hp"],  # 已包含在 hp 组，但再列一次无伤
        ["max_san"],  # 同上
    ]

    # helper: 给单个容器（dict）同步同义词组
    def sync_container(container: dict):
        if not isinstance(container, dict):
            return
        for group in SYNONYMS:
            # 查找组内在容器中存在的键（保留顺序）
            present_keys = [k for k in group if k in container]
            if not present_keys:
                continue
            # 以第一个出现的键的值作为统一值
            value = container[present_keys[0]]
            # 将组中所有键都写回该值（无则新增）
            for k in group:
                container[k] = value

    # 对主 data 同步
    sync_container(data)

    # 对 data 下的所有直接子 dict 也同步（常见的 attributes/skills 等）
    for k, v in list(data.items()):
        if isinstance(v, dict):
            sync_container(v)

    # 最后写回文件
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def get_skill_value(user_id: str, skill_name: str):
    """
    获取当前选中人物卡的某项技能值，不存在则返回0。
    """
    chara_data = get_current_character(user_id)
    if not chara_data or skill_name not in chara_data["attributes"]:
        return 0
    return chara_data["attributes"][skill_name]

def create_character(user_id: str, name: str, attributes: dict):
    """
    创建新人物卡，自动生成唯一ID，并设为当前人物卡。
    返回新人物卡ID。
    """
    chara_id = str(uuid.uuid4())
    data = {"id": chara_id, "name": name, "attributes": attributes}
    save_character(user_id, chara_id, data)
    set_current_character(user_id, chara_id)
    return chara_id

def delete_character(user_id: str, name: str):
    """
    删除指定名字的人物卡。
    若删除的是当前人物卡，则清空current.txt。
    返回 (是否成功, 被删除人物卡ID)。
    """
    characters = get_all_characters(user_id)
    chara_id = get_current_character_id(user_id)
    if name not in characters:
        return False, None
    chara_to_delete_id = characters[name]
    path = get_character_file(user_id, chara_to_delete_id)
    try:
        os.remove(path)
    except FileNotFoundError:
        return False, None
    if chara_to_delete_id == chara_id:
        set_current_character(user_id, None)
    return True, chara_to_delete_id

def set_nickname(user_id: str, chara_id: str, nickname: str):
    """
    为指定人物卡设置昵称。
    """
    chara = load_character(user_id, chara_id)
    if chara:
        chara["nickname"] = nickname
        save_character(user_id, chara_id, chara)
        return True
    
    
def grow_up(user_id: str, skill_name: str, skill_value: int = None):
    """
    技能成长判定（COC规则）
    不依赖 event，返回结果字符串，由调用端处理发送。
    """
    update_skill_value = False

    # 如果未提供 skill_value，则从当前人物卡读取
    if skill_value is None:
        skill_value = get_skill_value(user_id, skill_name)
        chara_id = get_current_character_id(user_id)
        chara_data = load_character(user_id, chara_id)
        update_skill_value = True
    else:
        chara_id = get_current_character_id(user_id)
        chara_data = load_character(user_id, chara_id)

    # 校验 skill_value 是否为整数
    try:
        skill_value = int(skill_value)
    except ValueError:
        return get_output("pc.show.attr_missing", skill_name=skill_name)

    # 掷骰
    tens_digit = random.randint(0, 9)
    ones_digit = random.randint(0, 9)
    roll_result = 100 if (tens_digit == 0 and ones_digit == 0) else (tens_digit * 10 + ones_digit)

    # 成长判定：roll > skill_value 或 roll > 95 成长
    if roll_result > skill_value or roll_result > 95:
        en_value = random.randint(1, 10)
        new_value = skill_value + en_value
        result = get_output("pc.grow.success", skill_name=skill_name, skill_value=skill_value, en_value=en_value, new_value = new_value)
        if update_skill_value:
            chara_data["attributes"][skill_name] = skill_value + en_value
            save_character(user_id, chara_id, chara_data)
    else:
        result = get_output("pc.grow.failure")

    # 返回完整输出
    return get_output(
        "pc.grow.boost_result",
        skill_name=skill_name,
        roll_result=roll_result,
        skill_value=skill_value,
        result=result
    )