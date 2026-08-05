from __future__ import annotations

import os
import tempfile
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from PIL import Image

from .core import extract_positive_prompt


@dataclass(frozen=True)
class ImportResult:
    selected_count: int
    imported_count: int
    skipped_count: int
    errors: tuple[str, ...]
    records: tuple[tuple[Path, str], ...] = ()


SCHEMA_VERSION = "prompt_batch.v1"
PRODUCER_NAME = "sd-webui-png-prompt-collector"
MAX_PROMPT_LENGTH = 12_000


def build_prompt_batch(records: Iterable[tuple[Path, str]], deduplicate: bool = True) -> dict[str, Any]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    digest_occurrences: dict[str, int] = {}
    digest_cache: dict[Path, str] = {}
    for index, (path, prompt) in enumerate(records, 1):
        image_path = Path(path)
        digest = digest_cache.get(image_path)
        if digest is None:
            digest = _sha256_file(image_path)
            digest_cache[image_path] = digest
        if deduplicate and digest in seen:
            continue
        positive = str(prompt).strip()
        if not positive:
            continue
        seen.add(digest)
        digest_occurrences[digest] = digest_occurrences.get(digest, 0) + 1
        if len(positive) > MAX_PROMPT_LENGTH:
            raise ValueError(f"{image_path.name} 的 Prompt 超过 {MAX_PROMPT_LENGTH} 字符")
        output.append(
            {
                "record_id": f"png-{digest}-{digest_occurrences[digest]}",
                "index": index,
                "image": {"filename": image_path.name, "sha256": digest},
                "prompt": {"positive": positive},
            }
        )
    return {"schema_version": SCHEMA_VERSION, "producer": {"name": PRODUCER_NAME}, "records": output}


def export_prompt_batch(batch: dict[str, Any]) -> str:
    batch = import_prompt_batch(batch)
    content = json.dumps(batch, ensure_ascii=False, indent=2) + "\n"
    handle, filename = tempfile.mkstemp(prefix="prompt_batch_", suffix=".json")
    os.close(handle)
    Path(filename).write_text(content, encoding="utf-8")
    return filename


