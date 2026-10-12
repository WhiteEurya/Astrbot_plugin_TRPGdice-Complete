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
import html
import hashlib
from pathlib import Path
from typing import Optional
from playwright.async_api import Error as PlaywrightError, async_playwright

# ========== MODULE IMPORT ========== #
from .component.pc import store as charmod
from .component.pc import dnd as dnd_mod
from .component.pc import resources as dnd_resources
from .component.roll import dice as dice_mod
from .component.coc import san as sanity
from .component.common.output import configure_output, get_output
from .component.common.webui import PluginConfigPage
from .component.common.utils import roll_character, format_character, roll_dnd_character, format_dnd_character, SYNONYMS
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
from .component.pc.nick import build_card_by_mode
from .component.pc.names import USAGE as NAME_USAGE, parse_name_request, generate_faker_names, generate_llm_names
from .component.pc.template import get_coc_st_template
from .component.pc.attributes import parse_st_expression, find_attribute_key, set_attribute_value
from .component.spells import query_coc_spell

logger_core = JSONLoggerCore()

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_DIR = os.path.join(PLUGIN_DIR, "data", "settings")
GROUP_POSTS_PATH = os.path.join(PLUGIN_DIR, "data", "group_posts.json")
GROUP_POST_MAX_AGE = 30 * 24 * 60 * 60
_T2I_FONT_PATCHED = False

GROUP_POST_SCHEMAS = {
    "coc": [
        "模组名", "规则类型", "kp", "期望人数", "预计长度", "开团时间",
        "联系方式", "跑团方式", "年代地点", "车卡要求", "推荐技能", "背景故事", "kp的建议",
    ],
    "dnd": [
        "模组名", "游戏规则", "扩充拓展", "等级资源", "联系方式", "跑团方式",
        "跑团平台", "期望人数", "开团时间", "预期长度", "故事地点", "背景简介", "备注",
    ],
}
GROUP_POST_REQUIRED_FIELDS = {
    "coc": {"模组名", "规则类型", "期望人数", "联系方式", "跑团方式", "预计长度", "年代地点", "背景故事"},
    "dnd": {"模组名", "游戏规则", "期望人数", "联系方式", "跑团方式", "预期长度", "等级资源", "背景简介"},
}

COMMANDS = [
    "show",
    "del",
    "clr",
    "export"
]

RULE_SYSTEMS = {
    "coc": {"label": "CoC", "default_roll": "1d100", "aliases": {"coc", "coc7", "cthulhu", "克苏鲁"}},
    "dnd": {"label": "DnD", "default_roll": "1d20", "aliases": {"dnd", "dnd5e", "d&d", "d20", "龙与地下城"}},
}
DEFAULT_RULE_SYSTEM = "coc"

log_help_str = '''.log 指令一览：
    .log on -- 开启log记录。亚托莉会记录之后所有的对话，并保存在“群名+时间”文件夹内。（施工中）
    .log off -- 暂停log记录。在同一群聊内再次使用.log on，可以继续记录未完成的log。（施工中）
    .log end -- 结束log记录。亚托莉会在群聊内发送“群名+时间.txt”的log文件。（施工中）
'''

HELP_PAGE_META = {
    "index": ("风铃协助手册", "跑团常用指令索引"),
    "dice": ("风铃协助手册 · 掷骰篇", "检定、奖励骰、暗骰与理智检定"),
    "expr": ("风铃协助手册 · 表达式篇", "复杂骰式、重复投掷与保留骰"),
    "pc": ("风铃协助手册 · 角色管理篇", "人物卡创建、切换、同步与删除"),
    "st": ("风铃协助手册 · 属性记录篇", "属性录入、查询、修改与导出"),
    "log": ("风铃协助手册 · 记录篇", "日志开启、暂停、导出与整理"),
    "coc": ("风铃协助手册 · COC 与杂项篇", "规则设置、法术查询与常用小工具"),
    "dnd": ("风铃协助手册 · DnD 篇", "角色生成、法术查询与先攻管理"),
}

HELP_COMMAND_ALIASES = {
    "help": "index",
    "helproll": "dice",
    "helpexpr": "expr",
    "helppc": "pc",
    "helpst": "st",
    "helplog": "log",
    "helpcoc": "coc",
    "helpdnd": "dnd",
    "help roll": "dice",
    "help expr": "expr",
    "help pc": "pc",
    "help st": "st",
    "help log": "log",
    "help coc": "coc",
    "help dnd": "dnd",
    "bothelp": "index",
    "dicehelp": "index",
    "dicehelproll": "dice",
    "dicehelpexpr": "expr",
    "dicehelppc": "pc",
    "dicehelpst": "st",
    "dicehelplog": "log",
    "dicehelpcoc": "coc",
    "dicehelpdnd": "dnd",
    "dicehelp roll": "dice",
    "dicehelp expr": "expr",
    "dicehelp pc": "pc",
    "dicehelp st": "st",
    "dicehelp log": "log",
    "dicehelp coc": "coc",
    "dicehelp dnd": "dnd",
}

HELP_COMMAND_PREFIXES = ("dicehelp", "help")
ASTRBOT_BUILTIN_HELP_TOPICS = {
    "astrbot",
    "system",
    "core",
    "原生",
    "系统",
}

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

