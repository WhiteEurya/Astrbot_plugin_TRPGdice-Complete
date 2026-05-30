import random

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import message_components as Comp
from astrbot.api.all import *
from astrbot.api import logger
from astrbot.api.message_components import Image, Plain

# ========== SYSTEM IMPORT ========== #
import re
import time
import os
import json
import sys
import subprocess
from pathlib import Path
from playwright.async_api import async_playwright

# ========== MODULE IMPORT ========== #
from .component.pc import store as charmod
from .component.roll import dice as dice_mod
from .component.coc import san as sanity
from .component.common.output import get_output
from .component.common.utils import generate_names, roll_character, format_character, roll_dnd_character, format_dnd_character, SYNONYMS
from .component.coc.rules import modify_coc_great_sf_rule_command
from .component.coc.checks import parse_difficulty_prefix, parse_versus_check, prepare_skill_check, split_skill_modifier
from .component.logs.store import JSONLoggerCore
from .component.combat.init import InitiativeItem, InitiativeManager
from .component.roll.parser import parse_inline_command, strip_command_prefix
from .component.pc.view import (
    clean_st_show_words,
    format_all_attributes,
    format_named_attributes,
    format_threshold_attributes,
)
from .component.pc.nick import build_card_by_mode, build_coc_card
from .component.pc.template import get_coc_st_template

from playwright.async_api import async_playwright

logger_core = JSONLoggerCore()

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_DIR = os.path.join(PLUGIN_DIR, "data", "settings")

