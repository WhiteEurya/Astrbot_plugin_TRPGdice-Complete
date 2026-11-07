"""Preserve legacy dice data before replacing an AstrBot plugin directory."""

import argparse
import filecmp
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory


PLAYER_DATA_DIR = "player_data"


def _legacy_sources(plugin_dir: Path) -> dict[str, Path]:
    sources = {
        "chara_data": plugin_dir / "chara_data",
        "settings": plugin_dir / "data" / "settings",
    }
    for source in sources.values():
        if (source.exists() or source.is_symlink()) and not source.is_dir():
            raise NotADirectoryError(source)
    return {name: source for name, source in sources.items() if source.is_dir()}


def _contains_snapshot(sources: dict[str, Path], target: Path) -> bool:
    for name, source in sources.items():
        root = target / name
        if not root.is_dir():
            return False
        for original in source.rglob("*"):
            copied = root / original.relative_to(source)
            if original.is_dir():
                if not copied.is_dir():
                    return False
            elif not copied.is_file() or not filecmp.cmp(original, copied, shallow=False):
                return False
    return True


def migrate_player_data(plugin_dir: Path, target: Path) -> bool:
    """Publish the first complete legacy snapshot, leaving both stores intact."""
    if target.is_dir():
        return False
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    sources = _legacy_sources(plugin_dir)
    if not sources:
        return False

    target.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=target.parent, prefix=".trpgdice-migrate-") as temp:
        staged = Path(temp) / PLAYER_DATA_DIR
        staged.mkdir()
        for name, source in sources.items():
            shutil.copytree(source, staged / name)
        if not _contains_snapshot(sources, staged):
            raise RuntimeError("复制校验失败，请停用骰子插件后重试。")
        try:
            staged.rename(target)
        except OSError:
            if target.is_dir():
                return False
            raise
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin_dir", type=Path, help="旧插件实际目录，例如 data/plugins/插件目录名")
    args = parser.parse_args()
    plugin_dir = Path(os.path.abspath(args.plugin_dir))
    if not plugin_dir.is_dir() or plugin_dir.parent.name != "plugins":
        parser.error("请指定 AstrBot 的 data/plugins 下实际存在的旧插件目录。")
    target = plugin_dir.parent.parent / "plugin_data" / plugin_dir.name / PLAYER_DATA_DIR
    try:
        if migrate_player_data(plugin_dir, target):
            print(f"已复制并校验人物卡和群设置：{target}")
        elif not target.is_dir():
            parser.error("未找到旧人物卡、群设置或已迁移的数据。请核对插件目录。")
        elif _contains_snapshot(_legacy_sources(plugin_dir), target):
            print(f"持久目录已包含旧数据：{target}")
        else:
            parser.error(f"持久目录与旧数据有差异，已保留两份数据。请在更新前另行备份旧目录：{target}")
    except (OSError, RuntimeError) as exc:
        parser.error(f"无法迁移数据：{exc}")


if __name__ == "__main__":
    main()
