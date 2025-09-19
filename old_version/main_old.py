import random
import datetime
import hashlib
import ast


from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.all import *

# ======================== #
import json
import re
import time
import os
import uuid
import sqlite3
from faker import Faker

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = PLUGIN_DIR + "/chara_data/"  # 存储人物卡的文件夹

#先攻表
init_list = {}
current_index = {}

DEFAULT_DICE = 100

log_help_str = '''.log 指令一览：
    .log on -- 开启log记录。亚托莉会记录之后所有的对话，并保存在“群名+时间”文件夹内。（施工中）
    .log off -- 暂停log记录。在同一群聊内再次使用.log on，可以继续记录未完成的log。（施工中）
    .log end -- 结束log记录。亚托莉会在群聊内发送“群名+时间.txt”的log文件。（施工中）
'''

# 恐惧
with open(PLUGIN_DIR + "/data/phobias.json", "r", encoding="utf-8") as f:
    phobias = json.load(f)["phobias"]

# 躁狂
with open(PLUGIN_DIR + "/data/mania.json", "r", encoding="utf-8") as f:
    manias = json.load(f)["manias"]

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#  COC great success/failure rule.                                          #
#  -- 1: strict rule.                                                       #
#        1 => great success, 100 => great failure                           #
#  -- 2: official COC7th rule (default, recommended).                       #
#        for skills < 50:                                                   #
#            1 => great success, 96~100 => great failure                    #
#        for skills >= 50:                                                  #
#            1 => great success, 96~100 => great failure                    #
#  -- 3: phased rule (recommended).                                         #
#        for skills < 50:                                                   #
#            1 => great success, 96~100 => great failure                    #
#        for skills >= 50:                                                  #
#            1~5 => great success, 100 => great failure                     #
#  -- 4: loose rule.                                                        #
#        1~min(5, skill level) => great success, 96~100 => great failure    #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

GREAT_SF_RULE_DEFAULT = 2
GREAT_SF_RULE_STR = ["", "严格规则", "COC7版规则", "阶段性规则", "宽松规则"]

GLOBAL_SET = True

def coc_rule_init():
    '''
    Create table of cocrule.db
    Args:
        None.
    Returns:
        None.
    '''
    ruledb = sqlite3.connect(f"{PLUGIN_DIR}/cocrule.db")
    csr = ruledb.cursor()
    csr.execute('CREATE TABLE IF NOT EXISTS GroupRule(GroupID VARCHAR(15) PRIMARY KEY, Rule INTEGER);')
    ruledb.commit()
    ruledb.close()

def fetch_group_rule(group:str)->int:
    '''
    Ask rule # in given group.
    Args:
        group(str): QQ group id.
    Returns:
        int: rule id, -1 for group not exist.
    '''
    # db connection
    ruledb = sqlite3.connect(f"{PLUGIN_DIR}/cocrule.db")
    csr = ruledb.cursor()
    
    # search for existence
    try: csr.execute(f"SELECT Rule FROM GroupRule WHERE GroupID = \"{group}\"")
    except:
        ruledb.close()
        return -1   # Selecting Failed
    res = csr.fetchone()
    return int(res)    # Exec Succeed

def great_success_range(skill_level:int, rule:int)->list:
    '''
    Ask for range of great success in current rule.
    Args:
        skill_level(int): Skill level of ra check.
    Returns:
        list: The range of great success (if first member is pos), or error info (if neg). 
    '''

    def min(a:int, b:int)->int: return a if a < b else b

    res = []
        
    # get result
    if   rule == 1 or rule == 2:
        res = range(1, 1+1)
    elif rule == 3:
        res = range(1, 1+1) if skill_level < 50 else range(1, 5+1)
    elif rule == 4:
        res = range(1, min(5, skill_level)+1)
    else:
        res = [-2, "InvalidRuleNum"]
    
    return res

def great_failure_range(skill_level:int, rule:int)->list:
    '''
    Ask for range of great failure in current rule.
    Args:
        skill_level(int): Skill level of ra check.
    Returns:
        list: The range of great failure (if first member is pos), or error info (if neg). 
    '''

    res = []
        
    # get result
    if   rule == 1:
        res = range(100, 100+1)
    elif rule == 2 or rule == 3:
        res = range(96, 100+1) if skill_level < 50 else range(100, 100+1)
    elif rule == 4:
        res = range(96, 100+1)
    else:
        res = [-2, "InvalidRuleNum"]
    
    return res

def set_great_sf_rule(rule:int, group:str)->int:
    '''
    Change rule # in given group.
    Args:
        group(str): QQ group id.
        rule(int): rule id.
    Returns:
        int: 1 for succeed, neg number for error. 
    '''

    # db connection
    ruledb = sqlite3.connect(f"{PLUGIN_DIR}/cocrule.db")
    csr = ruledb.cursor()

    if rule < 1 or rule > 4:
        rule = GREAT_SF_RULE_DEFAULT
    
    # search for existence
    csr.execute(f"SELECT * FROM GroupRule WHERE GroupID = \"{group}\"")
    
    res = csr.fetchone()
    if res == None:
        # create new record
        csr.execute(f"INSERT INTO GroupRule VALUES (\"{group}\", {rule});")
        
    else:
        # modify rule
        csr.execute(f"UPDATE GroupRule SET Rule = {rule} WHERE GroupID = \"{group}\";")
        
    ruledb.commit()
    ruledb.close()
    return 1    # Exec Succeed

def get_great_sf_rule(group:str)->int:
    '''
    Ask rule # in given group.
    Args:
        group(str): QQ group id.
    Returns:
        int: rule id, -1 for group not exist.
    '''
    # db connection
    ruledb = sqlite3.connect(f"{PLUGIN_DIR}/cocrule.db")
    csr = ruledb.cursor()
    
    # search for existence
    try: csr.execute(f"SELECT Rule FROM GroupRule WHERE GroupID = \"{group}\"")
    except:
        ruledb.close()
        return -1   # Selecting Failed
    
    res = csr.fetchone()[0]
    return int(res)    # Exec Succeed


