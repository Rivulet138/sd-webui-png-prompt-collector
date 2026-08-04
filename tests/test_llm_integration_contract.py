from __future__ import annotations

import re
import unittest
from pathlib import Path


EXTENSION_ROOT = Path(__file__).resolve().parents[1]
LLM_STUDIO_UI = EXTENSION_ROOT.parent / "sd-webui-llm-prompt-studio" / "scripts" / "prompt_studio_ui.py"
BRIDGE_JS = EXTENSION_ROOT / "javascript" / "png_prompt_collector.js"
COLLECTOR_UI = EXTENSION_ROOT / "png_prompt_collector" / "ui.py"


class LlmIntegrationContractTests(unittest.TestCase):
    def test_bridge_target_matches_visible_llm_studio_source_field(self):
        bridge = BRIDGE_JS.read_text(encoding="utf-8")
        llm_ui = LLM_STUDIO_UI.read_text(encoding="utf-8")
        match = re.search(r'const TARGET_ID = "([^"]+)";', bridge)

        self.assertIsNotNone(match)
        self.assertIn(f'elem_id="{match.group(1)}"', llm_ui)
        self.assertIn("PNG Tag 汇总可导入", llm_ui)

    def test_collector_exposes_visible_send_action(self):
        collector_ui = COLLECTOR_UI.read_text(encoding="utf-8")

        self.assertIn("LLM Prompt Studio 联动", collector_ui)
        self.assertIn("发送并打开 LLM Prompt Studio", collector_ui)
        self.assertIn("window.pngPromptCollector.sendToLlmPromptStudio", collector_ui)

    def test_collector_exposes_workflow_sections_and_status_targets(self):
        collector_ui = COLLECTOR_UI.read_text(encoding="utf-8")
        css = (EXTENSION_ROOT / "style.css").read_text(encoding="utf-8")

        for elem_id in (
            "ppc_collection_workspace",
            "ppc_collection_status",
            "ppc_llm_handoff",
            "ppc_export_result",
        ):
            self.assertIn(f'elem_id="{elem_id}"', collector_ui)
        self.assertIn(".ppc-workflow-section", css)
        self.assertIn("@media (max-width: 900px)", css)


if __name__ == "__main__":
    unittest.main()
