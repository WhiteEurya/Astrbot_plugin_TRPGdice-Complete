# app/config.py
import os
import yaml

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "backend", "config.yaml")
DEFAULT_CONFIG_PATH = os.path.join(BASE_DIR, "backend", "config.default.yaml")
ACTIVE_CONFIG_PATH = CONFIG_PATH if os.path.exists(CONFIG_PATH) else DEFAULT_CONFIG_PATH

with open(ACTIVE_CONFIG_PATH, "r", encoding="utf-8") as f:
    _cfg = yaml.safe_load(f)

export_root = _cfg.get("export_root", "")
if export_root and not os.path.isabs(export_root):
    export_root = os.path.join(BASE_DIR, export_root)
EXPORT_ROOT = os.path.abspath(export_root)
if not EXPORT_ROOT:
    raise RuntimeError(f"export_root 未配置，请检查 {ACTIVE_CONFIG_PATH}")
