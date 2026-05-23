import yaml
import os

COMMON_DIR = os.path.dirname(__file__)
COMPONENT_DIR = os.path.dirname(COMMON_DIR)
PLUGIN_DIR = os.path.dirname(COMPONENT_DIR)

CONFIG_CANDIDATES = [
    os.path.join(COMPONENT_DIR, "config.yaml"),
    os.path.join(COMPONENT_DIR, "config.default.yaml"),
    os.path.join(COMMON_DIR, "config.yaml"),
    os.path.join(COMMON_DIR, "config.default.yaml"),
    os.path.join(PLUGIN_DIR, "config.yaml"),
    os.path.join(PLUGIN_DIR, "config.default.yaml"),
]

CONFIG_PATH = next((path for path in CONFIG_CANDIDATES if os.path.exists(path)), CONFIG_CANDIDATES[0])

DEFAULT_OUTPUTS = {
    "log.no_active_session": "当前没有正在进行的日志记录。",
}

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

_config = load_config()

def get_output(key: str, **kwargs):
    """
    支持多层 key，通过点分隔，如 "skill_check.normal"
    根据 key 获取输出模板，并用 kwargs 格式化。
    如果 key 不存在则使用内置兜底或抛出错误。
    """
    keys = key.split(".")
    template = _config.get("output", {})
    for k in keys:
        if not isinstance(template, dict):
            template = {}
            break
        template = template.get(k, {})
    if not isinstance(template, str):
        template = DEFAULT_OUTPUTS.get(key)
    if not isinstance(template, str):
        raise ValueError(f"{key} cannot be found in {CONFIG_PATH}")
    try:
        return template.format(**kwargs)
    except Exception:
        return template
