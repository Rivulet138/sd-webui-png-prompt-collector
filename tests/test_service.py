from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image, PngImagePlugin

from png_prompt_collector.service import (
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

    def test_record_ids_are_stable_and_import_preserves_processing_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "one.png"
            write_test_png(image, "cat")
            first = build_prompt_batch([(image, "cat")])
            second = build_prompt_batch([(image, "cat")])

            self.assertEqual(first["records"][0]["record_id"], second["records"][0]["record_id"])
            record = first["records"][0]
            record["prompt"].update({"natural": "A cat.", "processed": "A detailed cat."})
            record.update({"status": "completed", "error": "", "appended": True, "booru": {"site": "danbooru"}})
            record["image"]["source_url"] = "https://example.invalid/post/1"

            imported = import_prompt_batch(first)["records"][0]
            self.assertEqual(imported["prompt"]["processed"], "A detailed cat.")
            self.assertEqual(imported["status"], "completed")
            self.assertTrue(imported["appended"])
            self.assertEqual(imported["booru"]["site"], "danbooru")
            self.assertEqual(imported["image"]["source_url"], "https://example.invalid/post/1")

    def test_import_rejects_duplicate_ids_and_malformed_sha256(self):
        base = {"image": {"filename": "one.png", "sha256": "a" * 64}, "prompt": {"positive": "cat"}}
        with self.assertRaisesRegex(ValueError, "record_id 重复"):
            import_prompt_batch({
                "schema_version": "prompt_batch.v1",
                "records": [{**base, "record_id": "same"}, {**base, "record_id": "same"}],
            })
        with self.assertRaisesRegex(ValueError, "sha256"):
            import_prompt_batch({
                "schema_version": "prompt_batch.v1",
                "records": [{"image": {"filename": "one.png", "sha256": "bad"}, "prompt": {"positive": "cat"}}],
            })

    def test_batch_record_count_is_unbounded_but_prompt_length_is_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "one.png"
            write_test_png(image, "cat")
            payload = {
                "schema_version": "prompt_batch.v1",
                "records": [
                    {"image": {"filename": f"{index}.png"}, "prompt": {"positive": f"prompt {index} " + "x" * 1024}}
                    for index in range(5001)
                ],
            }
            self.assertEqual(len(import_prompt_batch(payload)["records"]), 5001)
            batch = build_prompt_batch(
                [(image, f"prompt {index} " + "x" * 1024) for index in range(5001)],
                deduplicate=False,
            )
            self.assertEqual(len(batch["records"]), 5001)
            exported = Path(export_prompt_batch(payload))
            try:
                self.assertGreater(exported.stat().st_size, 4 * 1024 * 1024)
                self.assertEqual(len(import_prompt_batch(exported)["records"]), 5001)
            finally:
                exported.unlink(missing_ok=True)
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
