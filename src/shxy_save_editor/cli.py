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

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
