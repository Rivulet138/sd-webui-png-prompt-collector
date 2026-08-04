from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from PIL import Image

from .core import CollectionResult, aggregate_prompts, extract_positive_prompt


MAX_IMAGE_FILES = 10_000


@dataclass(frozen=True)
class ImportResult:
    collection: CollectionResult
    selected_count: int
    imported_count: int
    skipped_count: int
    errors: tuple[str, ...]


def collect_positive_prompts(
    uploaded_files: Any = None,
    directory: str | None = None,
    recursive: bool = False,
    deduplicate: bool = True,
    ignore_case: bool = True,
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

    collection = aggregate_prompts(
        entries,
        deduplicate=deduplicate,
        case_sensitive=not ignore_case,
    )
    return ImportResult(
        collection=collection,
        selected_count=len(paths),
        imported_count=len(entries),
        skipped_count=len(paths) - len(entries),
        errors=tuple(errors),
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
        if len(unique) == MAX_IMAGE_FILES:
            errors.append(f"文件数量超过上限，仅处理前 {MAX_IMAGE_FILES} 张 PNG")
            break

    return unique, tuple(errors)


def read_positive_prompt(path: str | Path) -> str:
    image_path = Path(path)
    with Image.open(image_path) as image:
        image.load()
        infotext = _read_webui_infotext(image)
        if not infotext:
            infotext = _read_raw_infotext(image)

    return extract_positive_prompt(infotext)


def write_export_file(text: str) -> str | None:
    if not text.strip():
        return None

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    descriptor, filename = tempfile.mkstemp(prefix=f"positive_prompt_tags_{timestamp}_", suffix=".txt")
    os.close(descriptor)
    Path(filename).write_text(text.rstrip() + "\n", encoding="utf-8")
    return filename


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

