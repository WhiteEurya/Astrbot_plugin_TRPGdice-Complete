# app/config.py
import os
import yaml

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "backend", "config.yaml")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    _cfg = yaml.safe_load(f)

EXPORT_ROOT = os.path.abspath(_cfg.get("export_root", ""))
if not EXPORT_ROOT:
    raise RuntimeError(f"export_root 未配置，请检查 {CONFIG_PATH}")
