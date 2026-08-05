from __future__ import annotations

import tempfile
import threading
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from PIL import Image, PngImagePlugin

from png_prompt_collector.service import (
    ImportResult,
    MAX_PROMPT_LENGTH,
    build_prompt_batch,
    build_prompt_batch_with_stats,
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
    def test_ui_collection_cancellation_keeps_records_read_before_cancel(self):
        original_modules = sys.modules.get("modules")
        original_shared = sys.modules.get("modules.shared")
        modules = types.ModuleType("modules")
        shared = types.ModuleType("modules.shared")
        shared.cmd_opts = SimpleNamespace(hide_ui_dir_config=False)
        modules.shared = shared
        sys.modules["modules"] = modules
        sys.modules["modules.shared"] = shared
        try:
            from png_prompt_collector import ui
        finally:
            if original_modules is None:
                sys.modules.pop("modules", None)
            else:
                sys.modules["modules"] = original_modules
            if original_shared is None:
                sys.modules.pop("modules.shared", None)
            else:
                sys.modules["modules.shared"] = original_shared

        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "completed.png"
            write_test_png(image, "completed prompt")
            task_id = "cancel-during-read"

            def cancelled_collection(*_args, **_kwargs):
                ui._COLLECTION_TASKS[task_id].set()
                return ImportResult(
                    selected_count=3,
                    imported_count=1,
                    skipped_count=0,
                    errors=(),
                    records=((image, "completed prompt"),),
                    processed_count=1,
                    cancelled_count=2,
                )

            with mock.patch.object(ui, "collect_positive_prompts", side_effect=cancelled_collection):
                status, rows, batch, exported, errors = ui._collect(
                    [str(image)], "", True, True, task_id, progress=lambda *_args, **_kwargs: None,
                )

            self.assertEqual(len(rows), 1)
            self.assertEqual(batch["records"][0]["prompt"]["positive"], "completed prompt")
            self.assertIsNotNone(exported)
            self.assertEqual(errors, "")
            self.assertIn("已完成记录已保留", status)
            self.assertIn("取消时剩余 2 张", status)

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

    def test_collection_reports_progress_for_every_selected_image(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for index in range(3):
                path = Path(directory) / f"{index}.png"
                write_test_png(path, f"prompt {index}" if index != 1 else None)
                paths.append(str(path))
            updates = []

            result = collect_positive_prompts(
                paths,
                progress=lambda completed, total, path: updates.append((completed, total, path.name)),
            )

            self.assertEqual(result.imported_count, 2)
            self.assertEqual(
                updates,
                [(1, 3, "0.png"), (2, 3, "1.png"), (3, 3, "2.png")],
            )

    def test_collection_cancellation_returns_completed_records_and_stops_before_next_image(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for index in range(3):
                path = Path(directory) / f"{index}.png"
                write_test_png(path, f"prompt {index}")
                paths.append(str(path))
            cancelled = threading.Event()

            result = collect_positive_prompts(
                paths,
                progress=lambda *_args: cancelled.set(),
                is_cancelled=cancelled.is_set,
            )

            self.assertEqual(result.processed_count, 1)
            self.assertEqual(result.cancelled_count, 2)
            self.assertEqual(result.imported_count, 1)
            self.assertEqual(result.skipped_count, 0)
            self.assertEqual([prompt for _, prompt in result.records], ["prompt 0"])

    def test_batch_build_cancellation_stops_before_hashing_the_next_image(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for index in range(3):
                path = Path(directory) / f"{index}.png"
                write_test_png(path, f"prompt {index}")
                paths.append(path)
            cancelled = threading.Event()
            hash_started = threading.Event()
            release_hash = threading.Event()
            holder = {}

            from png_prompt_collector import service
            original_hash = service._sha256_file

            def slow_first_hash(path):
                if not hash_started.is_set():
                    hash_started.set()
                    release_hash.wait(timeout=5)
                return original_hash(path)

            def build():
                holder["result"] = build_prompt_batch_with_stats(
                    [(path, f"prompt {index}") for index, path in enumerate(paths)],
                    is_cancelled=cancelled.is_set,
                )

            with mock.patch.object(service, "_sha256_file", side_effect=slow_first_hash):
                thread = threading.Thread(target=build)
                thread.start()
                self.assertTrue(hash_started.wait(timeout=5))
                cancelled.set()
                release_hash.set()
                thread.join(timeout=5)

            self.assertFalse(thread.is_alive())
            result = holder["result"]
            self.assertEqual(result.processed_count, 1)
            self.assertEqual(result.cancelled_count, 2)
            self.assertEqual(len(result.batch["records"]), 1)

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
            record["prompt"].update({
                "natural": "A cat.",
                "processed": "A detailed cat.",
                "processed_kind": "expanded",
                "output_kind": "positive_prompt",
            })
            record.update({"status": "completed", "error": "", "appended": True, "booru": {"site": "danbooru"}})
            record["source_identity"] = "tags:cat"
            record["image"]["source_url"] = "https://example.invalid/post/1"

            imported = import_prompt_batch(first)["records"][0]
            self.assertEqual(imported["prompt"]["processed"], "A detailed cat.")
            self.assertEqual(imported["prompt"]["processed_kind"], "expanded")
            self.assertEqual(imported["prompt"]["output_kind"], "positive_prompt")
            self.assertEqual(imported["status"], "completed")
            self.assertTrue(imported["appended"])
            self.assertEqual(imported["booru"]["site"], "danbooru")
            self.assertEqual(imported["image"]["source_url"], "https://example.invalid/post/1")
            self.assertEqual(imported["source_identity"], "tags:cat")

    def test_deduplication_keeps_contiguous_record_indexes(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.png"
            second = Path(directory) / "second.png"
            write_test_png(first, "cat")
            write_test_png(second, "dog")

            batch = build_prompt_batch([(first, "cat"), (first, "cat"), (second, "dog")])

            self.assertEqual([record["index"] for record in batch["records"]], [1, 2])
            self.assertEqual(import_prompt_batch(batch), batch)

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
