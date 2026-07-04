from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from shxy_save_editor import rmmzsave



def sample_save_data() -> dict:
    variables = [None] * 45
    variables[44] = 123
    return {
        "party": {
            "_gold": 456,
            "_actors": [1, 2],
            "_items": {"1": 2, "2": 3},
            "_weapons": {"5": 1},
            "_armors": {"7": 4},
        },
        "variables": {"_data": variables},
        "actors": {
            "_data": [
                None,
                {"_name": "周大", "_nickname": "", "_level": 8, "_hp": 100, "_mp": 30, "_tp": 0, "_paramPlus": [1, 2, 3, 4, 5, 6, 7, 8]},
                {"_name": "白乐天", "_nickname": "少时玩伴", "_level": 7, "_hp": 80, "_mp": 22, "_tp": 5, "_paramPlus": [0, 0, 0, 0, 0, 0, 0, 0]},
            ]
        },
    }


class RmmzSaveTests(unittest.TestCase):
    def test_roundtrip_and_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "file0.rmmzsave"
            data = sample_save_data()
            rmmzsave.write_save(save_path, data)

            loaded = rmmzsave.read_save(save_path)
            self.assertEqual(loaded, data)

            backup = rmmzsave.backup_save(save_path)
            self.assertTrue(backup.exists())
            self.assertTrue(str(backup).endswith(".bak"))

    def test_export_import_and_path_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "file1.rmmzsave"
            json_path = Path(tmp) / "file1.rmmzsave.json"
            data = sample_save_data()
            rmmzsave.write_save(save_path, data)

            exported = rmmzsave.export_json(save_path, json_path)
            self.assertEqual(exported, json_path)
            exported_data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(exported_data["party"]["_gold"], 456)

            loaded = rmmzsave.read_save(save_path)
            self.assertEqual(rmmzsave.get_path(loaded, "party._gold"), 456)
            rmmzsave.set_path(loaded, "variables._data.44", 999)
            self.assertEqual(loaded["variables"]["_data"][44], 999)

            json_path.write_text(json.dumps(loaded, ensure_ascii=False, indent=2), encoding="utf-8")
            rmmzsave.import_json(json_path, save_path)
            self.assertEqual(rmmzsave.read_save(save_path)["variables"]["_data"][44], 999)


if __name__ == "__main__":
    unittest.main()
