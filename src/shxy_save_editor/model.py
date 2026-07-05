from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import rmmzsave
from .locator import format_timestamp, list_save_files, resolve_slot_id

GOLD_PATH = "party._gold"
SP_PATH = "variables._data.44"
PARAM_LABELS = ["生命", "内力", "攻击", "防御", "内功", "内防", "轻功", "悟性"]
# Mirrors ActorStatLimiter.js plugin parameters in the game database.
# Limit = baseLimit + variables._data[180] * bonusMultiplier.
PARAM_PLUS_LIMITS = [
    (20000, 10000),
    (20000, 10000),
    (1000, 500),
    (1000, 500),
    (1000, 500),
    (1000, 500),
    (200, 100),
    (100, 50),
]
CUSTOM_VARIABLE_LABELS = ["道德", "厨艺", "酒量", "钓鱼等级", "炼药等级", "运势"]
EXTRA_STAT_LABELS = ["命中", "闪避", "暴击"]
X_PARAM_INDEX = {"命中": 0, "闪避": 1, "暴击": 2}
EXTRA_STAT_CANDIDATE_KEYS = {
    "命中": ["_hit", "hit", "_hitRate", "hitRate", "_xparamHit"],
    "闪避": ["_eva", "eva", "_evade", "evade", "_evadeRate", "evadeRate", "_xparamEva"],
    "暴击": ["_cri", "cri", "_crit", "crit", "_critical", "critical", "_critRate", "critRate", "_xparamCri"],
}


@dataclass(slots=True)
class SaveSlot:
    slot_id: int
    file_name: str
    file_path: Path
    title: str
    save_name: str
    playtime: str
    timestamp: str
    raw_timestamp: int | float | None
    exists_in_global: bool


@dataclass(slots=True)
class ActorSummary:
    actor_id: int
    name: str
    nickname: str
    level: int
    hp: int
    mp: int
    tp: int
    param_plus: list[int]
    extra_stats: dict[str, int]
    extra_stat_sources: dict[str, str]

    @property
    def label(self) -> str:
        level_text = f"Lv.{self.level}" if self.level else "Lv.?"
        return f"{self.name} ({level_text})"


@dataclass(slots=True)
class SaveSnapshot:
    slot: SaveSlot
    gold: int
    sp: int
    actors: list[ActorSummary]
    data: dict[str, Any]



def load_global_metadata(save_dir: Path) -> list[dict[str, Any]]:
    global_path = save_dir / "global.rmmzsave"
    if not global_path.exists():
        return []
    data = rmmzsave.read_save(global_path)
    return data if isinstance(data, list) else []



def list_slots(save_dir: Path) -> list[SaveSlot]:
    metadata = load_global_metadata(save_dir)
    meta_by_slot = {index: item for index, item in enumerate(metadata) if isinstance(item, dict)}
    slots: list[SaveSlot] = []

    for save_path in list_save_files(save_dir):
        slot_id = resolve_slot_id(save_path)
        if slot_id is None:
            continue
        meta = meta_by_slot.get(slot_id, {})
        slots.append(
            SaveSlot(
                slot_id=slot_id,
                file_name=save_path.name,
                file_path=save_path,
                title=str(meta.get("title", "")),
                save_name=str(meta.get("saveName", "")),
                playtime=str(meta.get("playtime", "")),
                timestamp=format_timestamp(meta.get("timestamp")),
                raw_timestamp=meta.get("timestamp"),
                exists_in_global=slot_id in meta_by_slot,
            )
        )
    return slots



def _normalize_percent_value(value: Any) -> int:
    numeric = float(value or 0)
    if abs(numeric) <= 1.5:
        return int(round(numeric * 100))
    return int(round(numeric))



def _denormalize_percent_value(value: int, original: Any) -> float | int:
    original_numeric = float(original or 0)
    if abs(original_numeric) <= 1.5:
        return float(value) / 100.0
    return int(value)



def detect_actor_extra_stats(actor: dict[str, Any]) -> tuple[dict[str, int], dict[str, str]]:
    stats: dict[str, int] = {}
    sources: dict[str, str] = {}

    xparam_plus = actor.get("_xparamPlus")
    if isinstance(xparam_plus, list):
        for label, index in X_PARAM_INDEX.items():
            if index < len(xparam_plus):
                stats[label] = _normalize_percent_value(xparam_plus[index])
                sources[label] = f"_xparamPlus[{index}]"

    for label, keys in EXTRA_STAT_CANDIDATE_KEYS.items():
        if label in stats:
            continue
        for key in keys:
            if key in actor:
                stats[label] = _normalize_percent_value(actor.get(key))
                sources[label] = key
                break

    return stats, sources



