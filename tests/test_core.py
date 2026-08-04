from __future__ import annotations

import unittest

from png_prompt_collector.core import aggregate_prompts, extract_positive_prompt, split_prompt_tags


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


class SplitPromptTagsTests(unittest.TestCase):
    def test_preserves_nested_commas_and_quoted_text(self):
        prompt = 'masterpiece, (red hair, blue eyes:1.2), <lora:name,variant:0.8>, "soft, light"'

        self.assertEqual(
            split_prompt_tags(prompt),
            ["masterpiece", "(red hair, blue eyes:1.2)", "<lora:name,variant:0.8>", '"soft, light"'],
        )

    def test_normalizes_whitespace_and_ignores_empty_tags(self):
        self.assertEqual(split_prompt_tags(" 1girl, , blue\n eyes, "), ["1girl", "blue eyes"])


class AggregatePromptsTests(unittest.TestCase):
    def test_deduplicates_in_first_seen_order_and_counts_sources(self):
        result = aggregate_prompts(
            [
                ("a.png", "Masterpiece, 1girl, blue eyes"),
                ("b.png", "masterpiece, blue eyes, smile"),
                ("b.png", "smile"),
            ],
            deduplicate=True,
            case_sensitive=False,
        )

        self.assertEqual(result.tags, ("Masterpiece", "1girl", "blue eyes", "smile"))
        self.assertEqual(result.total_occurrences, 7)
        self.assertEqual(result.duplicates_removed, 3)
        self.assertEqual(result.summaries[0].occurrences, 2)
        self.assertEqual(result.summaries[0].source_count, 2)
        self.assertEqual(result.summaries[-1].occurrences, 2)
        self.assertEqual(result.summaries[-1].source_count, 1)

    def test_can_keep_duplicate_tags(self):
        result = aggregate_prompts(
            [("a.png", "cat, cat"), ("b.png", "cat")],
            deduplicate=False,
        )

        self.assertEqual(result.tags, ("cat", "cat", "cat"))
        self.assertEqual(result.duplicates_removed, 0)


if __name__ == "__main__":
    unittest.main()

