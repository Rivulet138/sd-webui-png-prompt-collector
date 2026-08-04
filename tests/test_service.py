from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image, PngImagePlugin

from png_prompt_collector.service import (
    MAX_BATCH_RECORDS,
    MAX_PROMPT_LENGTH,
    build_prompt_batch,
    collect_positive_prompts,
    discover_png_paths,
    export_prompt_batch,
    import_prompt_batch,
    read_positive_prompt,
)


def write_test_png(path: Path, parameters: str | None = None) -> None:
    metadata = PngImagePlugin.PngInfo()
    if parameters is not None:
        metadata.add_text("parameters", parameters)
    Image.new("RGB", (8, 8), "white").save(path, pnginfo=metadata)


class PngServiceTests(unittest.TestCase):
    def test_reads_only_positive_prompt_from_png_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.png"
            write_test_png(
                path,
                "cat, window\nNegative prompt: dog, blur\nSteps: 20, Sampler: Euler, Seed: 1",
            )

            self.assertEqual(read_positive_prompt(path), "cat, window")

    def test_collects_uploaded_and_directory_files_without_double_reading(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "nested"
            nested.mkdir()
            first = root / "one.png"
            second = nested / "two.png"
            write_test_png(first, "cat, blue eyes")
            write_test_png(second, "cat, smile")

            result = collect_positive_prompts(
                [str(first)],
                str(root),
                recursive=True,
            )

            self.assertEqual(result.selected_count, 2)
            self.assertEqual(result.imported_count, 2)
            self.assertEqual([prompt for _, prompt in result.records], ["cat, blue eyes", "cat, smile"])

    def test_reports_png_without_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.png"
            write_test_png(path)

            result = collect_positive_prompts([str(path)])

            self.assertEqual(result.imported_count, 0)
            self.assertEqual(result.skipped_count, 1)
            self.assertIn("未找到可读取的正向提示词", result.errors[0])

    def test_discovers_only_png_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_test_png(root / "image.png", "cat")
            (root / "notes.txt").write_text("cat", encoding="utf-8")

            paths, errors = discover_png_paths(directory=str(root))

            self.assertEqual([path.name for path in paths], ["image.png"])
            self.assertEqual(errors, ())

    def test_records_preserve_each_image_and_batch_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "one.png"
            second = Path(directory) / "two.png"
            write_test_png(first, "cat")
            write_test_png(second, "dog")
            result = collect_positive_prompts([str(first), str(second)])
            batch = build_prompt_batch(result.records)
            self.assertEqual([r["prompt"]["positive"] for r in batch["records"]], ["cat", "dog"])
            self.assertEqual(import_prompt_batch(batch), batch)

    def test_batch_limits_are_enforced_without_silent_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "one.png"
            write_test_png(image, "cat")
            with self.assertRaisesRegex(ValueError, "最多"):
                build_prompt_batch([(image, f"prompt {index}") for index in range(MAX_BATCH_RECORDS + 1)], deduplicate=False)
            with self.assertRaisesRegex(ValueError, "超过"):
                build_prompt_batch([(image, "x" * (MAX_PROMPT_LENGTH + 1))])

    def test_export_can_be_imported_again(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "one.png"
            write_test_png(image, "cat")
            batch = build_prompt_batch([(image, "cat")])
            exported = export_prompt_batch(batch)
            self.assertEqual(import_prompt_batch(exported), batch)


if __name__ == "__main__":
    unittest.main()
