import os
import json
import uuid
import random
import shutil
import time

from ..common.output import get_output

from astrbot.api import logger

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FOLDER = os.path.join(PLUGIN_DIR, "..", "chara_data")

COC_DEFAULT_SKILLS = {
    "会计": 5,
    "人类学": 1,
    "估价": 5,
    "考古学": 1,
    "取悦": 15,
    "攀爬": 20,
    "计算机": 5,
    "信用": 0,
    "克苏鲁神话": 0,
    "乔装": 5,
    "汽车驾驶": 20,
    "电气维修": 10,
    "电子学": 1,
    "话术": 5,
    "斗殴": 25,
    "手枪": 20,
    "步枪": 25,
    "霰弹枪": 25,
    "弓": 15,
    "斧": 15,
    "剑": 20,
    "绞索": 15,
    "链锯": 10,
    "急救": 30,
    "历史": 5,
    "恐吓": 15,
    "跳跃": 20,
    "母语": 0,
    "法律": 5,
    "图书馆": 20,
    "聆听": 20,
    "开锁": 1,
    "机械维修": 10,
    "医学": 1,
    "博物学": 10,
    "领航": 10,
    "神秘学": 5,
    "重型操作": 1,
    "说服": 10,
    "精神分析": 1,
    "心理学": 10,
    "骑术": 5,
    "妙手": 10,
    "侦查": 25,
    "潜行": 20,
    "生存": 10,
    "游泳": 20,
    "投掷": 20,
    "追踪": 10,
    "驯兽": 5,
    "潜水": 1,
    "爆破": 1,
    "读唇": 1,
    "催眠": 1,
    "炮术": 1,
}

COC_DEFAULT_SKILL_ALIASES = {
    "计算机使用": "计算机",
    "电脑": "计算机",
    "信誉": "信用",
    "信用评级": "信用",
    "克苏鲁": "克苏鲁神话",
    "驾驶": "汽车驾驶",
    "汽车": "汽车驾驶",
    "图书馆使用": "图书馆",
    "撬锁": "开锁",
    "锁匠": "开锁",
    "自然学": "博物学",
    "导航": "领航",
    "重型机械": "重型操作",
    "操作重型机械": "重型操作",
    "重型": "重型操作",
    "闪躲": "闪避",
    "闪避": "闪避",
    "射击": "手枪",
    "射击(手枪)": "手枪",
    "射击（手枪）": "手枪",
    "射击(步枪)": "步枪",
    "射击（步枪）": "步枪",
    "射击(霰弹枪)": "霰弹枪",
    "射击（霰弹枪）": "霰弹枪",
    "步枪/霰弹枪": "步枪",
    "步霰": "步枪",
    "格斗": "斗殴",
    "格斗(斗殴)": "斗殴",
    "格斗（斗殴）": "斗殴",
}

COC_SPECIALIZED_DEFAULT_SKILLS = {
    "艺术": 5,
    "手艺": 5,
    "科学": 1,
    "外语": 1,
    "其他语言": 1,
    "生存": 10,
}

# NEW : BINDING

def get_user_folder(group_id: str, user_id: str):
    """
    获取：chara_data/{group_id}/{user_id}/
    """
    folder = os.path.join(DATA_FOLDER, str(group_id), str(user_id))
    os.makedirs(folder, exist_ok=True)
    return folder

def get_user_base_folder(user_id: str):
    """
    获取用户根目录：chara_data/user_metadata/{user_id}/
    用于存放 bindings.json 等跨群全局信息
    """
    folder = os.path.join(DATA_FOLDER, "user_metadata", str(user_id))
    os.makedirs(folder, exist_ok=True)
    return folder

def get_vault_folder(user_id: str):
    """获取用户的全域档案库目录。"""
    folder = os.path.join(get_user_base_folder(user_id), "vault")
    os.makedirs(folder, exist_ok=True)
    return folder

def get_vault_character_file(user_id: str, chara_id: str):
    return os.path.join(get_vault_folder(user_id), f"{chara_id}.json")

