"""Explicit, repeatable migration of group cards and vaults to rule directories."""

import argparse
import json
import os
from pathlib import Path
import tempfile


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_atomic(path, data, stat=None):
    new_parent = not path.parent.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    if new_parent and os.geteuid() == 0:
        parent_stat = path.parent.parent.stat()
        os.chown(path.parent, parent_stat.st_uid, parent_stat.st_gid)
        os.chmod(path.parent, parent_stat.st_mode & 0o777)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".migration-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=4)
            stream.flush()
            os.fsync(stream.fileno())
        if stat:
            os.chmod(temporary, stat.st_mode)
            if os.geteuid() == 0:
                os.chown(temporary, stat.st_uid, stat.st_gid)
            os.utime(temporary, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def migrate(data_folder, apply=False):
    root = Path(data_folder)
    cards = []
    bindings = []
    archived = []
    for group in sorted(root.iterdir()):
        if not group.is_dir() or group.name == "user_metadata":
            continue
        archived.extend(group.glob("*.json"))
        for user in sorted(group.iterdir()):
            if user.is_dir():
                cards.extend(user.glob("*.json"))
    metadata = root / "user_metadata"
    if metadata.exists():
        for user in sorted(metadata.iterdir()):
            if user.is_dir():
                cards.extend((user / "vault").glob("*.json"))
                if (user / "bindings.json").exists():
                    bindings.append(user / "bindings.json")

    # Preflight every input and destination before changing any file.
    moves = []
    card_rules = {}
    scoped_paths = list(root.glob("*/*/coc/*.json")) + list(root.glob("*/*/dnd/*.json"))
    scoped_paths += list(metadata.glob("*/vault/coc/*.json"))
    scoped_paths += list(metadata.glob("*/vault/dnd/*.json"))
    for path in scoped_paths:
        user_id = path.parent.parent.parent.name if "vault" == path.parent.parent.name else path.parent.parent.name
        card_rules.setdefault((user_id, path.stem), set()).add(path.parent.name)
    for source in sorted(cards):
        data = _read(source)
        if not isinstance(data, dict) or not all(key in data for key in ("id", "name", "attributes")):
            raise ValueError(f"Invalid character file: {source}")
        rule = data.get("rule_system", "coc")
        if rule not in {"coc", "dnd"}:
            raise ValueError(f"Unknown character rule system: {source}")
        destination = source.parent / rule / source.name
        data["rule_system"] = rule
        user_id = source.parent.parent.name if source.parent.name == "vault" else source.parent.name
        card_rules.setdefault((user_id, source.stem), set()).add(rule)
        if destination.exists() and _read(destination) != data:
            raise FileExistsError(f"Migration destination differs: {destination}")
        moves.append((source, destination, data, source.stat()))

    updates = []
    for path in bindings:
        raw = _read(path)
        if not isinstance(raw, dict):
            raise ValueError(f"Invalid bindings file: {path}")
        updated = {}
        for group_id, binding in raw.items():
            if isinstance(binding, dict) and any(key in binding for key in ("coc", "dnd")):
                updated[group_id] = binding
            else:
                card_id = binding.get("id") if isinstance(binding, dict) else binding
                rules = card_rules.get((path.parent.name, card_id), {"coc"})
                if len(rules) != 1:
                    raise ValueError(f"Ambiguous legacy binding: {path}, group {group_id}")
                updated[group_id] = {next(iter(rules)): binding}
        if updated != raw:
            updates.append((path, updated, path.stat()))

    if apply:
        for source, destination, data, stat in moves:
            if not destination.exists():
                _write_atomic(destination, data, stat)
            if _read(destination) != data:
                raise ValueError(f"Migration verification failed: {destination}")
            source.unlink()
        for path, data, stat in updates:
            _write_atomic(path, data, stat)

    return {"cards": len(moves), "bindings": len(updates),
            "older_user_cards_preserved": len(archived), "applied": apply}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_folder", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(migrate(args.data_folder, args.apply), indent=2))
