from __future__ import annotations

import unittest

from png_prompt_collector.core import extract_positive_prompt


class ExtractPositivePromptTests(unittest.TestCase):
    def test_removes_negative_prompt_and_generation_parameters(self):
        infotext = (
            "masterpiece, 1girl, blue eyes\n"
            "Negative prompt: lowres, bad hands\n"
            "Steps: 24, Sampler: Euler a, CFG scale: 7, Seed: 42, Size: 768x1024"
        )

        self.assertEqual(extract_positive_prompt(infotext), "masterpiece, 1girl, blue eyes")

    def test_removes_parameter_line_when_negative_prompt_is_absent(self):
        infotext = "a quiet street at night\nSteps: 20, Sampler: Euler, Seed: 9, Size: 512x512"

        self.assertEqual(extract_positive_prompt(infotext), "a quiet street at night")

    def test_accepts_positive_prompt_prefix(self):
        self.assertEqual(extract_positive_prompt("Positive prompt: cat, window"), "cat, window")

if __name__ == "__main__":
    unittest.main()