def import_prompt_batch(value: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        payload = value
    else:
        path = Path(value)
        payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON 顶层必须是对象")
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("仅支持 prompt_batch.v1 JSON")
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("records 必须是数组")
    normalized: list[dict[str, Any]] = []
    producer = payload.get("producer") if isinstance(payload.get("producer"), dict) else {}
    producer_name = str(producer.get("name") or PRODUCER_NAME)
    record_ids: set[str] = set()
    for index, record in enumerate(records, 1):
        if not isinstance(record, dict):
            raise ValueError(f"第 {index} 条记录不是对象")
        prompt = record.get("prompt")
        image = record.get("image")
        if not isinstance(prompt, dict) or not isinstance(image, dict):
            raise ValueError(f"第 {index} 条记录缺少 image 或 prompt")
        positive = str(prompt.get("positive") or "").strip()
        if not positive:
            raise ValueError(f"第 {index} 条记录缺少正向 Prompt")
        if len(positive) > MAX_PROMPT_LENGTH:
            raise ValueError(f"第 {index} 条 Prompt 超过 {MAX_PROMPT_LENGTH} 字符")
        filename = Path(str(image.get("filename") or f"record-{index}.png")).name
        record_id = str(record.get("record_id") or "").strip()
        sha256 = str(image.get("sha256") or "")
        if len(filename) > 255 or len(record_id) > 256 or len(sha256) > 128:
            raise ValueError(f"第 {index} 条图片标识过长")
        if sha256 and (len(sha256) != 64 or any(char not in "0123456789abcdefABCDEF" for char in sha256)):
            raise ValueError(f"第 {index} 条 sha256 必须是 64 位十六进制")
        if not record_id:
            identity = f"{producer_name}\x1f{sha256}\x1f{filename}\x1f{positive}"
            record_id = f"generated-{hashlib.sha256(identity.encode('utf-8')).hexdigest()}"
        if record_id in record_ids:
            raise ValueError(f"第 {index} 条 record_id 重复: {record_id}")
        record_ids.add(record_id)
        normalized_prompt = {"positive": positive}
        natural = str(prompt.get("natural") or "").strip()
        if natural:
            if len(natural) > MAX_PROMPT_LENGTH:
                raise ValueError(f"第 {index} 条自然语言 Prompt 超过 {MAX_PROMPT_LENGTH} 字符")
            normalized_prompt["natural"] = natural
        processed = str(prompt.get("processed") or "").strip()
        if processed:
            if len(processed) > MAX_PROMPT_LENGTH:
                raise ValueError(f"第 {index} 条处理结果超过 {MAX_PROMPT_LENGTH} 字符")
            normalized_prompt["processed"] = processed
        normalized_image = {"filename": filename, "sha256": sha256}
        for field in ("source_url", "preview_url"):
            if image.get(field):
                normalized_image[field] = str(image[field])
        normalized_record = {
            "record_id": record_id,
            "index": index,
            "image": normalized_image,
            "prompt": normalized_prompt,
        }
        for field in ("status", "error", "booru"):
            if field in record:
                normalized_record[field] = record[field]
        if record.get("appended") is True:
            normalized_record["appended"] = True
        normalized.append(normalized_record)
    return {
        "schema_version": SCHEMA_VERSION,
        "producer": {"name": producer_name},
        "records": normalized,
    }


def collect_positive_prompts(
    uploaded_files: Any = None,
    directory: str | None = None,
    recursive: bool = False,
) -> ImportResult:
    paths, discovery_errors = discover_png_paths(uploaded_files, directory, recursive)
    entries: list[tuple[str, str]] = []
    errors = list(discovery_errors)

    for path in paths:
        try:
            prompt = read_positive_prompt(path)
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        if not prompt:
            errors.append(f"{path.name}: 未找到可读取的正向提示词")
            continue
        entries.append((str(path), prompt))

    return ImportResult(
        selected_count=len(paths),
        imported_count=len(entries),
        skipped_count=len(paths) - len(entries),
        errors=tuple(errors),
        records=tuple((Path(source), prompt) for source, prompt in entries),
    )


def discover_png_paths(
    uploaded_files: Any = None,
    directory: str | None = None,
    recursive: bool = False,
) -> tuple[list[Path], tuple[str, ...]]:
    candidates: list[Path] = []
    errors: list[str] = []

    for value in _as_file_values(uploaded_files):
        path = _path_from_file_value(value)
        if path is None:
            errors.append("上传项缺少有效文件路径")
        elif path.suffix.lower() != ".png":
            errors.append(f"{path.name}: 仅支持 PNG 文件")
        else:
            candidates.append(path)

    directory_text = str(directory or "").strip().strip('"')
    if directory_text:
        root = Path(directory_text).expanduser()
        if not root.is_dir():
            errors.append(f"目录不存在或不可读取: {root}")
        else:
            iterator: Iterable[Path] = root.rglob("*") if recursive else root.iterdir()
            candidates.extend(path for path in iterator if path.is_file() and path.suffix.lower() == ".png")

    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = os.path.normcase(str(path.resolve(strict=False)))
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique, tuple(errors)


def read_positive_prompt(path: str | Path) -> str:
    image_path = Path(path)
    with Image.open(image_path) as image:
        image.load()
        infotext = _read_webui_infotext(image)
        if not infotext:
            infotext = _read_raw_infotext(image)

    return extract_positive_prompt(infotext)


def _read_webui_infotext(image: Image.Image) -> str | None:
    try:
        from modules import images

        infotext, _ = images.read_info_from_image(image)
        return str(infotext) if infotext else None
    except Exception:
        return None


def _read_raw_infotext(image: Image.Image) -> str | None:
    info = dict(image.info or {})
    parameters = info.get("parameters")
    if parameters:
        return str(parameters)

    if info.get("Software") == "NovelAI" and info.get("Description"):
        return str(info["Description"])

    converted = _convert_comfy_metadata(info, image)
    if converted:
        return converted

    description = info.get("Description") or info.get("description")
    return str(description) if description else None


def _convert_comfy_metadata(info: dict[str, Any], image: Image.Image) -> str | None:
    if not (info.get("prompt") or info.get("workflow")):
        return None
    try:
        from comfyui_pnginfo.parser import convert_info_to_infotext

        converted = convert_info_to_infotext(info, image_size=(image.width, image.height))
        return converted.infotext if converted else None
    except Exception:
        return None


def _as_file_values(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _path_from_file_value(value: Any) -> Path | None:
    if isinstance(value, (str, os.PathLike)):
        return Path(value)
    if isinstance(value, dict):
        path = value.get("path") or value.get("name")
        return Path(path) if path else None
    name = getattr(value, "name", None)
    return Path(name) if name else None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