def _read_character_file(path: str):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def _write_character_file(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_binding_info(user_id: str):
    """获取用户的全局绑定配置"""
    path = os.path.join(get_user_base_folder(user_id), "bindings.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {} # 格式示例: {"group_A": "uuid_1", "group_B": "uuid_2"}

def set_binding_info(user_id: str, group_id: str, chara_id: str, global_binding: bool = False, local_binding: bool = False):
    """更新某个群的绑定关系"""
    bindings = get_binding_info(user_id)
    if chara_id:
        if local_binding:
            bindings[str(group_id)] = {"id": chara_id, "local": True}
        elif global_binding:
            bindings[str(group_id)] = {"id": chara_id, "global": True}
        else:
            bindings[str(group_id)] = chara_id
    else:
        bindings.pop(str(group_id), None)
    
    path = os.path.join(get_user_base_folder(user_id), "bindings.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bindings, f, indent=4)

### Universal Player ###

def is_global_character(user_id: str, chara_id: str) -> bool:
    data = _read_character_file(get_vault_character_file(user_id, chara_id))
    return bool(data and data.get("global", True))

def is_local_binding(group_id: str, user_id: str, chara_id: str) -> bool:
    bindings = get_binding_info(user_id)
    binding = bindings.get(str(group_id))
    return bool(isinstance(binding, dict) and binding.get("id") == chara_id and binding.get("local"))

def _get_bound_character_path(group_id: str, user_id: str, chara_id: str):
    if str(group_id) == "Vault":
        return get_vault_character_file(user_id, chara_id)

    vault_path = get_vault_character_file(user_id, chara_id)
    local_path = get_character_file(group_id, user_id, chara_id)

    if is_local_binding(group_id, user_id, chara_id):
        return local_path

    vault_data = _read_character_file(vault_path)
    if vault_data and vault_data.get("global", True):
        return vault_path

    if os.path.exists(local_path):
        return local_path

    return vault_path

def push_character_to_vault(group_id: str, user_id: str, chara_id: str, global_card: bool = False):
    data = load_character(group_id, user_id, chara_id)
    if not data:
        return False

    data["mtime"] = time.time()
    data["global"] = True
    data["global_source_group_id"] = str(group_id)

    _write_character_file(get_vault_character_file(user_id, chara_id), data)
    return True

def mark_character_global(group_id: str, user_id: str, chara_id: str):
    if not push_character_to_vault(group_id, user_id, chara_id, global_card=True):
        return False
    set_binding_info(user_id, group_id, chara_id, global_binding=True)
    return True

def unmark_character_global(group_id: str, user_id: str, chara_id: str):
    """让当前群隔离使用该卡的本地副本，不影响其他群的全局版本。"""
    data = _read_character_file(get_vault_character_file(user_id, chara_id))
    if not data:
        data = load_character(group_id, user_id, chara_id)
    if not data:
        return False

    data.pop("global_source_group_id", None)
    data["mtime"] = time.time()

    local_data = dict(data)
    local_data["global"] = False
    _write_character_file(get_character_file(group_id, user_id, chara_id), local_data)
    set_binding_info(user_id, group_id, chara_id, local_binding=True)
    return True

def touch_character(group_id: str, user_id: str, chara_id: str):
    """
    手动 Push 逻辑：强行刷新档案的修改时间，使其在全域扫描中成为‘最新版本’
    """
    return push_character_to_vault(group_id, user_id, chara_id)

def get_all_universal_characters(user_id: str):
    """
    全域扫描：对比所有群聊文件 + 中央金库，寻找每个 UUID 的最新版本
    """
    unique_chars = {} 
    
    # 扫描列表：包含所有群组文件夹 + 中央金库文件夹
    scan_dirs = []
    # 1. 加入所有普通群组路径
    if os.path.exists(DATA_FOLDER):
        for g_id in os.listdir(DATA_FOLDER):
            if g_id != "user_metadata":
                scan_dirs.append((g_id, os.path.join(DATA_FOLDER, g_id, str(user_id))))
    
    # 2. 加入中央金库路径 (标识为 'Vault')
    vault_path = get_vault_folder(user_id)
    scan_dirs.append(("Vault", vault_path))

    for label, u_path in scan_dirs:
        if os.path.exists(u_path):
            for filename in os.listdir(u_path):
                if filename.endswith(".json"):
                    uuid = filename[:-5]
                    is_global = is_global_character(user_id, uuid)
                    if is_global and label != "Vault":
                        continue
                    file_path = os.path.join(u_path, filename)
                    mtime = os.path.getmtime(file_path)
                    
                    # 只有当此版本更新，或者之前没记录过时才覆盖
                    if uuid not in unique_chars or mtime > unique_chars[uuid]["mtime"]:
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                unique_chars[uuid] = {
                                    "name": data.get("name", "未知"),
                                    "uuid": uuid,
                                    "group_id": label, # 这里的 label 可能是群号，也可能是 'Vault'
                                    "mtime": mtime,
                                    "global": is_global or bool(data.get("global"))
                                }
                        except: continue
                        
    return sorted(unique_chars.values(), key=lambda x: x["mtime"], reverse=True)

def clone_character_to_group(user_id: str, from_group: str, to_group: str, uuid: str):
    """
    物理复制：从 A 群目录拷贝到 B 群目录
    """
    if str(from_group) == "Vault":
        src_path = get_vault_character_file(user_id, uuid)
    else:
        src_path = os.path.join(DATA_FOLDER, str(from_group), str(user_id), f"{uuid}.json")
    dest_dir = os.path.join(DATA_FOLDER, str(to_group), str(user_id))
    os.makedirs(dest_dir, exist_ok=True)
    
    dest_path = os.path.join(dest_dir, f"{uuid}.json")
    
    if os.path.exists(src_path):
        shutil.copy2(src_path, dest_path) # 带元数据的物理拷贝
        return True
    return False

def check_character_file_exists(group_id: str, user_id: str, uuid: str):
    """检查特定群组路径下是否存在该 UUID 的文件"""
    path = os.path.join(DATA_FOLDER, str(group_id), str(user_id), f"{uuid}.json")
    return os.path.exists(path)

def get_local_file_mtime(group_id: str, user_id: str, uuid: str) -> float:
    """获取本地文件的 mtime，优先从 JSON 读取，失败则读系统属性"""
    path = os.path.join(DATA_FOLDER, str(group_id), str(user_id), f"{uuid}.json")
    if not os.path.exists(path):
        return 0.0
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 优先使用我们注入的 mtime 字段
            return data.get("mtime", os.path.getmtime(path))
    except:
        return os.path.getmtime(path)

### TAG HELPER

def get_sorted_chara_list(group_id: str, user_id: str):
    """ 返回排序后的角色列表 [(name, id), ...] 用于序号对应 """
    chars = get_all_characters(group_id, user_id)
    # 按角色名排序，保证序号 [1, 2, 3...] 稳定
    return sorted(chars.items(), key=lambda x: x[0])

def resolve_identifier(group_id: str, user_id: str, identifier: str):
    """ 
    解析标识符：
    1. 如果是数字，对应序号
    2. 如果是字符串，对应角色名
    """
    sorted_list = get_sorted_chara_list(group_id, user_id)
    
    identifier = str(identifier).strip()
    
    # 尝试作为序号解析
    if identifier.isdigit():
        idx = int(identifier) - 1
        if 0 <= idx < len(sorted_list):
            return sorted_list[idx][1] # 返回 ID
    
    # 尝试作为名字解析
    for name, chara_id in sorted_list:
        if name == identifier:
            return chara_id
            
    return None

### RENAME

def rename_character(group_id: str, user_id: str, chara_id: str, new_name: str):
    """
    重命名指定 ID 的角色。
    """
    # 1. 检查新名字是否在当前群已存在（防止冲突）
    characters = get_all_characters(group_id, user_id)
    if new_name in characters:
        return False, "duplicate"

    # 2. 加载并修改数据
    data = load_character(group_id, user_id, chara_id)
    if not data:
        return False, "not_found"
    
    old_name = data.get("name", "未知")
    data["name"] = new_name
    
    # 3. 保存回文件
    save_character(group_id, user_id, chara_id, data)
    return True, old_name

### SYNC LOGIC
def sync_derived_attributes(chara_data: dict):
    """
    根据基础属性自动同步派生属性（HP上限、理智上限等）。
    """
    attrs = chara_data.get("attributes", {})
    updates_made = []

    # 1. 计算 HP 上限: (体质 + 体型) // 10
    val_siz = attrs.get("siz", attrs.get("体型", 0))
    val_con = attrs.get("con", attrs.get("体质", 0))
    new_max_hp = (val_siz + val_con) // 10
    
    if attrs.get("max_hp") != new_max_hp:
        attrs["max_hp"] = new_max_hp
        # 同时同步中文名（如果有同义词逻辑，这里也可以调用同步函数）
        attrs["体力上限"] = new_max_hp 
        updates_made.append(f"最大体力: {new_max_hp}")
        
        try :
            attrs["hp"] = min(new_max_hp, attrs["hp"])
        except :
            pass

    # 2. 计算 理智上限: 99 - 克苏鲁神话
    val_cm = attrs.get("cm", attrs.get("克苏鲁神话", attrs.get("克苏鲁", 0)))
    new_max_san = 99 - val_cm
    
    if attrs.get("max_san") != new_max_san:
        attrs["max_san"] = new_max_san
        attrs["理智上限"] = new_max_san
        updates_made.append(f"理智上限: {new_max_san}")
        
        try :
            attrs["san"] = min(new_max_san, attrs["san"])
        except :
            pass

    return updates_made # 返回修改了哪些项，方便输出提示

### OLD LOGIC

def get_all_characters(group_id: str, user_id: str):
    """ 获取【当前群】用户的所有人物卡 {名: ID} """
    folder = get_user_folder(group_id, user_id)
    characters = {}

    if os.path.exists(folder):
        for filename in os.listdir(folder):
            if filename.endswith(".json"):
                path = os.path.join(folder, filename)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        characters[data["name"]] = data["id"]
                except Exception:
                    continue

    vault_folder = get_vault_folder(user_id)
    if os.path.exists(vault_folder):
        for filename in os.listdir(vault_folder):
            if not filename.endswith(".json"):
                continue
            try:
                with open(os.path.join(vault_folder, filename), "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("global", True):
                    characters[data["name"]] = data["id"]
            except Exception:
                continue
    return characters

def get_character_file(group_id: str, user_id: str, chara_id: str):
    """ 获取指定群组下、指定人物卡的文件路径 """
    return os.path.join(get_user_folder(group_id, user_id), f"{chara_id}.json")

def get_current_character_file(user_id: str):
    """
    获取当前选中人物卡的记录文件路径。
    """
    return os.path.join(get_user_folder(user_id), "current.txt")

def get_current_character_id(group_id: str, user_id: str):
    """ 【核心】从 bindings 获取当前群绑定的 ID """
    bindings = get_binding_info(user_id)
    binding = bindings.get(str(group_id))
    if isinstance(binding, dict):
        return binding.get("id")
    return binding

def is_current_binding_global(group_id: str, user_id: str):
    bindings = get_binding_info(user_id)
    binding = bindings.get(str(group_id))
    if isinstance(binding, dict):
        return not binding.get("local")
    return bool(binding)

def get_current_character(group_id : str, user_id: str):
    """
    获取当前选中的人物卡数据（字典），没有则返回None。
    """
    chara_id = get_current_character_id(group_id, user_id)
    if not chara_id:
        return None
    return load_character(group_id, user_id, chara_id)

def set_current_character(user_id: str, chara_id: str):
    """
    设置当前选中的人物卡ID，写入current.txt。
    """
    with open(get_current_character_file(user_id), "w", encoding="utf-8") as f:
        f.write(chara_id if chara_id is not None else "")

def load_character(group_id: str, user_id: str, chara_id: str):
    """ 加载当前群下的指定人物卡 """
    path = _get_bound_character_path(group_id, user_id, chara_id)
    data = _read_character_file(path)
    if data:
        return data

    local_path = get_character_file(group_id, user_id, chara_id)
    if local_path != path:
        return _read_character_file(local_path)
    return None

def save_character(group_id: str, user_id: str, chara_id: str, data: dict):
    """
    保存人物卡数据到文件，并在写回前把常见同义词组同步更新。
    同义词组中任意一个字段在某个容器（data 或其子 dict）存在时，
    将把该容器内所有同义词字段更新为该出现字段的值。
    """
    path = _get_bound_character_path(group_id, user_id, chara_id)

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
        ["hp", "体力"],
        ["max_hp"],
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

    data["mtime"] = time.time()

    if path == get_vault_character_file(user_id, chara_id):
        data["global"] = True
        set_binding_info(user_id, group_id, chara_id, global_binding=True)
        path = get_vault_character_file(user_id, chara_id)

    # 最后写回文件
    _write_character_file(path, data)


def _get_attribute_value(attributes: dict, *names):
    for name in names:
        if name in attributes:
            return attributes[name]
    return None

def get_coc_default_skill_value(skill_name: str, attributes: dict = None):
    attributes = attributes or {}
    skill_name = (skill_name or "").strip()
    canonical_name = COC_DEFAULT_SKILL_ALIASES.get(skill_name, skill_name)

    if canonical_name == "母语":
        edu = _get_attribute_value(attributes, "edu", "EDU", "教育", "知识")
        try:
            return int(edu)
        except (TypeError, ValueError):
            return 50

    if canonical_name == "闪避":
        dex = _get_attribute_value(attributes, "dex", "DEX", "敏捷")
        try:
            return int(dex) // 2
        except (TypeError, ValueError):
            return 25

    if canonical_name in COC_DEFAULT_SKILLS:
        return COC_DEFAULT_SKILLS[canonical_name]

    for prefix, default_value in COC_SPECIALIZED_DEFAULT_SKILLS.items():
        if (
            canonical_name == prefix
            or canonical_name.startswith(f"{prefix}(")
            or canonical_name.startswith(f"{prefix}（")
        ):
            return default_value

    return 0

def get_skill_value(group_id: str, user_id: str, skill_name: str):
    """
    获取当前【群组绑定】人物卡的某项技能值；没有填写时回落到 COC7 常见默认值。
    """
    chara_data = get_current_character(group_id, user_id) # 这里的 get_current_character 内部应调用 get_binding_info
    if not chara_data or "attributes" not in chara_data:
        return get_coc_default_skill_value(skill_name)

    attributes = chara_data["attributes"]
    if skill_name in attributes:
        return attributes[skill_name]

    canonical_name = COC_DEFAULT_SKILL_ALIASES.get((skill_name or "").strip(), (skill_name or "").strip())
    if canonical_name in attributes:
        return attributes[canonical_name]

    return get_coc_default_skill_value(skill_name, attributes)

def create_character(group_id: str, user_id: str, name: str, attributes: dict):
    """
    创建新人物卡，并注入元数据。
    """
    chara_id = str(uuid.uuid4())
    current_time = time.time() # 获取当前精确时间戳

    data = {
        "id": chara_id, 
        "name": name, 
        "attributes": attributes, # 这里是属性字典
        "mtime": current_time,     # 注入时间戳，解决 fetch 的报错
        "create_time": current_time,
        "group_id": str(group_id),
        "global": True
    }
    
    # 默认保存到全域档案库，所有群共用同一份卡。
    _write_character_file(get_vault_character_file(user_id, chara_id), data)
    
    # 更新绑定
    set_binding_info(user_id, group_id, chara_id, global_binding=True)
    return chara_id

def delete_character(group_id: str, user_id: str, name: str):
    """
    删除当前群组下指定名字的人物卡，并清理绑定关系。
    """
    characters = get_all_characters(group_id, user_id)
    
    if name not in characters:
        return False, None

    return delete_character_by_id(group_id, user_id, characters[name])

def _binding_chara_id(binding):
    if isinstance(binding, dict):
        return binding.get("id")
    return binding

def _cleanup_character_bindings(user_id: str, chara_id: str, group_id: str = None, include_local: bool = True):
    bindings = get_binding_info(user_id)
    changed = False

    for bound_group_id, binding in list(bindings.items()):
        if group_id is not None and str(bound_group_id) != str(group_id):
            continue
        if _binding_chara_id(binding) == chara_id and (include_local or not (isinstance(binding, dict) and binding.get("local"))):
            bindings.pop(bound_group_id, None)
            changed = True

    if changed:
        path = os.path.join(get_user_base_folder(user_id), "bindings.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(bindings, f, indent=4)

def delete_character_by_id(group_id: str, user_id: str, chara_id: str):
    """
    按 ID 删除人物卡。全局卡删除 vault 档案；本地隔离卡删除当前群副本。
    同时清理所有指向该角色的绑定，避免后续读到已删除 ID。
    """
    paths = []
    local_path = get_character_file(group_id, user_id, chara_id)
    vault_path = get_vault_character_file(user_id, chara_id)
    local_only = is_local_binding(group_id, user_id, chara_id)

    if local_only and os.path.exists(local_path):
        paths.append(local_path)
    else:
        if os.path.exists(vault_path):
            paths.append(vault_path)
        if os.path.exists(DATA_FOLDER):
            for candidate_group_id in os.listdir(DATA_FOLDER):
                if candidate_group_id == "user_metadata":
                    continue
                candidate_path = os.path.join(DATA_FOLDER, candidate_group_id, str(user_id), f"{chara_id}.json")
                if os.path.exists(candidate_path) and candidate_path not in paths:
                    paths.append(candidate_path)

    if not paths:
        return False, None

    try:
        for path in paths:
            os.remove(path)
    except Exception:
        return False, None

    if local_only:
        _cleanup_character_bindings(user_id, chara_id, group_id=group_id)
    else:
        _cleanup_character_bindings(user_id, chara_id)
    return True, chara_id

def set_nickname(group_id: str, user_id: str, chara_id: str, nickname: str):
    """
    为指定群组下的某张卡设置昵称。
    """
    chara = load_character(group_id, user_id, chara_id)
    if chara:
        chara["nickname"] = nickname
        save_character(group_id, user_id, chara_id, chara)
        return True
    return False

def grow_up(group_id: str, user_id: str, skill_name: str, skill_value: int = None):
    """
    技能成长判定（COC规则）- 适配物理隔离方案
    """
    update_skill_value = False
    chara_id = get_current_character_id(group_id, user_id)
    
    if not chara_id and skill_value is None:
        return get_output("pc.grow.no_active")

    # 如果未提供 skill_value，则从当前绑定的卡读取
    if skill_value is None:
        skill_value = get_skill_value(group_id, user_id, skill_name)
        update_skill_value = True
    
    if chara_id :
        chara_data = load_character(group_id, user_id, chara_id)

    # 校验 skill_value 是否为整数
    try:
        skill_value = int(skill_value)
    except (ValueError, TypeError):
        return get_output("pc.show.attr_missing", skill_name=skill_name)

    # 掷骰 (1D100)
    roll_result = random.randint(1, 100)

    # 成长判定：roll > skill_value 或 roll > 95 成长
    if roll_result > skill_value or roll_result > 95:
        en_value = random.randint(1, 10)
        new_value = skill_value + en_value
        result = get_output("pc.grow.success", skill_name=skill_name, skill_value=skill_value, en_value=en_value, new_value=new_value)
        
        if update_skill_value and chara_data:
            if "attributes" not in chara_data: chara_data["attributes"] = {}
            chara_data["attributes"][skill_name] = new_value
            save_character(group_id, user_id, chara_id, chara_data)
    else:
        result = get_output("pc.grow.failure", skill_name=skill_name)

    return get_output(
        "pc.grow.boost_result",
        skill_name=skill_name,
        roll_result=roll_result,
        skill_value=skill_value,
        result=result
    )
