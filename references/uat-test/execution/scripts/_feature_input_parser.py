"""Shared parsing utilities for TR-level feature input syntax.

Supports bracket notation: Feature_Name[TR1-TR3,TR5-TR7,TR10]
"""

from __future__ import annotations

import re
from typing import NamedTuple


class FeatureSpec(NamedTuple):
    stem: str
    tr_filter: list[int] | None


_BRACKET_RE = re.compile(r"^([^\[\]]+)\[([^\]]*)\]$")
_RANGE_RE = re.compile(r"^TR(\d+)-TR(\d+)$", re.IGNORECASE)
_SINGLE_RE = re.compile(r"^TR(\d+)$", re.IGNORECASE)


def normalize_feature_stem(s: str) -> str:
    """Strip common suffixes (_TRs, _trs, .md) from a feature stem."""
    s = s.strip()
    for suf in ("_TRs", "_trs", ".md"):
        if s.endswith(suf):
            s = s[: -len(suf)]
    return s.strip()


def parse_feature_spec(raw: str) -> FeatureSpec:
    """Parse 'Feature[TR1-TR3,TR5]' into FeatureSpec(stem, [1,2,3,5]).

    Without brackets, returns tr_filter=None (all TRs).
    Empty brackets 'Feature[]' also returns tr_filter=None.
    """
    raw = raw.strip()
    m = _BRACKET_RE.match(raw)
    if not m:
        return FeatureSpec(stem=normalize_feature_stem(raw), tr_filter=None)
    stem = normalize_feature_stem(m.group(1))
    bracket_content = m.group(2).strip()
    if not bracket_content:
        return FeatureSpec(stem=stem, tr_filter=None)
    parts = [p.strip() for p in bracket_content.split(",")]
    trs: set[int] = set()
    for part in parts:
        rm = _RANGE_RE.match(part)
        if rm:
            lo, hi = int(rm.group(1)), int(rm.group(2))
            if lo > hi:
                raise ValueError(f"Invalid TR range (start > end): {part!r}")
            trs.update(range(lo, hi + 1))
            continue
        sm = _SINGLE_RE.match(part)
        if sm:
            trs.add(int(sm.group(1)))
            continue
        raise ValueError(f"Invalid TR spec: {part!r}")
    return FeatureSpec(stem=stem, tr_filter=sorted(trs))


def format_feature_spec(stem: str, tr_numbers: list[int] | None) -> str:
    """Reconstruct bracket syntax with range compression.

    format_feature_spec("Feat", [1,2,3,5,6,10]) -> "Feat[TR1-TR3,TR5-TR6,TR10]"
    format_feature_spec("Feat", None) -> "Feat"
    """
    if not tr_numbers:
        return stem
    parts: list[str] = []
    i = 0
    nums = sorted(tr_numbers)
    while i < len(nums):
        start = nums[i]
        end = start
        while i + 1 < len(nums) and nums[i + 1] == end + 1:
            i += 1
            end = nums[i]
        if start == end:
            parts.append(f"TR{start}")
        else:
            parts.append(f"TR{start}-TR{end}")
        i += 1
    return f"{stem}[{','.join(parts)}]"


def split_features_bracket_aware(text: str) -> list[str]:
    """Split comma/newline-separated feature specs, respecting brackets.

    Commas inside [] are NOT treated as separators.
    """
    out: list[str] = []
    for line in (text or "").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        depth = 0
        current: list[str] = []
        for ch in s:
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth = max(0, depth - 1)
            elif ch == "," and depth == 0:
                item = "".join(current).strip()
                if item and not item.startswith("#"):
                    out.append(item)
                current = []
                continue
            current.append(ch)
        item = "".join(current).strip()
        if item and not item.startswith("#"):
            out.append(item)
    return out