def actor_summary(data: dict[str, Any], actor_id: int) -> ActorSummary | None:
    actor_data = data.get("actors", {}).get("_data", [])
    if not isinstance(actor_data, list) or actor_id >= len(actor_data):
        return None
    actor = actor_data[actor_id]
    if not actor:
        return None
    extra_stats, extra_stat_sources = detect_actor_extra_stats(actor)
    return ActorSummary(
        actor_id=actor_id,
        name=str(actor.get("_name", f"角色{actor_id}")),
        nickname=str(actor.get("_nickname", "")),
        level=int(actor.get("_level", 0) or 0),
        hp=int(actor.get("_hp", 0) or 0),
        mp=int(actor.get("_mp", 0) or 0),
        tp=int(actor.get("_tp", 0) or 0),
        param_plus=list(actor.get("_paramPlus", [0] * 8)),
        extra_stats=extra_stats,
        extra_stat_sources=extra_stat_sources,
    )



def list_party_actors(data: dict[str, Any]) -> list[ActorSummary]:
    actor_ids = data.get("party", {}).get("_actors", [])
    result: list[ActorSummary] = []
    for actor_id in actor_ids:
        try:
            actor_id_int = int(actor_id)
        except (TypeError, ValueError):
            continue
        summary = actor_summary(data, actor_id_int)
        if summary:
            result.append(summary)
    return result



def rebuild_snapshot(snapshot: SaveSnapshot) -> SaveSnapshot:
    snapshot.gold = int(rmmzsave.get_path(snapshot.data, GOLD_PATH))
    snapshot.sp = int(rmmzsave.get_path(snapshot.data, SP_PATH))
    snapshot.actors = list_party_actors(snapshot.data)
    return snapshot



def load_snapshot(slot: SaveSlot) -> SaveSnapshot:
    data = rmmzsave.read_save(slot.file_path)
    snapshot = SaveSnapshot(slot=slot, gold=0, sp=0, actors=[], data=data)
    return rebuild_snapshot(snapshot)



def apply_gold(data: dict[str, Any], value: int) -> None:
    rmmzsave.set_path(data, GOLD_PATH, int(value))



def apply_sp(data: dict[str, Any], value: int) -> None:
    rmmzsave.set_path(data, SP_PATH, int(value))



def get_variable_value(data: dict[str, Any], index: int, default: int = 0) -> int:
    values = data.get("variables", {}).get("_data", [])
    if not isinstance(values, list) or index < 0 or index >= len(values):
        return default
    raw = values[index]
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return default



def set_variable_value(data: dict[str, Any], index: int, value: int) -> None:
    variables = data.setdefault("variables", {})
    values = variables.setdefault("_data", [])
    while len(values) <= index:
        values.append(0)
    values[index] = int(value)



def _param_plus_limits(data: dict[str, Any]) -> list[int]:
    bonus = get_variable_value(data, 180, 0)
    return [base + bonus * multiplier for base, multiplier in PARAM_PLUS_LIMITS]


def clamp_param_plus_values(data: dict[str, Any], values: list[int]) -> list[int]:
    limits = _param_plus_limits(data)
    result: list[int] = []
    for index, value in enumerate(values[: len(PARAM_LABELS)]):
        limit = limits[index] if index < len(limits) else int(value)
        result.append(min(int(value), limit))
    while len(result) < len(PARAM_LABELS):
        result.append(0)
    return result


def apply_actor_param_plus(data: dict[str, Any], actor_id: int, values: list[int]) -> list[int]:
    actor_data = data["actors"]["_data"][actor_id]
    clamped = clamp_param_plus_values(data, values)
    actor_data["_paramPlus"] = clamped
    return clamped



def apply_actor_extra_stats(data: dict[str, Any], actor_id: int, values: dict[str, int]) -> None:
    actor_data = data["actors"]["_data"][actor_id]
    current_stats, sources = detect_actor_extra_stats(actor_data)
    for label, value in values.items():
        source = sources.get(label)
        if not source:
            continue
        if source.startswith("_xparamPlus["):
            index = int(source[len("_xparamPlus[") : -1])
            xparam_plus = actor_data.setdefault("_xparamPlus", [])
            while len(xparam_plus) <= index:
                xparam_plus.append(0)
            xparam_plus[index] = _denormalize_percent_value(int(value), xparam_plus[index])
        else:
            actor_data[source] = _denormalize_percent_value(int(value), actor_data.get(source, current_stats.get(label, 0)))



def buff_party(data: dict[str, Any], amount: int) -> list[str]:
    changed: list[str] = []
    for actor in list_party_actors(data):
        new_values = [value + amount for value in actor.param_plus]
        apply_actor_param_plus(data, actor.actor_id, new_values)
        changed.append(actor.name)
    return changed



def set_party_params(data: dict[str, Any], value: int) -> list[str]:
    changed: list[str] = []
    for actor in list_party_actors(data):
        apply_actor_param_plus(data, actor.actor_id, [int(value)] * len(PARAM_LABELS))
        changed.append(actor.name)
    return changed



def fill_inventory_section(data: dict[str, Any], section: str, amount: int) -> int:
    inventory = data.get("party", {}).get(section, {})
    count = 0
    if isinstance(inventory, dict):
        for key in inventory:
            inventory[key] = int(amount)
            count += 1
    return count



def make_backup(slot: SaveSlot) -> Path:
    return rmmzsave.backup_save(slot.file_path)



def save_snapshot(snapshot: SaveSnapshot) -> Path:
    return rmmzsave.write_save(snapshot.slot.file_path, snapshot.data)
