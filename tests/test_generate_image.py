import importlib.util
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "generate_image.py"
SPEC = importlib.util.spec_from_file_location("generate_image", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class AtlasProviderTests(unittest.TestCase):
    def test_atlas_size_normalizes_supported_values(self):
        self.assertEqual(MODULE.atlas_size("2K"), "2048*2048")
        self.assertEqual(MODULE.atlas_size("2048x1152"), "2048*1152")
        self.assertIsNone(MODULE.atlas_size("adaptive"))

    def test_atlas_size_rejects_oversized_values(self):
        with self.assertRaisesRegex(ValueError, "最大支持"):
            MODULE.atlas_size("4K")
        with self.assertRaisesRegex(ValueError, "最大支持"):
            MODULE.atlas_size("4096x2048")

    def test_atlas_request_does_not_retry_generation_post(self):
        error = urllib.error.URLError("offline")
        with mock.patch.object(MODULE.urllib.request, "urlopen", side_effect=error) as urlopen:
            with self.assertRaisesRegex(RuntimeError, "连接错误"):
                MODULE.atlas_request("secret", {"model": MODULE.ATLAS_MODEL, "prompt": "test"})
        self.assertEqual(urlopen.call_count, 1)

    def test_atlas_generate_uses_schema_fields_and_outputs(self):
        submitted = {"data": {"id": "request-1", "status": "created"}}
        completed = {"id": "request-1", "status": "completed", "outputs": ["https://example.com/a.png"]}
        with mock.patch.object(MODULE, "atlas_request", return_value=submitted) as request:
            with mock.patch.object(MODULE, "atlas_prediction", return_value=completed):
                urls = MODULE.atlas_generate("secret", "draw a test", "2K", 1)

        self.assertEqual(urls, ["https://example.com/a.png"])
        payload = request.call_args.args[1]
        self.assertEqual(
            payload,
            {
                "model": "bytedance/seedream-v4",
                "prompt": "draw a test",
                "size": "2048*2048",
            },
        )

    def test_get_api_key_uses_provider_specific_environment(self):
        with mock.patch.dict(os.environ, {"ATLASCLOUD_API_KEY": "atlas-key"}, clear=True):
            self.assertEqual(MODULE.get_api_key("atlas"), "atlas-key")

    def test_correct_image_suffix_renames_jpeg_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "output.png"
            path.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 20)
            corrected = MODULE.correct_image_suffix(path)
            self.assertEqual(corrected.suffix, ".jpg")
            self.assertTrue(corrected.exists())
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
