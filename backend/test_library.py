"""Library scan / delete / select tests. Uses a temp MODEL_DIR."""

import pathlib
import tempfile
import unittest

from backend import config
from backend import download as download_mod
from backend import model as model_mod


class LibraryTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._real_dir = config.MODEL_DIR
        config.MODEL_DIR = pathlib.Path(self._tmp.name)
        # catalogue file in a tier subfolder (the on-disk layout)
        tier_file = config.MODEL_DIR / "lite" / config.MODELS["lite"]["file"]
        tier_file.parent.mkdir(parents=True)
        tier_file.write_bytes(b"\x00" * 64)

    def tearDown(self):
        config.MODEL_DIR = self._real_dir
        self._tmp.cleanup()
        download_mod._progress.clear()

    def test_find_local_searches_subfolders(self):
        found = download_mod.find_local("lite")
        self.assertTrue(str(found).endswith(config.MODELS["lite"]["file"]))
        self.assertTrue(download_mod.is_downloaded("lite"))
        self.assertFalse(download_mod.is_downloaded("medium"))

    def test_library_lists_only_catalogue_tiers(self):
        entries = {e["id"]: e for e in download_mod.library()}
        self.assertEqual(set(entries), set(config.MODELS))
        self.assertTrue(entries["lite"]["downloaded"])
        self.assertEqual(entries["lite"]["size_bytes"], 64)
        self.assertFalse(entries["medium"]["downloaded"])
        self.assertIsNone(entries["medium"]["size_bytes"])

    def test_delete_removes_tier_file(self):
        self.assertTrue(download_mod.delete("lite"))
        self.assertFalse(download_mod.is_downloaded("lite"))
        self.assertFalse(download_mod.delete("lite"))
        self.assertFalse(download_mod.delete("medium"))  # nothing on disk
        self.assertFalse(download_mod.delete("nope"))

    def test_spec_for_rejects_unknown_ids(self):
        model_mod.spec_for("lite")
        with self.assertRaises(ValueError):
            model_mod.spec_for("nope")
        with self.assertRaises(ValueError):
            model_mod.spec_for("file:whatever.gguf")

    def test_start_download_rejects_unknown_tiers(self):
        with self.assertRaises(ValueError):
            download_mod.start_download("nope")

if __name__ == "__main__":
    unittest.main()
