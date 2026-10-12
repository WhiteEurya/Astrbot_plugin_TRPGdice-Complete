"""Configuration API for the embedded AstrBot plugin page."""

import asyncio
import copy
import hashlib
import json
from pathlib import Path
from string import Formatter

from . import output


class ConfigConflict(ValueError):
    pass


class PluginConfigPage:
    def __init__(self, config, root):
        self.config = config
        self.root = Path(root)
        self.schema = json.loads((self.root / "_conf_schema.json").read_text(encoding="utf-8"))
        self.lock = asyncio.Lock()

    def revision(self):
        content = json.dumps({"config": dict(self.config), "yaml": output._config},
                             ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    def snapshot(self):
        fallback = copy.deepcopy(output._config.get("output", {}))
        legacy = self.config.get("dnd_output", {})
        if isinstance(legacy, dict):
            self._apply_nonempty(fallback.setdefault("dnd", {}), legacy)
        return {"config": copy.deepcopy(dict(self.config)), "schema": self.schema,
                "inherited_output": fallback, "revision": self.revision()}

    @classmethod
    def _apply_nonempty(cls, target, overrides):
        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                cls._apply_nonempty(target[key], value)
            elif isinstance(value, str) and value:
                target[key] = value

    def _validate_change(self, change):
        if not isinstance(change, dict):
            raise ValueError("配置变更格式无效。")
        path, value = change.get("path"), change.get("value")
        if not isinstance(path, list) or not path or not all(isinstance(key, str) for key in path):
            raise ValueError("配置路径无效。")
        fields = self.schema
        for index, key in enumerate(path):
            field = fields.get(key)
            if not isinstance(field, dict) or field.get("invisible"):
                raise ValueError("未知或不可编辑的配置项：" + ".".join(path))
            if index < len(path) - 1:
                fields = field.get("items", {})
        kind = field["type"]
        valid = ((kind in {"text", "string"} and isinstance(value, str))
                 or (kind == "bool" and type(value) is bool)
                 or (kind == "int" and type(value) is int))
        if not valid:
            raise ValueError("配置类型不正确：" + ".".join(path))
        if isinstance(value, str) and len(value) > 100000:
            raise ValueError("单项文案过长。")
        if field.get("options") and value not in field["options"]:
            raise ValueError("请选择支持的选项。")
        if path == ["group_post_wait_seconds"] and not 1 <= value <= 86400:
            raise ValueError("挂团等待时间须在 1 到 86400 秒之间。")
        if path[0] == "output" and value:
            try:
                list(Formatter().parse(value))
            except ValueError as exc:
                raise ValueError("文案花括号不匹配：" + ".".join(path)) from exc
        return path, value

    async def save(self, payload):
        if not isinstance(payload, dict) or not isinstance(payload.get("changes"), list):
            raise ValueError("缺少配置变更。")
        if not 1 <= len(payload["changes"]) <= 1000:
            raise ValueError("配置变更数量无效。")
        changes = [self._validate_change(change) for change in payload["changes"]]
        async with self.lock:
            if payload.get("revision") != self.revision():
                raise ConfigConflict("配置已在别处修改，请刷新后重新编辑。")
            if not callable(getattr(self.config, "save_config", None)):
                raise RuntimeError("当前 AstrBot 未提供配置持久化接口。")
            original = copy.deepcopy(dict(self.config))
            updated = copy.deepcopy(original)
            for path, value in changes:
                target = updated
                for key in path[:-1]:
                    if not isinstance(target.get(key), dict):
                        target[key] = {}
                    target = target[key]
                target[path[-1]] = value
            # Preserve a recoverable snapshot before invoking AstrBot's persistence API.
            backup_dir = self.root / "backups" / "webui_config"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup = backup_dir / (self.revision() + ".json")
            if not backup.exists():
                backup.write_text(json.dumps(original, ensure_ascii=False, indent=2), encoding="utf-8")
            try:
                self.config.save_config(updated)
            except Exception:
                self.config.clear()
                self.config.update(original)
                raise
            self.config.update(updated)
            output.configure_output(self.config.get("output"), self.config.get("dnd_output"))
            return self.snapshot()

    def register(self, context):
        from astrbot.api.web import error_response, json_response, request

        async def get_config():
            return json_response(self.snapshot())

        async def save_config():
            try:
                return json_response(await self.save(await request.json()))
            except ConfigConflict as exc:
                return error_response(str(exc), status_code=409)
            except ValueError as exc:
                return error_response(str(exc), status_code=400)
            except Exception:
                return error_response("保存失败，原配置备份已保留。", status_code=500)

        # Older AstrBot versions derive the extension owner from the register decorator.
        for owner in {"astrbot_plugin_TRPGdice_Complete", "astrbot_plugin_TRPG"}:
            context.register_web_api(f"/{owner}/config", get_config, ["GET"], "Read dice plugin configuration")
            context.register_web_api(f"/{owner}/config/save", save_config, ["POST"], "Save dice plugin configuration")
