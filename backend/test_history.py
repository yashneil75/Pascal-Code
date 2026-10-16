"""Model context follows the open conversation. Data ops only, no weights."""

import unittest

from backend import model as model_mod


class HistoryTest(unittest.TestCase):
    def test_model_history_round_trip(self):
        m = model_mod.Model("lite")
        m.set_history(
            [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "yo"},
            ]
        )
        self.assertEqual(
            m.get_history(),
            [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "yo"},
            ],
        )
        m.reset_history()
        self.assertEqual(m.get_history(), [])

    def test_model_history_drops_tool_traffic(self):
        m = model_mod.Model("lite")
        m.set_history(
            [
                {"role": "user", "content": "ls"},
                {"role": "assistant", "content": None, "tool_calls": ["x"]},
                {"role": "tool", "tool_call_id": "1", "content": "x"},
                {"role": "assistant", "content": "done"},
            ]
        )
        self.assertEqual(
            m.get_history(),
            [
                {"role": "user", "content": "ls"},
                {"role": "assistant", "content": "done"},
            ],
        )

    def test_manager_records_and_resets_without_loading(self):
        mgr = model_mod.ModelManager("lite")
        mgr.set_history([{"role": "user", "content": "a"}])
        self.assertEqual(mgr._history, [{"role": "user", "content": "a"}])
        mgr.reset_history()
        self.assertEqual(mgr._history, [])

    def test_manager_select_keeps_recorded_history_when_live_is_empty(self):
        # A mock (or never-started model) has no live history; select must not
        # wipe the history recorded by opening a chat before first load.
        mgr = model_mod.ModelManager("lite")
        mgr.set_history([{"role": "user", "content": "a"}])
        mgr.select("medium")
        self.assertEqual(mgr._history, [{"role": "user", "content": "a"}])


if __name__ == "__main__":
    unittest.main()
