from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Iterable


NEGATIVE_PROMPT_RE = re.compile(r"(?im)^\s*negative\s+prompt\s*:")
POSITIVE_PROMPT_RE = re.compile(r"(?i)^\s*positive\s+prompt\s*:\s*")
PARAMETER_RE = re.compile(
    r"(?:^|,\s*)(?:Steps|Sampler|Schedule type|CFG scale|Seed|Size|Model|"
    r"Model hash|Clip skip|VAE|Denoising strength|Hires steps)\s*:",
    re.IGNORECASE,
)
WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class TagSummary:
    tag: str
    occurrences: int
    source_count: int


@dataclass(frozen=True)
class CollectionResult:
    tags: tuple[str, ...]
    summaries: tuple[TagSummary, ...]
    prompt_count: int
    total_occurrences: int
    duplicates_removed: int

    @property
    def text(self) -> str:
        return ", ".join(self.tags)


def extract_positive_prompt(infotext: str | None) -> str:
    """Return only the positive prompt portion of an A1111-style infotext."""
    if not infotext:
        return ""

    text = str(infotext).replace("\ufeff", "").strip()
    negative_match = NEGATIVE_PROMPT_RE.search(text)
    if negative_match:
        text = text[: negative_match.start()]

    lines = text.rstrip().splitlines()
    while lines and _looks_like_parameter_line(lines[-1]):
        lines.pop()

    positive = "\n".join(lines).strip()
    return POSITIVE_PROMPT_RE.sub("", positive, count=1).strip()


def split_prompt_tags(prompt: str | None) -> list[str]:
    """Split comma-separated tags without breaking nested prompt syntax."""
    if not prompt:
        return []

    closing_for = {"(": ")", "[": "]", "{": "}", "<": ">"}
    closing_chars = set(closing_for.values())
    stack: list[str] = []
    quote: str | None = None
    escaped = False
    current: list[str] = []
    tags: list[str] = []

    for char in str(prompt):
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            current.append(char)
            escaped = True
            continue
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
            current.append(char)
            continue
        if char in closing_for:
            stack.append(closing_for[char])
            current.append(char)
            continue
        if char in closing_chars:
            if stack and char == stack[-1]:
                stack.pop()
            current.append(char)
            continue
        if char == "," and not stack:
            _append_tag(tags, current)
            current = []
            continue
        current.append(char)

    _append_tag(tags, current)
    return tags


def aggregate_prompts(
    entries: Iterable[tuple[str, str]],
    *,
    deduplicate: bool = True,
    case_sensitive: bool = False,
) -> CollectionResult:
    """Aggregate tags in first-seen order and retain frequency information."""
    stats: OrderedDict[str, dict[str, object]] = OrderedDict()
    output_tags: list[str] = []
    prompt_count = 0
    total_occurrences = 0

    for source, prompt in entries:
        tags = split_prompt_tags(prompt)
        if not tags:
            continue
        prompt_count += 1

        for tag in tags:
            total_occurrences += 1
            key = tag if case_sensitive else tag.casefold()
            record = stats.get(key)
            if record is None:
                record = {"tag": tag, "occurrences": 0, "sources": set()}
                stats[key] = record

            record["occurrences"] = int(record["occurrences"]) + 1
            sources = record["sources"]
            assert isinstance(sources, set)
            sources.add(source)

            if not deduplicate or int(record["occurrences"]) == 1:
                output_tags.append(tag)

    summaries = tuple(
        TagSummary(
            tag=str(record["tag"]),
            occurrences=int(record["occurrences"]),
            source_count=len(record["sources"]),
        )
        for record in stats.values()
    )
    return CollectionResult(
        tags=tuple(output_tags),
        summaries=summaries,
        prompt_count=prompt_count,
        total_occurrences=total_occurrences,
        duplicates_removed=total_occurrences - len(output_tags),
    )


def _looks_like_parameter_line(line: str) -> bool:
    return len(PARAMETER_RE.findall(line)) >= 2


def _append_tag(tags: list[str], characters: list[str]) -> None:
    tag = WHITESPACE_RE.sub(" ", "".join(characters)).strip()
    if tag:
        tags.append(tag)

