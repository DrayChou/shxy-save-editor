from __future__ import annotations

import json
import shutil
import zlib
from pathlib import Path
from typing import Any

SAVE_SUFFIX = ".rmmzsave"
JSON_SUFFIX = ".json"
BACKUP_SUFFIX = ".bak"
JsonValue = Any


class SaveError(Exception):
    """Raised when a save file cannot be decoded or written."""



def read_save(file_path: str | Path) -> JsonValue:
    path = Path(file_path)
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            text = handle.read()
        compressed = bytes(ord(char) & 0xFF for char in text)
        raw_json = zlib.decompress(compressed)
        return json.loads(raw_json)
    except Exception as exc:  # pragma: no cover, wrapped error path
        raise SaveError(f"读取存档失败: {path}") from exc



def encode_save_text(data: JsonValue) -> str:
    raw_json = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(raw_json, level=1)
    return "".join(chr(byte) for byte in compressed)



def write_save(file_path: str | Path, data: JsonValue) -> Path:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        text = encode_save_text(data)
        with tmp_path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        tmp_path.replace(path)
        return path
    except Exception as exc:  # pragma: no cover, wrapped error path
        tmp_path.unlink(missing_ok=True)
        raise SaveError(f"写入存档失败: {path}") from exc



def backup_save(file_path: str | Path, suffix: str = BACKUP_SUFFIX) -> Path:
    path = Path(file_path)
    backup_path = path.with_suffix(path.suffix + suffix)
    if not backup_path.exists():
        shutil.copy2(path, backup_path)
    return backup_path



def export_json(save_path: str | Path, json_path: str | Path | None = None) -> Path:
    save_file = Path(save_path)
    target = Path(json_path) if json_path else Path(f"{save_file}{JSON_SUFFIX}")
    data = read_save(save_file)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return target



def import_json(json_path: str | Path, save_path: str | Path | None = None) -> Path:
    source = Path(json_path)
    if save_path is None:
        target = Path(str(source)[:-5] if str(source).endswith(JSON_SUFFIX) else source)
    else:
        target = Path(save_path)
    data = json.loads(source.read_text(encoding="utf-8"))
    return write_save(target, data)



def get_path(data: JsonValue, path_str: str) -> JsonValue:
    current = data
    for part in path_str.split("."):
        if isinstance(current, (list, tuple)):
            current = current[int(part)]
        else:
            current = current[part]
    return current



def set_path(data: JsonValue, path_str: str, value: JsonValue) -> None:
    parts = path_str.split(".")
    current = data
    for part in parts[:-1]:
        if isinstance(current, (list, tuple)):
            current = current[int(part)]
        else:
            current = current[part]
    last = parts[-1]
    if isinstance(current, list):
        current[int(last)] = value
    else:
        current[last] = value
