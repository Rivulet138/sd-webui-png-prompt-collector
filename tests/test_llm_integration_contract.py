from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXTENSIONS = ROOT.parent

class IntegrationContractTests(unittest.TestCase):
    def test_batch_targets_and_payload_are_exposed(self):
        ui = (ROOT / "png_prompt_collector" / "ui.py").read_text(encoding="utf-8")
        js = (ROOT / "javascript" / "png_prompt_collector.js").read_text(encoding="utf-8")
        self.assertIn('elem_id="ppc_prompt_records"', ui)
        self.assertIn('elem_id="ppc_prompt_batch_payload"', ui)
        self.assertIn("sendBatchToLlm", ui)
        self.assertIn("sendBatchToRanbooru", ui)
        self.assertIn("llm_prompt_studio_png_batch_payload", js)
        self.assertIn("ranbooru_prompt_batch_payload", js)

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