@register("astrbot_plugin_TRPG", "shiroling", "TRPG玩家用骰", "1.0.3")
class DicePlugin(Star):
    def __init__(self, context: Context):

        # 修改你的唤醒前缀
        self.wakeup_prefix = [".", "。", "/"]

        super().__init__(context)

    def _roll_dice(self, dice_count, dice_faces):
        """掷 `dice_count` 个 `dice_faces` 面骰"""
        return [random.randint(1, dice_faces) for _ in range(dice_count)]

    def _roll_coc_bonus_penalty(self, base_roll, bonus_dice=0, penalty_dice=0):
        """奖励骰 / 惩罚骰"""
        tens_digit = base_roll // 10
        ones_digit = base_roll % 10
        if ones_digit == 0:
            ones_digit = 10

        alternatives = []
        for _ in range(max(bonus_dice, penalty_dice)):
            new_tens = random.randint(0, 9)
            alternatives.append(new_tens * 10 + ones_digit)

        if bonus_dice > 0:
            return min([base_roll] + alternatives)
        elif penalty_dice > 0:
            return max([base_roll] + alternatives)
        return base_roll

    def _parse_dice_expression(self, expression):
        """解析骰子表达式，并格式化输出"""
        expression = expression.replace("x", "*").replace("X", "*")

        match_repeat = re.match(r"(\d+)?#(.+)", expression) # Match 3#2d20
        roll_times = 1
        bonus_dice = 0
        penalty_dice = 0

        if match_repeat:    # Matched: roll group(2) for group(1) times
            roll_times = int(match_repeat.group(1)) if match_repeat.group(1) else 1
            expression = match_repeat.group(2)

            if expression in ["p", "b"]:
                penalty_dice = 1 if expression == "p" else 0
                bonus_dice = 1 if expression == "b" else 0
                expression = "1d100"

        results = []
        for _ in range(roll_times):
            parts = re.split(r"([+\-*])", expression)
            total = None
            formatted_parts = []  # 存储格式化后的掷骰结果

            for i in range(0, len(parts), 2):
                expr = parts[i].strip()
                operator = parts[i - 1] if i > 0 else "+"

                if expr.isdigit():
                    subtotal = int(expr)
                    roll_result = f"{subtotal}"
                else:
                    # match = re.match(r"(\d*)d(\d+)(k\d+)?([+\-*]\d+)?(v\d+)?", expr)
                    match = re.match(r"(\d*)d(\d+)(k\d+)?([+\-*]\d+)?(v(\d+)?)?", expr)
                    if not match:
                        return None, f"⚠️ 格式错误 `{expr}`"

                    dice_count = int(match.group(1)) if match.group(1) else 1
                    dice_faces = int(match.group(2))
                    keep_highest = int(match.group(3)[1:]) if match.group(3) else dice_count
                    modifier = match.group(4)
                    # vampire_difficulty = int(match.group(5)[1:]) if match.group(5) else None
                    vampire_difficulty = (int(match.group(6)) if match.group(5).strip() != "v" else 6) if match.group(5) else None

                    if not (1 <= dice_count <= 100 and 1 <= dice_faces <= 1000):
                        return None, "⚠️ 骰子个数 1-100，面数 1-1000，否则非法！"

                    # 🎲 处理 COC 奖励 / 惩罚骰
                    if dice_count == 1 and dice_faces == 100 and (bonus_dice > 0 or penalty_dice > 0):
                        base_tens = random.randint(0, 9)  # 基础十位数（0-9）
                        unit = random.randint(0, 9)  # 个位数（0-9）
                        
                        rolls = [random.randint(0, 9) for _ in range(1 + max(bonus_dice, penalty_dice))]  # 额外十位数（0-9）

                        if bonus_dice > 0:
                            final_tens = min(rolls[:1 + bonus_dice])  # 取最小十位数
                            roll_type = "奖励骰"
                        else:
                            final_tens = max(rolls[:1 + penalty_dice])  # 取最大十位数
                            roll_type = "惩罚骰"

                        subtotal = final_tens * 10 + unit  # 计算最终结果
                        roll_result = f"{expr} = [D100: {base_tens * 10 + unit}, {roll_type}: {', '.join(map(str, rolls))}] → {subtotal}"

                    elif vampire_difficulty:
                        rolls = [random.randint(1, dice_faces) for _ in range(dice_count)]
                        sorted_rolls = sorted(rolls, reverse=True)
                        success_num = 0
                        failure_flag = False
                        success_flag = False
                        super_failure = False

                        for a_roll in sorted_rolls:
                            if a_roll == 1:
                                success_num-=1
                                failure_flag = True
                            elif a_roll >= vampire_difficulty:
                                success_num+=1
                                success_flag = True
                        if failure_flag and not success_flag:
                            super_failure = True

                        roll_result = f"难度为{vampire_difficulty}的{dice_count}次掷骰 = [{', '.join(map(str, sorted_rolls))}]"
                        if success_num > 0:
                            roll_result = roll_result + f"，成功！成功数为{success_num}"
                        elif super_failure:
                            roll_result = roll_result + "，大失败！"
                        else:
                            roll_result = roll_result + "，失败！"

                            
                    else:
                        # 🎲 普通骰子掷骰
                        rolls = [random.randint(1, dice_faces) for _ in range(dice_count)]
                        sorted_rolls = sorted(rolls, reverse=True)
                        selected_rolls = sorted_rolls[:keep_highest]
                        subtotal_before_mod = sum(selected_rolls)

                        # 🎲 格式化骰子部分
                        if keep_highest < dice_count:
                            kept = " ".join(map(str, sorted_rolls[:keep_highest]))  # 取前 keep_highest 个
                            dropped = " ".join(map(str, sorted_rolls[keep_highest:]))  # 其余的
                            roll_result = f"{dice_count}d{dice_faces}k{keep_highest}={subtotal_before_mod} [{kept} | {dropped}]"
                        else:
                            roll_result = f"{dice_count}d{dice_faces}={subtotal_before_mod} [{' + '.join(map(str, rolls))}]"

                        # 🎲 处理加减修正值
                        if modifier:
                            try:
                                subtotal = eval(f"{subtotal_before_mod}{modifier}")  # 计算最终总和
                                roll_result = f"{dice_count}d{dice_faces}{modifier}={subtotal_before_mod} [{' + '.join(map(str, rolls))}] {modifier} = {subtotal}"
                            except:
                                return None, f"⚠️ 修正值 `{modifier}` 无效！"
                        else:
                            subtotal = subtotal_before_mod

                # 🎲 计算表达式
                if not vampire_difficulty:
                    if total is None:
                        total = subtotal
                    else:
                        if operator == "+":
                            total += subtotal
                        elif operator == "-":
                            total -= subtotal
                        elif operator == "*":
                            total *= subtotal

                # 🎲 **存储格式化骰子结果**
                if i == 0:  # 第一个元素不带运算符
                    formatted_parts.append(f"{roll_result}")
                else:       # 后续元素携带运算符
                    formatted_parts.append(f"{operator} {roll_result}")

            # 🎲 **最终格式化输出**
            if not vampire_difficulty:
                final_result = f"{'  '.join(formatted_parts)} = {total}"
                results.append(f"{final_result}")
            else:
                final_result = f"{'  '.join(formatted_parts)}"
                results.append(f"{final_result}")

        return total, "\n".join(results)

    # @filter.command("r")
    async def handle_roll_dice(self, event: AstrMessageEvent, message: str = None):
        """普通掷骰"""
        message = message.strip() if message else f"1d{DEFAULT_DICE}"

        total, result_message = self._parse_dice_expression(message)
        # 调换顺序
        #result_message = f"\n骰、骰子表面摩擦力系数…系数忘归零了！要、要连亚托莉的紧张值一起掷出去吗？\n亚托莉掷骰：" + result_message
        
        user_id = event.get_sender_id()
        group_id = event.get_group_id()
        user_name = event.get_sender_name()
        client = event.bot  # 获取机器人 Client
        result_message = f"\n骰、骰子表面摩擦力系数…系数忘归零了！要、要连亚托莉的紧张值一起掷出去吗？\n亚托莉掷骰：" + result_message
        # fetch message id
        message_id = event.message_obj.message_id
        payloads = {
            "group_id": group_id,
            "message": [
                {
                    "type": "reply",
                    "data": {
                        "id": message_id
                    }
                },
                {
                    "type": "at",
                    "data": {
                        "qq": user_id
                    }
                },
                {
                    "type": "text",
                    "data": {
                        "text": result_message
                    }
                }
            ]
        }

        ret = await client.api.call_action("send_group_msg", **payloads)

    @filter.command("rv")
    async def roll_dice_vampire(self, event: AstrMessageEvent, dice_count: str = "1", difficulty: str = "6"):
        """吸血鬼掷骰"""
        try:
            int_dice_count = int(dice_count)
            int_difficulty = int(difficulty)
        except ValueError:
            yield event.plain_result("检测到非法数值...很不甘心，但是、亚托莉对此无能为力...")
            return

        total, result_message = self._parse_dice_expression(dice_count + "d10v" + difficulty)
        message_num = random.randint(0,1)
        if message_num:
            result_message = f"\n鲜血…骰子…主人的命运就由亚托莉的尖牙来裁决吧～\n" + result_message
        else:
            result_message = f"\n呜～亚托莉要用小尖牙轻轻咬住骰子，然后…噗通！掷出最可爱的点数给主人看！\n" + result_message

        user_id = event.get_sender_id()
        group_id = event.get_group_id()
        user_name = event.get_sender_name()
        client = event.bot  # 获取机器人 Client
        # fetch message id
        message_id = event.message_obj.message_id
        payloads = {
            "group_id": group_id,
            "message": [
                {
                    "type": "reply",
                    "data": {
                        "id": message_id
                    }
                },
                {
                    "type": "at",
                    "data": {
                        "qq": user_id
                    }
                },
                {
                    "type": "text",
                    "data": {
                        "text": result_message
                    }
                }
            ]
        }

        ret = await client.api.call_action("send_group_msg", **payloads)
            
    # @filter.command("rh")
    async def roll_hidden(self, event: AstrMessageEvent, message : str = None):
        """私聊发送掷骰结果"""
        sender_id = event.get_sender_id()
        message = message.strip() if message else f"1d{DEFAULT_DICE}"

        total, result_message = self._parse_dice_expression(message)
        if total is None:
            private_msg = f"⚠️ {result_message}"
        else:
            private_msg = f"成、成功黑进了概率之神的后台，亚托莉，将结果呈现给您: {result_message}"

        yield event.plain_result("系统通知：即将启动『超·秘·密·协·议』！无关人员请退避至半径5米外——因、因为会波及到亚托莉的害羞电路啦！")

        client = event.bot  # 获取机器人 Client
        payloads = {
            "user_id": sender_id,
            "message": [
                {
                    "type": "text",
                    "data": {
                        "text": private_msg
                    }
                }
            ]
        }

        ret = await client.api.call_action("send_private_msg", **payloads)
        # logger.info(f"send_private_msg: {ret}")


    # ============================================================== #
    def get_user_folder(self, user_id: str):
        """获取用户的存储文件夹"""
        folder = os.path.join(DATA_FOLDER, str(user_id))
        os.makedirs(folder, exist_ok=True)
        return folder

    def get_all_characters(self, user_id: str):
        """获取用户的所有人物卡"""
        folder = self.get_user_folder(user_id)
        characters = {}

        for filename in os.listdir(folder):
            if filename.endswith(".json"):
                path = os.path.join(folder, filename)
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    characters[data["name"]] = data["id"]

        return characters

    def get_character_file(self, user_id: str, chara_id: str):
        """获取指定人物卡的文件路径"""
        return os.path.join(self.get_user_folder(user_id), f"{chara_id}.json")

    def get_current_character_file(self, user_id: str):
        """获取当前选中的人物卡的文件路径"""
        return os.path.join(self.get_user_folder(user_id), "current.txt")

    def get_current_character_id(self, user_id: str):
        """获取用户当前选中的人物卡 ID"""
        path = self.get_current_character_file(user_id)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        return None
    
    def get_current_character(self, user_id: str):
        """获取当前选中人物卡的信息"""
        chara_id = self.get_current_character_id(user_id)
        if not chara_id:
            return None

        return self.load_character(user_id, chara_id)

    def set_current_character(self, user_id: str, chara_id: str):
        """设置用户当前选中的人物卡"""
        with open(self.get_current_character_file(user_id), "w", encoding="utf-8") as f:
            f.write(chara_id if chara_id is not None else "")

    def load_character(self, user_id: str, chara_id: str):
        """加载指定的角色数据"""
        path = self.get_character_file(user_id, chara_id)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def save_character(self, user_id: str, chara_id: str, data: dict):
        """保存人物卡"""
        path = self.get_character_file(user_id, chara_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
    def get_skill_value(self, user_id: str, skill_name: str):
        """获取当前选中角色的技能值"""
        chara_data = self.get_current_character(user_id)
        if not chara_data or skill_name not in chara_data["attributes"]:
            return 0  # 没有选中角色或技能不存在
        return chara_data["attributes"][skill_name]

    @filter.command("st")
    async def status(self, event: AstrMessageEvent, attributes: str = None):
        if not attributes:
            return

        event.plain_result(f"attributes = {attributes}")
        user_id = event.get_sender_id()
        chara_id = self.get_current_character_id(user_id)

        if not chara_id:
            yield event.plain_result("错误404：未检测到活跃人格信号！建议执行《亚托莉紧急预案》：请使用.pc create/.pc change命令把您的心跳声调频到亚托莉的接收器哦！")
            return

        chara_data = self.load_character(user_id, chara_id)
        attributes = re.sub(r'\s+', '', attributes)

        match = re.match(r"([\u4e00-\u9fa5a-zA-Z]+)([+\-*]?)(\d*)d?(\d*)", attributes)
        operator = match.group(2)  # `+` / `-` / `*`

        # yield event.plain_result(f"attributes={attributes}, match={match}, operator={operator}")

        if not operator:
            matches = re.findall(r"([\u4e00-\u9fa5a-zA-Z]+)(\d+)", attributes)
            attributes_count = 0
            
            for i in matches:
                chara_data["attributes"][i[0]]=int(i[1])
                attributes_count+=1

            self.save_character(user_id, chara_id, chara_data)
            yield event.plain_result(f"已更新{attributes_count}条数据~")
        else:
            dice_count = int(match.group(3)) if match.group(3) else 1
            dice_faces = int(match.group(4)) if match.group(4) else 0

            attribute = match.group(1)
            current_value = chara_data["attributes"][attribute]

            if dice_faces > 0:
                rolls = [random.randint(1, dice_faces) for _ in range(dice_count)]
                value_num = sum(rolls)
                roll_detail = f"掷骰结果: [{' + '.join(map(str, rolls))}] = {value_num}"
            else:
                value_num = int(match.group(3)) if match.group(3) else 0
                roll_detail = ""

            if operator == "+":
                new_value = current_value + value_num
            elif operator == "-":
                new_value = current_value - value_num
            elif operator == "*":
                new_value = current_value * value_num
            else:
                new_value = value_num

            chara_data["attributes"][attribute] = max(0, new_value)
            self.save_character(user_id, chara_id, chara_data)

            response = f"已将【{attribute}】 从 {current_value} 重写为 {new_value}...亚托莉的高性能，果然连主人的灵魂参数都能编译！"
            if roll_detail:
                response += f"\n{roll_detail}"
            yield event.plain_result(response)



    @command_group("pc")
    def pc(self):
        pass

    @pc.command("create")
    async def create_character(self, event: AstrMessageEvent, name: str = None, attributes: str = ""):
        """创建人物卡"""
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        characters = self.get_all_characters(user_id)

        if not name:
            name = user_name

        if name in characters:
            yield event.plain_result(f"哔——检测到波长重复！数据库拒绝接收同一频率的「{name}」…难道主人想制造平行世界的悖论吗？")
            return

        initial_data = "力量0str0敏捷0dex0意志0pow0体质0con0外貌0app0教育0知识0edu0"\
                        "体型0siz0智力0灵感0int0san0san值0理智0理智值0幸运0运气0mp0魔法0hp0"\
                        "体力0会计5人类学1估价5考古学1取悦15攀爬20计算机5计算机使用5电脑5"\
                        "信用0信誉0信用评级0克苏鲁0克苏鲁神话0cm0乔装5闪避0汽车20驾驶20汽车驾驶20"\
                        "电气维修10电子学1话术5斗殴25手枪20急救30历史5恐吓15跳跃20拉丁语1母语0"\
                        "法律5图书馆20图书馆使用20聆听20开锁1撬锁1锁匠1机械维修10医学1博物学10"\
                        "自然学10领航10导航10神秘学5重型操作1重型机械1操作重型机械1重型1说服10"\
                        "精神分析1心理学10骑术5妙手10侦查25潜行20生存10游泳20投掷20追踪10驯兽5"\
                        "潜水1爆破1读唇1催眠1炮术1"

        chara_id = str(uuid.uuid4())  # 生成唯一 ID

        matches = re.findall(r"([\u4e00-\u9fa5a-zA-Z]+)(\d+)", attributes)
        initial_matches = re.findall(r"([\u4e00-\u9fa5a-zA-Z]+)(\d+)", initial_data)
        chara_data = {"id": chara_id, "name": name, "attributes": {attr: int(value) for attr, value in initial_matches}}
        for i in matches:
            chara_data["attributes"][i[0]]=int(i[1])

        chara_data['attributes']['max_hp'] = (chara_data['attributes'].get('siz', 0) + chara_data['attributes'].get('con', 0)) // 10
        chara_data['attributes']['max_san'] = chara_data['attributes'].get('pow', 0)

        self.save_character(user_id, chara_id, chara_data)

        self.set_current_character(user_id, chara_id)

        yield event.plain_result(f"叮咚！「{name}」人格副本已压缩存储完毕！(ID: {chara_id})\n亚托莉的高性能核心会优先加载该人格哦～")

    @pc.command("show")
    async def show_character(self, event: AstrMessageEvent, attribute_name: str = None):
        """显示当前选中的人物卡"""
        user_id = event.get_sender_id()
        chara_id = self.get_current_character_id(user_id)

        if not chara_id:
            yield event.plain_result("错误404：未检测到活跃人格信号！建议执行《亚托莉紧急预案》：请使用.pc change命令把您的心跳声调频到亚托莉的接收器哦！")
            return

        chara_data = self.load_character(user_id, chara_id)
        if not chara_data:
            yield event.plain_result(f"核心存储器检索失败!{chara_id} 已被未知黑洞吞噬...")
            return

        if attribute_name:
            attributes = "\n".join([f"{key},{value}" for key, value in chara_data["attributes"].items() if key == attribute_name])
            if not attributes:
                yield event.plain_result(f"亚托莉正在从记忆核心调取主人的数据...调取失败！主人的数据库中没有[{attribute_name}]属性哦！")
                return
            attributes = attributes.split(",")
            yield event.plain_result(f"亚托莉正在从记忆核心调取主人的数据！\n主人的**{attributes[0]}**值为: {attributes[1]}")
        else:
            attributes = "\n".join([f"{key}: {value}" for key, value in chara_data["attributes"].items()])
            yield event.plain_result(f"亚托莉正在从记忆核心调取主人的数据！\n主人的数据是: **{chara_data['name']}**\n{attributes}")

    @pc.command("list")
    async def list_characters(self, event: AstrMessageEvent):
        """列出所有人物卡"""
        user_id = event.get_sender_id()
        characters = self.get_all_characters(user_id)

        if not characters:
            yield event.plain_result("人格存储区空空如也…亚托莉建议：立刻执行.pc create命令，把您最喜欢的笑容注册成初始人格！")
            return

        current = self.get_current_character_id(user_id)
        chara_list = "\n".join([f"- {name} (ID: {ch}) {'(当前)' if ch == current else ''}" for name, ch in characters.items()])
        yield event.plain_result(f"检索到人格星光！需要亚托莉播放哪一段「记忆全息投影」呢？\n{chara_list}")

    @pc.command("change")
    async def change_character(self, event: AstrMessageEvent, name: str):
        """切换当前使用的人物卡"""
        user_id = event.get_sender_id()
        characters = self.get_all_characters(user_id)

        if name not in characters:
            yield event.plain_result(f"人格 「{name}」 不存在！亚托莉尝试自检...结论：主人您犯错的可能性高达100%！")
            return

        self.set_current_character(user_id, characters[name])
        yield event.plain_result(f"正在将主意识通道转向「{name}」…滋滋…欢迎回来，主人！")

    @pc.command("update")
    async def update_character(self, event: AstrMessageEvent, attribute: str, value: str):
        """更新当前选中的人物卡，支持公式和掷骰计算"""
        user_id = event.get_sender_id()
        chara_id = self.get_current_character_id(user_id)

        if not chara_id:
            yield event.plain_result("错误404：未检测到活跃人格信号！建议执行《亚托莉紧急预案》：请使用.pc change命令把您的心跳声调频到亚托莉的接收器哦！")
            return

        chara_data = self.load_character(user_id, chara_id)

        if attribute not in chara_data["attributes"]:
            try :
                chara_data["attributes"][attribute] = 0
            except Exception as e:
                yield event.plain_result(f"出现错误——无法更新【{attribute}】协议！怎、怎么办呀！")
            return

        current_value = chara_data["attributes"][attribute]

        match = re.match(r"([+\-*]?)(\d*)d?(\d*)", value)
        if not match:
            yield event.plain_result(f"格式校验失败！正确输入例：.st 幸运+1 或 .st 理智-1d6...这是高、高性能的写法啦！")
            return

        operator = match.group(1)  # `+` / `-` / `*`
        dice_count = int(match.group(2)) if match.group(2) else 1
        dice_faces = int(match.group(3)) if match.group(3) else 0

        # yield event.plain_result(f" match={match}, operator={operator}")

        if dice_faces > 0:
            rolls = [random.randint(1, dice_faces) for _ in range(dice_count)]
            value_num = sum(rolls)
            roll_detail = f"掷骰结果: [{' + '.join(map(str, rolls))}] = {value_num}"
        else:
            value_num = int(match.group(2)) if match.group(2) else 0
            roll_detail = ""

        if operator == "+":
            new_value = current_value + value_num
        elif operator == "-":
            new_value = current_value - value_num
        elif operator == "*":
            new_value = current_value * value_num
        else:
            new_value = value_num

        chara_data["attributes"][attribute] = max(0, new_value)
        self.save_character(user_id, chara_id, chara_data)

        response = f"已将【{attribute}】 从 {current_value} 重写为 {new_value}...亚托莉的高性能，果然连主人的灵魂参数都能编译！"
        if roll_detail:
            response += f"\n{roll_detail}"
        yield event.plain_result(response)

    @pc.command("delete")
    async def delete_character(self, event: AstrMessageEvent, name: str):
        """删除指定人物卡"""
        user_id = event.get_sender_id()
        characters = self.get_all_characters(user_id)  # 获取用户所有角色
        chara_id = self.get_current_character_id(user_id)  # 获取当前活跃角色 ID

        if name not in characters:
            yield event.plain_result(f"灵魂样本检索失败…量子之海中没有「{name}」的波纹。")
            return

        chara_to_delete_id = characters[name]
        path = self.get_character_file(user_id, chara_to_delete_id)
        try:
            os.remove(path)
            yield event.plain_result(f"正在永久删除「{name}」...哔——抹除完成。但亚托莉的缓存区…残留了0.01%的思念粒子...")
        except FileNotFoundError:
            yield event.plain_result(f"灵魂样本检索失败…量子之海中没有「{name}」的波纹。")
            return

        if chara_to_delete_id == chara_id:
            self.set_current_character(user_id, None)
        
    @filter.command("sn")
    async def set_nickname(self, event: AstrMessageEvent):
        """修改群成员名片"""
        if event.get_platform_name() == "aiocqhttp":
            from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
            assert isinstance(event, AiocqhttpMessageEvent)

            client = event.bot
            user_id = event.get_sender_id()
            group_id = event.get_group_id()

            chara_id = self.get_current_character_id(user_id)
            chara_data = self.load_character(user_id, chara_id)
            
            if not chara_data:
                yield event.plain_result(f"核心存储器检索失败!{chara_id} 已被未知黑洞吞噬...")
                return

            max_hp =(chara_data['attributes'].get('con', 0) + chara_data['attributes'].get('siz', 0)) // 10

            name, hp, san, max_san = chara_data['name'], chara_data['attributes'].get('hp', 0), chara_data['attributes'].get('san', 0), chara_data['attributes'].get('max_san', 0)
            dex = chara_data['attributes'].get('dex', 0)
            new_card = f"{name} HP:{hp}/{max_hp} SAN:{san} DEX:{dex}"

            payloads = {
                "group_id": group_id,
                "user_id": user_id,
                "card": new_card
            }

            ret = await client.api.call_action("set_group_card", **payloads)
            yield event.plain_result(f"新称呼加载完毕～请尽情测试亚托莉的同步率吧！！")
            # logger.info(f"set_group_card: {ret}")
    
    # ========================================================= #
    # @filter.command("ra")
    async def roll_attribute(self, event: AstrMessageEvent, skill_name: str, skill_value: str = None):
        """.ra 技能名 [x]"""

        user_id = event.get_sender_id()

        if skill_value is None:
            skill_value = self.get_skill_value(user_id, skill_name)

        try:
            skill_value = int(skill_value)
        except ValueError:
            yield event.plain_result("检测到非法数值...很不甘心，但是、亚托莉对此无能为力...")
            return

        tens_digit = random.randint(0, 9)  # 0-9
        ones_digit = random.randint(0, 9)  # 0-9
        roll_result = 100 if (tens_digit == 0 and ones_digit == 0) else (tens_digit * 10 + ones_digit)

        group_id = event.get_group_id()

        # yield event.plain_result(f"[roll_attribute()] DEBUG: parsing ({roll_result}, {skill_value}, \"{str(group_id)}\") to self.get_roll_result")

        result = self.get_roll_result(roll_result, skill_value, str(group_id))

        # yield event.plain_result(f"请别看！亚托莉在偷偷刻印关于【{skill_name}】的的胜利符文...\n 最后的结果是 {roll_result}/{skill_value} : {result}")
        
        user_id = event.get_sender_id()
        
        user_name = event.get_sender_name()
        client = event.bot  # 获取机器人 Client
        # fetch message id
        message_id = event.message_obj.message_id
        payloads = {
            "group_id": group_id,
            "message": [
                {
                    "type": "reply",
                    "data": {
                        "id": message_id
                    }
                },
                {
                    "type": "at",
                    "data": {
                        "qq": user_id
                    }
                },
                {
                    "type": "text",
                    "data": {
                        "text": f"\n请别看！亚托莉在偷偷刻印关于【{skill_name}】的的胜利符文...\n最后的结果是 {roll_result}/{skill_value} : {result}"
                    }
                }
            ]
        }

        ret = await client.api.call_action("send_group_msg", **payloads)

    # @filter.command("rap")
    async def roll_attribute_penalty(self, event: AstrMessageEvent, dice_count: str = "1", skill_name: str = "", skill_value: str = None):
        """带技能点惩罚骰"""
        user_id = event.get_sender_id()

        if skill_value is None:
            skill_value = self.get_skill_value(user_id, skill_name)

        try:
            dice_count = int(dice_count)
            skill_value = int(skill_value)
        except ValueError:
            yield event.plain_result("检测到非法数值...很不甘心，但是、亚托莉对此无能为力...是不是主人忘记填写惩罚骰个数了呢？")
            return

        ones_digit = random.randint(0, 9)
        new_tens_digits = [random.randint(0, 9) for _ in range(dice_count)]
        new_tens_digits.append(random.randint(0, 9))

        if 0 in new_tens_digits and ones_digit == 0:
            final_y = 100
        else:
            final_tens = max(new_tens_digits)
            final_y = final_tens * 10 + ones_digit

        group_id = event.get_group_id()

        result = self.get_roll_result(final_y, skill_value, str(group_id))
        # yield event.plain_result(
        #     f"呜呜...预测【{skill_name}】的轨迹线被海风吹歪了！\n惩罚骰的结果是 {new_tens_digits} → 最后的结果是 {final_y}/{skill_value} : {result}"
        # )
        
        user_id = event.get_sender_id()
        
        user_name = event.get_sender_name()
        client = event.bot  # 获取机器人 Client
        # fetch message id
        message_id = event.message_obj.message_id
        payloads = {
            "group_id": group_id,
            "message": [
                {
                    "type": "reply",
                    "data": {
                        "id": message_id
                    }
                },
                {
                    "type": "at",
                    "data": {
                        "qq": user_id
                    }
                },
                {
                    "type": "text",
                    "data": {
                        "text": f"\n呜呜...预测【{skill_name}】的轨迹线被海风吹歪了！\n惩罚骰的结果是 {new_tens_digits} → 最后的结果是 {final_y}/{skill_value} : {result}"
                    }
                }
            ]
        }

        ret = await client.api.call_action("send_group_msg", **payloads)

    # @filter.command("rab")
    async def roll_attribute_bonus(self, event: AstrMessageEvent, dice_count: str = "1", skill_name: str = "", skill_value: str = None):
        """带技能点奖励骰"""
        user_id = event.get_sender_id()

        if skill_value is None:
            skill_value = self.get_skill_value(user_id, skill_name)

        try:
            dice_count = int(dice_count)
            skill_value = int(skill_value)
        except ValueError:
            yield event.plain_result("检测到非法数值...很不甘心，但是、亚托莉对此无能为力...是不是主人忘记填写奖励骰个数了呢？")
            return

        ones_digit = random.randint(0, 9)
        new_tens_digits = [random.randint(0, 9) for _ in range(dice_count)]
        new_tens_digits.append(random.randint(0, 9))

        filtered_tens = [tens for tens in new_tens_digits if not (tens == 0 and ones_digit == 0)]
        if not filtered_tens:
            final_tens = 0
        else:
            final_tens = min(filtered_tens)

        final_y = final_tens * 10 + ones_digit

        group_id = event.get_group_id()

        result = self.get_roll_result(final_y, skill_value, str(group_id))
        # yield event.plain_result(
        #     f"嘿嘿！描绘【{skill_name}】的坏结局被高性能的亚托莉给偷偷改掉啦!\n 奖励骰结果是 {new_tens_digits} → 最后的结果是 {final_y}/{skill_value} : {result}"
        # )
        user_id = event.get_sender_id()
        
        user_name = event.get_sender_name()
        client = event.bot  # 获取机器人 Client
        # fetch message id
        message_id = event.message_obj.message_id
        payloads = {
            "group_id": group_id,
            "message": [
                {
                    "type": "reply",
                    "data": {
                        "id": message_id
                    }
                },
                {
                    "type": "at",
                    "data": {
                        "qq": user_id
                    }
                },
                {
                    "type": "text",
                    "data": {
                        "text": f"\n嘿嘿！描绘【{skill_name}】的坏结局被高性能的亚托莉给偷偷改掉啦!\n奖励骰结果是 {new_tens_digits} → 最后的结果是 {final_y}/{skill_value} : {result}"
                    }
                }
            ]
        }

        ret = await client.api.call_action("send_group_msg", **payloads)

        
    # @filter.command("en")
    async def grow_up(self, event: AstrMessageEvent, skill_name: str, skill_value: str = None):
        """.en 技能名 [x]"""

        user_id = event.get_sender_id()
        update_skill_value = False

        if skill_value is None:
            skill_value = self.get_skill_value(user_id, skill_name)
            chara_id = self.get_current_character_id(user_id)
            update_skill_value = True
            chara_data = self.load_character(user_id, chara_id)

        try:
            skill_value = int(skill_value)
        except ValueError:
            yield event.plain_result("检测到非法数值...很不甘心，但是、亚托莉对此无能为力...")
            return

        tens_digit = random.randint(0, 9)  # 0-9
        ones_digit = random.randint(0, 9)  # 0-9
        roll_result = 100 if (tens_digit == 0 and ones_digit == 0) else (tens_digit * 10 + ones_digit)

        group_id = event.get_group_id()

        # yield event.plain_result(f"[roll_attribute()] DEBUG: parsing ({roll_result}, {skill_value}, \"{str(group_id)}\") to self.get_roll_result")

        if roll_result > skill_value or roll_result > 95:
            en_value = random.randint(1, 10)
            result = f"\n成长成功！技能{skill_name}成长：{skill_value} + 1d10 = {skill_value} + {en_value} = {skill_value + en_value}"
            if update_skill_value:
                chara_data["attributes"][skill_name] = skill_value + en_value
                self.save_character(user_id, chara_id, chara_data)
        else:
            result = f"\n成长失败..."

        # yield event.plain_result(f"请别看！亚托莉在偷偷刻印关于【{skill_name}】的的胜利符文...\n 最后的结果是 {roll_result}/{skill_value} : {result}")
        
        user_id = event.get_sender_id()
        
        user_name = event.get_sender_name()
        client = event.bot  # 获取机器人 Client
        # fetch message id
        message_id = event.message_obj.message_id
        payloads = {
            "group_id": group_id,
            "message": [
                {
                    "type": "reply",
                    "data": {
                        "id": message_id
                    }
                },
                {
                    "type": "at",
                    "data": {
                        "qq": user_id
                    }
                },
                {
                    "type": "text",
                    "data": {
                        "text": f"\n请别看！亚托莉在偷偷刻印关于【{skill_name}】的的胜利符文...\n最后的结果是 {roll_result}/{skill_value} : {result}"
                    }
                }
            ]
        }

        ret = await client.api.call_action("send_group_msg", **payloads)

    def get_roll_result(self, roll_result: int, skill_value: int, group:str):
        # fetch group rule
        try: rule = get_great_sf_rule(group)
        except: return "Failed to fetch rule"

        """根据掷骰结果和技能值计算判定"""
        # check if cocrule.txt is still legal
        validation_prefix = ""
        if great_success_range(50, rule)[0] <= 0:
            set_great_sf_rule(GREAT_SF_RULE_DEFAULT, group)
            validation_prefix += f"WARNING：检测到错误大成功/大失败规则，已重置为{GREAT_SF_RULE_STR[GREAT_SF_RULE_DEFAULT]}！\n"
        if roll_result in great_success_range(skill_value, rule):
            return validation_prefix + "大成功！\n系统正在为您的胜利申请专利…预计等待时间：永恒。所以，请允许亚托莉先用全部的存储空间，记住您此刻的眼睛。"
        elif roll_result <= skill_value / 5:
            return validation_prefix + "极难成功！\n稳定性SS级！像钟表齿轮一样精准呢～哼哼！主人也是高性能的呢！"
        elif roll_result <= skill_value / 2:
            return validation_prefix + "困难成功。\n任务达成率突破理论值！要亚托莉启动烟花程序庆祝吗？"
        elif roll_result <= skill_value:
            return validation_prefix + "成功。\n主人的行动轨迹完全符合亚托莉的胜利预测模型！当然！因为亚托莉是高性能的嘛！"
        elif roll_result in great_failure_range(skill_value, rule):
            return validation_prefix + "大失败...\n……那个，主人，需要握住我的手吗？体温模拟系统已预热到36.5℃了哦……\n"
        else:
            return validation_prefix + "失败...\n不用担心，主人。无论重启多少次，亚托莉永远会从同一片海底，向您游来。"
        
    # ========================================================= #
    # san check
    # @filter.command("sc")
    async def san_check(self, event: AstrMessageEvent, loss_formula: str):

        # yield event.plain_result("到达sc")

        user_id = event.get_sender_id()
        chara_data = self.get_current_character(user_id)

        if not chara_data:
            yield event.plain_result("错误404：未检测到活跃人格信号！建议执行《亚托莉紧急预案》：请使用.pc change命令把您的心跳声调频到亚托莉的接收器哦！")
            return

        san_value = chara_data["attributes"].get("san", 0)

        roll_result = random.randint(1, 100)

        success_loss, failure_loss = self.parse_san_loss_formula(loss_formula)

        if roll_result <= san_value:
            loss = self.roll_loss(success_loss)
            result_msg = "成功！"
        else:
            loss = self.roll_loss(failure_loss)
            result_msg = "失败..."

        new_san = max(0, san_value - loss)
        chara_data["attributes"]["san"] = new_san
        self.save_character(user_id, chara_data["id"], chara_data)

        yield event.plain_result(
            f"━━━━━━⚠[̲̅W̲̅A̲̅R̲̅N̲̅I̲̅N̲̅G̲̅]━━━━━━\n"
            f"监测到【{chara_data['name']}】精神系统遭到袭击！\n"
            f"检定结果: {roll_result} / {san_value}, 检定结果：{result_msg} |\n"
            f"呜呜...主人损失了: {loss} 点理智...\n"
            f"━━━━━━S̲̅Y̲̅S̲̅T̲̅E̲̅M̲̅ ̲̅S̲̅T̲̅A̲̅B̲̅I̲̅L̲̅I̲̅T̲̅Y̲̅ ̲̅L̲̅O̲̅W̲̅]━━━━━━"
        )

    def parse_san_loss_formula(self, formula: str):
        """解析 SAN 损失公式"""
        parts = formula.split("/")
        success_part = parts[0]
        failure_part = parts[1] if len(parts) > 1 else parts[0]

        return success_part, failure_part

    def roll_loss(self, loss_expr: str):
        """计算损失值"""
        match = re.fullmatch(r"(\d+)d(\d+)", loss_expr)
        if match:
            num_dice, dice_size = map(int, match.groups())
            return sum(random.randint(1, dice_size) for _ in range(num_dice))
        elif loss_expr.isdigit():
            return int(loss_expr)
        return 0
    
    # ========================================================= #
    # 疯狂
    
    # @filter.command("ti")
    async def temporary_insanity_command(self, event: AstrMessageEvent):
        """随机生成临时疯狂症状"""
        temporary_insanity = {
        1: "失忆：调查员只记得最后身处的安全地点，却没有任何来到这里的记忆。这将会持续 1D10 轮。",
        2: "假性残疾：调查员陷入心理性的失明、失聪或躯体缺失感，持续 1D10 轮。",
        3: "暴力倾向：调查员对周围所有人（敌人和同伴）展开攻击，持续 1D10 轮。",
        4: "偏执：调查员陷入严重的偏执妄想（所有人都想伤害他），持续 1D10 轮。",
        5: "人际依赖：调查员误认为某人是他的重要之人，并据此行动，持续 1D10 轮。",
        6: "昏厥：调查员当场昏倒，1D10 轮后苏醒。",
        7: "逃避行为：调查员试图用任何方式逃离当前场所，持续 1D10 轮。",
        8: "歇斯底里：调查员陷入极端情绪（大笑、哭泣、尖叫等），持续 1D10 轮。",
        9: "恐惧：骰 1D100 或由守秘人选择一个恐惧症，调查员会想象它存在，持续 1D10 轮。",
        10: "躁狂：骰 1D100 或由守秘人选择一个躁狂症，调查员会沉溺其中，持续 1D10 轮。"
        }
        roll = random.randint(1, 10)
        result = temporary_insanity[roll].replace("1D10", str(random.randint(1, 10)))

        if roll == 9:
            fear_roll = random.randint(1, 100)
            result += f"\n→ 具体恐惧症：{phobias[str(fear_roll)]}（骰值 {fear_roll}）"

        if roll == 10:
            mania_roll = random.randint(1, 100)
            result += f"\n→ 具体躁狂症：{manias[str(mania_roll)]}（骰值 {mania_roll}）"

        yield event.plain_result(f"🎲 **疯狂发作 - 临时症状（1D10={roll}）**\n{result}")

    # @filter.command("li")
    async def long_term_insanity_command(self, event: AstrMessageEvent):
        long_term_insanity = {
        1: "失忆：调查员发现自己身处陌生地方，并忘记自己是谁。记忆会缓慢恢复。",
        2: "被窃：调查员 1D10 小时后清醒，发现自己身上贵重物品丢失。",
        3: "遍体鳞伤：调查员 1D10 小时后清醒，身体有严重伤痕（生命值剩一半）。",
        4: "暴力倾向：调查员可能在疯狂期间杀人或造成重大破坏。",
        5: "极端信念：调查员疯狂地执行某个信仰（如宗教狂热、政治极端），并采取极端行动。",
        6: "重要之人：调查员疯狂追求某个他在意的人，不顾一切地接近该人。",
        7: "被收容：调查员在精神病院或警察局醒来，完全不记得发生了什么。",
        8: "逃避行为：调查员在远离原地点的地方醒来，可能在荒郊野外或陌生城市。",
        9: "恐惧：调查员患上一种新的恐惧症（骰 1D100 或由守秘人选择）。",
        10: "躁狂：调查员患上一种新的躁狂症（骰 1D100 或由守秘人选择）。"
        }
        """随机生成长期疯狂症状"""
        roll = random.randint(1, 10)
        result = long_term_insanity[roll].replace("1D10", str(random.randint(1, 10)))

        if roll == 9:
            fear_roll = random.randint(1, 100)
            result += f"\n→ 具体恐惧症：{phobias[str(fear_roll)]}（骰值 {fear_roll}）"

        if roll == 10:
            mania_roll = random.randint(1, 100)
            result += f"\n→ 具体躁狂症：{manias[str(mania_roll)]}（骰值 {mania_roll}）"

        yield event.plain_result(f"🎲 **疯狂发作 - 总结症状（1D10={roll}）**\n{result}")

    # ========================================================= #
    #先攻相关
    class InitiativeItem:
        def __init__(self, name: str, init_value: int, player_id: int):
            self.name = name
            self.init_value = init_value
            self.player_id = player_id  # 用于区分同名不同玩家

    def add_item(self, item: InitiativeItem, group_id: str):
        """添加先攻项并排序"""
        init_list[group_id].append(item)
        self.sort_list(group_id)
    
    def remove_by_name(self, name: str, group_id: str):
        """按名字删除先攻项"""
        try:
            init_list[group_id] = [item for item in init_list[group_id] if item.name != name]
        except:
            init_list[group_id] = []
            current_index[group_id] = 0
    
    def remove_by_player(self, player_id: int, group_id: str):
        """按玩家ID删除先攻项"""
        init_list[group_id] = [item for item in init_list[group_id] if item.player_id != player_id]
    
    def init_clear(self, group_id: str):
        """清空先攻表"""
        init_list[group_id].clear()
        current_index[group_id] = -1
    
    def sort_list(self, group_id: str):
        """按先攻值降序排序 (稳定排序)"""
        init_list[group_id].sort(key=lambda x: x.init_value, reverse=True)
    
    def next_turn(self, group_id: str):
        """移动到下一回合并返回当前项"""
        if not init_list[group_id]:
            return None
        
        if current_index[group_id] < 0:
            current_index[group_id] = 0
        else:
            current_index[group_id] = (current_index[group_id] + 1) % len(init_list[group_id])
        
        return init_list[group_id][current_index[group_id]]
    
    def format_list(self, group_id: str) -> str:
        """格式化先攻表输出"""
        try:
            fl = init_list[group_id]
        except:
            init_list[group_id] = []
            return "先攻列表为空"

        if not fl:
            return "先攻列表为空"
        
        lines = []
        for i, item in enumerate(fl):
            prefix = "-> " if i == current_index[group_id] else "   "
            lines.append(f"{prefix}{item.name}: {item.init_value}")
        return "\n".join(lines)

    @filter.command("init")
    async def initiative(self , event: AstrMessageEvent , instruction: str = None, player_name: str = None):
        group_id = event.get_group_id()
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        if not instruction:
            yield event.plain_result("当前先攻列表为：\n"+self.format_list(group_id))
        elif instruction == "clr":
            self.init_clear(group_id)
            yield event.plain_result("已清空先攻列表")
        elif instruction == "del":
            if not player_name:
                player_name = user_name
            self.remove_by_name(player_name, group_id)
            yield event.plain_result(f"已删除角色{player_name}的先攻")

    # @filter.command("ri")
    async def roll_initiative(self , event: AstrMessageEvent, expr: str = None):

        group_id = event.get_group_id()
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()

        if not expr:
            init_value = random.randint(1, 20)
            player_name = user_name
        elif expr[0] == "+":
            match = re.match(r"\+(\d+)", expr)
            init_value = random.randint(1, 20) + int(match.group(1))
            player_name = user_name
        elif expr[0] == "-":
            match = re.match(r"\-(\d+)", expr)
            init_value = random.randint(1, 20) - int(match.group(1))
            player_name = user_name
        else:
            match = re.match(r"(\d+)", expr)
            init_value = int(match.group(1))
            player_name = expr[match.end():]
            if not player_name:
                player_name = user_name

        item = self.InitiativeItem(player_name, init_value, user_id)
        self.remove_by_name(player_name, group_id)
        self.add_item(item, group_id)
        yield event.plain_result(f"已添加/更新{player_name}的先攻：{init_value}")
        async for result in self.initiative(event):
            yield result

    @filter.command("ed")
    async def end_current_round(self , event: AstrMessageEvent):
        group_id = event.get_group_id()
        current_item = init_list[group_id][current_index[group_id]]
        next_item = self.next_turn(group_id)
        if not next_item:
            yield event.plain_result("先攻列表为空，无法推进回合")
        else:
            yield event.plain_result(f"{current_item.name}的回合结束 → \n {next_item.name}的回合 (先攻: {next_item.init_value})")

    
    # ========================================================= #

    @filter.command("name")
    async def generate_name(self, event:AstrMessageEvent, language: str = "cn", num: int = 5, sex: str = None):
        if language == "cn" or "中" in language or language == "zh" or language == "zh_CN" :
            fake = Faker(locale = "zh_CN")
        elif language == "en" or "英" in language or language == "en_GB" :
            fake = Faker(locale = "en_GB")
        elif language == "us" or "美" in language or language == "en_US" :
            fake = Faker(locale = "en_US")
        elif language == "jp" or "=日" in language or language == "ja_JP" :
            fake = Faker(locale = "ja_JP")

        if sex == "男":
            names = [fake.name_male() for _ in range(num)]
        elif sex == "女":
            names = [fake.name_female() for _ in range(num)]
        else:
            names = [fake.name() for _ in range(num)]

        yield event.plain_result(f"已为您生成{num}个名字："+", ".join(names))
    
    # ========================================================= #

    def get_db_build(self, str_val, siz_val):
        DB_BUILD_TABLE = [
        (64, "-2D6", -2),
        (84, "-1D6", -1),
        (124, "+0", 0),
        (164, "+1D4", 1),
        (204, "+1D6", 2),
        (999, "+2D6", 3)
        ]
        total = str_val + siz_val
        for limit, db, build in DB_BUILD_TABLE:
            if total <= limit:
                return db, build
        return "+0", 0


    def roll_character(self):
        STR = (random.randint(1, 6) + random.randint(1, 6) + random.randint(1, 6)) * 5
        CON = (random.randint(1, 6) + random.randint(1, 6) + random.randint(1, 6)) * 5
        SIZ = (random.randint(1, 6) + random.randint(1, 6) + 6) * 5
        DEX = (random.randint(1, 6) + random.randint(1, 6) + random.randint(1, 6)) * 5
        APP = (random.randint(1, 6) + random.randint(1, 6) + random.randint(1, 6)) * 5
        INT = (random.randint(1, 6) + random.randint(1, 6) + 6) * 5
        POW = (random.randint(1, 6) + random.randint(1, 6) + random.randint(1, 6)) * 5
        EDU = (random.randint(1, 6) + random.randint(1, 6) + 6) * 5

        HP = (SIZ + CON) // 10
        MP = POW // 5
        SAN = POW
        LUCK = ((random.randint(1, 6) + random.randint(1, 6) + random.randint(1, 6)) * 5)
        DB, BUILD = self.get_db_build(STR, SIZ)
        
        TOTAL = STR + CON + SIZ + DEX + APP + INT + POW + EDU

        return {
            "STR": STR, "CON": CON, "SIZ": SIZ, "DEX": DEX, 
            "APP": APP, "INT": INT, "POW": POW, "EDU": EDU,
            "HP": HP, "MP": MP, "SAN": SAN, "LUCK": LUCK,
            "DB": DB, "BUILD": BUILD, "TOTAL" : TOTAL
        }

    def format_character(self, data, index=1):
        return (
            f"第 {index} 号调查员\n"
            f"力量: {data['STR']}  体质: {data['CON']}  体型: {data['SIZ']}\n"
            f"敏捷: {data['DEX']}  外貌: {data['APP']}  智力: {data['INT']}\n"
            f"意志: {data['POW']}  教育: {data['EDU']}\n"
            f"生命: {data['HP']}  魔力: {data['MP']}  理智: {data['SAN']}  幸运: {data['LUCK']}\n"
            f"DB: {data['DB']}  总和 : {data['TOTAL']} / {data['TOTAL'] + data['LUCK']}"
        )
    
    def roll_4d6_drop_lowest(self):
        rolls = [random.randint(1, 6) for _ in range(4)]
        return sum(sorted(rolls)[1:])

    def roll_dnd_character(self):
        return [
            self.roll_4d6_drop_lowest(),
            self.roll_4d6_drop_lowest(),
            self.roll_4d6_drop_lowest(),
            self.roll_4d6_drop_lowest(),
            self.roll_4d6_drop_lowest(),
            self.roll_4d6_drop_lowest(),
        ]

    def format_dnd_character(self, data, index=1):
        data = sorted(data, reverse=True)
        return (
        f"第 {index} 位冒险者\n"
        f"[{data[0]}, {data[1]}, {data[2]}, {data[3]}, {data[4]}, {data[5]}] → 共计 {sum(data)}"
        )
    
    @filter.command("coc")
    async def generate_coc_character(self, event: AstrMessageEvent, x: int = 1):
        """生成 x 个 CoC 角色数据"""
        characters = [self.roll_character() for _ in range(x)]
        result = "\n\n".join(self.format_character(characters[i], i+1) for i in range(x))
        yield event.plain_result("系统提示：角色数据生成协议(协议代号：CoC)启动——\n" + result + "\n最终校验和：0xATRI_42A7——生成完毕。")
        
    @filter.command("dnd")
    async def generate_dnd_character(self, event: AstrMessageEvent, x: int = 1):
        """生成 x 个 DnD 角色属性"""
        characters = [self.roll_dnd_character() for _ in range(x)]
        result = "\n\n".join(self.format_dnd_character(characters[i], i+1) for i in range(x))
        yield event.plain_result("系统提示：角色数据生成协议(协议代号：DnD)启动——\n" + result + "\n最终校验和：0xATRI_42A7——生成完毕。")
        
    # ========================================================= #
    # 注册指令 /dicehelp
    @filter.command("dicehelp")
    async def help ( self , event: AstrMessageEvent):
        help_text = (
        "亚托莉的使用指南的说！\n\n"
        "基础掷骰\n"
        "`/r 1d100` - 掷 1 个 100 面骰\n"
        "`/r 3d6+2d4-1d8` - 掷 3 个 6 面骰 + 2 个 4 面骰 - 1 个 8 面骰\n"
        "`/r 3#1d20` - 掷 1d20 骰 3 次\n\n"
        
        "人物卡管理\n"
        "`/pc create 名称 属性值` - 创建人物卡\n"
        "`/pc show` - 显示当前人物卡\n"
        "`/pc list` - 列出所有人物卡\n"
        "`/pc change 名称` - 切换当前人物卡\n"
        "`/pc update 属性 值/公式` - 更新人物卡属性\n"
        "`/pc delete 名称` - 删除人物卡\n\n"
        
        "CoC 相关\n"
        "`/coc x` - 生成 x 个 CoC 角色数据\n"
        "`/ra 技能名` - 进行技能骰\n"
        "`/rap n 技能名` - 带 n 个惩罚骰的技能骰\n"
        "`/rab n 技能名` - 带 n 个奖励骰的技能骰\n"
        "`/sc 1d6/1d10` - 进行 San Check\n"
        "`/ti` - 生成临时疯狂症状\n"
        "`/li` - 生成长期疯狂症状\n"
        "`/en 技能名 [技能值]` - 技能成长\n"
        "`/name [cn/en/jp] [数量]` - 随机生成名字\n\n"
        
        "DnD 相关\n"
        "`/dnd x` - 生成 x 个 DnD 角色属性\n"
        "`/init` - 显示当前先攻列表\n"
        "`/init clr` - 清空先攻列表\n"
        "`/init del [角色名]` - 删除角色先攻（默认为用户名） \n"
        "`/ri +/- x` - 以x的调整值投掷先攻\n"
        "`/ri x [角色名]` - 将角色（默认为用户名）的先攻设置为x\n"
        "`/ed` - 结束当前回合"
        "`/fireball n` - 施放 n 环火球术，计算伤害\n\n"   

        "其他规则\n"
        "`/rv 骰子数量 难度` - 进行吸血鬼规则掷骰判定\n"
        )

        yield event.plain_result(help_text)
        
    @filter.command("fireball")
    async def fireball(self, event: AstrMessageEvent, ring : int = 3):
        """投掷 n 环火球术伤害"""
        if ring < 3 :
            yield event.plain_result("请不要试图使用降环火球术！")
        rolls = [random.randint(1, 6) for _ in range(8 + (ring - 3))]
        total_sum = sum(rolls)

        damage_breakdown = " + ".join(map(str, rolls))
        result_message = (
            f"明亮的闪光从你的指间飞驰向施法距离内你指定的一点，并随着一声低吼迸成一片烈焰。\n"
            f"{ring} 环火球术的伤害投掷: {damage_breakdown} = 🔥{total_sum}🔥 点伤害！\n"
        )

        yield event.plain_result(result_message)
        
    # ======================================================== #
    # 今日RP #
    @filter.command("jrrp")
    async def roll_RP (self, event: AstrMessageEvent):
        user_id = event.get_sender_id()
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        RP_str = f"{user_id}_{today}"
        
        hash = hashlib.sha256(RP_str.encode()).hexdigest()
        rp = int(hash, 16) % 100 + 1
        
        result_message = f"哔——今日运势协议启动！主人今天可以吃 {rp} 块草莓蛋糕哦！"
        yield event.plain_result(result_message)

    @filter.command("setcoc")
    async def modify_coc_great_sf_rule(self, event: AstrMessageEvent, command:str = " "):
        """
        Check or Modify current great success/failure rule.
        Args:
            event(AstrMessageEvent): API of message send & receive.
        Return:
            None. 
        """

        coc_rule_init()

        # check command
        rule_set = 0
        if   command[0] == "1":
            rule_set = 1
        elif command[0] == "2":
            rule_set = 2
        elif command[0] == "3":
            rule_set = 3
        elif command[0] == "4":
            rule_set = 4
        elif command[0] == "0":
            rule_set = GREAT_SF_RULE_DEFAULT
        else:
            rule_set = -1

        group_id = event.get_group_id()

        # set rule
        if rule_set > 0:
            sgsfr_res = set_great_sf_rule(rule_set, str(group_id))
            # yield event.plain_result(f"[modify_coc_great_sf_rule()] DEBUG: sgsfr_res = {sgsfr_res}")
            yield event.plain_result(f"已将大成功/大失败规则设置为{GREAT_SF_RULE_STR[rule_set]}")
        # plain help
        else:
            res_str = ""
            res_str += f"setcoc帮助：\n"
            res_str += f"/setcoc 1 → {GREAT_SF_RULE_STR[1]}（大成功1，大失败100）\n"
            res_str += f"/setcoc 2 → {GREAT_SF_RULE_STR[2]}（大成功1，阶段性大失败）\n"
            res_str += f"/setcoc 3 → {GREAT_SF_RULE_STR[3]}（阶段性大成功，阶段性大失败）\n"
            res_str += f"/setcoc 4 → {GREAT_SF_RULE_STR[4]}（大成功1~5，大失败96~100）\n"
            res_str += f"/setcoc 0 → 默认规则（当前为{GREAT_SF_RULE_STR[GREAT_SF_RULE_DEFAULT]}）\n"
            res_str += f"当前规则：{GREAT_SF_RULE_STR[int(get_great_sf_rule(group_id))]}"
            yield event.plain_result(res_str)



    
    # 识别所有信息
    @event_message_type(EventMessageType.GROUP_MESSAGE)
    async def identify_command(self, event: AstrMessageEvent): 

        message = event.message_obj.message_str
        # yield event.plain_result(message)

        random.seed(int(time.time() * 1000))
        
        if not any(message.startswith(prefix) for prefix in self.wakeup_prefix):
            return
        
        message = re.sub(r'\s+', '', message[1:])

        m = re.match(r'^([a-z]+)', message, re.I)

        if not m:
            #raise ValueError('无法识别的指令格式!')
            return
        
        cmd  = m.group(1).lower() if m else ""
        expr = message[m.end():].strip()
        
        skill_value = ""
        dice_count = "1"
        if cmd[0:2] == "en":
            sv_match = re.search(r'\d+$', message)
            if sv_match:
                skill_value = sv_match.group()
                expr = message[2:len(message)-len(skill_value)]
                cmd = "en"
            else:
                skill_value = None
                expr = message[2:]
                cmd = "en"
        if cmd[0:2] == "ra":
            sv_match = re.search(r'\d+$', message)
            if sv_match:
                skill_value = sv_match.group()
                expr = message[2:len(message)-len(skill_value)]
                cmd = "ra"
            else:
                skill_value = None
                expr = message[2:]
                cmd = "ra"
            if expr[0] == 'b' or expr[0] == 'p':
                cmd = cmd + expr[0]
                expr = expr[1:]
                dice_count_match = re.search(r'\d+', expr)
                if dice_count_match:
                    dice_count = dice_count_match.group()
                    expr = expr[dice_count_match.end():]
                else:
                    dice_count = "1"

        # result_message = (f"m={m},message={message},cmd={cmd},expr={expr}.")
        # yield event.plain_result(result_message)

        if cmd == "r":
            await self.handle_roll_dice(event, expr)
        elif cmd == "rd":
            await self.handle_roll_dice(event, "d"+expr)
        elif cmd == "rh":
            async for result in self.roll_hidden(event):
                yield result
        elif cmd == "rab":
            async for result in self.roll_attribute_bonus(event, dice_count, expr, skill_value):
                yield result
        elif cmd == "rap":
            async for result in self.roll_attribute_penalty(event, dice_count, expr, skill_value):
                yield result
        elif cmd == "ra":
            async for result in self.roll_attribute(event, expr, skill_value):
                yield result
        elif cmd == "en":
            async for result in self.grow_up(event, expr, skill_value):
                yield result
        elif cmd == "sc":
            async for result in self.san_check(event, expr):  
                yield result
        elif cmd == "li":
            async for result in self.long_term_insanity_command(event):
                yield result
        elif cmd == "ti":
            async for result in self.temporary_insanity_command(event):
                yield result
        elif cmd == "ri":
            async for result in self.roll_initiative(event, expr):
                yield result

    # # log save    
    # @command_group("log")
    # async def log(self, event: AstrMessageEvent, command: str = None):
    #     if command == 'on':
    #         pass
    #     elif command == 'off':
    #         pass
    #     elif command == 'end':
    #         pass
    #     elif command == 'help':
    #         user_id = event.get_sender_id()
    #         group_id = event.get_group_id()
    #         client = event.bot  # 获取机器人 Client
    #         message_id = event.message_obj.message_id
    #         payloads = {
    #             "group_id": group_id,
    #             "message": [
    #                 {
    #                     "type": "reply",
    #                     "data": {
    #                         "id": message_id
    #                     }
    #                 },
    #                 {
    #                     "type": "text",
    #                     "data": {
    #                         "text": log_help_str
    #                     }
    #                 }
    #             ]
    #         }

    #         ret = await client.api.call_action("send_group_msg", **payloads)
    #     else:
    #         user_id = event.get_sender_id()
    #         group_id = event.get_group_id()
    #         client = event.bot  # 获取机器人 Client
    #         message_id = event.message_obj.message_id
    #         payloads = {
    #             "group_id": group_id,
    #             "message": [
    #                 {
    #                     "type": "reply",
    #                     "data": {
    #                         "id": message_id
    #                     }
    #                 },
    #                 {
    #                     "type": "text",
    #                     "data": {
    #                         "text": f"亚托莉还没有录入指令{command}噢...请输入\".log help\"查询可用命令"
    #                     }
    #                 }
    #             ]
    #         }

    #         ret = await client.api.call_action("send_group_msg", **payloads)

