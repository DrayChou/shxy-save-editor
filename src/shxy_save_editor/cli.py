from __future__ import annotations

import argparse
import json
from pathlib import Path

from .locator import discover_save_locations
from .rmmzsave import backup_save, export_json, get_path, import_json, read_save, set_path, write_save


def parse_value(text: str):
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text


def diff_dict(d1: dict, d2: dict, prefix: str = "") -> list[tuple[str, object, object]]:
    changes: list[tuple[str, object, object]] = []
    keys = set(d1.keys()) | set(d2.keys())
    for key in sorted(keys):
        v1 = d1.get(key)
        v2 = d2.get(key)
        path = f"{prefix}.{key}" if prefix else str(key)
        if type(v1) is not type(v2):
            changes.append((path, v1, v2))
        elif isinstance(v1, dict):
            changes.extend(diff_dict(v1, v2, path))
        elif isinstance(v1, list) and isinstance(v2, list):
            changes.extend(diff_list(v1, v2, path))
        elif v1 != v2:
            changes.append((path, v1, v2))
    return changes


def diff_list(l1: list, l2: list, prefix: str = "") -> list[tuple[str, object, object]]:
    changes: list[tuple[str, object, object]] = []
    max_len = max(len(l1), len(l2))
    for index in range(max_len):
        v1 = l1[index] if index < len(l1) else "<MISSING>"
        v2 = l2[index] if index < len(l2) else "<MISSING>"
        path = f"{prefix}[{index}]"
        if isinstance(v1, dict) and isinstance(v2, dict):
            changes.extend(diff_dict(v1, v2, path))
        elif isinstance(v1, list) and isinstance(v2, list):
            changes.extend(diff_list(v1, v2, path))
        elif v1 != v2:
            changes.append((path, v1, v2))
    return changes


def find_value_paths(data: object, targets: set[object], prefix: str = "") -> list[tuple[str, object]]:
    matches: list[tuple[str, object]] = []
    if isinstance(data, dict):
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            matches.extend(find_value_paths(value, targets, path))
    elif isinstance(data, list):
        for index, value in enumerate(data):
            path = f"{prefix}[{index}]"
            matches.extend(find_value_paths(value, targets, path))
    elif data in targets:
        matches.append((prefix, data))
    return matches


def format_value_matches(matches: list[tuple[str, object]], limit: int) -> list[str]:
    lines: list[str] = []
    by_value: dict[object, list[str]] = {}
    for path, value in matches:
        by_value.setdefault(value, []).append(path)
    for value in sorted(by_value, key=lambda item: str(item)):
        paths = by_value[value]
        lines.append(f"值 {value!r}: 命中 {len(paths)} 处")
        for path in paths[:limit]:
            lines.append(f"  {path}")
        if len(paths) > limit:
            lines.append(f"  ... 还有 {len(paths) - limit} 处，使用 --limit 调大")
        lines.append("")
    return lines


def find_changed_paths(data1: object, data2: object, old_value: object, new_value: object, prefix: str = "") -> list[str]:
    matches: list[str] = []
    if isinstance(data1, dict) and isinstance(data2, dict):
        keys = set(data1.keys()) | set(data2.keys())
        for key in sorted(keys, key=str):
            path = f"{prefix}.{key}" if prefix else str(key)
            matches.extend(find_changed_paths(data1.get(key), data2.get(key), old_value, new_value, path))
    elif isinstance(data1, list) and isinstance(data2, list):
        max_len = max(len(data1), len(data2))
        for index in range(max_len):
            value1 = data1[index] if index < len(data1) else "<MISSING>"
            value2 = data2[index] if index < len(data2) else "<MISSING>"
            path = f"{prefix}[{index}]"
            matches.extend(find_changed_paths(value1, value2, old_value, new_value, path))
    elif data1 == old_value and data2 == new_value:
        matches.append(prefix)
    return matches


def find_changed_to_paths(data1: object, data2: object, new_value: object, prefix: str = "") -> list[tuple[str, object, object]]:
    matches: list[tuple[str, object, object]] = []
    if isinstance(data1, dict) and isinstance(data2, dict):
        keys = set(data1.keys()) | set(data2.keys())
        for key in sorted(keys, key=str):
            path = f"{prefix}.{key}" if prefix else str(key)
            matches.extend(find_changed_to_paths(data1.get(key), data2.get(key), new_value, path))
    elif isinstance(data1, list) and isinstance(data2, list):
        max_len = max(len(data1), len(data2))
        for index in range(max_len):
            value1 = data1[index] if index < len(data1) else "<MISSING>"
            value2 = data2[index] if index < len(data2) else "<MISSING>"
            path = f"{prefix}[{index}]"
            matches.extend(find_changed_to_paths(value1, value2, new_value, path))
    elif data1 != data2 and data2 == new_value:
        matches.append((prefix, data1, data2))
    return matches