COMMANDS = [
    "show",
    "del",
    "clr",
    "export"
]

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
        self.wakeup_prefix = [".", "。", "/", "!", "！"]
        self.uni_cache = {}
        self.initiative_manager = InitiativeManager()
        # install chromium for spell visualizing
        try:
            subprocess.run(
                [sys.executable, "-m", "playwright", "install-deps"], 
                check=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"], 
                check=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
        except Exception as e:
            print(f"Failed to install chromium: {e}")

        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))
        self.json_path = os.path.join(self.plugin_dir, "spellsearcher/SpellSourceFolder.json")
        self.htm_spells_dir = os.path.join(self.plugin_dir, "spellsearcher/HTMSpells")

        super().__init__(context)

    async def save_log(self, group_id, content) :
        if not group_id:
            return

        ok, info = await logger_core.add_message(
            group_id=group_id,
            user_id="Bot",
            nickname="风铃Velinithra",
            timestamp=int(time.time()),
            text=content,
            isDice = True
        )

    def _event_context_id(self, event: AstrMessageEvent) -> str:
        group_id = event.get_group_id()
        if group_id:
            return str(group_id)
        session_id = getattr(event.message_obj, "session_id", None)
        return str(session_id or event.get_sender_id())

    async def _event_display_name(self, event: AstrMessageEvent, user_id: str = None) -> str:
        user_id = user_id or event.get_sender_id()
        group_id = event.get_group_id()
        if group_id:
            try:
                nickname = await get_sender_nickname(event.bot, group_id, user_id)
                if nickname:
                    return nickname
            except Exception:
                pass
        return event.get_sender_name() if user_id == event.get_sender_id() else str(user_id)

    def _get_target_user_id(self, event: AstrMessageEvent) -> str:
        target_user_id = str(event.get_sender_id())
        for comp in getattr(event.message_obj, "message", []):
            if isinstance(comp, Comp.At):
                return str(comp.qq)
        return target_user_id

    def _strip_at_text(self, text: str) -> str:
        text = re.sub(r'\[CQ:at.*?\]', '', text or '')
        if '@' in text:
            text = text.split('@')[0]
        return text.strip()

    def _settings_path(self, kind: str, key: str) -> str:
        folder = os.path.join(SETTINGS_DIR, kind)
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, f"{key}.json")

    def _group_id(self, event: AstrMessageEvent):
        group_id = event.get_group_id()
        if group_id:
            return str(group_id)
        message_obj = getattr(event, "message_obj", None)
        group_id = getattr(message_obj, "group_id", None)
        if group_id:
            return str(group_id)
        session_id = getattr(message_obj, "session_id", None)
        return str(session_id or "")

    def _load_settings(self, kind: str, key: str) -> dict:
        path = self._settings_path(kind, str(key))
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_settings(self, kind: str, key: str, data: dict):
        path = self._settings_path(kind, str(key))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _get_group_settings(self, group_id) -> dict:
        return self._load_settings("groups", str(group_id))

    def _save_group_settings(self, group_id, data: dict):
        self._save_settings("groups", str(group_id), data)

    def _is_bot_enabled(self, group_id) -> bool:
        return self._get_group_settings(group_id).get("enabled", True)

    def _command_enabled(self, event: AstrMessageEvent) -> bool:
        group_id = self._group_id(event)
        if not group_id:
            return True
        return self._is_bot_enabled(group_id)

    def _stop_event(self, event: AstrMessageEvent):
        for method_name in ("stop_event", "stop_propagation", "stop"):
            method = getattr(event, method_name, None)
            if callable(method):
                try:
                    method()
                except TypeError:
                    pass
                return

    def _bot_image_path(self):
        candidates = [
            os.path.join(PLUGIN_DIR, "data", "velinithra.png"),
            os.path.join(SETTINGS_DIR, "bot.png"),
            os.path.join(SETTINGS_DIR, "bot.jpg"),
            os.path.join(PLUGIN_DIR, "bot.png"),
            os.path.join(PLUGIN_DIR, "bot.jpg"),
            os.path.join(PLUGIN_DIR, "assets", "bot.png"),
            os.path.join(PLUGIN_DIR, "assets", "bot.jpg"),
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def _bot_info_text(self, event: AstrMessageEvent) -> str:
        status = "开启" if self._is_bot_enabled(self._group_id(event)) else "关闭"
        return (
            "“呼——！感觉到了吗？是我带来的风哦！”\n"
            "“我是风铃，今天也请让我陪你一起出发吧！”\n\n"
            "本骰娘采用Astrbot框架。如有需求请联系骰主(2995186695)\n"
            "使用.bothelp学习如何使用本骰子。\n"
            f"当前状态：{status}"
        )

    def _get_user_aliases(self, user_id: str) -> dict:
        return self._load_settings("aliases", str(user_id))

    def _save_user_aliases(self, user_id: str, aliases: dict):
        self._save_settings("aliases", str(user_id), aliases)

    def _resolve_user_alias(self, user_id: str, name: str) -> str:
        if not name:
            return name
        aliases = self._get_user_aliases(str(user_id))
        return aliases.get(name, name)

    
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
        if not self._command_enabled(event):
            return
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
        """人物卡属性更新 / 掷骰 (V4 - 区分单/多重赋值)"""
        if not self._command_enabled(event):
            return
        if not attributes:
            return

        if attributes in COMMANDS :
            return

        user_id = self._get_target_user_id(event)
        operator_user_id = str(event.get_sender_id())
        group_id = event.get_group_id()
        chara_id = charmod.get_current_character_id(group_id, user_id)
        
        if not chara_id:
            if user_id == operator_user_id:
                yield event.plain_result(get_output("pc.show.no_active"))
            else:
                yield event.plain_result("该玩家尚未在当前群组绑定人物卡哦。")
            return

        chara_data = charmod.load_character(group_id, user_id, chara_id)
        full_expr = self._strip_at_text((str(attributes) if attributes else "") + (str(exp) if exp else ""))
        attributes_clean = re.sub(r'\s+', '', full_expr)

        # --- 
        # ⬇️ 多重赋值逻辑 ⬇️
        # ---
        multi_assign_pattern = r"^((?:[\u4e00-\u9fa5a-zA-Z/_]+)(\d+))+$"

        # 1. 检查是否符合“严格”的多重赋值模式
        if re.match(multi_assign_pattern, attributes_clean):
            
            matches = re.findall(r"([\u4e00-\u9fa5a-zA-Z/_]+)(\d+)", attributes_clean)
            
            derived_tips = None
            
            if len(matches) > 1:
                
                for match_pair in matches:
                    attribute = match_pair[0]
                    value_num = int(match_pair[1])

                    if attribute not in chara_data["attributes"]:
                        chara_data["attributes"][attribute] = 1
                    
                    new_value = value_num
                    chara_data["attributes"][attribute] = max(0, new_value)

                derived_tips = charmod.sync_derived_attributes(chara_data)

                # (循环外) 一次性保存并发送汇总回执
                charmod.save_character(group_id, user_id, chara_id, chara_data)
                if event.get_platform_name() == "aiocqhttp":
                    await self._update_user_nickname_card(event.bot, group_id, user_id)
                
                num_updates = len(matches)
                response = get_output("pc.update.batch_success", count=num_updates)
                if user_id != operator_user_id:
                    response = f"已代为更新 <{chara_data.get('name', user_id)}>：\n" + response
                
                if derived_tips:
                        response += "\n自动更新: " + ", ".join(derived_tips)
                
                await self.save_log(group_id=event.get_group_id(), content=response)
                yield event.plain_result(response)
                return # --- 多重更新结束 ---

            # 3. 如果 len(matches) == 1 (例如 .st 力量100)
            #    我们什么也不做 (pass)，让代码 *故意*
            #    掉入下面的“旧的单一属性逻辑”中去处理，
            #    以便它能输出 "力量: 0 -> 100" 的详细信息。

        # --- 
        # ⬆️ 多重赋值逻辑结束 ⬆️
        # ---

        # --- 
        # ⬇️ 旧的单一属性逻辑 (现在也会处理 .st 力量100) ⬇️
        # ---
        
        match = re.match(r"([\u4e00-\u9fa5a-zA-Z]+)\s*([+\-*]?)\s*(\d+(?:d\d+)?|\d*)", attributes_clean)
        if not match:
            yield event.plain_result(get_output("pc.update.error_format"))
            return

        attribute = match.group(1)
        operator = match.group(2) if match.group(2) else None
        value_expr = match.group(3) if match.group(3) else None

        derived_tips = None

        if attribute not in chara_data["attributes"]:
            chara_data["attributes"][attribute] = 1

        current_value = chara_data["attributes"][attribute]

        value_num = 0
        roll_detail = ""
        
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
                yield event.plain_result(get_output("pc.show.invalid_value", value=value_expr))
                return
        
        # (如果 value_expr 为空，例如 ".st san-")
        # 此时 value_num 保持为 0，这在COC中可能是有效的 (e.g. 减去0)
        # 如果你不希望这样，可以在这里加一个检查：
        if operator and not value_expr:
             yield event.plain_result(get_output("pc.update.error_format_no_value")) # 缺少值
             return

        # 根据运算符计算新值
        if operator == "+":
            new_value = current_value + value_num
        elif operator == "-":
            new_value = current_value - value_num
        elif operator == "*":
            new_value = current_value * value_num
        else:  # 无运算符 (例如 .st 力量100)，直接赋值
            new_value = value_num

        ### NEW : 更新所有的同义词
        target_group = [attribute]
        for group in SYNONYMS.SYNONYM:
            if attribute in group:
                target_group = group
                break
            
        new_val_final = max(0, new_value)
        for attr_name in target_group:
            if attr_name in chara_data["attributes"]:
                chara_data["attributes"][attr_name] = new_val_final

        derived_tips = charmod.sync_derived_attributes(chara_data)
        charmod.save_character(group_id, user_id, chara_id, chara_data)
        # 触发静默更新名片
        if event.get_platform_name() == "aiocqhttp":
            await self._update_user_nickname_card(event.bot, group_id, user_id)

        response = get_output("pc.update.success", attr=attribute, old=current_value, new=new_value)
        if user_id != operator_user_id:
            response = f"已代为更新 <{chara_data.get('name', user_id)}>：\n" + response
        if roll_detail:
            response += "\n" + roll_detail
            
        if derived_tips:
            response += "\n自动更新: " + ", ".join(derived_tips)

        await self.save_log(group_id=event.get_group_id(), content=response)
        yield event.plain_result(response)

    @command_group("st")
    async def st(self, event: AstrMessageEvent, attributes: str = None, exp : str = None):
        """人物卡属性更新 / 掷骰"""
        pass


    @st.command("show")
    async def pc_show_character(self, event: AstrMessageEvent, *, args_str: str = ""):
        if not self._command_enabled(event):
            return
        """
        .st show [属性...] [@某人] / .st show [数字] / .st show
        (V4 - 支持 @ 其他玩家查看其属性，智能过滤群名片残留)
        """
        group_id = str(event.get_group_id())
        
        # --- 1. 解析目标用户 (识别是否 @ 了别人) ---
        target_user_id = str(event.get_sender_id())
        for comp in event.message_obj.message:
            if isinstance(comp, Comp.At):  
                target_user_id = str(comp.qq)
                break
                
        chara_id = charmod.get_current_character_id(group_id, target_user_id)
        
        if not chara_id:
            if target_user_id == str(event.get_sender_id()):
                yield event.plain_result(get_output("pc.show.no_active"))
            else:
                yield event.plain_result("该玩家尚未在当前群组绑定人物卡哦。")
            return

        chara_data = charmod.load_character(group_id, target_user_id, chara_id)
        if not chara_data:
            yield event.plain_result(get_output("pc.show.load_fail", id=chara_id))
            return
        
        chara_attrs = chara_data.get("attributes", {})
        if not chara_attrs:
            yield event.plain_result(get_output("pc.show.attr_missing", attribute="任何属性"))
            return

        base_str = args_str.split('@')[0] if '@' in args_str else args_str
        
        # B. 进一步剔除可能存在的 CQ 码（AstrBot 有时会将 @ 转为 CQ 码字符串）
        clean_text = re.sub(r'\[CQ:at.*?\]', ' ', base_str)
        
        # C. 拆分单词并过滤掉群名片生成的“噪音”
        raw_words = clean_text.split()
        valid_words = []
        
        for w in raw_words:
            upper_w = w.upper()
            # 1. 过滤掉 @ 符号本身或可能的残留
            if w.startswith('@'): continue
            # 2. 过滤掉由 .sn 指令生成的群名片残影 (HP:10/10 SAN:50 等)
            if 'HP:' in upper_w or 'SAN:' in upper_w or 'DEX:' in upper_w: continue
            # 3. 过滤掉格式化的数值（如 13/13）
            if re.match(r'^\d+/\d+$', w): continue 
            # 4. 过滤掉被 @ 者的角色名本身（如果名字恰好在文本里）
            if w == chara_data.get('name'): continue
            
            valid_words.append(w)

        # --- 3. 显示逻辑 ---

        # 场景 A: 如果没有有效参数 ( .st show ) -> 显示 *PRIMARY* 属性
        if not valid_words:
            primary_attributes = {} 
            
            for attr, value in chara_attrs.items():
                primary_name = SYNONYMS.SYNONYM_MAP.get(attr, attr)
                if primary_name not in primary_attributes:
                    primary_attributes[primary_name] = (attr, value)
                else:
                    current_stored_attr_name = primary_attributes[primary_name][0]
                    if current_stored_attr_name != primary_name and attr == primary_name:
                        primary_attributes[primary_name] = (attr, value)

            output_list = []
            for primary_name, (original_attr, value) in sorted(primary_attributes.items()):
                output_list.append(f"{primary_name}: {value}")
                
            attributes_str = "\n".join(output_list)
            
            yield event.plain_result(get_output("pc.show.all", name=chara_data['name'], attributes=attributes_str))
            return

        # 场景 B: 尝试转为数字 ( .st show 30 ) 
        if len(valid_words) == 1 and valid_words[0].isdigit():
            threshold = int(valid_words[0])
            output_parts = []
            for attr, value in chara_attrs.items():
                if value > threshold:
                    output_parts.append(f"· {attr}: {value}")
            
            if not output_parts:
                yield event.plain_result(get_output("pc.show.none_above", num=threshold))
            else:
                header = get_output("pc.show.above_threshold_header", num=threshold)
                response = header + "\n" + "\n".join(output_parts)
                if target_user_id != str(event.get_sender_id()):
                    response = f"【{chara_data['name']}】的属性：\n" + response
                yield event.plain_result(response)
            return

        # 场景 C: 按属性名处理 ( .st show 力量 敏捷 )
        found_attrs = []
        not_found_attrs = []
        
        for key in valid_words:
            if key in chara_attrs:
                val = chara_attrs[key]
                found_attrs.append(get_output("pc.show.attr", attr=key, value=val))
            else:
                # 二次防误伤：如果残留的名片名字带有空格（如 John Doe）被切碎了
                # 只要这个碎词属于对方名字的一部分，我们就默默包容它，不报错
                if key in chara_data.get('name', ''): 
                    continue
                not_found_attrs.append(key)
        
        output_parts = []
        if target_user_id != str(event.get_sender_id()):
            output_parts.append(f"【{chara_data['name']}】的属性：")
            
        if found_attrs:
            output_parts.append("\n".join(found_attrs))
        if not_found_attrs:
            missing_str = ", ".join(not_found_attrs)
            output_parts.append(get_output("pc.show.attr_missing", attribute=missing_str))

        if output_parts:
            yield event.plain_result("\n".join(output_parts))

    @st.command("模板")
    async def st_template_cn(self, event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        yield event.plain_result(get_coc_st_template())

    @st.command("template")
    async def st_template(self, event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        yield event.plain_result(get_coc_st_template())

    @st.command("del")
    async def st_del(self, event: AstrMessageEvent, *, args_str: str = ""):
        if not self._command_enabled(event):
            return
        """ 
        .st del <属性1> <属性2> ... 
        (V2 - 支持删除同义词组, 并保护核心属性)
        """
        
        user_id = event.get_sender_id()
        group_id = event.get_group_id()
        chara_id = charmod.get_current_character_id(group_id, user_id)
        
        
        if not chara_id:
            yield event.plain_result(get_output("pc.show.no_active"))
            return

        chara_data = charmod.load_character(group_id, user_id, chara_id)
        if not chara_data:
            yield event.plain_result(get_output("pc.show.load_fail", id=chara_id))
            return
            
        args_str = args_str.strip()
        if not args_str:
            yield event.plain_result(get_output("pc.del.no_args"))
            return

        # --- 
        # ⬇️ 全新的核心逻辑 ⬇️
        # ---
        
        keys_to_del_input = args_str.split() # 用户输入的词
        
        # 跟踪结果
        protected_keys_requested = [] # 跟踪用户试图删除的受保护词
        deleted_groups_primary = set()  # 跟踪已删除的 *主名* (防重复删除)
        deleted_keys_actual = []      # 跟踪实际从卡上删除的 *所有* 词
        not_found_keys_input = []   # 跟踪用户输入了，但卡上(及其同义词)都不存在的词

        chara_attrs = chara_data.get("attributes", {})

        for requested_key in keys_to_del_input:
            
            # 1. 检查是否受保护
            if requested_key in SYNONYMS.PROTECTED_ATTRIBUTES:
                protected_keys_requested.append(requested_key)
                continue

            # 2. 找到这个词的 "主名" (e.g. "str" -> "力量"; "临时" -> "临时")
            primary_name = SYNONYMS.SYNONYM_MAP.get(requested_key, requested_key)
            
            # 3. 如果这个 *组* 已经被处理过，就跳过
            if primary_name in deleted_groups_primary:
                continue

            # 4. 找到这个主名对应的 *所有同义词* (e.g. "力量" -> {"力量", "str"})
            synonyms_in_group = SYNONYMS.PRIMARY_TO_ALL_MAP.get(primary_name, {primary_name})

            # 5. 遍历角色卡，删除这个组的所有同义词
            found_at_least_one = False
            for syn in synonyms_in_group:
                if syn in chara_attrs:
                    del chara_attrs[syn] # 从字典中删除
                    deleted_keys_actual.append(syn)
                    found_at_least_one = True

            # 6. 记录结果
            if found_at_least_one:
                deleted_groups_primary.add(primary_name) # 标记这个主名组已处理
            else:
                # 如果卡上一个同义词都没有，记为 "未找到"
                not_found_keys_input.append(requested_key)

        # --- 组合输出 ---
        response_parts = []
        if protected_keys_requested:
            response_parts.append(get_output("st.del.protected", attr=", ".join(set(protected_keys_requested))))
            
        if deleted_keys_actual:
            response_parts.append(get_output("st.del.success", attr=", ".join(deleted_keys_actual)))
            
        if not_found_keys_input:
            response_parts.append(get_output("st.del.not_found", attr=", ".join(not_found_keys_input)))
        
        response = "\n".join(response_parts)

        # --- 保存并响应 ---
        if deleted_groups_primary:
            charmod.save_character(group_id, user_id, chara_id, chara_data)
            await self.save_log(group_id=event.get_group_id(), content=response)
            
        yield event.plain_result(response)


    @st.command("clr")
    async def st_clr(self, event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        """ .st clr 清除所有非核心属性 (V2 - 统一 get_output 键) """
        
        user_id = event.get_sender_id()
        client = event.bot
        group_id = event.get_group_id()
        ret = await get_sender_nickname(client, group_id, user_id)
        ret = event.get_sender_name() if ret == "" else ret
        
        chara_id = charmod.get_current_character_id(group_id, user_id)
        
        if not chara_id:
            yield event.plain_result(get_output("st.show.no_active")) # 复用
            return

        chara_data = charmod.load_character(group_id, user_id, chara_id)
        if not chara_data:
            yield event.plain_result(get_output("st.show.load_fail", id=chara_id)) # 复用
            return
            
        chara_attrs = chara_data.get("attributes", {})
        if not chara_attrs:
            # 统一: pc. -> st.
            yield event.plain_result(get_output("st.clr.nothing", name = ret))
            return

        old_count = len(chara_attrs)
        
        new_attrs = {
            key: value for key, value in chara_attrs.items() 
            # 统一: 使用 self.
            if key in SYNONYMS.PROTECTED_ATTRIBUTES
        }
        
        new_count = len(new_attrs)
        deleted_count = old_count - new_count

        if deleted_count == 0:
            # 统一: pc. -> st.
            yield event.plain_result(get_output("st.clr.nothing"))
            return
        
        chara_data["attributes"] = new_attrs
        charmod.save_character(group_id, user_id, chara_id, chara_data)
        
        # 统一: pc. -> st. (参数 'count' 保持不变，因为它不是属性列表)
        response = get_output("st.clr.success", name=ret)
        
        await self.save_log(group_id=event.get_group_id(), content=response)
        yield event.plain_result(response)
        
    @st.command("export")
    async def st_export(self, event: AstrMessageEvent, *, args_str: str = ""):
        if not self._command_enabled(event):
            return
        """ 
        .st export 
        直接导出当前卡内所有属性，格式为：属性1数值1属性2数值2...
        不进行任何去重或同义词处理。
        """
        user_id = event.get_sender_id()
        group_id = event.get_group_id()
        args_str = args_str.strip()
        chara_id = charmod.get_current_character_id(group_id, user_id)

        if args_str:
            parts = args_str.split()
            target_id = charmod.resolve_identifier(group_id, user_id, parts[0])
            if target_id:
                chara_id = target_id
                args_str = " ".join(parts[1:])

        if not chara_id:
            yield event.plain_result(get_output("pc.show.no_active"))
            return

        chara_data = charmod.load_character(group_id, user_id, chara_id)
        if not chara_data:
            yield event.plain_result(get_output("pc.show.load_fail", id=chara_id))
            return

        # 获取属性字典，如果不存在则为空字典
        chara_attrs = chara_data.get("attributes", {})
        
        if not chara_attrs:
            yield event.plain_result(get_output("pc.show.attr_missing", attribute="任何属性"))
            return

        # --- 核心逻辑：直接拼接 ---
        # 直接遍历字典，不跳过任何同义词
        export_parts = []
        for attr_name, value in chara_attrs.items():
            export_parts.append(f"{attr_name}{value}")

        # 组合成长字符串
        export_str = "".join(export_parts)

        # 构建输出文案
        # 建议在 get_output 对应的模板中加入类似 "导出数据为：\n{data}" 的格式
        response = get_output("pc.export.success", name=chara_data.get('name', '未命名'), data=export_str)
        
        yield event.plain_result(response)

    @filter.command("fire")
    async def handle_pistol_fire(self, event: AstrMessageEvent, arg1: str = "", arg2: str = ""):
        """手枪三连发：.fire [p1/p2] [技能值]"""
        if not self._command_enabled(event):
            return
        
        user_id = event.get_sender_id()
        group_id = event.get_group_id()
        client = event.bot
        
        # 1. 环境准备：获取昵称和角色数据
        nickname = await get_sender_nickname(client, group_id, user_id)
        nickname = event.get_sender_name() if nickname == "" else nickname
        
        chara_data = charmod.get_current_character(group_id, user_id)
        
        # 2. 调用后端获取结果文本
        full_args = (str(arg1) + str(arg2)).lower().strip()
        result_text = dice_mod.handle_pistol_fire(full_args, name=nickname, chara_data=chara_data)
        
        # 3. 构造复合消息 payloads
        message_id = event.message_obj.message_id
        payloads = {
            "group_id": group_id,
            "message": [
                {"type": "reply", "data": {"id": message_id}},
                {"type": "at", "data": {"qq": user_id}},
                {"type": "text", "data": {"text": "\n" + result_text}}
            ]
        }
        
        # 4. 日志与发送
        await self.save_log(group_id=group_id, content=result_text)
        await client.api.call_action("send_group_msg", **payloads)

    @command_group("pc") # type: ignore
    async def pc(self, event: AstrMessageEvent):
        pass

    # ----------------- pc create (新建并自动绑定) -----------------
    async def _pc_new_character_impl(self, event, name: str):
        if not self._command_enabled(event):
            return
        user_id = event.get_sender_id()
        group_id = str(event.get_group_id())
        
        # 1. 检查当前群路径下是否已经存在同名角色
        characters = charmod.get_all_characters(group_id, user_id)
        if name in characters:
            yield event.plain_result(get_output("pc.create.duplicate", name=name))
            return

        # 2. 创建一个完全空白的属性字典
        attributes_dict = {}

        # 3. 调用 charmod 创建角色
        # charmod.create_character 内部逻辑：
        # - 生成 UUID
        # - 保存到 chara_data/{group_id}/{user_id}/{uuid}.json
        # - 在 metadata/{user_id}/bindings.json 中记录该群绑定此 UUID
        chara_id = charmod.create_character(group_id, user_id, name, attributes_dict)
        
        response = get_output("pc.create.success", name=name, id=chara_id)
        yield event.plain_result(response)
        await self.save_log(group_id=group_id, content=response)

    @pc.command("new")
    async def pc_new_character(self, event, name: str):
        """
        .pc new <角色名>
        仅通过名字在当前群路径下新建角色并绑定。
        """
        async for result in self._pc_new_character_impl(event, name):
            yield result

    @pc.command("create")
    async def pc_create_character(self, event, name: str):
        async for result in self._pc_new_character_impl(event, name):
            yield result

    # ----------------- pc list (列出当前群角色) -----------------
    @pc.command("list")
    async def pc_list_characters(self, event):
        if not self._command_enabled(event):
            return
        user_id = event.get_sender_id()
        group_id = str(event.get_group_id())
        
        # 获取有序列表，方便以后实现序号操作
        characters = charmod.get_all_characters(group_id, user_id)
        if not characters:
            yield event.plain_result(get_output("pc.list.empty"))
            return

        # 关键：从 bindings 获取当前群绑定的角色
        current = charmod.get_current_character_id(group_id, user_id)
        
        # 排序以保证序号稳定
        sorted_chars = sorted(characters.items(), key=lambda x: x[0])
        chara_list = []
        for i, (name, ch_id) in enumerate(sorted_chars, 1):
            tags = []
            if ch_id == current:
                tags.append("当前")
            if charmod.is_local_binding(group_id, user_id, ch_id):
                tags.append("隔离")
            if charmod.is_global_character(user_id, ch_id):
                tags.append("全局")
            tag = f"({'/'.join(tags)})" if tags else ""
            chara_list.append(f"{i}. {name} {tag}")
            
        response = get_output("pc.list.result", list="\n".join(chara_list))
        yield event.plain_result(response)

    # ----------------- pc tag (绑定/切换) -----------------
    async def _pc_tag_character_impl(self, event, identifier: str = None):
        if not self._command_enabled(event):
            return
        user_id = event.get_sender_id()
        group_id = str(event.get_group_id())
        
        if not identifier:
            # 如果不填，执行解除绑定
            charmod.set_binding_info(user_id, group_id, None)
            yield event.plain_result("已解除当前群组的角色绑定。")
            return

        # 解析名字或序号
        chara_id = charmod.resolve_identifier(group_id, user_id, identifier)
        if not chara_id:
            yield event.plain_result(f"未找到角色: {identifier}")
            return

        charmod.set_binding_info(user_id, group_id, chara_id)
        yield event.plain_result(f"已将角色绑定到当前群组。")

    @pc.command("tag")
    async def pc_tag_character(self, event, identifier: str = None):
        async for result in self._pc_tag_character_impl(event, identifier):
            yield result

    @pc.command("change")
    async def pc_change_character(self, event, identifier: str = None):
        async for result in self._pc_tag_character_impl(event, identifier):
            yield result
        
    @pc.command("rename")
    async def pc_rename_character(self, event, arg1: str, arg2: str = None):
        if not self._command_enabled(event):
            return
        """
        .pc rename <新角色名>
        .pc rename <角色名|序号> <新角色名>
        """
        user_id = event.get_sender_id()
        group_id = str(event.get_group_id())

        # 逻辑分流：判断是修改当前还是修改指定
        if arg2 is None:
            # 场景：.pc rename <新名字>
            new_name = arg1
            chara_id = charmod.get_current_character_id(group_id, user_id)
            if not chara_id:
                yield event.plain_result("当前群组未绑定角色，请指定要改名的角色。")
                return
        else:
            # 场景：.pc rename <旧名|序号> <新名字>
            identifier = arg1
            new_name = arg2
            chara_id = charmod.resolve_identifier(group_id, user_id, identifier)
            if not chara_id:
                yield event.plain_result(f"未找到角色: {identifier}")
                return

        # 执行重命名
        success, info = charmod.rename_character(group_id, user_id, chara_id, new_name)

        if success:
            response = f"已将角色「{info}」重命名为「{new_name}」。"
        else:
            if info == "duplicate":
                response = f"重命名失败：当前群已存在名为「{new_name}」的角色。"
            else:
                response = "重命名失败：角色档案加载异常。"

        yield event.plain_result(response)
        await self.save_log(group_id=group_id, content=response)

    # ----------------- pc delete (删除并解绑) -----------------
    async def _pc_delete_character_impl(self, event, identifier: str):
        if not self._command_enabled(event):
            return
        user_id = event.get_sender_id()
        group_id = str(event.get_group_id())
        
        # 1. 先通过名字或序号解析出 chara_id
        chara_id = charmod.resolve_identifier(group_id, user_id, identifier)
        if not chara_id:
            yield event.plain_result("未找到该角色。")
            return
            
        # 2. 获取名字用于显示
        data = charmod.load_character(group_id, user_id, chara_id)
        name = data['name'] if data else "未知"

        # 3. 执行删除（内部含 bindings 清理）
        success, _ = charmod.delete_character_by_id(group_id, user_id, chara_id)
        
        if not success:
            yield event.plain_result(get_output("pc.delete.fail", name=name))
            return
        yield event.plain_result(get_output("pc.delete.success", name=name))

    @pc.command("delete")
    async def pc_delete_character(self, event, identifier: str):
        async for result in self._pc_delete_character_impl(event, identifier):
            yield result

    @pc.command("del")
    async def pc_del_character(self, event, identifier: str):
        async for result in self._pc_delete_character_impl(event, identifier):
            yield result
        
    @pc.command("show")
    async def pc_show(self, event, *, args_str: str = ""):
        if not self._command_enabled(event):
            return
        """
        .st show [属性...] / .st show [数字] / .st show
        (V3 - "show all" 支持同义词合并)
        """
        user_id = event.get_sender_id()
        group_id = event.get_group_id()
        args_str = args_str.strip()
        chara_id = charmod.get_current_character_id(group_id, user_id)

        if args_str:
            parts = args_str.split()
            target_id = charmod.resolve_identifier(group_id, user_id, parts[0])
            if target_id:
                chara_id = target_id
                args_str = " ".join(parts[1:])

        if not chara_id:
            yield event.plain_result(get_output("pc.show.no_active"))
            return

        chara_data = charmod.load_character(group_id, user_id, chara_id)
        if not chara_data:
            yield event.plain_result(get_output("pc.show.load_fail", id=chara_id))
            return
        
        chara_attrs = chara_data.get("attributes", {})
        if not chara_attrs:
            yield event.plain_result(get_output("pc.show.attr_missing", attribute="任何属性"))
            return

        if not args_str:
            yield event.plain_result(format_all_attributes(chara_data))
            return

        try:
            threshold = int(args_str)
            yield event.plain_result(format_threshold_attributes(chara_attrs, threshold))
            return
        except ValueError:
            pass

        response = format_named_attributes(chara_data, args_str.split())
        if response:
            yield event.plain_result(response)

    @pc.command("update")
    async def pc_update_character(self, event, *, args_str: str = ""):
        if not self._command_enabled(event):
            return
        args_str = args_str.strip()
        if not args_str:
            yield event.plain_result(get_output("pc.update.error_format"))
            return

        async for result in self.status(event, args_str):
            yield result

    # ----------------- .pc push -----------------
    @pc.command("push")
    async def pc_push_character(self, event, mode: str = None):
        if not self._command_enabled(event):
            return
        """
        手动 Push：将当前群组的角色档案标记为全域最新版。
        .pc push global：将当前角色标记为全局卡，后续跨群读写同一份 vault 档案。
        """
        user_id = str(event.get_sender_id())
        group_id = str(event.get_group_id())
        
        # 1. 获取当前群绑定的角色 ID
        chara_id = charmod.get_current_character_id(group_id, user_id)
        if not chara_id:
            # 这里的 get_output 可以在语言包里写：“本群未绑定角色，无法执行 Push。”
            yield event.plain_result(get_output("pc.push.no_pc"))
            return

        is_global_mode = (mode or "").lower() in ("global", "g", "全局")
        if is_global_mode:
            if charmod.mark_character_global(group_id, user_id, chara_id):
                yield event.plain_result(get_output("pc.push.global_success"))
            else:
                yield event.plain_result(get_output("pc.push.fail"))
            return

        is_local_mode = (mode or "").lower() in ("local", "unglobal", "un-global", "取消全局", "本地")
        if is_local_mode:
            if charmod.unmark_character_global(group_id, user_id, chara_id):
                yield event.plain_result(get_output("pc.push.local_success"))
            else:
                yield event.plain_result(get_output("pc.push.fail"))
            return

        # 2. 调用后端 touch 逻辑，刷新 mtime 并写入全域档案库
        if charmod.touch_character(group_id, user_id, chara_id):
            if charmod.is_global_character(user_id, chara_id):
                yield event.plain_result(get_output("pc.push.global_sync"))
            else:
                yield event.plain_result(get_output("pc.push.success"))
        else:
            yield event.plain_result(get_output("pc.push.fail"))

    # ----------------- .pc fetch -----------------
    @pc.command("fetch")
    async def pc_fetch_list(self, event):
        if not self._command_enabled(event):
            return
        user_id = str(event.get_sender_id())
        
        all_chars = charmod.get_all_universal_characters(user_id)
        self.uni_cache[user_id] = all_chars # 更新序号缓存
        
        if not all_chars:
            yield event.plain_result(get_output("pc.uni.no_pc"))
            return
            
        char_lines = []
        for i, char in enumerate(all_chars, 1):
            # 格式化显示时间
            logger.info(char)
            time_str = time.strftime("%m-%d %H:%M", time.localtime(char['mtime']))
            # 标记来源（如果是 Vault 则高亮）
            source_label = "全局" if char.get("global") else f"{char['group_id']}"
            
            char_lines.append(f"{i}. {char['name']} (最新来源:{source_label} | {time_str})")
        
        msg = "\n".join(char_lines)
        yield event.plain_result(get_output("pc.uni.success", msg=msg))

    # ----------------- .pc pull -----------------
    @pc.command("pull")
    async def pc_pull_character(self, event, index: int, mode: str = None):
        if not self._command_enabled(event):
            return
        user_id = str(event.get_sender_id())
        group_id = str(event.get_group_id())
        
        # 1. 获取包含 mtime 信息的最新全域列表
        all_chars = charmod.get_all_universal_characters(user_id)
        self.uni_cache[user_id] = all_chars
        
        cache = self.uni_cache.get(user_id)
        if not cache or index > len(cache) or index <= 0:
            yield event.plain_result(get_output("pc.pull.no_pc"))
            return
            
        target = cache[index-1] # 这是全域中最热/最新的那个版本信息
        target_uuid = target['uuid']
        global_mode = (mode or "").lower() in ("global", "g", "全局")
        target_is_global = bool(target.get("global")) or charmod.is_global_character(user_id, target_uuid)

        if global_mode:
            success = charmod.mark_character_global(target["group_id"], user_id, target_uuid)
            if success:
                charmod.set_binding_info(user_id, group_id, target_uuid, global_binding=True)
                yield event.plain_result(get_output("pc.pull.global_success", name=target["name"]))
            else:
                yield event.plain_result(get_output("pc.pull.fail"))
            return

        if target_is_global:
            charmod.set_binding_info(user_id, group_id, target_uuid, global_binding=True)
            yield event.plain_result(get_output("pc.pull.global_success", name=target["name"]))
            return

        # 2. 获取本群当前该角色的信息（如果存在）
        local_exists = charmod.check_character_file_exists(group_id, user_id, target_uuid)
        
        needs_copy = True
        if local_exists:
            # 获取本地文件的修改时间进行对比
            local_mtime = charmod.get_local_file_mtime(group_id, user_id, target_uuid)
            # 如果本地的时间 >= 全域最热的时间，说明本地已经是最新，无需拷贝
            if local_mtime >= target['mtime']:
                needs_copy = False

        # 3. 执行逻辑分支
        if not needs_copy:
            # 文件已经是最新，仅检查绑定
            current_bound = charmod.get_current_character_id(group_id, user_id)
            if current_bound == target_uuid:
                yield event.plain_result(get_output("pc.pull.exist")) # 完全一致，无需操作
            else:
                charmod.set_binding_info(user_id, group_id, target_uuid, local_binding=True)
                yield event.plain_result(get_output("pc.pull.success", name=target['name']))
            return

        # 4. 需要拷贝（本地不存在，或者远程版本更新）
        # 调用 clone，内部执行物理覆盖
        success = charmod.clone_character_to_group(user_id, target['group_id'], group_id, target_uuid)
        
        if success:
            charmod.set_binding_info(user_id, group_id, target_uuid, local_binding=True)
            if local_exists : 
                yield event.plain_result(get_output("pc.pull.sync", name=target['name']))
            else :
                yield event.plain_result(get_output("pc.pull.success", name=target['name']))
        else:
            yield event.plain_result(get_output("pc.pull.fail"))

    # ----------------- filter sn -----------------
    async def _set_nickname_impl(self, event, mode: str = "coc"):
        if event.get_platform_name() != "aiocqhttp":
            yield event.plain_result(get_output("nick.platform_unsupported"))
            return

        from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent # type: ignore
        client = event.bot
        user_id = event.get_sender_id()
        group_id = event.get_group_id()

        chara_id = charmod.get_current_character_id(group_id, user_id)
        chara_data = charmod.load_character(group_id, user_id, chara_id)
        if not chara_data:
            yield event.plain_result(get_output("nick.no_character", id=chara_id))
            return

        new_card = build_card_by_mode(chara_data, mode)

        payloads = {"group_id": group_id, "user_id": user_id, "card": new_card}
        await client.api.call_action("set_group_card", **payloads)

        yield event.plain_result(get_output("nick.success"))

    @filter.command("sn")
    async def filter_set_nickname(self, event, mode: str = "coc"):
        if not self._command_enabled(event):
            return
        async for result in self._set_nickname_impl(event, mode):
            yield result

    @filter.command("nn")
    async def filter_set_nickname_dice_compat(self, event, mode: str = "coc"):
        if not self._command_enabled(event):
            return
        async for result in self._set_nickname_impl(event, mode):
            yield result
        
        
    async def _update_user_nickname_card(self, client, group_id: str, user_id: str):
        """静默更新玩家群名片，不返回任何群消息提示"""
        chara_id = charmod.get_current_character_id(group_id, user_id)
        if not chara_id:
            return False
            
        chara_data = charmod.load_character(group_id, user_id, chara_id)
        if not chara_data:
            return False

        new_card = build_coc_card(chara_data)
        payloads = {"group_id": group_id, "user_id": user_id, "card": new_card}
        
        try:
            await client.api.call_action("set_group_card", **payloads)
            return True
        except Exception as e:
            logger.error(f"自动更新群名片失败: {e}")
            return False

    
    # ========================================================= #
    def _resolve_skill_check(self, group_id, user_id, skill_name: str, skill_value: str = None):
        skill_name = self._resolve_user_alias(str(user_id), skill_name)
        if (skill_value is None or skill_value == "") and skill_name:
            explicit_match = re.match(r"^(.+?)(\d+)([+-]\d+)?$", skill_name.strip())
            if explicit_match:
                skill_name = explicit_match.group(1) + (explicit_match.group(3) or "")
                skill_value = explicit_match.group(2)

        lookup_name = skill_name or ""
        _, lookup_name = parse_difficulty_prefix(lookup_name)
        lookup_name, _ = split_skill_modifier(lookup_name)

        raw_value = skill_value
        if raw_value is None or raw_value == "":
            raw_value = charmod.get_skill_value(group_id, user_id, lookup_name)

        try:
            numeric_value = int(raw_value)
        except (TypeError, ValueError):
            return skill_name, raw_value

        if not skill_name:
            skill_name = str(numeric_value)
        return prepare_skill_check(skill_name, numeric_value)

    async def roll_attribute(self, event: AstrMessageEvent, skill_name: str, skill_value: str = None, roll_times = 1, target_user_id: str = None):
        group_id = event.get_group_id()
        # 决定最终查询的 user_id
        actual_user_id = target_user_id if target_user_id else event.get_sender_id()

        skill_name, skill_value = self._resolve_skill_check(group_id, actual_user_id, skill_name, skill_value)

        client = event.bot
        
        # 获取目标的名字
        ret = await get_sender_nickname(client, group_id, actual_user_id)
        if ret == "":
            ret = event.get_sender_name() if actual_user_id == event.get_sender_id() else str(actual_user_id)
            
        # 如果是代投，在名字上做个小标记
        if target_user_id and target_user_id != event.get_sender_id():
            ret = f"{ret} (由 <{event.get_sender_name()}> 代投)"

        logger.info(ret)
        
        result_message = dice_mod.roll_attribute(roll_times, skill_name, skill_value, str(group_id), ret)

        payloads = {
            "group_id": group_id,
            "message": [
                {"type": "reply", "data": {"id": event.message_obj.message_id}},
                # 依然 @ 触发指令的人，提醒他结果出来了
                {"type": "at", "data": {"qq": event.get_sender_id()}}, 
                {"type": "text", "data": {"text": "\n" + result_message}}
            ]
        }
        await self.save_log(group_id = event.get_group_id(), content = result_message)
        await client.api.call_action("send_group_msg", **payloads)

    async def roll_attribute_until_success(self, event: AstrMessageEvent, skill_name: str = "", skill_value: str = None, target_user_id: str = None):
        group_id = event.get_group_id()
        actual_user_id = target_user_id if target_user_id else event.get_sender_id()
        skill_name, skill_value = self._resolve_skill_check(group_id, actual_user_id, skill_name, skill_value)

        client = event.bot
        ret = await get_sender_nickname(client, group_id, actual_user_id)
        if ret == "":
            ret = event.get_sender_name() if actual_user_id == event.get_sender_id() else str(actual_user_id)
        if target_user_id and target_user_id != event.get_sender_id():
            ret = f"{ret} (由 <{event.get_sender_name()}> 代投)"

        result_message = dice_mod.roll_attribute_until_success(skill_name, skill_value, str(group_id), ret)
        payloads = {
            "group_id": group_id,
            "message": [
                {"type": "reply", "data": {"id": event.message_obj.message_id}},
                {"type": "at", "data": {"qq": event.get_sender_id()}},
                {"type": "text", "data": {"text": "\n" + result_message}}
            ]
        }
        await self.save_log(group_id=group_id, content=result_message)
        await client.api.call_action("send_group_msg", **payloads)

    # 惩罚骰技能判定
    async def roll_attribute_penalty(self, event: AstrMessageEvent, dice_count: str = "1", skill_name: str = "", skill_value: str = None, roll_times = 1, target_user_id: str = None):
        group_id = event.get_group_id()
        actual_user_id = target_user_id if target_user_id else event.get_sender_id()

        skill_name, skill_value = self._resolve_skill_check(group_id, actual_user_id, skill_name, skill_value)

        client = event.bot
        ret = await get_sender_nickname(client, group_id, actual_user_id)
        if ret == "":
            ret = event.get_sender_name() if actual_user_id == event.get_sender_id() else str(actual_user_id)
            
        if target_user_id and target_user_id != event.get_sender_id():
            ret = f"{ret} (由 <{event.get_sender_name()}> 代投)"

        result_message = dice_mod.roll_attribute_penalty(roll_times, dice_count, skill_name, skill_value, str(group_id), ret)

        payloads = {
            "group_id": group_id,
            "message": [
                {"type": "reply", "data": {"id": event.message_obj.message_id}},
                {"type": "at", "data": {"qq": event.get_sender_id()}},
                {"type": "text", "data": {"text": "\n" + result_message}}
            ]
        }

        await self.save_log(group_id = event.get_group_id(), content = result_message)
        await client.api.call_action("send_group_msg", **payloads)

    # 奖励骰技能判定
    async def roll_attribute_bonus(self, event: AstrMessageEvent, dice_count: str = "1", skill_name: str = "", skill_value: str = None, roll_times = 1, target_user_id: str = None):
        group_id = event.get_group_id()
        actual_user_id = target_user_id if target_user_id else event.get_sender_id()

        skill_name, skill_value = self._resolve_skill_check(group_id, actual_user_id, skill_name, skill_value)

        client = event.bot
        ret = await get_sender_nickname(client, group_id, actual_user_id)
        if ret == "":
            ret = event.get_sender_name() if actual_user_id == event.get_sender_id() else str(actual_user_id)
            
        if target_user_id and target_user_id != event.get_sender_id():
            ret = f"{ret} (由 <{event.get_sender_name()}> 代投)"

        result_message = dice_mod.roll_attribute_bonus(roll_times, dice_count, skill_name, skill_value, str(group_id), ret)

        payloads = {
            "group_id": group_id,
            "message": [
                {"type": "reply", "data": {"id": event.message_obj.message_id}},
                {"type": "at", "data": {"qq": event.get_sender_id()}},
                {"type": "text", "data": {"text": "\n" + result_message}}
            ]
        }

        await self.save_log(group_id = event.get_group_id(), content = result_message)
        await client.api.call_action("send_group_msg", **payloads)

    async def roll_attribute_hidden(self, event: AstrMessageEvent, skill_name: str = "", skill_value: str = None, roll_times = 1, target_user_id: str = None):
        group_id = event.get_group_id()
        actual_user_id = target_user_id if target_user_id else event.get_sender_id()
        skill_name, skill_value = self._resolve_skill_check(group_id, actual_user_id, skill_name, skill_value)

        client = event.bot
        ret = await get_sender_nickname(client, group_id, actual_user_id)
        if ret == "":
            ret = event.get_sender_name() if actual_user_id == event.get_sender_id() else str(actual_user_id)
        if target_user_id and target_user_id != event.get_sender_id():
            ret = f"{ret} (由 <{event.get_sender_name()}> 代投)"

        result_message = dice_mod.roll_attribute(roll_times, skill_name, skill_value, str(group_id), ret)
        await self.save_log(group_id=group_id, content="[Hidden Skill Check]" + result_message)

        yield event.plain_result("进行了一次暗中检定，结果已通过私聊发送。")
        await client.api.call_action(
            "send_private_msg",
            user_id=event.get_sender_id(),
            message=[{"type": "text", "data": {"text": result_message}}],
        )

    def _get_at_user_ids(self, event: AstrMessageEvent) -> list[str]:
        return [
            str(comp.qq)
            for comp in getattr(event.message_obj, "message", [])
            if isinstance(comp, Comp.At)
        ]

    async def roll_attribute_versus(self, event: AstrMessageEvent, expr: str, skill_value: str = None, target_user_id: str = None):
        group_id = event.get_group_id()
        spec = parse_versus_check(expr)
        if spec is None:
            yield event.plain_result("对抗检定格式错误：请使用 .rav技能名a点数/b点数，或 .rav技能名 @对抗者")
            return

        at_user_ids = self._get_at_user_ids(event)
        opponent_user_id = at_user_ids[0] if at_user_ids else None
        if not opponent_user_id and target_user_id and str(target_user_id) != str(event.get_sender_id()):
            opponent_user_id = str(target_user_id)

        left_skill_name, left_value = self._resolve_skill_check(
            group_id,
            event.get_sender_id(),
            spec.skill_name,
            spec.left_value or skill_value,
        )

        if spec.explicit_right:
            right_skill_name, right_value = self._resolve_skill_check(group_id, event.get_sender_id(), spec.skill_name, spec.right_value)
            left_label = event.get_sender_name() or "发起方"
            right_label = "对抗方"
        elif opponent_user_id:
            right_skill_name, right_value = self._resolve_skill_check(group_id, opponent_user_id, spec.skill_name, None)
            left_label = event.get_sender_name() or str(event.get_sender_id())
            try:
                right_label = await get_sender_nickname(event.bot, group_id, opponent_user_id) or str(opponent_user_id)
            except Exception:
                right_label = str(opponent_user_id)
        else:
            yield event.plain_result("对抗检定格式错误：请提供 /b点数，或 @一名对抗者。")
            return

        try:
            left_value = int(left_value)
            right_value = int(right_value)
        except (TypeError, ValueError):
            yield event.plain_result("对抗检定格式错误：双方都需要可解析的技能值；a点数可省略，b点数或@对抗者不能省略。")
            return

        left_name = f"<{left_label}> 的【{left_skill_name}】"
        right_name = f"<{right_label}> 的【{right_skill_name}】"
        result_message = dice_mod.roll_opposed_check(left_name, left_value, right_name, right_value, str(group_id))
        await self.save_log(group_id=group_id, content=result_message)
        yield event.plain_result(result_message)

        
    # @filter.command("en")
    async def pc_grow_up(self, event: AstrMessageEvent, skill_name: str, skill_value: str = None, target_user_id: str = None):
        """
        .en 技能成长判定
        调用 character 模块的 grow_up 生成结果文本，再通过 event 发送给用户。
        """
        user_id = target_user_id or event.get_sender_id()
        group_id = event.get_group_id()
        skill_name = self._resolve_user_alias(str(user_id), skill_name)

        # 调用 character.py 中同步逻辑函数，不传入额外函数引用
        result_str = charmod.grow_up(
            group_id,
            user_id,
            skill_name=skill_name,
            skill_value=skill_value
        )

        # 构造发送消息

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
    async def pc_san_check(self, event: AstrMessageEvent, loss_formula: str, target_user_id: str = None):
        """理智检定"""
        user_id = target_user_id or event.get_sender_id()
        operator_user_id = str(event.get_sender_id())
        group_id = event.get_group_id()
        chara_data = charmod.get_current_character(group_id, user_id)
        client = event.bot
        
        if not chara_data:
            if str(user_id) == operator_user_id:
                yield event.plain_result(get_output("pc.show.no_active"))
            else:
                yield event.plain_result("该玩家尚未在当前群组绑定人物卡哦。")
            return

        roll_result, san_value, result_msg, loss, new_san, expr = sanity.san_check(chara_data, loss_formula)

        # 更新人物卡
        chara_data["attributes"]["san"] = new_san
        charmod.save_character(group_id, user_id, chara_data["id"], chara_data)
        
        if event.get_platform_name() == "aiocqhttp":
            await self._update_user_nickname_card(client, group_id, user_id)

        if new_san == 0 :
            text = get_output(
                    "san.check_result.zero",
                    name=chara_data["name"],
                    roll_result=roll_result,
                    san_value=san_value,
                    result_msg=result_msg,
                    loss=loss,
                    new_san=new_san,
                    expr = expr
                )

        elif loss == 0 :
            text = get_output(
                "san.check_result.no_loss",
                name=chara_data["name"],
                roll_result=roll_result,
                san_value=san_value,
                result_msg=result_msg,
                loss=loss,
                new_san=new_san,
                expr = expr
            )
        elif loss < 5 :
            text = get_output(
                "san.check_result.loss",
                name=chara_data["name"],
                roll_result=roll_result,
                san_value=san_value,
                result_msg=result_msg,
                loss=loss,
                new_san=new_san,
                expr = expr
            )
        else :
            text = get_output(
                "san.check_result.great_loss",
                name=chara_data["name"],
                roll_result=roll_result,
                san_value=san_value,
                result_msg=result_msg,
                loss=loss,
                new_san=new_san,
                expr = expr
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
        text = get_output("san.temporary_insanity", result=result, name=event.get_sender_name())
        await self.save_log(group_id = event.get_group_id(), content = text)
        yield event.plain_result(text)


    async def pc_long_term_insanity(self, event: AstrMessageEvent):
        """长期疯狂"""
        result = sanity.get_long_term_insanity(sanity.phobias, sanity.manias)
        text = get_output("san.long_term_insanity", result=result, name=event.get_sender_name())
        await self.save_log(group_id = event.get_group_id(), content = text)
        yield event.plain_result(text)


    @filter.command("init")
    async def initiative(self , event: AstrMessageEvent , instruction: str = None, player_name: str = None):
        if not self._command_enabled(event):
            return
        group_id = event.get_group_id()
        user_name = event.get_sender_name()
        if not instruction:
            yield event.plain_result("当前先攻列表为：\n" + self.initiative_manager.format_list(group_id))
        elif instruction == "clr":
            self.initiative_manager.clear(group_id)
            yield event.plain_result("已清空先攻列表")
        elif instruction == "del":
            if not player_name:
                player_name = user_name
            self.initiative_manager.remove_by_name(group_id, player_name)
            yield event.plain_result(f"已删除角色{player_name}的先攻")

    # @filter.command("ri")
    async def roll_initiative(self , event: AstrMessageEvent, expr: str = None):

        group_id = event.get_group_id()
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()

        init_value, player_name = self.initiative_manager.parse_roll(expr, user_name)
        item = InitiativeItem(player_name, init_value, user_id)
        self.initiative_manager.remove_by_name(group_id, player_name)
        self.initiative_manager.add_item(group_id, item)
        yield event.plain_result(f"已添加/更新{player_name}的先攻：{init_value}")
        async for result in self.initiative(event):
            yield result
        return

    @filter.command("ed")
    async def end_current_round(self , event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        group_id = event.get_group_id()
        current_item = self.initiative_manager.current_turn(group_id)
        next_item = self.initiative_manager.next_turn(group_id)
        if not next_item:
            yield event.plain_result("先攻列表为空，无法推进回合")
        elif current_item is None:
            yield event.plain_result(f"{next_item.name}的回合开始(先攻: {next_item.init_value})")
        else:
            yield event.plain_result(f"{current_item.name}的回合结束 ->\n {next_item.name}的回合(先攻: {next_item.init_value})")
        return

    
    # ========================================================= #

    @filter.command("name")
    async def generate_name(self, event: AstrMessageEvent, language: str = "cn", num: int = 5, sex: str = None):
        if not self._command_enabled(event):
            return
        names = generate_names(language=language, num=num, sex=sex)
        yield event.plain_result(get_output("generated_names", num = num, names=", ".join(names)))

    # ------------------ CoC角色生成 ------------------ #
    async def generate_coc_character(self, event: AstrMessageEvent, x: int = 1):
        if not self._command_enabled(event):
            return
        x = max(1, min(int(x), 10))
        characters = [roll_character() for _ in range(x)]
        results = []
        for i, char in enumerate(characters):
            results.append(format_character(char, index=i+1))
        yield event.plain_result(get_output("character_list.coc", characters="\n\n".join(results)))

    # ------------------ DnD角色生成 ------------------ #
    async def generate_dnd_character(self, event: AstrMessageEvent, x: int = 1):
        if not self._command_enabled(event):
            return
        x = max(1, min(int(x), 10))
        characters = [roll_dnd_character() for _ in range(x)]
        results = []
        for i, char in enumerate(characters):
            results.append(format_dnd_character(char, index=i+1))
        yield event.plain_result(get_output("character_list.dnd", characters="\n\n".join(results)))

    @filter.command("ob")
    async def toggle_ob_mode(self, event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        group = event.message_obj.group_id
        user_id = str(event.get_sender_id())
        nickname = event.get_sender_name()
        try:
            nickname = await get_sender_nickname(event.bot, group, user_id) or nickname
        except Exception:
            pass
        ok, info = await logger_core.toggle_observer(group, user_id, nickname)
        yield event.plain_result(info)
        
    # ======================== LOG相关 ============================= #
    @filter.command_group("log")
    async def log(event: AstrMessageEvent):
        pass


    @log.command("new")
    async def cmd_log_new(self, event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        group = event.message_obj.group_id
        parts = event.message_str.strip().split()
        name = parts[2] if len(parts) >= 3 else None
        ok, info = await logger_core.new_session(group, name)
        return event.plain_result(info)


    @log.command("end")
    async def cmd_log_end(self, event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        group = event.message_obj.group_id
        ok, info = await logger_core.end_session(group)
        return event.plain_result(info)


    @log.command("off")
    async def cmd_log_off(self, event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        group = event.message_obj.group_id
        ok, info = await logger_core.pause_sessions(group)
        return event.plain_result(info)


    @log.command("on")
    async def cmd_log_on(self, event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        group = event.message_obj.group_id
        parts = event.message_str.strip().split()
        name = parts[2] if len(parts) >= 3 else None
        ok, info = await logger_core.resume_session(group, name)
        return event.plain_result(info)


    @log.command("list")
    async def cmd_log_list(self, event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        group = event.message_obj.group_id
        lines = await logger_core.list_sessions(group)
        return event.plain_result("\n".join(lines))


    @log.command("del")
    async def cmd_log_del(self, event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        group = event.message_obj.group_id
        parts = event.message_str.strip().split()
        if len(parts) < 3:
            return event.plain_result(get_output("log.delete_error"))
        name = parts[2]
        ok, info = await logger_core.delete_session(group, name)
        return event.plain_result(info)


    @log.command("get")
    async def cmd_log_get(self, event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        
        group = event.message_obj.group_id
        parts = event.message_str.strip().split()
        if len(parts) < 3:
            return event.plain_result("指令错误：请使用 .log get <日志名>")

        name = parts[2]
        grp = await logger_core.load_group(group)
        sec = grp.get(name)

        logger.info(f"{name}, {group}")

        if not sec:
            return event.plain_result(get_output("log.session_not_found", session_name=name))

        info = await logger_core.export_session(group, sec, name)
        
        return event.plain_result(info)

    @log.command("export")
    async def cmd_log_export(self, event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        group = event.message_obj.group_id
        parts = event.message_str.strip().split()
        if len(parts) < 3:
            return event.plain_result("指令错误：请使用 .log export <日志名> 或 .log export text <日志名>")

        if parts[2].lower() in {"text", "txt"}:
            if len(parts) < 4:
                return event.plain_result("指令错误：请使用 .log export text <日志名>")
            info = await logger_core.export_session_text(group, parts[3])
            return event.plain_result(info)

        name = parts[2]
        grp = await logger_core.load_group(group)
        sec = grp.get(name)
        if not sec:
            return event.plain_result(get_output("log.session_not_found", session_name=name))

        info = await logger_core.export_session(group, sec, name)
        return event.plain_result(info)


    @log.command("stat")
    async def cmd_log_stat(self, event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        group = event.message_obj.group_id
        parts = event.message_str.strip().split()
        name = parts[2] if len(parts) >= 3 else None
        all_flag = len(parts) >= 4 and parts[3] == "--all"
        lines = await logger_core.stat_sessions(group, name, all_flag)
        return event.plain_result("\n".join(lines))

    @log.command("ob")
    async def cmd_log_ob(self, event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        group = event.message_obj.group_id
        parts = event.message_str.strip().split()
        action = parts[2].lower() if len(parts) >= 3 else "list"
        session_name = parts[-1] if len(parts) >= 5 and not parts[-1].isdigit() else None

        if action in {"list", "ls"}:
            name = parts[3] if len(parts) >= 4 else None
            lines = await logger_core.list_observers(group, name)
            return event.plain_result("\n".join(lines))

        if action == "clear":
            ok, info = await logger_core.clear_observers(group, session_name)
            return event.plain_result(info)

        if action not in {"add", "del", "remove", "rm"}:
            return event.plain_result("指令错误：请使用 .log ob add/del/list/clear [@用户|QQ号]")

        targets = []
        for comp in getattr(event.message_obj, "message", []):
            if isinstance(comp, Comp.At):
                targets.append(str(comp.qq))

        if not targets and len(parts) >= 4:
            targets.append(parts[3])

        if not targets:
            return event.plain_result("请指定 OB 用户，例如 .log ob add @某人")

        enabled = action == "add"
        results = []
        for target in targets:
            nickname = target
            try:
                nickname = await get_sender_nickname(event.bot, group, target) or target
            except Exception:
                pass
            ok, info = await logger_core.set_observer(group, target, nickname, session_name, enabled)
            results.append(info)

        return event.plain_result("\n".join(results))
    # ======================== LOG相关 ============================= #
    
    # 注册指令 /dicehelp
    @filter.command("bothelp")
    async def help ( self , event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        help_text = (
        "要让风铃带你们跑团吗？那要好好学习怎么跑团呀。"
        "基础掷骰教程：.dicehelp roll\n"
        "进阶掷骰表达式：.dicehelp expr\n"
        "人物卡管理: .dicehelp pc\n"
        "属性值管理：.dicehelp st\n"
        "记录管理：.dicehelp log\n"
        "其余杂项指令：.dicehelp coc\n"
        
        "DnD 相关: .dicehelp dnd\n"

        "其他规则\n"
        "`/rv 骰子数量 难度` - 进行吸血鬼规则掷骰判定\n"
        )

        yield event.plain_result(help_text)
        
    @command_group("dicehelp")
    async def dicehelp(self, event : AstrMessageEvent) :
        pass

    @dicehelp.command("roll")
    async def help_roll ( self , event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        yield event.plain_result(get_output("help.dice"))
        
    @dicehelp.command("expr")
    async def help_expr ( self , event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        yield event.plain_result(get_output("help.expr"))
        
    @dicehelp.command("pc")
    async def help_pc ( self , event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        yield event.plain_result(get_output("help.pc"))
        
    @dicehelp.command("st")
    async def help_st ( self , event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        yield event.plain_result(get_output("help.st"))

    @dicehelp.command("log")
    async def help_log ( self , event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        yield event.plain_result(get_output("help.log"))
        
    @dicehelp.command("coc")
    async def help_coc ( self , event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        yield event.plain_result(get_output("help.coc"))
        
    @dicehelp.command("dnd")
    async def help_dnd ( self , event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        yield event.plain_result(get_output("help.dnd"))
        
    @filter.command("fireball")
    async def fireball_cmd(self, event: AstrMessageEvent, ring: int = 3):
        if not self._command_enabled(event):
            return
        result = dice_mod.fireball(ring)
        yield event.plain_result(result)

    @filter.command("jrrp")
    async def roll_RP_cmd(self, event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        user_id = event.get_sender_id()
        result = dice_mod.roll_RP(user_id)
        yield event.plain_result(result)

    @filter.command("d66")
    async def roll_d66_cmd(self, event: AstrMessageEvent, count: int = 1):
        if not self._command_enabled(event):
            return
        yield event.plain_result(dice_mod.roll_d66(count))

    async def _choose_impl(self, event: AstrMessageEvent, args_str: str = ""):
        if not self._command_enabled(event):
            return
        yield event.plain_result(dice_mod.choose_option(args_str))

    @filter.command("choose")
    async def choose_cmd(self, event: AstrMessageEvent, *, args_str: str = ""):
        async for result in self._choose_impl(event, args_str):
            yield result

    @filter.command("choice")
    async def choice_cmd(self, event: AstrMessageEvent, *, args_str: str = ""):
        async for result in self._choose_impl(event, args_str):
            yield result

    @filter.command_group("alias")
    async def alias(self, event: AstrMessageEvent):
        pass

    @alias.command("add")
    async def alias_add_cmd(self, event: AstrMessageEvent, alias_name: str, target_name: str):
        if not self._command_enabled(event):
            return
        user_id = str(event.get_sender_id())
        aliases = self._get_user_aliases(user_id)
        aliases[alias_name] = target_name
        self._save_user_aliases(user_id, aliases)
        yield event.plain_result(f"已记录别名：{alias_name} -> {target_name}")

    @alias.command("del")
    async def alias_del_cmd(self, event: AstrMessageEvent, alias_name: str):
        if not self._command_enabled(event):
            return
        user_id = str(event.get_sender_id())
        aliases = self._get_user_aliases(user_id)
        if alias_name not in aliases:
            yield event.plain_result(f"没有找到别名：{alias_name}")
            return
        aliases.pop(alias_name, None)
        self._save_user_aliases(user_id, aliases)
        yield event.plain_result(f"已删除别名：{alias_name}")

    @alias.command("list")
    async def alias_list_cmd(self, event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        aliases = self._get_user_aliases(str(event.get_sender_id()))
        if not aliases:
            yield event.plain_result("还没有设置技能别名。")
            return
        lines = [f"{alias_name} -> {target_name}" for alias_name, target_name in sorted(aliases.items())]
        yield event.plain_result("技能别名：\n" + "\n".join(lines))

    @filter.command("bot")
    async def bot_cmd(self, event: AstrMessageEvent, action: str = None):
        action = (action or "").lower()
        if not action:
            image_path = self._bot_image_path()
            if image_path:
                yield event.chain_result([
                    Image.fromFileSystem(image_path),
                    Plain(self._bot_info_text(event)),
                ])
            else:
                yield event.plain_result(self._bot_info_text(event))
            return

        group_id = self._group_id(event)
        settings = self._get_group_settings(group_id)

        if action == "on":
            settings["enabled"] = True
            self._save_group_settings(group_id, settings)
            yield event.plain_result("骰子功能已开启。")
            return

        if action == "off":
            settings["enabled"] = False
            self._save_group_settings(group_id, settings)
            yield event.plain_result("骰子功能已关闭。使用 .bot on 可以重新开启。")
            return

        if action == "status":
            enabled = self._is_bot_enabled(event.get_group_id())
            yield event.plain_result("骰子功能当前：" + ("开启" if enabled else "关闭"))
            return

        yield event.plain_result("用法：.bot / .bot on / .bot off / .bot status")

    @filter.command("setcoc")
    async def setcoc_cmd(self, event: AstrMessageEvent, command: str = " "):
        if not self._command_enabled(event):
            return
        group_id = event.get_group_id()
        result = modify_coc_great_sf_rule_command(group_id, command)
        yield event.plain_result(result)

    
    # 识别所有信息
    async def _dispatch_inline_command(self, event: AstrMessageEvent, parsed, target_user_id: str):
        cmd = parsed.cmd
        expr = parsed.expr
        remark = parsed.remark
        skill_value = parsed.skill_value
        dice_count = parsed.dice_count
        roll_times = parsed.roll_times

        if cmd == "r":
            await self.handle_roll_dice(event, expr, remark)
        elif cmd == "rd":
            await self.handle_roll_dice(event, expr, remark)
        elif cmd == "rh":
            async for result in self.roll_hidden(event, expr):
                yield result
        elif cmd == "rab":
            await self.roll_attribute_bonus(event, dice_count, expr, skill_value, roll_times, target_user_id)
        elif cmd == "rap":
            await self.roll_attribute_penalty(event, dice_count, expr, skill_value, roll_times, target_user_id)
        elif cmd == "rau":
            await self.roll_attribute_until_success(event, expr, skill_value, target_user_id)
        elif cmd == "ra":
            await self.roll_attribute(event, expr, skill_value, roll_times, target_user_id)
        elif cmd == "rc":
            await self.roll_attribute(event, expr, skill_value, roll_times, target_user_id)
        elif cmd in {"rah", "rch"}:
            async for result in self.roll_attribute_hidden(event, expr, skill_value, roll_times, target_user_id):
                yield result
        elif cmd in {"rav", "rcv"}:
            async for result in self.roll_attribute_versus(event, expr, skill_value, target_user_id):
                yield result
        elif cmd == "en":
            await self.pc_grow_up(event, expr, skill_value, target_user_id)
        elif cmd == "sc":
            async for result in self.pc_san_check(event, expr, target_user_id):
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
        elif cmd == "coc":
            count = int(expr) if str(expr).isdigit() else 1
            async for result in self.generate_coc_character(event, count):
                yield result
        elif cmd == "dnd":
            count = int(expr) if str(expr).isdigit() else 1
            async for result in self.generate_dnd_character(event, count):
                yield result

    async def _dispatch_private_inline_command(self, event: AstrMessageEvent, parsed):
        cmd = parsed.cmd
        expr = parsed.expr
        remark = parsed.remark
        skill_value = parsed.skill_value
        dice_count = parsed.dice_count
        roll_times = parsed.roll_times
        context_id = self._event_context_id(event)
        user_id = event.get_sender_id()
        name = await self._event_display_name(event, user_id)

        if cmd in {"r", "rd"}:
            result = dice_mod.handle_roll_dice(
                expr if expr else f"1d{dice_mod.DEFAULT_DICE}",
                name=name,
                remark=remark,
            )
            yield event.plain_result(result)
        elif cmd == "rh":
            yield event.plain_result(dice_mod.roll_hidden(expr))
        elif cmd in {"ra", "rc"}:
            skill_name, resolved_value = self._resolve_skill_check(context_id, user_id, expr, skill_value)
            result = dice_mod.roll_attribute(roll_times, skill_name, resolved_value, context_id, name)
            yield event.plain_result(result)
        elif cmd == "rab":
            skill_name, resolved_value = self._resolve_skill_check(context_id, user_id, expr, skill_value)
            result = dice_mod.roll_attribute_bonus(roll_times, dice_count, skill_name, resolved_value, context_id, name)
            yield event.plain_result(result)
        elif cmd == "rap":
            skill_name, resolved_value = self._resolve_skill_check(context_id, user_id, expr, skill_value)
            result = dice_mod.roll_attribute_penalty(roll_times, dice_count, skill_name, resolved_value, context_id, name)
            yield event.plain_result(result)
        elif cmd == "rau":
            skill_name, resolved_value = self._resolve_skill_check(context_id, user_id, expr, skill_value)
            result = dice_mod.roll_attribute_until_success(skill_name, resolved_value, context_id, name)
            yield event.plain_result(result)
        elif cmd in {"rah", "rch"}:
            skill_name, resolved_value = self._resolve_skill_check(context_id, user_id, expr, skill_value)
            result = dice_mod.roll_attribute(roll_times, skill_name, resolved_value, context_id, name)
            yield event.plain_result(result)
        elif cmd in {"rav", "rcv"}:
            async for result in self.roll_attribute_versus(event, expr, skill_value):
                yield result
        elif cmd == "en":
            yield event.plain_result(charmod.grow_up(context_id, user_id, skill_name=expr, skill_value=skill_value))
        elif cmd == "sc":
            chara_data = charmod.get_current_character(context_id, user_id)
            if not chara_data:
                yield event.plain_result(get_output("pc.show.no_active"))
                return

            roll_result, san_value, result_msg, loss, new_san, parsed_expr = sanity.san_check(chara_data, expr)
            chara_data["attributes"]["san"] = new_san
            charmod.save_character(context_id, user_id, chara_data["id"], chara_data)

            if new_san == 0:
                output_key = "san.check_result.zero"
            elif loss == 0:
                output_key = "san.check_result.no_loss"
            elif loss < 5:
                output_key = "san.check_result.loss"
            else:
                output_key = "san.check_result.great_loss"

            yield event.plain_result(get_output(
                output_key,
                name=chara_data["name"],
                roll_result=roll_result,
                san_value=san_value,
                result_msg=result_msg,
                loss=loss,
                new_san=new_san,
                expr=parsed_expr,
            ))
        elif cmd == "li":
            async for result in self.pc_long_term_insanity(event):
                yield result
        elif cmd == "ti":
            async for result in self.pc_temporary_insanity(event):
                yield result
        elif cmd == "coc":
            count = int(expr) if str(expr).isdigit() else 1
            async for result in self.generate_coc_character(event, count):
                yield result
        elif cmd == "dnd":
            count = int(expr) if str(expr).isdigit() else 1
            async for result in self.generate_dnd_character(event, count):
                yield result
        else:
            yield event.plain_result("该指令暂不支持私聊。")

    async def _record_group_message(self, event: AstrMessageEvent, message: str):
        group_id = event.message_obj.group_id
        if not group_id:
            return

        await logger_core.add_message(
            group_id=group_id,
            user_id=event.message_obj.sender.user_id,
            nickname=getattr(event.message_obj.sender, "nickname", ""),
            timestamp=int(event.message_obj.timestamp),
            text=message,
            components=getattr(event.message_obj, "message", [])
        )

    @event_message_type(EventMessageType.GROUP_MESSAGE, priority=sys.maxsize)
    async def identify_command(self, event: AstrMessageEvent):

        message = event.message_obj.message_str
        await self._record_group_message(event, message)

        target_user_id = self._get_target_user_id(event)

        # 在保留完整日志后，把文本里的 CQ 码和 @ 残留抹掉，
        # 确保它们绝对不会掉进下面那个“诡异”的正则解析器里
        message = self._strip_at_text(message)

        # logger.info(f"{message}, {target_user_id}")

        # yield event.plain_result(message)

        random.seed(int(time.time() * 1000))

        command_text = strip_command_prefix(message, self.wakeup_prefix)
        if command_text is None:
            return

        parsed = parse_inline_command(command_text)
        if parsed is None:
            return

        async for result in self._dispatch_inline_command(event, parsed, target_user_id):
            yield result
        return

    @event_message_type(EventMessageType.PRIVATE_MESSAGE)
    async def identify_private_command(self, event: AstrMessageEvent):
        message = event.message_obj.message_str

        random.seed(int(time.time() * 1000))

        command_text = strip_command_prefix(message, self.wakeup_prefix)
        if command_text is None:
            return

        if not self._is_bot_enabled(self._group_id(event)) and not command_text.lower().startswith("bot"):
            self._stop_event(event)
            return

        parsed = parse_inline_command(command_text)
        if parsed is None:
            return

        async for result in self._dispatch_private_inline_command(event, parsed):
            yield result
        return

    class SpellFeature:
        def __init__(self, spellname, spelllevel, spellschool, spellclasses, castingtime, spellrange, components, duration, description, source):
            self.spellname = spellname
            self.spelllevel = spelllevel
            self.spellschool = spellschool
            self.spellclasses = spellclasses
            self.castingtime = castingtime
            self.spellrange = spellrange
            self.components = components
            self.duration = duration
            self.description = description
            self.source = source

    @staticmethod
    def extract_spell_html(html_content, spell_name):
        safe_spell_name = re.escape(spell_name)
        sections = re.split(r'(?=<h4[^>]*>)', html_content, flags=re.IGNORECASE)
        
        for section in sections:
            header_match = re.search(r'^<h4[^>]*>(.*?)</h4>', section, flags=re.IGNORECASE | re.DOTALL)
            if header_match:
                header_text = header_match.group(1)
                if re.search(safe_spell_name, header_text, flags=re.IGNORECASE):
                    clean_section = re.sub(r'</?(html|body)[^>]*>\s*', '', section, flags=re.IGNORECASE).strip()
                    return clean_section
        return None

    def handle_spell_html(self, content: str, spellsource: str) -> SpellFeature:
        spellname_match = re.search(r"(<h4>(.*?)</h4>)", content, flags=re.IGNORECASE | re.DOTALL)
        spellname_with_header = spellname_match.group(1)  # 修正：用 group(1) 才能替换掉完整的 <h4>...</h4>
        spellname = spellname_match.group(2)

        spellcontent = content.replace(spellname_with_header, "")
        spellcontent_multiline = spellcontent.split("<BR>")

        # index 0 - spell belonging
        spellbelonging_match = re.search(r"<em>(.*?)环 (.*?)（(.*)）", spellcontent_multiline[0], flags=re.IGNORECASE | re.DOTALL)
        spelllevel = spellbelonging_match.group(1) if spellbelonging_match else "未知"
        spellschool = spellbelonging_match.group(2) if spellbelonging_match else "未知"
        spellclasses = spellbelonging_match.group(3) if spellbelonging_match else "未知"

        # index 1 - casting time
        castingtime_match = re.search(r"<(b|STRONG)>施法时间：<(/b|/STRONG)>(.*)", spellcontent_multiline[1], flags=re.IGNORECASE | re.DOTALL)
        castingtime = castingtime_match.group(3) if castingtime_match else ""

        # index 2 - range
        spellrange_match = re.search(r"<(b|STRONG)>施法距离：<(/b|/STRONG)>(.*)", spellcontent_multiline[2], flags=re.IGNORECASE | re.DOTALL)
        spellrange = spellrange_match.group(3) if spellrange_match else ""

        # index 3 - components
        components_match = re.search(r"<(b|STRONG)>法术成分：<(/b|/STRONG)>(.*)", spellcontent_multiline[3], flags=re.IGNORECASE | re.DOTALL)
        components = components_match.group(3) if components_match else ""

        # index 4 - duration
        duration_match = re.search(r"<(b|STRONG)>持续时间：<(/b|/STRONG)>(.*)", spellcontent_multiline[4], flags=re.IGNORECASE | re.DOTALL)
        duration = duration_match.group(3) if duration_match else ""

        # index 5+ - description
        spellcontent_length = len(spellcontent_multiline)
        description = ""
        for i in range(5, spellcontent_length):
            description += spellcontent_multiline[i]
            if i < spellcontent_length - 1: 
                description += "<BR>"
                
        return self.SpellFeature(spellname, spelllevel, spellschool, spellclasses, castingtime, spellrange, components, duration, description, spellsource)

    @staticmethod
    def spellfeature_to_html(res: SpellFeature) -> str:
        reference = "数据来自 DND5E不全书 2026.2.12版"
        sample_html = f"""
        <H4>{res.spellname}</H4>
        <em>{res.spelllevel}环 {res.spellschool}学派（{res.spellclasses}）</em>
        <p>
        <strong>施法时间：</strong>{res.castingtime}<br>
        <strong>施法距离：</strong>{res.spellrange}<br>
        <strong>法术成分：</strong>{res.components}<br>
        <strong>持续时间：</strong>{res.duration}
        </p>
        <p>{res.description}</p>
        <p><ref>{reference}</ref><span class="spell-source-bottom">【{res.source}】</span></p>
        """
        return re.sub(r"</?u\b[^>]*>", lambda match: "<strong>" if match.group(0)[1] != "/" else "</strong>", sample_html, flags=re.IGNORECASE)
        

    def search_spell_in_folder(self, spell_name: str) -> SpellFeature:
        """从本地文件夹中搜索法术并返回特征对象"""
        if not os.path.exists(self.json_path):
            print(f"[DND插件错误] 找不到配置文件: {self.json_path}")
            return None

        with open(self.json_path, 'r', encoding='utf-8') as ssf:
            ssf_data = json.load(ssf)
        
        for folder in ssf_data.keys():
            file_path = Path(os.path.join(self.htm_spells_dir, folder))
            if not file_path.exists():
                continue
                
            htm_files = list(file_path.glob('*.html')) + list(file_path.glob('*.htm'))
            for htm_file in htm_files:
                try:
                    with open(htm_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    extracted_html = self.extract_spell_html(content, spell_name)
                    if extracted_html:
                        return self.handle_spell_html(extracted_html, ssf_data[folder])
                except Exception as e:
                    pass
                    
        return None

    async def render_html_to_image(self, html_content: str, output_filename: str):
        custom_css = """
        body { width: 600px; margin: 0; padding: 0; background-color: #fdfaf6; }
        #card-container { padding: 30px; box-sizing: border-box; width: 100%; color: #333333; font-family: "Microsoft YaHei", "PingFang SC", sans-serif; }
        h4 { color: #7a200d; border-bottom: 2px solid #c9ad6a; padding-bottom: 5px; font-size: 24px; margin-top: 0; margin-bottom: 6px; }
        #card-container > p:last-of-type { position: relative; }
        .spell-source-bottom { position: absolute; right: 0; bottom: 0; color: #888888; font-style: italic; font-size: 13px; white-space: nowrap; }
        p { line-height: 1.6; font-size: 15px; text-align: justify; }
        table { width: 100% !important; max-width: 100%; table-layout: auto; border-collapse: collapse; }
        blockquote { margin: 10px 0; padding: 0; }
        td { padding: 5px 10px !important; border-bottom: 1px dashed #e0d8c8; }
        ref { color: #808080; }
        #card-container * { max-width: 100% !important; }
        """

        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{custom_css}</style>
        </head>
        <body>
            <div id="card-container">
                {html_content}
            </div>
        </body>
        </html>
        """

        # 异步调用 playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(args=['--no-sandbox']) 
            page = await browser.new_page()
            await page.set_content(full_html)
            
            locator = page.locator("#card-container")
            await locator.screenshot(path=output_filename)
            
            await browser.close()

    @filter.command("查询法术")
    async def query_spell(self, event: AstrMessageEvent, spell_name: str = ""):
        if not self._command_enabled(event):
            return
        if not spell_name:
            # 纯文本直接用 plain_result 传字符串
            yield event.plain_result("请提供要查询的法术名称，例如：查询法术 防护善恶")
            return

        # 提示正在搜索（传入纯字符串）
        yield event.plain_result(f"正在翻阅法术书查找“{spell_name}”...")
        
        try:
            res = self.search_spell_in_folder(spell_name)
        except Exception as e:
            yield event.plain_result(f"解析法术文本时出现问题: {str(e)}")
            return

        if not res:
            yield event.plain_result(f"法术书里没找到关于“{spell_name}”的记载哦。")
            return

        html_content = self.spellfeature_to_html(res)
        safe_spell_name = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", spell_name).strip("._") or "spell"
        temp_image_path = os.path.join(self.plugin_dir, f"temp_{safe_spell_name}_{int(time.time() * 1000)}.png")

        try:
            await self.render_html_to_image(html_content, temp_image_path)
            yield event.chain_result([Image.fromFileSystem(temp_image_path)])
        except Exception as e:
            yield event.plain_result(f"施法失败 (渲染报错): {str(e)}")
        finally:
            if os.path.exists(temp_image_path):
                try:
                    os.remove(temp_image_path)
                except OSError:
                    pass
