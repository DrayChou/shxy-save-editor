from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import rmmzsave
from .locator import format_timestamp, list_save_files, resolve_slot_id

GOLD_PATH = "party._gold"
SP_PATH = "variables._data.44"
PARAM_LABELS = ["生命", "内力", "攻击", "防御", "内功", "内防", "轻功", "悟性"]


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



def actor_summary(data: dict[str, Any], actor_id: int) -> ActorSummary | None:
    actor_data = data.get("actors", {}).get("_data", [])
    if not isinstance(actor_data, list) or actor_id >= len(actor_data):
        return None
    actor = actor_data[actor_id]
    if not actor:
        return None
    return ActorSummary(
        actor_id=actor_id,
        name=str(actor.get("_name", f"角色{actor_id}")),
        nickname=str(actor.get("_nickname", "")),
        level=int(actor.get("_level", 0) or 0),
        hp=int(actor.get("_hp", 0) or 0),
        mp=int(actor.get("_mp", 0) or 0),
        tp=int(actor.get("_tp", 0) or 0),
        param_plus=list(actor.get("_paramPlus", [0] * 8)),
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



def apply_actor_param_plus(data: dict[str, Any], actor_id: int, values: list[int]) -> None:
    actor_data = data["actors"]["_data"][actor_id]
    actor_data["_paramPlus"] = [int(item) for item in values]



def buff_party(data: dict[str, Any], amount: int) -> list[str]:
    changed: list[str] = []
    for actor in list_party_actors(data):
        new_values = [value + amount for value in actor.param_plus]
        apply_actor_param_plus(data, actor.actor_id, new_values)
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
