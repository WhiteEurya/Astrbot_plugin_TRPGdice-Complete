"""Generate AstrBot's grouped output editors from the default YAML templates."""

import argparse
import json
from pathlib import Path
from string import Formatter

import yaml


ROOT = Path(__file__).resolve().parents[1]
CATEGORY_LABELS = {
    "dnd": "DnD 人物卡、检定与资源", "common": "通用词语",
    "skill_check": "CoC 技能检定", "versus": "对抗检定", "alias": "技能别名",
    "bot": "机器人状态与入群", "private": "私聊", "group_post": "挂团回复与填写模板",
    "spell": "法术查询", "coc_rule": "CoC 规则设置", "rp": "骰点池",
    "fireball": "火球术", "coc_roll": "CoC 检定结果名称", "pc": "人物卡管理与同步",
    "st": "属性操作", "nick": "群名片", "dice": "普通掷骰与暗骰",
    "choice": "随机选择", "san": "理智检定与疯狂", "initiative": "先攻与回合",
    "character_list": "人物属性生成", "generated_names": "随机取名回复",
    "log": "日志与旁观者", "help": "帮助页面", "setting": "染色器与其他设置",
}
FIELD_LABELS = {
    "common": "通用", "sheet": "人物卡", "check": "检定", "resource": "资源",
    "class": "职业", "normal": "普通检定", "bonus": "奖励骰", "penalty": "惩罚骰",
    "head": "开头", "header": "标题", "detail": "详情", "roll": "骰点结果",
    "aside": "普通吐槽（天然 1 不显示）", "natural_20": "天然 20 特殊用语",
    "natural_1": "天然 1 特殊用语", "response": "回复正文", "error": "错误提示",
    "updated": "更新完成", "changed": "变更完成", "cleared": "清除完成",
    "restored": "休息恢复", "note": "补充说明", "usage": "用法提示",
    "waiting": "等待填写", "template_coc": "CoC 挂团填写模板",
    "template_dnd": "DnD 挂团填写模板", "created": "创建完成", "deleted": "删除完成",
    "invalid": "无效内容", "not_found": "未找到", "success": "成功",
    "failure": "失败", "great_success": "大成功", "great_failure": "大失败",
    "website": "染色器前端地址", "ob": "旁观者", "text_export": "纯文本导出",
    "grow_up": "技能成长", "until_success": "重复直到成功", "hidden": "暗骰",
    "difficulty": "难度", "pistol_check": "手枪连射", "stat": "统计",
    "index": "总目录", "expr": "骰式说明", "coc": "CoC 与杂项",
}


def make_editor(key, value, path):
    if not isinstance(key, str):
        raise TypeError(f"Output key {key!r} must be a string; quote YAML yes/no keys")
    label = CATEGORY_LABELS.get(key, FIELD_LABELS.get(key, key)) if len(path) == 1 else FIELD_LABELS.get(key, key)
    if isinstance(value, dict):
        return {"type": "object", "description": label,
                "items": {name: make_editor(name, child, (*path, name))
                          for name, child in value.items()}}
    if not isinstance(value, str):
        raise TypeError(f"Output template {'.'.join(path)} must be a string")
    hint = "留空沿用 component/config.yaml；支持直接换行。"
    try:
        fields = sorted({"{" + field + (":" + spec if spec else "") + "}"
                         for _, field, spec, _ in Formatter().parse(value) if field is not None})
    except ValueError:
        fields = []
    if fields:
        hint += "请保留占位符：" + "、".join(fields) + "。"
    if path == ("dnd", "check", "aside"):
        hint += "天然 1 时跳过此项；不要把这句吐槽写进骰点结果。"
    if path == ("initiative", "add"):
        hint += "{value} 是先攻数值，不是第几个行动；列表按先攻从高到低排序。"
    if path == ("group_post", "template_coc") or path == ("group_post", "template_dnd"):
        hint += "使用 丨字段名：内容；可修改提示内容与顺序，请勿删除必需字段或修改字段名。"
    if value:
        hint += "默认模板示例：" + value[:240]
    return {"type": "text", "description": label, "default": "", "hint": hint,
            "editor_mode": True, "editor_language": "plaintext"}


def build_schema(schema, outputs):
    result = dict(schema)
    if "dnd_output" in result:
        result["dnd_output"] = {**result["dnd_output"], "invisible": True,
                                "description": "旧版 DnD 文案（兼容保留）"}
    result["output"] = {
        "type": "object", "description": "回复文案与模板",
        "hint": "按功能分类编辑全部输出。填写后优先使用 UI 内容；留空沿用 YAML。"
                "旧版 DnD UI 文案仍然有效，新界面的非空内容优先。保存后自动重载插件。",
        "obvious_hint": True,
        "items": {key: make_editor(key, value, (key,)) for key, value in outputs.items()},
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check without writing")
    args = parser.parse_args()
    path = ROOT / "_conf_schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    defaults = yaml.safe_load((ROOT / "component/config.default.yaml").read_text(encoding="utf-8"))
    expected = build_schema(schema, defaults["output"])
    if args.check:
        if schema != expected:
            raise SystemExit("Output schema is out of date; run scripts/build_output_schema.py")
        print("Output schema is up to date")
    else:
        path.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("Updated _conf_schema.json")


if __name__ == "__main__":
    main()
