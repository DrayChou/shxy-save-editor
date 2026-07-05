from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from shxy_save_editor.cli import explain_actor_stats
from shxy_save_editor.rmmzsave import write_save


class CliExplainActorStatsTests(unittest.TestCase):
    def test_explain_actor_stats_uses_local_database_traits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            save_dir = root / "save"
            data_dir.mkdir()
            save_dir.mkdir()

            (data_dir / "Actors.json").write_text(json.dumps([None, {"id": 1, "name": "测试角色", "classId": 1, "traits": []}], ensure_ascii=False), encoding="utf-8")
            (data_dir / "Classes.json").write_text(
                json.dumps(
                    [
                        None,
                        {
                            "id": 1,
                            "name": "测试职业",
                            "params": [[0, 100], [0, 20], [0, 10], [0, 8], [0, 6], [0, 5], [0, 4], [0, 3]],
                            "traits": [
                                {"code": 21, "dataId": 2, "value": 2.0},
                                {"code": 22, "dataId": 0, "value": 1.0},
                                {"code": 22, "dataId": 1, "value": 0.05},
                            ],
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (data_dir / "Weapons.json").write_text(json.dumps([None, {"id": 1, "name": "木剑", "params": [0, 0, 5, 0, 0, 0, 0, 0], "traits": []}], ensure_ascii=False), encoding="utf-8")
            (data_dir / "Armors.json").write_text(json.dumps([None], ensure_ascii=False), encoding="utf-8")
            (data_dir / "States.json").write_text(json.dumps([None], ensure_ascii=False), encoding="utf-8")

            save_path = save_dir / "file1.rmmzsave"
            write_save(
                save_path,
                {
                    "actors": {
                        "_data": [
                            None,
                            {
                                "_name": "周一",
                                "_classId": 1,
                                "_level": 1,
                                "_paramPlus": [10, 0, 20, 0, 0, 0, 0, 0],
                                "_equips": [{"_dataClass": "weapon", "_itemId": 1}],
                                "_states": [],
                            },
                        ]
                    }
                },
            )

            lines = explain_actor_stats(str(save_path), actor_id=1, data_dir_text=str(data_dir))
            text = "\n".join(lines)
            self.assertIn("职业: class_id=1 测试职业", text)
            self.assertIn("攻击: 职业10 + paramPlus20 + 装备5 = 35; 倍率 2", text)
            self.assertIn("命中: 100.00%", text)
            self.assertIn("闪避: 5.00%", text)


if __name__ == "__main__":
    unittest.main()
