import random
import datetime
import hashlib
import ast
from typing import Optional

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import message_components as Comp
from astrbot.api.all import *
from astrbot.api import logger

# ========== SYSTEM IMPORT ========== #
import json
import re
import time
import os
import uuid
import sqlite3
from faker import Faker

# ========== MODULE IMPORT ========== #
from .component import character as charmod
from .component import dice as dice_mod
from .component import sanity
from .component.output import get_output
from .component.utils import generate_names, roll_character, format_character, roll_dnd_character, format_dnd_character
from .component.rules import modify_coc_great_sf_rule_command
from .component.log import JSONLoggerCore

logger_core = JSONLoggerCore()

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

async def get_sender_nickname(client, group_id, sender_id) :
    payloads = {
        "group_id": group_id,
        "user_id": sender_id,
        "no_cache": True
    }
    
    ret = await client.api.call_action("get_group_member_info", **payloads)
    
    return ret["card"]

async def init():
    await logger_core.initialize()

@register("astrbot_plugin_TRPG", "shiroling", "TRPG玩家用骰", "1.0.3")
class DicePlugin(Star):
    def __init__(self, context: Context):
        self.wakeup_prefix = [".", "。", "/"]

        super().__init__(context)

    async def save_log(self, group_id, content) :
        ok, info = await logger_core.add_message(
            group_id=group_id,
            user_id="Bot",
            nickname="风铃Velinithra",
            timestamp=int(time.time()),
            text=content,
            isDice = True
        )

    
    # @filter.command("r")
    async def handle_roll_dice(self, event: AstrMessageEvent, message: str = None, remark : str = None):
        """普通掷骰：改为直接调用 dice.handle_roll_dice，输出由 get_output 管理（无 fallback）"""
        
        message = message.strip() if message else None

        user_id = event.get_sender_id()
        group_id = event.get_group_id()
        client = event.bot
        
        ret = await get_sender_nickname(client, group_id, user_id)
        ret = event.get_sender_name() if ret == "" else ret

        # 让 dice 模块处理表达式并返回由 get_output 格式化好的文本（或错误文本）
        result_text = dice_mod.handle_roll_dice(message if message else f"1d{dice_mod.DEFAULT_DICE}", name = ret, remark = remark)
        message_id = event.message_obj.message_id
        payloads = {
            "group_id": group_id,
            "message": [
                {"type": "reply", "data": {"id": message_id}},
                {"type": "at", "data": {"qq": user_id}},
                {"type": "text", "data": {"text": "\n" + result_text}}
            ]
        }
        
        await self.save_log(group_id = event.get_group_id(), content = result_text)
        
        await client.api.call_action("send_group_msg", **payloads)

    @filter.command("rv")
    async def roll_dice_vampire(self, event: AstrMessageEvent, dice_count: str = "1", difficulty: str = "6"):
        """吸血鬼掷骰：使用 dice.roll_dice_vampire 得到内部结果，然后通过 get_output 输出模板文本（无 fallback）"""
        # 验证参数
        try:
            int_dice_count = int(dice_count)
            int_difficulty = int(difficulty)
        except ValueError:
            err = get_output("dice.vampire.error", error="非法数值")
            yield event.plain_result(err)
            return

        result_body = dice_mod.roll_dice_vampire(int_dice_count, int_difficulty)

        user_id = event.get_sender_id()
        group_id = event.get_group_id()
        client = event.bot

        ret = await get_sender_nickname(client, group_id, user_id)
        ret = event.get_sender_name() if ret == "" else ret
        text = get_output("dice.vampire.success", result=result_body, name = ret)
        
        message_id = event.message_obj.message_id
        payloads = {
            "group_id": group_id,
            "message": [
                {"type": "reply", "data": {"id": message_id}},
                {"type": "at", "data": {"qq": user_id}},
                {"type": "text", "data": {"text": "\n" + text}}
            ]
        }

        await self.save_log(group_id = event.get_group_id(), content = text)
        
        await client.api.call_action("send_group_msg", **payloads)
            
    async def roll_hidden(self, event: AstrMessageEvent, message: str = None):
        """私聊发送掷骰结果 —— 所有文本由 get_output 管理（无 fallback）"""
        sender_id = event.get_sender_id()
        message = message.strip() if message else f"1d{dice_mod.DEFAULT_DICE}"

        notice_text = get_output("dice.hidden.group")
        yield event.plain_result(notice_text)

        private_text = dice_mod.roll_hidden(message)

        # 3) 发送私聊（使用平台 API）
        client = event.bot
        payloads = {
            "user_id": sender_id,
            "message": [
                {
                    "type": "text",
                    "data": {
                        "text": private_text
                    }
                }
            ]
        }
        
        await self.save_log(group_id = event.get_group_id(), content = "[Private Roll Result]" + private_text)
        
        await client.api.call_action("send_private_msg", **payloads)


    @filter.command("st")
    async def status(self, event: AstrMessageEvent, attributes: str = None, exp : str = None):
        """人物卡属性更新 / 掷骰"""
        if not attributes:
            return

        user_id = event.get_sender_id()
        chara_id = charmod.get_current_character_id(user_id)
        if not chara_id:
            yield get_output("pc.show.no_active")
            return

        chara_data = charmod.load_character(user_id, chara_id)
        full_expr = (str(attributes) if attributes else "") + (str(exp) if exp else "")
        attributes_clean = re.sub(r'\s+', '', full_expr)

        # 正则匹配属性名 + 可选运算符 + 可选值（支持 san50, san+50, san +50, san*2, san+2d6）
        match = re.match(r"([\u4e00-\u9fa5a-zA-Z]+)\s*([+\-*]?)\s*(\d+(?:d\d+)?|\d*)", attributes_clean)
        if not match:
            yield get_output("pc.show.attr_missing", attribute=attributes_clean)
            return

        attribute = match.group(1)
        operator = match.group(2) if match.group(2) else None
        value_expr = match.group(3) if match.group(3) else None

        logger.info(f"{attributes_clean}")

        if attribute not in chara_data["attributes"]:
            yield get_output("pc.show.attr_missing", attribute=attribute)
            return

        current_value = chara_data["attributes"][attribute]

        value_num = 0
        roll_detail = ""
        # 判断是不是掷骰
        if value_expr and 'd' in value_expr.lower():
            dice_match = re.match(r"(\d*)d(\d+)", value_expr.lower())
            if dice_match:
                dice_count = int(dice_match.group(1)) if dice_match.group(1) else 1
                dice_faces = int(dice_match.group(2))
                rolls = dice_mod.roll_dice(dice_count, dice_faces)
                value_num = sum(rolls)
                
                roll_detail = get_output("dice.detail", detail=f"[{' + '.join(map(str, rolls))}] = {value_num}")
        elif value_expr:
            try:
                value_num = int(value_expr)
            except ValueError:
                yield get_output("pc.show.invalid_value", value=value_expr)
                return

        # 根据运算符计算新值
        if operator == "+":
            new_value = current_value + value_num
        elif operator == "-":
            new_value = current_value - value_num
        elif operator == "*":
            new_value = current_value * value_num
        else:  # 无运算符，直接赋值
            new_value = value_num

        chara_data["attributes"][attribute] = max(0, new_value)
        charmod.save_character(user_id, chara_id, chara_data)

        response = get_output("pc.update.success", attr=attribute, old=current_value, new=new_value)
        if roll_detail:
            response += "\n" + roll_detail

        await self.save_log(group_id=event.get_group_id(), content=response)

        yield event.plain_result(response)





    @command_group("pc")
    def pc(self):
        pass

    # ----------------- pc create -----------------
    @pc.command("create")
    async def pc_create_character(self, event, name: Optional[str] = None, attributes: str = ""):
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        characters = charmod.get_all_characters(user_id)

        if not name:
            name = user_name

        if name in characters:
            yield event.plain_result(get_output("pc.create.duplicate", name=name))
            return

        initial_data = (
            "力量0str0敏捷0dex0意志0pow0体质0con0外貌0app0教育0知识0edu0"
            "体型0siz0智力0灵感0int0san0san值0理智0理智值0幸运0运气0mp0魔法0hp0"
            "体力0会计5人类学1估价5考古学1取悦15攀爬20计算机5计算机使用5电脑5"
            "信用0信誉0信用评级0克苏鲁0克苏鲁神话0cm0乔装5闪避0汽车20驾驶20汽车驾驶20"
            "电气维修10电子学1话术5斗殴25手枪20急救30历史5恐吓15跳跃20拉丁语1母语0"
            "法律5图书馆20图书馆使用20聆听20开锁1撬锁1锁匠1机械维修10医学1博物学10"
            "自然学10领航10导航10神秘学5重型操作1重型机械1操作重型机械1重型1说服10"
            "精神分析1心理学10骑术5妙手10侦查25潜行20生存10游泳20投掷20追踪10驯兽5"
            "潜水1爆破1读唇1催眠1炮术1"
        )

        matches = re.findall(r"([\u4e00-\u9fa5a-zA-Z]+)(\d+)", attributes)
        initial_matches = re.findall(r"([\u4e00-\u9fa5a-zA-Z]+)(\d+)", initial_data)
        attributes_dict = {attr: int(value) for attr, value in initial_matches}
        for attr, val in matches:
            attributes_dict[attr] = int(val)

        attributes_dict['max_hp'] = (attributes_dict.get('siz', 0) + attributes_dict.get('con', 0)) // 10
        attributes_dict['max_san'] = attributes_dict.get('pow', 0)

        chara_id = charmod.create_character(user_id, name, attributes_dict)
        response = get_output("pc.create.success", name=name, id=chara_id)
        
        yield event.plain_result(response)
        await self.save_log(group_id = event.get_group_id(), content = response)


    # ----------------- pc show -----------------
    @pc.command("show")
    async def pc_show_character(self, event, attribute_name: Optional[str] = None):
        user_id = event.get_sender_id()
        chara_id = charmod.get_current_character_id(user_id)

        if not chara_id:
            yield event.plain_result(get_output("pc.show.no_active"))
            return

        chara_data = charmod.load_character(user_id, chara_id)
        if not chara_data:
            yield event.plain_result(get_output("pc.show.load_fail", id=chara_id))
            return

        if attribute_name:
            if attribute_name not in chara_data["attributes"]:
                yield event.plain_result(get_output("pc.show.attr_missing", attribute=attribute_name))
                return
            val = chara_data["attributes"][attribute_name]
            yield event.plain_result(get_output("pc.show.attr", attr=attribute_name, value=val))
        else:
            attributes = "\n".join([f"{key}: {value}" for key, value in chara_data["attributes"].items()])
            yield event.plain_result(get_output("pc.show.all", name=chara_data['name'], attributes=attributes))


    # ----------------- pc list -----------------
    @pc.command("list")
    async def pc_list_characters(self, event):
        user_id = event.get_sender_id()
        characters = charmod.get_all_characters(user_id)
        if not characters:
            yield event.plain_result(get_output("pc.list.empty"))
            return

        current = charmod.get_current_character_id(user_id)
        chara_list = "\n".join([f"- {name} (ID: {ch}) {'(当前)' if ch == current else ''}" for name, ch in characters.items()])
        yield event.plain_result(get_output("pc.list.result", list=chara_list))


    # ----------------- pc change -----------------
    @pc.command("change")
    async def pc_change_character(self, event, name: str):
        user_id = event.get_sender_id()
        characters = charmod.get_all_characters(user_id)
        if name not in characters:
            yield event.plain_result(get_output("pc.change,missing", name=name))
            return

        charmod.set_current_character(user_id, characters[name])
        yield event.plain_result(get_output("pc.change.success", name=name))


    # ----------------- pc update -----------------
    @pc.command("update")
    async def pc_update_character(self, event, attribute: str, value: str):
        user_id = event.get_sender_id()
        chara_id = charmod.get_current_character_id(user_id)
        if not chara_id:
            yield event.plain_result(get_output("pc.update.no_active"))
            return

        chara_data = charmod.load_character(user_id, chara_id)
        if attribute not in chara_data["attributes"]:
            chara_data["attributes"][attribute] = 0

        current_value = chara_data["attributes"][attribute]
        match = re.match(r"([+\-*]?)(\d*)d?(\d*)", value)
        if not match:
            yield event.plain_result(get_output("pc.update.error_format"))
            return

        operator = match.group(1)
        dice_count = int(match.group(2)) if match.group(2) else 1
        dice_faces = int(match.group(3)) if match.group(3) else 0

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
        charmod.save_character(user_id, chara_id, chara_data)

        text = get_output("pc.update.success", attr=attribute, old=current_value, new=new_value)
        if roll_detail:
            text = text + "\n" + roll_detail
        await self.save_log(group_id = event.get_group_id(), content = text)
        yield event.plain_result(text)


    # ----------------- pc delete -----------------
    @pc.command("delete")
    async def pc_delete_character(self, event, name: str):
        user_id = event.get_sender_id()
        success, _ = charmod.delete_character(user_id, name)
        if not success:
            yield event.plain_result(get_output("pc.delete.fail", name=name))
            return
        yield event.plain_result(get_output("pc.delete.success", name=name))


    # ----------------- filter sn -----------------
    @filter.command("sn")
    async def filter_set_nickname(self, event):
        if event.get_platform_name() != "aiocqhttp":
            yield event.plain_result(get_output("nick.platform_unsupported"))
            return

        from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
        client = event.bot
        user_id = event.get_sender_id()
        group_id = event.get_group_id()

        chara_id = charmod.get_current_character_id(user_id)
        chara_data = charmod.load_character(user_id, chara_id)
        if not chara_data:
            yield event.plain_result(get_output("nick.no_character", id=chara_id))
            return

        max_hp = (chara_data['attributes'].get('con', 0) + chara_data['attributes'].get('siz', 0)) // 10
        name = chara_data['name']
        hp = chara_data['attributes'].get('hp', 0)
        san = chara_data['attributes'].get('san', 0)
        dex = chara_data['attributes'].get('dex', 0)
        new_card = f"{name} HP:{hp}/{max_hp} SAN:{san} DEX:{dex}"

        payloads = {"group_id": group_id, "user_id": user_id, "card": new_card}
        await client.api.call_action("set_group_card", **payloads)

        yield event.plain_result(get_output("nick.success"))

    
    # ========================================================= #
    async def roll_attribute(self, event: AstrMessageEvent, skill_name: str, skill_value: str = None):
        user_id = event.get_sender_id()
        group_id = event.get_group_id()
        name = event.get_sender_name()

        if skill_value is None:
            skill_value = charmod.get_skill_value(user_id, skill_name)

        client = event.bot
        ret = await get_sender_nickname(client, group_id, user_id)
        
        logger.info(ret)
        
        ret = event.get_sender_name() if ret == "" else ret
        result_message = dice_mod.roll_attribute(skill_name, skill_value, str(group_id), ret)

        payloads = {
            "group_id": group_id,
            "message": [
                {"type": "reply", "data": {"id": event.message_obj.message_id}},
                {"type": "at", "data": {"qq": user_id}},
                {"type": "text", "data": {"text": "\n" + result_message}}
            ]
        }
        await self.save_log(group_id = event.get_group_id(), content = result_message)
        await client.api.call_action("send_group_msg", **payloads)

    # 惩罚骰技能判定
    async def roll_attribute_penalty(self, event: AstrMessageEvent, dice_count: str = "1", skill_name: str = "", skill_value: str = None):
        user_id = event.get_sender_id()
        group_id = event.get_group_id()

        if skill_value is None:
            skill_value = charmod.get_skill_value(user_id, skill_name)

        client = event.bot
        ret = await get_sender_nickname(client, group_id, user_id)
        ret = event.get_sender_name() if ret == "" else ret
        result_message = dice_mod.roll_attribute_penalty(dice_count, skill_name, skill_value, str(group_id), ret)

        payloads = {
            "group_id": group_id,
            "message": [
                {"type": "reply", "data": {"id": event.message_obj.message_id}},
                {"type": "at", "data": {"qq": user_id}},
                {"type": "text", "data": {"text": "\n" + result_message}}
            ]
        }

        await self.save_log(group_id = event.get_group_id(), content = result_message)
        await client.api.call_action("send_group_msg", **payloads)

    # 奖励骰技能判定
    async def roll_attribute_bonus(self, event: AstrMessageEvent, dice_count: str = "1", skill_name: str = "", skill_value: str = None):
        user_id = event.get_sender_id()
        group_id = event.get_group_id()

        if skill_value is None:
            skill_value = charmod.get_skill_value(user_id, skill_name)

        client = event.bot
        ret = await get_sender_nickname(client, group_id, user_id)
        ret = event.get_sender_name() if ret == "" else ret
        result_message = dice_mod.roll_attribute_bonus(dice_count, skill_name, skill_value, str(group_id), ret)

        payloads = {
            "group_id": group_id,
            "message": [
                {"type": "reply", "data": {"id": event.message_obj.message_id}},
                {"type": "at", "data": {"qq": user_id}},
                {"type": "text", "data": {"text": "\n" + result_message}}
            ]
        }

        await self.save_log(group_id = event.get_group_id(), content = result_message)
        await client.api.call_action("send_group_msg", **payloads)

        
    # @filter.command("en")
    async def pc_grow_up(self, event: AstrMessageEvent, skill_name: str, skill_value: str = None):
        """
        .en 技能成长判定
        调用 character 模块的 grow_up 生成结果文本，再通过 event 发送给用户。
        """
        user_id = event.get_sender_id()

        # 调用 character.py 中同步逻辑函数，不传入额外函数引用
        result_str = charmod.grow_up(
            user_id,
            skill_name=skill_name,
            skill_value=skill_value
        )

        # 构造发送消息
        group_id = event.get_group_id()
        user_name = event.get_sender_name()
        client = event.bot  # 获取机器人 Client
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
                        "text": "\n" + result_str
                    }
                }
            ]
        }

        await self.save_log(group_id = event.get_group_id(), content = result_str)
        await client.api.call_action("send_group_msg", **payloads)


    # ========================================================= #
    # san check
    # @filter.command("sc")
    async def pc_san_check(self, event: AstrMessageEvent, loss_formula: str):
        """理智检定"""
        user_id = event.get_sender_id()
        group_id = event.get_group_id()
        chara_data = charmod.get_current_character(user_id)
        client = event.bot
        
        if not chara_data:
            yield event.plain_result(get_output("pc.show.no_active"))
            return

        roll_result, san_value, result_msg, loss, new_san = sanity.san_check(chara_data, loss_formula)

        # 更新人物卡
        chara_data["attributes"]["san"] = new_san
        charmod.save_character(user_id, chara_data["id"], chara_data)

        if new_san == 0 :
            text = get_output(
                    "san.check_result.zero",
                    name=chara_data["name"],
                    roll_result=roll_result,
                    san_value=san_value,
                    result_msg=result_msg,
                    loss=loss,
                    new_san=new_san
                )

        elif loss == 0 :
            text = get_output(
                "san.check_result.no_loss",
                name=chara_data["name"],
                roll_result=roll_result,
                san_value=san_value,
                result_msg=result_msg,
                loss=loss,
                new_san=new_san
            )
        elif loss < 5 :
            text = get_output(
                "san.check_result.loss",
                name=chara_data["name"],
                roll_result=roll_result,
                san_value=san_value,
                result_msg=result_msg,
                loss=loss,
                new_san=new_san
            )
        else :
            text = get_output(
                "san.check_result.great_loss",
                name=chara_data["name"],
                roll_result=roll_result,
                san_value=san_value,
                result_msg=result_msg,
                loss=loss,
                new_san=new_san
            )

        payloads = {
            "group_id": group_id,
            "message": [
                {"type": "reply", "data": {"id": event.message_obj.message_id}},
                {"type": "at", "data": {"qq": user_id}},
                {"type": "text", "data": {"text": "\n" + text}}
            ]
        }
        
        await self.save_log(group_id = event.get_group_id(), content = text)
        
        await client.api.call_action("send_group_msg", **payloads)


    async def pc_temporary_insanity(self, event: AstrMessageEvent):
        """临时疯狂"""
        result = sanity.get_temporary_insanity(sanity.phobias, sanity.manias)
        text = get_output("san.temporary_insanity", result=result)
        await self.save_log(group_id = event.get_group_id(), content = text)
        yield event.plain_result(text)


    async def pc_long_term_insanity(self, event: AstrMessageEvent):
        """长期疯狂"""
        result = sanity.get_long_term_insanity(sanity.phobias, sanity.manias)
        text = get_output("san.long_term_insanity", result=result)
        await self.save_log(group_id = event.get_group_id(), content = text)
        yield event.plain_result(text)

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
    async def generate_name(self, event: AstrMessageEvent, language: str = "cn", num: int = 5, sex: str = None):
        names = generate_names(language=language, num=num, sex=sex)
        yield event.plain_result(get_output("generated_names", num = num, names=", ".join(names)))

    # ------------------ CoC角色生成 ------------------ #
    @filter.command("coc")
    async def generate_coc_character(self, event: AstrMessageEvent, x: int = 1):
        characters = [roll_character() for _ in range(x)]
        results = []
        for i, char in enumerate(characters):
            results.append(format_character(char, index=i+1))
        yield event.plain_result(get_output("character_list.coc", characters="\n\n".join(results)))

    # ------------------ DnD角色生成 ------------------ #
    @filter.command("dnd")
    async def generate_dnd_character(self, event: AstrMessageEvent, x: int = 1):
        characters = [roll_dnd_character() for _ in range(x)]
        results = []
        for i, char in enumerate(characters):
            results.append(format_dnd_character(char, index=i+1))
        yield event.plain_result(get_output("character_list.dnd", characters="\n\n".join(results)))
        
    # ======================== LOG相关 ============================= #
    @filter.command_group("log")
    async def log(event: AstrMessageEvent):
        pass


    @log.command("new")
    async def cmd_log_new(self, event: AstrMessageEvent):
        group = event.message_obj.group_id
        parts = event.message_str.strip().split()
        name = parts[2] if len(parts) >= 3 else None
        ok, info = await logger_core.new_session(group, name)
        return event.plain_result(info)


    @log.command("end")
    async def cmd_log_end(self, event: AstrMessageEvent):
        group = event.message_obj.group_id
        ok, info = await logger_core.end_session(group)
        return event.plain_result(info)


    @log.command("off")
    async def cmd_log_off(self, event: AstrMessageEvent):
        group = event.message_obj.group_id
        ok, info = await logger_core.pause_sessions(group)
        return event.plain_result(info)


    @log.command("on")
    async def cmd_log_on(self, event: AstrMessageEvent):
        group = event.message_obj.group_id
        parts = event.message_str.strip().split()
        name = parts[2] if len(parts) >= 3 else None
        ok, info = await logger_core.resume_session(group, name)
        return event.plain_result(info)


    @log.command("list")
    async def cmd_log_list(self, event: AstrMessageEvent):
        group = event.message_obj.group_id
        lines = await logger_core.list_sessions(group)
        return event.plain_result("\n".join(lines))


    @log.command("del")
    async def cmd_log_del(self, event: AstrMessageEvent):
        group = event.message_obj.group_id
        parts = event.message_str.strip().split()
        if len(parts) < 3:
            return event.plain_result(get_output("log.delete_error"))
        name = parts[2]
        ok, info = await logger_core.delete_session(group, name)
        return event.plain_result(info)


    @log.command("get")
    async def cmd_log_get(self, event: AstrMessageEvent):
        group = event.message_obj.group_id
        parts = event.message_str.strip().split()
        name = parts[2] if len(parts) >= 3 else None
        ok, info = await logger_core.export_session(group, name)
        return event.plain_result(info)


    @log.command("stat")
    async def cmd_log_stat(self, event: AstrMessageEvent):
        group = event.message_obj.group_id
        parts = event.message_str.strip().split()
        name = parts[2] if len(parts) >= 3 else None
        all_flag = len(parts) >= 4 and parts[3] == "--all"
        lines = await logger_core.stat_sessions(group, name, all_flag)
        return event.plain_result("\n".join(lines))
    # ======================== LOG相关 ============================= #
    
    # 注册指令 /dicehelp
    @filter.command("dicehelp")
    async def help ( self , event: AstrMessageEvent):
        help_text = (
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
            "`/name [cn/en/jp] [数量]` - 随机生成名字\n"
            "/setcoc 规则编号 - 设置COC规则\n\n"
            
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
            
            "Log 管理\n"
            "/log new <日志名> - 开始新的日志会话\n"
            "/log off - 暂停当前的日志会话\n"
            "/log on - 开始当前的日志会话\m"
            "/log end - 结束当前的日志会话"
            "/log del <日志名> - 删除日志会话\n"
            "/log get <日志名> - 获取日志会话\n"
            "/log stat <日志名> - 获取日志会话统计信息\n"
        )

        yield event.plain_result(help_text)
        
    @filter.command("fireball")
    async def fireball_cmd(self, event: AstrMessageEvent, ring: int = 3):
        result = dice_mod.fireball(ring)
        yield event.plain_result(result)

    @filter.command("jrrp")
    async def roll_RP_cmd(self, event: AstrMessageEvent):
        user_id = event.get_sender_id()
        result = dice_mod.roll_RP(user_id)
        yield event.plain_result(result)

    @filter.command("setcoc")
    async def setcoc_cmd(self, event: AstrMessageEvent, command: str = " "):
        group_id = event.get_group_id()
        result = modify_coc_great_sf_rule_command(group_id, command)
        yield event.plain_result(result)

    
    # 识别所有信息
    @event_message_type(EventMessageType.GROUP_MESSAGE)
    async def identify_command(self, event: AstrMessageEvent): 

        message = event.message_obj.message_str
        
         # ------------------- 日志收集逻辑 -------------------
        group_id = event.message_obj.group_id
        
        if group_id:
            user_id = event.message_obj.sender.user_id
            nickname = getattr(event.message_obj.sender, "nickname", "")
            timestamp = int(event.message_obj.timestamp)
            components = getattr(event.message_obj, "message", [])

            # 调用功能性模块添加消息
            await logger_core.add_message(
                group_id=group_id,
                user_id=user_id,
                nickname=nickname,
                timestamp=timestamp,
                text=message,
                components=components
            )
        # ----------------------------------------------------
        
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
        remark = None
        
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
                
            if expr and (expr[0] == 'b' or expr[0] == 'p') :
                cmd = cmd + expr[0]
                expr = expr[1:]
                dice_count_match = re.search(r'\d+', expr)
                if dice_count_match:
                    dice_count = dice_count_match.group()
                    expr = expr[dice_count_match.end():]
                else:
                    dice_count = "1"
                    
            if expr.isdigit():
                skill_value = expr
                
            if not expr and skill_value:
                expr = skill_value
                
        elif cmd[0:2] == "rd":
            raw = message[2:].strip()
            dice_match = re.match(r'(\d+)', raw)
            
            if dice_match:
                dice_size = dice_match.group(1)
                expr = f"1d{dice_size}"
                remark = raw[(len(dice_size)):].strip()
            else:
                expr = "1d100"
                remark = raw.strip()
                
        elif cmd[0] == "r":
            r_match = re.match(r'([0-9]*[dD][0-9]+)', message[1:])
            if r_match:
                expr = r_match.group(1)
                remark = message[1+len(expr):].strip()
                if remark:
                    expr = expr
            else:
                expr = message[1:].strip()
                
        # result_message = (f"m={m},message={message},cmd={cmd},expr={expr}.")
        # yield event.plain_result(result_message)

        if cmd == "r":
            await self.handle_roll_dice(event, expr, remark)
        elif cmd == "rd":
            await self.handle_roll_dice(event, expr, remark)
        elif cmd == "rh":
            async for result in self.roll_hidden(event) :
                yield result
        elif cmd == "rab":
            await self.roll_attribute_bonus(event, dice_count, expr, skill_value)
        elif cmd == "rap":
            await self.roll_attribute_penalty(event, dice_count, expr, skill_value)
        elif cmd == "ra":
            await self.roll_attribute(event, expr, skill_value)
        elif cmd == "en":
            await self.pc_grow_up(event, expr, skill_value)
        elif cmd == "sc":
            async for result in self.pc_san_check(event, expr) :
                yield result
        elif cmd == "li":
            async for result in self.pc_long_term_insanity(event):
                yield result
        elif cmd == "ti":
            async for result in self.pc_temporary_insanity(event):
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

