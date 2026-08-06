from pathlib import Path
import sys
import types
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
EXTENSIONS = ROOT.parent

class IntegrationContractTests(unittest.TestCase):
    def test_collector_ui_builds_without_importing_receiver_plugins(self):
        original_modules = sys.modules.get("modules")
        original_shared = sys.modules.get("modules.shared")
        modules = types.ModuleType("modules")
        shared = types.ModuleType("modules.shared")
        shared.cmd_opts = SimpleNamespace(hide_ui_dir_config=False)
        modules.shared = shared
        sys.modules["modules"] = modules
        sys.modules["modules.shared"] = shared
        try:
            from png_prompt_collector.ui import create_ui

            tabs = create_ui()
        finally:
            if original_modules is None:
                sys.modules.pop("modules", None)
            else:
                sys.modules["modules"] = original_modules
            if original_shared is None:
                sys.modules.pop("modules.shared", None)
            else:
                sys.modules["modules.shared"] = original_shared

        self.assertEqual(len(tabs), 1)
        self.assertEqual(tabs[0][1:], ("PNG Prompt Collector", "png_prompt_collector"))

    def test_batch_targets_and_payload_are_exposed(self):
        ui = (ROOT / "png_prompt_collector" / "ui.py").read_text(encoding="utf-8")
        js = (ROOT / "javascript" / "png_prompt_collector.js").read_text(encoding="utf-8")
        self.assertIn('elem_id="ppc_prompt_records"', ui)
        self.assertIn('elem_id="ppc_prompt_batch_payload"', ui)
        self.assertIn('elem_id="ppc_cancel"', ui)
        self.assertNotIn("cancels=[collect_event]", ui)
        self.assertNotIn("collection_task_id = gr.State", ui)
        self.assertIn("is_cancelled=_COLLECTION_CANCEL.is_set", ui)
        self.assertIn("sendBatchToLlm", ui)
        self.assertIn("sendBatchToRanbooru", ui)
        self.assertIn("llm_prompt_studio_png_batch_payload", js)
        self.assertIn("ranbooru_prompt_batch_payload", js)
        self.assertIn("Array.isArray(batch?.records) ? batch.records : []", js)
        self.assertIn("const producer = batch?.producer", js)
        self.assertNotIn("slice(0, 200)", js)

    def test_receivers_expose_the_same_versioned_json_contract(self):
        llm = (EXTENSIONS / "sd-webui-llm-prompt-studio" / "scripts" / "prompt_studio_ui.py").read_text(encoding="utf-8")
        ranbooru_ui = (EXTENSIONS / "sd-webui-ranbooru-reforge" / "scripts" / "ranbooru.py").read_text(encoding="utf-8")
        ranbooru_db = (EXTENSIONS / "sd-webui-ranbooru-reforge" / "scripts" / "cache_db.py").read_text(encoding="utf-8")
        self.assertIn('PNG_BATCH_SCHEMA = "prompt_batch.v1"', llm)
        self.assertIn('elem_id="llm_prompt_studio_png_batch_payload"', llm)
        self.assertIn('elem_id="ranbooru_prompt_batch_payload"', ranbooru_ui)
        self.assertIn('PROMPT_BATCH_SCHEMA = "prompt_batch.v1"', ranbooru_db)

if __name__ == "__main__":
    unittest.main()
