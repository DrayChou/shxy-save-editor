from __future__ import annotations

import re
import string
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

APP_ID = "4106980"
GAME_NAME = "山河小侠"
MANIFEST_NAME = f"appmanifest_{APP_ID}.acf"
GLOBAL_FILE = "global.rmmzsave"
SAVE_GLOB = "file*.rmmzsave"
TIMESTAMP_EPOCH_CUTOFF = 10_000_000_000
WINDOWS_DRIVE_RE = re.compile(r"^(?P<drive>[A-Za-z]):/(?P<rest>.*)$")
ACCOUNT_ID_RE = re.compile(r'"accountid"\s+"(?P<accountid>\d+)"')
INSTALLDIR_RE = re.compile(r'"installdir"\s+"(?P<installdir>[^"]+)"')


@dataclass(slots=True)
class SaveLocation:
    save_dir: Path
    source: str
    manifest_path: Path | None = None



def _unique_paths(paths: Iterable[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path).lower()
        if key not in seen:
            result.append(path)
            seen.add(key)
    return result



def _drive_roots() -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = []
    for letter in string.ascii_uppercase:
        windows_root = Path(f"{letter}:/")
        wsl_root = Path(f"/mnt/{letter.lower()}")
        if windows_root.exists():
            roots.append((letter, windows_root))
        elif wsl_root.exists():
            roots.append((letter, wsl_root))
    return roots



def candidate_library_bases() -> list[Path]:
    bases: list[Path] = []
    for letter, root in _drive_roots():
        if str(root).startswith("/mnt/"):
            bases.extend(
                [
                    root / "SteamLibrary",
                    root / "Steam",
                    root / "Program Files (x86)" / "Steam",
                    root / "Program Files" / "Steam",
                    root / "Games" / "SteamLibrary",
                    root / "Games" / "Steam",
                ]
            )
        else:
            bases.extend(
                [
                    Path(f"{letter}:/SteamLibrary"),
                    Path(f"{letter}:/Steam"),
                    Path(f"{letter}:/Program Files (x86)/Steam"),
                    Path(f"{letter}:/Program Files/Steam"),
                    Path(f"{letter}:/Games/SteamLibrary"),
                    Path(f"{letter}:/Games/Steam"),
                ]
            )
    return _unique_paths(bases)



def _path_variants(raw_path: str) -> list[Path]:
    cleaned = raw_path.replace("\\\\", "\\").replace("\\", "/")
    variants = [Path(cleaned)]
    match = WINDOWS_DRIVE_RE.match(cleaned)
    if match:
        drive = match.group("drive").lower()
        rest = match.group("rest")
        variants.append(Path(f"/mnt/{drive}/{rest}"))
    return _unique_paths(variants)



def parse_libraryfolders(vdf_path: Path) -> list[Path]:
    libraries: list[Path] = []
    if not vdf_path.exists():
        return libraries
    for line in vdf_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if '"path"' not in line:
            continue
        parts = re.findall(r'"([^"]+)"', line)
        if len(parts) < 2:
            continue
        for variant in _path_variants(parts[1]):
            if variant.exists():
                libraries.append(variant)
    return _unique_paths(libraries)



def infer_save_dir_from_game_dir(game_dir: Path) -> Path | None:
    candidates = [
        game_dir,
        game_dir / "save",
        game_dir / "SHXY" / "save",
    ]
    for candidate in candidates:
        if (candidate / GLOBAL_FILE).exists():
            return candidate
    return None



def find_save_dir_from_manifest(manifest_path: Path) -> SaveLocation | None:
    try:
        text = manifest_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    match = INSTALLDIR_RE.search(text)
    if not match:
        return None
    install_dir = match.group("installdir")
    common_dir = manifest_path.parent / "common" / install_dir
    save_dir = infer_save_dir_from_game_dir(common_dir)
    if save_dir:
        return SaveLocation(save_dir=save_dir, source="steam manifest", manifest_path=manifest_path)
    return None



def find_save_dir_near(start: Path) -> SaveLocation | None:
    candidates = [start, *start.parents]
    for base in candidates:
        nearby = [
            base,
            base / "save",
            base / "SHXY" / "save",
            base / "steamapps" / "common" / "SHXY" / "SHXY" / "save",
        ]
        for candidate in nearby:
            if (candidate / GLOBAL_FILE).exists():
                return SaveLocation(save_dir=candidate, source="near current location")
    return None



def discover_save_locations(start: Path | None = None) -> list[SaveLocation]:
    results: list[SaveLocation] = []
    seen: set[str] = set()

    def add(location: SaveLocation | None) -> None:
        if not location:
            return
        try:
            key = str(location.save_dir.resolve()).lower()
        except OSError:
            key = str(location.save_dir).lower()
        if key not in seen:
            results.append(location)
            seen.add(key)

    if start is None:
        start = Path.cwd()
    add(find_save_dir_near(start))

    for base in candidate_library_bases():
        steamapps = base / "steamapps"
        manifest_path = steamapps / MANIFEST_NAME
        add(find_save_dir_from_manifest(manifest_path))

        direct_game_dir = steamapps / "common" / "SHXY"
        direct_save_dir = infer_save_dir_from_game_dir(direct_game_dir)
        if direct_save_dir:
            add(
                SaveLocation(
                    save_dir=direct_save_dir,
                    source="steam library scan",
                    manifest_path=manifest_path if manifest_path.exists() else None,
                )
            )

        for library in parse_libraryfolders(steamapps / "libraryfolders.vdf"):
            lib_steamapps = library / "steamapps"
            manifest_path = lib_steamapps / MANIFEST_NAME
            add(find_save_dir_from_manifest(manifest_path))
            direct_game_dir = lib_steamapps / "common" / "SHXY"
            direct_save_dir = infer_save_dir_from_game_dir(direct_game_dir)
            if direct_save_dir:
                add(
                    SaveLocation(
                        save_dir=direct_save_dir,
                        source="libraryfolders scan",
                        manifest_path=manifest_path if manifest_path.exists() else None,
                    )
                )

    return results



def list_save_files(save_dir: Path) -> list[Path]:
    files = [path for path in save_dir.glob(SAVE_GLOB) if path.is_file()]
    return sorted(files, key=lambda item: item.name)



def resolve_slot_id(save_path: Path) -> int | None:
    match = re.match(r"file(\d+)\.rmmzsave$", save_path.name)
    return int(match.group(1)) if match else None



def read_account_id(auto_cloud_path: Path) -> str | None:
    if not auto_cloud_path.exists():
        return None
    text = auto_cloud_path.read_text(encoding="utf-8", errors="ignore")
    match = ACCOUNT_ID_RE.search(text)
    return match.group("accountid") if match else None



def format_timestamp(value: int | float | None) -> str:
    if not value:
        return "-"
    timestamp = float(value)
    if timestamp > TIMESTAMP_EPOCH_CUTOFF:
        timestamp /= 1000
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
