from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from shxy_save_editor import rmmzsave
from shxy_save_editor.locator import discover_save_locations, find_save_dir_near, infer_save_dir_from_game_dir
from shxy_save_editor.model import buff_party, fill_inventory_section, list_slots, load_snapshot



def sample_save_data() -> dict:
    variables = [None] * 45
    variables[44] = 321
    return {
        "party": {
            "_gold": 888,
            "_actors": [1, 2],
            "_items": {"1": 1, "2": 2},
            "_weapons": {"9": 1},
            "_armors": {"4": 1},
        },
        "variables": {"_data": variables},
        "actors": {
            "_data": [
                None,
                {"_name": "周大", "_nickname": "", "_level": 10, "_hp": 111, "_mp": 22, "_tp": 0, "_paramPlus": [10, 10, 10, 10, 10, 10, 10, 10]},
                {"_name": "白乐天", "_nickname": "少时玩伴", "_level": 9, "_hp": 99, "_mp": 18, "_tp": 5, "_paramPlus": [1, 2, 3, 4, 5, 6, 7, 8]},
            ]
        },
    }


class LocatorAndModelTests(unittest.TestCase):
    def _make_save_dir(self, base: Path) -> Path:
        save_dir = base / "SHXY" / "save"
        save_dir.mkdir(parents=True, exist_ok=True)
        rmmzsave.write_save(
            save_dir / "global.rmmzsave",
            [
                {
                    "title": "山河小侠",
                    "saveName": "大理山洞",
                    "playtime": "01:23:45",
                    "timestamp": 1776011068894,
                }
            ],
        )
        rmmzsave.write_save(save_dir / "file0.rmmzsave", sample_save_data())
        return save_dir

    def test_locator_helpers_find_save_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_dir = self._make_save_dir(root)
            self.assertEqual(infer_save_dir_from_game_dir(save_dir.parent), save_dir)
            self.assertEqual(infer_save_dir_from_game_dir(save_dir.parent.parent), save_dir)
            self.assertEqual(find_save_dir_near(save_dir).save_dir, save_dir)
            discovered = [item.save_dir for item in discover_save_locations(save_dir)]
            self.assertIn(save_dir, discovered)

    def test_model_lists_slots_and_modifies_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            save_dir = self._make_save_dir(Path(tmp))
            slots = list_slots(save_dir)
            self.assertEqual(len(slots), 1)
            self.assertEqual(slots[0].save_name, "大理山洞")
            snapshot = load_snapshot(slots[0])
            self.assertEqual(snapshot.gold, 888)
            self.assertEqual(snapshot.sp, 321)
            self.assertEqual([actor.name for actor in snapshot.actors], ["周大", "白乐天"])

            changed = buff_party(snapshot.data, 5)
            self.assertEqual(changed, ["周大", "白乐天"])
            self.assertEqual(snapshot.data["actors"]["_data"][1]["_paramPlus"][0], 15)
            self.assertEqual(snapshot.data["actors"]["_data"][2]["_paramPlus"][7], 13)

            item_count = fill_inventory_section(snapshot.data, "_items", 99)
            self.assertEqual(item_count, 2)
            self.assertEqual(snapshot.data["party"]["_items"], {"1": 99, "2": 99})


if __name__ == "__main__":
    unittest.main()
