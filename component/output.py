import yaml
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "default_config.yaml")

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

_config = load_config()

def get_output(key: str, **kwargs):
    """
    支持多层 key，通过点分隔，如 "skill_check.normal"
    根据 key 获取输出模板，并用 kwargs 格式化。
    如果 key 不存在则返回空字符串。
    """
    keys = key.split(".")
    template = _config.get("output", {})
    for k in keys:
        template = template.get(k, {})
    if not isinstance(template, str):
        raise ValueError(f"{key} cannot be found in config.yaml")
    try:
        return template.format(**kwargs)
    except Exception:
        return template