@register("astrbot_plugin_TRPG", "shiroling", "TRPG玩家用骰", "v2.3.1")
class DicePlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        self.wakeup_prefix = [".", "。", "/", "!", "！"]
        self.uni_cache = {}
        self.initiative_manager = InitiativeManager()
        self.config = config or {}
        configure_output(self.config.get("output"), self.config.get("dnd_output"))
        self.pending_group_posts = {}
        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))
        self.json_path = os.path.join(self.plugin_dir, "spellsearcher/SpellSourceFolder.json")
        self.htm_spells_dir = os.path.join(self.plugin_dir, "spellsearcher/HTMSpells")

        super().__init__(context)
        if callable(getattr(context, "register_web_api", None)):
            try:
                self.config_page = PluginConfigPage(self.config, self.plugin_dir)
                self.config_page.register(context)
            except ImportError:
                logger.warning("当前 AstrBot 缺少 Plugin Pages API，请使用原生插件配置页。")

    @filter.event_message_type(EventMessageType.ALL)
    async def send_bot_info_on_group_join(self, event: AstrMessageEvent):
        if not self.config.get("auto_bot_on_join", True):
            return

        raw_message = getattr(getattr(event, "message_obj", None), "raw_message", None)
        if not isinstance(raw_message, dict):
            return
        if raw_message.get("post_type") != "notice" or raw_message.get("notice_type") != "group_increase":
            return
        if str(raw_message.get("user_id")) != str(raw_message.get("self_id")):
            return

        group_id = str(raw_message.get("group_id") or event.get_group_id() or "")
        if not group_id:
            return

        image_path = self._bot_image_path()
        if image_path:
            yield event.chain_result([
                Image.fromFileSystem(image_path),
                Plain(self._bot_info_text(event)),
            ])
        else:
            yield event.plain_result(self._bot_info_text(event))

    async def save_log(self, group_id, content, event: AstrMessageEvent = None) :
        if not group_id:
            return
        source_user_id = event.get_sender_id() if event else None
        source_nickname = event.get_sender_name() if event else ""

        ok, info = await logger_core.add_message(
            group_id=group_id,
            user_id="Bot",
            nickname="风铃Velinithra",
            timestamp=int(time.time()),
            text=content,
            isDice=True,
            source_user_id=source_user_id,
            source_nickname=source_nickname
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

    def _load_group_posts(self) -> list[dict]:
        if not os.path.exists(GROUP_POSTS_PATH):
            return []
        try:
            with open(GROUP_POSTS_PATH, "r", encoding="utf-8") as file:
                data = json.load(file)
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def _save_group_posts(self, posts: list[dict]):
        os.makedirs(os.path.dirname(GROUP_POSTS_PATH), exist_ok=True)
        with open(GROUP_POSTS_PATH, "w", encoding="utf-8") as file:
            json.dump(posts, file, ensure_ascii=False, indent=2)

    def _cleanup_group_posts(self, posts: list[dict]) -> list[dict]:
        now = time.time()
        active = [
            post for post in posts
            if now - float(post.get("created_at", 0)) < GROUP_POST_MAX_AGE
        ]
        if len(active) != len(posts):
            self._save_group_posts(active)
        return active

    def _parse_group_post(self, payload: str) -> tuple[str, dict] | tuple[None, str]:
        normalized_payload = payload.replace("\r\n", "\n")
        normalized_payload = re.sub(r"(?=[丨|][^丨|\n：]+：)", "\n", normalized_payload)
        lines = [line.strip() for line in normalized_payload.split("\n") if line.strip()]
        if not lines:
            return None, get_output("group_post.empty")

        parsed = []
        current_label = None
        for line in lines:
            if line[0] in {"丨", "|"} and "：" in line:
                label, value = line[1:].split("：", 1)
                current_label = label.strip()
                parsed.append((current_label, value.strip()))
            elif current_label is not None:
                old_label, old_value = parsed[-1]
                parsed[-1] = (old_label, f"{old_value}\n{line}" if old_value else line)
            else:
                return None, get_output("group_post.malformed_line", line=line)

        labels = [label for label, _ in parsed]
        all_labels = {label for schema in GROUP_POST_SCHEMAS.values() for label in schema}
        unknown = [label for label in labels if label not in all_labels]
        if unknown:
            return None, get_output("group_post.unknown_fields", fields="、".join(unknown))
        duplicates = [label for label in set(labels) if labels.count(label) > 1]
        if duplicates:
            return None, get_output("group_post.duplicate_fields", fields="、".join(duplicates))

        if "游戏规则" in labels or any(label in labels for label in {"扩充拓展", "等级资源", "预期长度", "故事地点", "背景简介"}):
            candidate = "dnd"
        elif "规则类型" in labels or any(label in labels for label in {"年代地点", "车卡要求", "推荐技能", "背景故事", "kp的建议"}):
            candidate = "coc"
        else:
            return None, get_output("group_post.unknown_rule")

        missing = sorted(GROUP_POST_REQUIRED_FIELDS[candidate] - set(labels))
        if missing:
            return None, get_output("group_post.missing_fields", schema=candidate.upper(), fields="、".join(missing))

        schema_matches = [
            name for name, schema in GROUP_POST_SCHEMAS.items()
            if set(labels).issubset(set(schema))
            and GROUP_POST_REQUIRED_FIELDS[name].issubset(set(labels))
        ]
        if len(schema_matches) != 1:
            return None, get_output("group_post.invalid_schema")
        schema_name = schema_matches[0]

        values = dict(parsed)
        return schema_name, {label: values.get(label, "") for label in GROUP_POST_SCHEMAS[schema_name]}

    def _group_post_html(self, posts: list[dict]) -> str:
        cards = []
        for post in posts:
            rows = "".join(
                f'<div class="post-row"><span class="post-label">{html.escape(label)}</span>'
                f'<span class="post-value">{html.escape(value) or "<span class=empty>（未填写）</span>"}</span></div>'
                for label, value in post["fields"].items()
            )
            cards.append(
                f'<article class="post-card"><div class="post-meta">#{html.escape(post["id"])} · '
                f'{html.escape(post["schema"].upper())}</div>{rows}</article>'
            )
        body = "".join(cards) or '<div class="empty-list">目前还没有正在招募的团。</div>'
        return f"""
        <section id="group-posts">
          <header><div class="brand"><span class="dot"></span>TRPG Dice</div><span>GROUP POSTS</span></header>
          <h1>当前挂团公告</h1><p class="subtitle">共 {len(posts)} 个进行中的团</p>
          {body}
        </section>
        """

    async def _render_group_posts_image(self, posts: list[dict], output_filename: str):
        css = """
        body { margin: 0; background: transparent; font-family: "Noto Sans CJK SC", Arial, sans-serif; }
        #group-posts { width: 900px; box-sizing: border-box; padding: 34px; color: #29342f;
          background: linear-gradient(180deg, #fbf5e9, #f1e5d0); }
        header { display:flex; justify-content:space-between; align-items:center; border-top:8px solid #254c3a;
          padding:20px 0 14px; border-bottom:1px solid #d7c7a8; color:#6d624c; font-size:16px; font-weight:700; }
        .brand { display:flex; align-items:center; gap:10px; } .dot { width:11px; height:11px; border-radius:50%; background:#b99b54; }
        h1 { margin:22px 0 6px; color:#223f32; font-size:40px; } .subtitle { margin:0 0 20px; color:#75684f; font-size:18px; }
        .post-card { margin:16px 0; border:1px solid #d6c6a5; border-radius:8px; overflow:hidden; background:#fffaf0; box-shadow:0 8px 20px rgba(60,45,25,.1); }
        .post-meta { padding:12px 16px; background:#f2e6d2; color:#806a3d; font-weight:700; }
        .post-row { display:grid; grid-template-columns:150px 1fr; gap:16px; padding:10px 16px; border-top:1px dashed #e1d4bc; line-height:1.5; }
        .post-label { color:#2e5b46; font-weight:700; } .post-value { white-space:pre-wrap; overflow-wrap:anywhere; }
        .empty { color:#9a8c72; } .empty-list { padding:28px; text-align:center; color:#75684f; background:#fffaf0; border:1px solid #d6c6a5; }
        """
        document = f"<!doctype html><html><head><meta charset='UTF-8'><style>{css}</style></head><body>{self._group_post_html(posts)}</body></html>"
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(args=["--no-sandbox"])
                page = await browser.new_page(viewport={"width": 900, "height": 1400}, device_scale_factor=1)
                await page.set_content(document)
                await page.locator("#group-posts").screenshot(path=output_filename)
                await browser.close()
        except PlaywrightError as exc:
            raise RuntimeError("Playwright Chromium 未安装，无法生成挂团图片。") from exc

    def _bot_identity(self, event) -> tuple[str, str]:
        message = getattr(event, "message_obj", None)
        get_self_id = getattr(event, "get_self_id", None)
        bot_id = get_self_id() if callable(get_self_id) else None
        bot_id = bot_id or getattr(message, "self_id", None) or getattr(getattr(event, "bot", None), "self_id", "")
        get_platform = getattr(event, "get_platform_name", None)
        platform = get_platform() if callable(get_platform) else ""
        return str(platform or ""), str(bot_id or "")

    def _bot_settings_key(self, group_id, event) -> str:
        platform, bot_id = self._bot_identity(event)
        if not bot_id:
            return ""
        identity = json.dumps([platform, bot_id, str(group_id)], ensure_ascii=True)
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    def _bot_command_targets_self(self, event) -> bool:
        targets = {str(comp.qq) for comp in getattr(getattr(event, "message_obj", None), "message", [])
                   if isinstance(comp, Comp.At)}
        if not targets:
            return True
        return self._bot_identity(event)[1] in targets

    def _set_bot_enabled(self, event, enabled: bool):
        group_id = self._group_id(event)
        key = self._bot_settings_key(group_id, event)
        if key:
            self._save_settings("bots", key, {"enabled": enabled})
        else:
            settings = self._get_group_settings(group_id)
            settings["enabled"] = enabled
            self._save_group_settings(group_id, settings)

    def _is_bot_enabled(self, group_id, event=None) -> bool:
        if event is not None:
            key = self._bot_settings_key(group_id, event)
            if key:
                settings = self._load_settings("bots", key)
                if "enabled" in settings:
                    return settings["enabled"]
        # Keep old group switches as defaults until this bot receives its own setting.
        return self._get_group_settings(group_id).get("enabled", True)

    def _command_enabled(self, event: AstrMessageEvent) -> bool:
        group_id = self._group_id(event)
        if not group_id:
            return True
        return self._is_bot_enabled(group_id, event)

    def _allowed_when_disabled(self, command_text: str) -> bool:
        command = re.sub(r"\s+", " ", (command_text or "").strip().lower())
        return command in {"bot on", "bot quit"}

    def _is_native_reset_command(self, command_text: str) -> bool:
        command = re.sub(r"\s+", " ", (command_text or "").strip().lower())
        return command in {"reset", "r eset"}

    def _normalize_rule_system(self, value: str) -> str:
        value = (value or "").strip().lower()
        for system, meta in RULE_SYSTEMS.items():
            if value == system or value in meta["aliases"]:
                return system
        return ""

    def _get_rule_system(self, context_id) -> str:
        if not context_id:
            return DEFAULT_RULE_SYSTEM
        settings = self._get_group_settings(context_id)
        system = self._normalize_rule_system(settings.get("rule_system", ""))
        return system or DEFAULT_RULE_SYSTEM

    def _set_rule_system(self, context_id, system: str) -> str:
        normalized = self._normalize_rule_system(system)
        if not normalized:
            return ""
        settings = self._get_group_settings(context_id)
        settings["rule_system"] = normalized
        self._save_group_settings(context_id, settings)
        return normalized

    def _default_roll_expr(self, context_id) -> str:
        system = self._get_rule_system(context_id)
        return RULE_SYSTEMS[system]["default_roll"]

    def _format_rule_system_status(self, context_id) -> str:
        system = self._get_rule_system(context_id)
        meta = RULE_SYSTEMS[system]
        return f"当前规则系统：{meta['label']}，.r 默认骰为 {meta['default_roll']}。"

    def _advantage_roll_expression(self, context_id, modifier: str, disadvantage: bool = False) -> str:
        default_roll = self._default_roll_expr(context_id)
        match = re.fullmatch(r"1d(\d+)", default_roll)
        dice_faces = match.group(1) if match else "20"
        keep = "k-1" if disadvantage else "k1"
        return f"2d{dice_faces}{keep}{modifier}"

    def _stop_event(self, event: AstrMessageEvent):
        for method_name in ("stop_event", "stop_propagation", "stop"):
            method = getattr(event, method_name, None)
            if callable(method):
                try:
                    method()
                except TypeError:
                    pass
                return

    def _help_command_page(self, command_text: str) -> str:
        command = re.sub(r"\s+", " ", (command_text or "").strip().lower())
        return HELP_COMMAND_ALIASES.get(command, "")

    def _help_topic_from_command(self, command_text: str) -> str:
        command = re.sub(r"\s+", " ", (command_text or "").strip().lower())
        for prefix in HELP_COMMAND_PREFIXES:
            if command == prefix:
                return ""
            if command.startswith(prefix):
                return command[len(prefix):].strip(" .:/_-")
        return ""

    def _resolve_help_request(self, command_text: str) -> tuple[str, str]:
        command = re.sub(r"\s+", " ", (command_text or "").strip().lower())
        page = self._help_command_page(command)
        if page:
            return "page", page
        topic = self._help_topic_from_command(command)
        if topic in ASTRBOT_BUILTIN_HELP_TOPICS:
            return "builtin", topic
        if topic:
            return "command", topic
        if command.startswith(HELP_COMMAND_PREFIXES):
            return "page", "index"
        return "", ""

    def _suppress_astrbot_builtin_help(self, event: AstrMessageEvent):
        activated_handlers = event.get_extra("activated_handlers") or []
        handlers_parsed_params = event.get_extra("handlers_parsed_params") or {}

        kept_handlers = []
        for handler in list(activated_handlers):
            module_path = getattr(handler, "handler_module_path", "")
            full_name = getattr(handler, "handler_full_name", "")
            handler_name = getattr(handler, "handler_name", "")
            is_builtin_help = (
                handler_name == "help"
                and (
                    "packages.astrbot" in module_path
                    or "packages.astrbot" in full_name
                    or module_path == "astrbot.main"
                )
            )
            if is_builtin_help:
                logger.debug(f"suppress builtin AstrBot help handler: {full_name}")
                handlers_parsed_params.pop(full_name, None)
                continue
            kept_handlers.append(handler)

        activated_handlers[:] = kept_handlers
        event.set_extra("activated_handlers", kept_handlers)
        event.set_extra("handlers_parsed_params", handlers_parsed_params)

    def _split_help_line(self, line: str) -> tuple[str, str]:
        stripped = line.strip()
        if not stripped:
            return "", ""

        normalized = stripped.replace("`", "")
        for separator in (" : ", " ：", "：", " - ", " -- "):
            if separator in normalized:
                left, right = normalized.split(separator, 1)
                left = left.strip()
                right = right.strip()
                if left.startswith((".", "/", "!", "！")):
                    return left, right
                if right.startswith((".", "/", "!", "！")):
                    return right, left
                return left, right

        command_match = re.match(r"^([./!！][^\s，。；;：:]+(?:\s+[^\s，。；;：:]+){0,3})(.*)$", normalized)
        if command_match:
            return command_match.group(1).strip(), command_match.group(2).strip()

        return "", normalized

    def _iter_help_entries(self):
        for page_key in HELP_PAGE_META:
            if page_key == "index":
                continue
            raw_text = get_output(f"help.{page_key}")
            for raw_line in raw_text.splitlines():
                line = raw_line.strip()
                if not line or line.startswith("《"):
                    continue
                command, description = self._split_help_line(line)
                if command:
                    yield page_key, command, description

    def _normalize_help_command_key(self, value: str) -> str:
        value = (value or "").lower().replace("！", "!")
        value = re.sub(r"<[^>]*>|\[[^\]]*\]|（.*?）|\(.*?\)", "", value)
        value = re.sub(r"[`./!。/]", "", value)
        return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value)

    def _help_command_aliases(self, command: str) -> set[str]:
        aliases = set()
        for part in re.split(r"[/；;，,、]", command):
            part = part.strip()
            if not part:
                continue
            key = self._normalize_help_command_key(part)
            if key:
                aliases.add(key)
            head_match = re.match(r"^[`]*[./!！。]?([a-z][a-z0-9]*)(?:\s+([a-z0-9]+))?", part.lower())
            if head_match:
                first = head_match.group(1)
                second = head_match.group(2) or ""
                aliases.add(first)
                if second:
                    aliases.add(first + second)
        return aliases

    def _find_help_command(self, query: str) -> Optional[tuple[str, str, str]]:
        normalized_query = self._normalize_help_command_key(query)
        if not normalized_query:
            return None
        for page_key, command, description in self._iter_help_entries():
            if normalized_query in self._help_command_aliases(command):
                return page_key, command, description
        for page_key, command, description in self._iter_help_entries():
            if normalized_query in self._normalize_help_command_key(command):
                return page_key, command, description
        return None

    def _build_help_command_html(self, query: str) -> tuple[str, str]:
        match = self._find_help_command(query)
        if not match:
            topic = html.escape(query)
            fallback_text = f"未找到 help {query} 的说明。可以试试 .help、.help roll 或 .dicehelp roll。"
            return (
                fallback_text,
                f"""
                <section class="help-card">
                    <div class="help-topline">
                        <span class="help-dot"></span>
                        <span>TRPG Dice</span>
                        <span class="help-page-key">HELP</span>
                    </div>
                    <header class="help-header">
                        <h1>没有找到这个指令</h1>
                        <p>查询：{topic}</p>
                    </header>
                    <div class="help-note">可以使用 .help 查看索引，或使用 .help roll / .help pc 查看分类帮助。</div>
                </section>
                """,
            )

        page_key, command, description = match
        title, _subtitle = HELP_PAGE_META.get(page_key, HELP_PAGE_META["index"])
        fallback_text = f"{command}\n{description}\n\n来自：{title}"
        return (
            fallback_text,
            f"""
            <section class="help-card">
                <div class="help-topline">
                    <span class="help-dot"></span>
                    <span>TRPG Dice</span>
                    <span class="help-page-key">{html.escape(page_key.upper())}</span>
                </div>
                <header class="help-header">
                    <h1>指令说明</h1>
                    <p>{html.escape(title)}</p>
                </header>
                <div class="help-section">
                    <div class="help-section-title">
                        <span class="help-icon">◆</span>
                        <span>{html.escape(command)}</span>
                    </div>
                    <div class="help-command-detail">{html.escape(description)}</div>
                </div>
                <footer class="help-footer">
                    <span>更多：.help {html.escape(page_key)} / .help</span>
                </footer>
            </section>
            """,
        )

    def _build_help_html(self, page_key: str) -> str:
        title, subtitle = HELP_PAGE_META.get(page_key, HELP_PAGE_META["index"])
        text_key = "help.index" if page_key == "index" else f"help.{page_key}"
        raw_text = get_output(text_key)

        rows = []
        notes = []
        for raw_line in raw_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("《") and line.endswith(("》", "》。")):
                continue
            command, description = self._split_help_line(line)
            if command:
                rows.append((command, description))
            else:
                notes.append(description)

        notes_html = "".join(
            f'<div class="help-note">{html.escape(note)}</div>'
            for note in notes[:3]
            if note
        )
        rows_html = "".join(
            '<div class="help-row">'
            f'<div class="help-command">{html.escape(command)}</div>'
            f'<div class="help-desc">{html.escape(description)}</div>'
            '</div>'
            for command, description in rows
        )
        if not rows_html:
            rows_html = "".join(
                f'<div class="help-note">{html.escape(line.strip())}</div>'
                for line in raw_text.splitlines()
                if line.strip()
            )

        return f"""
        <section class="help-card">
            <div class="help-topline">
                <span class="help-dot"></span>
                <span>TRPG Dice</span>
                <span class="help-page-key">{html.escape(page_key.upper())}</span>
            </div>
            <header class="help-header">
                <h1>{html.escape(title)}</h1>
                <p>{html.escape(subtitle)}</p>
            </header>
            <div class="help-notes">{notes_html}</div>
            <div class="help-section">
                <div class="help-section-title">
                    <span class="help-icon">◆</span>
                    <span>指令速查</span>
                </div>
                <div class="help-rows">{rows_html}</div>
            </div>
            <footer class="help-footer">
                <span>更多：.dicehelp roll / expr / pc / st / log / coc / dnd</span>
            </footer>
        </section>
        """

    async def render_help_html_to_image(self, html_content: str, output_filename: str):
        custom_css = """
        :root {
            color-scheme: light;
            font-family: "Noto Sans CJK SC", "Source Han Sans SC", "Microsoft YaHei", "PingFang SC", Arial, sans-serif;
        }
        body {
            margin: 0;
            padding: 0;
            background: transparent;
        }
        #help-container {
            width: 900px;
            box-sizing: border-box;
            padding: 34px;
            background:
                radial-gradient(circle at 14% 10%, rgba(118, 99, 59, 0.08), transparent 28%),
                linear-gradient(180deg, #fbf4e7 0%, #f4ead8 100%);
            color: #26322b;
        }
        .help-card {
            position: relative;
            overflow: hidden;
            border: 1px solid #c9b995;
            border-radius: 8px;
            background: rgba(255, 252, 244, 0.92);
            box-shadow: 0 14px 34px rgba(49, 39, 23, 0.16);
            padding: 30px 34px 26px;
        }
        .help-card::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 9px;
            background: linear-gradient(90deg, #254c3a, #406b53 55%, #b99b54);
        }
        .help-topline {
            display: flex;
            align-items: center;
            gap: 10px;
            color: #6d624c;
            font-size: 16px;
            letter-spacing: 0;
            margin-top: 2px;
        }
        .help-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #b99b54;
            box-shadow: 0 0 0 4px rgba(185, 155, 84, 0.18);
        }
        .help-page-key {
            margin-left: auto;
            color: #2f5a45;
            font-weight: 700;
        }
        .help-header {
            margin: 20px 0 22px;
            padding-bottom: 18px;
            border-bottom: 1px solid #dccfb4;
        }
        .help-header h1 {
            margin: 0 0 9px;
            color: #223f32;
            font-size: 42px;
            line-height: 1.16;
            font-weight: 800;
            letter-spacing: 0;
        }
        .help-header p {
            margin: 0;
            color: #6a5d48;
            font-size: 20px;
            line-height: 1.45;
        }
        .help-notes {
            display: grid;
            gap: 8px;
            margin-bottom: 18px;
        }
        .help-note {
            border-left: 4px solid #b99b54;
            background: #f7efdF;
            padding: 10px 13px;
            color: #4d473a;
            font-size: 18px;
            line-height: 1.48;
            border-radius: 6px;
        }
        .help-section {
            border: 1px solid #ded1b5;
            border-radius: 8px;
            background: #fffaf0;
        }
        .help-section-title {
            display: flex;
            align-items: center;
            gap: 9px;
            padding: 14px 18px;
            color: #264736;
            font-size: 22px;
            font-weight: 800;
            border-bottom: 1px solid #e5d9c0;
            background: #f5ead7;
        }
        .help-icon {
            color: #b99b54;
            font-size: 17px;
        }
        .help-rows {
            display: grid;
        }
        .help-row {
            display: grid;
            grid-template-columns: minmax(210px, 0.86fr) minmax(0, 1.7fr);
            gap: 18px;
            align-items: start;
            padding: 13px 18px;
            border-bottom: 1px dashed #dfd2b8;
        }
        .help-row:last-child {
            border-bottom: none;
        }
        .help-command {
            display: inline-block;
            width: fit-content;
            max-width: 100%;
            box-sizing: border-box;
            padding: 5px 9px;
            border-radius: 6px;
            background: #e8efe7;
            color: #1f4a38;
            font-family: "Cascadia Mono", "Consolas", "Menlo", monospace;
            font-size: 17px;
            line-height: 1.35;
            font-weight: 700;
            overflow-wrap: anywhere;
        }
        .help-desc {
            color: #342f27;
            font-size: 18px;
            line-height: 1.48;
        }
        .help-command-detail {
            padding: 22px 24px;
            color: #342f27;
            font-size: 22px;
            line-height: 1.62;
            background: #fffaf0;
        }
        .help-footer {
            display: flex;
            justify-content: flex-end;
            margin-top: 18px;
            color: #6f634c;
            font-size: 16px;
        }
        """
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{custom_css}</style>
        </head>
        <body>
            <div id="help-container">{html_content}</div>
        </body>
        </html>
        """

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(args=['--no-sandbox'])
                page = await browser.new_page(viewport={"width": 900, "height": 1400}, device_scale_factor=1)
                await page.set_content(full_html)
                locator = page.locator("#help-container")
                await locator.screenshot(path=output_filename)
                await browser.close()
        except PlaywrightError as exc:
            raise RuntimeError(
                "Playwright Chromium 未安装或缺少系统依赖；Docker 用户请执行 "
                "`python -m playwright install --with-deps chromium` 后重启 AstrBot。"
            ) from exc

    async def _yield_help_result(self, event: AstrMessageEvent, page_key: str):
        text_key = "help.index" if page_key == "index" else f"help.{page_key}"
        fallback_text = get_output(text_key)
        safe_key = re.sub(r"[^a-z0-9_-]+", "_", page_key.lower()) or "index"
        temp_image_path = os.path.join(self.plugin_dir, f"temp_help_{safe_key}_{int(time.time() * 1000)}.png")

        try:
            await self.render_help_html_to_image(self._build_help_html(page_key), temp_image_path)
            yield event.chain_result([Image.fromFileSystem(temp_image_path)]).stop_event()
        except Exception as e:
            yield event.plain_result(f"帮助图片生成失败：{e}\n\n{fallback_text}").stop_event()
        finally:
            if os.path.exists(temp_image_path):
                try:
                    os.remove(temp_image_path)
                except OSError:
                    pass

    async def _yield_help_command_result(self, event: AstrMessageEvent, query: str):
        fallback_text, html_content = self._build_help_command_html(query)
        safe_key = re.sub(r"[^a-z0-9_-]+", "_", query.lower()) or "command"
        temp_image_path = os.path.join(self.plugin_dir, f"temp_help_cmd_{safe_key}_{int(time.time() * 1000)}.png")

        try:
            await self.render_help_html_to_image(html_content, temp_image_path)
            yield event.chain_result([Image.fromFileSystem(temp_image_path)]).stop_event()
        except Exception as e:
            yield event.plain_result(f"帮助图片生成失败：{e}\n\n{fallback_text}").stop_event()
        finally:
            if os.path.exists(temp_image_path):
                try:
                    os.remove(temp_image_path)
                except OSError:
                    pass

    def _bot_image_path(self):
        configured = self.config.get("bot_image_path")
        if configured is not None:
            configured = configured.strip()
            if not configured:
                return None
            path = os.path.expanduser(configured)
            if not os.path.isabs(path):
                path = os.path.join(PLUGIN_DIR, path)
            return path if os.path.isfile(path) else None
        candidates = [
            os.path.join(PLUGIN_DIR, "data", "bot.png"),
            os.path.join(SETTINGS_DIR, "bot.png"),
            os.path.join(SETTINGS_DIR, "bot.jpg"),
            os.path.join(PLUGIN_DIR, "bot.png"),
            os.path.join(PLUGIN_DIR, "bot.jpg"),
            os.path.join(PLUGIN_DIR, "assets", "bot.png"),
            os.path.join(PLUGIN_DIR, "assets", "bot.jpg"),
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path
        return None

    def _bot_info_text(self, event: AstrMessageEvent) -> str:
        status_key = "bot.status_on" if self._is_bot_enabled(self._group_id(event), event) else "bot.status_off"
        return get_output("bot.info", status=get_output(status_key))

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
        
        await self.save_log(group_id = event.get_group_id(), content = result_text, event=event)
        
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
            err = get_output("dice.vampire.error", error=get_output("common.invalid_number"))
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

        await self.save_log(group_id = event.get_group_id(), content = text, event=event)
        
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
        
        await self.save_log(group_id = event.get_group_id(), content = "[Private Roll Result]" + private_text, event=event)
        
        await client.api.call_action("send_private_msg", **payloads)


    @filter.command("st")
    async def status(self, event: AstrMessageEvent, attributes: str = None, exp : str = None):
        """人物卡属性更新 / 掷骰 (V4 - 区分单/多重赋值)"""
        rule_system = self._get_rule_system(self._group_id(event))
        if not self._command_enabled(event):
            return
        if not attributes:
            return

        if attributes in COMMANDS :
            return

        if rule_system == "dnd":
            full_expr = " ".join(str(value) for value in (attributes, exp) if value is not None)
            raw = self._strip_at_text(event.get_message_str())
            command = strip_command_prefix(raw, self.wakeup_prefix) or raw
            if re.match(r"^st\s", command, re.I):
                full_expr = re.sub(r"^st\s+", "", command, count=1, flags=re.I)
            async for result in self._dnd_st(event, "update", full_expr):
                yield result
            return

        user_id = self._get_target_user_id(event)
        operator_user_id = str(event.get_sender_id())
        group_id = event.get_group_id()
        chara_id = charmod.get_current_character_id(group_id, user_id, rule_system=rule_system)
        
        if not chara_id:
            if user_id == operator_user_id:
                yield event.plain_result(get_output("pc.show.no_active"))
            else:
                yield event.plain_result(get_output("pc.show.target_no_active"))
            return

        chara_data = charmod.load_character(group_id, user_id, chara_id, rule_system=rule_system)
        full_expr = self._strip_at_text((str(attributes) if attributes else "") + (str(exp) if exp else ""))
        try:
            entries = parse_st_expression(full_expr)
        except ValueError:
            yield event.plain_result(get_output("pc.update.error_format"))
            return

        if len(entries) > 1:
            for attribute, _, value in entries:
                set_attribute_value(chara_data["attributes"], attribute, int(value))

            derived_tips = charmod.sync_derived_attributes(chara_data, rule_system=rule_system)
            charmod.save_character(group_id, user_id, chara_id, chara_data, rule_system=rule_system)
            if event.get_platform_name() == "aiocqhttp":
                await self._update_user_nickname_card(event.bot, group_id, user_id)

            response = get_output("pc.update.batch_success", count=len(entries))
            if user_id != operator_user_id:
                response = get_output("pc.update.proxy_prefix", name=chara_data.get('name', user_id), content=response)
            if derived_tips:
                response += "\n" + get_output("pc.update.derived_suffix", tips=", ".join(derived_tips))

            await self.save_log(group_id=event.get_group_id(), content=response, event=event)
            yield event.plain_result(response)
            return

        attribute, operator, value_expr = entries[0]
        derived_tips = None
        existing_key = find_attribute_key(chara_data["attributes"], attribute)
        current_value = chara_data["attributes"].get(existing_key, 1)

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
        
        # 根据运算符计算新值
        if operator == "+":
            new_value = current_value + value_num
        elif operator == "-":
            new_value = current_value - value_num
        elif operator == "*":
            new_value = current_value * value_num
        else:  # 无运算符 (例如 .st 力量100)，直接赋值
            new_value = value_num

        new_val_final = max(0, new_value)
        set_attribute_value(chara_data["attributes"], attribute, new_val_final)

        derived_tips = charmod.sync_derived_attributes(chara_data, rule_system=rule_system)
        charmod.save_character(group_id, user_id, chara_id, chara_data, rule_system=rule_system)
        # 触发静默更新名片
        if event.get_platform_name() == "aiocqhttp":
            await self._update_user_nickname_card(event.bot, group_id, user_id)

        response = get_output("pc.update.success", attr=attribute, old=current_value, new=new_val_final)
        if user_id != operator_user_id:
            response = get_output("pc.update.proxy_prefix", name=chara_data.get('name', user_id), content=response)
        if roll_detail:
            response += "\n" + roll_detail
            
        if derived_tips:
            response += "\n" + get_output("pc.update.derived_suffix", tips=", ".join(derived_tips))

        await self.save_log(group_id=event.get_group_id(), content=response, event=event)
        yield event.plain_result(response)

    async def _dnd_st(self, event: AstrMessageEvent, action: str, args: str = ""):
        if not self._command_enabled(event):
            return
        group_id = str(event.get_group_id())
        user_id = self._get_target_user_id(event)
        card = charmod.get_current_character(group_id, user_id, rule_system="dnd")
        if not card:
            yield event.plain_result(get_output("pc.show.no_active"))
            return
        args = self._strip_at_text(args)
        try:
            if action == "show":
                response = dnd_mod.format_card(card, args)
            elif action == "export":
                response = dnd_mod.export_card(card)
            else:
                if action == "update":
                    updated, detail = dnd_mod.update_card(card, args)
                elif action in {"del", "clr"}:
                    updated, detail = dnd_mod.delete_attributes(card, args, clear=action == "clr")
                else:
                    raise ValueError("未知 DnD 属性操作。")
                charmod.save_character(group_id, user_id, card["id"], updated, rule_system="dnd")
                if event.get_group_id() and event.get_platform_name() == "aiocqhttp":
                    await self._update_user_nickname_card(event.bot, group_id, user_id)
                response = get_output("dnd.sheet.updated", name=card["name"], detail=detail)
                await self.save_log(group_id=event.get_group_id(), content=response, event=event)
        except ValueError as exc:
            yield event.plain_result(get_output("dnd.common.error", reason=str(exc)))
            return
        yield event.plain_result(response)

    async def _dnd_check(self, event: AstrMessageEvent, expression: str):
        if not self._command_enabled(event):
            return
        user_id = self._get_target_user_id(event)
        card = charmod.get_current_character(str(event.get_group_id()), user_id, rule_system="dnd")
        if not card:
            yield event.plain_result(get_output("pc.show.no_active"))
            return
        try:
            response = dnd_mod.roll_check(card, self._strip_at_text(expression))
        except ValueError as exc:
            yield event.plain_result(get_output("dnd.common.error", reason=str(exc)))
            return
        await self.save_log(group_id=event.get_group_id(), content=response, event=event)
        yield event.plain_result(response)

    @command_group("st")
    async def st(self, event: AstrMessageEvent, attributes: str = None, exp : str = None):
        """人物卡属性更新 / 掷骰"""
        pass


    @st.command("show")
    async def pc_show_character(self, event: AstrMessageEvent, *, args_str: str = ""):
        rule_system = self._get_rule_system(self._group_id(event))
        if not self._command_enabled(event):
            return
        if rule_system == "dnd":
            async for result in self._dnd_st(event, "show", args_str):
                yield result
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
                
        chara_id = charmod.get_current_character_id(group_id, target_user_id, rule_system=rule_system)
        
        if not chara_id:
            if target_user_id == str(event.get_sender_id()):
                yield event.plain_result(get_output("pc.show.no_active"))
            else:
                yield event.plain_result(get_output("pc.show.target_no_active"))
            return

        chara_data = charmod.load_character(group_id, target_user_id, chara_id, rule_system=rule_system)
        if not chara_data:
            yield event.plain_result(get_output("pc.show.load_fail", id=chara_id))
            return
        
        chara_attrs = chara_data.get("attributes", {})
        if not chara_attrs:
            yield event.plain_result(get_output("pc.show.attr_missing", attribute=get_output("pc.show.attribute_any")))
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
                    response = get_output("pc.show.named_header", name=chara_data["name"], content=response)
                yield event.plain_result(response)
            return

        # 场景 C: 按属性名处理 ( .st show 力量 敏捷 )
        found_attrs = []
        not_found_attrs = []
        
        for key in valid_words:
            resolved_key = find_attribute_key(chara_attrs, key)
            if resolved_key is not None:
                val = chara_attrs[resolved_key]
                found_attrs.append(get_output("pc.show.attr", attr=key, value=val))
            else:
                # 二次防误伤：如果残留的名片名字带有空格（如 John Doe）被切碎了
                # 只要这个碎词属于对方名字的一部分，我们就默默包容它，不报错
                if key in chara_data.get('name', ''): 
                    continue
                not_found_attrs.append(key)
        
        output_parts = []
        if target_user_id != str(event.get_sender_id()):
            output_parts.append(get_output("pc.show.named_title", name=chara_data["name"]))
            
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
        if self._get_rule_system(self._group_id(event)) == "dnd":
            yield event.plain_result(dnd_mod.template())
            return
        yield event.plain_result(get_coc_st_template())

    @st.command("template")
    async def st_template(self, event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        if self._get_rule_system(self._group_id(event)) == "dnd":
            yield event.plain_result(dnd_mod.template())
            return
        yield event.plain_result(get_coc_st_template())

    @st.command("del")
    async def st_del(self, event: AstrMessageEvent, *, args_str: str = ""):
        rule_system = self._get_rule_system(self._group_id(event))
        if rule_system == "dnd":
            async for result in self._dnd_st(event, "del", args_str):
                yield result
            return
        if not self._command_enabled(event):
            return
        """ 
        .st del <属性1> <属性2> ... 
        (V2 - 支持删除同义词组, 并保护核心属性)
        """
        
        user_id = event.get_sender_id()
        group_id = event.get_group_id()
        chara_id = charmod.get_current_character_id(group_id, user_id, rule_system=rule_system)
        
        
        if not chara_id:
            yield event.plain_result(get_output("pc.show.no_active"))
            return

        chara_data = charmod.load_character(group_id, user_id, chara_id, rule_system=rule_system)
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
            charmod.save_character(group_id, user_id, chara_id, chara_data, rule_system=rule_system)
            await self.save_log(group_id=event.get_group_id(), content=response, event=event)
            
        yield event.plain_result(response)


    @st.command("clr")
    async def st_clr(self, event: AstrMessageEvent):
        rule_system = self._get_rule_system(self._group_id(event))
        if rule_system == "dnd":
            async for result in self._dnd_st(event, "clr"):
                yield result
            return
        if not self._command_enabled(event):
            return
        """ .st clr 清除所有非核心属性 (V2 - 统一 get_output 键) """
        
        user_id = event.get_sender_id()
        client = event.bot
        group_id = event.get_group_id()
        ret = await get_sender_nickname(client, group_id, user_id)
        ret = event.get_sender_name() if ret == "" else ret
        
        chara_id = charmod.get_current_character_id(group_id, user_id, rule_system=rule_system)
        
        if not chara_id:
            yield event.plain_result(get_output("st.show.no_active")) # 复用
            return

        chara_data = charmod.load_character(group_id, user_id, chara_id, rule_system=rule_system)
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
        charmod.save_character(group_id, user_id, chara_id, chara_data, rule_system=rule_system)
        
        # 统一: pc. -> st. (参数 'count' 保持不变，因为它不是属性列表)
        response = get_output("st.clr.success", name=ret)
        
        await self.save_log(group_id=event.get_group_id(), content=response, event=event)
        yield event.plain_result(response)
        
    @st.command("export")
    async def st_export(self, event: AstrMessageEvent, *, args_str: str = ""):
        rule_system = self._get_rule_system(self._group_id(event))
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
        chara_id = charmod.get_current_character_id(group_id, user_id, rule_system=rule_system)

        if args_str:
            parts = args_str.split()
            target_id = charmod.resolve_identifier(group_id, user_id, parts[0], rule_system=rule_system)
            if target_id:
                chara_id = target_id
                args_str = " ".join(parts[1:])

        if not chara_id:
            yield event.plain_result(get_output("pc.show.no_active"))
            return

        chara_data = charmod.load_character(group_id, user_id, chara_id, rule_system=rule_system)
        if not chara_data:
            yield event.plain_result(get_output("pc.show.load_fail", id=chara_id))
            return

        if rule_system == "dnd":
            yield event.plain_result(dnd_mod.export_card(chara_data))
            return

        # 获取属性字典，如果不存在则为空字典
        chara_attrs = chara_data.get("attributes", {})
        
        if not chara_attrs:
            yield event.plain_result(get_output("pc.show.attr_missing", attribute=get_output("pc.show.attribute_any")))
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
        response = get_output("pc.export.success", name=chara_data.get('name', get_output("common.unnamed")), data=export_str)
        
        yield event.plain_result(response)

    @filter.command("fire")
    async def handle_pistol_fire(self, event: AstrMessageEvent):
        """手枪三次检定，支持模式、技能值和额外奖励/惩罚骰。"""
        rule_system = self._get_rule_system(self._group_id(event))
        if rule_system != "coc":
            yield event.plain_result("此操作目前仅支持 CoC 人物卡。")
            return
        if not self._command_enabled(event):
            return
        message = self._strip_at_text(event.get_message_str()).strip()
        command = strip_command_prefix(message, self.wakeup_prefix) or message
        full_args = re.sub(r"^fire(?:\s+|$)", "", command, count=1).strip()
        user_id = event.get_sender_id()
        group_id = self._group_id(event)
        nickname = await self._event_display_name(event)
        chara_data = charmod.get_current_character(group_id, user_id, rule_system=rule_system)
        result_text = dice_mod.handle_pistol_fire(
            full_args, name=nickname, chara_data=chara_data, group_id=group_id,
        )
        await self.save_log(group_id=group_id, content=result_text, event=event)
        yield event.plain_result(result_text)

    @command_group("pc") # type: ignore
    async def pc(self, event: AstrMessageEvent):
        pass

    # ----------------- pc create (新建并自动绑定) -----------------
    async def _pc_new_character_impl(self, event, name: str):
        rule_system = self._get_rule_system(self._group_id(event))
        if not self._command_enabled(event):
            return
        user_id = event.get_sender_id()
        group_id = str(event.get_group_id())
        
        # 1. 检查当前群路径下是否已经存在同名角色
        characters = charmod.get_all_characters(group_id, user_id, rule_system=rule_system)
        if name in characters:
            yield event.plain_result(get_output("pc.create.duplicate", name=name))
            return

        # 2. DnD 新角色从 1 级开始；旧卡不补写等级。
        attributes_dict = {"等级": 1} if rule_system == "dnd" else {}

        # 3. 调用 charmod 创建角色
        # charmod.create_character 内部逻辑：
        # - 生成 UUID
        # - 保存到 chara_data/{group_id}/{user_id}/{uuid}.json
        # - 在 metadata/{user_id}/bindings.json 中记录该群绑定此 UUID
        chara_id = charmod.create_character(group_id, user_id, name, attributes_dict, rule_system=rule_system)
        
        response = get_output("pc.create.success", name=name, id=chara_id)
        yield event.plain_result(response)
        await self.save_log(group_id=group_id, content=response, event=event)

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
        rule_system = self._get_rule_system(self._group_id(event))
        if not self._command_enabled(event):
            return
        user_id = event.get_sender_id()
        group_id = str(event.get_group_id())
        
        # 获取有序列表，方便以后实现序号操作
        characters = charmod.get_all_characters(group_id, user_id, rule_system=rule_system)
        if not characters:
            yield event.plain_result(get_output("pc.list.empty"))
            return

        # 关键：从 bindings 获取当前群绑定的角色
        current = charmod.get_current_character_id(group_id, user_id, rule_system=rule_system)
        
        # 排序以保证序号稳定
        sorted_chars = sorted(characters.items(), key=lambda x: x[0])
        chara_list = []
        for i, (name, ch_id) in enumerate(sorted_chars, 1):
            tags = []
            if ch_id == current:
                tags.append(get_output("pc.list.tag_current"))
            if charmod.is_local_binding(group_id, user_id, ch_id, rule_system=rule_system):
                tags.append(get_output("pc.list.tag_local"))
            if charmod.is_global_character(user_id, ch_id, rule_system=rule_system):
                tags.append(get_output("pc.list.tag_global"))
            tag = f"({'/'.join(tags)})" if tags else ""
            chara_list.append(f"{i}. {name} {tag}")
            
        response = get_output("pc.list.result", list="\n".join(chara_list))
        yield event.plain_result(response)

    # ----------------- pc tag (绑定/切换) -----------------
    async def _pc_tag_character_impl(self, event, identifier: str = None):
        rule_system = self._get_rule_system(self._group_id(event))
        if not self._command_enabled(event):
            return
        user_id = event.get_sender_id()
        group_id = str(event.get_group_id())
        
        if not identifier:
            # 如果不填，执行解除绑定
            charmod.set_binding_info(user_id, group_id, None, rule_system=rule_system)
            yield event.plain_result(get_output("pc.tag.cleared"))
            return

        # 解析名字或序号
        chara_id = charmod.resolve_identifier(group_id, user_id, identifier, rule_system=rule_system)
        if not chara_id:
            yield event.plain_result(get_output("pc.tag.not_found", identifier=identifier))
            return

        charmod.set_binding_info(user_id, group_id, chara_id, rule_system=rule_system)
        yield event.plain_result(get_output("pc.tag.success"))

    @pc.command("tag")
    async def pc_tag_character(self, event, identifier: str = None):
        async for result in self._pc_tag_character_impl(event, identifier):
            yield result

    @pc.command("change")
    async def pc_change_character(self, event, identifier: str = None):
        async for result in self._pc_tag_character_impl(event, identifier):
            yield result
        
    @pc.command("class")
    async def pc_class(self, event, *, args_str: str = ""):
        if not self._command_enabled(event):
            return
        if self._get_rule_system(self._group_id(event)) != "dnd":
            yield event.plain_result("职业设置只适用于 DnD，请先使用 .ruleset dnd。")
            return
        raw = re.sub(r"\[CQ:at[^\]]*\]", "", event.get_message_str())
        # Source markers inside subclass parentheses are not player mentions.
        parts = re.split(r"(\([^()\r\n]*\)|（[^（）\r\n]*）|[^\s/():（）：]+@(?:2014|2024|phb2014|phb2024)(?=\s*[:：(（]))", raw, flags=re.I)
        raw = "".join(part if part.startswith(("(", "（")) or re.search(r"@(?:2014|2024|phb2014|phb2024)$", part, re.I)
                      else part.split("@", 1)[0] for part in parts)
        command = strip_command_prefix(raw, self.wakeup_prefix) or raw
        match = re.match(r"^pc\s+(?:class|职业)(?:\s+|$)(.*)$", command, re.I | re.S)
        args = (match.group(1) if match else args_str).strip()
        query = re.fullmatch(r"(?:list|列表)(?:\s+(.*))?", args, re.I | re.S)
        if query:
            try:
                response = dnd_mod.format_subclass_catalog(query.group(1) or "")
            except ValueError as exc:
                response = str(exc)
            yield event.plain_result(response)
            return
        if args.lower() in {"help", "帮助"}:
            yield event.plain_result(dnd_mod.CLASS_HELP)
            return
        group_id = str(event.get_group_id())
        user_id = self._get_target_user_id(event)
        card = charmod.get_current_character(group_id, user_id, rule_system="dnd")
        if not card:
            yield event.plain_result(get_output("pc.show.no_active"))
            return
        if not args:
            yield event.plain_result(dnd_mod.format_card(card, "职业") + "\n" + dnd_mod.CLASS_HELP)
            return
        try:
            if args.lower() in {"clear", "clr", "清除"}:
                updated = dict(card)
                updated.pop("dnd_classes", None)
                detail = get_output("dnd.class.cleared")
            else:
                updated = dnd_mod.update_classes(card, args)
                detail = get_output("dnd.class.updated", classes=dnd_mod.format_classes(updated), level=updated['attributes']['等级'])
                if any(item.get("subclass_status") == "needs_source" for item in updated["dnd_classes"]):
                    detail += "\n子职有多个版本，请用 子职@2024 / 子职@塔莎 等明确来源；目前仅记录名称。"
            charmod.save_character(group_id, user_id, card["id"], updated, rule_system="dnd")
        except ValueError as exc:
            yield event.plain_result(str(exc))
            return
        if event.get_group_id() and event.get_platform_name() == "aiocqhttp":
            await self._update_user_nickname_card(event.bot, group_id, user_id)
        response = get_output("dnd.common.response", name=card["name"], detail=detail)
        await self.save_log(group_id=event.get_group_id(), content=response, event=event)
        yield event.plain_result(response)

    @pc.command("职业")
    async def pc_class_cn(self, event, *, args_str: str = ""):
        async for result in self.pc_class(event, args_str=args_str):
            yield result

    @pc.command("version")
    async def pc_version(self, event, *, args_str: str = ""):
        if not self._command_enabled(event):
            return
        if self._get_rule_system(self._group_id(event)) != "dnd":
            yield event.plain_result("版本设置只适用于 DnD，请先使用 .ruleset dnd。")
            return
        raw = self._strip_at_text(event.get_message_str())
        command = strip_command_prefix(raw, self.wakeup_prefix) or raw
        match = re.match(r"^pc\s+(?:version|版本)(?:\s+|$)(.*)$", command, re.I | re.S)
        args = (match.group(1) if match else args_str).strip()
        group_id = str(event.get_group_id())
        user_id = self._get_target_user_id(event)
        card = charmod.get_current_character(group_id, user_id, rule_system="dnd")
        if not card:
            yield event.plain_result(get_output("pc.show.no_active"))
            return
        try:
            if not args:
                detail = "规则版本: " + dnd_resources.card_edition(card)
            else:
                updated = dnd_resources.set_version(card, args)
                charmod.save_character(group_id, user_id, card["id"], updated, rule_system="dnd")
                detail = dnd_resources.format_resources(updated)
        except ValueError as exc:
            yield event.plain_result(str(exc))
            return
        response = get_output("dnd.common.response", name=card["name"], detail=detail)
        if args:
            await self.save_log(group_id=event.get_group_id(), content=response, event=event)
        yield event.plain_result(response)

    @pc.command("版本")
    async def pc_version_cn(self, event, *, args_str: str = ""):
        async for result in self.pc_version(event, args_str=args_str):
            yield result

    @filter.command("res", alias={"resource", "资源"})
    async def pc_resources(self, event, *, args_str: str = ""):
        if not self._command_enabled(event):
            return
        if self._get_rule_system(self._group_id(event)) != "dnd":
            yield event.plain_result("资源操作只适用于 DnD，请先使用 .ruleset dnd。")
            return
        raw = self._strip_at_text(event.get_message_str())
        command = strip_command_prefix(raw, self.wakeup_prefix) or raw
        match = re.match(r"^(?:pc\s+)?(?:res|resource|资源)(?:\s+|$)(.*)$", command, re.I | re.S)
        args = (match.group(1) if match else args_str).strip()
        group_id = str(event.get_group_id())
        user_id = self._get_target_user_id(event)
        card = charmod.get_current_character(group_id, user_id, rule_system="dnd")
        if not card:
            yield event.plain_result(get_output("pc.show.no_active"))
            return
        try:
            updated, detail = dnd_resources.resource_command(card, args)
            if updated is not None:
                charmod.save_character(group_id, user_id, card["id"], updated, rule_system="dnd")
        except ValueError as exc:
            yield event.plain_result(str(exc))
            return
        response = get_output("dnd.common.response", name=card["name"], detail=detail)
        if updated is not None:
            await self.save_log(group_id=event.get_group_id(), content=response, event=event)
        yield event.plain_result(response)

    @pc.command("res")
    async def pc_resources_legacy(self, event, *, args_str: str = ""):
        async for result in self.pc_resources(event, args_str=args_str):
            yield result

    @pc.command("resource")
    async def pc_resource_alias(self, event, *, args_str: str = ""):
        async for result in self.pc_resources(event, args_str=args_str):
            yield result

    @pc.command("资源")
    async def pc_resources_cn(self, event, *, args_str: str = ""):
        async for result in self.pc_resources(event, args_str=args_str):
            yield result

    @pc.command("rename")
    async def pc_rename_character(self, event, arg1: str, arg2: str = None):
        rule_system = self._get_rule_system(self._group_id(event))
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
            chara_id = charmod.get_current_character_id(group_id, user_id, rule_system=rule_system)
            if not chara_id:
                yield event.plain_result(get_output("pc.rename.no_active"))
                return
        else:
            # 场景：.pc rename <旧名|序号> <新名字>
            identifier = arg1
            new_name = arg2
            chara_id = charmod.resolve_identifier(group_id, user_id, identifier, rule_system=rule_system)
            if not chara_id:
                yield event.plain_result(get_output("pc.tag.not_found", identifier=identifier))
                return

        # 执行重命名
        success, info = charmod.rename_character(group_id, user_id, chara_id, new_name, rule_system=rule_system)

        if success:
            response = get_output("pc.rename.success", old_name=info, new_name=new_name)
        else:
            if info == "duplicate":
                response = get_output("pc.rename.duplicate", name=new_name)
            else:
                response = get_output("pc.rename.load_fail")

        yield event.plain_result(response)
        await self.save_log(group_id=group_id, content=response, event=event)

    # ----------------- pc delete (删除并解绑) -----------------
    async def _pc_delete_character_impl(self, event, identifier: str):
        rule_system = self._get_rule_system(self._group_id(event))
        if not self._command_enabled(event):
            return
        user_id = event.get_sender_id()
        group_id = str(event.get_group_id())
        
        # 1. 先通过名字或序号解析出 chara_id
        chara_id = charmod.resolve_identifier(group_id, user_id, identifier, rule_system=rule_system)
        if not chara_id:
            yield event.plain_result(get_output("pc.delete.not_found"))
            return
            
        # 2. 获取名字用于显示
        data = charmod.load_character(group_id, user_id, chara_id, rule_system=rule_system)
        name = data['name'] if data else get_output("common.unknown")

        # 3. 执行删除（内部含 bindings 清理）
        success, _ = charmod.delete_character_by_id(group_id, user_id, chara_id, rule_system=rule_system)
        
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
        rule_system = self._get_rule_system(self._group_id(event))
        if not self._command_enabled(event):
            return
        """
        .st show [属性...] / .st show [数字] / .st show
        (V3 - "show all" 支持同义词合并)
        """
        user_id = event.get_sender_id()
        group_id = event.get_group_id()
        args_str = args_str.strip()
        chara_id = charmod.get_current_character_id(group_id, user_id, rule_system=rule_system)

        if args_str:
            parts = args_str.split()
            target_id = charmod.resolve_identifier(group_id, user_id, parts[0], rule_system=rule_system)
            if target_id:
                chara_id = target_id
                args_str = " ".join(parts[1:])

        if not chara_id:
            yield event.plain_result(get_output("pc.show.no_active"))
            return

        chara_data = charmod.load_character(group_id, user_id, chara_id, rule_system=rule_system)
        if not chara_data:
            yield event.plain_result(get_output("pc.show.load_fail", id=chara_id))
            return
        
        chara_attrs = chara_data.get("attributes", {})
        if not chara_attrs:
            yield event.plain_result(get_output("pc.show.attr_missing", attribute=get_output("pc.show.attribute_any")))
            return

        if rule_system == "dnd":
            yield event.plain_result(dnd_mod.format_card(chara_data, args_str))
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
        rule_system = self._get_rule_system(self._group_id(event))
        if not self._command_enabled(event):
            return
        """
        手动 Push：将当前群组的角色档案标记为全域最新版。
        .pc push global：将当前角色标记为全局卡，后续跨群读写同一份 vault 档案。
        """
        user_id = str(event.get_sender_id())
        group_id = str(event.get_group_id())
        
        # 1. 获取当前群绑定的角色 ID
        chara_id = charmod.get_current_character_id(group_id, user_id, rule_system=rule_system)
        if not chara_id:
            # 这里的 get_output 可以在语言包里写：“本群未绑定角色，无法执行 Push。”
            yield event.plain_result(get_output("pc.push.no_pc"))
            return

        is_global_mode = (mode or "").lower() in ("global", "g", "全局")
        if is_global_mode:
            if charmod.mark_character_global(group_id, user_id, chara_id, rule_system=rule_system):
                yield event.plain_result(get_output("pc.push.global_success"))
            else:
                yield event.plain_result(get_output("pc.push.fail"))
            return

        is_local_mode = (mode or "").lower() in ("local", "unglobal", "un-global", "取消全局", "本地")
        if is_local_mode:
            if charmod.unmark_character_global(group_id, user_id, chara_id, rule_system=rule_system):
                yield event.plain_result(get_output("pc.push.local_success"))
            else:
                yield event.plain_result(get_output("pc.push.fail"))
            return

        # 2. 调用后端 touch 逻辑，刷新 mtime 并写入全域档案库
        if charmod.touch_character(group_id, user_id, chara_id, rule_system=rule_system):
            if charmod.is_global_character(user_id, chara_id, rule_system=rule_system):
                yield event.plain_result(get_output("pc.push.global_sync"))
            else:
                yield event.plain_result(get_output("pc.push.success"))
        else:
            yield event.plain_result(get_output("pc.push.fail"))

    # ----------------- .pc fetch -----------------
    @pc.command("fetch")
    async def pc_fetch_list(self, event):
        rule_system = self._get_rule_system(self._group_id(event))
        if not self._command_enabled(event):
            return
        user_id = str(event.get_sender_id())
        
        all_chars = charmod.get_all_universal_characters(user_id, rule_system=rule_system)
        cache_key = (user_id, rule_system)
        self.uni_cache[cache_key] = all_chars
        
        if not all_chars:
            yield event.plain_result(get_output("pc.uni.no_pc"))
            return
            
        char_lines = []
        for i, char in enumerate(all_chars, 1):
            # 格式化显示时间
            logger.info(char)
            time_str = time.strftime("%m-%d %H:%M", time.localtime(char['mtime']))
            # 标记来源（如果是 Vault 则高亮）
            source_label = get_output("pc.uni.source_global") if char.get("global") else f"{char['group_id']}"
            
            char_lines.append(get_output("pc.uni.line", index=i, name=char["name"], source=source_label, time=time_str))
        
        msg = "\n".join(char_lines)
        yield event.plain_result(get_output("pc.uni.success", msg=msg))

    # ----------------- .pc pull -----------------
    @pc.command("pull")
    async def pc_pull_character(self, event, index: int, mode: str = None):
        rule_system = self._get_rule_system(self._group_id(event))
        if not self._command_enabled(event):
            return
        user_id = str(event.get_sender_id())
        group_id = str(event.get_group_id())
        
        # 1. 获取包含 mtime 信息的最新全域列表
        all_chars = charmod.get_all_universal_characters(user_id, rule_system=rule_system)
        cache_key = (user_id, rule_system)
        self.uni_cache[cache_key] = all_chars
        
        cache = self.uni_cache.get(cache_key)
        if not cache or index > len(cache) or index <= 0:
            yield event.plain_result(get_output("pc.pull.no_pc"))
            return
            
        target = cache[index-1] # 这是全域中最热/最新的那个版本信息
        target_uuid = target['uuid']
        global_mode = (mode or "").lower() in ("global", "g", "全局")
        target_is_global = bool(target.get("global")) or charmod.is_global_character(user_id, target_uuid, rule_system=rule_system)

        if global_mode:
            success = charmod.mark_character_global(target["group_id"], user_id, target_uuid, rule_system=rule_system)
            if success:
                charmod.set_binding_info(user_id, group_id, target_uuid, global_binding=True, rule_system=rule_system)
                yield event.plain_result(get_output("pc.pull.global_success", name=target["name"]))
            else:
                yield event.plain_result(get_output("pc.pull.fail"))
            return

        if target_is_global:
            charmod.set_binding_info(user_id, group_id, target_uuid, global_binding=True, rule_system=rule_system)
            yield event.plain_result(get_output("pc.pull.global_success", name=target["name"]))
            return

        # 2. 获取本群当前该角色的信息（如果存在）
        local_exists = charmod.check_character_file_exists(group_id, user_id, target_uuid, rule_system=rule_system)
        
        needs_copy = True
        if local_exists:
            # 获取本地文件的修改时间进行对比
            local_mtime = charmod.get_local_file_mtime(group_id, user_id, target_uuid, rule_system=rule_system)
            # 如果本地的时间 >= 全域最热的时间，说明本地已经是最新，无需拷贝
            if local_mtime >= target['mtime']:
                needs_copy = False

        # 3. 执行逻辑分支
        if not needs_copy:
            # 文件已经是最新，仅检查绑定
            current_bound = charmod.get_current_character_id(group_id, user_id, rule_system=rule_system)
            if current_bound == target_uuid:
                yield event.plain_result(get_output("pc.pull.exist")) # 完全一致，无需操作
            else:
                charmod.set_binding_info(user_id, group_id, target_uuid, local_binding=True, rule_system=rule_system)
                yield event.plain_result(get_output("pc.pull.success", name=target['name']))
            return

        # 4. 需要拷贝（本地不存在，或者远程版本更新）
        # 调用 clone，内部执行物理覆盖
        success = charmod.clone_character_to_group(user_id, target['group_id'], group_id, target_uuid, rule_system=rule_system)
        
        if success:
            charmod.set_binding_info(user_id, group_id, target_uuid, local_binding=True, rule_system=rule_system)
            if local_exists : 
                yield event.plain_result(get_output("pc.pull.sync", name=target['name']))
            else :
                yield event.plain_result(get_output("pc.pull.success", name=target['name']))
        else:
            yield event.plain_result(get_output("pc.pull.fail"))

    # ----------------- filter sn -----------------
    async def _set_nickname_impl(self, event, mode: str = "coc"):
        rule_system = self._get_rule_system(self._group_id(event))
        if event.get_platform_name() != "aiocqhttp":
            yield event.plain_result(get_output("nick.platform_unsupported"))
            return

        if not event.get_group_id():
            yield event.plain_result("群名片只能在群聊中修改。")
            return
        client = event.bot
        user_id = event.get_sender_id()
        group_id = event.get_group_id()

        chara_id = charmod.get_current_character_id(group_id, user_id, rule_system=rule_system)
        chara_data = charmod.load_character(group_id, user_id, chara_id, rule_system=rule_system)
        if not chara_data:
            yield event.plain_result(get_output("nick.no_character", id=chara_id))
            return

        new_card = build_card_by_mode(chara_data, mode)

        payloads = {"group_id": group_id, "user_id": user_id, "card": new_card}
        try:
            await client.api.call_action("set_group_card", **payloads)
        except Exception as exc:
            logger.error(f"修改群名片失败: {exc}")
            yield event.plain_result("修改群名片失败，请检查机器人权限后重试。")
            return

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
        rule_system = self._get_rule_system(group_id)
        chara_id = charmod.get_current_character_id(group_id, user_id, rule_system=rule_system)
        if not chara_id:
            return False
            
        chara_data = charmod.load_character(group_id, user_id, chara_id, rule_system=rule_system)
        if not chara_data:
            return False

        new_card = build_card_by_mode(chara_data)
        payloads = {"group_id": group_id, "user_id": user_id, "card": new_card}
        
        try:
            await client.api.call_action("set_group_card", **payloads)
            return True
        except Exception as e:
            logger.error(f"自动更新群名片失败: {e}")
            return False

    
    # ========================================================= #
    def _resolve_skill_check(self, group_id, user_id, skill_name: str, skill_value: str = None):
        rule_system = self._get_rule_system(group_id)
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
            raw_value = charmod.get_skill_value(group_id, user_id, lookup_name, rule_system=rule_system)

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
            ret = get_output("skill_check.proxy_name", name=ret, operator=event.get_sender_name())

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
        await self.save_log(group_id = event.get_group_id(), content = result_message, event=event)
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
            ret = get_output("skill_check.proxy_name", name=ret, operator=event.get_sender_name())

        result_message = dice_mod.roll_attribute_until_success(skill_name, skill_value, str(group_id), ret)
        payloads = {
            "group_id": group_id,
            "message": [
                {"type": "reply", "data": {"id": event.message_obj.message_id}},
                {"type": "at", "data": {"qq": event.get_sender_id()}},
                {"type": "text", "data": {"text": "\n" + result_message}}
            ]
        }
        await self.save_log(group_id=group_id, content=result_message, event=event)
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
            ret = get_output("skill_check.proxy_name", name=ret, operator=event.get_sender_name())

        result_message = dice_mod.roll_attribute_penalty(roll_times, dice_count, skill_name, skill_value, str(group_id), ret)

        payloads = {
            "group_id": group_id,
            "message": [
                {"type": "reply", "data": {"id": event.message_obj.message_id}},
                {"type": "at", "data": {"qq": event.get_sender_id()}},
                {"type": "text", "data": {"text": "\n" + result_message}}
            ]
        }

        await self.save_log(group_id = event.get_group_id(), content = result_message, event=event)
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
            ret = get_output("skill_check.proxy_name", name=ret, operator=event.get_sender_name())

        result_message = dice_mod.roll_attribute_bonus(roll_times, dice_count, skill_name, skill_value, str(group_id), ret)

        payloads = {
            "group_id": group_id,
            "message": [
                {"type": "reply", "data": {"id": event.message_obj.message_id}},
                {"type": "at", "data": {"qq": event.get_sender_id()}},
                {"type": "text", "data": {"text": "\n" + result_message}}
            ]
        }

        await self.save_log(group_id = event.get_group_id(), content = result_message, event=event)
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
            ret = get_output("skill_check.proxy_name", name=ret, operator=event.get_sender_name())

        result_message = dice_mod.roll_attribute(roll_times, skill_name, skill_value, str(group_id), ret)
        await self.save_log(group_id=group_id, content="[Hidden Skill Check]" + result_message, event=event)

        yield event.plain_result(get_output("skill_check.hidden.sent"))
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
            yield event.plain_result(get_output("versus.error.format"))
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
            left_label = event.get_sender_name() or get_output("versus.label.left")
            right_label = get_output("versus.label.right")
        elif opponent_user_id:
            right_skill_name, right_value = self._resolve_skill_check(group_id, opponent_user_id, spec.skill_name, None)
            left_label = event.get_sender_name() or str(event.get_sender_id())
            try:
                right_label = await get_sender_nickname(event.bot, group_id, opponent_user_id) or str(opponent_user_id)
            except Exception:
                right_label = str(opponent_user_id)
        else:
            yield event.plain_result(get_output("versus.error.no_target"))
            return

        try:
            left_value = int(left_value)
            right_value = int(right_value)
        except (TypeError, ValueError):
            yield event.plain_result(get_output("versus.error.invalid_value"))
            return

        left_name = get_output("versus.participant", name=left_label, skill_name=left_skill_name)
        right_name = get_output("versus.participant", name=right_label, skill_name=right_skill_name)
        result_message = dice_mod.roll_opposed_check(left_name, left_value, right_name, right_value, str(group_id))
        await self.save_log(group_id=group_id, content=result_message, event=event)
        yield event.plain_result(result_message)

        
    # @filter.command("en")
    async def pc_grow_up(self, event: AstrMessageEvent, skill_name: str, skill_value: str = None, target_user_id: str = None):
        """
        .en 技能成长判定
        调用 character 模块的 grow_up 生成结果文本，再通过 event 发送给用户。
        """
        rule_system = self._get_rule_system(self._group_id(event))
        user_id = target_user_id or event.get_sender_id()
        group_id = event.get_group_id()
        skill_name = self._resolve_user_alias(str(user_id), skill_name)

        # 调用 character.py 中同步逻辑函数，不传入额外函数引用
        result_str = charmod.grow_up(
            group_id,
            user_id,
            skill_name=skill_name,
            skill_value=skill_value,
            rule_system=rule_system,
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

        await self.save_log(group_id = event.get_group_id(), content = result_str, event=event)
        await client.api.call_action("send_group_msg", **payloads)


    # ========================================================= #
    # san check
    # @filter.command("sc")
    async def pc_san_check(self, event: AstrMessageEvent, loss_formula: str, target_user_id: str = None):
        """理智检定"""
        rule_system = self._get_rule_system(self._group_id(event))
        if rule_system != "coc":
            yield event.plain_result("此操作目前仅支持 CoC 人物卡。")
            return
        user_id = target_user_id or event.get_sender_id()
        operator_user_id = str(event.get_sender_id())
        group_id = event.get_group_id()
        chara_data = charmod.get_current_character(group_id, user_id, rule_system=rule_system)
        client = event.bot
        
        if not chara_data:
            if str(user_id) == operator_user_id:
                yield event.plain_result(get_output("pc.show.no_active"))
            else:
                yield event.plain_result(get_output("pc.show.target_no_active"))
            return

        roll_result, san_value, result_msg, loss, new_san, expr = sanity.san_check(chara_data, loss_formula)

        # 更新人物卡
        chara_data["attributes"]["san"] = new_san
        charmod.save_character(group_id, user_id, chara_data["id"], chara_data, rule_system=rule_system)
        
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
        
        await self.save_log(group_id = event.get_group_id(), content = text, event=event)
        
        await client.api.call_action("send_group_msg", **payloads)


    async def pc_temporary_insanity(self, event: AstrMessageEvent):
        """临时疯狂"""
        result = sanity.get_temporary_insanity(sanity.phobias, sanity.manias)
        text = get_output("san.temporary_insanity", result=result, name=event.get_sender_name())
        await self.save_log(group_id = event.get_group_id(), content = text, event=event)
        yield event.plain_result(text)


    async def pc_long_term_insanity(self, event: AstrMessageEvent):
        """长期疯狂"""
        result = sanity.get_long_term_insanity(sanity.phobias, sanity.manias)
        text = get_output("san.long_term_insanity", result=result, name=event.get_sender_name())
        await self.save_log(group_id = event.get_group_id(), content = text, event=event)
        yield event.plain_result(text)


    @filter.command("init")
    async def initiative(self , event: AstrMessageEvent , instruction: str = None, player_name: str = None):
        if not self._command_enabled(event):
            return
        group_id = event.get_group_id()
        user_name = event.get_sender_name()
        if not instruction:
            yield event.plain_result(get_output("initiative.list", content=self.initiative_manager.format_list(group_id)))
        elif instruction == "clr":
            self.initiative_manager.clear(group_id)
            yield event.plain_result(get_output("initiative.clear"))
        elif instruction == "del":
            if not player_name:
                player_name = user_name
                if self._get_rule_system(self._group_id(event)) == "dnd":
                    card = charmod.get_current_character(group_id, event.get_sender_id(), rule_system="dnd")
                    if card:
                        player_name = card["name"]
            self.initiative_manager.remove_by_name(group_id, player_name)
            yield event.plain_result(get_output("initiative.remove_name", name=player_name))

    # @filter.command("ri")
    async def roll_initiative(self , event: AstrMessageEvent, expr: str = None):
        if not self._command_enabled(event):
            return
        group_id = event.get_group_id()
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()

        if not expr and self._get_rule_system(self._group_id(event)) == "dnd":
            card = charmod.get_current_character(group_id, user_id, rule_system="dnd")
            if not card:
                yield event.plain_result(get_output("pc.show.no_active"))
                return
            try:
                bonus, _ = dnd_mod.check_bonus(card, "先攻")
            except ValueError as exc:
                yield event.plain_result(str(exc))
                return
            user_name = card["name"]
            expr = f"{bonus:+d}"
        try:
            init_value, player_name = self.initiative_manager.parse_roll(expr, user_name)
        except (ValueError, AttributeError):
            yield event.plain_result("请使用 .ri、.ri +4 或 .ri 18 角色名。")
            return
        item = InitiativeItem(player_name, init_value, user_id)
        self.initiative_manager.remove_by_name(group_id, player_name)
        self.initiative_manager.add_item(group_id, item)
        yield event.plain_result(get_output("initiative.add", name=player_name, value=init_value))
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
            yield event.plain_result(get_output("initiative.empty"))
        elif current_item is None:
            yield event.plain_result(get_output("initiative.next_turn", name=next_item.name, value=next_item.init_value))
        else:
            yield event.plain_result(get_output(
                "initiative.turn_advance",
                current_name=current_item.name,
                next_name=next_item.name,
                value=next_item.init_value,
            ))
        return

    
    # ========================================================= #

    @filter.command("name", alias={"取名"})
    async def generate_name(self, event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        # Read the whole message: command argument splitting would truncate free-form requests.
        message = self._strip_at_text(event.get_message_str()).strip()
        command = strip_command_prefix(message, self.wakeup_prefix) or message
        args = re.sub(r"^(?:name|取名)(?:\s+|$)", "", command, count=1).strip()
        try:
            request = parse_name_request(args)
            backend = str(self.config.get("name_backend", "faker")).strip().lower()
            if backend == "faker":
                names = generate_faker_names(request)
                response = get_output("generated_names", num=len(names), names=", ".join(names))
            elif backend == "llm":
                provider_id = str(self.config.get("name_llm_provider_id", "") or "").strip()
                response = await generate_llm_names(self.context, request, provider_id)
            else:
                raise ValueError("name_backend 配置须为 faker 或 llm。")
        except ValueError as exc:
            yield event.plain_result(f"{exc}\n{NAME_USAGE}")
            return
        except TimeoutError:
            yield event.plain_result("取名请求超时，请稍后重试。")
            return
        except Exception as exc:
            logger.error(f"name generation failed: {type(exc).__name__}")
            yield event.plain_result("取名失败，请稍后重试或检查 LLM 提供商配置。")
            return
        yield event.plain_result(response)

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
    async def toggle_ob_mode(self, event: AstrMessageEvent, action: str = ""):
        if not self._command_enabled(event):
            return
        group = event.message_obj.group_id
        if action.lower() in {"list", "ls"}:
            lines = await logger_core.list_observers(group)
            yield event.plain_result("\n".join(lines))
            return

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
        ob_lines = await logger_core.list_observers(group)
        info = "\n".join([info, *ob_lines])
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
        ob_lines = await logger_core.list_observers(group)
        info = "\n".join([info, *ob_lines])
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
            return event.plain_result(get_output("log.get_usage"))

        name = parts[2]
        session_uuid, sec = await logger_core.get_session(group, name)

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
            return event.plain_result(get_output("log.export_usage"))

        if parts[2].lower() in {"text", "txt"}:
            if len(parts) < 4:
                return event.plain_result(get_output("log.export_text_usage"))
            info = await logger_core.export_session_text(group, parts[3])
            return event.plain_result(info)

        name = parts[2]
        session_uuid, sec = await logger_core.get_session(group, name)
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
            return event.plain_result(get_output("log.ob.usage"))

        targets = []
        for comp in getattr(event.message_obj, "message", []):
            if isinstance(comp, Comp.At):
                targets.append(str(comp.qq))

        if not targets and len(parts) >= 4:
            targets.append(parts[3])

        if not targets:
            return event.plain_result(get_output("log.ob.missing_target"))

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
        yield event.plain_result(get_output("alias.added", alias=alias_name, target=target_name))

    @alias.command("del")
    async def alias_del_cmd(self, event: AstrMessageEvent, alias_name: str):
        if not self._command_enabled(event):
            return
        user_id = str(event.get_sender_id())
        aliases = self._get_user_aliases(user_id)
        if alias_name not in aliases:
            yield event.plain_result(get_output("alias.not_found", alias=alias_name))
            return
        aliases.pop(alias_name, None)
        self._save_user_aliases(user_id, aliases)
        yield event.plain_result(get_output("alias.deleted", alias=alias_name))

    @alias.command("list")
    async def alias_list_cmd(self, event: AstrMessageEvent):
        if not self._command_enabled(event):
            return
        aliases = self._get_user_aliases(str(event.get_sender_id()))
        if not aliases:
            yield event.plain_result(get_output("alias.empty"))
            return
        lines = [f"{alias_name} -> {target_name}" for alias_name, target_name in sorted(aliases.items())]
        yield event.plain_result(get_output("alias.list", aliases="\n".join(lines)))

    @filter.command("bot")
    async def bot_cmd(self, event: AstrMessageEvent, action: str = None):
        if not self._bot_command_targets_self(event):
            return
        action = (action or "").lower()
        if not self._is_bot_enabled(self._group_id(event), event) and action not in {"on", "quit"}:
            return
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
        if action == "on":
            self._set_bot_enabled(event, True)
            yield event.plain_result(get_output("bot.enabled"))
            return

        if action == "off":
            self._set_bot_enabled(event, False)
            yield event.plain_result(get_output("bot.disabled"))
            return

        if action == "quit":
            if not group_id:
                yield event.plain_result(get_output("bot.quit_private"))
                return
            yield event.plain_result(get_output("bot.quit"))
            try:
                await event.bot.api.call_action("set_group_leave", group_id=group_id)
            except Exception as exc:
                logger.error(f"退群失败（群 {group_id}）：{exc}")
                yield event.plain_result(get_output("bot.quit_error", error=exc))
            return

        if action == "status":
            enabled = self._is_bot_enabled(self._group_id(event), event)
            status_key = "bot.status_on" if enabled else "bot.status_off"
            yield event.plain_result(get_output("bot.status", status=get_output(status_key)))
            return

        yield event.plain_result(get_output("bot.usage"))

    @filter.command("setcoc")
    async def setcoc_cmd(self, event: AstrMessageEvent, command: str = " "):
        if not self._command_enabled(event):
            return
        group_id = self._group_id(event)
        self._set_rule_system(group_id, "coc")
        result = modify_coc_great_sf_rule_command(group_id, command)
        yield event.plain_result(result)

    async def _set_rule_system_cmd(self, event: AstrMessageEvent, system: str = None):
        if not self._command_enabled(event):
            return
        context_id = self._group_id(event)
        if not system:
            yield event.plain_result(
                self._format_rule_system_status(context_id)
                + "\n可用规则：coc、dnd。用法：.ruleset dnd / .ruleset coc"
            )
            return

        normalized = self._set_rule_system(context_id, system)
        if not normalized:
            yield event.plain_result("不认识这个规则系统。可用规则：coc、dnd。")
            return

        meta = RULE_SYSTEMS[normalized]
        yield event.plain_result(f"已切换到 {meta['label']}，.r 默认骰现在是 {meta['default_roll']}。")

    @filter.command("ruleset")
    async def ruleset_cmd(self, event: AstrMessageEvent, system: str = None):
        async for result in self._set_rule_system_cmd(event, system):
            yield result

    @filter.command("setrule")
    async def setrule_cmd(self, event: AstrMessageEvent, system: str = None):
        async for result in self._set_rule_system_cmd(event, system):
            yield result

    @filter.command("system")
    async def system_cmd(self, event: AstrMessageEvent, system: str = None):
        async for result in self._set_rule_system_cmd(event, system):
            yield result

    # 识别所有信息
    async def _dispatch_inline_command(self, event: AstrMessageEvent, parsed, target_user_id: str):
        if parsed.cmd == "dnd_check" and self._get_rule_system(self._group_id(event)) == "dnd":
            async for result in self._dnd_check(event, parsed.expr):
                yield result
            return
        if (self._get_rule_system(self._group_id(event)) != "coc"
                and parsed.cmd in {"ra", "rc", "rab", "rap", "rau", "rah", "rch", "rav", "rcv", "en", "sc"}):
            yield event.plain_result("此指令适用于 CoC；DnD 请使用 .rc 技能 / .rc 属性豁免。")
            return
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
        elif cmd in {"radv", "rdis"}:
            expression = self._advantage_roll_expression(
                self._group_id(event), expr, disadvantage=cmd == "rdis"
            )
            await self.handle_roll_dice(event, expression, remark)
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
        if parsed.cmd == "dnd_check" and self._get_rule_system(self._group_id(event)) == "dnd":
            async for result in self._dnd_check(event, parsed.expr):
                yield result
            return
        rule_system = self._get_rule_system(self._group_id(event))
        if (rule_system != "coc"
                and parsed.cmd in {"ra", "rc", "rab", "rap", "rau", "rah", "rch", "rav", "rcv", "en", "sc"}):
            yield event.plain_result("此指令适用于 CoC；DnD 请使用 .rc 技能 / .rc 属性豁免。")
            return
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
        elif cmd in {"radv", "rdis"}:
            expression = self._advantage_roll_expression(
                context_id, expr, disadvantage=cmd == "rdis"
            )
            yield event.plain_result(dice_mod.handle_roll_dice(expression, name=name, remark=remark))
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
            yield event.plain_result(charmod.grow_up(context_id, user_id, skill_name=expr, skill_value=skill_value, rule_system=rule_system))
        elif cmd == "sc":
            chara_data = charmod.get_current_character(context_id, user_id, rule_system=rule_system)
            if not chara_data:
                yield event.plain_result(get_output("pc.show.no_active"))
                return

            roll_result, san_value, result_msg, loss, new_san, parsed_expr = sanity.san_check(chara_data, expr)
            chara_data["attributes"]["san"] = new_san
            charmod.save_character(context_id, user_id, chara_data["id"], chara_data, rule_system=rule_system)

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
            yield event.plain_result(get_output("private.unsupported"))

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

    async def _handle_group_post_command(self, event: AstrMessageEvent, command_text: str):
        payload = command_text[len("挂团"):].lstrip(" \t\n")
        all_posts = self._cleanup_group_posts(self._load_group_posts())
        group_id = str(self._group_id(event))
        posts = [post for post in all_posts if str(post.get("group_id", "")) == group_id]

        if not payload:
            key = (group_id, str(event.get_sender_id()))
            wait_seconds = self.config.get("group_post_wait_seconds", 120)
            try:
                wait_seconds = max(1, int(wait_seconds))
            except (TypeError, ValueError):
                wait_seconds = 120
            self.pending_group_posts[key] = time.time() + wait_seconds
            rule = self._get_rule_system(group_id)
            template = get_output(f"group_post.template_{rule}")
            yield event.plain_result(get_output("group_post.waiting", seconds=wait_seconds) + "\n" + template)
            return

        if payload.lower() in {"list", "列表", "查看"}:
            output_path = os.path.join(self.plugin_dir, f"temp_group_posts_{int(time.time() * 1000)}.png")
            try:
                await self._render_group_posts_image(posts, output_path)
            except RuntimeError as exc:
                yield event.plain_result(str(exc))
                return
            yield event.chain_result([Image.fromFileSystem(output_path)])
            return

        if payload.lower().startswith(("del ", "delete ", "删除 ")):
            post_id = payload.split(None, 1)[1].strip()
            remaining = [post for post in posts if post.get("id") != post_id]
            if len(remaining) == len(posts):
                yield event.plain_result(get_output("group_post.not_found", post_id=post_id))
                return
            updated_posts = [
                post for post in all_posts
                if str(post.get("group_id", "")) != group_id
            ] + remaining
            self._save_group_posts(updated_posts)
            yield event.plain_result(get_output("group_post.deleted", post_id=post_id))
            return

        schema_name, parsed = self._parse_group_post(payload)
        if schema_name is None:
            yield event.plain_result(get_output("group_post.invalid", reason=parsed))
            return

        try:
            bot_user_id = str(
                getattr(getattr(event, "message_obj", None), "self_id", None)
                or getattr(event.bot, "self_id", "")
            )
            if not bot_user_id:
                bot_user_id = str(getattr(event.message_obj, "self_id", ""))
            member = await event.bot.api.call_action(
                "get_group_member_info",
                group_id=group_id,
                user_id=bot_user_id,
                no_cache=True,
            )
            role = str((member or {}).get("role", "member")).lower()
        except Exception as exc:
            logger.warning(f"无法检查挂团发布权限（群 {group_id}）：{exc}")
            yield event.plain_result(get_output("group_post.permission_check_failed"))
            return

        if role not in {"admin", "owner"}:
            yield event.plain_result(get_output("group_post.bot_not_admin"))
            return

        post_id = f"{int(time.time() * 1000)}"
        post = {
            "id": post_id,
            "schema": schema_name,
            "fields": parsed,
            "created_at": time.time(),
            "creator_id": str(event.get_sender_id()),
            "group_id": group_id,
        }
        notice_lines = [f"【挂团公告 #{post_id}】"]
        notice_lines.extend(
            f"丨{label}：{value}" for label, value in parsed.items() if value
        )
        notice = "\n".join(notice_lines)
        notice_error = None
        for action in ("send_group_notice", "_send_group_notice"):
            try:
                await event.bot.api.call_action(action, group_id=group_id, content=notice)
                notice_error = None
                break
            except Exception as exc:
                notice_error = exc
        if notice_error is not None:
            logger.error(f"发布群公告失败（群 {group_id}）：{notice_error}")
            yield event.plain_result(get_output("group_post.publish_failed", error=notice_error))
            return

        self._save_group_posts(all_posts + [post])
        yield event.plain_result(get_output("group_post.created", post_id=post_id))

    @event_message_type(EventMessageType.GROUP_MESSAGE, priority=sys.maxsize)
    async def identify_command(self, event: AstrMessageEvent):

        message = event.message_obj.message_str
        await self._record_group_message(event, message)

        target_user_id = self._get_target_user_id(event)

        # 在保留完整日志后，把文本里的 CQ 码和 @ 残留抹掉，
        # 确保它们绝对不会掉进下面那个“诡异”的正则解析器里
        message = self._strip_at_text(message)

        pending_key = (str(self._group_id(event)), str(event.get_sender_id()))
        pending_until = self.pending_group_posts.get(pending_key)
        if pending_until is not None:
            if time.time() <= pending_until and not any(message.startswith(prefix) for prefix in self.wakeup_prefix):
                self.pending_group_posts.pop(pending_key, None)
                async for result in self._handle_group_post_command(event, "挂团\n" + message):
                    yield result
                return
            if time.time() > pending_until:
                self.pending_group_posts.pop(pending_key, None)

        # logger.info(f"{message}, {target_user_id}")

        # yield event.plain_result(message)

        command_text = strip_command_prefix(message, self.wakeup_prefix)
        if command_text is None:
            return
        if command_text == "挂团" or command_text.startswith("挂团 ") or command_text.startswith("挂团\n"):
            if not self._command_enabled(event):
                self._stop_event(event)
                return
            async for result in self._handle_group_post_command(event, command_text):
                yield result
            return
        if self._is_native_reset_command(command_text):
            return
        if re.match(r"^bot(?:\s|$)", command_text, re.IGNORECASE) and not self._bot_command_targets_self(event):
            return
        if not self._is_bot_enabled(self._group_id(event), event) and not self._allowed_when_disabled(command_text):
            self._stop_event(event)
            return
        help_kind, help_target = self._resolve_help_request(command_text)
        if help_kind:
            if help_kind == "builtin":
                return
            self._suppress_astrbot_builtin_help(event)
            self._stop_event(event)
            if not self._command_enabled(event):
                return
            if help_kind == "page":
                async for result in self._yield_help_result(event, help_target):
                    yield result
            else:
                async for result in self._yield_help_command_result(event, help_target):
                    yield result
            return

        parsed = parse_inline_command(command_text, self._default_roll_expr(self._group_id(event)))
        if parsed is None:
            return

        async for result in self._dispatch_inline_command(event, parsed, target_user_id):
            yield result
        return

    @event_message_type(EventMessageType.PRIVATE_MESSAGE)
    async def identify_private_command(self, event: AstrMessageEvent):
        message = event.message_obj.message_str

        command_text = strip_command_prefix(message, self.wakeup_prefix)
        if command_text is None:
            return
        if self._is_native_reset_command(command_text):
            return
        help_kind, help_target = self._resolve_help_request(command_text)
        if help_kind:
            if help_kind == "builtin":
                return
            self._suppress_astrbot_builtin_help(event)
            self._stop_event(event)
            if not self._command_enabled(event):
                return
            if help_kind == "page":
                async for result in self._yield_help_result(event, help_target):
                    yield result
            else:
                async for result in self._yield_help_command_result(event, help_target):
                    yield result
            return

        if not self._is_bot_enabled(self._group_id(event), event) and not command_text.lower().startswith("bot"):
            self._stop_event(event)
            return

        parsed = parse_inline_command(command_text, self._default_roll_expr(self._group_id(event)))
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

    def handle_spell_html(self, content: str, spellsource: str, new_version: bool) -> SpellFeature:
        spellname_match = re.search(r"(<h4>(.*?)</h4>)", content, flags=re.IGNORECASE | re.DOTALL)
        spellname_with_header = spellname_match.group(1)  # 修正：用 group(1) 才能替换掉完整的 <h4>...</h4>
        spellname = spellname_match.group(2)

        spellcontent = content.replace(spellname_with_header, "")
        spellcontent_multiline = spellcontent.split("<BR>")

        # index 0 - spell belonging
        spellbelonging_match = re.search(r"<em>(.*?) (.*?)（(.*)）", spellcontent_multiline[0], flags=re.IGNORECASE | re.DOTALL)
        format_check = spellbelonging_match.group(2)
        if format_check == "戏法":
            spellschool = spellbelonging_match.group(1)
            spelllevel = "零"
        else:
            spellschool = spellbelonging_match.group(2)
            spelllevel_withcharacter = spellbelonging_match.group(1)
            spelllevel_match = re.search(r"(.*?)环", spelllevel_withcharacter, flags=re.IGNORECASE | re.DOTALL)
            spelllevel = spelllevel_match.group(1)

        spellclasses = spellbelonging_match.group(3)
        if not new_version:
            spellclasses = spellclasses.replace("魔契师", "邪术师")

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
        reference = get_output("spell.reference")
        cantrip_suffix = get_output("spell.cantrip_suffix") if res.spelllevel == get_output("spell.cantrip_level") else ""
        sample_html = f"""
        <H4>{res.spellname}</H4>
        <em>{get_output("spell.level_line", level=res.spelllevel, cantrip_suffix=cantrip_suffix, school=res.spellschool, classes=res.spellclasses)}</em>
        <p>
        <strong>{get_output("spell.label.casting_time")}</strong>{res.castingtime}<br>
        <strong>{get_output("spell.label.range")}</strong>{res.spellrange}<br>
        <strong>{get_output("spell.label.components")}</strong>{res.components}<br>
        <strong>{get_output("spell.label.duration")}</strong>{res.duration}
        </p>
        <p>{res.description}</p>
        <p><ref>{reference}</ref><span class="spell-source-bottom">【{res.source}】</span></p>
        """
        return re.sub(r"</?u\b[^>]*>", lambda match: "<strong>" if match.group(0)[1] != "/" else "</strong>", sample_html, flags=re.IGNORECASE)

    @staticmethod
    def _html_fragment_to_text(value: str) -> str:
        text = re.sub(r"(?i)<br\s*/?>", "\n", value or "")
        text = re.sub(r"(?i)</p\s*>", "\n", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @classmethod
    def spellfeature_to_text(cls, res: SpellFeature) -> str:
        cantrip_suffix = get_output("spell.cantrip_suffix") if res.spelllevel == get_output("spell.cantrip_level") else ""
        level_line = get_output(
            "spell.level_line",
            level=res.spelllevel,
            cantrip_suffix=cantrip_suffix,
            school=res.spellschool,
            classes=res.spellclasses,
        )
        return "\n".join(
            part
            for part in [
                f"# {res.spellname}",
                level_line,
                f"- {get_output('spell.label.casting_time')}{cls._html_fragment_to_text(res.castingtime)}",
                f"- {get_output('spell.label.range')}{cls._html_fragment_to_text(res.spellrange)}",
                f"- {get_output('spell.label.components')}{cls._html_fragment_to_text(res.components)}",
                f"- {get_output('spell.label.duration')}{cls._html_fragment_to_text(res.duration)}",
                cls._html_fragment_to_text(res.description),
                f"> {get_output('spell.reference')}【{res.source}】",
            ]
            if part
        )

    def search_spell_in_folder(self, spell_name: str, new_version: bool) -> SpellFeature:
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
                if not new_version and ("玩家手册2024" in str(htm_file) or "费伦英雄" in str(htm_file)):
                    continue
                try:
                    with open(htm_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    extracted_html = self.extract_spell_html(content, spell_name)
                    if extracted_html:
                        return self.handle_spell_html(extracted_html, ssf_data[folder], new_version)
                except Exception as e:
                    pass
                    
        return None

    async def render_html_to_image(self, html_content: str, output_filename: str):
        custom_css = """
        body { width: 600px; margin: 0; padding: 0; background-color: #fdfaf6; }
        #card-container { padding: 30px; box-sizing: border-box; width: 100%; color: #333333; font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif; }
        h4 { color: #7a200d; border-bottom: 2px solid #c9ad6a; padding-bottom: 5px; font-size: 24px; margin-top: 0; margin-bottom: 6px; }
        #card-container > p:last-of-type { position: relative; }
        .spell-source-bottom { position: absolute; right: 0; bottom: 0; color: #888888; font-style: italic; font-size: 13px; white-space: nowrap; }
        p { line-height: 1.6; font-size: 15px; text-align: justify; }
        table { width: 100% !important; max-width: 100%; table-layout: auto; border-collapse: collapse; }
        blockquote { margin: 10px 0; padding: 0; }
        td { padding: 5px 10px !important; border-bottom: 1px dashed #e0d8c8; }
        ref { color: #808080; }
        #card-container * { max-width: 100% !important; }
        div.stat-block {
            margin: 20px auto;
            width: 537px;
            background-color: #fdf1dc;
            padding: 18px 20px;
            border: 1px solid #c9ad6a;
            border-top: 5px solid #7a200d;
            border-bottom: 5px solid #7a200d;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            font-size: 13.5px;
            box-sizing: border-box;
        }
        div.stat-block h5, div.stat-block h6 { color: #7a200d; font-weight: bold; border-bottom: 2px solid #7a200d; padding-bottom: 3px; }
        div.stat-block h5 { font-size: 150%; margin-top: 0px; margin-bottom: 4px; }
        div.stat-block h6 { font-size: 115%; margin-top: 15px; margin-bottom: 8px; }
        div.stat-block .sub-line { color: #6b6b6b; font-style: italic; margin-top: -2px; margin-bottom: 10px; }
        div.stat-block table { width: 100%; color: #7a200d; border-collapse: collapse; margin-bottom: 12px; }
        div.stat-block table td { padding: 3px 0; line-height: 1.4; }
        div.stat-block table strong { color: #7a200d; }
        table.stat-abilities {
            text-align: center;
            margin: 15px 0;
            white-space: nowrap;
            table-layout: fixed;
            border-collapse: collapse !important;
            border-spacing: 0 !important;
            width: 100% !important;
        }
        table.stat-abilities th, table.stat-abilities td { border: none !important; padding: 5px 0 !important; line-height: 1.2; }
        table.stat-abilities th { font-size: 11px; color: #8a7a66; font-weight: bold;}
        table.stat-abilities th:nth-child(1), table.stat-abilities td:nth-child(1),
        table.stat-abilities th:nth-child(2), table.stat-abilities td:nth-child(2),
        table.stat-abilities th:nth-child(6), table.stat-abilities td:nth-child(6),
        table.stat-abilities th:nth-child(7), table.stat-abilities td:nth-child(7),
        table.stat-abilities th:nth-child(11), table.stat-abilities td:nth-child(11),
        table.stat-abilities th:nth-child(12), table.stat-abilities td:nth-child(12) { width: 8%; }
        table.stat-abilities th:nth-child(3), table.stat-abilities td:nth-child(3),
        table.stat-abilities th:nth-child(4), table.stat-abilities td:nth-child(4),
        table.stat-abilities th:nth-child(8), table.stat-abilities td:nth-child(8),
        table.stat-abilities th:nth-child(9), table.stat-abilities td:nth-child(9),
        table.stat-abilities th:nth-child(13), table.stat-abilities td:nth-child(13),
        table.stat-abilities th:nth-child(14), table.stat-abilities td:nth-child(14) { width: 7%; }
        table.stat-abilities th:nth-child(5), table.stat-abilities td:nth-child(5),
        table.stat-abilities th:nth-child(10), table.stat-abilities td:nth-child(10) { width: 5%; }
        td.c1 { background-color: #ebdcb9 !important; color: #5c180a !important; }
        td.c2 { background-color: #d9caa5 !important; color: #5c180a !important; }
        td.c3 { background-color: #e6d7b5 !important; color: #2e4436 !important; }
        td.c4 { background-color: #d1c39f !important; color: #2e4436 !important; }
        div.stat-block p { margin: 6px 0; font-size: 13px; color: #2b2b2b; }
        div.stat-block p strong { color: #000; }
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

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(args=['--no-sandbox'])
                page = await browser.new_page()
                await page.set_content(full_html)

                locator = page.locator("#card-container")
                await locator.screenshot(path=output_filename)

                await browser.close()
        except PlaywrightError as exc:
            raise RuntimeError(
                "Playwright Chromium 未安装或缺少系统依赖；Docker 用户请执行 "
                "`python -m playwright install --with-deps chromium` 后重启 AstrBot。"
            ) from exc

    @filter.command("find")
    async def query_spell(self, event: AstrMessageEvent, spell_name: str = "", version_tag: str = ""):
        if not self._command_enabled(event):
            return
        if not spell_name:
            # 纯文本直接用 plain_result 传字符串
            yield event.plain_result(get_output("spell.usage"))
            return

        # 提示正在搜索（传入纯字符串）
        new_version = True
        if version_tag == "旧版" or version_tag == "5e" or version_tag == "2014":
            new_version = False
        lookup_query = spell_name
        if version_tag and spell_name.lower() in {"coc", "克苏鲁", "神话", "仪式"}:
            lookup_query = f"{spell_name} {version_tag}"
        yield event.plain_result(get_output("spell.searching", spell_name=lookup_query))
        
        try:
            res = self.search_spell_in_folder(spell_name, new_version)
        except Exception as e:
            yield event.plain_result(get_output("spell.parse_error", error=str(e)))
            return

        if not res:
            coc_result = query_coc_spell(lookup_query)
            if coc_result:
                yield event.plain_result(coc_result)
                return
            yield event.plain_result(get_output("spell.not_found", spell_name=lookup_query))
            return

        html_content = self.spellfeature_to_html(res)
        text = self.spellfeature_to_text(res)
        safe_spell_name = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", spell_name).strip("._") or "spell"
        temp_image_path = os.path.join(self.plugin_dir, f"temp_{safe_spell_name}_{int(time.time() * 1000)}.png")

        try:
            await self.render_html_to_image(html_content, temp_image_path)
            yield event.chain_result([Image.fromFileSystem(temp_image_path)])
        except Exception as e:
            yield event.plain_result(f"{get_output('spell.render_error', error=str(e))}\n\n{text}")
        finally:
            if os.path.exists(temp_image_path):
                try:
                    os.remove(temp_image_path)
                except OSError:
                    pass
