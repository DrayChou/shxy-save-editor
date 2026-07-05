from __future__ import annotations

import unittest

from shxy_save_editor.model import apply_actor_param_plus, detect_actor_extra_stats, get_variable_value, set_party_params, set_variable_value


class ModelExtraStatsTests(unittest.TestCase):
    def test_detect_actor_extra_stats_prefers_xparam_plus(self) -> None:
        actor = {
            "_xparamPlus": [1.0, 0.05, 0.12],
            "_hit": 88,
            "_eva": 1,
            "_cri": 2,
        }
        stats, sources = detect_actor_extra_stats(actor)
        self.assertEqual(stats["命中"], 100)
        self.assertEqual(stats["闪避"], 5)
        self.assertEqual(stats["暴击"], 12)
        self.assertEqual(sources["命中"], "_xparamPlus[0]")
        self.assertEqual(sources["闪避"], "_xparamPlus[1]")
        self.assertEqual(sources["暴击"], "_xparamPlus[2]")

    def test_apply_actor_param_plus_returns_clamped_values(self) -> None:
        data = {
            "variables": {"_data": [None] * 181},
            "actors": {"_data": [None, {"_paramPlus": [0] * 8}]},
        }
        data["variables"]["_data"][180] = 1
        applied = apply_actor_param_plus(data, 1, [99999] * 8)
        expected = [30000, 30000, 1500, 1500, 1500, 1500, 300, 150]
        self.assertEqual(applied, expected)
        self.assertEqual(data["actors"]["_data"][1]["_paramPlus"], expected)

    def test_set_party_params_sets_all_eight_values(self) -> None:
        data = {
            "party": {"_actors": [1, 2]},
            "actors": {
                "_data": [
                    None,
                    {"_name": "甲", "_paramPlus": [1, 2, 3, 4, 5, 6, 7, 8]},
                    {"_name": "乙", "_paramPlus": [0, 0, 0, 0, 0, 0, 0, 0]},
                ]
            },
        }
        changed = set_party_params(data, 9999)
        self.assertEqual(changed, ["甲", "乙"])
        expected = [9999, 9999, 1000, 1000, 1000, 1000, 200, 100]
        self.assertEqual(data["actors"]["_data"][1]["_paramPlus"], expected)
        self.assertEqual(data["actors"]["_data"][2]["_paramPlus"], expected)

    def test_variable_helpers_expand_and_read_defaults(self) -> None:
        data = {"variables": {"_data": [None, 1, 2]}}
        self.assertEqual(get_variable_value(data, 1), 1)
        self.assertEqual(get_variable_value(data, 99, 7), 7)
        set_variable_value(data, 5, 123)
        self.assertEqual(data["variables"]["_data"][5], 123)
        self.assertEqual(get_variable_value(data, 5), 123)


if __name__ == "__main__":
    unittest.main()
