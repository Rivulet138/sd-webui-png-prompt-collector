from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image, PngImagePlugin

from png_prompt_collector.service import collect_positive_prompts, discover_png_paths, read_positive_prompt


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
                deduplicate=True,
                ignore_case=True,
            )

            self.assertEqual(result.selected_count, 2)
            self.assertEqual(result.imported_count, 2)
            self.assertEqual(result.collection.tags, ("cat", "blue eyes", "smile"))

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


if __name__ == "__main__":
    unittest.main()

