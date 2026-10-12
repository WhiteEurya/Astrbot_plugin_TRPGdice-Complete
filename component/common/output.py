import logging
import os
try:
    import yaml
except ImportError:
    yaml = None

COMMON_DIR = os.path.dirname(__file__)
COMPONENT_DIR = os.path.dirname(COMMON_DIR)
PLUGIN_DIR = os.path.dirname(COMPONENT_DIR)
logger = logging.getLogger(__name__)

CONFIG_CANDIDATES = [
    os.path.join(COMPONENT_DIR, "config.yaml"),
    os.path.join(COMPONENT_DIR, "config.default.yaml"),
    os.path.join(COMMON_DIR, "config.yaml"),
    os.path.join(COMMON_DIR, "config.default.yaml"),
    os.path.join(PLUGIN_DIR, "config.yaml"),
    os.path.join(PLUGIN_DIR, "config.default.yaml"),
]

DEFAULT_CONFIG_PATH = os.path.join(COMPONENT_DIR, "config.default.yaml")
USER_CONFIG_PATH = os.path.join(COMPONENT_DIR, "config.yaml")
CONFIG_PATH = USER_CONFIG_PATH if os.path.exists(USER_CONFIG_PATH) else DEFAULT_CONFIG_PATH

DEFAULT_OUTPUTS = {
    "log.no_active_session": "当前没有正在进行的日志记录。",
    "log.message_added": "log.message_added",
    "log.new_session": "log.new_session",
    "log.ob.header": "log.ob.header",
    "log.ob.toggle_on": "log.ob.toggle_on",
    "log.session_exported": "{result_website}",
    "setting.website": "",
    "coc_rule.rule_1": "严格规则",
    "coc_rule.rule_2": "COC7版规则",
    "coc_rule.rule_3": "阶段性规则",
    "coc_rule.rule_4": "宽松规则",
    "skill_check.difficulty.hard": "困难",
    "skill_check.difficulty.extreme": "极难",
    "skill_check.until_success.success": "{name} 的【{skill_name}】连续检定直到成功：\n第 {attempts} 次成功。\n前10次结果：\n{results}",
    "skill_check.until_success.failure": "{name} 的【{skill_name}】连续检定直到成功：\n已达到 {max_attempts} 次上限，仍未成功。\n前10次结果：\n{results}",
    "dice.expression.zero_division": "dice.expression.zero_division",
    "choice.not_enough": "choice.not_enough",
    "choice.result": "choice.result",
    "common.none": "无",
    "common.unknown": "未知",
    "common.yes": "是",
    "common.no": "否",
    "spell.sealdice_dnd_source": "资料源：SeaDice sealdice-builtins DND 查询资料；D&D 系列资料整理者主要为 DicePP 项目组成员。",
    "spell.sealdice_coc_source": "资料源：SeaDice sealdice-builtins CoC 魔法大典；整理者：魔骨、NULL、Dr.Amber。",
    "spell.coc_result": "【COC法术】{name}\n{content}\n{source}",
    "coc_roll.results.great_success": "大成功",
    "coc_roll.results.extreme_success": "极难成功",
    "coc_roll.results.hard_success": "困难成功",
    "coc_roll.results.success": "成功",
    "coc_roll.results.failure": "失败",
    "coc_roll.results.great_failure": "大失败",
    "versus.no_winner": "双方均失败，无胜者",
    "versus.tie": "平局",
    "versus.result": "来，让我听听这一次风会偏向哪一边。\n对抗检定结果：\n{left_name}：{left_roll}/{left_value} —— {left_result}\n{right_name}：{right_roll}/{right_value} —— {right_result}\n嗯……我听清楚了，这次是：{winner}",
}

def _load_yaml(path):
    if not os.path.exists(path):
        return {}
    if yaml is None:
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _deep_merge(base, override):
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config():
    config = _load_yaml(DEFAULT_CONFIG_PATH)
    user_config = _load_yaml(USER_CONFIG_PATH)
    if user_config:
        config = _deep_merge(config, user_config)
    if config:
        return config
    for path in CONFIG_CANDIDATES:
        loaded = _load_yaml(path)
        if loaded:
            return loaded
    return {}

_config = load_config()
_ui_output = {}
_ui_dnd_output = {}


def configure_dnd_output(settings=None):
    """Apply AstrBot UI overrides without modifying the YAML configuration."""
    global _ui_dnd_output
    _ui_dnd_output = settings if isinstance(settings, dict) else {}


def configure_output(settings=None, legacy_dnd=None):
    """Configure all UI templates, retaining the earlier DnD settings."""
    global _ui_output
    _ui_output = settings if isinstance(settings, dict) else {}
    configure_dnd_output(legacy_dnd)


def _find_template(settings, keys):
    for key in keys:
        if not isinstance(settings, dict):
            return None
        settings = settings.get(key)
    return settings if isinstance(settings, str) else None

def get_output(key: str, **kwargs):
    """
    支持多层 key，通过点分隔，如 "skill_check.normal"
    根据 key 获取输出模板，并用 kwargs 格式化。
    如果 key 不存在则使用内置兜底或抛出错误。
    """
    keys = key.split(".")
    template = _find_template(_ui_output, keys)
    if not template and keys[0] == "dnd":
        template = _find_template(_ui_dnd_output, keys[1:])
    if not template:
        template = _find_template(_config.get("output", {}), keys)
    if not isinstance(template, str):
        template = DEFAULT_OUTPUTS.get(key)
    if not isinstance(template, str):
        raise ValueError(f"{key} cannot be found in {CONFIG_PATH}")
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError, TypeError, AttributeError) as exc:
        logger.warning("Output template %s could not be formatted: %s", key, exc)
        return template
