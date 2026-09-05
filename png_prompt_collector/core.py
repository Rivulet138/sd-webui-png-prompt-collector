from __future__ import annotations

import re


NEGATIVE_PROMPT_RE = re.compile(r"(?im)^\s*negative\s+prompt\s*:")
POSITIVE_PROMPT_RE = re.compile(r"(?i)^\s*positive\s+prompt\s*:\s*")
PARAMETER_RE = re.compile(
    r"(?:^|,\s*)(?:Steps|Sampler|Schedule type|CFG scale|Seed|Size|Model|"
    r"Model hash|Clip skip|VAE|Denoising strength|Hires steps)\s*:",
    re.IGNORECASE,
)
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


def _looks_like_parameter_line(line: str) -> bool:
    matches = PARAMETER_RE.findall(line)
    if len(matches) >= 2:
        return True
    # A1111/Forge may emit a single generation parameter (for example
    # ``Steps: 20``). Only treat a one-field line as metadata when the whole
    # line is a parameter pair; a prompt containing ``Seed:`` must remain.
    return len(matches) == 1 and bool(re.fullmatch(
        r"\s*(?:Steps|Sampler|Schedule type|CFG scale|Seed|Size|Model|"
        r"Model hash|Clip skip|VAE|Denoising strength|Hires steps)\s*:\s*.+\s*",
        line,
        re.IGNORECASE,
    ))