PARAM_LABELS = ["生命", "内力", "攻击", "防御", "内功", "内防", "轻功", "悟性"]
XPARAM_LABELS = ["命中", "闪避", "暴击"]


def resolve_data_dir(save_file: str, data_dir: str | None) -> Path:
    if data_dir:
        path = Path(data_dir)
    else:
        save_path = Path(save_file).resolve()
        path = save_path.parent.parent / "data" if save_path.parent.name.lower() == "save" else save_path.parent / "data"
    if not path.exists():
        raise FileNotFoundError(f"未找到游戏 data 目录：{path}，请使用 --data-dir 指定")
    return path


def read_database(data_dir: Path, file_name: str) -> list:
    path = data_dir / file_name
    if not path.exists():
        raise FileNotFoundError(f"缺少数据库文件：{path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def safe_db_get(db: list, item_id: int) -> dict:
    if item_id <= 0 or item_id >= len(db) or not isinstance(db[item_id], dict):
        return {}
    return db[item_id]


def collect_actor_trait_sources(actor: dict, actor_id: int, databases: dict[str, list]) -> list[tuple[str, list]]:
    sources: list[tuple[str, list]] = []
    actor_db = safe_db_get(databases["actors"], actor_id)
    if actor_db.get("traits"):
        sources.append((f"角色数据库 #{actor_id} {actor_db.get('name', '')}", actor_db.get("traits", [])))

    class_id = int(actor.get("_classId", actor_db.get("classId", 0)) or 0)
    class_db = safe_db_get(databases["classes"], class_id)
    if class_db.get("traits"):
        sources.append((f"职业 #{class_id} {class_db.get('name', '')}", class_db.get("traits", [])))

    for equip in actor.get("_equips", []) or []:
        if not isinstance(equip, dict):
            continue
        item_id = int(equip.get("_itemId", 0) or 0)
        data_class = equip.get("_dataClass")
        if data_class == "weapon":
            item = safe_db_get(databases["weapons"], item_id)
            if item.get("traits"):
                sources.append((f"武器 #{item_id} {item.get('name', '')}", item.get("traits", [])))
        elif data_class == "armor":
            item = safe_db_get(databases["armors"], item_id)
            if item.get("traits"):
                sources.append((f"护甲 #{item_id} {item.get('name', '')}", item.get("traits", [])))

    for state_id in actor.get("_states", []) or []:
        item = safe_db_get(databases["states"], int(state_id or 0))
        if item.get("traits"):
            sources.append((f"状态 #{state_id} {item.get('name', '')}", item.get("traits", [])))

    if actor.get("_customTraits"):
        sources.append(("存档自定义 traits", actor.get("_customTraits", [])))
    if actor.get("_itemEffectTraits"):
        sources.append(("存档道具效果 traits", actor.get("_itemEffectTraits", [])))
    return sources


def explain_actor_stats(save_file: str, actor_id: int, data_dir_text: str | None = None) -> list[str]:
    data_dir = resolve_data_dir(save_file, data_dir_text)
    save = read_save(save_file)
    actor = get_path(save, f"actors._data.{actor_id}")
    if not isinstance(actor, dict):
        raise ValueError(f"存档中不存在 actor_id={actor_id}")

    databases = {
        "actors": read_database(data_dir, "Actors.json"),
        "classes": read_database(data_dir, "Classes.json"),
        "weapons": read_database(data_dir, "Weapons.json"),
        "armors": read_database(data_dir, "Armors.json"),
        "states": read_database(data_dir, "States.json"),
    }

    actor_db = safe_db_get(databases["actors"], actor_id)
    class_id = int(actor.get("_classId", actor_db.get("classId", 0)) or 0)
    class_db = safe_db_get(databases["classes"], class_id)
    level = int(actor.get("_level", 1) or 1)
    param_plus = list(actor.get("_paramPlus", [0] * 8))
    param_plus.extend([0] * (8 - len(param_plus)))

    equip_params = [0] * 8
    equip_lines: list[str] = []
    for equip in actor.get("_equips", []) or []:
        if not isinstance(equip, dict):
            continue
        item_id = int(equip.get("_itemId", 0) or 0)
        data_class = equip.get("_dataClass")
        db_key = "weapons" if data_class == "weapon" else "armors" if data_class == "armor" else ""
        if not db_key or item_id <= 0:
            continue
        item = safe_db_get(databases[db_key], item_id)
        params = item.get("params", [0] * 8)
        for index in range(min(8, len(params))):
            equip_params[index] += int(params[index] or 0)
        equip_lines.append(f"  - {data_class} #{item_id} {item.get('name', '')}: {params}")

    trait_sources = collect_actor_trait_sources(actor, actor_id, databases)
    param_rate_sources: list[list[tuple[str, float]]] = [[] for _ in range(8)]
    xparam_sources: list[list[tuple[str, float]]] = [[] for _ in range(3)]
    for source_name, traits in trait_sources:
        for trait in traits or []:
            code = int(trait.get("code", 0) or 0)
            data_id = int(trait.get("dataId", 0) or 0)
            value = float(trait.get("value", 0) or 0)
            if code == 21 and 0 <= data_id < 8:
                param_rate_sources[data_id].append((source_name, value))
            elif code == 22 and 0 <= data_id < 3:
                xparam_sources[data_id].append((source_name, value))

    lines = [
        f"存档: {save_file}",
        f"数据目录: {data_dir}",
        f"角色: actor_id={actor_id} {actor.get('_name', actor_db.get('name', ''))}  Lv.{level}",
        f"职业: class_id={class_id} {class_db.get('name', '')}",
        "",
        "[装备]",
        *(equip_lines or ["  无装备加成"]),
        "",
        "[八维计算]",
    ]

    class_params = class_db.get("params", [])
    for index, label in enumerate(PARAM_LABELS):
        base = 0
        if index < len(class_params) and isinstance(class_params[index], list) and level < len(class_params[index]):
            base = int(class_params[index][level] or 0)
        raw = base + int(param_plus[index] or 0) + equip_params[index]
        rate = 1.0
        for _source, value in param_rate_sources[index]:
            rate *= value
        final = round(raw * rate)
        source_text = "；".join(f"{name} ×{value:g}" for name, value in param_rate_sources[index]) or "无倍率 trait"
        lines.append(f"  {label}: 职业{base} + paramPlus{param_plus[index]} + 装备{equip_params[index]} = {raw}; 倍率 {rate:g}; 最终≈{final}")
        lines.append(f"    来源: {source_text}")

    lines.extend(["", "[命中/闪避/暴击]"])
    for index, label in enumerate(XPARAM_LABELS):
        total = sum(value for _source, value in xparam_sources[index])
        source_text = "；".join(f"{name} +{value:g}" for name, value in xparam_sources[index]) or "无 code=22 来源"
        lines.append(f"  {label}: {total:.2%}  ({source_text})")
    return lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SHXY 存档工具")
    sub = parser.add_subparsers(dest="command", required=True)

    export_p = sub.add_parser("export", help="导出 .rmmzsave 为 JSON")
    export_p.add_argument("save_file")
    export_p.add_argument("json_file", nargs="?")

    import_p = sub.add_parser("import", help="导入 JSON 回存档")
    import_p.add_argument("json_file")
    import_p.add_argument("save_file", nargs="?")

    read_p = sub.add_parser("read", help="读取某个 JSON 路径的值")
    read_p.add_argument("save_file")
    read_p.add_argument("path")

    edit_p = sub.add_parser("edit", help="修改某个 JSON 路径的值")
    edit_p.add_argument("save_file")
    edit_p.add_argument("path")
    edit_p.add_argument("value")

    scan_p = sub.add_parser("scan", help="扫描 Steam 存档目录")
    scan_p.add_argument("--start", default=".")

    batch_p = sub.add_parser("batch-export", help="批量导出目录下所有 .rmmzsave")
    batch_p.add_argument("--dir", default=".")
    batch_p.add_argument("--clean", action="store_true")

    compare_p = sub.add_parser("compare", help="对比两个存档")
    compare_p.add_argument("save1")
    compare_p.add_argument("save2")
    compare_p.add_argument("--path", default=None)

    find_p = sub.add_parser("find-value", help="在存档中按真实数值反查路径")
    find_p.add_argument("save_file")
    find_p.add_argument("values", nargs="+", help="要查找的值，例如 61 100 5")
    find_p.add_argument("--path", default=None, help="只在指定路径下查找，例如 variables._data 或 actors._data.1")
    find_p.add_argument("--limit", type=int, default=80, help="每个值最多显示多少条路径")

    change_p = sub.add_parser("find-change", help="在两个存档中查找指定 old -> new 的变化路径")
    change_p.add_argument("save1")
    change_p.add_argument("save2")
    change_p.add_argument("old_value")
    change_p.add_argument("new_value")
    change_p.add_argument("--path", default=None, help="只在指定路径下查找，例如 variables._data 或 actors._data.1")

    to_p = sub.add_parser("find-to", help="在两个存档中查找变化后等于指定值的路径")
    to_p.add_argument("save1")
    to_p.add_argument("save2")
    to_p.add_argument("new_value")
    to_p.add_argument("--path", default=None, help="只在指定路径下查找，例如 variables._data 或 actors._data.1")

    explain_p = sub.add_parser("explain-actor-stats", help="结合游戏 data 目录解释角色属性来源")
    explain_p.add_argument("save_file")
    explain_p.add_argument("--actor-id", type=int, default=1)
    explain_p.add_argument("--data-dir", default=None, help="游戏 data 目录；不填时尝试从存档路径旁边推断")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "export":
        result = export_json(args.save_file, args.json_file)
        print(result)
        return 0

    if args.command == "import":
        result = import_json(args.json_file, args.save_file)
        print(result)
        return 0

    if args.command == "read":
        data = read_save(args.save_file)
        print(json.dumps(get_path(data, args.path), ensure_ascii=False, indent=2))
        return 0

    if args.command == "edit":
        backup = backup_save(args.save_file)
        data = read_save(args.save_file)
        value = parse_value(args.value)
        set_path(data, args.path, value)
        write_save(args.save_file, data)
        print(f"backup: {backup}")
        print(f"{args.path} = {json.dumps(value, ensure_ascii=False)}")
        return 0

    if args.command == "scan":
        start = Path(args.start).resolve()
        locations = discover_save_locations(start)
        for location in locations:
            print(f"{location.save_dir}\t[{location.source}]")
        return 0

    if args.command == "batch-export":
        target_dir = Path(args.dir)
        files = sorted(target_dir.glob("*.rmmzsave"))
        if not files:
            print("未找到任何 .rmmzsave 文件")
            return 0
        for save_path in files:
            json_path = Path(f"{save_path}.json")
            if args.clean and json_path.exists():
                json_path.unlink()
                print(f"[清理] {json_path.name}")
            export_json(save_path, json_path)
            print(f"[导出] {save_path.name} -> {json_path.name}")
        print(f"完成，共导出 {len(files)} 个存档")
        return 0

    if args.command == "compare":
        d1 = read_save(args.save1)
        d2 = read_save(args.save2)
        path = args.path
        if path:
            d1 = get_path(d1, path)
            d2 = get_path(d2, path)
            print(f"对比路径: {path}")
        if isinstance(d1, dict) and isinstance(d2, dict):
            changes = diff_dict(d1, d2, path or "")
        elif isinstance(d1, list) and isinstance(d2, list):
            changes = diff_list(d1, d2, path or "")
        else:
            changes = [(path or "<root>", d1, d2)] if d1 != d2 else []
        if not changes:
            print("没有差异")
            return 0
        print(f"发现 {len(changes)} 处差异:")
        print("-" * 60)
        for item_path, v1, v2 in changes:
            print(item_path)
            print(f"  {args.save1}: {v1}")
            print(f"  {args.save2}: {v2}")
        return 0

    if args.command == "find-value":
        data = read_save(args.save_file)
        root = get_path(data, args.path) if args.path else data
        prefix = args.path or ""
        targets = {parse_value(item) for item in args.values}
        matches = find_value_paths(root, targets, prefix)
        if not matches:
            print("没有找到匹配值")
            return 0
        for line in format_value_matches(matches, args.limit):
            print(line)
        return 0

    if args.command == "find-change":
        data1 = read_save(args.save1)
        data2 = read_save(args.save2)
        root1 = get_path(data1, args.path) if args.path else data1
        root2 = get_path(data2, args.path) if args.path else data2
        prefix = args.path or ""
        old_value = parse_value(args.old_value)
        new_value = parse_value(args.new_value)
        matches = find_changed_paths(root1, root2, old_value, new_value, prefix)
        if not matches:
            print(f"没有找到 {old_value!r} -> {new_value!r} 的变化路径")
            return 0
        print(f"找到 {len(matches)} 处 {old_value!r} -> {new_value!r}:")
        for path in matches:
            print(path)
        return 0

    if args.command == "find-to":
        data1 = read_save(args.save1)
        data2 = read_save(args.save2)
        root1 = get_path(data1, args.path) if args.path else data1
        root2 = get_path(data2, args.path) if args.path else data2
        prefix = args.path or ""
        new_value = parse_value(args.new_value)
        matches = find_changed_to_paths(root1, root2, new_value, prefix)
        if not matches:
            print(f"没有找到变化后等于 {new_value!r} 的路径")
            return 0
        print(f"找到 {len(matches)} 处变化后等于 {new_value!r}:")
        for path, old, new in matches:
            print(f"{path}: {old!r} -> {new!r}")
        return 0

    if args.command == "explain-actor-stats":
        for line in explain_actor_stats(args.save_file, args.actor_id, args.data_dir):
            print(line)
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
