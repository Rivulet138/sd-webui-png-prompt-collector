import json
import sys
import tempfile
import unittest
from pathlib import Path

from png_prompt_collector.service import build_prompt_batch, import_prompt_batch


ROOT = Path(__file__).resolve().parents[1]
EXTENSIONS = ROOT.parent
STUDIO_ROOT = EXTENSIONS / "sd-webui-llm-prompt-studio"


@unittest.skipUnless(STUDIO_ROOT.is_dir(), "LLM Prompt Studio is not installed")
class CrossPluginRoundTripTests(unittest.TestCase):
    @staticmethod
    def _load_studio():
        scripts = str(STUDIO_ROOT / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        import prompt_studio_ui
        return prompt_studio_ui

    def test_collector_studio_json_round_trip(self):
        studio = self._load_studio()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / "one.png", root / "two.png"
            first.write_bytes(b"first image")
            second.write_bytes(b"second image")
            collected = build_prompt_batch([(first, "same tags"), (second, "same tags")])

            original = studio._expand_or_polish
            studio._expand_or_polish = lambda source, *_args: (f"Natural description of {source}.", "ok")
            try:
                updates = list(studio._png_batch_run(
                    collected, "Polish", "Natural Language", "", "Auto / checkpoint default",
                    "SFW", "", "", "OpenAI Compatible", "http://127.0.0.1:1234/v1",
                    "test-model", "", 0.3, 30, 1024, True, "cross-plugin-roundtrip",
                ))
            finally:
                studio._expand_or_polish = original
                studio._PNG_BATCH_CANCEL.clear()

            processed = studio._normalize_png_batch_payload(updates[-1][0])
            self.assertEqual(len(processed["records"]), 2)
            self.assertEqual(
                [record["prompt"]["processed_kind"] for record in processed["records"]],
                ["natural", "natural"],
            )

            source = root / "studio.json"
            source.write_text(json.dumps(processed, ensure_ascii=False), encoding="utf-8")
            loaded = import_prompt_batch(str(source))
            self.assertEqual([record["record_id"] for record in loaded["records"]], [
                collected["records"][0]["record_id"], collected["records"][1]["record_id"],
            ])
            self.assertEqual(
                [record["prompt"]["processed"] for record in loaded["records"]],
                ["Natural description of same tags.", "Natural description of same tags."],
            )


if __name__ == "__main__":
    unittest.main()
